# Pulse Induction Metal Detector (PIMD)

**Author:** Mark Makies (Australia) · **Licence:** CC BY-SA 4.0
**Hardware rev:** 6.04 · **Firmware:** v4.02 · **PC tools:** v4.00 · **Coil:** v4
**Last bench update:** 2026-06-16 (RX front-end rework + Mode-2 first light)
**Doc rev:** 1.1 (2026-06-17) — fixed §17.1 table; added scan-grid sizing (§10) and a CC changelog / read-only policy (§16); flagged §3 noise & sample-timing as pre-rework (TBC). Bump this line on every edit.

> This file is self-contained: a new reader — human or AI agent — should be able to pick
> up the project cold from here alone. Empirically measured operating values are marked
> *(measured)*; everything else is a nominal/design figure. **§16 is the agent-facing
> brief** (intent, invariants, conventions). **§17 is the living test log.**

---

## 1. What this is, and current status

A pulse-induction (PI) metal detector designed and built from scratch since November 2023
by a maker with no prior analogue-electronics background. It is **not** a clone; several
choices are deliberately unconventional (§13).

The detector is one payload of a larger system: it is towed on a trailer behind
**Roverling**, an autonomous RTK-GPS ground robot, so detection events can be tagged with
centimetre-level position and streamed over LoRa. It therefore has to be quiet, stable and
remotely controllable, not merely sensitive.

**Status — working and field-tested, not a bring-up project.** It discriminates ferrous
from non-ferrous targets in real soil, reliably to ~20 cm before the noise floor
dominates. **Mode 1 (filtered)** is mature and was used for all baselines and field tests
here. **Mode 2 (raw profile sweep)** — the decay-curve / future-ML path — is newly working
and under active development; first confirmed metal-detection response 2026-06-16. The RX
front end was reworked June 2026 (§7). Remaining work is **refinement** (thermal drift,
supply noise) and finishing Mode 2 — not redesign.

> **Reviewer/agent note:** the goal of any review is refinement — lower noise, less drift,
> more robust firmware. Do **not** propose ground-up redesigns or "should have used X"
> rewrites unless a concrete defect justifies it. If your analysis implies the detector
> "can't work" the way it's built, you are missing context — the builder has scope captures
> proving otherwise. **Flag the concern; don't assert a contradiction.**

---

## 2. Operating principle

A short, high-current pulse is driven through the TX coil, building a magnetic field. The
drive FET is switched off hard; the collapsing field induces a large flyback then a
decaying eddy-current response. A nearby metal target sustains its own eddy currents,
perturbing the decay. Sampling the RX-coil voltage at a precise short delay after turn-off
and comparing to a baseline reveals the target's presence and (via polarity and
pulse-width response) its type. **Turn-off speed and sample-timing precision set the floor
on what can be detected.**

**Target polarity (measured convention):** ferrous targets → **positive** spike (stored
magnetic energy reinforces the decay field); non-ferrous → **negative** spike (opposing
eddy currents weaken it).

---

## 3. Measured operating envelope — treat as ground truth

- **Two operating points in use:** **5 kHz / 40 µs / 8.4 µs** (filtered Mode 1 — all
  baselines and field tests) and **10 kHz / 40 µs** (the front-end bench "bible", §7).
- **Flyback** *(measured, bible 2026-06-16, 10 kHz / 40 µs)*: TX coil **−18 V to +265 V**,
  RX coil **−15 V to +135 V**. Gate turn-off **11.47 V → 0.44 V in 733 ns**.

- **FET Q1 limits (schematic):** < 10 A, < 300 µs, < 2 % duty. *(The detector deliberately
  runs above the 2 % duty note — see §17 power table and §14.)*
- **RX front end** *(reworked June 2026)*: R1 1.3k damp · R9 4.7k clamp-limit · D2 1N4732
  (4.7 V zener) · D3 1N5819 (Schottky) · 47 Ω into ADC · LT6203 on single +12 V.
  Node after R9 **−0.48 / +5.11 V**; ADC input settles **~5.0 V**, edge ring peaks
  **+5.30 / −0.69 V** (brief, harmless, current-limited). Detail in §7.
- **Noise - TBC** *(measured)*: filtered path ≈ **±450 µV**; raw ≈ **±1400 µV**; warmed-up
  σ < 100 µV; precision ≈ 10 µV.
- **Sample-timing precision - TBC** ≈ **15–20 ns** *(measured)*. **Thermal drift** ≈ **−89 µV/s**
  at 5 kHz / 40 µs *(measured)* — the figure any thermal-compensation work must beat.

  *TBC: the noise and sample-timing figures above were measured on an earlier build and may
  correspond to the pre-rework front end (§7) — re-measure on the current build to confirm.*

---

## 4. System block diagram (text)

```
 5x LiPo (16.5–21 V)
        │  F1 2A ─ D4 reverse-prot ─ FB1
        ├── U1 L7815CV ──► +15 V  (coil drive rail)
        ├── U2 L7812CV ──► +12 V  (analogue rail)
        ├── U9 L7805CV ──► +5 V   (digital) ──► RP2040 onboard LDO ──► +3V3
        └── U7 LT1762-2.5 ──► +2V5 (ADC)        U5 LTC6655-5 ──► +5V precision ref

 RP2040-Zero (U10)
   GPIO4  PWM2A ─ COIL-DRIVE ─► U4C/U4D gate driver ─► Q1 (IRF610) ─► TX coil
   GPIO5  PWM2B ─ SAMPLE/MCLK ───────────────────────────► LTC2508 conversion start
   (GPIO4 & GPIO5 share PWM slice 2 → phase-locked TX pulse & sample trigger)

 TX coil ──(flyback, resistive damping ~220R)
 RX coil ─► R1 1.3k damp ║ R9 4.7k series ─► clamp (D2 4.7V zener + D3 1N5819) ─► 47R
          ─► LT6203 preamp/ADC driver (U3, single +12V) ─► LTC2508-32 ADC (U6)
          ─SPI─► RP2040
                       SDOA/SCKA/DRL  = 32-bit filtered/decimated  (SPI1, Mode 1)
                       SDOB/SCKB/BUSY = no-latency raw 14-bit       (SPI0, Mode 2)

 RP2040 ─ serial (USB-CDC / UART) ─► PC tools (PyQt6) and/or Roverling over LoRa
```
---

## 5. Coils

Separate TX and RX windings (a two-winding "transformer", **not** a shared mono coil). 

**Coil v4:** two coils slotted into 12 mm Perspex, RX shielded with copper tape,
both embedded for mechanical stability (earlier coils shifted under rover vibration;
epoxy/Perspex fixed the resulting drift). Faraday shield with **no closed loop**.

**Damping is intentionally biased toward over-damping** — it kills ring faster and lets
sampling start earlier, trading a little amplitude for earlier access to the decay. Values
are tuned empirically on a scope, not by formula. (Winding specs and historic damping
values: Appendix A / B.)

---

## 6. Transmit / drive chain

- **Q1:** IRF610 N-channel MOSFET, low-side switch, source to GND. Schematic limits
  < 10 A / < 300 µs / < 2 % duty; the 200 V rating is marginal against measured flyback and
  is managed by duty limits + damping. *(See §14 + §17: present operation pushes the duty
  limit.)*
- **Gate driver:** U4C → U4D (TL074 sections) level-shift the 3.3 V `COIL-DRIVE` logic up to
  a ~10 V gate swing. Design intent throughout: fast, non-linear FET switching with
  parasitic-capacitance management.
- **Gate / damping network:** R10 270 Ω, R11 220 Ω 5 W (damping). **R12/R13 are now 0 Ω**
  (originally 4.7 Ω 5 W, added on expert advice to slow the gate edge for SOA; this build
  performs better without them).
- **Turn-off** *(measured, 10 kHz / 40 µs)*: gate **11.47 V → 0.44 V in 733 ns** — clean,
  fast.
- **Flyback** *(measured)*: TX coil **−18 V to +265 V**.

---

## 7. Receive / acquisition chain

### RX front end — current verified design (June 2026, schematic v6.04)
Reworked after the detector came out of storage. Confirmed topology:

```
RX coil ─┬─ R1 1.3k ─ GND              (shunt = damping)
         └─ R9 4.7k ──┬─ D2 1N4732 (4.7V zener) ─┐  (positive clamp)
                      │  D3 1N5819 (Schottky) ───┘  (negative clamp)
                      └─ 47R ─► LT6203 +input (single +12V supply)
```

- **R1 = 1.3k (shunt) is the RX damping resistor.** A pot across the RX coil rings ~25 µs
  (+100/−50 V) at 25 k and **critically damps at ≈ 1.3–1.4k** *(measured)*, which also
  cleans up TX via mutual coupling.
- **R9 = 4.7k (series) is clamp current-limit only**, not damping — it holds clamp current
  to ≈ 9.6 mA at the +50 V damped peak, well inside the LT6203 rating.
- **D2 (4.7 V zener) / D3 (1N5819 Schottky)** sit in series across the post-R9 node and only
  conduct outside ~0–5 V; between the rails the diodes are off and R1 does the damping.
- **47 Ω** between the LT6203 output and the ADC input limits over-range current into the
  ADC's internal protection.

**Bible measurements** *(2026-06-16, 10 kHz / 40 µs — supersede all earlier RX voltages)*:

| Node | Range | Note |
|------|-------|------|
| Node after R9 (4.7k) | **−0.48 V to +5.11 V** | clamped by D2/D3, settled |
| ADC input | settles **~5.0 V**; transient edge ring **+5.30 / −0.69 V** | overshoot only |

The +5.30 / −0.69 V ADC-input overshoot is a brief (~300–400 ns) edge ring, not a settled
level; it grazes the LTC2508 abs-max (≈ −0.3 to +5.3 V) but is current-limited by the 47 Ω
into the ADC's protection diodes, so it is harmless. Front-end recovery (ring → flat) is
~300–700 ns, so early sampling is preserved.

**What the clamp protects:** the LT6203 runs on a single **+12 V** supply, so a +135 V
flyback never threatens the op-amp's survival. The clamp's real job is to keep the op-amp's
*output* under the **LTC2508 input abs-max (≈ 5.3 V)** and keep the amp out of saturation so
it recovers fast. The 4.7 V zener sets the clamp ceiling, not the sample timing.

### Preamp / ADC / references
- **U3 LT6203** dual high-speed op-amp, single +12 V 
- **U6 LTC2508-32**, 32-bit oversampling SAR with a configurable decimation filter **and** a
  no-latency raw output:
  - **SDOA (SPI1):** 32-bit filtered/decimated value, `DRL` = data-ready-low — the precision
    path *(noise ≈ ±450 µV)*.
  - **SDOB (SPI0):** no-latency raw value (firmware/diary call it 14-bit; schematic annotates
    "22-bit composite = 14-bit differential + 8-bit common-mode") — baseline + sample-timing
    search *(noise ≈ ±1400 µV)*.
  - **Decimation** SEL0 (GPIO12): 256 (operating) or 1024. SEL1 is not wired, so only those
    two ratios are reachable on the filtered path; the raw path is unaffected.
  - **Conversion sync:** the falling edge of GPIO5 (`SAMPLE`/`MCLK`) starts each conversion,
    so every TX cycle yields one timed sample at exactly `sample_delay` after coil turn-off.
- **References:** U5 LTC6655-5 (precision 5 V), U7 LT1762-2.5 (low-noise 2.5 V for ADC).

### Acquisition architecture (decided)
For decay-curve / multi-delay capture and any moving-platform tracking, use the **fast
no-latency raw output (SDOB, 14-bit)**, **not** the filtered path. At 5 kHz the filtered
path has ≈ 0.46 s group delay, ≈ 0.5 s settling after any delay change, and only ≈ 2.4 Hz
bandwidth — unusable for sweeping the sample point. Recover resolution by **boxcar-averaging
M raw samples at a held delay** (noise ∝ 1/√M; M=16 ≈ 350 µV in ~3.2 ms, matching the
filtered path's real-world 450 µV floor). Reserve the filtered 32-bit path (SDOA) for a
single held sweet-spot delay as the low-noise baseline, where ~0.5 s latency is fine. The
32-bit precision is otherwise wasted: measured noise (~450 µV) is ~500× the converter's own
0.95 µV floor — **the front end dominates.** The raw SPI path (SPI0/SDOB) is live in
`mcu/pimd_mcu.py` (Mode 2); metal-detection response via Mode 2 confirmed 2026-06-16.

**Clip-release** — the instant the conditioned signal leaves the clamp rail (~4.7 V) and
enters the linear 0–5 V window — is the true earliest-valid sample time. The
`src/pimd_delaycal.py` tool measures it directly (§15).

### Still to measure
- **Actual RX coil L and C** — the old 3.9 mH / 311 pF was *inferred* from a resonance and is
  now stale (the measured ~1.3k critical-damping value implies √(L/C) ≈ 2.6k). Re-measure the
  RX self-resonant frequency to pin L and C.

---

## 8. Digital / timing (RP2040)

- **MCU:** Waveshare RP2040-Zero (U10), MicroPython.
- **Pulse + sample generation:** two PWM channels on the **same slice** (GPIO4 = PWM2A drive,
  GPIO5 = PWM2B sample). Same slice ⇒ both rising edges align at period start; drive falls at
  `pulse_width`, sample falls at `pulse_width + sample_delay`. **This phase-locking is the
  core timing mechanism — never split these onto different slices.** *(timing precision
  ≈ 15–20 ns, measured.)*
- **Pulse width:** 5–50 µs. **Sample delay:** software-set, with an empirical
  `SAMPLE_PULSE_CORRECTION = 0.752 µs` offset between the PWM edge and the ADC trigger.
- **Pulse rate:** 5 kHz typical. A **prime-ish** rate (3719 Hz historically) halved noise by
  avoiding beat frequencies — the rate choice is deliberate, not arbitrary.
- **SPI map:** SPI0 raw (SCKB GPIO2 / SDOB GPIO0 / BUSY GPIO15); SPI1 filtered (SCKA GPIO10 /
  SDOA GPIO8 / DRL GPIO9); SEL0 = GPIO12.

---

## 9. Serial protocol (both modes) — the firmware↔tooling contract

Two **mutually exclusive** acquisition modes over one serial link (115200 baud). Starting
one requires `E` first. *(Literal field separator in records and the `*` config string is
`", "` — comma-space — shown below comma-only for readability; parsers tolerate either.)*

**Mode 1 — filtered / interrupt-driven** (mature; all baselines & field tests):
- **in:** `S`/`s` start · `E`/`e` stop · `*<freq_kHz>,<pulse_us>,<delay_us>,<downsample>` configure
- **out:** `*<time_ms>,<value_uV>,<stddev_uV>,<freq_kHz>,<pulse_us>,<delay_us>,<downsample>`
- **rate:** pulse_freq / downsample (~20/s at 5 kHz / 256)

**Mode 2 — raw interleaved moving-average sweep** (new; under active development):
- **in:** `Q<n>` select profile · `G`/`g` start streaming · `E`/`e` stop
- **out:** `W<profile_idx>,<time_ms>,<mean_ch0>,<mean_ch1>,...`
- **rate:** min(100 Hz, profile_freq / (n_pulses × n_delays)); `S` rejected while Mode 2 runs

**Both modes:**
- `V`/`v`/`?` identify → `V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_kHz>,<pulse_us>,<delay_us>,<downsample>`
- `L` list profiles → one `L<idx>,<freq_kHz>,<n_pulses>,<n_delays>,<averages>,<name>` line each
- `A<n>` raw boxcar average (idle / Mode 1 only) → one `R<time_ms>,<mean_uV>,<std_uV>,<count>,<freq_kHz>,<pulse_us>,<delay_us>` line
- `E` is the universal stop. Modes are mutually exclusive.

**µV scaling (invariant):** filtered (Mode 1) `raw32 * 5_000_000 // 2**31`; raw (Mode 2 / `A`)
`raw14 * 10_000_000 / 2**14`.

---

## 10. Scan profiles (compiled into firmware — `PROFILES` table in `mcu/pimd_mcu.py`)

| Idx | Name | Freq | pulses_us (n) | delays_us (n) | averages | Cells | Confirmed |
|-----|------|------|---------------|---------------|----------|-------|-----------|
| 0 | FAST_TRACK | 5 kHz | 40 (1) | 8.4 (1) | 8 | 1 | not bench-tested this session |
| 1 | CLASSIFY | 10 kHz | 8 / 20 / 40 (3) | 8 log-spaced 5–40 (8) | 32 | 24 | not bench-tested this session |
| 2 | SCOPE_CAL | 5 kHz | 10 (1) | 8 log-spaced 5–40 (8) | 1 | 8 | not bench-tested this session |
| 3 | TRACK_25K | 25 kHz | 10 (1) | 7.6 (1) | 16 | 1 | **verified 2026-06-16 (metal detection confirmed)** |

Profiles are fixed/compiled-in RAM constants (no flash writes). Geometry is constant per
profile, so any future ML classifier is trained per profile and the table is the
firmware↔ML contract.

### Scan-grid sizing (guidance — 10 kHz, slow movement)
A profile *is* a scan grid: **averages** raw samples per cell, across **n_delays** sample
delays, for **n_pulses** pulse widths. Sensible starting point:
- **averages ≈ 32** → ~250 µV (raw floor ≈ 1400 µV, noise = 1400/√averages), ~3.2 ms/cell.
- **n_delays ≈ 8**, log-spaced ~5–40 µs via `e^(0.3n)−1`.
- **n_pulses ≈ 3**: 8 / 20 / 40 µs (the ferrous/non-ferrous discriminant axis).
- Frame ≈ averages·n_delays·n_pulses·100 µs ≈ 77 ms (~13 frames/s); at 0.2 m/s a target
  dwells ~20 frames.

Constraints: at 10 kHz the 100 µs period must hold `pulse_width + max_delay + recovery`, so
delays ≤ ~40 µs and pulse widths ≤ ~40–50 µs; wide ferrous-favouring pulses (50–100 µs) need
a separate low-rate (~2.5–3 kHz) burst pass. **Thermal duty — not time — is the binding
constraint**: higher duty drives the −89 µV/s drift, so keep n_pulses small. Possible
refinements: adaptive averages (light on high-SNR cells, heavy near the floor), and two
cadences — one cheap cell per cycle for position tracking, the full n_delays×n_pulses matrix
every few hundred ms for classification.

---

## 11. Invariants — do not break

- **Same-slice PWM phase-locking** (GPIO4/GPIO5, slice 2).
- The **serial wire format**, both modes (§9).
- The **µV scaling** constants: `5_000_000 // 2**31` (Mode 1) and `raw14 * 10_000_000 / 2**14`
  (Mode 2).
- The deliberate **over-damping / early-sample** design philosophy.
- The **prime-ish pulse-rate** choice (noise mitigation, not arbitrary).
- **No scan scheduler or PC-defined logic in firmware** beyond the fixed profile loop; **no
  flash writes** in normal operation (flash writes spike the noise floor ~10×).

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

Input: 5× LiPo (16.5–21 V), F1 2 A, D4 1N4004 reverse protection, FB1 ferrite bead. A
**dedicated** battery powers the detector (the rover's 40 V supply was too noisy).

**Known supply-noise facts** *(measured, free-air, 10-sample σ):* ~200 µV USB / no flash ·
~250 µV battery / no flash · ~900 µV USB / using flash · ~4000 µV battery / using flash. USB
power is ~50 % quieter than the onboard 7805 path — **cause unknown, unsolved.** Writing to
flash raises the noise floor ~10× (mitigated by streaming over a single UART TX pin).

---

## 13. What makes this design unusual (deliberate, validated choices)

- Sampling the **0.5 V–5 V** band of the flyback decay rather than the usual bottom ~700 mV —
  found to carry more discrimination information and sit well above the noise floor.
- **Circular/rectangular RX under elliptical/larger TX** to cut mutual coupling and enable
  very early sampling.
- A **signed-standard-deviation edge detector** (σ × sign of start-to-end sample difference)
  in place of a high-pass filter — handles slow thermal/baseline drift while still flagging
  target edges and their direction.
- **Dual-output ADC strategy:** fast raw path for baseline/timing search, slow filtered path
  for the precision measurement.

---

## 14. Open problems (priority order)

1. **Thermal drift.** Wider pulses heat the TX damping/gate resistors; the drive circuit
   drifts and the sensitive RX side drifts with it — the main ceiling on using pulse-width as
   a discrimination axis. *Current measured baseline ≈ **−89 µV/s** at 5 kHz / 40 µs; target
   for any compensation work.*
2. **7805-vs-USB supply-noise mystery.** Onboard 7805 path ~50 % noisier than USB; unresolved.
3. **General supply noise floor** (battery vs USB, flash penalty — partially mitigated).
4. **Q1 duty headroom.** Present operating points run well above the schematic's < 2 % FET
   duty note (see §17) — Q1 (IRF610) is being pushed past its noted SOA; a higher-rated
   replacement FET is probably warranted.
5. **Coil mechanical stability** — largely solved (epoxy + Perspex).
6. **RX front-end damping/clamp** — resolved June 2026 (§7). Open sub-items: confirm
   clip-release didn't regress; re-measure RX coil L/C.

---

## 15. Repository / file inventory

| File | Role |
|------|------|
| `mcu/pimd_mcu.py` | RP2040 MicroPython firmware (**v4.02**) — both modes, all profiles |
| `mcu/main.py` | One-line board launcher: `import pimd_mcu` |
| `src/pimd_gui.py` | PC PyQt6 GUI **v4.00** — Mode 1 filtered telemetry display |
| `src/pimd_scope.py` | PC PyQt6 scope **v4.00** — Mode 2 raw streaming visualiser (metal detection confirmed 2026-06-16) |
| `src/pimd_delaycal.py` | PC PyQt6 delay-calibration sweeper (**v1.02**; header title line still reads v1.01 — reconcile). Steps `sample_delay` per freq/pulse pair via `*`+`A<n>` and records the delay at which the ADC reading crosses each target voltage — i.e. measures clip-release / earliest-valid-sample |
| `src/pimd302.py` | Legacy PC GUI v3.02 (superseded; kept for reference) |
| `src/pimd111.ui` | Qt Designer UI source for the legacy GUI |
| `src/requirements.txt` | Python deps for PC tools |
| `Electronics/PIMD604/PIMD604.kicad_sch` | Schematic, KiCad 8, rev 6.04 (multi-sheet) |
| `pics/Scematic_Baseline.jpg` | Schematic export, rev 6.04 (current front-end, R12/R13 = 0 Ω, field annotations) |
| `pics/Oscilloscope_Mode_1_Baseline.jpeg` | Scope baseline, Mode 1, 10 kHz / 40 µs — **yellow = TX drive, cyan = RX coil, pink = filtered/clipped ADC input, blue (rising) = sample point/MCLK** |
| `pics/App_Baseline.jpg` | App baseline, Mode 1 v4.00, 10 kHz / 20 µs / 10 µs / DS 1024 — positive spike = ferrous, negative spike = non-ferrous, noise < 500 µV |
| `pics/Screenshot_2026-06-16_13-34-49.jpg` | Scope: ADC-input edge ring (+5.30 / −0.69 V) settling to ~5.0 V (front-end recovery; §7) |
| `LTC2508-32.pdf` | ADC datasheet — source for the settling/bandwidth math |
| `docs/build_notes.md` | PC GUI dev-environment setup, UI regeneration, packaging/deploy notes |
| `PIMD___Mark_Makies.pdf` | 34-page work-in-progress diary (Nov 2023 – Feb 2025) |
| `CHANGELOG.md` | Running change log — agents write here; this README is consolidated from it (§16) |
| `README.md` | **This file** (the single working document) |

> **PC-tool / firmware version skew:** `pimd_gui.py` and `pimd_scope.py` self-identify as
> v4.00 while the firmware is v4.02. The serial protocol did **not** change across v4.01/v4.02
> (those were internal timing/priming fixes), so they interoperate; the labels are just stale.

> **Open gaps:** KiCad PCB layout + Gerbers; BOM; bench test of profiles 0–2 and `pimd_gui.py`
> against current firmware; scope captures of the 7805 supply-noise event.

---

## 16. For Claude / CC — working brief

Everything an AI agent needs to make safe edits. (The hard facts above — envelope §3,
invariants §11, wire format §9, profiles §10 — are the ground truth; this section is the
*how to behave* layer.)

### Mindset
- **It already works.** Refine; don't redesign. No "you should have used X" rewrites without a
  concrete defect. If your analysis says it "can't work," you're missing context — **flag,
  don't assert.** The builder has scope captures.
- When you **cannot** determine something from text (analogue behaviour, PCB layout, scope
  data), **say so explicitly** rather than guessing.
- Keep changes **minimal and reversible** — prefer a flagged main-loop fix over restructuring
  the ISR/acquisition model unless asked.

### Control model — MCU stays a simple primitive + fixed profiles
- The MCU must **not** grow a PC-driven scan engine. Multi-point scans run from **fixed,
  compiled-in profiles** (`PROFILES`, selected by `Q<n>`), built on one raw-acquisition
  primitive (interleaved one-period-per-cell loop with a rolling average of depth `averages`).
  `G` starts streaming; `E` stops. One command pair in → continuous `W` stream out. **No
  PC-defined logic, no scheduler.**
- **No flash writes** in the hot path (they spike the noise floor ~10×). Profiles are RAM
  constants.
- Manual `*`/`S`/`E` stay for debug; `Q`/`G`/`L`/`V`/`?` are additive. `W` records are a new
  record type; the legacy `*` line stays valid. The old `P<n>` one-shot (v3.x) was removed —
  use `Q<n>` + `G`.
- Keep a single read-line / write-line transport seam (USB-serial now → UART/LoRa later).
- Scan geometry is fixed per profile → ML classifiers are trained per profile.

### Coding conventions / environment
- **MicroPython** on RP2040 for `mcu/pimd_mcu.py`; pure-Python only, no CPython-only libs.
- PC tools are **PyQt6**: `pimd_gui.py` (Mode 1), `pimd_scope.py` (Mode 2), `pimd_delaycal.py`
  (delay cal). `pimd302.py` is the superseded v3.x GUI.
- **Bump the version number and add a header changelog line on every file edit — this is
  important.** (Detailed changelogs live in the source-file headers; this README keeps only a
  one-line summary.)

### This README is read-only for agents
- **Do not edit this file.** Record every change you make — firmware, PC tools, hardware, or
  new findings — in a separate **`CHANGELOG.md`** (component · what changed · why · date).
- This README is regenerated from `CHANGELOG.md` by a periodic human-run consolidation pass
  (using a more capable model). Treat it as a stable reference snapshot, not a scratchpad.
- The Test Log (§17) follows the same rule: append observations to `CHANGELOG.md`, and the
  consolidation pass folds them in here.

### Run / deploy (PC venv)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
cd src
python pimd_gui.py        # Mode 1 GUI (filtered telemetry)
python pimd_scope.py      # Mode 2 scope (raw streaming)
python pimd_delaycal.py   # delay-calibration sweep
```
PC tools connect to `/dev/ttyACM0` @ 115200 (hardcoded in `serial_open()`).

```bash
# Firmware: no build step — copy onto the board, then power-cycle it.
mpremote connect /dev/ttyACM0 fs cp mcu/pimd_mcu.py :pimd_mcu.py + fs cp mcu/main.py :main.py
# (mpremote reset does not re-enumerate USB reliably — power-cycle.)
mpremote connect /dev/ttyACM0 repl
```

### Bench-test over a serial terminal (115200)
```
V                     → version / identify
L                     → list profiles
Q3  then  G           → Mode 2 streaming (W records, ≤100 Hz);  E to stop
*5,40,8.4,256  then S → Mode 1 streaming (* records, ~20/s);    E to stop
A32                   → one raw boxcar average (R record), idle/Mode 1 only
```

---

## 17. Test log / observations (curated — see §16)

Per-entry: **date · fw/hw rev · one-line summary**, grouped by subject. Detailed changelogs
stay in source-file headers. When an observation **supersedes** an envelope value (§3), update
the envelope in place with a dated note and record the raw observation in `CHANGELOG.md`. **Agents: log new observations to `CHANGELOG.md`, not directly here** — §17 is refreshed at consolidation (§16).

### 17.1 Power / current vs pulse width
*Method: for each pulse width, raise PRF until the bench-supply draw reaches 0.5 A. Below
20 µs the supply current can't reach 0.5 A — a frequency/duty ceiling is hit first.
"current" = average bench-supply current (at 20 V), not peak coil current. The 40 µs / 10.6 kHz
/ 500 mA row matches the schematic annotation "10 kHz 40 µs pulses, 500 mA from bench supply
at 20 V."*

| Pulse (µs) | Freq Req (Hz) | Freq (actual) | Current (mA) | Note |
|---|---|---|---|---|
| 40 | 10601 | 10601.025 | 500 | raise freq until 0.5 A |
| 30 | 17599 | 17599.127 | 500 | as above |
| 20 | 29201 | 29201.343 | 410 | now frequency/duty-cycle constrained |
| 10 | 43003 | 43003.354 | 201 | as above |
| 5 | 56992 | 56933.047 | 105 | as above |

Note that freq taken to next achievable/actual (after conversion to PWM) prime

> **Flag (builder's note):** the duty at these points (pulse × freq ≈ 28–58 %) is far above the
> schematic's < 2 % FET-duty note and above the ~20 % of the 5 kHz / 40 µs operating point.
> Q1 (IRF610) is being pushed past its noted SOA — **a higher-rated replacement FET is probably
> warranted.** Recorded as raw notes; entry: *2026-06-16 · fw v4.02 · power sweep, bench supply 20 V.*

### 17.2 (next subject)
*Add new topical tables here — e.g. noise, thermal drift, clip-release vs pulse, target
signatures. Keep raw; push any envelope-superseding result up into §3 with a dated note.*

---

## Appendix A — Schematic-level reference

**Coil v4 (full specs):** 
TX 520 × 360 mm, 10 turns 0.5 mm (24 AWG) enamelled, 17.6 m, 1.7 Ω ·
RX 430 × 265 mm, 50 turns 0.25 mm (30 AWG) Teflon silver-plated wire-wrap, 30.8 m, 22.9 Ω.
Cable: RG62A/U coax (93 Ω, 47 pF/ft) + twin 26/0.3.

