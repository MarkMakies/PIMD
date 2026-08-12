# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
###############################################################################
# Pulse Induction Metal Detector, v4.37, coil v4
# Runs on RP2040 dev board (Waveshare RP2040-Zero, MicroPython)
#
# Interfaces to LTC2508-32 ADC:
#   SPI1 / filtered 32-bit (SDOA/SCKA/DRL, GPIO8/10/9)  — Mode 1
#   SPI0 / raw 14-bit     (SDOB/SCKB/BUSY, GPIO0/2/15)  — Mode 2
#   1-Wire / DS18B20 board temperature (DQ, GPIO6)      — both modes, v4.33
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
#   V/v/? identify -> V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>,
#                     <pack_mV>,<board_temp_dC>,<pack_voltage_lockout>
#         (v4.28 appends the three trailing sensor/lockout fields. Additive: no parser
#         in src/ splits V by field count, so this breaks no consumer.)
#   L     list profiles -> one L<idx>,<freq_hz>,<n_pulses>,<n_delays>,<averages>,<name> line each
#   B/b   diagnostic counters, reset on read (9 fields since v4.37)
#         -> B<busy_high_count>,<overrun_count>,<emit_block_count>,<emit_block_ms_max>,
#            <gate_reject_count>,<gate_reprime_count>,
#            <busy_timeout_count>,<busy_spin_min_left>,<rail_absent_ms_max>
#         emit_block_* (v4.27) count Mode 2 emits whose print() blocked longer than
#         EMIT_BLOCK_WARN_MS — i.e. the host stopped draining USB CDC. Non-zero means
#         the sweep was paused and the rig's thermal load changed with it.
#         gate_* (v4.35) count outlier-gate rejections and the re-primes that bound
#         them. Rejections without re-primes = the gate catching glitches; re-primes
#         tracking the signal = the gate fighting real signal (see OUTLIER_GATE_FRAC).
#         busy_timeout_count (v4.37) counts abandoned samples — did a rail loss
#         happen at all. busy_spin_min_left is how close a HEALTHY spin came to
#         BUSY_SPIN_LIMIT (resets to the limit, not 0): small means the cap is too
#         tight and a false abort is coming. rail_absent_ms_max is the longest
#         outage dwell. busy_high_count freezes when BUSY stops, so near-zero
#         alongside a non-zero busy_timeout_count means the outage spanned the
#         whole read window.
#   (unsolicited, both modes) pack-voltage / board-temp telemetry, every SENSOR_REPORT_MS:
#         -> P<time_ms>,<pack_mV>,<board_temp_dC>
#         Both fields are REAL calibrated readings: pack_mV since v4.29 (22k/2k7
#         divider on GP26, see PACK_VOLTAGE_FULLSCALE_MV), board_temp_dC since v4.33
#         (DS18B20 1-Wire sensor on GP6, factory-calibrated to ±0.5 °C).
#         board_temp_dC is deci-degrees C (x10 integer), and TEMP_INVALID_DC (-32768)
#         means NO READING — sensor absent, not responding, or CRC-failing. A consumer
#         must blank its display on that value, never plot it. It cannot collide with a
#         real reading: the DS18B20's range is -55..+125 °C, i.e. -550..+1250 dC.
#   (v4.28) LOW-VOLTAGE FAILSAFE: if pack_mV <= PACK_VOLTAGE_TRIP_MV for
#         PACK_VOLTAGE_TRIP_CONSECUTIVE consecutive samples, firmware forces a stop,
#         disables drive, and LATCHES — S/G/D are rejected until a physical power-cycle.
#         No serial command can clear the latch (deliberate: see CHANGELOG v4.28).
#   (v4.31) PACK-ABSENT SUSPEND: below PACK_ABSENT_MV the rail is off and the MCU is
#         running on USB, so there is no pack to protect — the failsafe suspends instead
#         of latching, and releases when a pack returns at >= PACK_REARM_MV. Lets the
#         pack be switched off or swapped without a physical MCU reset, and lets the
#         board be USB-powered for programming with the pack switched on later.
#         Still not a serial re-arm: it requires the pack to physically go and a
#         healthy one to come back.
#   (v4.37) RAIL-LOSS ABORT: the Mode 2 BUSY poll is bounded by BUSY_SPIN_LIMIT. If
#         the ADC stops converting — typically the +20V rail switched off while the MCU
#         stays alive on USB — the sweep aborts instead of spinning with IRQs masked,
#         which used to take USB CDC down with it and silence the board completely,
#         including the 'PACK: rail absent' the failsafe was supposed to print.
#         Firmware then rests in state 'rail_absent': drive safe, pack/temp telemetry
#         unaffected, Mode 2 resuming by itself once the pack returns at >=
#         PACK_REARM_MV for RAIL_RESUME_CONSECUTIVE checks. A BUSY timeout with the
#         pack reading HEALTHY is a different fault and stops instead ('ADC:' line).
#         S and A<n> are refused while the rail is absent — their read paths still
#         have the unbounded wait (chunks 2 and 3).
#

# History (full detail in CHANGELOG.md):
#   v4.37 FIX read_raw_bytes_hold: unbounded IRQ-off BUSY spin went silent on rail loss; rail-absent state keeps telemetry alive
#   v4.36 TEST BUILD: pack floor 21.0 -> 19.0 V, re-arm 21.5 -> 19.5 V. Revert before a keeper pack
#   v4.35 FIX acquire_mode2: outlier gate was an absorbing state — cells latched permanently
#   v4.34 FIX acquire_mode2: boundary settle measured from the config write, not the loop top
#   v4.33 DS18B20 board temperature on GP6 (1-Wire); GP27 pot placeholder path retired
#   v4.32 pack absent->present transition always announces itself, so 'failsafe armed' is observable
#   v4.31 pack-absent suspend (<6 V = USB power) + re-arm hysteresis; battery swap no longer needs a reset
#   v4.30 harden boot check against divider RC settling — settle delay + spaced boot samples (defensive)
#   v4.29 pack divider built + bench-calibrated: FULLSCALE 25000 -> 30083 mV; POT pin comments corrected
#   v4.28 pack-voltage + board-temp sense (ADC), periodic 'P' telemetry, hard-latched low-voltage failsafe
#   v4.27 diagnostic: emit-block counters via 'B' (host-stall detection; emit path unchanged)
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
from machine import ADC, Pin, PWM, SPI, unique_id, disable_irq, enable_irq

# v4.33: 1-Wire for the DS18B20 board-temperature sensor. Guarded because the
# detector must boot and run fully without it — a build lacking the module (it is
# frozen into the official RP2040 MicroPython images, but that is a property of the
# image, not of the chip) leaves temperature reported as TEMP_INVALID_DC and changes
# nothing else. ds18x20 is deliberately NOT imported: its read_temp() issues
# MATCH-ROM, writing 8 address bytes (~4.8 ms of blocking bit-bang) to address the
# only device on the bus. See _ds_read_scratch().
try:
    import onewire
except ImportError:
    onewire = None

FW_VERSION = '4.37'
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
# Pack-voltage sense (RP2040 on-chip ADC, v4.28; board temp moved to 1-Wire at v4.33)
# ---------------------------------------------------------------------------
# GP26-29 (ADC0-3) are unused elsewhere in this firmware. Sheet 1 wires all four
# to onboard 10k pots for bench bring-up. The pin->pot mapping runs BACKWARDS from
# the pin numbering, which v4.28's comments had wrong (they claimed GP26="POT-0"):
#   GP26 = ADC0 = POT-3 = RV8      GP28 = ADC2 = POT-1 = RV6
#   GP27 = ADC1 = POT-2 = RV7      GP29 = ADC3 = POT-0 = RV5
# GP28/29 remain the spare fallback pins.
#
# (v4.29) GP26 now carries the REAL pack-voltage divider, not a pot: RV8 has been
# removed from the board and a 22k/2k7 divider fitted from the +20V rail (J11 pin 2)
# to its footprint, with 1u across the 2k7 and 1k/100n at the pin.
#
# (v4.33) GP27 is no longer read. It carried a bench pot (RV7) scaled by a placeholder
# linear constant and reported on the wire as board_temp_dC — a pot position dressed as
# a temperature. The planned analogue NTC front end for it was never built and is now
# superseded by the DS18B20 on GP6 below, which is digital and factory-calibrated, so
# the Beta/Steinhart-Hart curve the analogue path would have needed does not arise.
# RV7 stays fitted on the board; the firmware simply ignores it. GP27/28/29 are spares.
PACK_VOLTAGE_ADC_PIN = 26   # GP26 / ADC0 — pack divider (was RV8 / "POT-3")
pack_voltage_adc = ADC(Pin(PACK_VOLTAGE_ADC_PIN))

# ---------------------------------------------------------------------------
# DS18B20 board temperature — 1-Wire on GP6 (v4.33)
# ---------------------------------------------------------------------------
# GP6 was reserved for a panel meter that is not being fitted. It is free of every
# timing-critical function: the drive/sample PWM pair is GPIO4/5 on slice 2 (DESIGN
# §11), and GP6 is slice 3 used here as a plain open-drain GPIO, so the same-slice
# phase-locking invariant is untouched.
#
# HARDWARE (required, not optional): an external 4.7k pull-up from DQ to +3V3. The
# RP2040's internal pull-up is ~50-80k, which against even 50-100 pF of bus capacitance
# gives a rise time of several µs — and the master samples a read slot ~15 µs in. It can
# appear to work on a short lead and then fail intermittently, which is the worst way for
# it to fail. The MicroPython driver sets the pad OPEN_DRAIN|PULL_UP regardless; that is
# not a substitute. Sensor runs from +3V3 (NOT +5 V — DQ must not exceed the RP2040 rail)
# in normal 3-wire mode, NOT parasite power (parasite needs an active strong pull-up
# during conversion, which this pin cannot provide while the sweep is running).
DS18B20_PIN = 6

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
# (v4.37) Max polls of GP15 in EITHER spin of read_raw_bytes_hold() before the ADC
# is declared not-converting. This is NOT sized to a conversion time.
#
# A HEALTHY spin here is 1-2 ms, not microseconds: DESIGN §7 records the poll
# catching only ~1-in-6 BUSY-high windows, and v4.34 measured per-cell interpreter
# cost at ~2.3 ms "dominated by the BUSY sync" (see the note above the settle
# block). cal_63 cross-checks it — 63 cells at 6.88 Hz is 2.31 ms/cell. The wait is
# also STOCHASTIC and scales with the PWM period, so its tail is not knowable from
# source. That is the whole argument for a generous cap.
#
# THE REGRESSION TO FEAR IS A FALSE ABORT MID-SWEEP, not a slow one. The abort is a
# once-per-outage event costing at most 2x this in IRQ-off time; a cap set too tight
# silently truncates good sweeps. Read busy_spin_min_left from 'B' after a long run
# before ever lowering this — that field exists precisely so this number stays
# auditable instead of being a guess.
#
# MEASURED on this board 2026-08-12 (RP2040-Zero, GP15, 50k-iteration REPL runs,
# spread < 0.03 % across 5 repeats):
#     b.value() alone .................. 5.816 µs
#     bounded spin, as written below .... 9.024 µs/iteration
#     same bound folded into the while
#       condition instead ............... 9.008 µs — no cheaper, so the clearer
#                                         body-test form is kept
#     for/range instead of a counter .... 9.848 µs — SLOWER as well as allocating
# 6000 x 9.024 µs = 54.1 ms. Re-measure and reset this if the RP2040-Zero module or
# the MicroPython build is ever changed; the recipe is in the v4.37 CHANGELOG entry.
#
# WHY 6000 AND NOT THE 2200 THIS SHIPPED WITH FIRST. 2200 (19.9 ms) was sized at
# ~10x the ~2.3 ms typical per-cell BUSY sync. Test A then measured what a healthy
# spin ACTUALLY costs at its tail: busy_spin_min_left came back 887 of 2200 over
# 118k cell reads on cal_2x11_v5, i.e. the worst legitimate spin used 1313
# iterations = 11.85 ms — 60 % of the budget, a margin of 1.68x rather than 10x.
# Spin 1's wait scales with the PWM period, so at the DESIGN §8 floor of 2 kHz
# (500 µs vs 320 µs) the same tail projects to ~18.5 ms, or 93 % of a 2200 cap:
# false aborts mid-sweep, which is the regression this whole change most needs to
# avoid. 6000 restores ~2.9x margin against that projection.
# The price is paid only on a real abort — 2 x 54 ms of IRQ-off time, once per
# outage — against a false abort that would silently truncate good sweeps forever.
BUSY_SPIN_LIMIT = 6000
# THE COST, stated plainly because it is the one number this change puts at risk:
# the poll period rises 5.816 -> 9.024 µs, i.e. +55 %. The pre-v4.37 loop body was a
# bare `pass`. Against DESIGN §7's ~15 µs BUSY-high window that still leaves 1.66
# polls per window (was 2.6), so every window should still be caught and the catch
# behaviour should not change — but whether 3.2 µs of extra latency in noticing BUSY
# FALL matters cannot be settled from source: it needs the LTC2508 data-hold window
# (no datasheet in the tree) or a scope. The empirical answer is a before/after run
# comparing sweep rate, per-channel σ and gate_reject_count against the pre-change
# baseline of 16.13 Hz on cal_2x11_v5.

# ---------------------------------------------------------------------------
# Mode 2 output rate cap and band-boundary settling
# ---------------------------------------------------------------------------
MIN_EMIT_MS = 10      # emit W records at most every 10 ms (100 Hz max)
EMIT_BLOCK_WARN_MS = 50  # an emit print() slower than this counts as a host stall
                         # (v4.27 diagnostic). A normal emit is a few ms, so this sits
                         # an order above nominal and cannot trip on ordinary jitter.
                         # It does NOT change the emit — see emit_block_count.
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
                        # v4.34 is what makes this an absolute floor in fact as well as in
                        # name — see the settle block in acquire_mode2().
                        # 10000 WAS TRIED AND REVERTED (2026-08-09). Do not re-run this blind:
                        # the experiment was done and the result is worth keeping.
                        # The 2026-08-09 band-swap A/B showed the transient for a 12.5x power
                        # step (P ∝ pulse²×freq, 10 µs/25 kHz <-> 100 µs/3.125 kHz) runs
                        # ~9-11 ms, so 3000 is genuinely short FOR THAT PROFILE. Raising the
                        # floor to 10000 did exactly what it was predicted to do: the 100 µs
                        # band's leading gradient collapsed from 8.1/7.8/5.3 ns to 3.3/3.9/3.0,
                        # and the 25 kHz band's from 5.2/5.2/4.3 to 2.2/2.3/2.1 — both bands,
                        # both protocol orders, settling problem solved.
                        # It was reverted anyway, for two reasons. (1) The cost is real and
                        # global: 12.1 -> 10.5 Hz here, and ~6.2 -> ~4.8 Hz on
                        # cal_63_air_bat_v3's 7 boundaries, against the 6.88-6.92 Hz DESIGN §8
                        # records as that profile's measured rate. cal_63's adjacent bands step
                        # ×1.5, not ×12.5, so they very likely never needed it. (2) It did NOT
                        # fix the thing it was raised to chase — the cell-0 outlier population
                        # survived a 10 ms settle at 23.3 events/1000 above 100 mV. That is the
                        # useful negative result: with ~16 ms of dwell before the sample, the
                        # transient is long over, so VARIABLE EMIT DWELL IS NOT THE MECHANISM.
                        # If a profile with a large adjacent-band energy step needs this, the
                        # right shape is a per-boundary floor scaled to the step, not a bigger
                        # global constant.
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
OUTLIER_GATE_MAX_RUN = 4  # consecutive rejections a cell may take before the gate
                        # YIELDS: it empties the ring and accepts the sample. This is
                        # what keeps the gate a glitch filter instead of a lock (v4.35).
                        # The §7 artefacts it exists for are single-sample events at
                        # exactly 1/2 and 1/4 of the true value, and a cell is sampled
                        # once per sweep, so four in a row is not a glitch population —
                        # it is the signal having moved. 4 costs at most 3 sweeps of
                        # lag (~0.24 s at 12.7 Hz) on a genuine step; going lower
                        # starts letting real truncation artefacts re-prime a cell.
                        # DO NOT raise this to "be safer": time spent rejecting is
                        # time the cell is not measuring, and the v4.34 failure was
                        # precisely an unbounded rejection run.

# ---------------------------------------------------------------------------
# Pack-voltage sensing + low-voltage failsafe (v4.28)
# ---------------------------------------------------------------------------
ADC_OVERSAMPLE_N = 64          # raw ADC reads averaged per pack-voltage sample
SENSOR_SAMPLE_MS = 1000        # pack re-sampled + failsafe re-checked, 1 Hz. Board temp
                               # is NOT on this cadence — see DS18B20_INTERVAL_MS.
SENSOR_REPORT_MS = 60_000      # 'P' telemetry line emitted this often
# PACK: real hardware as of v4.29. 22k/2k7 divider (nominal ratio 9.1481) from the
# +20V rail, which is the pack terminal voltage — D4 is a SHUNT reverse-polarity
# clamp, not a series diode, so there is no forward drop to compensate and no drift
# with load current. Bench calibration 2026-08-07: 2.460 V at the ADC pin measured
# against 22.59 V at the pack => ratio 9.18293 (+0.38% of nominal, i.e. R_top
# ~22.094k, inside 1% tolerance — the build checks out). Second point 2.457 V /
# 22.55 V gives 9.17786, agreeing to 0.055%: the divider is stable and correct.
#
# The reference is NOT 3.300 V. With the old FS=25000 still loaded, a pin measured at
# 2.457 V reported 18740 mV, which solves for ADC_VREF = 3.2777 V — the RP2040-Zero's
# 3V3 LDO is 0.67% LOW. (It is the ADC reference and is not a precision part.) That
# single reading, taken against a KNOWN constant, is the full calibration: it absorbs
# the divider ratio and the reference together.
#   3.2777 V x 9.17786 = 30.083 V   ->   30_083 mV
# Re-deriving from any future pair is the same one-liner: scale this constant by
# V_dmm / V_reported. Redo it if the RP2040-Zero module is ever swapped — the LDO
# term is per-module, and it is 0.73% (221 mV at full scale), not a rounding error.
# 1 LSB = 7.35 mV at the pack; 25.2 V (6S full) sits at 83.8% of range.
PACK_VOLTAGE_FULLSCALE_MV = 30_083     # 0-VREF ADC <-> 0-30.083V pack (fully calibrated)
# (v4.36) TEST BUILD FLOOR — 19_000, NOT the DESIGN §12 working floor of 21_000.
# Lowered deliberately on 2026-08-12 to characterise the detector below the §12
# floor: at 21.02 V pack the +15V rail still measured 15.20 V on a DMM, i.e. the
# L7815 has ~3.8 V of headroom left and the 21_000 trip is protecting the CELLS,
# not the rail. Nothing electrical stops the board running to ~17.2 V in.
#
# WHAT THIS COSTS, measured on the pack fitted that day: four cells at 3.84 V at
# rest, the remaining two at 2.83 V — a badly imbalanced string. Pack volts divided
# by six does NOT describe it. At a 19_000 trip the weak pair is dragged to roughly
# 2.0-2.1 V, below the ICR18650-26C 2.75 V cutoff and into the region where copper
# current-collector dissolution starts. Cells taken there can develop internal
# shorts ON THE NEXT CHARGE. This floor is for a scrap pack on a supervised bench,
# and it must go back to 21_000 before any pack that is meant to survive.
PACK_VOLTAGE_TRIP_MV = 19_000           # hard floor, mV — see the block above before raising/lowering
PACK_VOLTAGE_TRIP_CONSECUTIVE = 3      # consecutive sub-floor SENSOR_SAMPLE_MS samples
                                        # required to latch (debounce against ADC noise)
# (v4.30) The divider is an RC, and at boot it is still charging. Source impedance
# is 22k||2k7 = 2405 ohm against C_tap 1u + C_pin 100n, so tau = 2.65 ms; reaching
# one LSB (7.3 mV) of the settled value takes 8.3 tau = 22 ms. Worse, GP26 sits under
# the RP2040 pad's DEFAULT PULL-DOWN for the whole MicroPython boot, until
# ADC(Pin(26)) is constructed a few ms before pack_voltage_boot_check() runs — so the
# node is recovering from a depressed level exactly when the boot check samples it.
# 100 ms is ~38 tau, i.e. total settling with large margin, and is paid once at boot.
PACK_SENSE_SETTLE_MS = 100
# Boot samples must ALSO be spaced in time. Back-to-back they take ~1-2 ms in total
# and all three land inside the same transient, so the 3-sample debounce degenerates
# into a single sample of the worst moment. 20 ms apart makes it a real debounce.
PACK_VOLTAGE_BOOT_SAMPLE_MS = 20
# (v4.31) Pack-absent detection and re-arm hysteresis. The MCU is USB-powered and
# OUTLIVES the +20V rail — measured: the board ran normally with the rail decayed to
# 3.85 V. So switching the pack off, or swapping cells, drops the sense reading to
# near zero without the firmware having rebooted, and v4.30 and earlier read that as
# a catastrophically flat pack and latched. Clearing it then needed a physical MCU
# reset, which is not a reasonable price for changing a battery.
PACK_ABSENT_MV = 6_000     # below this the rail is OFF and we are running on USB. This
                           # is not a pack reading at all: a connected 6S pack cannot sit
                           # at 1 V/cell, and the +15V rail dropped out ~12 V higher up,
                           # so nothing is being discharged and there is nothing for the
                           # failsafe to protect. Suspend rather than latch.
PACK_REARM_MV = 19_500     # a returning pack must reach THIS to clear the latch, not
                           # merely clear PACK_VOLTAGE_TRIP_MV. 500 mV of hysteresis.
                           # Re-arming at the trip itself would let a genuinely flat pack
                           # switched off and back on return on its no-load recovery,
                           # re-arm, then sag straight back under load — the exact cycle
                           # the v4.28 hard latch exists to stop.
                           #
                           # (v4.36) TRACKS THE TRIP, and must keep tracking it. It was
                           # 21_500 against a 21_000 trip, chosen to double as the DESIGN
                           # §12 clean-window lower edge; that coincidence is gone now the
                           # trip is a test-build 19_000 and the 500 mV is the only thing
                           # this level still means. Leaving it at 21_500 would have made
                           # the hysteresis 2_500 mV: latch at 19.0 V, cycle the pack, and
                           # it returns below 21.5 V so the latch does NOT clear — and
                           # since the MCU is USB-powered, pulling the pack cannot reset
                           # it either. Recovery would mean unplugging USB mid-test.
                           # Restore BOTH to 21_500/21_000 together.

# ---------------------------------------------------------------------------
# DS18B20 timing + the hot-path budget that sets it (v4.33)
# ---------------------------------------------------------------------------
# 1-Wire is bit-banged, and each bit slot is ~70 µs with IRQs briefly off inside the
# driver. That is CPU time, and CPU time only: the PWM pair and the LTC2508's
# conversions are hardware and free-run through it. So the cost is purely how long the
# firmware is not free to do something else, and the ONLY place that can be afforded is
# the i==0 service point in acquire_mode2(), which already absorbs the ms-scale blocking
# emit print() and where a delay lands as EXTRA settling for cell 0 (see the v4.24 note
# in that loop) rather than as a corrupted read. Routing every 1-Wire access through
# service_sensors() enforces that by construction — it is the only Mode 2 call site.
#
# Budget per reading: kick ~2.2 ms (reset + 2 bytes), read ~7.6 ms (reset + 2 bytes +
# 9 bytes in). At 30 s that is ~10 ms per ~200 sweeps, i.e. one sweep in 200 running
# ~5% long. Well inside the 3x window-span guard the PC tools apply, and in the
# direction (more settling) that is benign.
DS18B20_INTERVAL_MS = 30_000   # complete convert+read cycle this often. Deliberately NOT
                               # SENSOR_SAMPLE_MS: board thermal time constants are
                               # minutes, so 1 Hz would be 30x the hot-path exposure for
                               # no information that the 60 s 'P' report could even carry.
DS18B20_CONVERT_MS = 800       # wait at least this long after 0x44 before reading the
                               # scratchpad. Datasheet max is 750 ms at 12-bit; the
                               # conversion is NEVER waited on inline — the state machine
                               # returns and is re-entered on a later service tick, so
                               # this costs nothing but latency.
TEMP_INVALID_DC = -32768       # board_temp_dC sentinel: NO READING (sensor absent, not
                               # responding, or CRC-failing). Cannot collide with a real
                               # reading — the part's range is -55..+125 °C = -550..+1250 dC.
DS_IDLE = 0                    # state machine: nothing pending, waiting for the interval
DS_CONVERTING = 1              # 0x44 issued, waiting out DS18B20_CONVERT_MS

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
                              # | 'rail_absent' (v4.37: Mode 2 aborted on a BUSY
                              #   timeout — drive safe, telemetry still running,
                              #   resumes itself when the pack returns)
active_profile_index = 0
mode2_profile_changed = False
dynamic_profile = None        # set by the D command; RAM only, lost on reset

# Pack-voltage sensing state (v4.28) — RAM only, lost on reset.
# pack_voltage_lockout is still never clearable by any serial command; as of v4.31
# the ONE thing that clears it without a reset is the pack physically going away and
# a healthy one returning (see PACK_ABSENT_MV / PACK_REARM_MV).
pack_voltage_lockout = False
pack_voltage_low_streak = 0
pack_absent = False           # v4.31: rail below PACK_ABSENT_MV — USB-only, failsafe
                              # suspended because there is no pack to protect
last_pack_mV = 0
last_sensor_sample_ms = ticks_ms()
last_sensor_report_ms = ticks_ms()

# Rail-absent supervisory state (v4.37) — RAM only, lost on reset. See
# service_rail_absent(). rail_absent_announced doubles as "have we already done the
# one-time entry work", which is what keeps the wire quiet during a long outage.
rail_absent_announced = False
rail_absent_entered_ms = 0
rail_last_check_ms = 0
rail_resume_ok_streak = 0
RAIL_RECHECK_MS = 1000        # cadence of the resume re-check. A ticks_diff gate, the
                              # house idiom — without it the streak below would count
                              # thousands of times a second against a pack_absent flag
                              # that only updates at 1 Hz.
RAIL_RESUME_CONSECUTIVE = 3   # consecutive healthy re-checks before pulsing restarts.
                              # Mirrors PACK_VOLTAGE_TRIP_CONSECUTIVE at the same
                              # cadence, i.e. ~3 s of a steady rail either way.

# DS18B20 board-temperature state (v4.33). Starts INVALID rather than 0: until the
# first conversion completes there is genuinely no reading, and 0 dC is a plausible
# enough temperature to be believed.
last_board_temp_dC = TEMP_INVALID_DC
ds_bus = None                 # onewire.OneWire once constructed; None if unavailable
ds_state = DS_IDLE
ds_present = False            # last known sensor health — transitions are printed, and
                              # only transitions, so a sensor failing during a Mode 2
                              # sweep cannot spray the wire with per-attempt errors (a
                              # print in that loop is the v4.27 emit-block hazard)
ds_last_cycle_ms = ticks_ms()
ds_convert_started_ms = ticks_ms()
ds_scratch = bytearray(9)     # pre-allocated scratchpad buffer — see _ds_read_scratch()


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
emit_block_count = 0  # DIAGNOSTIC (v4.27): emits whose print() took longer than
                      # EMIT_BLOCK_WARN_MS. print() writes to USB CDC and BLOCKS
                      # when the host stops draining the pipe; the PWM keeps
                      # free-running at cell[0]'s config throughout (see the
                      # v4.24 note in acquire_mode2), so a long stall parks the
                      # rig on one band's duty instead of sweeping all of them.
                      # Measured 2026-07-29 23:03-23:50: a 47-minute host stall
                      # dropped ~90% of frames and cooled the rig enough to move
                      # the operating point (+10 mV on the 9 us band to +78 mV on
                      # 100 us). Silent until now — hence these counters.
emit_block_ms_max = 0 # DIAGNOSTIC (v4.27): longest single emit print(), ms.
                      # Both read out and reset via 'B'.
gate_reject_count = 0   # DIAGNOSTIC (v4.35): outlier-gate rejections — samples dropped
                        # as implausible. Read out via 'B'. Before v4.35 the gate was
                        # entirely silent, which is why a latched profile cost a bench
                        # session to diagnose rather than one 'B'.
gate_reprime_count = 0  # DIAGNOSTIC (v4.35): times a cell hit OUTLIER_GATE_MAX_RUN
                        # consecutive rejections and the gate yielded, emptying the ring.
                        # Read out via 'B'. The ratio to gate_reject_count is the number
                        # that matters: reject-heavy with near-zero reprimes means the
                        # gate is catching glitches, which is its job; reprimes climbing
                        # with the signal means the gate is fighting real signal and
                        # OUTLIER_GATE_FRAC is too tight for the profile in use.
busy_timeout_count = 0  # DIAGNOSTIC (v4.37): times a read_raw_bytes_hold() spin hit
                        # BUSY_SPIN_LIMIT and abandoned the sample. Answers the
                        # question the 2026-08-12 outage could not be asked — "did
                        # this happen" — instead of leaving it to be reconstructed
                        # from a truncated session log. Read out via 'B'.
                        # NOTE busy_high_count above becomes genuinely useful now:
                        # it freezes the instant BUSY stops moving, so a near-zero
                        # busy_high_count next to a non-zero busy_timeout_count is
                        # the signature of an outage spanning the whole read window.
busy_spin_min_left = BUSY_SPIN_LIMIT
                        # DIAGNOSTIC (v4.37): smallest residual ever seen on spin 1,
                        # i.e. HOW CLOSE A HEALTHY SPIN HAS COME TO THE CAP. This is
                        # the field that de-risks BUSY_SPIN_LIMIT — it turns the
                        # constant from a guess into a measured margin. If it ever
                        # reads small on a healthy run, the cap is too tight and a
                        # false abort is coming. Resets to BUSY_SPIN_LIMIT, not 0.
rail_absent_ms_max = 0  # DIAGNOSTIC (v4.37): longest single rail-absent dwell, ms.
                        # Companion to a count in the same shape as
                        # emit_block_ms_max — that field type is already established
                        # in this record. Read out and reset via 'B'.
_busy_spin_left = BUSY_SPIN_LIMIT
                        # Scratch: spin 1's residual for the cell just read. Module
                        # global rather than a return value to keep the hot path
                        # allocation-free, same reasoning as _held_irq below. Folded
                        # into busy_spin_min_left by acquire_mode2 OUTSIDE the
                        # IRQ-off section.


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
    write (see header note).

    (v4.37) BOTH spins are bounded by BUSY_SPIN_LIMIT polls. On expiry this
    function RE-ENABLES IRQS ITSELF and returns None. A None return means the ADC
    is not converting — typically the +20V rail switched off while the MCU stays
    alive on USB. THE CALLER MUST ABANDON THE SAMPLE AND MUST NOT CALL
    enable_irq(_held_irq) AGAIN. Before v4.37 both loops were unbounded, so a
    dead ADC spun here forever with interrupts globally masked, which took USB
    CDC down with it and silenced the board completely — including the
    'PACK: rail absent' message the failsafe exists to print.

    The two spins are not symmetric. Spin 1 waits for the next MCLK trigger: up
    to a full PWM period, times the ~6 windows the poll misses (DESIGN §7), so it
    is the long variable one, it is where nearly all iterations are spent, and it
    is the only one whose margin is worth tracking. Spin 2's wait is
    hardware-bounded by the conversion itself (~15 µs at 10 kHz, i.e. a couple of
    polls); it is bounded too, but for a different reason — an ADC that is powered
    and stuck mid-conversion, which the rail check cannot catch.

    SPIN 1 IS THE ONE THAT TRAPS ON RAIL LOSS, and that is now known from the
    schematic rather than inferred: GP15 carries a 1k pull-down, with 110R in
    series from the ADC's BUSY output (chosen to damp digital noise). An
    unpowered ADC stops driving BUSY, the pull-down takes GP15 firmly LOW, and
    `while not busy_pin.value()` therefore spins. Deterministic, not a floating
    pin — so the abort path is exercised by every rail loss, not just some."""
    global busy_high_count, _held_irq, _busy_spin_left, busy_timeout_count
    _held_irq = disable_irq()
    n = BUSY_SPIN_LIMIT
    while not busy_pin.value():   # wait for MCLK to fire (BUSY high)
        n -= 1
        if not n:
            busy_timeout_count += 1
            enable_irq(_held_irq)
            return None
    _busy_spin_left = n
    busy_high_count += 1
    n = BUSY_SPIN_LIMIT
    while busy_pin.value():        # wait for conversion complete (BUSY low)
        n -= 1
        if not n:
            busy_timeout_count += 1
            enable_irq(_held_irq)
            return None
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
    global emit_block_count, emit_block_ms_max
    global gate_reject_count, gate_reprime_count
    global state, busy_spin_min_left   # v4.37: rail-loss abort + spin margin

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
    # v4.35: consecutive outlier-gate rejections per cell. Bounds how long the
    # gate may hold out against the ADC — see the gate block in the loop below.
    reject_run = [0] * n

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
            if data_bytes is None:
                # v4.37: BUSY never moved within BUSY_SPIN_LIMIT polls, so the ADC
                # is not converting. With the +20V rail switched off while the MCU
                # stays alive on USB that is the NORMAL case, not an error — and
                # before v4.37 control never got here at all: it spun in
                # read_raw_bytes_hold() forever with IRQs masked, taking USB CDC
                # down with it. The board went completely silent, including the
                # 'PACK: rail absent' line the failsafe exists to print, which is
                # why the 2026-08-12 12:48 outage left no telemetry to diagnose.
                #
                # IRQs were ALREADY RESTORED inside read_raw_bytes_hold() — do not
                # call enable_irq() here. Bail before the boundary freq() writes
                # below: the PWM must not be reconfigured for a sample we discard.
                # Leave the sweep and let the main loop's supervisory state sort
                # out what happened (service_rail_absent).
                state = 'rail_absent'
                break
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
            # v4.37: fold spin 1's residual into the running minimum. Outside the
            # IRQ-off section on purpose — this is bookkeeping, not hot path.
            if _busy_spin_left < busy_spin_min_left:
                busy_spin_min_left = _busy_spin_left
            # v4.34: cell[i]'s freq/CC are LIVE from here, and only from here.
            # Everything before this instant — above all read_raw_bytes_hold()'s
            # BUSY sync — was spent at cell[i-1]'s configuration and cannot count
            # towards cell[i]'s settling. See the settle block below.
            t_cfg = ticks_us()
            raw = raw14_from_bytes(data_bytes)

            # Outlier gate. v4.35 rebuilt this so it cannot become an absorbing
            # state (CHANGELOG.md v4.35 has the session that proved it was one).
            # Three properties the old shape lacked, all of them load-bearing:
            #   (a) a rejected sample is DROPPED, never substituted back into the
            #       ring, so "every slot equals the mean" is no longer a fixed
            #       point of the update and there is no floor-division ratchet;
            #   (b) a run of OUTLIER_GATE_MAX_RUN rejections means the signal has
            #       genuinely moved, so the gate yields and re-primes the cell;
            #   (c) it arms only on a FULL ring, so a cell still settling after
            #       G/Q cannot seed the gate with a warm-up value.
            accept = True
            cnt = rolling_count[prev]
            if cnt >= avg_depth:
                mean_raw = rolling_sum[prev] // cnt
                dev = raw - mean_raw
                if dev < 0:
                    dev = -dev
                gate = mean_raw if mean_raw >= 0 else -mean_raw
                gate //= OUTLIER_GATE_FRAC
                if gate < OUTLIER_GATE_MIN:
                    gate = OUTLIER_GATE_MIN
                if dev > gate:
                    run = reject_run[prev] + 1
                    if run < OUTLIER_GATE_MAX_RUN:
                        # Isolated glitch: DROP the sample. The ring keeps its
                        # real history and the reported mean simply holds for
                        # this sweep. Nothing is written back, so there is no
                        # state the gate can drive itself into.
                        reject_run[prev] = run
                        gate_reject_count += 1
                        accept = False
                    else:
                        # Sustained excursion — this is signal, not a glitch.
                        # Empty the ring and take the sample: the cell then
                        # re-converges on the new operating point in avg_depth
                        # sweeps, with the gate disarmed until the ring refills,
                        # instead of crawling there one accepted sample in
                        # OUTLIER_GATE_MAX_RUN.
                        reject_run[prev] = 0
                        rolling_sum[prev] = 0
                        rolling_count[prev] = 0
                        rolling_idx[prev] = 0
                        gate_reprime_count += 1
                else:
                    reject_run[prev] = 0
            if accept:
                # The fill branch adds without subtracting. v4.34 and earlier
                # always subtracted, which was correct only because `rolling`
                # is zero-initialised and each slot is therefore 0 on its first
                # write. That holds for the first fill and NOT for a re-prime,
                # where the slots still carry the previous generation's values.
                idx = rolling_idx[prev]
                if rolling_count[prev] < avg_depth:
                    rolling_sum[prev] += raw
                    rolling_count[prev] += 1
                else:
                    rolling_sum[prev] += raw - rolling[prev][idx]
                rolling[prev][idx] = raw
                rolling_idx[prev] = (idx + 1) % avg_depth

            # Sleep out the remainder of this cell's period.
            # At band/drive-energy boundaries add settle_i extra periods
            # (>= BOUNDARY_PRIME, floored to SETTLE_FLOOR_US of real time —
            # v4.24) so the coil reaches steady state before the next cell
            # reads this cell's SDOB, breaking the contamination cascade.
            #
            # v4.34: the settle is measured from t_cfg, not from t0. The old
            # `remaining = period - elapsed - 2; remaining += period * settle`
            # deducted `elapsed` — time spent at the PREVIOUS cell's config,
            # dominated by the BUSY sync — from this cell's budget, so the
            # delivered settle was `period*settle - (elapsed - period)`. With
            # per-cell interpreter cost ~2.3 ms (measured) against a 40 µs
            # period, cell 0 of a 25 kHz band received ~0.6 ms of the intended
            # 3 ms. SETTLE_FLOOR_US was therefore not an absolute floor on ANY
            # band whose period is shorter than the per-cell cost — which is
            # every band in every profile. v4.24 was still a real improvement
            # (before it the sleep went negative and there was no settle at
            # all, which is why it bench-verified), but it did not deliver what
            # its name says. Non-boundary cells are unchanged.
            elapsed = ticks_diff(ticks_us(), t0)
            remaining = period_i - elapsed - 2
            if needs_settling:
                settle_left = period_i * settle_i - ticks_diff(ticks_us(), t_cfg)
                if settle_left > remaining:
                    remaining = settle_left
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
                    # v4.27: time the emit. print() blocks on USB CDC when the host
                    # stops reading, and the PWM free-runs at cell[0]'s config while
                    # it does (see the v4.24 note above), so an unbounded stall is a
                    # silent change to BOTH timing and thermal load. Measuring is all
                    # that happens here: the call, its position in the loop and the
                    # sequencing around it are untouched, deliberately — a skip-when-
                    # blocked guard needs bench proof that this port reports stdout
                    # writability at all, and it would sit in the hot path.
                    # ticks_ms, not ticks_us: ticks_us wraps every ~17.9 min and
                    # ticks_diff is only valid over half that (~8.9 min), so the
                    # 47-minute stall this exists to catch would decode wrong.
                    # ticks_ms wraps at ~12.4 days. 1 ms resolution is ample against
                    # a 50 ms threshold.
                    _emit_t0 = ticks_ms()
                    print(','.join(fields))
                    _emit_ms = ticks_diff(ticks_ms(), _emit_t0)
                    if _emit_ms > EMIT_BLOCK_WARN_MS:
                        emit_block_count += 1
                        if _emit_ms > emit_block_ms_max:
                            emit_block_ms_max = _emit_ms
                    last_emit_ms = now
                if ticks_diff(now, last_poll_ms) >= COMMAND_POLL_MS:
                    check_for_commands(timeout_ms=0)
                    last_poll_ms = now
                # v4.28: the main loop's service_sensors() call doesn't run while
                # control sits in this function's own while loop (i.e. for the
                # whole sweep), so it's serviced here too, at the same i==0 cadence
                # point as the emit/poll above. A trip here exits the sweep
                # immediately (break, then the while-loop condition below is
                # already false) rather than waiting for the ~145 ms sweep to
                # finish like a normal 'E' stop would — deliberate for the safety
                # path.
                service_sensors()
                if pack_voltage_lockout:
                    break


# ---------------------------------------------------------------------------
# Safe state
# ---------------------------------------------------------------------------
def set_safe_state():
    drive_coil_pwm.duty_u16(0)
    sample_coil_pwm.duty_u16(2 ** 16 - 1)
    drl_pin.irq(handler=None)
    print('SAFE: Drive OFF / Sampling OFF / Interrupts OFF')


# ---------------------------------------------------------------------------
# Pack-voltage sense + low-voltage failsafe (v4.28)
# ---------------------------------------------------------------------------
def _adc_oversampled_u16(adc):
    """Average ADC_OVERSAMPLE_N raw 16-bit reads from one ADC channel."""
    total = 0
    for _ in range(ADC_OVERSAMPLE_N):
        total += adc.read_u16()
    return total // ADC_OVERSAMPLE_N


def read_pack_voltage_mv():
    """Oversampled pack-voltage read through the 22k/2k7 divider on GP26,
    bench-calibrated linear scale (see PACK_VOLTAGE_FULLSCALE_MV)."""
    return _adc_oversampled_u16(pack_voltage_adc) * PACK_VOLTAGE_FULLSCALE_MV // 65535


# ---------------------------------------------------------------------------
# DS18B20 board temperature — 1-Wire on GP6 (v4.33)
# ---------------------------------------------------------------------------
# Everything below is called ONLY from service_sensors(). That is the placement rule
# the whole design rests on — see the DS18B20_INTERVAL_MS comment block.
def _ds_mark_present(present, why):
    """Record sensor health, printing ONLY on a transition. Both messages name the
    resulting state, following the v4.32 PACK: convention — the state you most need
    to be sure of is the one that was reached silently."""
    global ds_present, last_board_temp_dC
    if present == ds_present:
        return
    ds_present = present
    if present:
        print('DS18B20: responding on GP{0:d} — board temperature live'.format(
            DS18B20_PIN))
    else:
        last_board_temp_dC = TEMP_INVALID_DC
        print('DS18B20: no reading on GP{0:d} ({1}) — board temperature '
              'reported invalid, acquisition unaffected'.format(DS18B20_PIN, why))


def _ds_kick_convert():
    """Start a temperature conversion on every device on the bus (SKIP ROM + CONVERT T).
    Returns immediately — the ~750 ms conversion is NEVER waited on inline. ~2.2 ms."""
    if ds_bus is None:
        return False
    try:
        if not ds_bus.reset():
            _ds_mark_present(False, 'no presence pulse')
            return False
        ds_bus.writebyte(0xCC)      # SKIP ROM
        ds_bus.writebyte(0x44)      # CONVERT T
        return True
    except Exception as e:
        _ds_mark_present(False, 'bus error: {0}'.format(e))
        return False


def _ds_read_scratch():
    """Read the scratchpad and return deci-degC, or None on any failure.

    SKIP ROM (0xCC), not MATCH ROM: there is one device on this bus, and addressing it
    by its 64-bit ROM code — which is what ds18x20.read_temp() does — writes 8 extra
    bytes, ~4.8 ms of blocking bit-bang, to reach the only thing that could answer.

    All 9 bytes are read rather than the 2 that carry the temperature. The extra 7
    bytes cost ~4.2 ms and buy the CRC, which is the difference between a corrupted bit
    showing up as a wrong temperature and it showing up as no temperature. On a line
    running past a pulse-induction front end, that is worth 4 ms once every 30 s."""
    global last_board_temp_dC
    if ds_bus is None:
        return None
    try:
        if not ds_bus.reset():
            _ds_mark_present(False, 'no presence pulse')
            return None
        ds_bus.writebyte(0xCC)      # SKIP ROM
        ds_bus.writebyte(0xBE)      # READ SCRATCHPAD
        # Fill the pre-allocated buffer and read it back from the buffer, NOT from
        # readinto()'s return value: it fills in place and different onewire.py
        # revisions disagree on whether they also return it. Pre-allocated at module
        # scope because this runs inside the Mode 2 loop, and a per-read bytearray is a
        # heap allocation that can trigger a GC pass at an unpredictable moment.
        ds_bus.readinto(ds_scratch)
        buf = ds_scratch
    except Exception as e:
        _ds_mark_present(False, 'bus error: {0}'.format(e))
        return None
    if ds_bus.crc8(buf):
        # crc8 over all 9 bytes (byte 8 is the CRC itself) is 0 when intact.
        _ds_mark_present(False, 'scratchpad CRC fail')
        return None
    raw = (buf[1] << 8) | buf[0]
    if raw & 0x8000:
        raw -= 0x10000              # two's complement — the part reads to -55 °C
    # Known footgun, guarded by sequencing rather than by a value check: the DS18B20's
    # power-on scratchpad default is 0x0550, exactly +85.0 °C, so a scratchpad read that
    # beats the first conversion returns a plausible hot reading instead of an error.
    # This path is only ever reached DS18B20_CONVERT_MS after a CONVERT T that returned a
    # presence pulse, so it cannot be hit except by the sensor resetting inside that
    # window. Not value-filtered: +85.0 is a legal reading, and rejecting it would mean
    # silently dropping a real over-temperature — the one reading you must not lose.
    # 12-bit default: 1 LSB = 1/16 °C. Integer maths only (no floats on the wire, §9),
    # and floor division is used deliberately in both directions: -0.05 °C reporting as
    # -1 dC rather than 0 dC is the honest rounding for a sub-zero reading.
    _ds_mark_present(True, '')
    last_board_temp_dC = raw * 10 // 16
    return last_board_temp_dC


def service_ds18b20(now):
    """One step of the convert/read state machine. Called from service_sensors() only.

    Split into two transactions across service ticks so the 750 ms conversion is never
    waited on: the longest thing this can ever block for is the ~7.6 ms scratchpad read.
    A failure at either step falls back to IDLE and retries on the next interval — there
    is no error latch, because a sensor that comes back should just start working."""
    global ds_state, ds_last_cycle_ms, ds_convert_started_ms
    if ds_bus is None:
        return
    if ds_state == DS_IDLE:
        if ticks_diff(now, ds_last_cycle_ms) >= DS18B20_INTERVAL_MS:
            ds_last_cycle_ms = now
            if _ds_kick_convert():
                ds_convert_started_ms = now
                ds_state = DS_CONVERTING
    elif ds_state == DS_CONVERTING:
        if ticks_diff(now, ds_convert_started_ms) >= DS18B20_CONVERT_MS:
            _ds_read_scratch()      # sets last_board_temp_dC, or marks absent
            ds_state = DS_IDLE


def ds18b20_init():
    """Construct the bus and probe for the sensor, then kick the first conversion so
    the first 'P' report carries a real number rather than the startup sentinel.

    Runs AFTER pack_voltage_boot_check() — the "never fires a pulse below the floor"
    guarantee stays first in the boot order, and nothing here is allowed to delay it.
    Every failure path is non-fatal: no sensor means no temperature, not no detector."""
    global ds_bus, ds_state, ds_last_cycle_ms, ds_convert_started_ms
    ds_last_cycle_ms = ticks_ms()
    if onewire is None:
        print('DS18B20: onewire module not available in this MicroPython build — '
              'board temperature reported invalid, acquisition unaffected')
        return
    try:
        ds_bus = onewire.OneWire(Pin(DS18B20_PIN))
    except Exception as e:
        ds_bus = None
        print('DS18B20: bus init failed on GP{0:d} ({1}) — board temperature '
              'reported invalid, acquisition unaffected'.format(DS18B20_PIN, e))
        return
    # Boot announces its result UNCONDITIONALLY, unlike the steady-state path which
    # prints only on transitions. ds_present starts False, so a sensor missing at boot
    # is not a transition and _ds_mark_present() would say nothing at all — leaving the
    # "no temperature sensor" state indistinguishable from a healthy silent one. That is
    # the same trap v4.32 closed on the PACK: messages.
    if _ds_kick_convert():
        _ds_mark_present(True, '')
        ds_convert_started_ms = ticks_ms()
        ds_state = DS_CONVERTING
    else:
        print('DS18B20: not detected on GP{0:d} at boot — board temperature reported '
              'invalid, acquisition unaffected (retrying every {1:d} s)'.format(
                  DS18B20_PIN, DS18B20_INTERVAL_MS // 1000))


def _pack_voltage_trip_check(pack_mV):
    """Debounced low-voltage latch. Once tripped, pack_voltage_lockout stays
    True until a physical power-cycle clears the RAM state — no serial
    command re-arms it (see CHANGELOG v4.28: an auto/soft-resume risks
    repeating the over-discharge incident that motivated this).

    (v4.31) One exception, and only one: if the rail drops below PACK_ABSENT_MV
    the pack is GONE, not flat — we are on USB power. The failsafe is suspended
    for as long as that holds, and released when a pack returns at or above
    PACK_REARM_MV. This is still not a serial re-arm: it takes physically
    removing the pack and presenting a healthy one."""
    global pack_voltage_lockout, pack_voltage_low_streak, pack_absent, state
    if pack_mV < PACK_ABSENT_MV:
        # Rail off / USB-only. Neither latch nor clear here — a reading taken with
        # no pack present says nothing about any pack. Just suspend and wait.
        pack_voltage_low_streak = 0
        if not pack_absent:
            pack_absent = True
            print('PACK: rail absent ({0:d} mV) — USB power assumed, failsafe '
                  'suspended until a pack returns'.format(pack_mV))
        return
    if pack_absent:
        # First real reading after the rail came back. (v4.32) EVERY path through
        # here prints, and every message ends '— failsafe armed'. v4.31 printed only
        # when there was a latch to clear, so the common case (USB-first boot, pack
        # switched on later) transitioned in silence and left no way — from the log
        # or from the wire — to tell an armed failsafe from a still-suspended one.
        # That is the one state you most need to be sure you are not in.
        pack_absent = False
        if pack_mV >= PACK_REARM_MV:
            if pack_voltage_lockout:
                pack_voltage_lockout = False
                print('PACK: present again at {0:d} mV — lockout cleared, '
                      'failsafe armed'.format(pack_mV))
            else:
                print('PACK: present again at {0:d} mV — failsafe armed'.format(
                      pack_mV))
        else:
            print('PACK: present again at {0:d} mV, below re-arm floor {1:d} mV — '
                  'lockout state unchanged, failsafe armed'.format(
                      pack_mV, PACK_REARM_MV))
        # Either way the normal trip logic below resumes immediately, so a pack that
        # comes back weak and keeps sagging still latches on its own merits.
    if pack_mV <= PACK_VOLTAGE_TRIP_MV:
        pack_voltage_low_streak += 1
    else:
        pack_voltage_low_streak = 0
    if pack_voltage_low_streak >= PACK_VOLTAGE_TRIP_CONSECUTIVE and not pack_voltage_lockout:
        pack_voltage_lockout = True
        state = 'stop'
        set_safe_state()
        print('LOCKOUT: pack voltage {0:d} mV <= floor {1:d} mV — pulsing '
              'disabled, power-cycle required to clear'.format(
                  pack_mV, PACK_VOLTAGE_TRIP_MV))


def service_rail_absent():
    """(v4.37) Supervisory resting state, entered when acquire_mode2 abandoned a
    sweep on a BUSY timeout.

    It does almost nothing on purpose. The main loop calls check_for_commands()
    and service_sensors() every pass REGARDLESS of state, so pack voltage, board
    temperature, the 60 s 'P' report and the whole v4.28/v4.31 failsafe keep
    running here without this function touching any of them. All it adds is (a)
    one announcement on entry, (b) a cadence-gated re-check that puts the sweep
    back when a healthy pack returns.

    NOT a scan scheduler (DESIGN §11). It selects no profile, sequences no cells,
    times no acquisition and takes no scheduling input from the PC. It restores
    the single thing the operator already commanded with 'G', after an
    involuntary interruption. A scheduler decides WHAT runs next; this decides
    only WHETHER the thing already running may continue — the same authority the
    v4.28 lockout and the v4.31 suspend/re-arm already exercise."""
    global state, rail_absent_announced, rail_absent_entered_ms
    global rail_last_check_ms, rail_resume_ok_streak, rail_absent_ms_max
    global last_pack_mV

    if not rail_absent_announced:
        set_safe_state()
        rail_absent_announced = True
        rail_absent_entered_ms = ticks_ms()
        rail_last_check_ms = rail_absent_entered_ms
        rail_resume_ok_streak = 0
        # A FRESH reading, not last_pack_mV: that can be a second stale, and this
        # one decision — rail loss versus a live ADC that stopped answering —
        # hangs entirely on it.
        mv = read_pack_voltage_mv()
        last_pack_mV = mv
        _pack_voltage_trip_check(mv)      # prints 'PACK: rail absent …' if < 6 V
        if state != 'rail_absent':
            # The failsafe latched (a FLAT pack, not an absent one) and has
            # already set state='stop'. Its decision wins; stand down.
            rail_absent_announced = False
            return
        if mv >= PACK_ABSENT_MV:
            # BUSY died with the pack reading healthy. That is NOT a rail loss and
            # must not auto-resume — resuming would just abort again. Stop and make
            # the operator look. This is also what makes a thrash loop impossible:
            # the one shape that could oscillate is caught here, at entry.
            print('ADC: BUSY silent for {0:d} polls with the pack at {1:d} mV — '
                  'NOT a rail loss; Mode 2 stopped, check the analogue supply '
                  'and GP15'.format(BUSY_SPIN_LIMIT, mv))
            state = 'stop'
            rail_absent_announced = False
            return
        print('PACK: rail lost mid-sweep at {0:d} mV — Mode 2 aborted, drive '
              'safe, pack/temp telemetry continues; resumes at >= {1:d} mV'.format(
                  mv, PACK_REARM_MV))
        return

    now = ticks_ms()
    if ticks_diff(now, rail_last_check_ms) < RAIL_RECHECK_MS:
        return
    rail_last_check_ms = now
    # PACK_REARM_MV, not PACK_ABSENT_MV: resuming into a 10 V rail would fire the
    # coil into a browning-out supply. Reusing the existing "healthy pack"
    # definition also means this threshold tracks the trip floor automatically if
    # PACK_VOLTAGE_TRIP_MV is ever moved. A latched failsafe can never be walked
    # around from here.
    if pack_absent or pack_voltage_lockout or last_pack_mV < PACK_REARM_MV:
        rail_resume_ok_streak = 0
        return
    rail_resume_ok_streak += 1
    if rail_resume_ok_streak < RAIL_RESUME_CONSECUTIVE:
        return
    down_ms = ticks_diff(now, rail_absent_entered_ms)
    if down_ms > rail_absent_ms_max:
        rail_absent_ms_max = down_ms
    print('PACK: rail back at {0:d} mV for {1:d} s — resuming Mode 2, profile '
          '{2:d}'.format(last_pack_mV, down_ms // 1000, active_profile_index))
    rail_absent_announced = False
    state = 'mode2_running'


def pack_voltage_boot_check():
    """Run before 'Ready' / before any command can be accepted, so a rig
    powered on already at or below the floor never fires a single pulse."""
    global last_pack_mV, last_sensor_sample_ms, last_sensor_report_ms
    sleep_ms(PACK_SENSE_SETTLE_MS)   # v4.30: divider RC + pad pull-down release
    for i in range(PACK_VOLTAGE_TRIP_CONSECUTIVE):
        if i:
            sleep_ms(PACK_VOLTAGE_BOOT_SAMPLE_MS)
        last_pack_mV = read_pack_voltage_mv()
        _pack_voltage_trip_check(last_pack_mV)
    last_sensor_sample_ms = ticks_ms()
    last_sensor_report_ms = ticks_ms()


def service_sensors():
    """Shared per-tick helper, called from both the main loop and
    acquire_mode2's own loop (see each call site) so the sample/report
    cadence below holds in both modes despite acquire_mode2 owning its own
    internal loop for the whole duration of a Mode 2 sweep. Uses the same
    ticks_ms/ticks_diff idiom as MIN_EMIT_MS/COMMAND_POLL_MS.

    (v4.33) This is also the ONLY place 1-Wire is allowed to be touched, and that is
    load-bearing rather than tidiness. Its Mode 2 call site is the i==0 service point,
    which already absorbs the blocking emit print() and where a delay becomes extra
    settling for cell 0 instead of a corrupted read. Calling any _ds_* helper from
    anywhere else — above all from near read_raw_bytes_hold() — puts a ~7.6 ms
    bit-banged blackout somewhere the sweep cannot afford it."""
    global last_pack_mV, last_sensor_sample_ms, last_sensor_report_ms
    now = ticks_ms()
    if ticks_diff(now, last_sensor_sample_ms) >= SENSOR_SAMPLE_MS:
        last_pack_mV = read_pack_voltage_mv()
        _pack_voltage_trip_check(last_pack_mV)
        last_sensor_sample_ms = now
    # v4.33: board temperature is 1-Wire, not ADC, so it runs on its own much slower
    # cadence and its own state machine. Placed AFTER the pack block deliberately — a
    # pack trip must never wait behind a ~7.6 ms bit-banged scratchpad read.
    service_ds18b20(now)
    if ticks_diff(now, last_sensor_report_ms) >= SENSOR_REPORT_MS:
        elapsed_ms = ticks_diff(now, base_time_ms)
        print('P{0:d},{1:d},{2:d}'.format(elapsed_ms, last_pack_mV, last_board_temp_dC))
        last_sensor_report_ms = now


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
    global busy_high_count, overrun_count, emit_block_count, emit_block_ms_max
    global gate_reject_count, gate_reprime_count
    global busy_timeout_count, busy_spin_min_left, rail_absent_ms_max   # v4.37

    try:
        if not serial_poll.poll(timeout_ms):
            return
        line = stdin.readline()
        if not line:
            return
        cmd = line[0]

        if cmd in ('S', 's'):
            if pack_voltage_lockout:
                print('Command Input ERROR: S rejected — pack-voltage lockout latched '
                      '(last {0:d} mV <= floor {1:d} mV); power-cycle to clear'.format(
                          last_pack_mV, PACK_VOLTAGE_TRIP_MV))
                return
            if state == 'mode2_running':
                print('Command Input ERROR: S rejected while Mode 2 running (send E first)')
                return
            if pack_absent:
                # v4.37: Mode 1 waits on DRL from the ADC (acquire_filtered_data),
                # and with the rail off that flag never arrives, so
                # measurement_cycle() never returns and the main loop stops
                # servicing sensors and commands — the same telemetry blackout the
                # Mode 2 spin used to cause, by a different route. Bounding that
                # wait is deferred (chunk 3); refusing the command makes the bug
                # unreachable in the case that actually gets hit.
                print('Command Input ERROR: S rejected — pack rail absent '
                      '(last {0:d} mV); Mode 1 waits on DRL from an unpowered ADC '
                      'and would stall telemetry'.format(last_pack_mV))
                return
            state = 'mode1_running'
            update_pulse_configuration()

        elif cmd in ('E', 'e'):
            state = 'stop'

        elif cmd in ('G', 'g'):
            if pack_voltage_lockout:
                print('Command Input ERROR: G rejected — pack-voltage lockout latched '
                      '(last {0:d} mV <= floor {1:d} mV); power-cycle to clear'.format(
                          last_pack_mV, PACK_VOLTAGE_TRIP_MV))
                return
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
            if pack_voltage_lockout:
                print('Command Input ERROR: D rejected — pack-voltage lockout latched '
                      '(last {0:d} mV <= floor {1:d} mV); power-cycle to clear'.format(
                          last_pack_mV, PACK_VOLTAGE_TRIP_MV))
                return
            if state == 'mode2_running':
                print('Command Input ERROR: D rejected while Mode 2 running (send E first)')
                return
            try:
                body = line[1:].strip()
                avg_part, *band_parts = body.split(';')
                averages = int(avg_part)
                # v4.35: bound it. averages=0 builds zero-length rings and kills
                # acquire_mode2 on `% avg_depth` (ZeroDivisionError, caught by the
                # v4.14 try/except and reported as an opaque Mode 2 failure); large
                # values are the v4.14 memory crash, where 128 was fine and 256 was
                # not. Refuse both here, where the operator can see why.
                if not 1 <= averages <= 128:
                    print('Command Input ERROR: D rejected, averages must be '
                          '1..128 (got {0:d})'.format(averages))
                    return
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
            if pack_absent:
                # v4.37: read_raw_sample() has the same unbounded IRQ-off BUSY spin
                # read_raw_bytes_hold() had. Bounding it needs a different abort
                # contract (it returns an int, so None would poison
                # acquire_raw_average's arithmetic) and is deferred to chunk 2;
                # refusing the command keeps it out of reach meanwhile.
                print('Command Input ERROR: A rejected — pack rail absent '
                      '(last {0:d} mV); the raw read waits on BUSY from an '
                      'unpowered ADC'.format(last_pack_mV))
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
            print('V{0},{1},{2},{3},{4:d},{5:d},{6:d},{7:d},{8:d},{9:d},{10:d}'.format(
                FW_VERSION, board_id_hex, NUM_PROFILES, active_profile_index,
                sample_frequency_hz,
                round(pulse_width_us * 1000), round(sample_delay_us * 1000),
                down_sample,
                last_pack_mV, last_board_temp_dC, int(pack_voltage_lockout)))

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
            # v4.27 appends the two host-stall counters. Additive extension of a
            # diagnostic response: nothing in src/ parses 'B' (it is read by a
            # human over the §16 serial terminal), so the two new trailing fields
            # break no consumer. Reset-on-read, matching the two before them.
            # v4.35 appends the two outlier-gate counters on the same terms.
            # v4.37 appends the three rail-loss counters, again on the same terms.
            print('B{0:d},{1:d},{2:d},{3:d},{4:d},{5:d},{6:d},{7:d},{8:d}'.format(
                busy_high_count, overrun_count, emit_block_count, emit_block_ms_max,
                gate_reject_count, gate_reprime_count,
                busy_timeout_count, busy_spin_min_left, rail_absent_ms_max))
            busy_high_count = 0
            overrun_count = 0
            emit_block_count = 0
            emit_block_ms_max = 0
            gate_reject_count = 0
            gate_reprime_count = 0
            busy_timeout_count = 0
            busy_spin_min_left = BUSY_SPIN_LIMIT   # v4.37: NOT 0 — it is a minimum
            rail_absent_ms_max = 0

        else:
            print('Command Input ERROR: unknown command')

    except Exception as e:
        print('Command Input EXCEPTION:', e)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
pack_voltage_boot_check()  # v4.28: latch before 'Ready' if already at/below the floor
ds18b20_init()             # v4.33: after the pack check — the failsafe leads the boot order
print('Ready')

serial_poll = select.poll()
serial_poll.register(stdin, select.POLLIN)

try:
    while True:
        check_for_commands()
        service_sensors()
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
                #
                # v4.37: RESTORE INTERRUPTS FIRST, REPORT SECOND. acquire_mode2
                # runs an IRQ-off critical section per cell (read_raw_bytes_hold
                # through to the freq/CC writes). An exception raised inside it
                # unwinds to here with IRQs still masked — and print() needs USB
                # CDC IRQs to reach the wire, so the board would brick itself
                # silent while reporting its own error. Idempotent: enable_irq()
                # restores a saved state, so calling it on a path that already
                # re-enabled is a no-op. The None guard matters — _held_irq is
                # None before the first hold and enable_irq(None) raises.
                if _held_irq is not None:
                    enable_irq(_held_irq)
                print('Mode 2 ERROR:', e)
                state = 'stop'
        elif state == 'rail_absent':
            service_rail_absent()
        elif state == 'stop':
            set_safe_state()
            # v4.37: an 'E' during an outage lands here, so clear the rail-absent
            # entry latch or the next abort would skip its announcement.
            rail_absent_announced = False
            state = 'ready'
except KeyboardInterrupt:
    print('\nTerminating')
    drive_coil_pwm.duty_u16(0)
finally:
    set_safe_state()
    print()
