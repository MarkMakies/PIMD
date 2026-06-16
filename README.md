# Pulse Induction Metal Detector (PIMD)

**Author:** Mark Makies (Australia) · **Licence:** CC BY-SA 4.0
**Hardware rev:** 6.04 · **Firmware:** v4.0x · **PC tools:** v4.00 · **Coil:** v4
**Last bench update:** 2026-06-16 (front-end rework + Mode-2 first light)

> This README is written to be self-contained: it should let a new reader — human or
> AI — pick up the project cold and understand the whole system without the rest of
> the conversation history. Where a fact is an empirically measured operating value
> rather than a nominal design figure, it is marked *(measured)*.

---

## 1. What this is and why it exists

A pulse induction (PI) metal detector designed and built from scratch, starting
November 2023, by a maker with no prior analogue-electronics background. It is not a
clone of an existing design; several choices are deliberately unconventional (see §9).

The detector is one payload of a larger system: it is intended to be towed on a
trailer behind **Roverling**, an autonomous RTK-GPS ground robot, so that detection
events can be tagged with centimetre-level position and logged/streamed over LoRa for
autonomous ground search. The detector therefore has to be quiet, stable, and remotely
controllable, not just sensitive.

**Current status:** working and field-tested. It discriminates ferrous from
non-ferrous targets in real soil, reliably to roughly 20 cm before the noise floor
dominates. **Mode 1 (filtered) is mature and was used for all baselines/field tests
here.** Mode 2 (raw profile sweep, the decay-curve/ML path) is newly working and under
active development — first confirmed metal-detection response 2026-06-16. The RX front
end was reworked in June 2026 (see §6). Remaining work is refinement (thermal drift,
supply noise) and finishing Mode 2, not bring-up.

---

## 2. Operating principle (PI in one paragraph)

A short, high-current pulse is driven through the transmit (TX) coil, building a
magnetic field. The drive FET is switched off hard; the collapsing field induces a
large flyback and then a decaying eddy-current response. A nearby metal target sustains
its own eddy currents, perturbing the decay curve. By sampling the receive (RX) coil
voltage at a precise, short delay after turn-off and comparing to a baseline, the
presence and (via polarity and pulse-width response) the type of target is inferred.
**Turn-off speed and sample-timing precision set the floor on what can be detected.**

**Target polarity (measured convention):** ferrous targets produce a **positive**
spike (stored magnetic energy reinforces the decay field); non-ferrous targets produce
a **negative** spike (opposing eddy currents weaken the field).

---

## 3. System block diagram (text)

```
 5x LiPo (16.5–21 V)
        │  F1 2A ─ D4 reverse-prot
        ├── U1 L7815CV ──► +15 V  (coil drive rail)
        ├── U2 L7812CV  ──► +12 V  (analogue rail)
        ├── U9 L7805CV ──► +5 V   (digital) ──► RP2040 onboard LDO ──► +3V3
        └── U7 LT1762-2.5 ──► +2V5 (ADC)         U5 LTC6655-5 ──► +5V precision ref

 RP2040-Zero (U10)
   GPIO4  PWM2A ─ COIL-DRIVE ─► U4C/U4D gate driver ─► Q1 (IRF610) ─► TX coil
   GPIO5  PWM2B ─ SAMPLE/MCLK ───────────────────────────────────► LTC2508 conv start
   (GPIO4 & GPIO5 share PWM slice 2 → phase-locked TX pulse & sample trigger)

 TX coil ──(flyback, resistive damping 220R)
 RX coil ─► R1 1.3k damp ║ R9 4.7k series ─► clamp (D2 4.7V zener + D3 1N5819) ─► 47R
          ─► LT6203 preamp/ADC driver (U3, single +12V) ─► LTC2508-32 ADC (U6)
          ─SPI─► RP2040
                                   SDOA/SCKA/DRL  = 32-bit filtered/decimated  (SPI1)
                                   SDOB/SCKB/BUSY = no-latency raw output       (SPI0)

 RP2040 ─ serial (USB-CDC / UART) ─► PC GUI (PyQt6) and/or Roverling over LoRa
 RP2040 ─ differential PWM ─► analogue panel meter (METER-POS / METER-NEG)
```

---

## 4. Coils

Separate TX and RX windings (a two-winding "transformer", **not** a shared mono coil).
The geometry has been through several revisions; the principle that unlocked early
sampling was **overlaying a circular/rectangular RX coil under an elliptical/larger TX
coil** to minimise mutual coupling, which dropped the usable minimum sample delay into
the single-digit microseconds (important for small/gold targets).

**Coil v3 (documented full specs):**
- TX: 520 × 360 mm, 10 turns 0.5 mm (24 AWG) enamelled magnet wire, 17.6 m, **1.7 Ω**
- RX: 430 × 265 mm, 50 turns 0.25 mm (30 AWG) Teflon-insulated silver-plated
  wire-wrap wire, 30.8 m, **22.9 Ω**

**Coil v4 (current):** two coils slotted into 12 mm Perspex, RX shielded with copper
tape, both embedded for mechanical stability (earlier coils shifted under vibration on
the rover; epoxy/Perspex fixed the drift this caused).

**Schematic annotations (per-winding model):**
- TX: 0.5 mm × 14 T elliptical, ~1.8 Ω, step response ~544 kHz, calc **275 µH / 266 pF**,
  critical-damping Rd ≈ 469 Ω (builder notes 220 Ω gives better early sampling — i.e.
  deliberately over-damped)
- RX: 0.25 mm × 50 T round 400 mm, ~19.9 Ω, step response ~184 kHz, calc **3.9 mH / 311 pF**,
  Rd ≈ 1822 Ω
- Cable: RG62A/U coax (93 Ω, 47 pF/ft) and twin 26/0.3 (1.84 mm²). Faraday shield with
  **no closed loop**.

**Damping:** tuned empirically with potentiometers on a scope, not purely by formula.
Historic values: TX 220 Ω (→ 490 Ω after shortening coil leads from ~2 m to ~0.5 m,
which cut parasitic capacitance and sped the coil up); RX 470 Ω. Over-damping is
intentional — it kills ring faster and lets sampling start earlier, trading a little
amplitude for earlier access to the decay.

---

## 5. Transmit / drive chain

- **Q1:** IRF610 N-channel MOSFET, low-side switch, source to GND. Operating limits
  noted on schematic: **< 10 A, < 300 µs, < 2 % duty**. The 200 V rating is marginal
  against measured flyback (see below) and is managed by the duty limits + damping.
- **Gate driver:** U4C → U4D (sections of a TL074), labelled "MOSFET GATE DRIVER",
  level-shifting the 3.3 V `COIL-DRIVE` logic up to a ~10 V gate swing
  (annotated stages [1.7] → [1.7–3.4] → [1.6–10.7] V). Earlier breadboard revisions
  used a discrete bipolar totem-pole; the design intent throughout is fast,
  non-linear FET switching with parasitic-capacitance management.
- **Gate / damping network:** R10 270 Ω, R11 220 Ω 5 W (damping). **R12/R13 (originally
  4.7 Ω 5 W) are now 0 Ω** — they were added on expert advice to slow the gate edge for
  SOA, but in this build the detector performs better without them (schematic v6.04
  annotation). Q1 note: drain/gate were reversed on an earlier PCB; corrected in the
  current revision.
- **Gate-drive turn-off (measured, bible 2026-06-16, 10 kHz / 40 µs):** gate falls
  **11.47 V → 0.44 V in 733 ns** — a clean, fast turn-off.
- **Flyback (measured, bible 2026-06-16):** TX coil **−18 V to +265 V**; RX coil
  **−15 V to +135 V**. No dedicated TVS; energy is absorbed by the resistive damping and
  the FET's avalanche capability within the stated duty limits. *(Supersedes the earlier
  251 V / 176 V figures, which were taken at the 5 kHz / 40 µs operating point.)*

---

## 6. Receive / acquisition chain

### RX front end — current verified design (2026-06, supersedes the rev-6.01 schematic; now captured in schematic v6.04)
The RX input network was reworked during a bench session after the detector was pulled
out of storage. Confirmed topology (schematic v6.04 / `pics/Scematic_Baseline.jpg`):

```
RX coil ─┬─ R1 1.3k ─ GND        (shunt = damping)
         └─ R9 4.7k ──┬─ D2 1N4732 (4.7V zener) ─┐  (positive clamp)
                      │  D3 1N5819 (Schottky) ───┘  (negative clamp)
                      └─ 47R ─► LT6203 +input (single +12V supply)
```

- **R1 = 1.3k (shunt to GND) is the RX damping resistor.** Bench-measured: a pot across
  the RX coil rings ~25 µs (+100 V/−50 V) at 25k and **critically damps at ≈ 1.3–1.4k**,
  which also cleans up TX via the mutual coupling. *(measured)*
- **R9 = 4.7k (series) is the clamp current-limit only** — it is NOT a damping element.
  At the measured damped peaks it limits clamp current to ≈ 9.6 mA (+50 V positive peak)
  and a few mA on the negative swing, both well inside the LT6203 input rating.
- **D2 = 1N4732 (4.7 V zener):** positive clamp. **D3 = 1N5819 (Schottky, 40 V):**
  negative clamp. They are in series across the post-R9 node and only conduct on
  excursions outside ~0–5 V; between the rails the diodes are off and R1 does the
  damping.
- **47 Ω** sits between the LT6203 output and the ADC input (limits current into the
  ADC's internal protection on any over-range).

**Bible measurements (2026-06-16, 10 kHz / 40 µs — these supersede all earlier RX-chain voltages):**
| Node | Range | Note |
|------|-------|------|
| Node after R9 (4.7k) | **−0.48 V to +5.11 V** | clamped by D2/D3, settled |
| ADC input | settles **~5.0 V**; transient edge ring peaks **+5.30 V / −0.69 V** | overshoot only |

The ADC-input overshoot to +5.30 V / −0.69 V is a brief (~300–400 ns) edge ring, not a
settled level — confirmed on scope (`pics/Screenshot_2026-06-16_13-34-49.jpg`): the trace
rings then settles cleanly to ~5.0 V and holds flat. The peaks graze the LTC2508 abs-max
(≈ −0.3 to +5.3 V) but are current-limited by the 47 Ω into the ADC's internal protection
diodes (rated 100 mA; actual « that), so it is harmless. Front-end recovery (ring → flat)
is ~300–700 ns, i.e. early sampling is preserved.

**What the clamp actually protects (important):** the **LT6203 runs on a single +12 V
supply**, so a +135 V flyback does not threaten the op-amp's survival. The clamp's real
job is to keep the op-amp's *output* under the **LTC2508 input abs-max (REF + 0.3 ≈
5.3 V)** downstream, and to keep the amp out of saturation so it recovers fast. This is
why the zener stays and why 4.7 V is the right value — it buys ADC headroom; it does NOT
slow acquisition (the zener voltage sets the clamp ceiling, not the sample timing, which
is set by damping + recovery).

**Key diagnostic insight from the rework:** the old RX used **R1 = 20 k**, which is
~11× the ~1.4k critical value — i.e. the RX was **chronically under-damped**, and the
large ring was simply being *clipped* by the diodes so it looked bounded on the ADC
node. When D3 (then a 1N5817) failed **open**, the negative-peak clipping vanished and
the under-damping became visible (free ring to −50 V). So the fix was to make a real
~1.3k resistor do the damping and let the diodes do protection-only — a clean separation
the original design lacked.

**Failure history:** the original D3 (1N5817, 20 V reverse rating) went **open** —
consistent with repetitive clamp over-stress and/or its low reverse rating. Replaced
with **1N5819** (same Schottky drop, 40 V reverse, ~25 A surge). The earlier removal of
a fast diode (old "D1") that clamped into the **5 V reference** was also retained — that
clamp injected switching transients onto V_REF, which directly degraded ADC dynamic
range; getting any clamp off the reference was the more important earlier fix.

**Earlier-caution retraction:** an earlier note worried the zener would slow RX recovery
via junction capacitance. With R9's series resistance ahead of it and the clamp now
doing protection-only (not sitting across the bare RX input), that concern is largely
masked; the zener is in a defensible spot. Confirm on the scope (see "to measure" below).

- **Preamp / ADC driver:** U3 LT6203 (dual high-speed op-amp, single +12 V supply;
  BOM/symbol also references LT6234 — reconcile). Earlier prototypes used NE5534 audio
  op-amps; replaced because their ~13 V/µs slew was too slow to resolve the sweet spot
  after high gain.
- **ADC:** U6 **LTC2508-32**, 32-bit oversampling SAR with a configurable digital
  decimation filter **and** a no-latency output.
  - **SDOA (SPI1):** 32-bit filtered/decimated value, `DRL` = data-ready-low. This is
    the precision measurement path. *(measured noise ≈ ±450 µV)*
  - **SDOB (SPI0):** no-latency raw value (schematic annotates "22 bits raw"; firmware
    and diary call it "14-bit"). Used in the full system for baseline + sample-timing
    search. *(measured noise ≈ ±1400 µV)*
  - **Decimation** SEL0 (GPIO12): 256 (operating) or 1024. SEL1 is not driven by the
    current firmware, so only two ratios are reachable.
  - **Conversion sync:** the falling edge of the GPIO5 PWM (the `SAMPLE`/`MCLK` line)
    starts each conversion, so every TX cycle yields one timed sample at exactly
    `sample_delay` after coil turn-off.
- **References:** U5 LTC6655-5 (precision 5 V), U7 LT1762-2.5 (low-noise 2.5 V for ADC).
- **Theoretical resolution:** 32 bits over 5 V ≈ 1.2 nV LSB. *(measured ≈ 10 µV
  precision; warmed-up standard deviation typically < 100 µV.)*

### RX front-end — still to measure
- **Actual RX coil L and C** — the old 3.9 mH / 311 pF was *inferred* from a resonant
  frequency and is now stale (the measured ~1.3k critical-damping value implies
  √(L/C) ≈ 2.6k, not the ~3.5k the old figures gave). Re-measure the RX self-resonant
  frequency to pin L and C. *(Clip-release/recovery has since been measured — see the
  ADC-input overshoot note above: ~300–700 ns ring-to-settle, no regression.)*

---

## 7. Digital / timing (RP2040)

- **MCU:** Waveshare RP2040-Zero (U10), running MicroPython.
- **Pulse + sample generation:** two PWM channels on the **same slice** (GPIO4 = PWM2A
  drive, GPIO5 = PWM2B sample). Same slice ⇒ both rising edges align at period start;
  drive falls at `pulse_width`, sample falls at `pulse_width + sample_delay`. This
  phase-locking is essential and is the core timing trick — **do not split these onto
  different slices.** *(measured sample-timing precision ≈ 15–20 ns.)*
- **Pulse width:** 5–50 µs. **Sample delay:** software-set, with an empirical
  `SAMPLE_PULSE_CORRECTION = 0.752 µs` offset.
- **Pulse rate:** 5 kHz typical. A **prime-ish** rate (3719 Hz was used historically)
  was found to halve noise by avoiding beat frequencies.
- **SPI map:** SPI0 = raw (SCKB GPIO2 / SDOB GPIO0 / BUSY GPIO15); SPI1 = filtered
  (SCKA GPIO10 / SDOA GPIO8 / DRL GPIO9); SEL0 = GPIO12.
- **Meter:** differential PWM drives an analogue panel meter (`METER-POS`/`METER-NEG`).
- **Front-panel:** 4 pots (POT-0..3), 2 buttons (SW-0/1), 12 test points, RF shield.

### Serial protocol — two non-concurrent modes (v4.0x)

The firmware exposes two mutually-exclusive acquisition modes over one serial link:
- **Mode 1 — filtered / interrupt-driven** (the mature path, unchanged from v3.x): the
  32-bit filtered ADC output, streamed at ~20/s. **This is the mode used for all the
  baseline captures and field tests in this document, and is working well.**
- **Mode 2 — raw interleaved moving-average sweep** (new in v4.00, *still under
  development/testing*): cycles a profile's z×y (pulse-width × delay) grid one PWM period
  per cell, keeps a rolling average of depth x per cell, and streams a per-cell vector.
  This is the decay-curve / ML acquisition path (rationale in §13). Metal-detection
  response via Mode 2 was first confirmed 2026-06-16 (profile 3, TRACK_25K).

> The exact command set, record formats, scaling constants, and the compiled profile
> table are the firmware↔tooling contract and live in **`CLAUDE.md`** (kept there to
> avoid drift between this narrative and the wire format). This README does not duplicate
> them — see CLAUDE.md "Serial protocol" and "Scan Profiles".

---

## 8. Power system

| Rail | Source | Purpose |
|------|--------|---------|
| +15 V | U1 L7815CV | coil drive |
| +12 V | U2 L7812CV | analogue |
| +5 V | U9 L7805CV | digital |
| +3V3 | RP2040-Zero onboard LDO | MCU/logic |
| +2V5 | U7 LT1762-2.5 | ADC |
| 5 V ref | U5 LTC6655-5 | precision reference |

Input: 5× LiPo (16.5–21 V), F1 2 A fuse, D4 1N4004 reverse protection, FB1 ferrite
bead. A **dedicated** battery is used for the detector (the rover's 40 V supply was too
noisy). **Known supply-noise facts** (measured, free-air, 10-sample σ):
- ~200 µV USB-powered, no flash
- ~250 µV battery, no flash
- ~900 µV USB, using onboard flash
- ~4000 µV battery, using flash
USB power is ~50 % quieter than the onboard 7805-from-supply path — **cause unknown,
unsolved.** Writing to onboard flash raises the noise floor ~10× (mitigated by
streaming over a single UART TX pin instead). A Ryobi tool battery injected a large
glitch every ~15 s and was abandoned for precision use.

---

## 9. What makes this design unusual (deliberate, validated choices)

- Sampling the **0.5 V–5 V** band of the flyback decay rather than the usual bottom
  ~700 mV — found to carry more discrimination information and sit well above the noise
  floor.
- **Circular/rectangular RX under elliptical/larger TX** to cut mutual coupling and
  enable very early sampling.
- A **signed-standard-deviation edge detector** (σ × sign of start-to-end sample
  difference) used in place of a high-pass filter to handle slow thermal/baseline
  drift while still flagging target edges and their direction.
- **Dual-output ADC strategy:** fast raw path for baseline/timing search, slow filtered
  path for the precision measurement.

---

### v512 — single pulse, air baseline (10 µs pulse)
Rigol, HiRes, CH1/CH2 5 V/div, CH3 50 V/div; trigger on the conditioned ADC input at
t = 0, TX cutoff at −2.5 µs.
- **CH3 (TX drive node):** baseline through the 10 µs on-time, then a fast clean spike
  to ≈ **170 V** at cutoff and rapid collapse. Fast clean turn-off, no long ring.
- **CH1 (RX response):** swings hard negative during the pulse (negative clip active),
  flips positive and saturates at cutoff, then decays.
- **CH2 (conditioned ADC input):** hard-clamped to **+5 V** while the signal is large,
  then released into the linear 0–5 V window as the decay falls.
- **Usable result:** sampling possible from ≈ **4 µs after TX cutoff** (the exact figure
  is the instant CH2 leaves the +5 V rail; measure cutoff→clip-release with a cursor,
  not from the trigger, since trigger and cutoff differ by 2.5 µs here).

### v513 — pulse-width family, air (1–100 µs)
Persistence sweep over pulse widths 1–20 µs in 1 µs steps, then 30, 40, 50, 100 µs.
CH1/CH2 50 V/div (flyback nodes), CH3 2 V/div (conditioned ADC input). On-screen
measurements:
- **Vmax CH1 (TX flyback)** = **251.22 V**
- **Vmax CH2 (RX flyback)** = **176.12 V**  ·  Vmin CH2 = 186.66 mV
- **Vmax CH3 (conditioned ADC input)** = **5.1776 V**  ·  Vmin CH3 = 17.6 mV
- **Reading:** flyback matches the characterised 251 V / 176 V exactly. The conditioning
  holds the ADC input inside ≈ 0–5.18 V across the *entire* pulse-width range (1 µs to
  100 µs). The curve family is the empirical map of the **pulse-width → response
  timing/amplitude** relationship: wider pulse ⇒ higher, later-peaking, slower-decaying
  response ⇒ later earliest-valid sample but larger (ferrous-favouring) swing. This is
  the visual form of the `e^(index·0.3) − 1` sample-delay spacing, and the spread of the
  conditioned curves through the 0.5–5 V band is the discrimination information the
  design targets.

> Both frames are internally consistent with §10: short pulse (10 µs) samples ≈ 4 µs;
> the 40 µs operating point samples 8.4 µs. Shorter pulse → less stored energy → faster
> decay → earlier sample.

### Operating-point air test — ferrous vs non-ferrous + drift (5 kHz / 40 µs / 8.4 µs)
Captured in the PC GUI at the actual operating point (DS 256), bench/air. 2 mV/div,
1 s/div, 30 s window.
- **Discrimination:** one sharp **up-spike ≈ +8 mV (ferrous)** and one sharp
  **down-spike ≈ −4 mV (non-ferrous)** against a quiet baseline ≈ +5 mV. Cleanest
  polarity-discrimination reference in the set (no ground wander in air).
- **Noise:** Std Dev **165 µV** at the operating point — better than the field run.
- **Drift (measured):** baseline **slope ≈ −89 µV/s** across the window — thermal drift
  live at the operating point. At 165 µV noise, the baseline moves by more than the
  noise floor in under ~2 s, which is why static baselining alone is insufficient and
  the signed-σ / slope detector exists. **Use −89 µV/s as the current baseline figure
  that any thermal-compensation work must reduce.** A cold-start-to-steady capture of
  this idle baseline gives the warm-up curve (slope decaying toward a residual
  steady-state value).

> Field equivalent (rough dirt, moving): a separate GUI capture at 9.6 kHz / 20 µs /
> 8 µs showed three non-ferrous (down) and two ferrous (up) targets discriminated by
> polarity while the unit was pushed over uneven ground, with Std Dev ≈ 226 µV. The
> slow baseline wander in that frame is ground/lift-off signal — the reference a future
> two-gate ground-balance scheme would subtract (see §12).

### Post-rework baselines (2026-06-16, after the RX front-end rework — current reference)
Three captures taken once the reworked front end (§6) was running, Mode 1 / v4.00:
- **App baseline** (`pics/App_Baseline.jpg`) — 10 kHz / 20 µs / 10 µs / DS 1024. Clean
  polarity discrimination: the **positive spike is a steel spanner (ferrous)**, the
  **negative spike is an aluminium bar (non-ferrous)**, against a quiet baseline with
  **noise well under 500 µV**. Confirms the front-end rework preserved discrimination and
  a healthy noise floor.
- **Scope baseline** (`pics/Oscilloscope_Mode_1_Baseline.jpeg`) — 10 kHz / 40 µs, four
  traces: **yellow = across TX coil, aqua = RX coil, cyan = ADC input (conditioned),
  blue (rising) = sample point / MCLK**. The blue MCLK edge shows *where in the decay the
  sample is taken* relative to the conditioned ADC-input trace — i.e. the visual link
  between sample-delay and clip-release. This frame is the source of the §6 bible voltages.
- **ADC-input edge detail** (`pics/Screenshot_2026-06-16_13-34-49.jpg`) — the edge ring
  peaking +5.30 V / −0.69 V and settling to ~5.0 V within ~300 ns (front-end recovery;
  see §6).

---

## 12. Open problems (priority order)

1. **Thermal drift.** Wider pulses heat the TX damping/gate resistors (R10 270 Ω, R11
   220 Ω 5 W — R12/R13 are now 0 Ω); the drive circuit drifts and the sensitive RX side
   drifts with it. This is the main ceiling on using pulse-width as a discrimination axis.
   Likely a thermal-design / compensation problem.
   *Current measured baseline: ≈ **−89 µV/s** at the 5 kHz / 40 µs operating point (air,
   §11). Target for any compensation work.*
2. **7805-vs-USB supply-noise mystery.** Onboard 7805 path is ~50 % noisier than USB
   power; cause unresolved.
3. **General supply noise floor** (battery vs USB, flash penalty — partially mitigated).
4. **Coil mechanical stability** — largely solved in v3/v4 (epoxy + Perspex).
5. **RX front-end damping/clamp (resolved 2026-06)** — the RX was chronically
   under-damped (R1 = 20 k vs ~1.3k critical), masked by clamp clipping; exposed when
   the D3 Schottky failed open. Fixed: R1 → 1.3k (real damping), R9 → 4.7k (clamp
   current-limit), D2 → 1N4732 4.7 V, D3 → 1N5819. Op-amp output now 5.189 V (under the
   5.3 V ADC abs-max). See §6. Open sub-items: confirm clip-release didn't regress;
   re-measure RX coil L/C.

---

## 13. Future direction — ML / target classification

Project goal note: this is a **discovery / learning project**, intended for publication
(e.g. Instructables) so others can benefit. It is **not** trying to compete with
commercial gold detectors. ML-based classification fits that goal well and is a good
publishable arc.

### The enabling data-format change (do this first)
Each logged CSV row is currently **one scalar per pulse** — the decay voltage at a
single `sample_delay` (`time_ms, value, stddev, freq, pulse, delay, downsample`). The
discrimination information lives in the **shape of the decay curve**, not a single
point. Example from target-characterisation captures: a silver-plated spoon shows a
negative swing from the silver coating at ~8.5 µs, then a **+10 mV positive swing from
the stainless core at ~13 µs** — a sign-flip that a single 8.4 µs sample cannot see.
Likewise a stainless pipe reads non-ferrous-like at low pulse energy but differently at
100 µs.

**Required firmware change:** capture a *vector*, not a point — sweep `sample_delay`
across ~8–16 values (≈ 5–30 µs), optionally × two pulse widths, so each detection
becomes a short decay curve. Either step the delay across successive pulses
(time-multiplex — fine for a slow-moving rover) or read multiple gates from the fast
raw ADC path (currently dead code) within one decay. This vector is the ML feature
source; without it, classification has almost nothing to learn from.

### Realistic ML approach (classic ML, not deep learning)
With curve data, hand-derived features are likely sufficient and far more publishable:
- decay time constant(s) from an exponential fit
- early/late amplitude ratio
- target polarity (ferrous = positive, non-ferrous = negative)
- pulse-width response slope (10 µs vs 100 µs behaviour)
- presence of a sign-flip / two-phase signature (e.g. coated objects)

Feed these into a small classifier (k-NN, random forest, logistic regression). This is
effectively learning, from data, the equivalent of the hand-tuned "soil timings" a
commercial unit ships with.

### Two distinct problems — don't conflate them
- **Cleanup** (drift removal, ground/lift-off subtraction, denoising): signal
  processing. The signed-σ / slope detector and a future second sample gate live here.
  ML optional.
- **Classification** (what metal is it): where ML earns its keep, and it **requires**
  the multi-delay curve data above.

### Honest caveats for the writeup
The existing target-characterisation montage is excellent but small, hand-labelled, and
captured **in air**. ML is only as good as the labelled dataset. Realistic arc:
add multi-delay capture → log many passes over the known test-object set → fit a small
classifier → demonstrate it labelling held-out passes. Achievable and publishable; does
not require chasing commercial performance.

### Chosen acquisition architecture (raw path + firmware averaging)
The LTC2508-32 has two outputs; the decay-curve capture must use the **fast no-latency
(raw) path**, not the 32-bit filtered path. The reasoning, worked at the 5 kHz pulse
rate (not the datasheet's 1 Msps headline):

- **Filtered (SDOA, 32-bit) is a near-DC instrument here.** At DF=256 the filter is a
  2304-tap FIR; group delay ≈ 2304 conversions and full settling ≈ 10 output samples.
  At 5 kHz that is ≈ **0.46 s group delay** and ≈ **0.5 s to settle after any change of
  sample delay**. Its −3 dB bandwidth scales from 480 Hz @ 1 Msps to ≈ **2.4 Hz** @
  5 kHz. An 8–16-point delay sweep would take 4–8 s — unusable on a moving platform.
- **The 32-bit resolution is mostly wasted in this system anyway.** Filtered transition
  noise at DF=256 is 0.095 ppm ≈ **0.95 µV** (10 V span), but *measured* filtered noise
  is ≈ **450 µV** — ~500× higher. The noise floor is set by the coil/front-end/
  environment, not the converter. Paying 0.5 s latency for sub-µV precision the analog
  side cannot deliver is a bad trade.
- **Raw (SDOB, 14-bit) updates every conversion with zero latency**, so stepping the
  sample delay pulse-to-pulse tracks instantly. Quantisation noise ≈ 1 LSB RMS ≈
  10 V/16384 ≈ **610 µV** (consistent with the ≈ 1400 µV measured raw figure).
- **Recover resolution in firmware by boxcar-averaging M raw samples at a held delay:**
  noise falls as √M. M=16 → ≈ **350 µV** (matching the filtered path's real-world
  450 µV) in **16/5000 ≈ 3.2 ms**, versus the filter's ≈ 460 ms — ~140× faster for
  equivalent real-world noise, with latency *you* control. The on-chip filter is just a
  2304-point sinc average; a 16–64-point boxcar captures most of the benefit.

**Resulting split (datasheet Fig 35 reads both outputs together):**
- **Raw 14-bit (SDOB):** sample-timing search, the multi-delay decay-curve capture for
  ML, and tracking while the coil moves. Averaged to taste.
- **Filtered 32-bit (SDOA):** held at one fixed sweet-spot delay, allowed to settle,
  used as the low-noise baseline / steady-state precision reading where ~0.5 s latency
  is acceptable.

This matches the diary's original intent ("sample timing determined using the raw
14-bit data," then filtered 32-bit for the measurement); the ML direction simply leans
harder on the raw path. **Firmware note (v4.00):** the raw SPI path (SPI0/SDOB) is **now live** in
`mcu/pimd_mcu.py`. Mode 2 uses it for all profile acquisition; metal detection response
confirmed 2026-06-16. SEL1 is still unwired (DF limited to 256/1024 for the filtered
path); the raw path is unaffected. Wire SEL1 if the 4096/16384 filtered options are
ever wanted.

### Scan grid (x / y / z) at 10 kHz, slow movement
A scan captures **x** raw averages per point, at **y** sample delays, for **z** pulse
widths. Recommended starting grid (full derivation in `CC_PROMPT.md` Appendix A):
- **x ≈ 32** averages → ~250 µV (raw floor ≈ 1400 µV, noise = 1400/√x), 3.2 ms/point.
- **y ≈ 8** delays, log-spaced ~5–40 µs via `e^(0.3n)−1`.
- **z ≈ 3** pulse widths: 8 / 20 / 40 µs (the ferrous/non-ferrous discriminant axis).
- Frame time ≈ x·y·z·100 µs = 32·8·3 ≈ **77 ms** (~13 frames/s); at 0.2 m/s a target
  dwells ~20 frames. Time is comfortable — spend it on x and low z (heat), not speed.

Constraints: at 10 kHz the 100 µs period must hold `pulse_width + max_delay + recovery`,
so delays ≤ ~40 µs and pulse widths ≤ ~40–50 µs; wide ferrous-favouring pulses
(50–100 µs) need a separate low-rate (~2.5–3 kHz) burst pass. **Thermal duty, not time,
is the binding constraint** — higher duty drives the −89 µV/s drift, so keep z small.
Refinements: adaptive x (light on high-SNR points, heavy near the floor), and two
cadences — a cheap single point every cycle for position tracking, the full y×z matrix
every few hundred ms for classification.

### Control model — why fixed compiled profiles (rationale)
The orchestration choice (the *mechanics* — command set, the interleaved sweep loop, and
the compiled `PROFILES` table — live in **`CLAUDE.md`**; this is the *why*):
- **Keep the MCU a simple primitive engine**, not a PC-driven scan engine. A scan is a
  **fixed, compiled-in profile** the MCU runs locally, so the link carries "run profile
  n / stream" rather than dozens of per-point round-trips. That kills the serial
  round-trip latency that was the real speed concern, and is transport-independent (helps
  even more over a future LoRa/UART link, the path to an untethered unit).
- **No flash writes** — profiles are compiled constants. Writing to flash spiked the
  noise floor ~10× (§8), so the profile mechanism deliberately avoids it. Profiles are a
  control-plane change and do **not** affect the noise floor.
- **Manual Mode-1 commands stay** for debug/tuning; the profile commands are additive.
- **Fixed per-profile geometry → ML trained per profile.** Because a profile's z×y grid
  is constant, the feature-vector shape is constant, so a classifier is trained per
  profile and the profile listing is the firmware↔ML contract.

### Two unsolved sub-questions parked here
- Mode 2 / profile acquisition is **working but still under active development and
  testing** — only profile 3 (single-point 25 kHz tracker) has confirmed metal-detection
  response so far; the multi-cell classification profiles (0–2) are not yet bench-validated.
- The decay-curve capture is the firmware enabler; the **per-profile feature reduction
  and classifier** are PC/app-side and not yet built.
- Whether wide-pulse ferrous discrimination justifies a separate low-rate burst pass is
  an open empirical question (needs ground-vs-air captures).

---

## 14. Repository / file inventory

| File | Role |
|------|------|
| `mcu/pimd_mcu.py` | RP2040 MicroPython firmware (header v4.01; `FW_VERSION='4.00'` string — reconcile) — both modes, all profiles |
| `mcu/main.py` | One-line board launcher: `import pimd_mcu` |
| `src/pimd_gui.py` | PC PyQt6 GUI v4.00 — Mode 1 filtered telemetry display *(not bench-tested v4.00)* |
| `src/pimd_scope.py` | PC PyQt6 scope v4.00 — Mode 2 raw streaming visualiser (metal detection confirmed 2026-06-16) |
| `src/pimd302.py` | Legacy PC GUI v3.02 (superseded; kept for reference) |
| `src/pimd111.ui` | Qt Designer UI source for legacy GUI *(pimd111_ui.py generation not re-tested)* |
| `src/requirements.txt` | Python dependencies for PC tools |
| `src/serial-speed-test.py` | Raw packet-rate/interval probe on /dev/ttyACM0 |
| `Electronics/PIMD604/PIMD604.kicad_sch` | *Schematic, KiCad 8, rev 6.04 (multi-sheet)* |
| `PIMD___Mark_Makies.pdf` | *34-page work-in-progress diary (Nov 2023 – Feb 2025)* |
| `docs/reference/schematic_v601.jpg` | *Schematic export, rev 6.01, for quick reference without opening KiCad* |
| `docs/reference/v512_baseline.jpeg` | *Reference scope capture: 10 µs pulse, air (see §11)* |
| `docs/reference/v513_pulse_width_response_test.jpeg` | *Reference scope capture: pulse-width family 1–100 µs (see §11)* |
| `docs/reference/operating_point_ferrous_nonferrous_drift.jpg` | *GUI capture: operating-point air, ferrous vs non-ferrous, drift −89 µV/s (see §11)* |
| `pics/Scematic_Baseline.jpg` | Schematic export, **rev 6.04** (current front-end + R12/R13=0Ω + field annotations) |
| `pics/Oscilloscope_Mode_1_Baseline.jpeg` | Scope baseline, Mode 1, 10 kHz / 40 µs: yellow=TX coil, aqua=RX coil, cyan=ADC input, blue=sample point/MCLK |
| `pics/App_Baseline.jpg` | App baseline, Mode 1 v4.00, 10 kHz / 20 µs / 10 µs / DS1024: steel spanner (+) vs aluminium bar (−), noise < 500 µV |
| `pics/Screenshot_2026-06-16_13-34-49.jpg` | Scope: ADC-input edge ring (+5.30/−0.69 V) settling to ~5.0 V in ~300 ns (front-end recovery; see §6) |
| `Screenshot_2025-02-28_13-42-12.png` | *GUI capture: field test in rough dirt, 5 targets discriminated by polarity (see §11)* |
| `docs/reference/target_characterisation_montage.jpg` | *Target-characterisation montage: 8 metals, decay response at 10 µs vs 100 µs (coil v2) — ML signature reference (see §13)* |
| `data/P2702-113819.csv` | *Example telemetry log, single-scalar-per-pulse format (see §13)* |
| `LTC2508-32.pdf` | ADC datasheet (Analog Devices) — source for the settling/bandwidth math in §13 |
| `docs/build_notes.md` | *PC GUI dev-environment setup, UI regeneration, and packaging/deploy notes* |
| `README.md` | This file |
| `CLAUDE.md` | Agent-facing intent + operating envelope + invariants |
| `REVIEW.md` | Design-review findings |

> **Open gaps (would close understanding):** the KiCad **PCB** layout (`.kicad_pcb`)
> and Gerbers; the BOM; a scope capture of the single stable ~7.6 µs edge in Mode 2 at
> 25 kHz (to confirm no PWM ping-pong regression after v4.00 deploy); bench test of
> profiles 0–2 and `pimd_gui.py` against v4.00 firmware; scope captures of the 7805
> supply-noise event.

---

## 15. Glossary

- **PI** — pulse induction.
- **Flyback** — the high-voltage transient when coil current is interrupted.
- **Critical damping** — resistive loading that suppresses coil ring without
  over-slowing recovery; here intentionally biased toward over-damping for early
  sampling.
- **Decimation / down-sample** — the LTC2508's digital filter averaging factor
  (256/1024…), trading output rate for noise.
- **DRL / BUSY** — LTC2508 data-ready signals for the filtered / raw outputs.
- **Same-slice PWM** — using two channels of one RP2040 PWM slice so the TX pulse and
  the sample trigger are phase-locked.
- **Sweet spot** — the post-pulse delay window giving the best target-vs-baseline
  signal-to-noise (currently ≈ 8.4 µs).
- **Clip-release** — the instant the conditioned signal leaves the clamp rail (now
  ~4.7 V, set by D2) and enters the linear measurement window; this, not the trigger or
  TX cutoff, is the true earliest-valid sample time. Measure it by triggering on TX
  turn-off and reading the time until the ADC-input node drops off the clamp level into
  the linear band.