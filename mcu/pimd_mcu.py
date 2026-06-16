###############################################################################
# Pulse Induction Metal Detector, v4.01, coil v4
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
#   rate: min(100 Hz, profile_freq / (z*y))
#
# Other commands (both modes):
#   A<x>  acquire x boxcar-averaged raw samples at held config (Mode 1 or idle only)
#   V/v/? identify -> V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_kHz>,<pulse_us>,<delay_us>,<downsample>
#   L     list profiles -> one L<idx>,<freq_kHz>,<z>,<y>,<x>,<name> line each
#
# v4.00 complete serial protocol rewrite (two non-concurrent modes, W streaming,
#       Q/G commands, file renamed from pimd_mcu_302.py to pimd_mcu.py)
###############################################################################

# pyright: reportMissingImports=false

import ubinascii
import struct
import select
from sys import stdin
from utime import sleep_ms, sleep_us, ticks_ms, ticks_us, ticks_diff
from machine import Pin, PWM, SPI, unique_id

FW_VERSION = '4.00'
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
# Mode 2 output rate cap
# ---------------------------------------------------------------------------
MIN_EMIT_MS = 10  # emit W records at most every 10 ms (100 Hz max)

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
        'freq_hz': 5000,
        'pulses_us': (40.0,),
        'delays_us': (8.4,),
        'x': 8,
    },
    {   # Profile 1: 3 pulse widths x 8 log-spaced delays, classification grid
        'name': 'CLASSIFY',
        'freq_hz': 10000,
        'pulses_us': (8.0, 20.0, 40.0),
        'delays_us': (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0),
        'x': 32,
    },
    {   # Profile 2: scope-correlated delay sweep, single pulse, x=1 (no averaging)
        'name': 'SCOPE_CAL',
        'freq_hz': 5000,
        'pulses_us': (10.0,),
        'delays_us': (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0),
        'x': 1,
    },
    {   # Profile 3: single-point 25 kHz tracker — correlate raw vs old filtered system
        'name': 'TRACK_25K',
        'freq_hz': 25000,
        'pulses_us': (10.0,),
        'delays_us': (7.6,),
        'x': 16,
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
    """Return None if all cells are valid; else return first bad (pulse, delay, dd, sd)."""
    for pulse in profile['pulses_us']:
        for delay in profile['delays_us']:
            dd, sd = compute_pulse_duties(pulse, delay, profile['freq_hz'])
            if not pulse_duties_valid(dd, sd):
                return pulse, delay, dd, sd
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
    variance = sum((x - mean_value) ** 2 for x in data) / n
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
# Raw SPI0 helpers (shared by Mode 2 and A<x>)
# ---------------------------------------------------------------------------
def read_raw_sample():
    """Read one signed 14-bit raw sample from SDOB over SPI0."""
    data_bytes = adc_raw_spi.read(4)
    word = struct.unpack('>I', data_bytes)[0]
    raw14 = (word >> RAW_DIFF_SHIFT) & RAW_DIFF_MASK
    if raw14 & (RAW_DIFF_MASK // 2 + 1):
        raw14 -= RAW_DIFF_MASK + 1
    return raw14


def acquire_raw_average(x):
    """Boxcar-average x raw samples at the current held config. Returns (mean_uV, std_uV)."""
    period_us = 1_000_000 // sample_frequency_hz
    samples = []
    for _ in range(x):
        samples.append(read_raw_sample())
        sleep_us(period_us)
    mean = sum(samples) / x
    variance = sum((s - mean) ** 2 for s in samples) / x
    mean_uV = int(mean * RAW_FULL_SCALE_UV / 2 ** 14)
    std_uV = int((variance ** 0.5) * RAW_FULL_SCALE_UV / 2 ** 14)
    return mean_uV, std_uV


# ---------------------------------------------------------------------------
# Mode 2 — interleaved moving-average sweep
# ---------------------------------------------------------------------------
def acquire_mode2(profile):
    """
    Continuously cycle through all z*y cells at one PWM period each, maintaining
    a rolling average of depth x per cell. Emits one W record per MIN_EMIT_MS ms.
    Returns when state leaves 'mode2_running' or mode2_profile_changed is set.

    Read-first / update-CC-second pattern ensures CC is always written before
    the next trigger fires: all profiles have trigger >= ~13 us from period start,
    SPI read + CC write completes in ~5-7 us, leaving >= 6 us margin.
    """
    global mode2_profile_changed

    freq = profile['freq_hz']
    period_us = 1_000_000 // freq
    x_depth = profile['x']

    # Flat cell list: pulse-width-major (z outer, delay inner)
    cells = [(p, d) for p in profile['pulses_us'] for d in profile['delays_us']]
    n = len(cells)

    # Per-cell rolling buffers (raw 14-bit signed integers)
    rolling = [[] for _ in range(n)]

    # Set slice frequency once (both channels share the same slice)
    drive_coil_pwm.freq(freq)
    sample_coil_pwm.freq(freq)

    # Prime pipeline: configure cell[0] trigger and wait one full period
    dd0, sd0 = compute_pulse_duties(cells[0][0], cells[0][1], freq)
    drive_coil_pwm.duty_u16(dd0)
    sample_coil_pwm.duty_u16(sd0)
    sleep_us(period_us)

    last_emit_ms = ticks_ms()
    mode2_profile_changed = False

    while state == 'mode2_running' and not mode2_profile_changed:
        for i in range(n):
            t0 = ticks_us()

            # Step 1: read SDOB — result from cell[(i-1)%n]'s trigger
            raw = read_raw_sample()

            # Step 2: push into previous cell's rolling buffer (cap at x_depth)
            prev = (i - 1) % n
            rolling[prev].append(raw)
            if len(rolling[prev]) > x_depth:
                rolling[prev].pop(0)

            # Step 3: configure PWM for cell[i]'s next trigger
            dd, sd = compute_pulse_duties(cells[i][0], cells[i][1], freq)
            drive_coil_pwm.duty_u16(dd)
            sample_coil_pwm.duty_u16(sd)

            # Step 4: sleep out the remainder of this period
            elapsed = ticks_diff(ticks_us(), t0)
            remaining = period_us - elapsed - 2
            if remaining > 0:
                sleep_us(remaining)

        # After each complete z*y cycle: maybe emit W record and poll commands
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
                      '(pw={1:.1f}, delay={2:.1f})'.format(
                          active_profile_index, invalid[0], invalid[1]))
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
                print('Command Input ERROR: profile {0} has invalid cell'.format(idx))
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
                x = int(line[1:])
            except ValueError:
                x = 0
            if not 1 <= x <= 1000:
                print('Command Input ERROR: invalid count (A{0})'.format(line[1:].strip()))
                return
            dd, sd = compute_pulse_duties(pulse_width_us, sample_delay_us, sample_frequency_hz)
            if not pulse_duties_valid(dd, sd):
                print('Command Input ERROR: current config invalid for A<x>')
                return
            mean_uV, std_uV = acquire_raw_average(x)
            elapsed = ticks_diff(ticks_ms(), base_time_ms)
            print('R{0:d}, {1:d}, {2:d}, {3:d}, {4:.1f}, {5:.1f}, {6:.1f}'.format(
                elapsed, mean_uV, std_uV, x,
                sample_frequency_hz / 1000, pulse_width_us, sample_delay_us))

        elif cmd in ('V', 'v', '?'):
            print('V{0},{1},{2},{3},{4:.1f},{5:.1f},{6:.1f},{7:d}'.format(
                FW_VERSION, board_id_hex, NUM_PROFILES, active_profile_index,
                sample_frequency_hz / 1000, pulse_width_us, sample_delay_us, down_sample))

        elif cmd == 'L':
            for idx, p in enumerate(PROFILES):
                print('L{0:d},{1:.1f},{2:d},{3:d},{4:d},{5}'.format(
                    idx, p['freq_hz'] / 1000,
                    len(p['pulses_us']), len(p['delays_us']), p['x'], p['name']))

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
