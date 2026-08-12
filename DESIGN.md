# Pulse Induction Metal Detector (PIMD)

**Author:** Mark Makies (Australia) · **Licence:** CC BY-SA 4.0
**Hardware rev:** 6.04 + shielded enclosure (2026-07-13) + 6S Li-ion supply (2026-07-24) + pack-voltage sense & DS18B20 board temperature (2026-08-07) + **RX front-end +97 mV bias (2026-08-10)** + **U1 L7815CV replaced 2026-08-10 (failed; like-for-like on a larger heatsink)** + **38 mm forced-air fan on the U1/FET cluster — mandatory, fitted 2026-08-11, used in all cases** · **Firmware:** v4.35 · **PC tools:** gui v4.17 · classviz v1.73 · delaycal v1.48 · rawlog v1.16 · features v14 · shape v1 · target_check v4 · corpus_check v1.9 · **Coil:** v4 · **Operating profile:** `cal_2x11_v5` (2026-08-11, 2 × 11 = 22 cells, **not locked, no corpus**). Bump this line on every edit.
**Last bench update:** 2026-08-11 (bias mod fitted and characterised; fw v4.35 bench-verified; `cal_2x11_v5` hand-tuned)
**Doc rev:** 2.0.1 (2026-08-12) Manual cleanup, corrected after audit

> This file is self-contained: a new reader — human or AI agent — should be able to pick up the
> project cold from here alone. Empirically measured values are marked *(measured)*; everything
> else is nominal or design intent. **Detail, rationale and history live in `CHANGELOG.md`** —
> if you want to know *why* something is the way it is, search there, not here.

---

## 1. What this is, and current status

A pulse-induction (PI) metal detector designed and built from scratch since November 2023 by a
maker with no prior analogue-electronics background. It is not a clone; several choices are
deliberately unconventional.

The detector is one payload of a larger system: it is towed on a trailer behind **Roverling**, an
autonomous RTK-GPS ground robot, so detection events can be tagged with centimetre-level position
and streamed over LoRa. It therefore has to be quiet, stable and remotely controllable, not merely
sensitive.

**Status — working and field tested.** It discriminates ferrous from
non-ferrous targets in real soil, reliably to ~20 cm before the noise floor dominates.
**Mode 1 (filtered)** is mature and was used for all baselines and field tests. **Mode 2 (raw
profile sweep)** — the decay-curve — is operational and is where all current work
sits. 


---

## 2. Operating principle

A short, high-current pulse is driven through the TX coil, building a magnetic field. The drive FET
is switched off hard; the collapsing field induces a large flyback then a decaying eddy-current
response. A nearby metal target sustains its own eddy currents, perturbing the decay. Sampling the
RX-coil voltage at a precise short delay after turn-off and comparing to a baseline reveals the
target's presence and type. **Turn-off speed and sample-timing precision set the floor on what can
be detected.**

**Target polarity (measured convention):** ferrous → **positive** spike (stored magnetic energy
reinforces the decay field); non-ferrous → **negative** spike (opposing eddy currents weaken it).

**1 — Early: polarity.** Before the front end's negative lobe, sign splits the families. On the
100 µs band that window is **sd 7.97–12.30 µs**, widest at 9.57 µs — steel **+46.5 mV**, copper
**−74.4 mV** against air.  The crossing where a non-ferrous target stops reading negative and starts
reading positive **marches earlier with shorter pulse** — brass crosses at **~12.3 µs** on the 50 µs 
band and **~11.7 µs** on the 10 µs.

**2 — Through the null.** **Both families read positive against air**,
because air is the thing that dips and both targets fill the dip in. Sign is useless there; depth
is the measurement. 

**3 — Late: decay rate.** Out on the pedestal both families read positive and only decay rate
separates them (copper outlasts steel, crossing at ~44 µs on the coil and ~77 µs at 60 mm — the
crossover moves with coupling). A ferrous target adds a genuine **second, slow pole** of its own
that air and non-ferrous do not have.

---

## 3. Measured operating envelope (updated 2026-08-12)

- **Flyback** *(measured, 10 kHz / 40 µs)*: TX coil **−18 V to +265 V**, RX coil
  **−15 V to +135 V**. Gate turn-off **11.47 V → 0.44 V in 733 ns**.
- **FET Q1 limits:** < 10 A, < 300 µs, < 2 % duty. The detector runs above the duty limit and needs redesign.
- **RX front-end node** after R9: **−0.48 / +5.11 V**; ADC input settles
  **~5.0 V**; edge ring peaks **+5.30 / −0.69 V** (brief, current-limited, harmless).
- **Post-bias, air never goes below 67.2 mV** *(measured 2026-08-10, worst case = 100 µs band)*
  against the amplifier's 2.441 mV output floor, all three bands, now has ≥ 65 mV of headroom underneath it.
- **Sample-timing precision** ≈ **5 ns** *(measured)*.
- **Thermal drift** ≈ **−50 µV/s** at 10 kHz / 20 µs *(measured)*. 
- **Standard Operating Conditions (SoC):** Mode 1 · 10.0 kHz / 20.0 µs pulse / 10.0 µs delay /
  DS 256 · coil in air, no targets. Reference capture:
  `References/images/GUI-steady-state-256-1024.jpg`. Two caveats, both live: the **4 min warm-up**
  figure was established on the **20 V bench supply that no longer exists** and **warm-up is longer
  on the 6S pack** 
- **Board temperature moves the operating point, and it moves it *up* on cooling** *(measured
  2026-08-10/11)*.

---

## 4. System block diagram (text)

```
 6S Li-ion (19.8–25.2 V, working floor 21.0 V)
        │  F1 2A ─ D4 reverse-prot ─ FB1 ──► `+20V` rail (raw pack, after fuse + toroid — feeds
        │                                     the three linear regs below and GPIO26's divider)
        ├── U1 L7815CV ──► +15 V  (coil drive rail)
        ├── U2 L7812CV ──► +12 V  (analogue rail)
        ├── U9 L7805CV ──► +5 V   (digital) ──► RP2040 onboard LDO ──► +3V3
        └── U7 LT1762-2.5 ──► +2V5 (ADC)        U5 LTC6655-5 ──► +5V precision ref

 RP2040-Zero (U10)
   GPIO4  PWM2A ─ COIL-DRIVE ─► U4C/U4D gate driver ─► Q1 (IRF610) ─► TX coil
   GPIO5  PWM2B ─ SAMPLE/MCLK ───────────────────────────► LTC2508 conversion start
   (GPIO4 & GPIO5 share PWM slice 2 → phase-locked TX pulse & sample trigger)
   GPIO26 pack-voltage sense (22k/2.7k divider)   GPIO6 DS18B20 board temperature

 TX coil ──(flyback, resistive damping ~220R)
 RX coil ─► R1 damp (1.5k‖10k=1304Ω) ║ R9 4.7k series ─► clamp (D2 4.7V zener + D3 1N5819) ─► 47R
          ─► LT6203 preamp/ADC driver (U3, single +12V) ─► LTC2508-32 ADC (U6)
          ─SPI─► RP2040
                       SDOA/SCKA/DRL  = 32-bit filtered/decimated  (SPI1, Mode 1)
                       SDOB/SCKB/BUSY = no-latency raw 14-bit       (SPI0, Mode 2)

 RP2040 ─ serial (USB-CDC / UART) ─► PC tools (PyQt6)
```

---

## 5. Coils

Separate TX and RX windings (a two-winding "transformer", **not** a shared mono coil).

**Coil v4:** both coils slotted into 12 mm Perspex, RX shielded with copper tape, both embedded for
mechanical stability (earlier coils shifted under rover vibration and drifted). Faraday shield on
RX with **no closed loop**.

- **TX** 520 × 360 mm, 10 turns 0.5 mm (24 AWG) enamelled, **17.6 m**, 1.7 Ω
- **RX** 430 × 265 mm, 50 turns 0.25 mm (30 AWG) Teflon silver-plated wire-wrap, **≈ 69.5 m**,
  22.9 Ω
- Cable: RG62A/U coax (93 Ω, 47 pF/ft) + twin 26/0.3

**Damping is intentionally biased toward over-damping** — it kills ring faster and lets sampling
start earlier, trading a little amplitude for earlier access to the decay. Tuned empirically on a
scope, not by formula.

---

## 6. Transmit / drive chain

- **Q1:** IRF610 N-channel MOSFET, low-side switch, source to GND. Schematic limits < 10 A /
  < 300 µs / < 2 % duty; the 200 V rating is marginal against measured flyback and is managed by
  duty limits + damping (§14.2).
- **Gate driver:** U4C → U4D (TL074 sections) level-shift the 3.3 V `COIL-DRIVE` logic to a ~10 V
  gate swing. Design intent: fast, non-linear FET switching with parasitic-capacitance management.
- **Gate / damping network:** R12/R13 are now **0 Ω** (originally 4.7 Ω 5 W to slow the gate edge
  for SOA; this build performs better without them).
- **Turn-off** *(measured, 10 kHz / 40 µs)*: gate **11.47 V → 0.44 V in 733 ns**.

---

## 7. Receive / acquisition chain

### RX front end (schematic v6.04)

```
RX coil ─┬─ R1 ─ GND                   (shunt = damping; AS BUILT 1.5k ‖ 10k = 1304Ω,
         │                              schematic v6.04 still draws a single 1.3k — §14.4)
         └─ R9 4.7k ──┬─ D2 1N4732 (4.7V zener) ─┐  (positive clamp)
                      │  D3 1N5819 (Schottky) ───┘  (negative clamp)
                      └─ 47R ─┬─► U3A LT6203 +input, pin 3 (single +12V supply)
                              │
    U5 pin 7 (5V-REF) ─[240k 1% metal film]─┘   +97 mV bias — fitted 2026-08-10, NOT on the
                                                schematic (§14.4)
```

- **R1 (shunt) is the RX damping resistor**, which also cleans up TX via mutual coupling.
   **As built it is TWO resistors in parallel, and the schematic does not show this**:
  **1.5 kΩ ∥ 10 kΩ**  **1304 Ω effective**. Schematic v6.04 still draws a single `R1 1.3k`. 
  By that fit the network sits at **ζ = 1.06 — just into over-damping**, which is the intent.
- **R9 = 4.7k (series) is clamp current-limit only**, not damping.
- **D2 / D3** sit in series across the post-R9 node and conduct only outside ~0–5 V; between the
  rails the diodes are off and R1 does the damping.
- **47 Ω** between LT6203 output and ADC input limits over-range current into the ADC's protection.

### Preamp / ADC / references

- **U3 LT6203** dual high-speed op-amp, single +12 V.
- **U6 LTC2508-32**, 32-bit oversampling SAR with a configurable decimation filter **and** a
  no-latency raw output:
  - **SDOA (SPI1):** 32-bit filtered/decimated, `DRL` data-ready-low — the precision path.
  - **SDOB (SPI0):** no-latency raw 14-bit the acquisition path.
  - **Decimation** SEL0 (GPIO12): 256 (operating) or 1024.
  - **Conversion sync:** the falling edge of GPIO5 (`SAMPLE`/`MCLK`) starts each conversion, so
    every TX cycle yields one timed sample at exactly `sample_delay` after coil turn-off.
- **References:** U5 LTC6655-5 (precision 5 V), U7 LT1762-2.5 (low-noise 2.5 V for ADC).

### Acquisition architecture (decided)

Use the **raw no-latency path (SDOB)**, not the filtered one. At 5 kHz the filtered path has
≈ 0.46 s group delay, ≈ 0.5 s settling after any delay change and only ≈ 2.4 Hz bandwidth —
unusable for sweeping the sample point. Recover resolution by **boxcar-averaging M raw samples at a
held delay** (noise ∝ 1/√M; M = 16 ≈ 350 µV in ~3.2 ms, matching the filtered path's real-world
450 µV floor). The 32-bit precision is otherwise wasted: measured noise is ~500× the converter's
own 0.95 µV floor — **the front end dominates.**

**BUSY edge sync is required for accurate SDOB reads** : wait for BUSY-high (conversion
starts), then BUSY-low (complete), then read SDOB. Without it, reads landing mid-conversion produce
bit-truncated outliers at exactly **1/4 and 1/2** of the true value. Side effect: the BUSY-high
pulse at 10 kHz is ≈ 15 µs and MicroPython's polling loop catches ≈ 1-in-6, reducing effective raw
sample rate to ≈ 1.6 kHz. Accepted trade for accuracy.

**Clip-release** — the instant the conditioned signal leaves the clamp rail (~4.7 V) and enters the
linear 0–5 V window — is the true earliest-valid sample time. `pimd_delaycal.py` measures it
directly.

### The front-end transient — measured at the amplifier input

**Shape — from the 2026-08-08 fit, and the shape is what survives:**

- **Two real poles with opposite-sign residues**, `V = A·e^(−t/τf) − B·e^(−t/τs) + V_q`:
  **τ_fast = 1.125 µs, τ_slow = 2.270 µs** *(measured)*, fit RMS 0.87 mV over 894 points. Exactly
  **one zero crossing** — it is not ringing.
- **ζ = 1.06 — mildly over-damped**, not critically damped. 
- **The negative lobe is real, it is in air, and it is on every band.** It is **not** amplifier
  overload recovery: it is present *before* the LT6203, and it **responds to metal** — a steel
  spanner on the coil removes the zero crossing entirely (minimum +15.5 mV, difference up to
  +48.9 mV). 

### The +97 mV bias mod — built and characterised *(2026-08-10)*

**The problem it solves.** U3A is a unity-gain follower on a single +12 V rail and its output cannot
go below **2.441 mV**, so air's excursion below quiescent was clipped flat. 

**The fix is one resistor** 240 k 1 % metal film from U5 pin 7
(5V-REF) to U3A pin 3. Pin 3's DC path to ground is `R8 + R9 + RX coil` ≈ **4.77 kΩ** (the coil's
19.9 Ω shorts out R1, so R1 barely features), giving 5.0 × 4770/244770 = **97.4 mV**. Taken from
5V-REF rather than +5 V or +12 V so that offset and full scale drift together and the code does not
move. Signal-node loading is **1.9 %**.


### Target decay — model fits over the measured window *(2026-08-10, fitted in log space)*

**Air and brass need only a single repeated pole** — the free two-pole fit drives τ_fast → τ_slow,
and `(P + Q·t)·e^(−t/τ)` fits identically well. **Steel on the two long bands needs a genuine
second, slow pole, and that is the target's own eddy decay:**

| band | air | brass | steel |
|---|---|---|---|
| 100 µs | τ 1.96 µs · ±5.6 mV | τ 1.79 µs · ±8.5 mV | τf 1.24, **τs 19.0 µs** · ±6.0 mV |
| 50 µs | τ 1.89 µs · ±6.8 mV | τ 1.77 µs · ±8.4 mV | τf 1.18, **τs 23.4 µs** · ±8.7 mV |
| 10 µs | τ 1.78 µs · ±13.4 mV | τ 1.76 µs · ±13.2 mV | τ 1.67 µs · ±12.4 mV |

**The slow pole appears only with a ferrous target and vanishes on the 10 µs band** — a 10 µs pulse
barely excites it. Independently corroborated by the fill fractions, where steel filled only 62 % of
the null at 10 µs against 100 % on both long bands (§2). *Caveat on the fast pole: every capture
starts at ~9–12 µs, so a ~1.2 µs pole is far outside the data and **τ_fast is not independently
identifiable here** — treat it as a fitted shape parameter, not a measurement.*
`References/images/bias_mod_delay_plot_20260810.png` overlays these fits on the traces.

### RX L and C — pinned *(2026-08-08)*

**ζ is the one number here that does not depend on R at all.** For a parallel RLC the two fitted
poles alone fix it:

> **ζ = (τ_f + τ_s) / (2 √(τ_f · τ_s)) = 1.0622**

Taking the fitted poles with R1 = 1300 Ω gives **C = 579 pF**, **L = 4.41 mH**, √(L/C) = 2762 Ω and
**R_crit = ½√(L/C) = 1381 Ω**. 

**Substitution sensitivity** — what happens if R1 is *changed*, holding the fitted L and C. Damping
is a **shunt**, so **lower R means more damping**. (Unlike ζ above, this table inherits the R = 1300
assumption through L and C, so read it as a guide to picking a resistor, not as a measurement.)

| R1 | ζ | |
|---|---|---|
| 1239 Ω — as-built pair, −5 % corner | 1.11 | over-damped |
| **1304 Ω — as built, nominal (1.5k ∥ 10k)** | **1.06** | **over-damped, the intent** |
| 1370 Ω — as-built pair, +5 % corner | **1.01** | over-damped, but **effectively critical** |
| 1380 Ω | 1.00 | critical |
| 1400 Ω | 0.99 | under-damped — ring returns |

**These values rest on the 2026-08-08 scope fit alone** — 894 points, residual RMS 0.87 mV, taken
at the amplifier input on the current hardware. 

---

## 8. Digital / timing (RP2040)

- **MCU:** Waveshare RP2040-Zero (U10), MicroPython. Firmware `mcu/pimd_mcu.py` **v4.35**.
- **Pulse + sample generation:** two PWM channels on the **same slice** (GPIO4 = PWM2A drive,
  GPIO5 = PWM2B sample). Same slice ⇒ both rising edges align at period start; drive falls at
  `pulse_width`, sample falls at `pulse_width + sample_delay`. **This phase-locking is the core
  timing mechanism — never split these onto different slices**. Timing precision ≈ 5 ns
  *(measured)*.
- **Pulse width** 5–100 µs typical. **Sample delay** software-set, with an
  empirical `SAMPLE_PULSE_CORRECTION = 0.904 µs` offset between the PWM edge and the ADC trigger.
  Every delay the hardware can produce is a multiple of the **8 ns PWM grid**; an off-grid request
  is silently rounded. **8 ns is also the hard minimum spacing between two cells** — the `dd`/`sd`
  CC-write skip means two cells closer than that collapse silently into one.
- **Pulse rate** 2–50 kHz. A **prime-ish** rate halved noise by avoiding beat frequencies — the
  choice is deliberate. **Known-bad rate: 31.25 kHz** 
- **Board temperature: DS18B20 on GP6.** 1-Wire, SKIP ROM, CRC-checked, 30 s cadence,
  3V3 normal 3-wire mode.
- **SPI map:** SPI0 raw (SCKB GPIO2 / SDOB GPIO0 / BUSY GPIO15); SPI1 filtered (SCKA GPIO10 /
  SDOA GPIO8 / DRL GPIO9); SEL0 = GPIO12.

---

## 9. Serial protocol (both modes) — the firmware↔tooling contract

Two **mutually exclusive** acquisition modes over one serial link (115200 baud). Starting one
requires `E` first. *(Literal field separator is `", "` — comma-space — shown comma-only below;
parsers tolerate either. All timing fields are exact integers: freq in Hz, pulse and delay in ns —
**except the `D` command below, whose `pulse` and per-cell delays are in µs.**)*

**Mode 1 — filtered / interrupt-driven** (mature; all baselines & field tests):
- **in:** `S`/`s` start · `E`/`e` stop · `*<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>` configure
- **out:** `*<time_ms>,<value_uV>,<stddev_uV>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>`
- **rate:** pulse_freq / downsample (~20/s at 5 kHz / 256)

**Mode 2 — raw interleaved moving-average sweep** (the active path):
- **in:** `Q<n>` select profile · `G`/`g` start streaming · `E`/`e` stop ·
  `D<avg>;<freq_hz>,<pulse_us>,<d0>,…;…` define the RAM-only dynamic profile (index 5).
  **`avg` is bounded 1..128 since v4.35**; the whole `D` is refused on any invalid cell, and a
  refused `D` leaves the previous dynamic profile live — **wait for `D OK`** (§8).
- **out:** `W<profile_idx>,<time_ms>,<mean_ch0>,<mean_ch1>,...`
- **rate:** one W record per full sweep, rate-limited to one per `MIN_EMIT_MS = 10` ms (never
  reached in practice). Each cell gets one PWM period per sweep, with a rolling average `averages`
  deep held *across* sweeps — so emitted rate **is** sweep rate. `S` is rejected while Mode 2 runs.

**Both modes:**
- `V`/`v`/`?` identify →
  `V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>,<pack_mV>,<board_temp_dC>,<lockout>`
  — **11 fields since v4.28**; the trailing three are sensor/lockout state. `board_temp_dC` is
  deci-degrees C and **`-32768` means NO READING**, never a temperature. **Consumers must treat the
  reply as extensible.**
- `P<time_ms>,<pack_mV>,<board_temp_dC>` — **unsolicited** sensor telemetry, ~60 s cadence
  *(v4.28+)*. **Parsers must anchor on a digit after `P`**: `PACK:` and `LOCKOUT:` are
  human-readable firmware messages on the same wire, and matching `P` alone swallows them.
- `L` list profiles → one `L<idx>,<freq_hz>,<n_bands>,<n_cells>,<averages>,<name>` per profile
- `A<n>` raw boxcar average (idle / Mode 1 only) →
  `R<time_ms>,<mean_uV>,<std_uV>,<count>,<freq_hz>,<pulse_ns>,<delay_ns>,<min_uV>,<max_uV>`
- `B` diagnostic counters, **reset-on-read** — **6 fields since v4.35** →
  `B<busy_high_count>,<overrun_count>,<emit_block_count>,<emit_block_ms_max>,<gate_reject_count>,`
  `<gate_reprime_count>`. No parser exists in `src/` — read by a human over a serial terminal.
  **The ratio is the number to read:** rejections with near-zero re-primes means the outlier gate is
  catching glitches, which is its job; re-primes climbing with the signal means it is fighting real
  signal and `OUTLIER_GATE_FRAC` is too tight for the profile in use (§8).
- `E` is the universal stop. Modes are mutually exclusive.

**µV scaling (invariant):** filtered (Mode 1) `raw32 * 5_000_000 // 2**31`; raw (Mode 2 / `A`)
`raw14 * 10_000_000 / 2**14`.

---

## 10. Scan profiles

Profiles are fixed/compiled-in or RAM constants (no flash writes). **Geometry is constant per
profile**.
**Frames from different profile geometries must never be mixed in one dataset.** An identical cell
count does *not* imply comparability — comparability rests entirely on the
`(profile_name, profile_sha8)` guard in `pimd_features`, **which must not be relaxed**.

### Operating profile — `cal_2x11_v5` (2026-08-11)

#### cal_2x11_v5 — Cell / Zone / Delay Range / Anchor Table

Derived on paper, 2026-08-11. 2 bands × 11 cells (22 cells total). **Not swept or bench-verified.**
The sole profile in use — no other geometry is current.

**Runs at 3.125 kHz on the 100 µs band, and requires the cooling fan running.** Without the fan,
this band trips the +15 V regulator (U1) on a ~42 s cycle. The fan is a mandatory part of the
build (hardware-rev line) and runs in all cases — there is no fan-off operating mode.

| Cell | Zone | Delay range (μs, 100 μs band → 10 μs band) | Anchor type |
|---|---|---|---|
| 1 | Early | 10.792 → 8.040 | Amplitude-anchored — 2.4 V |
| 2 | Early | 11.904 → 9.120 | Amplitude-anchored — ~1.1 V (log-linear interpolated midpoint of cells 1 & 3) |
| 3 | Early | 13.032 → 10.208 | Amplitude-anchored — 0.5 V |
| 4 | Early | 13.912 → 11.064 | Amplitude-anchored — 250 mV |
| 5 | Early | 14.816 → 11.984 | Amplitude-anchored — 125 mV |
| 6 | Mid descent | 15.872 → 12.896 | Time-anchored, band-dependent — midpoint between cell 5 and null minimum |
| 7 | Peak min | 16.920 → 13.800 | Null minimum (band-dependent depth) |
| 8 | Rising | 21.160 → 16.160 | Rising out of null (band-dependent) |
| 9 | Late | 37.736 → 19.640 | Geometric ladder step 1 of 2 (ratio 1.7834 / 1.2152) — reaches ~110 mV air pedestal |
| 10 | Late | 67.296 → 23.864 | Geometric ladder step 2 of 2 — decay rate, not amplitude |
| 11 | Late | 120.000 → 29.000 | Band's longest delay (10 μs band at hardware limit, 95 ns margin) |

**Zone breakdown:** 5 early / 1 mid descent / 1 peak min / 1 rising / 3 late — 11 cells total per band.

**Cross-band matching:** holds for cells 1–5 only (amplitude anchors). Cells 6–8 are null-region, band-dependent by construction. Cells 9–11 are time-anchored.

**The null is sampled deliberately at its minimum** (cell 7) 

**`threshold_v` is a PLACEHOLDER ORDERING KEY, not a voltage.** 
**Do not mine that column**.

---

## 11. Invariants — do not break

- **Same-slice PWM phase-locking** (GPIO4/GPIO5, slice 2).
- **serial wire format**, both modes (§9).
- **No scan scheduler or PC-defined logic in firmware** beyond the fixed profile loop.
- **no flash writes** in normal operation (flash writes spike the noise floor ~10×).

---
## 12. Power system

| Rail | Source | Purpose |
|------|--------|---------|
| +15 V | U1 L7815CV | coil drive |
| +12 V | U2 L7812CV | analogue |
| +5 V | U9 L7805CV | digital |
| +3V3 | RP2040 onboard LDO | MCU/logic |
| +2V5 | U7 LT1762-2.5 | ADC |
| 5 V ref | U5 LTC6655-5 | precision reference |

Input: **6S Li-ion (19.8–25.2 V)** — 18650 cells (ICR18650-26C, recovered laptop cells). F1 2 A, D4
1N4004 reverse protection, FB1 ferrite bead. A **dedicated** battery powers the detector; the
rover's 40 V supply was too noisy.

**Why 6S.** At 5S (16.5–21 V) the pack falls below the L7815's dropout headroom over the back half
of its discharge, so coil drive — and therefore decay amplitude, and therefore the voltage each
amplitude-anchored delay lands on — sags with state of charge. 6S holds the +15 V rail in
regulation across the whole usable discharge.

---

## 13. What makes this design unusual (deliberate, validated choices)

- **Sampling high on the flyback decay rather than just the usual bottom ~700 mV.** The early-decay
  region carries the most discrimination information and sits well above the noise floor. This is
  the oldest unconventional choice in the project and it still holds.
- **The profile spans the whole decay with no gaps.** It runs from **2.4 V down to the
  ~70 mV pedestal** in 11 cells, and there is nothing it has to avoid.
- **Two anchoring schemes in one profile — amplitude early, time late.** Conventionally a PI profile
  picks one. Here the early cells are anchored to *voltages* on the decay, because that is where
  target **polarity** separates families; the late cells are anchored to *delays* out on the tail,
  because past the front end's lobe both families read positive and only **decay rate** separates
  them. Using one scheme for both halves would sample the wrong quantity in one of them.

---

## 14. Open problems

1. **Thermal drift.** Wider pulses heat the TX damping/gate
   resistors; the drive circuit drifts and the RX side drifts with it. **Fingerprint:** heavy bands
   drift low, light bands high, monotonic with pulse width; warm recalibration moves delays by tens
   of ns. **The sign test that separates it from a supply shift:** thermal moves light and heavy
   bands in opposite directions; a supply shift moves all bands the same way (§17.14).

2. **Q1 duty headroom.** Present operating points run well above the schematic's < 2 % FET duty
   note; Q1 (IRF610) is being pushed past its noted SOA. A higher-rated replacement is probably
   warranted.

3. **C18 under-rated.** 4700 µF **25 V** on a rail that reaches 25.2 V on a fresh pack. 35 V
   replacement identified, not fitted. **It sits on the `+20V` rail feeding the regulator that
   failed on 2026-08-10** (§12), so it is a candidate contributor to that failure rather than an
   independent tidy-up — untested either way, since no post-mortem was done.

4. **The schematic no longer matches the build in two places, both at the RX front end.**
   *(a)* **The 240 k bias resistor from 5V-REF to U3A pin 3 is not drawn at all.**  
   *(b)* **R1 is two resistors in parallel — 1.5 kΩ ∥ 10 kΩ, 1304 Ω effective** — the schematic
   still draws a single 1.3 kΩ.

---

## 15. Repository / file inventory

**One line per file: what it is, not what it has been.** Version history and design rationale live
in `CHANGELOG.md` and in each file's own header lineage.

| Path | Role |
|------|------|
| `mcu/pimd_mcu.py` | RP2040 MicroPython firmware (**v4.35**) — both modes, all profiles, the RAM-only dynamic profile (index 5), pack sense and board temperature. MicroPython **pure-Python only**. |
| `mcu/main.py` | One-line board launcher: `import pimd_mcu` |
| `src/pimd_gui.py` | **v4.17** — Mode 1 filtered-telemetry GUI. Pack SoC / board-temperature gauges; session logs to `data/sessions/gui_<ts>.csv`. |
| `src/pimd_classviz.py` | **v1.73** — Mode 2 signature visualiser and the **corpus-capture workbench**. Four tabs (Heatmap / Stats / Analysis / Family Plane). Loads and runs saved profiles as RAM-only dynamic profiles — **`Load & Run` waits for `D OK`** before selecting or streaming, so a refused profile can never be mis-labelled in the session header (§8). **Marks ADC-railed cells**: a standing `⚠ RAIL: N cells` label in the top bar, a red *Latest* cell with tooltip, and a session mark on each new entry — the value is deliberately **not** filtered or substituted, because a rail is a profile defect to fix at the delay ladder. Auto-logs a self-describing session dump whenever the stream runs; registry-backed structured capture writing `src/data/corpora/`; pack/temperature telemetry written to the dump automatically. Profile *authoring* is not here — it is in delaycal. |
| `src/pimd_delaycal.py` | **v1.48** — delay-calibration sweeper and the only profile author. Coarse+fine two-phase sweep per (freq, pulse) pair, threshold-crossing delays snapped to the 8 ns grid, thermal soak monitoring, auto-nudge, Compare Profiles tab, pack/temperature gauges and a conditions span recorded into every exported profile's notes.  |
| `src/pimd_rawlog.py` | **v1.16** — deliberately dumb raw logger: loads a profile, streams it, writes every firmware line **verbatim** to `data/sessions/rawlog_<ts>.txt`. No tables, no derived values, so it cannot develop display-layer defects.  |
| `src/pimd_shape.py` | **v1** — shared signature-geometry maths (pure NumPy, **no Qt**). `unit_shape` / `amp_l2` / `snr`, `band_means`, `band_range_mean`, `crossing_us`, `decay_persistence`, `family`. Geometry always passed explicitly; bands and thresholds resolved **by value**, never by stored index. `family` (sign) and `decay_persistence` (magnitude) are read together and neither overrules the other. |
| `src/pimd_features.py` | **v14** — session-CSV → training-corpus builder (offline CLI). Registry join, **hard geometry guard: one `(profile_name, profile_sha8)` per corpus build**. Parses the dump's `# pack_v:` / `# soak:` / `# stall:` / `# capture:` / `# mark:` comment tracks; `pack_v_at()` interpolates a voltage per capture. |
| `src/pimd_target_check.py` | **v4** — target-registry loader/validator (CLI + library). `DEFAULT_REGISTRY_PATH` here is the single source of truth for registry location. `-f` is required — there is no default path. |
| `src/pimd_corpus_check.py` | **v1.9** — corpus-level acceptance checker. Shape distance-invariance, split-half SNR, repeat consistency, falloff fit. One flat PASS/AMBER/FAIL/SKIP table, exit 1 on any FAIL, so it can gate a capture day. |
| `src/data/profiles/` | **v5** `cal_2x11_v5.json` is the operating profile — the only one in use. Runs at 3.125 kHz; **requires the cooling fan running** (§10, hardware-rev line). |
| `src/data/targets/targets_v3.csv` | Human-authored target registry, **current**, 27 objects — `pimd_target_check`'s `DEFAULT_REGISTRY_PATH` and what `pimd_classviz` / `pimd_features` use. Human-owned: tooling reads and validates only, never writes. `targets_v1.csv` is retained for reading the 2026-07-23 corpus. ⚠ `targets_v4.csv` is also tracked and is what **`pimd_rawlog` alone** reads (23 rows, different field set); despite the name it is **not** a successor to v3. |
| `src/data/corpora/` | Signature corpora (`gui_signatures_*.csv`).  |
| `src/data/sessions/` | Raw Mode 2 session dumps — self-describing CSV with embedded profile JSON, per-column map, marks and comment tracks; plus rawlog's verbatim `.txt`. Written automatically whenever the stream runs, ~220 KB/min. Untracked and **not reconstructable after the fact.** |
| `src/data/scratch/` | Scratch captures of **unregistered** objects. Never written into `corpora/` — a corpus build hard-errors on an unregistered `target_id` and that guard stays. |
| `References/images/` | Schematics, scope and GUI reference captures (§15 note below). |
| `References/scope/` | Raw scope CSVs, tracked again as of `20260810_bias_mod/` — nine traces (air / brass / steel RHS × three bands, all at 0 cm) plus `plot_bias.py` and `plot_delay.py`. This is the primary evidence behind §2's fill fractions and §7's post-bias measurements, and the one place they can be re-derived. |
| `USAGE.md` | Per-app usage guide — intent, operation and pipeline flow for the firmware and each PC tool. |
| `CHANGELOG.md` | Running change log — **the source this file is consolidated from**, and where all history and rationale lives. |
| `DESIGN.md` | **This file** — curated snapshot. Do not edit directly outside a consolidation pass (§18). |
| `CLAUDE.md` | AI-agent working brief — how to behave in this repo. Not project facts. |

**Key reference images** (all in `References/images/`): `schematic-v604.jpg` and
`schematic-v604-sheet2.jpg` (rev 6.04 — **does not show the bias resistor**, §14.4) ·
**`bias_mod_delay_plot_20260810.png`** (the current front end: three bands, air / brass / steel with
the §7 fits overlaid) · `6S-pack-discharge-curve.jpg` (§12) · `GUI-steady-state-256-1024.jpg` (the
SoC reference capture) · `warmup-with-8ns-steps.jpg` (why delays snap to the 8 ns grid).

**Pre-bias-mod images, kept as history only:** `lobe_at_amp_input_20260808.png`,
`spanner_fills_the_null_20260808.png` and `decay_model.png` show the front end before 2026-08-10 —
the shape is still the right picture of the mechanism, the **voltages are void** (§7).

---

## 16. Build, run & deploy

No build step for either the PC tools or the firmware. **Always work inside the venv.** Agent
conventions — version bumps, changelog discipline, the "don't edit DESIGN.md" rule — live in
`CLAUDE.md`.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
cd src

python pimd_gui.py        # Mode 1 GUI (filtered telemetry)
python pimd_classviz.py   # Mode 2 visualiser + corpus capture
python pimd_delaycal.py   # delay-calibration sweep / profile authoring
python pimd_rawlog.py     # raw verbatim session logger — ground truth for offline work

# Offline: registry validation (-f is required; there is no default)
python pimd_target_check.py -f data/targets/targets_v3.csv

# Offline: feature-maths acceptance check. NOTE: expectations are hard-coded from
# the 2026-07-23 63-cell analysis, so this FAILs against any other epoch.
python pimd_shape.py --selftest data/corpora/gui_signatures_targets_v1_20260723.csv

# Offline: corpus acceptance checks (exit 1 on any FAIL, so it can gate a capture day).
# NOTE: the v3-corpus FAILs were never diagnosed. Read the table, not the exit code.
python pimd_corpus_check.py data/corpora/<corpus>.csv
```

PC tools connect to `/dev/ttyACMx` @ 115200.

```bash
# Firmware: no build step — copy onto the board, then power-cycle it.
.venv/bin/mpremote connect /dev/ttyACM0 fs cp mcu/pimd_mcu.py :pimd_mcu.py + fs cp mcu/main.py :main.py
# (mpremote reset does not re-enumerate USB reliably — power-cycle.)
.venv/bin/mpremote connect /dev/ttyACM0 repl
```

### Bench-test over a serial terminal (115200)

```
V                     → version / identify (11 fields, §9)
L                     → list profiles
B                     → diagnostic counters (reset-on-read, 6 fields since v4.35, §9)
Q4  then  G           → Mode 2 streaming, static CLASSIFY_EP profile;  E to stop
*5000,40000,8400,256  then S → Mode 1 streaming (~20/s);  E to stop
A32                   → one raw boxcar average (R record), idle/Mode 1 only
```

---

## 17. Standing measured facts

> Everything here is a *conclusion*, with the epoch it belongs to. The experiments, the reasoning
> and the results that were superseded along the way are in `CHANGELOG.md` — search by date.
> **Any figure taken under a retired profile is epoch-bound** .

| # | Fact | Epoch |
|---|---|---|
| 17.2 | **The front end is two real poles with opposite-sign residues** — τ_fast 1.125 µs, τ_slow 2.270 µs, ζ 1.06 — giving exactly one zero crossing, and it is not ringing. **The shape stands; the 2026-08-08 voltages do not**. | shape current, voltages void |
| 17.3 | **The null responds to metal.** A steel spanner on the coil removes the zero crossing entirely. It is real coil physics, not an amplifier artefact — which is what made biasing it into view worth doing. | current |
| 17.5 | **The null is the best-SNR region on the ladder.** Steel:brass magnitude ratio through the null is 6–8× on every band against 5.8× at sd 30 µs — the same discrimination at **+187 mV instead of +78 mV**, against a noise floor that does not change with delay. | current |
| 17.6 | **A ferrous target adds a genuine slow pole of its own** — τ_s 19.0 µs (100 µs band), 23.4 µs (50 µs) — which air and non-ferrous do not have, and which vanishes on the 10 µs band because a 10 µs pulse barely excites it. | current |
| 17.7 | **The +97 mV bias mod met its design number**: predicted quiescent +111.7 mV, measured +112.8 mV, and air's worst case moved from clipped to **67.2 mV** above the 2.441 mV floor . | current |
| 17.11 | **Board temperature moves the operating point, upward on cooling** — the same cell was 46.7 % railed at 52.5 °C and 100 % railed at 31.5 °C. Which cells are usable is a function of (pack × temperature), not a static property of the ladder . | current |
| 17.14 | **Thermal and supply drift are separable by sign:** thermal moves light and heavy bands in opposite directions (r = +0.99 across bands); supply moves all bands the same way. | all |
| 17.16 | **31.25 kHz is a bad rep rate** — an entire band unusable at 31.25 kHz / 9 µs, restored by moving to 25 kHz with the pulse unchanged. Noise followed the rep rate, not the decay alignment. | all |
| 17.21 | **Family is an orientation coordinate, not a material one.** The early-band sign splits by *placement*: 90.9 % accurate transverse, 53.8 % axial. The **late**-band sign — iron-bearing vs non-ferrous — is the robust axis at **97.2 % ungated**. | prev-epoch |
| 17.22 | **The signature is rank 2 in orientation** and the Pasion–Oldenburg two-basis mixing law is confirmed on oblique captures, so orientation becomes a fitted parameter rather than a confound. | prev-epoch |
| 17.23 | **The data-quality noise zone sits at a fixed place on the decay while pack voltage scales the decay** — so which threshold columns it hits is a function of state of charge. Mechanism of *why that region is noisy* remains open. | prev-epoch |

---

## 18. Change Log Consolidation Pass

You are performing a "human-run consolidation pass".
For THIS task only, you are authorised to edit DESIGN.md (the read-only rule is suspended for this
pass).

CHANGELOG.md is the source of truth for everything that has changed since the last consolidation.
For this consolidation only focus on the lines in CHANGELOG.md **above** the marker:
`<!-- Add new entries above this line. Format: ### <file> — v<N> — <short title> -->`

IMPORTANT — the CHANGELOG is NOT in chronological order. Do not replay entries. First determine the
NET CURRENT STATE per file, then synthesise. DESIGN.md is a consolidated snapshot, not a
concatenation.

**DESIGN.md is a working brief, not an archive.** It carries specs, measured values, the protocol,
invariants, current profile and open problems. It does **not** carry narrative: how a result was
reached, what was tried and reverted, or per-version tool history. All of that lives in
CHANGELOG.md and must not be copied back in. When a fact and its story both exist, keep the fact and
cite the epoch. If a section is growing past a screen or two, it is drifting back toward an archive.

Before editing, produce these for my review:
  1. Current version of each file (firmware and each PC tool) as you read them from the CHANGELOG.
  2. An asset mapping table: each existing DESIGN.md asset path → its `References/` target. Flag any
     old reference with no clear match, and any file in `References/` not yet cited anywhere — do
     NOT guess a match.
  3. Which DESIGN.md sections you'll change, and the net change for each (expect at least the
     header/Doc-rev line).
  4. Anything you plan to drop or significantly reword, and any contradictions found.

Preserve policy text, the invariants (§11) and the protocol (§9) verbatim. Bump the Doc-rev line.
**Delete content that is superseded, contradicted, or duplicated from CHANGELOG.md** — but never
delete a measured value that is still valid without saying where it went.

After I approve and you've updated DESIGN.md:
  - Reset CHANGELOG.md by moving the marker to the top of the file.
  - Add a line under the moved marker: `## Archive — consolidated YYYY-MM-DD`