###############################################################################
# Pulse Induction Metal Detector, v4.06, coil v4
# Runs on RP2040 dev board (Waveshare RP2040-Zero, MicroPython)
#
# Interfaces to LTC2508-32 ADC:
#   SPI1 / filtered 32-bit (SDOA/SCKA/DRL, GPIO8/10/9)  — Mode 1
#   SPI0 / raw 14-bit     (SDOB/SCKB/BUSY, GPIO0/2/15)  — Mode 2
#
# Mode 1  — filtered/interrupt-driven acquisition
#   S/s  start streaming '*' telemetry
#   E/e  stop (shared with Mode 2)
#   *<freq_kHz>,<pulse_us>,<delay_us>,<downsample>  configure
#   output: *<time_ms>,<value_uV>,<stddev_uV>,<freq_kHz>,<pulse_us>,<delay_us>,<downsample>
#   rate: pulse_freq / downsample (e.g. ~20/s at 5 kHz / 256)
#
# Mode 2  — raw interleaved moving-average sweep (see PROFILES table)
#   Q<n>  select profile n (default 0)
#   G/g   start streaming 'W' telemetry
#   E/e   stop (shared)
#   output: W<profile_idx>,<time_ms>,<mean_ch0>,<mean_ch1>,...
#   rate: min(100 Hz, profile_freq / (n_pulses * n_delays))
#
# Other commands (both modes):
#   A<n>  acquire N boxcar-averaged raw samples at held config (Mode 1 or idle only)
#   V/v/? identify -> V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_kHz>,<pulse_us>,<delay_us>,<downsample>
#   L     list profiles -> one L<idx>,<freq_kHz>,<n_pulses>,<n_delays>,<averages>,<name> line each
#
# v4.00 complete serial protocol rewrite (two non-concurrent modes, W streaming,
#       Q/G commands, file renamed from pimd_mcu_302.py to pimd_mcu.py)
# v4.01 acquire_mode2: CC written first at period start (~1-2 us) before SPI read
#       — eliminates CC-write race on multi-cell profiles; precompute cell_duties;
#       prime now fires cell[n-1] (removes startup transient in rolling[n-1]);
#       command poll moved out of W-emit gate ('E' stops within one n_pulses*n_delays cycle)
# v4.02 acquire_raw_average: discard first 5 samples (priming) so PWM wrap-register
#       glitch after freq change settles before the averaged window begins; fixes
#       near-zero readings on A<n> when frequency changes between * commands
# v4.03 profile structure changed from {freq_hz, pulses_us, delays_us} to
#       {bands: [(freq_hz, pulse_us, delays_us)…]} so each band can have its own
#       frequency; acquire_mode2 updates the PWM slice freq at band boundaries;
#       new profile 4 CLASSIFY_EP: 5 equal-power bands × 9 calibrated delays = 45 cells
# v4.06 acquire_mode2: add BOUNDARY_PRIME (default 5) extra PWM periods of
#       settling at each band boundary. Root cause of inter-band leakage: the
#       first cell of each new band has only 1 period of drive at the new
#       frequency before its SDOB is read; the previous band's coil energy
#       (especially high-power→low-power transitions like B3→B4) cascades
#       through cells 0–7 of the new band via initial conditions, locking a
#       systematic offset into the rolling average. The last cell (cell 8) of
#       each band reads correctly because its SDOB is read at the start of the
#       next cycle's boundary processing — after a full sweep cycle of settling.
#       Fix: extend the sleep at each boundary by BOUNDARY_PRIME periods so the
#       coil reaches steady state before the first SDOB is taken. Tunable via
#       BOUNDARY_PRIME; overhead ≈ 875 µs/cycle at default 5, emit rate unchanged.
# v4.05 CLASSIFY_EP band frequencies updated to prime-ish actuals from §17.1
#       power table (10601/17599/29201/43003/56992 Hz) — avoids beat-frequency
#       noise, matches the measured equal-power sweep operating points.
# v4.04 acquire_mode2: at band boundaries read SDOB before calling pwm.freq().
#       When freq increases, the new WRAP register is smaller; if the running
#       counter already exceeds the new WRAP, the RP2040 PWM wraps immediately,
#       generating a spurious MCLK falling edge that triggers a new ADC conversion
#       and overwrites the previous cell's result. Fix: read SDOB first at every
#       band boundary, then change freq, preserving CC-write-first for same-band cells.
###############################################################################

# pyright: reportMissingImports=false

import ubinascii
import struct
import select
from sys import stdin
from utime import sleep_ms, sleep_us, ticks_ms, ticks_us, ticks_diff
from machine import Pin, PWM, SPI, unique_id

FW_VERSION = '4.06'
print('Pulse Induction Metal Detector v' + FW_VERSION)
board_id = unique_id()
board_id_hex = ubinascii.hexlify(board_id).upper().decode()
print('On RP2040 Waveshare RP2040-Zero, ID: ' + board_id_hex)

# ---------------------------------------------------------------------------
# PWM — drive (GPIO4 = PWM2A) and sample-trigger (GPIO5 = PWM2B), same slice
# ---------------------------------------------------------------------------
drive_coil_pwm = PWM(Pin(4))
drive_coil_pwm.freq(10000)
drive_coil_pwm.duty_u16(0)

sample_coil_pwm = PWM(Pin(5))
sample_coil_pwm.freq(10000)

# ---------------------------------------------------------------------------
# ADC interfaces
# ---------------------------------------------------------------------------
# Raw 14-bit, no latency (SPI0)
sckb_pin = Pin(2, Pin.OUT)
sdob_pin = Pin(0, Pin.IN)
busy_pin = Pin(15, Pin.IN)
adc_raw_spi = SPI(0, baudrate=10_000_000, sck=sckb_pin, miso=sdob_pin)

# Filtered 32-bit, decimated (SPI1)
scka_pin = Pin(10, Pin.OUT)
sdoa_pin = Pin(8, Pin.IN)
drl_pin = Pin(9, Pin.IN)
adc_filtered_spi = SPI(1, baudrate=10_000_000, sck=scka_pin, miso=sdoa_pin)

ltc2508_sel0 = Pin(12, Pin.OUT)

# ---------------------------------------------------------------------------
# PWM scaling constants
# ---------------------------------------------------------------------------
PWM_SCALING_NUMERATOR = 2 ** 16       # 65536
PWM_SCALING_DENOMINATOR_NS = 10 ** 9  # 1_000_000_000
SAMPLE_PULSE_CORRECTION = 0.752       # µs: measured offset between PWM edge and ADC trigger

# ---------------------------------------------------------------------------
# Raw ADC constants
# ---------------------------------------------------------------------------
RAW_DIFF_SHIFT = 18
RAW_DIFF_MASK = 0x3FFF
RAW_FULL_SCALE_UV = 10_000_000  # ±5 V differential span in µV

# ---------------------------------------------------------------------------
# Mode 2 output rate cap and band-boundary settling
# ---------------------------------------------------------------------------
MIN_EMIT_MS = 10      # emit W records at most every 10 ms (100 Hz max)
BOUNDARY_PRIME = 5    # extra PWM periods to let coil settle after a band-freq change;
                      # increase (try 10, 15) if std dev remains elevated in high-freq bands

# ---------------------------------------------------------------------------
# Signal parameters — held config for Mode 1 / A<x> / * command
# ---------------------------------------------------------------------------
pulse_width_us = 10.0
sample_delay_us = 10.0
sample_frequency_hz = 10000
down_sample = 256

# ---------------------------------------------------------------------------
# Filtered-path acquisition state (Mode 1)
# ---------------------------------------------------------------------------
NUM_FILTERED_SAMPLES = 100
filtered_samples = [0] * NUM_FILTERED_SAMPLES
current_filtered_value = 0
drl_ready = False
group_delay = 10
group_delay_counter = group_delay
base_time_ms = ticks_ms()

# ---------------------------------------------------------------------------
# Scan Profiles (fixed, compiled-in — see CLAUDE.md "Control model")
# ---------------------------------------------------------------------------
PROFILES = (
    {   # Profile 0: fast single-point tracking
        'name': 'FAST_TRACK',
        'bands': (
            (5000, 40.0, (8.4,)),
        ),
        'averages': 8,
    },
    {   # Profile 1: 3 pulse widths × 8 log-spaced delays, classification grid
        'name': 'CLASSIFY',
        'bands': (
            (10000,  8.0, (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0)),
            (10000, 20.0, (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0)),
            (10000, 40.0, (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0)),
        ),
        'averages': 32,
    },
    {   # Profile 2: scope-correlated delay sweep, single pulse, averages=1 (no averaging)
        'name': 'SCOPE_CAL',
        'bands': (
            (5000, 10.0, (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0)),
        ),
        'averages': 1,
    },
    {   # Profile 3: single-point 25 kHz tracker
        'name': 'TRACK_25K',
        'bands': (
            (25000, 10.0, (7.6,)),
        ),
        'averages': 16,
    },
    {   # Profile 4: equal-power 5-band classification
        #   5 bands × 9 calibrated delays = 45 cells
        #   Delays are the interpolated sample times (µs) at which the ADC
        #   crosses 4.5/4.0/3.5/3.0/2.5/2.0/1.5/1.0/0.5 V thresholds
        #   (delaycal 2026-06-17, equal-power combinations P ∝ pulse²×freq)
        'name': 'CLASSIFY_EP',
        'bands': (
            (10601, 40.0, ( 8.56,  8.98,  9.37,  9.72, 10.08, 10.49, 10.96, 11.57, 12.53)),
            (17599, 30.0, ( 8.12,  8.54,  8.92,  9.27,  9.63, 10.02, 10.50, 11.10, 12.03)),
            (29201, 20.0, ( 7.62,  8.03,  8.40,  8.75,  9.11,  9.50,  9.96, 10.55, 11.46)),
            (43003, 10.0, ( 6.80,  7.22,  7.58,  7.93,  8.28,  8.66,  9.11,  9.70, 10.57)),
            (56992,  5.0, ( 6.03,  6.43,  6.78,  7.12,  7.46,  7.84,  8.28,  8.85,  9.71)),
        ),
        'averages': 32,
    },
)
NUM_PROFILES = len(PROFILES)    

# ---------------------------------------------------------------------------
# Operational state
# ---------------------------------------------------------------------------
state = 'ready'               # 'ready' | 'mode1_running' | 'mode2_running' | 'stop'
active_profile_index = 0
mode2_profile_changed = False


# ---------------------------------------------------------------------------
# PWM helpers
# ---------------------------------------------------------------------------
def compute_pulse_duties(pulse_width_us, sample_delay_us, sample_frequency_hz):
    """Return (drive_duty, sample_duty) as duty_u16 counts for the given config."""
    pulse_width_ns = int(pulse_width_us * 1000)
    sample_delay_ns = int((sample_delay_us + SAMPLE_PULSE_CORRECTION) * 1000)
    drive_duty = (pulse_width_ns * sample_frequency_hz * PWM_SCALING_NUMERATOR) // PWM_SCALING_DENOMINATOR_NS
    sample_duty = (drive_duty
                   + (sample_delay_ns * sample_frequency_hz * PWM_SCALING_NUMERATOR)
                   // PWM_SCALING_DENOMINATOR_NS)
    return drive_duty, sample_duty


def pulse_duties_valid(drive_duty, sample_duty):
    """True iff both duties fit in 16 bits and sample falls strictly after drive."""
    return 0 <= drive_duty <= 65535 and 0 <= sample_duty <= 65535 and sample_duty > drive_duty


def update_pulse_configuration():
    """Reconfigure PWM from the held Mode 1 globals."""
    global group_delay_counter
    drive_duty, sample_duty = compute_pulse_duties(pulse_width_us, sample_delay_us, sample_frequency_hz)
    group_delay_counter = group_delay
    drive_coil_pwm.freq(sample_frequency_hz)
    sample_coil_pwm.freq(sample_frequency_hz)
    drive_coil_pwm.duty_u16(drive_duty)
    sample_coil_pwm.duty_u16(sample_duty)
    ltc2508_sel0.value(down_sample == 1024)


def validate_profile(profile):
    """Return None if all cells valid; else return first bad (freq_hz, pulse_us, delay_us, dd, sd)."""
    for freq_hz, pulse_us, delays_us in profile['bands']:
        for delay_us in delays_us:
            dd, sd = compute_pulse_duties(pulse_us, delay_us, freq_hz)
            if not pulse_duties_valid(dd, sd):
                return freq_hz, pulse_us, delay_us, dd, sd
    return None


# ---------------------------------------------------------------------------
# Mode 1 — filtered/DRL acquisition
# ---------------------------------------------------------------------------
def filtered_data_callback(pin):
    global drl_ready, group_delay_counter
    if group_delay_counter == 0:
        pin.irq(handler=None)
        drl_ready = True
    else:
        group_delay_counter -= 1


def acquire_filtered_data():
    global current_filtered_value, drl_ready
    drl_ready = False
    drl_pin.irq(trigger=Pin.IRQ_FALLING, handler=filtered_data_callback)
    while not drl_ready:
        sleep_ms(1)
    data_bytes = adc_filtered_spi.read(4)
    current_filtered_value = int(struct.unpack('>i', data_bytes)[0])
    filtered_samples.pop(0)
    filtered_samples.append(current_filtered_value)


def calculate_standard_deviation(data):
    n = len(data)
    mean_value = sum(data) / n
    variance = sum((v - mean_value) ** 2 for v in data) / n
    return variance ** 0.5


def measurement_cycle():
    acquire_filtered_data()
    current_uV = (current_filtered_value * 5_000_000) // (2 ** 31)
    std_raw = int(calculate_standard_deviation(filtered_samples))
    std_uV = (std_raw * 5_000_000) // (2 ** 31)
    elapsed = ticks_diff(ticks_ms(), base_time_ms)
    print('*{0:d}, {1:d}, {2:d}, {3:1.1f}, {4:1.1f}, {5:1.1f}, {6:d}'.format(
        elapsed, current_uV, std_uV,
        sample_frequency_hz / 1000, pulse_width_us, sample_delay_us, down_sample))


# ---------------------------------------------------------------------------
# Raw SPI0 helpers (shared by Mode 2 and A<n>)
# ---------------------------------------------------------------------------
def read_raw_sample():
    """Read one signed 14-bit raw sample from SDOB over SPI0."""
    data_bytes = adc_raw_spi.read(4)
    word = struct.unpack('>I', data_bytes)[0]
    raw14 = (word >> RAW_DIFF_SHIFT) & RAW_DIFF_MASK
    if raw14 & (RAW_DIFF_MASK // 2 + 1):
        raw14 -= RAW_DIFF_MASK + 1
    return raw14


def acquire_raw_average(n_samples):
    """Boxcar-average n_samples raw readings at the current held config. Returns (mean_uV, std_uV)."""
    period_us = 1_000_000 // sample_frequency_hz
    # Prime: discard 5 samples so the PWM wrap-register glitch that follows any
    # freq change (via *) has fully settled before the averaging window opens.
    for _ in range(5):
        read_raw_sample()
        sleep_us(period_us)
    samples = []
    for _ in range(n_samples):
        samples.append(read_raw_sample())
        sleep_us(period_us)
    mean = sum(samples) / n_samples
    variance = sum((s - mean) ** 2 for s in samples) / n_samples
    mean_uV = int(mean * RAW_FULL_SCALE_UV / 2 ** 14)
    std_uV = int((variance ** 0.5) * RAW_FULL_SCALE_UV / 2 ** 14)
    return mean_uV, std_uV


# ---------------------------------------------------------------------------
# Mode 2 — interleaved moving-average sweep
# ---------------------------------------------------------------------------
def acquire_mode2(profile):
    """
    Continuously cycle through all cells in the profile (one PWM period each),
    maintaining a rolling average of depth `averages` per cell. Emits one W record
    per MIN_EMIT_MS ms.
    Returns when state leaves 'mode2_running' or mode2_profile_changed is set.

    Profile structure: each band is (freq_hz, pulse_us, delays_us). Cells are
    enumerated band-major. The PWM slice frequency is updated only at band
    boundaries; within a band only CC (duty) is written each period.

    Timing model:
      Non-boundary cells (CC-write-first): write CC (~2 us), then read SDOB
      (~6-7 us SPI). Minimum trigger ≥ 6 us, so CC precedes any trigger.
      Band-boundary cells (SDOB-first): read SDOB (~7 us), change freq (~4 us,
      counter resets to 0), write CC (~2 us). CC is written ~2 us after counter
      reset; minimum drive trigger ≥ 5 us, so CC still precedes the trigger.

    Prime fires cell[n-1] so iteration i=0 correctly stores the result in
    rolling[(0-1)%n] = rolling[n-1], eliminating the startup transient.
    """
    global mode2_profile_changed

    avg_depth = profile['averages']

    # Flatten bands into a cell list: (freq_hz, period_us, drive_duty, sample_duty)
    cells = []
    for freq_hz, pulse_us, delays_us in profile['bands']:
        period_us = 1_000_000 // freq_hz
        for delay_us in delays_us:
            dd, sd = compute_pulse_duties(pulse_us, delay_us, freq_hz)
            cells.append((freq_hz, period_us, dd, sd))

    n = len(cells)
    rolling = [[] for _ in range(n)]

    # Prime: fire cell[n-1] so that iteration i=0 stores the result in
    # rolling[(0-1)%n] = rolling[n-1] with no startup transient.
    f_last, p_last, dd_last, sd_last = cells[n - 1]
    drive_coil_pwm.freq(f_last)
    sample_coil_pwm.freq(f_last)
    drive_coil_pwm.duty_u16(dd_last)
    sample_coil_pwm.duty_u16(sd_last)
    sleep_us(p_last)

    last_emit_ms = ticks_ms()
    mode2_profile_changed = False

    while state == 'mode2_running' and not mode2_profile_changed:
        for i in range(n):
            t0 = ticks_us()

            freq_i, period_i, dd, sd = cells[i]
            prev = (i - 1) % n
            at_boundary = freq_i != cells[prev][0]

            # At band boundaries: read SDOB BEFORE calling pwm.freq().
            # When freq increases, the RP2040 shrinks the PWM WRAP register;
            # if the running counter already exceeds the new WRAP it wraps
            # immediately, generating a spurious MCLK falling edge that starts
            # a new ADC conversion and corrupts the previous cell's result.
            # Reading first avoids this race. (Decreasing-freq boundaries are
            # also read first for uniformity — they cannot wrap spuriously but
            # early reads are always safe.)
            if at_boundary:
                raw = read_raw_sample()
                rolling[prev].append(raw)
                if len(rolling[prev]) > avg_depth:
                    rolling[prev].pop(0)
                drive_coil_pwm.freq(freq_i)
                sample_coil_pwm.freq(freq_i)

            # Write CC for cell[i] — must precede the next drive/sample trigger.
            drive_coil_pwm.duty_u16(dd)
            sample_coil_pwm.duty_u16(sd)

            # Non-boundary: read SDOB after CC write (CC-write-first timing preserved).
            if not at_boundary:
                raw = read_raw_sample()
                rolling[prev].append(raw)
                if len(rolling[prev]) > avg_depth:
                    rolling[prev].pop(0)

            # Sleep out the remainder of this cell's period.
            # At band boundaries add BOUNDARY_PRIME extra periods so the coil
            # reaches steady state at the new frequency before the next cell
            # reads this cell's SDOB, breaking the contamination cascade.
            elapsed = ticks_diff(ticks_us(), t0)
            remaining = period_i - elapsed - 2
            if at_boundary:
                remaining += period_i * BOUNDARY_PRIME
            if remaining > 0:
                sleep_us(remaining)

        # After each complete cycle: maybe emit W record; always poll commands.
        now = ticks_ms()
        if ticks_diff(now, last_emit_ms) >= MIN_EMIT_MS:
            means = []
            for buf in rolling:
                if buf:
                    mean_uV = int(sum(buf) / len(buf) * RAW_FULL_SCALE_UV / 2 ** 14)
                else:
                    mean_uV = 0
                means.append(mean_uV)
            elapsed_ms = ticks_diff(now, base_time_ms)
            fields = ['W{0:d}'.format(active_profile_index), '{0:d}'.format(elapsed_ms)]
            fields += ['{0:d}'.format(m) for m in means]
            print(','.join(fields))
            last_emit_ms = now
        check_for_commands(timeout_ms=0)


# ---------------------------------------------------------------------------
# Safe state
# ---------------------------------------------------------------------------
def set_safe_state():
    drive_coil_pwm.duty_u16(0)
    sample_coil_pwm.duty_u16(2 ** 16 - 1)
    drl_pin.irq(handler=None)
    print('SAFE: Drive OFF / Sampling OFF / Interrupts OFF')


# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------
def check_for_commands(timeout_ms=1):
    """
    Poll stdin for one command. timeout_ms=0 for non-blocking (used in Mode 2 loop).

    Mode 1 commands:
      S/s  start Mode 1 streaming
      E/e  stop (either mode)
      *<freq_kHz>,<pulse_us>,<delay_us>,<downsample>  configure held parameters
      A<x> acquire x boxcar-averaged raw samples (idle or Mode 1 only)

    Mode 2 commands:
      Q<n> select profile n
      G/g  start Mode 2 streaming
      E/e  stop (either mode)

    Common:
      V/v/? identify
      L     list profiles
    """
    global state, sample_frequency_hz, pulse_width_us, sample_delay_us, down_sample
    global active_profile_index, mode2_profile_changed

    try:
        if not serial_poll.poll(timeout_ms):
            return
        line = stdin.readline()
        if not line:
            return
        cmd = line[0]

        if cmd in ('S', 's'):
            if state == 'mode2_running':
                print('Command Input ERROR: S rejected while Mode 2 running (send E first)')
                return
            state = 'mode1_running'
            update_pulse_configuration()

        elif cmd in ('E', 'e'):
            state = 'stop'

        elif cmd in ('G', 'g'):
            if state == 'mode1_running':
                print('Command Input ERROR: G rejected while Mode 1 running (send E first)')
                return
            if not 0 <= active_profile_index < NUM_PROFILES:
                print('Command Input ERROR: no valid profile selected (use Q<n> first)')
                return
            invalid = validate_profile(PROFILES[active_profile_index])
            if invalid:
                print('Command Input ERROR: profile {0} has invalid cell '
                      '(freq={1:.0f}Hz, pw={2:.1f}us, delay={3:.1f}us)'.format(
                          active_profile_index, invalid[0], invalid[1], invalid[2]))
                return
            state = 'mode2_running'

        elif cmd in ('Q', 'q'):
            try:
                idx = int(line[1:])
            except ValueError:
                idx = -1
            if not 0 <= idx < NUM_PROFILES:
                print('Command Input ERROR: invalid profile index (Q{0})'.format(line[1:].strip()))
                return
            invalid = validate_profile(PROFILES[idx])
            if invalid:
                print('Command Input ERROR: profile {0} has invalid cell '
                      '(freq={1:.0f}Hz, pw={2:.1f}us, delay={3:.1f}us)'.format(
                          idx, invalid[0], invalid[1], invalid[2]))
                return
            active_profile_index = idx
            print('Q{0} OK: {1}'.format(idx, PROFILES[idx]['name']))
            if state == 'mode2_running':
                mode2_profile_changed = True  # signals acquire_mode2 to restart

        elif cmd == '*':
            if state == 'mode2_running':
                print('Command Input ERROR: * rejected while Mode 2 running (send E first)')
                return
            parts = line[1:].split(',')
            new_freq_hz = int(1000 * float(parts[0]))
            new_pulse_us = float(parts[1])
            new_delay_us = float(parts[2])
            new_down = int(parts[3])
            dd, sd = compute_pulse_duties(new_pulse_us, new_delay_us, new_freq_hz)
            if pulse_duties_valid(dd, sd):
                sample_frequency_hz = new_freq_hz
                pulse_width_us = new_pulse_us
                sample_delay_us = new_delay_us
                down_sample = new_down
                update_pulse_configuration()
            else:
                print('Command Input ERROR: rejected pulse config '
                      '(drive_duty={0}, sample_duty={1})'.format(dd, sd))

        elif cmd in ('A', 'a'):
            if state == 'mode2_running':
                print('Command Input ERROR: A rejected while Mode 2 running (send E first)')
                return
            try:
                n_samples = int(line[1:])
            except ValueError:
                n_samples = 0
            if not 1 <= n_samples <= 1000:
                print('Command Input ERROR: invalid count (A{0})'.format(line[1:].strip()))
                return
            dd, sd = compute_pulse_duties(pulse_width_us, sample_delay_us, sample_frequency_hz)
            if not pulse_duties_valid(dd, sd):
                print('Command Input ERROR: current config invalid for A<n>')
                return
            mean_uV, std_uV = acquire_raw_average(n_samples)
            elapsed = ticks_diff(ticks_ms(), base_time_ms)
            print('R{0:d}, {1:d}, {2:d}, {3:d}, {4:.1f}, {5:.1f}, {6:.1f}'.format(
                elapsed, mean_uV, std_uV, n_samples,
                sample_frequency_hz / 1000, pulse_width_us, sample_delay_us))

        elif cmd in ('V', 'v', '?'):
            print('V{0},{1},{2},{3},{4:.1f},{5:.1f},{6:.1f},{7:d}'.format(
                FW_VERSION, board_id_hex, NUM_PROFILES, active_profile_index,
                sample_frequency_hz / 1000, pulse_width_us, sample_delay_us, down_sample))

        elif cmd == 'L':
            for idx, p in enumerate(PROFILES):
                n_bands = len(p['bands'])
                n_cells = sum(len(d) for _, _, d in p['bands'])
                first_freq_khz = p['bands'][0][0] / 1000
                print('L{0:d},{1:.1f},{2:d},{3:d},{4:d},{5}'.format(
                    idx, first_freq_khz, n_bands, n_cells, p['averages'], p['name']))

        else:
            print('Command Input ERROR: unknown command')

    except Exception as e:
        print('Command Input EXCEPTION:', e)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
print('Ready')

serial_poll = select.poll()
serial_poll.register(stdin, select.POLLIN)

try:
    while True:
        check_for_commands()
        if state == 'mode1_running':
            measurement_cycle()
        elif state == 'mode2_running':
            acquire_mode2(PROFILES[active_profile_index])
        elif state == 'stop':
            set_safe_state()
            state = 'ready'
except KeyboardInterrupt:
    print('\nTerminating')
    drive_coil_pwm.duty_u16(0)
finally:
    set_safe_state()
    print()
