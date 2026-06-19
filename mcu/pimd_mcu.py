###############################################################################
# Pulse Induction Metal Detector, v4.21, coil v4
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
#         -> R<time_ms>,<mean_uV>,<std_uV>,<n>,<freq_kHz>,<pulse_us>,<delay_us>,<min_uV>,<max_uV>
#   V/v/? identify -> V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_kHz>,<pulse_us>,<delay_us>,<downsample>
#   L     list profiles -> one L<idx>,<freq_kHz>,<n_pulses>,<n_delays>,<averages>,<name> line each
#

# v4.21 FIX read_raw_sample: wrap BUSY poll + SPI read in disable_irq/enable_irq
#       so USB CDC IRQs cannot fire between the BUSY-low edge and the SPI clock.
#       Eliminates two Mode 2 anomaly types confirmed in quiet 45-channel recordings:
#       (1) §7 SDOB bit-truncation (value ≈ 50%/25% of true): USB IRQ delays SPI
#       start past the next MCLK; partial SDOB shift produces half/quarter values.
#       (2) Cell-value bleed (value > next-cell, ratio >1.0): USB IRQ starves the
#       BUSY-high poll long enough to miss the current cell's MCLK entirely, landing
#       on the previous cell's still-valid output. Both produce 32-frame flat level
#       shifts (one bad sample × M=32 rolling-buffer depth). IRQ blackout per call
#       ≤36 µs worst-case (just missed MCLK); safe for USB SOF at 1 kHz.
#       Also adds a per-cell 10% plausibility gate: if raw14 deviates >10% from
#       rolling mean (after ≥8 samples), substitute the mean instead of updating.
#       Belt-and-suspenders secondary defence; all 8 observed events caught.
#       FW_VERSION synced to file header (was stuck at 4.15).
# v4.20 FIX acquire_mode2: two first/last-cell std-dev bugs fixed.
#       (1) BOUNDARY_PRIME 5→15: 470 µs was insufficient for the 5µs→40µs
#       wrap-around thermal transient (8× pulse-energy step); settling
#       signature was the 3.1→1.6→0.6 mV gradient in band-0 cells 0-2.
#       (2) emit/poll moved from after the for-loop to inside it at i==0:
#       previously print() ran between cell[n-1]'s write and its read,
#       and USB CDC IRQs (~10-50 µs) exceed the 2.5 µs BUSY-LOW window at
#       57 kHz — causing the §7 mid-conversion bit-truncated outliers in
#       cell[n-1]. Moving here: cell[n-1] read is clean, USB noise overlaps
#       the already-running cell[0] settling sleep instead.
# v4.19 revert v4.18: v4.18's sleep_us+post-read-retry approach brought back
#       the outlier corruption that v4.17 had eliminated. v4.17's BUSY edge
#       sync (wait-for-high then wait-for-low) is restored. The reduced sample
#       rate (~1.6 kHz effective vs 10 kHz configured) is accepted for now —
#       the accuracy improvement (tracking within a few mV) outweighs it.
#       updated SAMPLE_PULSE_CORRECTION to 0.908, to match new coil/front end
# v4.18 FIX read_raw_sample: v4.17 replaced sleep_us pacing with a full
#       BUSY edge sync (wait-for-high then wait-for-low). This is correct in
#       principle but the ~15µs BUSY-high pulse at 10 kHz is too short for
#       MicroPython polling to catch reliably — only ~1 in 6 pulses detected,
#       dropping effective sample rate from 10 kHz to ~1.6 kHz (observed as
#       Sa/s falling from 9.8 to 6.4 and Rx freq showing 1.6 kHz).
#       Approach: restore sleep_us(period_us) pacing, add a pre-read wait for
#       BUSY low (v4.16 fix) AND a post-read BUSY check — if MCLK fired
#       during the 3.2µs SPI transfer, retry once after waiting for the
#       newly-started conversion to finish. Double-retry probability is
#       negligible (SPI transfer takes ~3.2µs, next MCLK is ~period_us away).
# v4.17 FIX read_raw_sample: v4.16 guarded against reading while BUSY was
#       already high, but left a second window: when called just before MCLK
#       fires, BUSY is already low (previous conversion done), the check
#       passes, and the SPI read starts — then MCLK fires mid-read and the
#       LTC2508-32 invalidates the SDOB register, producing a bit-truncated
#       result. Confirmed: min/max (v4.15) shows discrete outlier values at
#       ~375k and ~750k µV (exactly 1/4 and 1/2 of the true ~1511k µV) —
#       ratios consistent with 1-2 bits of partial/corrupted SPI data.
#       Fix: change from "guard-only-if-high" to "sync to the edge" — wait
#       for BUSY to go HIGH (MCLK has fired), then wait for BUSY LOW
#       (conversion complete), then read. This places the SPI clock at
#       maximum margin from both edges and makes timing 100% hardware-locked.
#       acquire_raw_average's sleep_us(period_us) loop is also removed — each
#       read_raw_sample() call now naturally consumes exactly one MCLK period
#       via the BUSY waits, so software timing is no longer needed.
# v4.16 FIX read_raw_sample: was counting BUSY-high hits but reading SDOB
#       immediately regardless. The sleep_us()-paced loop drifts relative to
#       the free-running PWM and occasionally lands mid-conversion (BUSY high),
#       returning corrupt/low data — confirmed by v4.15 min/max: min drops to
#       ~375 kµV while normal samples cluster at ~1511 kµV, pulling the boxcar
#       mean down and producing the sawtooth oscillation and "never exceeds
#       Mode 1" behaviour seen in pimd_gui.py. Fix: wait for BUSY low before
#       clocking SDOB (one while-loop after the existing counter increment).
#       busy_high_count now measures how often the wait was needed.
# v4.15 acquire_raw_average now also returns min_uV/max_uV (the boxcar
#       window's sample extremes), appended to the R record:
#       R<t>,<mean_uV>,<std_uV>,<n>,<freq_kHz>,<pulse_us>,<delay_us>,<min_uV>,<max_uV>
#       Diagnostic for a new anomaly: pimd_gui.py's "Raw Avg" chart toggle
#       (v4.03) showed the A<n> boxcar mean swinging by several mV between
#       polls in a repeating sawtooth, while the filtered path stayed flat —
#       suspected to be the same unresolved family as the Mode 2 single-cell
#       noise (v4.08-v4.14 notes below): a static PWM config, read repeatedly
#       via read_raw_sample() in a sleep_us()-paced loop. min/max exposes
#       whether a handful of outlier samples are hiding inside the average,
#       the same way per-sample inspection (not just mean/std) cracked the
#       Mode 2 cell-misattribution bug. Appended at the end — existing
#       consumers (pimd_gui.py, pimd_delaycal.py) only read fields up to
#       index 3, unaffected by the new trailing fields.
# v4.14 two fixes from user testing of a same-freq/different-pulse-width
#       profile (D128;5000,50.0,<9 delays>;5000,10.0,<9 delays>):
#       1) needs_settling now also fires on a drive-duty (pulse-width) change,
#          not just a frequency change — at_boundary alone missed same-freq
#          band transitions, so BOUNDARY_PRIME settling never applied there.
#          First cell of each band showed the same "contaminated" signature
#          as the original v4.06 cross-band leakage (confirmed via user's
#          stats CSV: first-cell std dev 55-65mV vs 2-12mV for the rest).
#       2) acquire_mode2's rolling buffers were plain lists using
#          append()+pop(0) — O(avg_depth) per sample, scaling badly and
#          implicated in a board crash at averages=256 (128 was fine).
#          Replaced with pre-allocated fixed-size circular buffers + an
#          incrementally-maintained sum — O(1) per sample regardless of
#          avg_depth, no list resizing/heap churn. Also wrapped the Mode 2
#          main-loop call in try/except so any future unhandled error reports
#          over serial and returns to a safe state instead of crashing outright.
# v4.13 FIX (not just diagnostic): acquire_mode2 non-boundary cells now read
#       SDOB BEFORE writing new CC values, matching what boundary cells already
#       did. Root cause of the v4.08-v4.12 investigation, finally isolated: a
#       2-cell profile's reported values were found to be EXACTLY swapped
#       between cells (not random) at both 25kHz and 57kHz, and reversing the
#       delay order in the D command reversed which channel reported which
#       value — proving array-order-following, deterministic mis-indexing,
#       not noise. Mechanism: writing a new compare value while the counter
#       has already passed it can fire an immediate spurious trigger (same
#       family as the already-fixed v4.04 freq/WRAP issue, but for duty_u16's
#       compare register) — write-before-read meant the read right after
#       captured THIS cell's own just-triggered conversion instead of the
#       PREVIOUS cell's already-completed one. busy_high_count/overrun_count
#       (v4.11/v4.12) did not correlate with the bug and remain as harmless
#       diagnostics for now. Verify: re-run the 2-cell swap tests and the full
#       CLASSIFY_EP sweep after flashing.
# v4.12 add temporary diagnostic: overrun_count (global) increments in
#       acquire_mode2() whenever a cell's loop iteration overran its period
#       budget (remaining <= 0, no sleep_us call) — i.e. software fell behind
#       the free-running hardware PWM. Reported via 'B' alongside
#       busy_high_count. Direct test of a new finding: raw (averages=1)
#       captures show that for a 2-cell profile (25kHz/10us, delays 7.6us and
#       10.0us), each cell's reported value randomly flips between two
#       discrete states (~3520mV, matching the true 7.6us value confirmed via
#       A256, and ~820mV) — i.e. cell identity is being randomly swapped
#       between conversions, not just noisy. A 1-cell profile at the same
#       parameters is rock stable (no swapping possible — nothing to swap to).
#       Averaging (avg_depth=16) blends the two states into what looked like
#       a clean-but-wrong mean with deceptively low std dev. This is a
#       correctness bug, potentially affecting any multi-cell Mode 2 profile
#       (not just the single-cell edge case), pending confirmation.
# v4.11 add temporary diagnostic: busy_high_count (global) increments in
#       read_raw_sample() whenever busy_pin is found high at SDOB read time —
#       per the LTC2508-32 datasheet ("MCLK Timing", p.20) this should never
#       happen; BUSY goes high at conversion start and low when complete, and
#       data is meant to be clocked out during the auto-power-down idle window
#       after. New 'B' command reports and resets the counter. Direct test of
#       whether the Mode 2 single-cell noise anomaly (see v4.08-v4.10 note)
#       correlates with reading SDOB while a conversion is still in progress.
#       Temporary — remove once the investigation concludes.
# v4.10 corrected the v4.08/v4.09 comments below in place: both changes were
#       directly A/B-tested on real hardware and found to make NO measurable
#       difference to the noise anomaly they were written to fix. No code
#       logic changed in v4.10 — comments only, version bumped per policy.
# v4.09/v4.08 acquire_mode2 investigation (corrected — see below for the actual
#       finding; both changes are kept as harmless, but neither was the fix):
#       v4.08 skips the duty_u16() rewrite when dd/sd are unchanged from the
#       previous period; v4.09 throttles check_for_commands() to once per
#       COMMAND_POLL_MS instead of once per sweep cycle. Both were tested by
#       direct A/B and made NO measurable difference — falsified.
#
#       Investigation trigger: a 1-cell dynamic profile (averages=16,
#       25kHz/10us/7.6us) showed up to ~25-30mV std dev vs Mode 1's <100uV at
#       identical parameters (verified on scope, identical waveform);
#       scope-measured pulse-to-sample delay jitter was 60ns in Mode 2 vs <10ns
#       in Mode 1 (README §8 documents ~15-20ns for the static-PWM baseline).
#
#       ACTUAL finding (isolated by direct A/B, not yet explained at the
#       RP2040-hardware level): noise is high specifically when the PWM
#       duty_u16 compare value is held CONSTANT across consecutive periods —
#       whether by skipping the write (v4.08) or by rewriting the identical
#       value (original code, and Mode 1's one-time setup). It is LOW
#       (~310uV, matching the A32/README ~350uV expectation) when the value
#       actually CHANGES every period. Confirmed with 4 data points: n=1 (any
#       fix combination) ~24-30mV; n=2 profile with two DIFFERENT delays
#       (different sample_duty each period) ~310uV; n=2 profile with two
#       IDENTICAL delays (same dd/sd every period, like n=1) back to ~25mV.
#       Whether the value is written or skipped doesn't matter — only whether
#       it differs from the previous period.
#
#       Practical conclusion: Mode 2 (interleaved sweep) is not suited to
#       genuine single-point / repeated-identical-cell measurement — that is
#       exactly what Mode 1 already does well. Multi-cell sweeps (the actual
#       purpose of Mode 2, including CLASSIFY_EP) are unaffected since cells
#       legitimately differ period to period. No further firmware change
#       attempted without RP2040 PWM datasheet-level investigation beyond what
#       can be confirmed via code reading and serial A/B testing.
#
#       Diagnostic A32 raw-path boxcar average (static PWM, same SPI0 path)
#       measured ~100uV-1mV early in the investigation — ruling out the
#       raw-vs-filtered ADC path as the dominant cause before the real (CC-
#       value-must-change) finding above was isolated.
# v4.07 add D command: defines a RAM-only 'dynamic' profile (global dynamic_profile,
#       selected via Q<DYNAMIC_PROFILE_INDEX>) so a PC app can try new band/pulse/
#       delay combinations without editing PROFILES and reflashing. Lost on reset —
#       same configure-then-select pattern as Mode 1's '*' + S. get_profile(idx)
#       added as the single lookup point (PROFILES[idx] or dynamic_profile),
#       replacing direct PROFILES[active_profile_index] indexing in the main loop
#       and the Q/G command handlers; L listing includes it when defined.
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
# v4.03 profile structure changed from {freq_hz, pulses_us, delays_us} to
#       {bands: [(freq_hz, pulse_us, delays_us)…]} so each band can have its own
#       frequency; acquire_mode2 updates the PWM slice freq at band boundaries;
#       new profile 4 CLASSIFY_EP: 5 equal-power bands × 9 calibrated delays = 45 cells
# v4.02 acquire_raw_average: discard first 5 samples (priming) so PWM wrap-register
#       glitch after freq change settles before the averaged window begins; fixes
#       near-zero readings on A<n> when frequency changes between * commands
# v4.01 acquire_mode2: CC written first at period start (~1-2 us) before SPI read
#       — eliminates CC-write race on multi-cell profiles; precompute cell_duties;
#       prime now fires cell[n-1] (removes startup transient in rolling[n-1]);
#       command poll moved out of W-emit gate ('E' stops within one n_pulses*n_delays cycle)
# v4.00 complete serial protocol rewrite (two non-concurrent modes, W streaming,
#       Q/G commands, file renamed from pimd_mcu_302.py to pimd_mcu.py)
###############################################################################

# pyright: reportMissingImports=false

import ubinascii
import struct
import select
from sys import stdin
from utime import sleep_ms, sleep_us, ticks_ms, ticks_us, ticks_diff
from machine import Pin, PWM, SPI, unique_id, disable_irq, enable_irq

FW_VERSION = '4.21'
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
SAMPLE_PULSE_CORRECTION = 0.908       # µs: measured offset between PWM edge and ADC trigger

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
COMMAND_POLL_MS = 1   # poll stdin for commands at most once per ms instead of once
                      # per sweep cycle (was every PWM period for a 1-2 cell profile).
                      # A reasonable reduction in syscall rate regardless, but tested
                      # and confirmed NOT the cause of the single-cell noise anomaly
                      # — see the v4.08/v4.09 note in the file header for what was.
OUTLIER_GATE_FRAC = 10  # per-cell raw14 plausibility gate: reject samples deviating
                        # >1/10 (10%) from rolling mean; substitute mean instead.
                        # Secondary defence after the IRQ critical section (v4.21).

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
    print('*{0:d}, {1:d}, {2:d}, {3:1.1f}, {4:1.1f}, {5:1.1f}, {6:d}'.format(
        elapsed, current_uV, std_uV,
        sample_frequency_hz / 1000, pulse_width_us, sample_delay_us, down_sample))


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
    word = struct.unpack('>I', data_bytes)[0]
    raw14 = (word >> RAW_DIFF_SHIFT) & RAW_DIFF_MASK
    if raw14 & (RAW_DIFF_MASK // 2 + 1):
        raw14 -= RAW_DIFF_MASK + 1
    return raw14


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

    Prime fires cell[n-1] so iteration i=0 correctly stores the result in
    rolling[(0-1)%n] = rolling[n-1], eliminating the startup transient.
    """
    global mode2_profile_changed, overrun_count

    avg_depth = profile['averages']

    # Flatten bands into a cell list: (freq_hz, period_us, drive_duty, sample_duty)
    cells = []
    for freq_hz, pulse_us, delays_us in profile['bands']:
        period_us = 1_000_000 // freq_hz
        for delay_us in delays_us:
            dd, sd = compute_pulse_duties(pulse_us, delay_us, freq_hz)
            cells.append((freq_hz, period_us, dd, sd))

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
    f_last, p_last, dd_last, sd_last = cells[n - 1]
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

            freq_i, period_i, dd, sd = cells[i]
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
            if at_boundary:
                raw = read_raw_sample()
                cnt = rolling_count[prev]
                if cnt >= 8:
                    mean_raw = rolling_sum[prev] // cnt
                    dev = raw - mean_raw
                    if dev < 0:
                        dev = -dev
                    if dev > mean_raw // OUTLIER_GATE_FRAC:
                        raw = mean_raw
                idx = rolling_idx[prev]
                rolling_sum[prev] += raw - rolling[prev][idx]
                rolling[prev][idx] = raw
                rolling_idx[prev] = (idx + 1) % avg_depth
                if rolling_count[prev] < avg_depth:
                    rolling_count[prev] += 1
                drive_coil_pwm.freq(freq_i)
                sample_coil_pwm.freq(freq_i)
            else:
                raw = read_raw_sample()
                cnt = rolling_count[prev]
                if cnt >= 8:
                    mean_raw = rolling_sum[prev] // cnt
                    dev = raw - mean_raw
                    if dev < 0:
                        dev = -dev
                    if dev > mean_raw // OUTLIER_GATE_FRAC:
                        raw = mean_raw
                idx = rolling_idx[prev]
                rolling_sum[prev] += raw - rolling[prev][idx]
                rolling[prev][idx] = raw
                rolling_idx[prev] = (idx + 1) % avg_depth
                if rolling_count[prev] < avg_depth:
                    rolling_count[prev] += 1

            # Write CC for cell[i] — now after the read. Skip the rewrite when
            # dd/sd are unchanged from the previous period (always true for a
            # 1-cell profile, occasionally true otherwise) — harmless
            # micro-optimization, confirmed not itself a fix for anything.
            if dd != last_dd or sd != last_sd:
                drive_coil_pwm.duty_u16(dd)
                sample_coil_pwm.duty_u16(sd)
                last_dd, last_sd = dd, sd

            # Sleep out the remainder of this cell's period.
            # At band/drive-energy boundaries add BOUNDARY_PRIME extra periods
            # so the coil reaches steady state before the next cell reads this
            # cell's SDOB, breaking the contamination cascade.
            elapsed = ticks_diff(ticks_us(), t0)
            remaining = period_i - elapsed - 2
            if needs_settling:
                remaining += period_i * BOUNDARY_PRIME
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
            # Moving here: cell[n-1] is read clean (i=0 read before this block),
            # and the USB activity overlaps cell[0]'s already-running settling sleep.
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
            mean_uV, std_uV, min_uV, max_uV = acquire_raw_average(n_samples)
            elapsed = ticks_diff(ticks_ms(), base_time_ms)
            print('R{0:d}, {1:d}, {2:d}, {3:d}, {4:.1f}, {5:.1f}, {6:.1f}, {7:d}, {8:d}'.format(
                elapsed, mean_uV, std_uV, n_samples,
                sample_frequency_hz / 1000, pulse_width_us, sample_delay_us,
                min_uV, max_uV))

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
            if dynamic_profile is not None:
                p = dynamic_profile
                n_bands = len(p['bands'])
                n_cells = sum(len(d) for _, _, d in p['bands'])
                first_freq_khz = p['bands'][0][0] / 1000
                print('L{0:d},{1:.1f},{2:d},{3:d},{4:d},{5}'.format(
                    DYNAMIC_PROFILE_INDEX, first_freq_khz, n_bands, n_cells,
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
