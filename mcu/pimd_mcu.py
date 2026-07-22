# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
###############################################################################
# Pulse Induction Metal Detector, v4.26, coil v4
# Runs on RP2040 dev board (Waveshare RP2040-Zero, MicroPython)
#
# Interfaces to LTC2508-32 ADC:
#   SPI1 / filtered 32-bit (SDOA/SCKA/DRL, GPIO8/10/9)  — Mode 1
#   SPI0 / raw 14-bit     (SDOB/SCKB/BUSY, GPIO0/2/15)  — Mode 2
#
# Mode 1  — filtered/interrupt-driven acquisition
#   S/s  start streaming '*' telemetry
#   E/e  stop (shared with Mode 2)
#   *<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>  configure
#   output: *<time_ms>,<value_uV>,<stddev_uV>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>
#   rate: pulse_freq / downsample (e.g. ~20/s at 5 kHz / 256)
#
# Mode 2  — raw interleaved moving-average sweep (see PROFILES table)
#   Q<n>  select profile n (default 0); n == DYNAMIC_PROFILE_INDEX selects the
#         RAM-only profile last defined by D (see below)
#   G/g   start streaming 'W' telemetry
#   E/e   stop (shared)
#   D<averages>;<freq_hz>,<pulse_us>,<d1>,<d2>,...;<freq_hz>,<pulse_us>,<d1>,...;...
#         define the dynamic profile (RAM only, lost on reset). All bands must have
#         the same number of delays. Select it afterwards with Q<DYNAMIC_PROFILE_INDEX>.
#   output: W<profile_idx>,<time_ms>,<mean_ch0>,<mean_ch1>,...
#   rate: min(100 Hz, profile_freq / (n_pulses * n_delays))
#
# Other commands (both modes):
#   A<n>  acquire N boxcar-averaged raw samples at held config (Mode 1 or idle only)
#         -> R<time_ms>,<mean_uV>,<std_uV>,<n>,<freq_hz>,<pulse_ns>,<delay_ns>,<min_uV>,<max_uV>
#   V/v/? identify -> V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>
#   L     list profiles -> one L<idx>,<freq_hz>,<n_pulses>,<n_delays>,<averages>,<name> line each
#

# History (full detail in CHANGELOG.md):
#   v4.26 FIX acquire_mode2: post-emit USB IRQ burst mis-timed cell[i]'s CC write (channel-1 σ)
#   v4.25 FIX acquire_mode2: outlier gate could permanently latch small-signal cells
#   v4.24 FIX acquire_mode2: boundary settling time-floored (SETTLE_FLOOR_US), not period-scaled
#   v4.23 serial protocol: freq in Hz, pulse/delay in ns (exact 8 ns PWM-grid integers)
#   v4.22 SAMPLE_PULSE_CORRECTION 0.908 → 0.904 µs — removes half-step delay dither
#   v4.21 FIX read_raw_sample: IRQ-guard BUSY poll + SPI read; per-cell 10% plausibility gate
#   v4.20 FIX acquire_mode2: BOUNDARY_PRIME 5→15; emit/poll moved inside loop at i==0
#   v4.19 revert v4.18; restore v4.17 BUSY edge sync; SAMPLE_PULSE_CORRECTION 0.908
#   v4.18 FIX read_raw_sample: restore sleep_us pacing + pre/post-read BUSY checks
#   v4.17 FIX read_raw_sample: sync to BUSY edge (high then low), clear of MCLK
#   v4.16 FIX read_raw_sample: wait for BUSY low before clocking SDOB
#   v4.15 acquire_raw_average returns min_uV/max_uV (appended to R record)
#   v4.14 needs_settling fires on pulse-width change; O(1) circular rolling buffers; Mode 2 try/except
#   v4.13 FIX acquire_mode2: non-boundary cells read SDOB before writing CC (cell-swap root cause)
#   v4.12 diagnostic: overrun_count via 'B'
#   v4.11 diagnostic: busy_high_count via 'B'
#   v4.10 comments-only: v4.08/v4.09 A/B-falsified, corrected in place
#   v4.09/v4.08 acquire_mode2 investigation (duty-skip / poll-throttle — both falsified; CC must change)
#   v4.07 add D command: RAM-only dynamic profile; get_profile(idx) single lookup
#   v4.06 acquire_mode2: BOUNDARY_PRIME settling at band boundaries (inter-band leakage)
#   v4.05 CLASSIFY_EP band freqs → prime-ish §17.1 power-table actuals
#   v4.04 acquire_mode2: read SDOB before pwm.freq() at band boundaries (WRAP-glitch race)
#   v4.03 per-band frequency profile structure; profile 4 CLASSIFY_EP (5 bands × 9 delays)
#   v4.02 acquire_raw_average: discard first 5 priming samples after freq change
#   v4.01 acquire_mode2: CC written first at period start; precompute cell_duties; prime cell[n-1]
#   v4.00 complete serial protocol rewrite (two modes, W streaming, Q/G; renamed from pimd_mcu_302.py)
###############################################################################

# pyright: reportMissingImports=false

import ubinascii
import struct
import select
from sys import stdin
from utime import sleep_ms, sleep_us, ticks_ms, ticks_us, ticks_diff
from machine import Pin, PWM, SPI, unique_id, disable_irq, enable_irq

FW_VERSION = '4.26'
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
SAMPLE_PULSE_CORRECTION = 0.904       # µs: measured offset between PWM edge and ADC trigger

# -------------------------------------------------------------------1--------
# Raw ADC constants
# ---------------------------------------------------------------------------
RAW_DIFF_SHIFT = 18
RAW_DIFF_MASK = 0x3FFF
RAW_FULL_SCALE_UV = 10_000_000  # ±5 V differential span in µV

# ---------------------------------------------------------------------------
# Mode 2 output rate cap and band-boundary settling
# ---------------------------------------------------------------------------
MIN_EMIT_MS = 10      # emit W records at most every 10 ms (100 Hz max)
BOUNDARY_PRIME = 15   # extra PWM periods to let coil settle after a band-freq change.
                      # 5 was insufficient for the 5µs→40µs wrap-around (8× energy step):
                      # the settling signature (3.1→1.6→0.6 mV gradient in band 0) persisted.
                      # 15 × 94 µs = 1.41 ms; with emit firing during this sleep the effective
                      # settling is 3–7 ms on emit cycles — enough for the thermal transient.
SETTLE_FLOOR_US = 3000  # minimum ABSOLUTE settling time at a band/energy boundary (v4.24).
                        # BOUNDARY_PRIME alone scales with the band period, so high-frequency
                        # bands got far less real settling time (25 kHz: 600 µs) than the
                        # ~1 ms+ the energy-step transient needs. Per-band settle periods are
                        # max(BOUNDARY_PRIME, ceil(SETTLE_FLOOR_US / period_us)).
COMMAND_POLL_MS = 1   # poll stdin for commands at most once per ms instead of once
                      # per sweep cycle (was every PWM period for a 1-2 cell profile).
                      # A reasonable reduction in syscall rate regardless, but tested
                      # and confirmed NOT the cause of the single-cell noise anomaly
                      # — see the v4.08/v4.09 note in the file header for what was.
OUTLIER_GATE_FRAC = 10  # per-cell raw14 plausibility gate: reject samples deviating
                        # >1/10 (10%) from rolling mean; substitute mean instead.
                        # Secondary defence after the IRQ critical section (v4.21).
OUTLIER_GATE_MIN = 164  # absolute gate floor in raw14 counts (≈100 mV, 1% FS).
                        # raw14 is signed: without a floor, a near-zero mean gives
                        # a 0 threshold and a negative mean a negative one — every
                        # sample rejected, cell latched at its warm-up value (v4.25;
                        # bit-truncation glitches are volts-scale, still caught).

# ---------------------------------------------------------------------------
# Signal parameters — held config for Mode 1 / A<x> / * command
# ---------------------------------------------------------------------------
pulse_width_us = 20.0
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
DYNAMIC_PROFILE_INDEX = NUM_PROFILES  # Q<this> selects the RAM-only profile from D

# ---------------------------------------------------------------------------
# Operational state
# ---------------------------------------------------------------------------
state = 'ready'               # 'ready' | 'mode1_running' | 'mode2_running' | 'stop'
active_profile_index = 0
mode2_profile_changed = False
dynamic_profile = None        # set by the D command; RAM only, lost on reset


def get_profile(idx):
    """Return the profile dict for idx: PROFILES[idx], the dynamic profile if
    idx == DYNAMIC_PROFILE_INDEX and one is defined, or None if neither applies."""
    if 0 <= idx < NUM_PROFILES:
        return PROFILES[idx]
    if idx == DYNAMIC_PROFILE_INDEX and dynamic_profile is not None:
        return dynamic_profile
    return None


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
    print('*{0:d},{1:d},{2:d},{3:d},{4:d},{5:d},{6:d}'.format(
        elapsed, current_uV, std_uV,
        sample_frequency_hz,
        round(pulse_width_us * 1000), round(sample_delay_us * 1000),
        down_sample))


# ---------------------------------------------------------------------------
# Raw SPI0 helpers (shared by Mode 2 and A<n>)
# ---------------------------------------------------------------------------
busy_high_count = 0   # DIAGNOSTIC (temporary): counts read_raw_sample() calls
                      # (BUSY edge sync, increments on every sample).
                      # Read out via the 'B' command.
overrun_count = 0     # DIAGNOSTIC (temporary): counts how often acquire_mode2's
                      # per-cell loop iteration overran its period budget
                      # (remaining <= 0, no sleep_us call) — i.e. software fell
                      # behind the free-running hardware PWM. Read out via 'B'.


def raw14_from_bytes(data_bytes):
    """Decode a 4-byte SDOB SPI word into a signed 14-bit sample."""
    word = struct.unpack('>I', data_bytes)[0]
    raw14 = (word >> RAW_DIFF_SHIFT) & RAW_DIFF_MASK
    if raw14 & (RAW_DIFF_MASK // 2 + 1):
        raw14 -= RAW_DIFF_MASK + 1
    return raw14


def read_raw_sample():
    """Read one signed 14-bit raw sample from SDOB over SPI0."""
    global busy_high_count
    irq_state = disable_irq()      # keep USB IRQs out of the BUSY-poll + SPI window
    while not busy_pin.value():   # wait for MCLK to fire (BUSY high)
        pass
    busy_high_count += 1
    while busy_pin.value():        # wait for conversion complete (BUSY low)
        pass
    data_bytes = adc_raw_spi.read(4)
    enable_irq(irq_state)          # restore IRQs before Python processing
    return raw14_from_bytes(data_bytes)


_held_irq = None   # irq state stashed by read_raw_bytes_hold() (module global,
                   # not a return tuple, to keep the Mode 2 hot path
                   # allocation-free — the v4.14 heap-churn lesson)


def read_raw_bytes_hold():
    """BUSY-synced SDOB read like read_raw_sample(), but leaves IRQs DISABLED
    and returns the undecoded 4 SPI bytes. The caller performs its
    time-critical PWM writes, then MUST call enable_irq(_held_irq) on every
    path, and decodes via raw14_from_bytes(). Added in v4.26 so the post-emit
    USB IRQ burst cannot land between the SDOB read and the next cell's CC
    write (see header note)."""
    global busy_high_count, _held_irq
    _held_irq = disable_irq()
    while not busy_pin.value():   # wait for MCLK to fire (BUSY high)
        pass
    busy_high_count += 1
    while busy_pin.value():        # wait for conversion complete (BUSY low)
        pass
    return adc_raw_spi.read(4)


def acquire_raw_average(n_samples):
    """Boxcar-average n_samples raw readings at the current held config.
    Returns (mean_uV, std_uV, min_uV, max_uV). min/max (v4.15) are a direct
    look at the sample distribution within one boxcar window — diagnostic
    for the GUI's "Raw Avg"/"Raw sigma" anomaly (mean swinging by mV-scale
    amounts between A<n> calls): a few outlier samples would show up here as
    a wide min-max spread even when the mean/std look only moderately off."""
    # Prime: discard 5 samples so the PWM wrap-register glitch that follows any
    # freq change (via *) has fully settled before the averaging window opens.
    # No sleep_us needed — read_raw_sample() syncs to BUSY edges and naturally
    # consumes exactly one MCLK period per call.
    for _ in range(5):
        read_raw_sample()
    samples = []
    for _ in range(n_samples):
        samples.append(read_raw_sample())
    mean = sum(samples) / n_samples
    variance = sum((s - mean) ** 2 for s in samples) / n_samples
    mean_uV = int(mean * RAW_FULL_SCALE_UV / 2 ** 14)
    std_uV = int((variance ** 0.5) * RAW_FULL_SCALE_UV / 2 ** 14)
    min_uV = int(min(samples) * RAW_FULL_SCALE_UV / 2 ** 14)
    max_uV = int(max(samples) * RAW_FULL_SCALE_UV / 2 ** 14)
    return mean_uV, std_uV, min_uV, max_uV


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

    Timing model (read-first for ALL cells as of v4.13 — see header note):
      Read SDOB (~6-7 us SPI) for the previous cell's already-completed
      conversion, THEN write new CC (~2 us) for cell[i] (boundary cells also
      change freq between the read and the CC write). Effective sample
      delay must be ≳9 us (read ~6-7 us + write ~2 us) for the new CC to
      reliably precede this period's own trigger — true for every delay in
      every compiled profile (smallest is band4's drive_duty+6.03us+0.75us
      correction ≈ 11.8us). Reading first removes the write-before-read race
      that caused a clean, deterministic value swap between cells (see v4.13).
      As of v4.26 the read -> freq/CC-write sequence runs in one IRQ-off
      critical section with the rolling bookkeeping done afterwards, so the
      write lands ~2 us after the read with no USB IRQ exposure.

    Prime fires cell[n-1] so iteration i=0 correctly stores the result in
    rolling[(0-1)%n] = rolling[n-1], eliminating the startup transient.
    """
    global mode2_profile_changed, overrun_count

    avg_depth = profile['averages']

    # Flatten bands into a cell list:
    # (freq_hz, period_us, drive_duty, sample_duty, settle_periods).
    # settle_periods (v4.24): boundary settling in periods, floored so the
    # ABSOLUTE settle time is at least SETTLE_FLOOR_US — BOUNDARY_PRIME alone
    # under-settled high-frequency bands (see header note).
    cells = []
    for freq_hz, pulse_us, delays_us in profile['bands']:
        period_us = 1_000_000 // freq_hz
        settle = max(BOUNDARY_PRIME,
                     (SETTLE_FLOOR_US + period_us - 1) // period_us)
        for delay_us in delays_us:
            dd, sd = compute_pulse_duties(pulse_us, delay_us, freq_hz)
            cells.append((freq_hz, period_us, dd, sd, settle))

    n = len(cells)
    # Pre-allocated fixed-size circular buffers — avoids list.append()+pop(0)'s
    # O(avg_depth) shift cost (and the heap churn from constantly resizing n
    # lists) that scaled badly with `averages` and was implicated in a crash
    # at averages=256 (v4.14; 128 was fine, 256 was not — a scaling issue).
    # rolling_sum is maintained incrementally (O(1) per sample) instead of
    # summed fresh at emit time.
    rolling = [[0] * avg_depth for _ in range(n)]
    rolling_sum = [0] * n
    rolling_count = [0] * n
    rolling_idx = [0] * n

    # Prime: fire cell[n-1] so that iteration i=0 stores the result in
    # rolling[(0-1)%n] = rolling[n-1] with no startup transient.
    f_last, p_last, dd_last, sd_last, _ = cells[n - 1]
    drive_coil_pwm.freq(f_last)
    sample_coil_pwm.freq(f_last)
    drive_coil_pwm.duty_u16(dd_last)
    sample_coil_pwm.duty_u16(sd_last)
    sleep_us(p_last)

    last_dd, last_sd = dd_last, sd_last
    last_emit_ms = ticks_ms()
    last_poll_ms = last_emit_ms
    mode2_profile_changed = False

    while state == 'mode2_running' and not mode2_profile_changed:
        for i in range(n):
            t0 = ticks_us()

            freq_i, period_i, dd, sd, settle_i = cells[i]
            prev = (i - 1) % n
            at_boundary = freq_i != cells[prev][0]
            # needs_settling also catches pulse-width-only transitions between
            # bands that share a frequency (dd = drive duty changes even when
            # freq doesn't) — at_boundary alone missed this case (v4.14): a
            # same-freq, different-pulse-width profile showed the same
            # "contaminated first cell" signature as the original v4.06
            # cross-band leakage, because BOUNDARY_PRIME settling was gated on
            # at_boundary (freq change only) and never fired here.
            needs_settling = at_boundary or dd != cells[prev][2]

            # Read SDOB BEFORE writing new CC values for cell[i] — for BOTH
            # boundary and non-boundary cells (changed in v4.13; non-boundary
            # cells used to write-then-read). Root cause: writing a new compare
            # value while the counter has already passed it can fire an
            # immediate spurious trigger (same family as the v4.04 freq/WRAP
            # issue, but for duty_u16's compare register) — the read right
            # after a write-first then captures THIS cell's own just-triggered
            # conversion instead of the PREVIOUS cell's already-completed one,
            # producing a clean, deterministic off-by-one: empirically, a
            # 2-cell profile's reported values were exactly swapped between
            # the two cells, reproduced at both 25kHz and 57kHz and confirmed
            # to follow array order (reversing the delay order reversed which
            # channel reported which value). Reading first removes the race:
            # at boundaries this also avoids the v4.04 WRAP-shrink issue.
            #
            # v4.26: IRQs stay disabled from the BUSY-synced read through the
            # freq/CC writes, and the gate/rolling bookkeeping (identical in
            # both branches, now a single copy) moved AFTER the hardware
            # writes. Previously ~tens of µs of interpreter time plus the
            # post-emit USB IRQ burst sat between the read and cell[i]'s CC
            # write, which could push the write past the PWM wrap — CC is not
            # double-buffered, so the next conversion then fired at cell[i-1]'s
            # compare point (see header note; symptom was channel 1's inflated
            # σ / biased mean).
            data_bytes = read_raw_bytes_hold()
            if at_boundary:
                drive_coil_pwm.freq(freq_i)
                sample_coil_pwm.freq(freq_i)
            # Skip the CC rewrite when dd/sd are unchanged from the previous
            # period (always true for a 1-cell profile, occasionally true
            # otherwise) — harmless micro-optimization, confirmed not itself
            # a fix for anything.
            if dd != last_dd or sd != last_sd:
                drive_coil_pwm.duty_u16(dd)
                sample_coil_pwm.duty_u16(sd)
                last_dd, last_sd = dd, sd
            enable_irq(_held_irq)
            raw = raw14_from_bytes(data_bytes)

            cnt = rolling_count[prev]
            if cnt >= 8:
                mean_raw = rolling_sum[prev] // cnt
                dev = raw - mean_raw
                if dev < 0:
                    dev = -dev
                gate = mean_raw if mean_raw >= 0 else -mean_raw
                gate //= OUTLIER_GATE_FRAC
                if gate < OUTLIER_GATE_MIN:
                    gate = OUTLIER_GATE_MIN
                if dev > gate:
                    raw = mean_raw
            idx = rolling_idx[prev]
            rolling_sum[prev] += raw - rolling[prev][idx]
            rolling[prev][idx] = raw
            rolling_idx[prev] = (idx + 1) % avg_depth
            if rolling_count[prev] < avg_depth:
                rolling_count[prev] += 1

            # Sleep out the remainder of this cell's period.
            # At band/drive-energy boundaries add settle_i extra periods
            # (>= BOUNDARY_PRIME, floored to SETTLE_FLOOR_US of real time —
            # v4.24) so the coil reaches steady state before the next cell
            # reads this cell's SDOB, breaking the contamination cascade.
            elapsed = ticks_diff(ticks_us(), t0)
            remaining = period_i - elapsed - 2
            if needs_settling:
                remaining += period_i * settle_i
            if remaining > 0:
                sleep_us(remaining)
            else:
                overrun_count += 1

            # Emit W record and poll commands at i==0 only (once per cycle), placed
            # AFTER reading cell[n-1] and AFTER the boundary settling sleep.
            # Previously this block ran after the for loop, meaning cell[n-1]'s read
            # (at i=0) was the first read after print() — USB CDC IRQs from print()
            # have ~10-50 µs latency, wider than the 2.5 µs BUSY-LOW window at 57 kHz,
            # causing bit-truncated outliers (the §7 mid-conversion read mechanism).
            # Moving here: cell[n-1] is read clean (i=0 read before this block).
            # NOTE (v4.24): the print() does NOT overlap the settling sleep as the
            # v4.20 note claimed — sleep_us blocks, then print() runs. The PWM keeps
            # free-running at cell[0]'s config during the ms-scale print, so cell[0]
            # in effect receives extra settling every emit cycle — which is why
            # band 1's first cell stayed clean while other bands' first cells were
            # under-settled before the SETTLE_FLOOR_US fix.
            if i == 0:
                now = ticks_ms()
                if ticks_diff(now, last_emit_ms) >= MIN_EMIT_MS:
                    means = []
                    for j in range(n):
                        cnt = rolling_count[j]
                        if cnt:
                            mean_uV = int(rolling_sum[j] / cnt * RAW_FULL_SCALE_UV / 2 ** 14)
                        else:
                            mean_uV = 0
                        means.append(mean_uV)
                    elapsed_ms = ticks_diff(now, base_time_ms)
                    fields = ['W{0:d}'.format(active_profile_index), '{0:d}'.format(elapsed_ms)]
                    fields += ['{0:d}'.format(m) for m in means]
                    print(','.join(fields))
                    last_emit_ms = now
                if ticks_diff(now, last_poll_ms) >= COMMAND_POLL_MS:
                    check_for_commands(timeout_ms=0)
                    last_poll_ms = now


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
      D<averages>;<freq_hz>,<pulse_us>,<d1>,...;...  define dynamic profile (RAM only)

    Common:
      V/v/? identify
      L     list profiles
    """
    global state, sample_frequency_hz, pulse_width_us, sample_delay_us, down_sample
    global active_profile_index, mode2_profile_changed, dynamic_profile
    global busy_high_count, overrun_count

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
            profile = get_profile(active_profile_index)
            if profile is None:
                print('Command Input ERROR: no valid profile selected (use Q<n> first)')
                return
            invalid = validate_profile(profile)
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
            profile = get_profile(idx)
            if profile is None:
                print('Command Input ERROR: invalid profile index (Q{0})'.format(line[1:].strip()))
                return
            invalid = validate_profile(profile)
            if invalid:
                print('Command Input ERROR: profile {0} has invalid cell '
                      '(freq={1:.0f}Hz, pw={2:.1f}us, delay={3:.1f}us)'.format(
                          idx, invalid[0], invalid[1], invalid[2]))
                return
            active_profile_index = idx
            print('Q{0} OK: {1}'.format(idx, profile['name']))
            if state == 'mode2_running':
                mode2_profile_changed = True  # signals acquire_mode2 to restart

        elif cmd in ('D', 'd'):
            if state == 'mode2_running':
                print('Command Input ERROR: D rejected while Mode 2 running (send E first)')
                return
            try:
                body = line[1:].strip()
                avg_part, *band_parts = body.split(';')
                averages = int(avg_part)
                bands = []
                n_delays = None
                for bp in band_parts:
                    fields = bp.split(',')
                    freq_hz = int(float(fields[0]))
                    pulse_us = float(fields[1])
                    delays_us = tuple(float(x) for x in fields[2:])
                    if n_delays is None:
                        n_delays = len(delays_us)
                    elif len(delays_us) != n_delays:
                        print('Command Input ERROR: D rejected, all bands must have '
                              'the same number of delays')
                        return
                    bands.append((freq_hz, pulse_us, delays_us))
                if not bands or n_delays == 0:
                    print('Command Input ERROR: D rejected, no bands/delays given')
                    return
            except Exception as e:
                print('Command Input ERROR: D parse failed:', e)
                return
            candidate = {'name': 'DYNAMIC', 'bands': tuple(bands), 'averages': averages}
            invalid = validate_profile(candidate)
            if invalid:
                print('Command Input ERROR: dynamic profile has invalid cell '
                      '(freq={0:.0f}Hz, pw={1:.1f}us, delay={2:.1f}us)'.format(
                          invalid[0], invalid[1], invalid[2]))
                return
            dynamic_profile = candidate
            print('D OK: {0} bands x {1} delays, averages={2}'.format(
                len(bands), n_delays, averages))

        elif cmd == '*':
            if state == 'mode2_running':
                print('Command Input ERROR: * rejected while Mode 2 running (send E first)')
                return
            parts = line[1:].split(',')
            new_freq_hz = int(parts[0])
            new_pulse_us = int(parts[1]) / 1000.0
            new_delay_us = int(parts[2]) / 1000.0
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
            mean_uV, std_uV, min_uV, max_uV = acquire_raw_average(n_samples)
            elapsed = ticks_diff(ticks_ms(), base_time_ms)
            print('R{0:d},{1:d},{2:d},{3:d},{4:d},{5:d},{6:d},{7:d},{8:d}'.format(
                elapsed, mean_uV, std_uV, n_samples,
                sample_frequency_hz,
                round(pulse_width_us * 1000), round(sample_delay_us * 1000),
                min_uV, max_uV))

        elif cmd in ('V', 'v', '?'):
            print('V{0},{1},{2},{3},{4:d},{5:d},{6:d},{7:d}'.format(
                FW_VERSION, board_id_hex, NUM_PROFILES, active_profile_index,
                sample_frequency_hz,
                round(pulse_width_us * 1000), round(sample_delay_us * 1000),
                down_sample))

        elif cmd == 'L':
            for idx, p in enumerate(PROFILES):
                n_bands = len(p['bands'])
                n_cells = sum(len(d) for _, _, d in p['bands'])
                first_freq_hz = p['bands'][0][0]
                print('L{0:d},{1:d},{2:d},{3:d},{4:d},{5}'.format(
                    idx, first_freq_hz, n_bands, n_cells, p['averages'], p['name']))
            if dynamic_profile is not None:
                p = dynamic_profile
                n_bands = len(p['bands'])
                n_cells = sum(len(d) for _, _, d in p['bands'])
                first_freq_hz = p['bands'][0][0]
                print('L{0:d},{1:d},{2:d},{3:d},{4:d},{5}'.format(
                    DYNAMIC_PROFILE_INDEX, first_freq_hz, n_bands, n_cells,
                    p['averages'], p['name']))

        elif cmd in ('B', 'b'):
            # DIAGNOSTIC (temporary): report and reset busy_high_count and
            # overrun_count — see read_raw_sample()/acquire_mode2() and the
            # Mode 2 single-cell noise investigation.
            print('B{0:d},{1:d}'.format(busy_high_count, overrun_count))
            busy_high_count = 0
            overrun_count = 0

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
            try:
                acquire_mode2(get_profile(active_profile_index))
            except Exception as e:
                # Defensive: an unhandled exception here previously crashed the
                # board outright (e.g. at averages=256 before the v4.14
                # circular-buffer fix). Report and return to a safe state
                # instead of silently dying.
                print('Mode 2 ERROR:', e)
                state = 'stop'
        elif state == 'stop':
            set_safe_state()
            state = 'ready'
except KeyboardInterrupt:
    print('\nTerminating')
    drive_coil_pwm.duty_u16(0)
finally:
    set_safe_state()
    print()
