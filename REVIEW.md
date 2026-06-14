# REVIEW.md — PIMD design review

Scope of this review: schematic `PIMD601.kicad_sch` (rev 6.01), firmware
`pimd_mcu_302.py` (v3.02), PC GUI `pimd302.py` (v3.02), and the 34-page diary.
Severity key: **[blocking]** breaks correct operation · **[bites-later]** latent /
edge-case · **[cosmetic]** hygiene.

This review is grounded in the **measured** operating point (see `README.md` §10).
Several concerns a schematic-only reviewer would raise (gate-driver slew, ADC fit) are
**already answered** by the builder's scope data and are recorded as resolved in §4.

---

## 1. Firmware — `pimd_mcu_302.py`

### 1.1 [bites-later] `print()` inside the DRL interrupt handler
`filtered_data_callback()` calls `print('.', end='')` (line 152) and `print()`
(line 154) inside an ISR, and also performs a 4-byte SPI transfer
`adc_filtered_spi.read(4)` (line 144) in the same handler. In MicroPython, allocating
inside an ISR can raise `MemoryError: memory allocation in interrupt` or behave
non-deterministically under load. SPI reads in an ISR are heavy and lengthen interrupt
latency, which matters on a timing-critical instrument.
**Fix:** in the ISR, capture only what's needed and set a flag (or use
`micropython.schedule()`); do the SPI read and any printing in the main loop. Remove
the progress-dot prints from the ISR entirely.

### 1.2 [bites-later] No bound on PWM duty — silent timing corruption at the edges
`drive_duty` (line 122) and `sample_duty` (line 123) are computed from user-supplied
`pulse_width_us`, `sample_delay_us`, and `sample_frequency_hz` and written straight to
`duty_u16()` (lines 129–130) with no range check. At high pulse rate with a wide pulse
(e.g. a wide pulse approaching the period at tens of kHz), the 16-bit duty can exceed
65535 and wrap, producing wrong/garbage timing rather than an error. The normal
operating envelope (5 kHz, 40 µs) is safe, but the GUI lets frequency and pulse move
independently, so a slider combination can reach the wrap region.
**Fix:** validate that `0 < drive_duty < 65536` and `drive_duty < sample_duty < 65536`
before applying; reject or clamp out-of-range commands and report back over serial.

### 1.3 [cosmetic] Raw-ADC path is initialised but unused
`adc_raw_spi`, `raw_samples`, `raw_median`, `raw_in_progress`, `current_raw_value` are
### 1.3 [bites-later] Raw-ADC path is dead code — and it is the strategic path
`adc_raw_spi`, `raw_samples`, `raw_median`, `raw_in_progress`, `current_raw_value` are
set up but never read in `measurement_cycle()`. This is not merely cosmetic: the **raw
no-latency output (SDOB, 14-bit) is the chosen acquisition path** for decay-curve /
multi-delay capture and moving-platform tracking (see README §13 and CLAUDE.md). The
32-bit filtered path used here has ≈ 0.5 s settling and ≈ 2.4 Hz bandwidth at 5 kHz —
fine as a held baseline, unusable for sweeping the sample point. So the dead raw path is
exactly the capability to **bring to life**, with firmware boxcar-averaging (noise ∝
1/√M; M≈16 recovers the filtered path's real-world ~450 µV floor in ~3.2 ms vs ~460 ms).
**Action:** implement raw-path read + averaging; keep the filtered path for a single
held sweet-spot baseline. Don't just delete the init.

### 1.4 [cosmetic] Magic calibration constant
`SAMPLE_PULSE_CORRECTION = 0.752` (line 66) carries a comment that says "0.5us faster".
The number and the comment disagree and the origin isn't recorded.
**Fix:** document how 0.752 µs was derived (measured edge-to-edge offset on which
hardware rev) so it can be re-derived if the gate driver or buffer changes.

### 1.5 [cosmetic] Decimation SEL1 unwired
`ltc2508_sel0.value(down_sample == 1024)` (line 133) drives only SEL0, so only 256/1024
are reachable. The LTC2508 supports 256/1024/4096/16384 via SEL0+SEL1. The raw path is
unaffected; wire SEL1 only if the 4096/16384 filtered options are ever wanted.

### 1.6 [cosmetic] Blocking acquisition + per-cycle pure-Python σ
`acquire_filtered_data()` busy-waits with `sleep_ms(1)` (line 169) and
`measurement_cycle()` recomputes a 100-sample standard deviation in pure Python every
cycle. Harmless at 20 samples/s, but it caps throughput and would bite if the sample
rate is raised. Note for future scaling, not urgent.

---

## 2. PC GUI — `pimd302.py`

No structural defects found. It is a PyQt6 telemetry scope: `QSerialPort` link,
QtCharts plot of voltage + computed σ + slope, file logging, full keyboard control.
Defaults `pulse_width = 10 µs`, `sample_delay = 7.4 µs`. `pimd111_ui.py` (generated UI)
was **not** reviewed — provide it to complete the picture. Detection logic proper is
not in this version.

---

## 3. Hardware (text-readable BOM/value items only)

Confirmed value-vs-symbol/footprint mismatches — each a BOM/assembly trap:

| Ref | Value (BOM) | Symbol/footprint | Note |
|-----|-------------|------------------|------|
| **Q1** | IRF610 | IRF6613 | **TO-220 vs DirectFET — incompatible packages.** Resolve before fab/assembly; this is the coil switch. |
| U3 | LT6203 | LT6234 | both dual hi-speed op-amps; pick one, align BOM |
| U7 | LT1763-2.5 | LT1762-2.5 | different part; reconcile |
| U6 | LTC2508-32 | LTC2508CDKD-32 | consistent — OK |

Other notes:
- **C19 470 µF / 16 V** sits on the 15 V coil-drive rail (≈ 1 V headroom) and sees the
  high-current pulse transients. Recommend ≥ 25 V. **[bites-later]**
- **RX clamp zener (D2 1N4733):** the builder's own schematic note questions it
  (*"better response from zener?"*). Zener junction capacitance likely slows RX
  recovery; the 1N5817 Schottkys are the faster clamp. Worth a bench A/B with a
  low-capacitance diode clamp. **[bites-later]**
- **Flyback vs FET rating:** measured TX flyback ≈ 251 V against a 200 V IRF610,
  managed by the < 10 A / < 300 µs / < 2 % duty limits and resistive damping. Functional
  today; tight margin, worth keeping in mind if duty/pulse-width is pushed. **[note]**

---

## 4. Resolved by measured data (recorded so they aren't re-raised)

- **Gate-driver speed.** A schematic-only read suggests a TL074-based gate driver might
  be slew-limited. Measured turn-off + damping to ~3 V by 8.4 µs proves it's adequate
  for the present design. Not an issue.
- **ADC fit.** The LTC2508-32 is correctly chosen as a dual-output device. **Decided
  architecture (README §13):** use the raw 14-bit no-latency path + firmware averaging
  for curve/multi-delay capture and tracking; reserve the 32-bit filtered path for a
  held sweet-spot baseline only. The filtered path's ≈ 0.5 s settling / ≈ 2.4 Hz BW at
  5 kHz makes it unusable for sweeping the sample point, and its sub-µV floor is wasted
  (front end dominates at ~450 µV). This is now the firmware target, not a critique.
- **Drift is quantified.** Baseline slope ≈ **−89 µV/s** at the 5 kHz / 40 µs operating
  point (air). Recorded as the target figure for any thermal-compensation work.
- **Timing method.** Same-slice paired PWM is the right approach and is a documented
  invariant — do not "modernise" it.

---

## 5. Cannot assess from text (needs more inputs)

- TX turn-off edge shape, flyback clamp behaviour, and exact decay vs sample timing →
  need **scope captures** and/or the **PCB layout** (grounding, return paths).
- The 7805-vs-USB ~50 % noise difference → need the supply layout / Gerbers and a scope
  capture of the noise event; this is the highest-value open investigation.
- Thermal drift mechanism → need the PCB (resistor placement / copper / airflow) and
  ideally a thermal capture.
- Full detection state-machine correctness → not in the provided firmware version.

---

## 6. Recommended next actions (priority)

1. Fix firmware items 1.1 and 1.2 (ISR safety + duty bounds) — small, safe, real.
2. Implement the raw-path acquisition (item 1.3): read SDOB, boxcar-average M samples,
   add a sample-delay sweep to capture decay curves. This is the enabler for both the
   ML direction and faster moving-platform tracking.
3. BOM reconciliation: Q1 package first, then U3/U7.
4. Bench A/B the RX zener; bump C19 to 25 V on the next board spin.
5. Provide PCB + scope captures to open the 7805-noise and thermal-drift
   investigations — that's where the remaining detector performance lives.
