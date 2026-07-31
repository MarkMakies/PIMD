# Pulse Induction Metal Detector (PIMD)

**Author:** Mark Makies (Australia) · **Licence:** CC BY-SA 4.0
**Hardware rev:** 6.04 + shielded enclosure (2026-07-13) + 6S LiPo supply (2026-07-24) · **Firmware:** v4.27 · **PC tools:** gui v4.13 · classviz v1.69 · delaycal v1.30 · features v14 · shape v1 · target_check v4 · corpus_check v1.9 · **Coil:** v4 · **Operating profile:** cal_63_air_bat_v3 (locked 2026-07-26, sha `4a2352d2`).  Bump this line on every edit.
**Last bench update:** 2026-07-31 (v3 corpus at 188 captures; oblique-orientation study)
**Doc rev:** 1.13.1 (2026-07-31) — post-consolidation corrections, **no new bench data**. The three defects 1.13 recorded as *known but not fixed* are fixed, so the text that called them open is now wrong and is corrected here: classviz **v1.69** closes both Std Dev bypasses — the glitch filter and the stall guard — in the heatmap **and** the Stats table, which shared them (§14.12); features **v14** re-syncs `TOOL_VERSION`, which is stamped into corpus rows rather than being a label; delaycal **v1.30** puts the fine step back on the 8 ns grid at default, restore and use (§15). New **§14.15**: both offline acceptance gates fail on the current corpus and **neither failure is a regression** — `pimd_shape --selftest` is being pointed at a corpus from a different epoch than its hard-coded expectations (38 of its 46 problems are the per-epoch crossing ladder), and `pimd_corpus_check`'s 229 FAILs are undiagnosed; §16 carries a caveat on both commands until that is decided. Previous: 1.13 (2026-07-31) — consolidation pass, **the orientation reframe**: the early-band sign separating `ferrous` from `crossover` is an *orientation* coordinate, not a material one; the Pasion–Oldenburg two-basis mixing law is confirmed, so orientation becomes a fitted parameter; the **late**-band sign survives as the robust axis at **97.2 % ungated**. Full detail in `CHANGELOG.md`.

> This file is self-contained: a new reader — human or AI agent — should be able to pick
> up the project cold from here alone. Empirically measured operating values are marked
> *(measured)*; everything else is a nominal/design figure. 

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
here. **Mode 2 (raw profile sweep)** — the decay-curve / future-ML path — is confirmed
operational: first metal-detection response 2026-06-16; CLASSIFY_EP (profile 4,
45-channel sweep) confirmed streaming 2026-06-17 with stable W4 records. The RX front end
was reworked June 2026 (§7). Remaining work is **refinement** (thermal drift, supply noise)
and the ML/classification layer — not redesign.

**Measurement epoch (2026-07-13):** the electronics were moved into a new **shielded
enclosure**, and fw v4.24 changed Mode 2 boundary-settling timing. Together these void
most previously measured quantitative values (noise floors, drift rates, delay tables,
target-session numbers). §3 and §17.1–17.6 are retained as flagged history — re-measure
before relying on any pre-2026-07-13 figure. The ML signature corpus is to be rebuilt on
the new hardware state — the capture tooling for that rebuild landed 2026-07-14
(`targets.csv` registry, classviz v1.32 structured capture, features v6; §15) and was
hardened through 2026-07-23 (classviz v1.39, targets v2, corpus_check v1.6; §15).

**First post-enclosure corpus captured 2026-07-23** — 66 captures over 22 registered
targets at 60–420 mm under `cal_63_air_v2`. Its offline analysis established the signature
geometry the classification layer will be built on: signatures separate into three family
quadrants on an early-vs-late pulse plane, the zero-crossing pulse width is a stable third
coordinate that orders the crossover family, and a threshold-axis "decay persistence" ratio
reads decay behaviour independently of sign — a second opinion to the family verdict rather
than a class test, since the ferrite toroid reads ferrous by sign and non-ferrous by decay
(§17.9). That geometry is now
live in the tooling — `pimd_shape.py` v1 holds the maths, classviz's **Family Plane Analysis**
tab (named Shape Space before v1.43) displays it (§15). *(The second, 2.6× larger corpus
re-scopes one of those three coordinates — see the orientation paragraph below and §17.14.)*

**Supply epoch (2026-07-24):** the bench supply failed and the detector moved to a **6S Li-ion
pack** (18650 cells; called "6S LiPo" in earlier entries — §12). Unlike the enclosure change this is *not* a measurement-epoch reset — no §3 or
§17 value is voided by it — but warm-up is longer, and the regulated-window claim is narrower
than it first read (§12, §17.10, §17.13). Recalibration against the new supply completed
2026-07-26: **`cal_63_air_bat_v3` is the locked operating profile** (sha `4a2352d2`, §10) and
the registry moved to **`targets_v3.csv`** (27 objects). The supply change paid off directly —
autonudge now converges at a 0.3 mV threshold that was never reachable on the bench PSU
(§17.11).

**Pack state of charge is an operating variable (2026-07-30).** The most consequential result
since the enclosure: the two highest-signal threshold columns are unusable on a freshly-charged
pack and clean on a half-drained one, because a noise zone sits at a fixed place on the **decay
waveform** while pack voltage scales the decay. **Run the pack at 21.5 – 23.3 V.** Above
**≈ 24.0 V** the 3.80/4.40 V columns are bad however long the rig has run; **22.5 – 24.0 V** is
a transition band where soak time is worth ~2.5–3× against voltage's ~11×, so a soaked rig can
read clean inside it; below ≈ 21.5 V the trouble migrates to the 4.20 V / 4.75 V columns and the
9 µs band. The 21.5 – 23.3 V window is the conservative interior, and **≈ 23.5 V is shorthand
for the transition's practical onset**, not a fourth limit *(edges restated 2026-07-31 — they
were previously used interchangeably; §12, §17.13)*. This is a *data-quality* window inside the
wider
*regulation* window, and it costs the top 1.78 h (17 %) of every pack, which must be streamed
off rather than waited out (§12, §14.7, §17.13). It also reattributes the "≈ 3 h warm-up",
which is largely this discharge rather than thermal soak; thermal drift is real but smaller
(§3, §14.1).

**Family is an orientation coordinate, not a material one (2026-07-31).** The v3-epoch corpus
— **188 captures over 25 targets**, 2.6× the first one and deliberately spanning orientation —
overturns how the three-family split has been read since §17.9. The **early**-band sign that
separates `ferrous` from `crossover` splits by *placement*, not by target: 90.9 % accurate on
transverse captures, **53.8 % axial**, and every miss in the corpus is an axial one. A cast-iron
trivet reads `crossover` lying flat and `ferrous` stood on edge, because the early axis measures
**presented eddy-loop area = geometry × orientation**. What survives is stronger than the old
verdict: the **late**-band sign — iron-bearing vs non-ferrous — reads **97.2 % ungated**, with
decay persistence a clean independent second opinion on it. Alongside this, the
**Pasion–Oldenburg two-basis mixing law is confirmed** on oblique captures, so orientation stops
being a confound and becomes a *fitted parameter*, and an orientation-invariant descriptor (the
2-D subspace itself) becomes well-defined — the foundation the τ-class + size tier needs. The
practical consequence is that tier 2 should be **renamed and re-scoped rather than its accuracy
chased** (§14.9, §17.14).

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

> **Epoch note (2026-07-13):** every value below was measured **before** the shielded
> enclosure and fw v4.24 (§1, §17.7). Treat as historical reference until re-measured;
> one post-enclosure fact is already known — the settled top-of-decay reads
> ~4.87–4.89 V on the heavy bands at short delays, so the delaycal signal-detect
> ceiling must be set to **5.0 V** (a 4.9 V ceiling false-triggers the coarse hunt).

- **Flyback** *(measured, 2026-06-16, 10 kHz / 40 µs)*: TX coil **−18 V to +265 V**,
  RX coil **−15 V to +135 V**. Gate turn-off **11.47 V → 0.44 V in 733 ns**.

- **FET Q1 limits:** < 10 A, < 300 µs, < 2 % duty. *(The detector deliberately
  runs above the 2 % duty note — see §17 power table and §14.)*
- **RX front end** : R1 1.3k damp · R9 4.7k clamp-limit · D2 1N4732
  (4.7 V zener) · D3 1N5819 (Schottky) · 47 Ω into ADC · LT6203 on single +12 V.
  Node after R9 **−0.48 / +5.11 V**; ADC input settles **~5.0 V**, edge ring peaks
  **+5.30 / −0.69 V** (brief, harmless, current-limited). Detail in §7.

- **Noise, warmed-up** *(measured, DS 256)*: filtered path (SDOA) ≈ **±200 µV**; raw single
  sample (SDOB) ≈ **±1400 µV**. *(Corrected 2026-07-31: this line read "raw ≈ ±400 µV", a
  figure that appears nowhere in the record; §7 and every changelog measurement give ±1400 µV,
  and the boxcar arithmetic throughout this document is built on it. The filtered figure is
  not reconciled with §7's "real-world 450 µV floor" at 5 kHz — both are pre-enclosure and
  are on the §14.8 re-measurement backlog.)*
- **Sample-timing precision** ≈ **5 ns** *(measured)*. **Thermal drift** ≈ **−50 µV/s**
  at 10 kHz / 20 µs *(measured)*. *(Note: the one direct check of this rate — 5.2 mV
  accumulated over 150 s, §17.10 — implies ≈ 35 µV/s. The reference-age figures in §14.1
  are computed at 50 µV/s and are therefore an upper bound.)*

- **Standard Operating Conditions (SoC)** *(established 2026-06-18)*: Mode 1 · 10.0 kHz /
  20.0 µs pulse / 10.0 µs sample delay / DS 256 · coil in air, no targets · 20 V bench
  supply · allow **4 min warm-up** from cold (expect ≈ 50 µV/s drop during warm-up; do not
  take noise-floor readings before this point). Reference capture: `References/GUI-steady-state-256-1024.jpg`.
  *(Supply note, 2026-07-24: the 20 V bench supply no longer exists — SoC now runs on the 6S
  pack, §12. Warm-up is longer than 4 min on battery, §14.1. **Amended 2026-07-30:** the
  regulated-window claim holds only over the 0.55 V interval it was measured on — pack voltage
  *does* reach the operating point at 43–51 mV/V over 21–25 V, so **SoC on battery is not
  fully specified without a pack-voltage range**; state one, inside the 21.5–23.3 V window,
  §12/§17.13.)*

- **Mode 2 warm-up ≈ 5 min** *(established 2026-07-02/03; **does not hold for a 63-cell
  profile on battery** — see below)*: the profile duty is much heavier than Mode 1 SoC; run the
  profile in ClassViz until thermal drift settles before calibrating or recording. Cold-ish,
  heavy bands drift up to ~250 ns in calibrated delay; soaked, repeat cals agree to ≤ 40 ns
  (one 8 ns grid step for the light bands). See §17.5.

- **Time-to-usable-data on battery is set by pack voltage, not warm-up** *(measured 2026-07-30,
  §17.13)*. There is no single number, so pick by criterion: **49 of 63 cells reach the floor
  within minutes** and stay there (excluding the two affected threshold columns the grid reads
  0.141 mV cold, unchanged for five hours); a capture the quality gate accepts takes **~2 h**;
  the 4.40 V column clears in **~70 min** and the 3.80 V column in **~2h50m**; within those two
  columns the 100 µs band is the long pole and was **not at the floor in 90 min** *(scoped
  2026-07-31: the "long pole" applies to the affected columns' cells, not to the 100 µs band as
  a whole — §17.13 measures the other seven columns flat from the first window)*. The dominant
  mechanism in all of it
  is the pack draining into the 21.5–23.3 V window — **1.78 h of unavoidable streaming from
  full** — not thermal settling.

- **`splithalf_floor` understates reproducibility noise by roughly 2×** *(measured 2026-07-31,
  §17.14)*. It is a within-capture short-timescale statistic, so it does not see everything that
  moves between two captures of the same thing. Measured two ways that agree: shape scatter
  between repeats runs **2.4× the isotropic-additive-noise prediction** built from it in 90 % of
  pairs, and the corpus's air captures show it directly — across-capture L2 **4.03 mV** against a
  median `splithalf_floor` of **1.82 mV** (×2.2). Practical consequence: **the SNR ≥ 5 gate is
  really a reproducibility gate of ≈ 2.5–3.5**, which is why raising it keeps paying.

- **The between-session noise component measures zero** *(measured 2026-07-31, §17.14)*. Pooling
  within-session per-cell σ over the corpus's 19 air captures against the all-captures σ gives
  **4.24 mV vs 4.03 mV** across three days and eight sessions — no measurable session-to-session
  offset. Captures made on different days are directly comparable, which is what a training
  corpus needs and was not previously established.

---

## 4. System block diagram (text)

```
 6S LiPo (19.8–25.2 V, working floor 21.0 V)
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

 RP2040 ─ serial (USB-CDC / UART) ─► PC tools (PyQt6) 
```
---

## 5. Coils

Separate TX and RX windings (a two-winding "transformer", **not** a shared mono coil). 

**Coil v4:** two coils slotted into 12 mm Perspex, RX shielded with copper tape,
both embedded for mechanical stability (earlier coils shifted under rover vibration;
epoxy/Perspex fixed the resulting drift). Faraday shield on RX with **no closed loop**.

TX 520 × 360 mm, 10 turns 0.5 mm (24 AWG) enamelled, 17.6 m, 1.7 Ω ·
RX 430 × 265 mm, 50 turns 0.25 mm (30 AWG) Teflon silver-plated wire-wrap, **≈ 69.5 m**, 22.9 Ω.
*(Corrected 2026-07-31: this read 30.8 m, which is impossible for the stated geometry —
2 × (0.43 + 0.265) m × 50 turns = 69.5 m — and inconsistent with its own resistance, since
22.9 Ω at ~0.34 Ω/m for 30 AWG implies ~67 m. Two independent routes agree; 30.8 m was out by
2.3×. TX checks exactly: 2 × (0.52 + 0.36) × 10 = 17.6 m.)*
Cable: RG62A/U coax (93 Ω, 47 pF/ft) + twin 26/0.3.


**Damping is intentionally biased toward over-damping** — it kills ring faster and lets
sampling start earlier, trading a little amplitude for earlier access to the decay. Values
are tuned empirically on a scope, not by formula. 

---

## 6. Transmit / drive chain

- **Q1:** IRF610 N-channel MOSFET, low-side switch, source to GND. Schematic limits
  < 10 A / < 300 µs / < 2 % duty; the 200 V rating is marginal against measured flyback and
  is managed by duty limits + damping. *(See §14 + §17: present operation pushes the duty
  limit.)*
- **Gate driver:** U4C → U4D (TL074 sections) level-shift the 3.3 V `COIL-DRIVE` logic up to
  a ~10 V gate swing. Design intent throughout: fast, non-linear FET switching with
  parasitic-capacitance management.
- **Gate / damping network:** R12/R13 are now 0 Ω 
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

- **R1 = 1.3k (shunt) is the RX damping resistor** — **critically damps at ≈ 1.3–1.4k**
  *(measured)*, which also cleans up TX via mutual coupling.
- **R9 = 4.7k (series) is clamp current-limit only**, not damping — it holds clamp current
  to ≈ 9.6 mA at the +50 V damped peak, well inside the LT6203 rating. *(Open, flagged
  2026-07-31: the +50 V "damped peak" is not reconciled with the §3 flyback measurement of
  **+135 V at the RX coil**, which through 4.7k would imply ~28 mA. Either the two are measured
  at different points or under different damping — a scope check at the post-R9 node would
  settle it. Not a claim that the front end is out of spec: it has run for months.)*
- **D2 (4.7 V zener) / D3 (1N5819 Schottky)** sit in series across the post-R9 node and only
  conduct outside ~0–5 V; between the rails the diodes are off and R1 does the damping.
- **47 Ω** between the LT6203 output and the ADC input limits over-range current into the
  ADC's internal protection.

### Preamp / ADC / references
- **U3 LT6203** dual high-speed op-amp, single +12 V 
- **U6 LTC2508-32**, 32-bit oversampling SAR with a configurable decimation filter **and** a
  no-latency raw output:
  - **SDOA (SPI1):** 32-bit filtered/decimated value, `DRL` = data-ready-low — the precision
    path *(noise ≈ ±450 µV)*.
  - **SDOB (SPI0):** no-latency raw value (firmware/diary call it 14-bit; schematic annotates
    "22-bit composite = 14-bit differential + 8-bit common-mode") — baseline + sample-timing
    search *(noise ≈ ±1400 µV)*.
  - **Decimation** SEL0 (GPIO12): 256 (operating) or 1024. 
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

**BUSY edge sync (required for accurate SDOB reads, firmware v4.19):** `read_raw_sample()`
must synchronise to the LTC2508-32's BUSY signal — wait for BUSY-high (MCLK fires,
conversion starts), then BUSY-low (conversion complete), then read SDOB. Without this,
reads that land mid-conversion produce bit-truncated outliers at exactly 1/4 and 1/2 of
the true value (1–2 SPI bits cut off and zero-filled). Confirmed mechanism via v4.15
min/max diagnostic: outliers at ≈ 375 000 µV and 750 000 µV alongside normals at
≈ 1 511 000 µV — ratios of exactly 1/4 and 1/2. Side-effect: the BUSY-high pulse at
10 kHz is ≈ 15 µs; MicroPython's polling loop catches ≈ 1-in-6, reducing effective raw
sample rate to ≈ 1.6 kHz (vs 10 kHz configured). Accepted tradeoff for accuracy.

**Mode 2 single-cell noise:** normal multi-cell sweeps (cells alternating duty values) give
≈ 310 µV std dev — matching the **M=16** boxcar expectation (≈ 1400 µV / √16 = 350 µV), which
is the averaging depth the profile under test actually used. *(Corrected 2026-07-31: this read
"M=32", whose expectation is 247 µV — 25 % below the measurement it was said to match.)*
A degenerate
single-cell run where the PWM compare value never changes gives ≈ 24–30 mV std dev. The
exact RP2040 PWM register mechanism is unconfirmed empirically; the finding is reproducible.
Practical conclusion: use Mode 1 for single-point measurement; Mode 2 is for multi-cell sweeps.

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
  ≈ 5 ns, measured.)*
- **Pulse width:** 5–50 µs. **Sample delay:** software-set, with an empirical
  `SAMPLE_PULSE_CORRECTION = 0.904 µs` offset between the PWM edge and the ADC trigger.
- **Pulse rate:** 5-50 kHz typical. A **prime-ish** rate  halved noise by
  avoiding beat frequencies — the rate choice is deliberate, not arbitrary.
  **Known-bad rate: 31.25 kHz** *(measured, 2026-07-02)* — at 31.25 kHz / 9 µs an entire
  profile band was unusable (three cells never settled, σ 2–5 mV; remaining cells 5–10×
  noisier than neighbouring bands, non-monotonic means). Moving the band to 25 kHz with the
  pulse unchanged restored normal behaviour (σ 0.02–0.10 mV) — the noise followed the rep
  rate, not the pulse/decay alignment. Mechanism unconfirmed; avoid 31.25 kHz in profiles.
- **Mode 2 boundary settling is time-floored** *(fw v4.24, 2026-07-13)*: settling at each
  band/energy boundary is `max(BOUNDARY_PRIME = 15 periods, ceil(SETTLE_FLOOR_US = 3000 µs
  / period))`. The earlier period-only budget under-settled high-frequency bands (25 kHz:
  600 µs, 20 kHz: 750 µs vs the ~1 ms+ the band-to-band energy-step transient needs) —
  root cause of the first-heatmap-column noise, bench-verified fixed (§17.7). Sweep cost
  ≈ +12 ms on the 72-cell profile. *(Corrected 2026-07-31: this used to add "(~289 → ~301 ms
  refresh)". Those figures were never measured — they came from a per-cell timing model that
  assumed 32 conversions per cell per visit. The firmware takes **one** period per cell per
  sweep and emits one W record per sweep, and the measured interval is **0.1445–0.1455 s
  (6.88–6.92 Hz)** on the 63-cell profile, §17.13. The +12 ms settle cost is unaffected.)*
- **Raw-read outlier gate is floored** *(fw v4.25, 2026-07-14)*: the v4.21 plausibility
  gate now compares against `abs(mean_raw)` with an absolute floor
  `OUTLIER_GATE_MIN = 164` raw14 counts (≈ 100 mV). Previously a near-zero or negative
  rolling mean made the threshold ≤ 0, every sample was rejected and the substituted mean
  froze the cell at its warm-up value forever — root cause of the "last cell flat at zero"
  seen on the deepest-decay cell (§17.8).
- **IRQs stay disabled through the freq/CC writes** *(fw v4.26, 2026-07-14)*:
  `read_raw_bytes_hold()` extends the v4.21 critical section from the BUSY-synced SPI read
  through the PWM freq/CC register writes (~2–6 µs on top of the ≤ 36 µs blackout), and
  rolling-buffer bookkeeping moved after the hardware writes. Closes the race where the
  W-record `print()` at sweep index 0 left USB-CDC IRQ bursts queued to fire between the
  read and cell 2's `duty_u16` write — the RP2040 CC register is not double-buffered, so a
  late write left one conversion sampling at the previous cell's compare point, poisoning
  that cell's rolling average every sweep (index-locked σ anomaly, bench-verified fixed —
  §17.8).
- **The Mode 2 emit can block, and the host can cause it** *(fw v4.27, 2026-07-30)*: the emit is
  a blocking `print()` to USB CDC, so a host that stops draining the pipe stalls the MCU *inside*
  it — observed for 47 minutes (§14.10, §17.13). v4.27 **counts** these rather than preventing
  them: the emit `print()` is bracketed with `ticks_ms()` and calls over
  `EMIT_BLOCK_WARN_MS = 50` increment `emit_block_count` / `emit_block_ms_max`, reported on `B`
  (§9). `ticks_ms` not `ticks_us` is a deliberate margin choice — `ticks_us` wraps every
  ~17.9 min with `ticks_diff` valid over only half a wrap (~8.9 min), so any *single* emit
  blocked longer than that would decode to plausible-looking garbage. *(Reason corrected
  2026-07-31: this claimed the 47-minute stall itself would have decoded wrong. It would not
  have — the counter brackets one `print()` call, and that stall was 222 separate blocks of
  2–15 s, all far inside `ticks_us` range. The choice is still right, as nothing bounds a
  single block.)* Making the emit non-blocking is **deliberately not done**: dropping
  a record beats stalling the sweep and no invariant objects, but it sits in the acquisition hot
  path (the v4.13/v4.20/v4.24/v4.26 sequence is fair warning) and needs bench proof that
  MicroPython's rp2 port reports stdout writability at all. Measure first — the counters say
  whether it ever recurs.
- **SPI map:** SPI0 raw (SCKB GPIO2 / SDOB GPIO0 / BUSY GPIO15); SPI1 filtered (SCKA GPIO10 /
  SDOA GPIO8 / DRL GPIO9); SEL0 = GPIO12.

---

## 9. Serial protocol (both modes) — the firmware↔tooling contract

Two **mutually exclusive** acquisition modes over one serial link (115200 baud). Starting
one requires `E` first. *(Literal field separator in records and the `*` config string is
`", "` — comma-space — shown below comma-only for readability; parsers tolerate either.)*
*(All timing fields are exact integers: freq in Hz, pulse and delay in ns — no decimal points.
At the 8 ns PWM grid every value is an exact multiple of 8.)*

**Mode 1 — filtered / interrupt-driven** (mature; all baselines & field tests):
- **in:** `S`/`s` start · `E`/`e` stop · `*<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>` configure
- **out:** `*<time_ms>,<value_uV>,<stddev_uV>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>`
- **rate:** pulse_freq / downsample (~20/s at 5 kHz / 256)

**Mode 2 — raw interleaved moving-average sweep** (new; under active development):
- **in:** `Q<n>` select profile · `G`/`g` start streaming · `E`/`e` stop
- **out:** `W<profile_idx>,<time_ms>,<mean_ch0>,<mean_ch1>,...`
- **rate:** one W record per full sweep of the profile, rate-limited to at most one per
  `MIN_EMIT_MS = 10` ms (100 Hz ceiling, never reached in practice). Each cell gets one PWM
  period per sweep, with a rolling average `averages` deep held *across* sweeps — so the
  emitted rate is the sweep rate. **Measured 6.88–6.92 Hz** (0.1445–0.1455 s) under
  `cal_63_air_bat_v3` *(2026-07-30/31, firmware clock, §17.13)*. `S` rejected while Mode 2 runs

**Both modes:**
- `V`/`v`/`?` identify → `V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>`
- `L` list profiles → one `L<idx>,<freq_hz>,<n_bands>,<n_cells>,<averages>,<name>` line each
- `A<n>` raw boxcar average (idle / Mode 1 only) → one `R<time_ms>,<mean_uV>,<std_uV>,<count>,<freq_hz>,<pulse_ns>,<delay_ns>,<min_uV>,<max_uV>` line
- `B` diagnostic counters, **reset-on-read** → `B<busy_high_count>,<overrun_count>,<emit_block_count>,<emit_block_ms_max>`.
  The command has existed since v4.11 and was previously undocumented here; the last two fields
  are new at **v4.27** (§8, §14.10). This is an **additive** extension of a documented wire
  format — there is no parser for `B` anywhere in `src/` (it is read by a human over the §16
  serial terminal), so no consumer breaks. Recorded explicitly rather than treated as free, per §11.
- `E` is the universal stop. Modes are mutually exclusive.

**µV scaling (invariant):** filtered (Mode 1) `raw32 * 5_000_000 // 2**31`; raw (Mode 2 / `A`)
`raw14 * 10_000_000 / 2**14`.

---

## 10. Scan profiles

Profiles are fixed/compiled-in RAM constants (no flash writes). Geometry is constant per
profile, so any future ML classifier is trained per profile and the table is the
firmware↔ML contract. **Frames from different profile geometries must never be mixed in
one dataset.**

**A profile is only fully specified together with a pack-voltage range** *(new term,
2026-07-30)*. On a bench supply the operating point is fixed; on battery it is defined only
inside a stated voltage window, because pack voltage scales the decay the amplitude-anchored
delays are cut against (43–51 mV/V, §12/§17.13). Every lock must record the voltage it was
swept at, and every capture campaign must state the window it ran in. This is a dimension of
the firmware↔ML contract that did not exist before the 6S epoch.

### Operating profile — `cal_63_air_bat_v3` (locked 2026-07-26, sha `4a2352d2`)

**7 bands × 9 delays = 63 cells**, averages 32 per cell, raw path (SDOB). Marks the move from
bench PSU to the 6S pack. Two changes from `cal_63_air_v2`:

- **The threshold ladder moves in one position** — 4.9 / 4.8 / **4.75** / 4.4 / 4.2 / 3.8 /
  2.4 / 1.5 / 0.5 V, against v2's 4.70 in third place. The 4.70 column started misbehaving
  after ~30 minutes in classviz, so the profile was re-swept with that step raised. Of the
  4.75/4.35/3.70 ladder trialled on 2026-07-24 **only the 4.75 step is adopted**: 4.40 and
  3.80 keep their original values. *(The reason recorded at the time — that the 4.40/3.80
  elevation was "supply-borne" — was later vindicated on much stronger evidence, though not
  in the way meant: it is pack **voltage**, not the failing PSU. §17.13.)*
- **Delays re-anchored for the supply change:** **+40…+144 ns** against v2, band means +90 ns
  (100 µs) to +125 ns (30 µs). The third column is the outlier at +40…+72 ns and is **not** a
  like-for-like delta — that cell targets a different voltage, so its shift is threshold move
  *plus* supply change, and the two are not separated.

**This is both a new calibration epoch and a threshold-geometry change**, which is weaker than
a clean epoch change and makes the feature-portability question live (raised in §17.10's closing
bench observation). Cross-epoch
comparison is interpretable for the eight columns whose target voltage is unchanged; **the
third column is not comparable to v2's even feature-wise.** An identical cell count does *not*
imply comparability — a cell-count sanity check passes here — so comparability rests entirely
on the `(profile_name, profile_sha8)` guard in `pimd_features`, **which must not be relaxed.**

**Feature portability across the v2→v3 change — answered 2026-07-31 (§17.14), and it is
benign.** Measured across every target held in both corpora, the shift is **coherent and
one-parameter**, exactly as v3's later delay anchoring predicts: both the early and late
band-range means move **+5.2 ×10⁻³ (median, positive)**, and every crossing width interior to the
ladder in both epochs moves **shorter, ratio 0.76 median** (trivet 34 → 24 µs, SS disc 31 → 18,
gal RHS 21 → 19, gal pipe 17 → 13). v3 samples 40–144 ns later, so the fast negative eddy term
has decayed further by the sample instant — every band mean moves positive and the
negative→positive crossing arrives at a shorter pulse width. Amplitude moves **by family, not by
gain** (non-ferrous ×0.67–0.89, iron-bearing ×1.28–1.79), which is the same explanation and
rules out a supply effect, which would scale everything one way. **No target changed its
majority family verdict, and nothing needs re-labelling.** Two consequences that do bite:
the shift lands hardest on the crossover family, because that is where |early| is smallest; and
**crossing widths are per-epoch quantities** — §17.6's ladder values are v2-era and must be
restated against v3 before reuse. The `(profile_name, profile_sha8)` guard still stands: this
result says the two epochs are *relatable*, not interchangeable.

**Calibration conditions:** pack **23.5 → 23.35 V** across the sweep; thermal state at lock
not recorded. Noted for any future re-lock: that span sits **above** the 21.5–23.3 V window,
inside the 22.5–24.0 V transition band, where a soaked rig reads clean but a cold one need not
(§17.13) — **~22.5 V would be more central** and is the voltage to re-lock at. *(Restated
2026-07-31: this previously called 23.5 V "the upper edge of the clean window", which it is
not.)* **No profile change follows from the 2026-07-30 result**; the ladder and `4a2352d2`
stand.

**Revised delaycal parameters** — without these the calibration is not reproducible: fine
sweep 80 → **40**, autonudge threshold 0.5 → **0.3 mV**, nudge step 16 → **8 ns**, soak
20 → **40 s**, std dev n = **16**. The 0.3 mV convergence is itself a result (§17.11).

| Band | Freq (kHz) | Pulse (µs) | Duty | Band share of sweep |
|---|---|---|---|---|
| 1 | 25.0 | 9.00 | 22.5 % | 4.1 % |
| 2 | 20.0 | 13.44 | 26.9 % | 5.1 % |
| 3 | 15.625 | 20.00 | 31.25 % | 6.5 % |
| 4 | 10.0 | 30.00 | 30.0 % | 10.2 % |
| 5 | 6.25 | 45.00 | 28.1 % | 16.3 % |
| 6 | 4.0 | 67.20 | 26.9 % | 25.4 % |
| 7 | 3.125 | 100.00 | 31.25 % | 32.5 % |

**Band plan is unchanged from `cal_63_air_v2`, verified band for band** — the table above
serves both. Full delay table lives in `src/data/profiles/cal_63_air_bat_v3.json`, the only
tracked profile (§15).

**Frame rate: 6.88–6.92 Hz measured** (0.1445–0.1455 s per sweep, firmware clock, §17.13). One
W record is emitted per sweep, and each cell is sampled once per sweep into a 32-deep rolling
average held across sweeps — so frame rate and sweep rate are the same number.

### Superseded — `cal_63_air_v2` (locked 2026-07-14)

Same 63-cell geometry as above, with 4.70 V in the third threshold position, delays anchored
under the **bench PSU**. This is `cal_72_air_v3`'s band plan and top-dense threshold ladder
(all design principles below carry over) with two changes:

- **The 6 µs / 50 kHz band is dropped** (first as `cal_63_air_v1`, 2026-07-14): bench
  judgment — it carried no target information not already present in the other bands and
  was notoriously noisy (its 20 µs period gave the tightest CC-write budget of all bands,
  §17.8; likely a contributor to that reputation). The remaining 7 bands were
  byte-identical to v3.
- **Delays re-anchored fully warmed under fw v4.26** (v1 → v2, same cell geometry):
  shifts of −56…+16 ns vs v1, heavy bands earliest — the thermal signature (decays arrive
  earlier warm). This retired the drift that had pushed the 100 µs / 4.70 V cell onto the
  ≈ 4.67 V upper edge of the §17.7 threshold noise zone (bench-confirmed fixed, §17.8).

Sweep time is slightly under `cal_72_air_v3`'s (one band and one boundary-settle fewer); the
measured figure for the 63-cell profiles is 0.1445–0.1455 s. *(2026-07-31: this sentence used
to give ≈ 301 ms, from the unmeasured model corrected in §8.)* Superseded by
`cal_63_air_bat_v3` at the supply epoch and **retired from tracking 2026-07-26**; the JSON is
retained on disk, and stays available to delaycal's Compare Profiles as a reference. Note
`gui_signatures_targets_v1_20260723.csv` was captured under v2, so the only tracked profile no
longer matches that corpus — expected across an epoch boundary, and exactly what the
`(profile_name, profile_sha8)` guard exists to catch. `cal_63_air_v1.json` (cold-anchored
delays) is likewise retained untracked.

### Superseded — `cal_72_air_v3` (locked 2026-07-13)

8 bands × 9 delays = 72 cells, **averages 32** per cell (raw floor ≈ 1400 µV / √32 ≈ 250 µV),
raw path (SDOB). Calibrated post-enclosure with fw v4.24 (delaycal export
`cal_20260713_210057`, renamed). Superseded by `cal_63_air_v2` (above); the design
principles established here still govern the operating profile:

- **Pulse widths geometric ×≈1.5** (6 → 100 µs). Pulse width is a target-time-constant-selective
  excitation axis; constant-ratio spacing gives equal discrimination information per band and
  removes the near-duplicate bands of the earlier even-spread guesses. (Unchanged from v2.)
- **Frequencies from the CLEAN_FREQS 125 MHz-divisor list**, chosen to hold duty near 30 %
  (22.5–31.25 %) so per-band heating stays roughly even. Duty absorbs the grid quantisation;
  the pulse ladder is kept exact. (Unchanged from v2.)
- **Sample thresholds top-dense (reverse-geometric): 4.9 / 4.8 / 4.7 / 4.4 / 4.2 / 3.8 /
  2.4 / 1.5 / 0.5 V** (amplitude-anchored delays, snapped to the 8 ns PWM grid by
  `pimd_delaycal.py`). Replaces v2's ×0.766 ladder from a 4.2 V anchor: the
  early-decay/high-voltage region carries the most discrimination information and became
  usable once the fw v4.24 settling fix removed the first-column noise (v2's 4.2 V anchor
  was working around what turned out to be a firmware settling artifact plus a bounded bad
  zone, not an inherent top-of-curve problem). Targets deliberately straddle the measured
  **~4.45–4.65 V noise keep-out zone** (§17.7; mechanism unknown, §14) — 4.7 above it,
  4.4 below it.
- **Supersedes `cal_72_air_v2`** (locked 2026-07-03, ×0.766 thresholds from 4.2 V; its
  standalone profile doc was removed with the pre-v4.26 data — the JSON remains in
  `src/data/profiles/`). Frames are **not comparable** across the two (different
  threshold geometry, different hardware epoch; the profile is the firmware↔ML contract).

| Band | Freq (kHz) | Pulse (µs) | Duty | Band share of sweep |
|---|---|---|---|---|
| 1 | 50.0 | 6.00 | 30.0 % | 2.0 % |
| 2 | 25.0 | 9.00 | 22.5 % | 4.0 % |
| 3 | 20.0 | 13.44 | 26.9 % | 5.0 % |
| 4 | 15.625 | 20.00 | 31.25 % | 6.4 % |
| 5 | 10.0 | 30.00 | 30.0 % | 10.0 % |
| 6 | 6.25 | 45.00 | 28.1 % | 15.9 % |
| 7 | 4.0 | 67.20 | 26.9 % | 24.9 % |
| 8 | 3.125 | 100.00 | 31.25 % | 31.9 % |

Full-sweep time rose by ≈ 12 ms with fw v4.24's time-floored boundary settling. *(The ≈ 289 →
≈ 301 ms figures previously quoted here were modelled, not measured, and are ~2× the measured
sweep time — see §8. This profile is retired, so it was never re-measured directly; the 63-cell
successors run 0.1445–0.1455 s.)*
Band 2 runs 25 kHz, not the duty-rule 31.25 kHz — see §8 known-bad rate. Bands 7+8 consume
~57 % of acquisition time and are retained deliberately: target data (§17.6, historical)
showed ferrous targets and copper still rising steeply at the top of the ladder. Full delay
table lives in the profile JSON (`src/data/profiles/cal_72_air_v3.json`).

---

## 11. Invariants — do not break

- **Same-slice PWM phase-locking** (GPIO4/GPIO5, slice 2).
- **serial wire format**, both modes (§9).
- **No scan scheduler or PC-defined logic in firmware** beyond the fixed profile loop; 
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

Input: **6S Li-ion (19.8–25.2 V)** — 18650 cells; earlier entries say "LiPo", and the pack in
use is built from recovered ICR18650-26C cells (see the capacity bullet below). F1 2 A, D4
1N4004 reverse protection, FB1 ferrite bead. A
**dedicated** battery powers the detector (the rover's 40 V supply was too noisy).

**6S epoch (2026-07-24).** The 1990s bench supply failed and the pack replaced it. A cell was
added rather than replacing the documented 5-cell pack like-for-like: at 5S (16.5–21 V) the
pack falls below the L7815's dropout headroom over the back half of its discharge, so coil
drive — and therefore decay amplitude, and therefore the voltage each amplitude-anchored
delay actually lands on (§13) — sags with state of charge. 6S holds the +15 V rail in
regulation across the whole usable discharge. Field deployment is battery-powered regardless,
so this brings forward a supply change the soil phase would have forced anyway.

- **Working discharge floor 21.0 V** (3.5 V/cell) — comfortably above the ≈ 18 V at which the
  7815 loses headroom, and coincident with the cells' own useful-capacity limit, so there is
  no region where the electronics still work but the pack is being damaged.
- **Cost: up to roughly double the dissipation in U1** (≈ 2.5 W on the old 20 V bench supply →
  ≈ 4.6 W at the top of a charged pack, at the §17.1 measured ~0.5 A average; across the usable
  discharge the average is nearer ≈ 3.6–3.8 W, so "double" is the worst case, not the mean),
  inside a sealed shielded enclosure, on a project whose first open problem is thermal drift.
  Warm-up is correspondingly longer than the 5S/bench-supply case (§14.1).
- **Data-quality limits** *(measured 2026-07-30, §17.13)* — a **different kind of limit** from
  the regulation floor above, and the one that actually binds in practice. The 3.80 V and
  4.40 V threshold columns carry the *most* target signal in the grid, so they cannot be worked
  around by ignoring them. Four numbers, which are **not interchangeable** *(restated
  2026-07-31 — they had been used as if they were)*:
  - **≈ 24.0 V — always-bad edge.** Above it those two columns are unusable however long the
    rig has run.
  - **22.5 – 24.0 V — transition band.** Here soak time is a real second variable, worth
    ~2.5–3× against voltage's ~11× across its full range, so a well-soaked rig can read clean
    inside this band and a cold one need not. The v3 profile was locked at 23.5 → 23.35 V,
    i.e. *here* (§10).
  - **21.5 – 23.3 V — the operating window.** The conservative interior; state it for any
    capture campaign.
  - **≈ 21.5 V — lower edge.** Below it the trouble migrates to the 4.20 V and 4.75 V columns
    and the 9 µs band, so the window is bounded on both sides.

  "**≈ 23.5 V ceiling**" as used elsewhere in this document is shorthand for the transition's
  practical onset, not a fifth limit. The 21.0 V regulation floor needs no change — it was never
  the binding limit for data quality. **Caveat on the lower edge** *(2026-07-31)*: "below
  22.5 V the columns are always acceptable" is too strong — the one cold start measured near
  that edge (≈ 22.45 V) still read ~5× its own floor. Below ~22.5 V they are *usually* at the
  floor, but a cold rig there is not guaranteed clean.
- **Pack state of charge DOES reach the operating point** — **43–51 mV/V over 21–25 V**, one
  sign across all seven bands, r = 0.96–0.97 *(2026-07-30, §17.13)*. This **corrects the
  earlier reading.** §17.10 established the opposite across 23.60 → 23.05 V, and is not wrong
  about its own interval: over 0.55 V the effect predicts only ~25 mV, comfortably buried under
  the thermal drift that measurement was actually reading. Over the 4 V now available it is a
  160 mV effect and unmissable. **The result does not generalise beyond its measured span** —
  a standing caution for any regulated-window claim taken over a narrow interval.
- **Capacity and drain, pack A** *(one full discharge, 21 settled readings, §17.13)*:
  **620 streaming-min (10.33 h) full to empty** at the §17.1 measured ~0.5 A average, implying
  **≈ 5.2 Ah** — about the rated capacity of a 6S2P ICR18650-26C pack, so a pack built from
  recovered laptop cells is behaving at its rating. Split by the window above:

  | | streaming hours | share of pack |
  |---|---|---|
  | full → 23.3 V — unusable, above the data-quality ceiling | 1.78 h | 17 % |
  | **23.3 → 21.5 V — the clean window** | **4.55 h** | **44 %** |
  | 21.5 V → empty — below the window | 4.0 h | 39 % |

  **4.55 h is the session-planning number.** Just under half the pack is usable for profiling,
  and it is the middle half. Runtime is cross-checked two ways that do not depend on the fitted
  curve's absolute placement (leave-one-out holds it to 1.7 %; an independent interval
  measurement agrees to 3.5 %) — **trust the runtime, not the curve's voltage axis**, which is
  an alignment of a nominal OCV shape rather than a measured one. The terminal knee below
  21.08 V is extrapolated, not observed.
- **Idle drain 0.019 V/h against 0.28–0.34 V/h streaming — roughly 15×.** The operational
  consequence: **a fresh pack cannot be idled into the window.** At 0.019 V/h the top 1.4 V
  would take three days, so the 1.78 h above is unavoidable *bench* time rather than a wait
  that can be scheduled around. Do not start a profiling session on a freshly-charged pack.
- **Measured IR drop is ~0.29 V at the terminals**, not the ~0.95 V a two-parameter discharge
  fit initially attributed to it: pack B reads 25.04 V no-load / 24.96 MCU-only / **24.75 V
  running**. Recorded because the fit's error was silent — a physically-named fitted parameter
  will take a confident value whether or not the name is right, and the residual does not
  complain (§17.13).
- **Not yet measured, and now the highest-value measurement on the project:** the +15 V rail
  under scope *during a TX pulse*, fresh pack vs near-flat. A depleted pack's internal
  resistance may sag the rail at the pulse instant in a way a DMM on the pack cannot show. The
  2026-07-30 result *infers* a supply mechanism from its band signature; this capture would
  observe it directly, and it is the only way to settle whether the residual pack-to-pack
  difference is internal resistance. **There is no voltage-sense and no temperature-sense
  hardware on the board** (6.04 schematic: no divider, no thermistor, GP26–29 unconnected), so
  **no amount of logging substitutes for it** — the whole supply-vs-thermal separation achieved
  so far rests on band *geometry*, because the two channels that would have shown it outright
  do not exist.

**Known supply-noise facts** *(measured, free-air, 10-sample σ; **5S/pre-enclosure**, not yet
re-measured on 6S — §14.3):* ~200 µV USB / no flash · ~250 µV battery / no flash ·
~900 µV USB / using flash · ~4000 µV battery / using flash.  Writing to
flash raises the noise floor ~10×.

---

## 13. What makes this design unusual (deliberate, validated choices)

- Sampling the **0.5 V – 4.9 V** band of the flyback decay rather than the usual bottom ~700 mV —
  found to carry more discrimination information and sit well above the noise floor. The
  early-decay top of that range (4.7–4.9 V) is sampled densely, avoiding only the measured
  ~4.45–4.65 V noise zone — see §10. *(The third step moved 4.70 → 4.75 V at the v3 lock, and
  the top of the ladder is where the `(9 µs, 4.9 V)` corner lives — §14.11.)*
- **The threshold ladder is a fixed set of voltages sampling a decay whose scale moves with the
  pack.** This is the cost of amplitude-anchored delays, and it was not anticipated: which
  threshold columns land in a bad region of the decay is a function of state of charge, so
  "which cells are good" is not a static property of a profile (§12, §14.7, §14.11).
- **Geometric pulse ladder (×1.5) + top-dense amplitude thresholds** — every band
  interrogates a distinct, evenly spaced slice of log target-τ; the threshold ladder is
  densest where the decay carries the most information (§10). Amplitude-anchored delays
  make the matrix self-normalising across bands. *(The feature-portability worry this raised
  across a threshold-geometry change is now measured and benign — the v2→v3 shift is coherent
  and one-parameter, and no target changed family. §10, §17.14.)*
- **The signature is a two-basis object, and that is now measured rather than assumed.** Each
  target's orientation set is **rank 2** — one axial and one transverse basis shape — and an
  oblique pose is a positive convex combination of them landing on the arc between, with weights
  on the dipole prediction `cos²θ / sin²θ`. So the 63-cell matrix carries enough structure to
  *solve for* orientation instead of being confounded by it, and an orientation-invariant
  descriptor is the 2-D subspace rather than any signature in it (§17.14, §14.9).

---

## 14. Open problems

1. **Thermal drift.** Wider pulses heat the TX damping/gate resistors; the drive circuit
   drifts and the sensitive RX side drifts with it. *(Pre-enclosure numbers — re-measure,
   the enclosure may have changed thermal behaviour.)* Post-enclosure signature (§17.8,
   2026-07-14): heavy bands drift −20…−31 mV below their calibrated operating point,
   monotonic with pulse width; light bands ≈ +9 mV high; warm recalibration moves delays
   −56…+16 ns. Mitigation: calibrate fully soaked (cal_63_air_v2).
   **Signature survives the 6S supply change and warm-up is longer** *(2026-07-24, §17.10)*:
   two cals 37 min apart reproduce the same fingerprint (light bands later, heavy bands
   progressively earlier, −96…+16 ns, r = −0.95 against log pulse width), still converging,
   consistent with roughly doubled 7815 dissipation (§12).
   **Scope correction (2026-07-30, §17.13): the "≈ 3 h warm-up" was mostly pack discharge, not
   thermal soak.** The two were perfectly confounded in every session before 2026-07-30 — the
   pack drains into the clean window over roughly the same ~2 h — which is why they looked
   interchangeable. Thermal drift **remains a genuine open problem** and its fingerprint is
   independently confirmed (a thermal shift moves light and heavy bands in *opposite*
   directions, r = +0.99 across bands; a supply shift moves all seven the same way — that sign
   test is what separates them). It is simply **the smaller of the two effects**, and it is not
   what the 3.80/4.40 V columns were showing. Inside the 22.5–24.0 V transition band soak is
   visible as a real secondary variable worth ~2.5–3×, against ~11× for voltage across its range.
   **Practical consequence — reference age is a hard ceiling on any frozen-reference
   measurement.** At ~50 µV/s an air reference accumulates 0.5 mV/cell at 10 s, 3.0 mV at
   60 s, 7.5 mV at 150 s — so a reference older than ~10 s already rivals a weak target, and
   one minute exceeds a strong target at close range. Removing a target can make |Δ| go *up*
   (§17.10). Any procedure that does not bracket air on both sides is unreliable beyond ~10 s;
   this is the quantitative justification for the air-bracketed Training cycle (§17.5).
   **Independently confirmed offline** *(2026-07-31, §15 `session_relabel`)*: matching plateaus
   in the raw dumps against corpus signatures, a single earlier air reference carries the full
   drift to the capture — tens of mV over a ~400 s plateau gap — and cost ~0.05 of cosine, while
   **interpolating between a reference before and one after** took the correct pairings to
   0.996–1.000. Bracketing is not just good practice; without it the drift is large enough to
   degrade target *identity*, not merely amplitude.
2. **7805-vs-USB supply-noise mystery.** Onboard 7805 path ~50 % noisier than USB;
   unresolved. *(Re-measure post-enclosure — shielding may have changed the picture.)*
3. **General supply noise floor** (battery vs USB, flash penalty — partially mitigated).
   *(Re-measure post-enclosure — and now also post-6S: the §12 table is 5S/pre-enclosure on
   both counts, so the battery rows are doubly stale.)*
   **Partially answered on battery** *(2026-07-28, §17.12)*: the capture-level `splithalf_floor`
   sits at **~0.9 mV** and is unchanged across a 1.27 V discharge *and* across a pack swap —
   both nulls. Free-air wander over one settle window reads **0.2–0.3 mV steady** at the v3
   operating point, ~2× better than the ~0.8 mV predicted from the §17.2 50 µV/s drift rate,
   so either the settle window is shorter than assumed or drift at this operating point is
   below the (pre-enclosure) §17.2 figure — not separated. The soaked per-cell floor is a
   near-uniform **70–130 ps** of equivalent timing jitter expressed as slope × time across most
   of the grid; the exceptions are the top thresholds and the 9 µs / 100 µs bands at
   260–400 ps, consistent with §14.11 being a separate mechanism. Still outstanding: the
   USB-vs-battery and flash-penalty rows of the §12 table.
4. **Q1 duty headroom.** Present operating points run well above the schematic's < 2 % FET
   duty note (see §17) — Q1 (IRF610) is being pushed past its noted SOA; a higher-rated
   replacement FET is probably warranted.
5. **Coil mechanical stability** — largely solved (epoxy + Perspex).
6. **Possible TX coil-current plateau above ~67 µs.** In every calibration of the geometric
   ladder, the 67.2 → 100 µs band-to-band clip-release increment is the smallest on the
   ladder — consistent with coil current flattening (τ_coil = L/R never measured). Needs a
   scope on coil current vs pulse width. Bears on whether the 100 µs band justifies its
   ~32 % share of frame time and its thermal cost — though target data (§17.6, historical)
   showed band 8 still carrying real long-τ information.
7. **Threshold noise zone ~4.45–4.65 V — mechanism unknown.** A fine threshold sweep
   (4.700 → 4.400 V, 37.5 mV steps) shows column σ elevated across roughly 4.45–4.65 V in
   nearly every band (up to ~2.2 mV) while both ends are clean (§17.7). Values above
   (4.7–4.9) and below (≤ 4.4) behave normally, so the zone is excluded from target lists
   (§10) — but why that band of the decay is noisy is not understood. 2026-07-14 (§17.8):
   the zone's **upper edge is sharp and sits near ≈ 4.67 V** on the 100 µs band — a
   4 mV operating-point shift (4.673 → 4.669 V) took the event rate 1 → 10 per session.
   Events are quantized two-state (single samples of ±64 mV), suggesting a discrete
   (ringing-phase-like) mechanism, not broadband. Follow-ups: fine-map 4.65–4.70 V on the
   heavy bands; if the edge crowds 4.70 V warm, move the third threshold up (e.g. 4.75 V)
   in the next profile rev. Watch item: ch9 (13.44 µs band, first cell) shows ~6 small
   quantized events per session — band-head related, minor.
   **The zone tracks the operating point, not a fixed voltage** *(2026-07-24, §17.10)*: on
   the 6S pack at 22.4 V under `cal_63_air_v2`, the **4.40 V and 3.80 V columns** were
   elevated across all seven bands at ~5× the free-air floor. The defect followed the
   *threshold* axis, not the band axis — bands share the ladder but sample it at different
   delays and pulse energies, so a fault tracking the voltage label localises the mechanism
   to the voltage domain (front end / 1N4732 clamp / preamp) rather than to timing or drive
   energy.
   **Mechanism resolved 2026-07-30 (§17.13); the geometry is not.** The noisy region sits at a
   **fixed place on the decay waveform** while pack voltage **scales the decay**, so which
   threshold columns intersect it moves with the pack. That single statement accounts for both
   things previously recorded as unresolved: the zone "tracking the operating point" is the pack
   moving it, and **noisy–clean–noisy is not a contradiction** — a zone crossing a fixed
   threshold ladder produces exactly that, with 4.20 V clean between two bad columns. Direct
   evidence: at 21.08 V the trouble has *left* 3.80/4.40 V (189/189 µV) and appeared at
   **4.20 V (457 µV)** and 4.75 V (295 µV) — the operator's own observation that "the noise just
   changes area". Also disposes of the 1N4732 objection: 3.80 V never needed the clamp to be
   participating. The per-band pattern is zone-like rather than uniform (on a fresh pack the
   3.80 V degradation peaks in the middle bands, 19× at 20–45 µs, and is weakest at 9 µs and
   100 µs), consistent with each band having a differently-shaped decay so the zone lands on a
   different threshold in each.
   **Independently re-measured 2026-07-31** by a drift-immune estimator (successive-frame
   differences, so a warm-up slope cannot masquerade as noise): on a fresh pack the 3.80/4.40 V
   columns read 749/277 µV against 83 µV at 4.20 V between them, the whole grid sits at one
   57–72 µV floor mid-window, and at 21.08 V the trouble has left 3.80/4.40 V (64/70 µV) and
   appeared at 4.20 V (173 µV). The migration is confirmed on the raw dumps, not only inferred.
   **Seen a third time, in target-free data** *(2026-07-31, §17.14)*: per-cell σ over the v3
   corpus's own 19 air captures puts **46 % of all noise energy in the 3.80 V column alone**
   (column L2 2.85 mV against 0.37–1.48 for the other eight), and that excess is **entirely
   confined to the fresh-pack and cold-start captures** — 24.40 V reads 5.55 mV on that column,
   23.69 V reads 4.39, the cold pair 4.85/6.15, while every settled capture inside the
   21.1–23.4 V window reads 0.64–2.06. Air captures at 23.36 V *after* a long soak read clean
   (0.64, 1.56), consistent with the transition band being soak-sensitive rather than
   voltage-fatal. **The 46 % is therefore a pack-state artefact that operator discipline already
   removes, not a property of the profile** — which is worth stating plainly, because a naive
   read of the corpus noise census would condemn the column.
   **Unresolved tension, flagged rather than resolved:** the 2026-07-24 survey above found the
   columns elevated **at 22.4 V**, which the 07-30 rule would call clean. That survey ran
   `cal_63_air_v2`, whose delays are 40–144 ns *earlier* than v3's. Since the zone sits at a
   fixed place on the decay and each profile's delays cut the decay at different points, the
   clean window may belong to **(pack voltage × profile delays)** rather than to pack voltage
   alone — which would reconcile the two readings. This is a hypothesis, not a result: no
   v2-era session dumps exist to test it (auto-logging begins 07-29).
   **What is still open:** the zone's actual position and width *on the decay*, and its physical
   cause. Both listed follow-ups stand — fine threshold sweep (§17.7 method) and a scope on the
   front end — but they must now be specified **at a stated pack voltage** or they will not
   reproduce. Best single experiment: repeat the §17.7 fine sweep at **two** stated voltages
   (say 24.5 and 22.0 V) **and under both v2's and v3's delay sets**, which maps the zone's
   position directly, tests the per-profile hypothesis above, and would turn the present
   inference into a model. A related open question the logs cannot answer: **does the noise
   follow the DELAY or the THRESHOLD?** A fine delay sweep at the 3.80/4.40 cells separates
   those. Note the ~4.45–4.65 V keep-out zone (§17.7) and the `(9 µs, 4.9 V)` corner (§14.11)
   are separate observations and are not explained by this.
8. **Post-enclosure re-measurement backlog.** Noise floors, drift rates, the settled
   top-of-decay level (~4.87–4.89 V observed on heavy bands — bears on the delaycal
   signal-detect ceiling, now 5.0 V), and the §17.4 delay-zone map all predate the
   enclosure and need redoing on the new hardware state.
9. **Classification layer: the early-band axis is an orientation coordinate, and tier 2 needs
   re-scoping rather than a better threshold.** *(Substantially revised 2026-07-31 against the
   v3 corpus, §17.14.)* This was recorded as a **noise** problem — solid ferrous sitting
   knife-edge on the family plane's early-band axis, losing its sign as SNR falls (§17.9's
   directional misclassifications; `Fe_spanner_01` measured flipping ferrous → crossover on an
   early-band mean of just **+0.045 mV**, §17.10). That much is real and still stands. But it is
   the second-order effect. The **first**-order effect is that the axis is not measuring what the
   family names claim:

   | orientation | ferrous-vs-crossover accuracy (gated) |
   |---|---|
   | ax = y (transverse) | 90.9 % (n = 22) |
   | ax = x (transverse) | 75.0 % (n = 16) |
   | ax = z (**axial**) | **53.8 %** (n = 13) — chance |

   **Every crossover→ferrous miss in the corpus is an axial capture.** The early axis measures
   **presented eddy-loop area = geometry × orientation**, so the same object changes family as it
   is tipped: `Fe_Cast_iron_trivet_01` lying flat reads `crossover` (crossing 29–36 µs, early
   −50…−102 ×10⁻³); stood on edge it reads `ferrous` (crossing pinned at the 8 µs rail, early
   +7…+47) and is 2.4× louder. That is what a 3 mm-thick 75 mm disc must do — face-on the eddy
   loop has the full 75 mm of area and the fast negative term dominates the early bands; edge-on
   the loop area collapses to the 3 mm thickness and the magnetic term is left exposed. The
   spanner fails the other way, reading `crossover` broadside. Decay persistence does **not**
   rescue the split (ferrous median 4.20, crossover 4.82, fully overlapping).

   **Consequences, in order.** (a) A noise-scaled dead band around zero is still worth having and
   works as anticipated — 1.5σ → 90.7 % on 92 % decided, 3σ → 95.7 % on 80 % decided — but it is
   a **coverage trade, not a fix**, because the misses are *physical* rather than marginal. A
   live cursor should still show the band rather than assert a family. (b) The tier should be
   **renamed and re-scoped** to what it measures; "ferrous vs crossover" is a material-sounding
   name for an orientation reading. (c) The real path forward is §17.14's two-basis result:
   with a target's axial and transverse basis shapes, orientation is *solvable* and the
   orientation-invariant descriptor is the 2-D subspace itself. (d) **Tier 1 — the late-band
   sign, iron-bearing vs non-ferrous — is the robust axis** at 97.2 % ungated / 98.3 % gated,
   and does not need the gate at all. Build on that.

   **Do not read §17.9's 97.8 % / §17.12's 100 % gated three-class figures as a regression
   against v3's 88.1 %.** The v1 corpus held **no axial captures of any crossover target** — it
   sampled only the orientation where the early sign happens to work. The v3 corpus is 2.6×
   larger and deliberately spans orientation, so it exposes a failure mode the earlier number
   could not see.
10. **The host can block the MCU, and did — for 47 minutes.** *(2026-07-29, §17.13.)* The Mode 2
    emit is a blocking `print()` to USB CDC (§8); when the host stopped draining the pipe the MCU
    stalled inside it and frame delivery collapsed from **414 per minute to ~20–35** *(the
    recorded figures do not close: ~35/min over 47 min cannot coexist with the 2 700 s of dead
    time counted in the same 2 820 s window, which leaves only ~120 s live ⇒ ~18/min. The 2 700 s
    is corroborated twice; the rate is the soft number.)* It is not merely lost data — **the rig
    cooled**, because the PWM free-runs at cell[0]'s config during the print, so a long stall
    parks the detector on one band's duty instead of sweeping seven. The operating point stepped
    **−8.3 mV (9 µs) to +23.8 mV (100 µs)** — changing sign across the ladder, the thermal
    signature (§17.13). *(Corrected 2026-07-31: this read "+10 mV (9 µs) to +78 mV (100 µs)",
    one sign across all bands. That was the first pass through this dump — the same pass whose
    stall-spanning windows manufactured the phantom "noise relapse" below. The sign-changing row
    is from the stall-guard-cleaned re-analysis and is the only version consistent with the
    supply-vs-thermal discriminator this document relies on.)* Likely trigger, not
    established: the PC suspending or starving the Qt event loop. **Detection landed, the fix did
    not** — fw v4.27 counts blocked emits (§8, §9), classviz v1.64 latches a stall warning and
    writes `# stall:` lines into the session dump, and the window-span guard now fails safe to
    "not settled" rather than reading accumulated drift as noise. Making the emit non-blocking is
    deliberately deferred pending bench proof (§8). Open until the counters show whether it
    recurs. Two lessons recorded: it went unnoticed **live** because the Rate readout self-clears,
    and unnoticed **in analysis** because a fixed-frame window silently becomes a longer *time*
    window during a stall — which manufactured a phantom "noise relapse" that does not exist.
11. **The `(9 µs, 4.9 V)` corner — 3 cells of 63, and it cannot be fixed statically.**
    *(2026-07-28, §17.12.)* Noise/signal at `(9 µs, 4.9 V)` and `(9 µs, 4.8 V)` runs **3–10×
    above every other cell**; `(13.44 µs, 4.9 V)` is implicated only marginally — it reads about
    **1.2×** the best of the rest, so the "3–10×" applies to two cells, not three *(scoped
    2026-07-31)*. Together 4.8 % of the grid, the **top of the
    ladder meeting the shortest band**, and a *separate* observation from both §14.7 and the
    ~4.45–4.65 V keep-out zone. Because `splithalf_floor` is an L2 over all 63 cells, that corner
    sets the noise figure for the whole capture, which is why it presents as a floor problem.
    Excluding just those 3 cells cuts the paired-difference L2 by **29 % median / 32 % mean**.
    **Decision: keep profiling, change nothing yet** — the benefit is available at *analysis*
    time and is reversible, where a profile change mints a new `profile_sha8` and needs a fresh
    sweep and lock. Two constraints on any eventual fix: dropping the band and the column would
    discard 15 cells to fix 3 and take the early-band discrimination §14.9 depends on with it;
    and a **static** cell exclusion cannot work at all, because §14.7 establishes that which
    cells are bad is a function of pack state. Any exclusion has to be dynamic and stated
    against a pack voltage. **Warning against the obvious analysis**: averaging down the column
    and across the band gives 4.9 V = 0.93 and 9 µs = 0.94, which reads as two bad lines and
    argues for deleting a band and a threshold — both averages are dragged up by the single cell
    at their intersection, and neither line is bad. Open sub-question: is 4.9 V simply
    unreachable for a 9 µs flyback (the crossing landing at or past the clamp, making the sample
    time ill-defined), in which case the ladder's top step is the thing to reconsider, not the
    band?
    **Scoped 2026-07-31 (§17.14): the corner is not the dominant floor feature.** Per-cell σ over
    the corpus's 19 air captures puts **46 % of all noise energy in the 3.80 V column** and only
    **7 % in the three corner cells**. The two findings are not in conflict — the 07-28 corner
    came from matched target pairs within one afternoon, while this is across-capture σ spanning
    the whole campaign, and the 3.80 V excess is a pack-state artefact (§14.7). But it does
    reorder the priority: **the corner is a genuine but second-rank floor contributor**, and the
    29 %/32 % paired-difference improvement from excluding it should be read against a floor whose
    largest single term is something operator discipline already removes.
12. **The Std Dev displays showed known artefacts as noise — FIXED, classviz v1.69
    (2026-07-31).** *(Raised at §17.15.)* The Std Dev heatmap was the only heatmap mode
    **bypassing both the 64-frame glitch substitution and the v1.64 window-span stall guard**, so
    a glitch rendered as noise and post-stall accumulated drift rendered as noise — in the one
    display an operator uses specifically to judge the noise floor, and the one the standing
    protocol says to read before every target. **The Stats table's Mean/Std columns had the same
    two defects** and were fixed with it: those two agreeing for the same N is a stated property,
    so they now share a single computation and cannot drift apart again. Display path only — no
    recorded data was ever affected. Refusal is now **visible** rather than silent (the scale
    label reads `STALLED <n> s window — not reduced`, the table shows `—` with neutral
    colouring), because drawing a stalled stream as a *quiet* grid is the same bug inverted.
    **Measured before/after on the real dumps:** replaying the 07-29 stall, 61 of 4 079 sampled
    windows are now refused that the old path reduced — worst case a window spanning **101 s
    (14× nominal) from which the old path drew mean σ of 1 716 µV**, i.e. drift drawn as noise at
    a magnitude squarely inside the range this display exists to detect. A healthy 89 692-frame
    dump refuses nothing. The **glitch half is defensive**: across all 12 dumps (373 k+ frames)
    there are **zero mid-run glitch frames** (every flag sits in the first 64, the buffer's own
    fill period), so it is verified by injection instead — one 600 mV artifact takes the old path
    to 334× the floor and the new path to 1.00×.
13. **Neither quality gate catches a rogue capture, and a within-placement check would.**
    *(2026-07-31, §17.14.)* `Fe_Cast_iron_trivet_01` @ 120 mm, ax = x, r1 is stamped `ok` at
    **SNR 16.5** and passes everything, while sitting at cosine 0.33–0.68 to every other trivet
    capture *including its own r2 sibling at 0.577* (persistence 1.15 against 2.6–4.4; late-band
    mean +70 against +116…+155). One capture single-handedly sets the corpus's worst within-target
    cross-distance cosine (0.591 against a 0.985 median) and inflates the trivet's noise reference
    from ~0.13 to 0.320. Air-reference staleness is the leading suspect (§14.1) but **the corpus
    carries no air age**, so it cannot be settled from the file. Two things follow: add a
    **within-placement consistency check between repeats** to `pimd_corpus_check`, and consider
    recording air-reference age as a corpus column so this class of defect is diagnosable
    afterwards rather than only detectable.
14. **`Sn_Pb_solder_spool_01` is two physical objects under one `target_id`, and the second one
    is a tier-1 false-positive mode.** *(2026-07-31, §17.14.)* `targets_v3.csv`'s own header
    records "changed solder roll", and the data agrees emphatically — cross-epoch cosine of the
    mean shapes is **+0.143**, against ≥ 0.95 for every other matched target. **All cross-epoch
    comparison for this id is invalid until it is split**; since the registry's own rule is that
    an id is never reused, the new object needs its own id with the v1 captures left pointing at
    the old one. That is an operator decision, not a tooling one. The physics is the more
    interesting half: the new roll is **not magnetic** (operator-verified, so the registry row is
    correct and an earlier "steel spool core" speculation is withdrawn), yet broadside it reads
    ferrous on *both* tier-1 discriminators — late +178 ×10⁻³, decay persistence 4.28–5.70,
    crossing pinned at the 8 µs rail — while end-on it reads non-ferrous (1.07–1.20). The
    surviving explanation is a **shorted multi-turn coil**: a spool whose wire ends touch is a
    closed loop of high inductance and very low resistance, i.e. a long L/R time constant, and a
    slowly-decaying induced current is indistinguishable from ferrous by both sign and decay. It
    is the one non-ferrous target in the corpus that breaks the 97.2 % late-sign rule, and **a
    shorted loop is a shape a real buried target can take**. *Flagged, not asserted* — the corpus
    cannot settle it. The decisive test takes seconds: **a continuity measurement across the
    spool's two wire ends.**
15. **Both offline acceptance gates fail on the current corpus, and neither failure is a
    regression.** *(2026-07-31. Pre-existing; found while regression-testing the v1.69 fixes and
    confirmed identical with those changes stashed.)* This needs an operator decision, which is
    why it is here rather than silently fixed.
    - **`pimd_shape.py --selftest` reads FAIL (46 problems)** against the v3 corpus and **PASS**
      against v1. Its expectations are hard-coded from the 2026-07-23 `cal_63_air_v2` analysis,
      and **38 of the 46 are item 3, the crossing ladder** — precisely the quantity §17.14 has
      just shown to be **per-epoch** (`Fe_SS_disc_01` @60 reads 18.59 µs against a hard-coded
      30.6 ± 1.5). The test is not detecting a fault; it is correctly reporting that it was
      pointed at a corpus from a different epoch than its expectations. Item 4's two failures are
      the §14.13 rogue capture. **§16's documented command has therefore been wrong since the
      registry moved to v3.** Three fixes, none obviously right: point §16 back at the v1 corpus
      (honest, but then the check never exercises the live epoch); re-derive the expectations
      against v3 (exercises the live epoch, but bakes in the rogue capture unless it is excluded
      first); or make the expectations epoch-parameterised. **Decide before the next capture day
      leans on this as a gate** — a gate that always fails is a gate nobody reads.
    - **`pimd_corpus_check` reads 411 checks: 181 PASS, 229 FAIL** on the v3 corpus (101
      `splithalf-snr`, 95 `repeat-consistency`, 24 `shape-invariance`, 9 `distance-falloff`).
      **Not diagnosed** — consistent in kind with §17.14's own measurements (the SNR ≥ 5 gate
      really being a reproducibility gate of ≈ 2.5–3.5, §14.13's rogue capture, §14.14's solder
      spool), but the count is high enough to deserve its own look rather than an assumption.

---

## 15. Repository / file inventory

| File | Role |
|------|------|
| `mcu/pimd_mcu.py` | RP2040 MicroPython firmware (**v4.27**) — both modes, all profiles; BUSY edge sync (v4.19); IRQ critical section + 10 % plausibility gate on raw reads (v4.21); SAMPLE_PULSE_CORRECTION 0.904 µs (v4.22); protocol: freq in Hz, pulse/delay in ns (v4.23); time-floored Mode 2 boundary settling, SETTLE_FLOOR_US 3000 (v4.24); outlier gate on abs(mean) with OUTLIER_GATE_MIN floor — no more latched cells (v4.25); IRQ hold through freq/CC writes via `read_raw_bytes_hold()` — CC-write race closed (v4.26); **emit-block counters on `B`** (v4.27) — diagnostic only, the emit path and all PWM/CC sequencing untouched, for the host-stall defect §14.10 |
| `mcu/main.py` | One-line board launcher: `import pimd_mcu` |
| `src/pimd_gui.py` | PC PyQt6 GUI **v4.13** — Mode 1 filtered telemetry display; boxcar toggle; 8 ns grid snapping with orange-highlight warnings; no auto-connect; sub-200 µV V/div removed; settings persistence |
| `src/pimd_classviz.py` | PC PyQt6 Mode 2 signature visualiser (**v1.69**) — real-time heatmap + stats table + 64-frame glitch filter; top-bar saved-profile **Load & Run** (sends RAM-only dynamic profile via `D`, replaces the old Profile Builder tab — profile authoring lives in delaycal); session-dump recorder (self-describing per-session CSV to `src/data/sessions/`, embedded profile JSON + per-column map + marks); **Std Dev (rolling N) heatmap mode** (live noise monitor); settledness-gated, glitch-excluding signature captures (v1.31); **registry-backed structured target-metadata capture** — target combo + placement fields from `pimd_target_check.py`, `# mark_target:` session-dump lines, capture provenance (profile_sha8 / fw_version / supply), corpus CSVs to `src/data/corpora/` (v1.32); settings persistence. **Four tabs: Heatmap / Stats / Analysis / Family Plane Analysis** (the fourth was named **Shape Space** before v1.43; internal names stay `shape`/`_shape_*` and `pimd_shape.py` is unchanged — §17.9 and older §15/USAGE text describing "Shape Space" mean this tab) — the Analysis tab is the sole corpus-capture workbench (live comparison charts, decoupled heatmap + colorbar range control, per-group normalize/scale) and carries the **automated Training cycle** (v1.34–v1.35: one Space press per cycle, auto place/remove detection, 30 s guard countdowns, Save/Ignore) plus capture ergonomics (v1.38: splitter-resizable heatmap vs signature list, new captures auto-checked onto the charts, black live traces, per-parameter green/amber/red quality colouring against editable thresholds). The separate guided **Training Session tab was removed at v1.39** — all corpus capture goes through Analysis. **Shape Space (v1.42)** plots every loaded signature as a point in a selectable 2-D feature space with the live frame moving through it — five movable/floatable docks (Scatter, Band Curves, Crossing Ladder, Tile Inspector, Gauges), all feature maths from `pimd_shape.py`. It is the one place in the app that plots **mixed profile geometries** together, and marks every foreign capture on sight (marker shape, standing banner, tooltip, tile title) because they are comparable in kind but not calibrated against each other; the Analysis tab's raw cell-by-cell overlays still refuse. Carries its **own two-mode rolling air reference** (air / measure, Space toggles) rather than the shared static baseline — a frozen baseline made the tab meaningless under drift (§14.1) — and **scratch captures** of unregistered objects to `src/data/scratch/`, never to `src/data/corpora/`. **v1.43–v1.66 in four groups.** *(a) Session provenance — the group the 2026-07-30 result rests on:* dumps now **auto-log with the stream** (v1.63, default on, so the warm-up window nobody presses Record for is captured; an explicit Stop stays stopped only until the next start); a **pack-voltage track** written as `# pack_v: <iso>, <volts>, age_s=<n>` on a `Log V` press, where *age* is seconds since the value was last **typed**, so a restored spinbox reports `age_s=unknown` rather than a confident lie (v1.64, v1.66); **`# soak:` run-history lines** carrying `streamed_s` / `stalled_s` / `idle_before_s` (v1.66 — note `streamed_s` banks per process, not across restarts, and `idle_before_s` is classviz-observed idle, **not** guaranteed rig idle). *(b) Stall safety (§14.10):* a **window span guard** — all four window reductions go through `_window_frames()` and return `None` when the window spans > 3× its expected duration, so a stall fails safe to "not settled" instead of to a plausible number; span is measured on the **firmware clock**, never on PC arrival time, which is burst-batched (median arrival interval 0.0035 s against a uniform 0.1440 s — the two share a *mean*, which is the trap); plus ingest-side gap detection writing `# stall:` lines with a latched Rate warning, and a per-chart draw **Pause** (v1.64, draw only — never "don't record"). *(c) Live gates made visible:* the Analysis **Trigger Levels** gauge column, thresholds draggable (v1.51); a stale-air-reference fix — the Detect gauge was showing an ageing frozen reference as a live deviation (v1.52, with a new **Air age** gauge); **launch auto-start** (v1.53); removal auto-detect reworked to require a settle-loss *transient* **and** departure from a fresh target snapshot, because §17.10 proves no magnitude test against a frozen reference can detect removal (v1.54–v1.55); Training A/B labels that name the gate holding each phase up (v1.56); live **central-frame count** with Frames default 60 → **100**, since 60 trims to 36 central and was stamping every default capture `short` (v1.57). *(d) Capture schema and the Family Plane:* the unused `face_normal` / offset X / offset Y inputs removed while the **schema keeps all eight keys** as `na`/0/0 so the checker's placement tuple is unbroken (v1.60); signature rows carry long axis + repeat and colour is per **target** via `zlib.crc32` — not the salted builtin `hash()` (v1.61); `repeat_idx` no longer sticks at r1 (v1.62); corpus append writes **the file's own header columns**, not the tool's, so adding a column can never again produce a ragged CSV (v1.65). Family Plane: renamed, material tags, per-axis custom bands, clickable ladder (v1.43); explicit Min/Max heatmap scale (v1.44); the colorbar rebuilt as a true absolute range slider (v1.45); scratch saves plot immediately as triangles (v1.46); per-axis **Scale** curves — cube / atanh / rank, all range-preserving, with a log axis deliberately **not** offered because nothing lives near zero (v1.47); no gridlines on a rank axis and zero rails that follow the spacing curve (v1.48); custom band pair no longer lost to startup-profile clamping (v1.49); below-gate frames leave no trail at all (v1.50). **v1.67–v1.68 — orientation capture, and the dumps stop being unlabelled.** *(v1.67)* A **Tilt (°)** spinbox (0–90, step 5) in the Analysis placement row: `long_axis` can only express 0° or 90° to the coil axis, so every capture in every corpus on disk sat at one of the two extremes and the two-basis model's actual content could not be tested (§17.14). Enabled only when **Long axis is `z`** *and* a signature file is open — a tilt is defined against the coil normal, so `_placement_from_widgets()` is the single place the rule lives and emits `''` for x/y, meaning a 30° left over from an oblique run cannot reach an x/y row. **Deliberately not persisted to settings** (reopens at 0 every launch): a persisted placement combo riding silently along on every later capture is exactly what got `face_normal` removed at v1.60. `tilt_deg` joins the placement tuple, so Repeat # re-wires to the spinbox — otherwise a 30° capture inherits the 0° count and the two poses collide as repeats of one placement. *(v1.68)* **Saving a signature now marks the dump.** `_append_mark()`/`_append_mark_target()` had existed since v1.32 but were only ever called from the manual Mark button, which nobody pressed — so all eleven dumps then on disk carried **zero `# mark:` lines**: ~380 000 frames of raw per-cell data with the ground truth sitting in a separate CSV and no key between them. `_on_sig_save_clicked()` now stamps the running dump with the same `placement` dict the corpus row was built from. **The new `# capture:` line is the part that matters** — a mark says *what* was in the field, not *which frames*, and the two were not recoverable from each other (the corpus `session` id and the dump filename are independent stamps, and `captured_at` is stamped at **save** time, tens of seconds after the frames). `_append_capture()` writes `capture_id`, the corpus `session` id, `n_central` and the target / air-before / air-after windows as epoch seconds, taken **straight off the capture buffers** rather than re-derived, on the same PC clock that stamps every frame's `pc_wallclock` — so the join is exact and lossless. Guarding is in the caller by necessity and the write is wrapped: the corpus row is the product and is already on disk, so a dump-annotation failure reports to the status bar rather than taking the capture down. **v1.69 — the two Std Dev bypasses closed (§14.12).** A new `_rolling_disp_buf` carries the glitch-substituted frames, appended in lockstep with `_rolling_buf` / `_fw_ms_buf` and with the same maxlen so index `-k` aligns across all three — the parallel-deque pattern v1.64 introduced, kept for the same reason: `_rolling_buf` must go on holding *unfiltered* raw, because the session dump and the capture path read it and a recording has to stay faithful. `_get_current_baseline()`'s rolling mode is deliberately left on the raw buffer (it reduces with a median, already immune). A single new `_stddev_window()` is the only place either display computes σ. `_window_frames()` gains **`record=False`**: the guard's side effect of publishing span/reason for the status line is ordering-sensitive, and the heatmap redraws on the 30 Hz timer *ahead* of the gauges, so a recording call from it would have described the heatmap's window underneath the gauges' number — all four pre-existing callers keep the default and are unaffected |
| `src/pimd_delaycal.py` | PC PyQt6 delay-calibration sweeper (**v1.30**). Coarse+fine two-phase sweep per freq/pulse pair via `*`+`A<n>`; records threshold-crossing delays (clip-release / earliest-valid-sample); 3-d.p. voltage headers; profile export/import; thermal monitoring; zigzag auto-nudge (parallel or sequential) with ceiling latch + lock-on-pass; activity log; settings persistence. **v1.26–v1.29:** fine sweep step is now set in **ns down to the 8 ns PWM grid** (was a µs spinbox with a 10 ns floor — off-grid and unable to reach one step; a stored `step_size` in µs migrates ×1000); **THERMAL auto-starts on sweep completion** (v1.27), which also means every fresh profile arrives measured; a **Compare Profiles tab** (v1.28) answering the question that actually matters after a re-sweep — for every cell two profiles share, how far apart are the delays and does that gap move the measured voltage — matching cells on `(freq_hz, pulse_us, threshold_v)` so every row is like-for-like at the same intended target voltage, Δ coloured against the 8 ns grid, with a `<current calibration table>` entry so a sweep can be compared without exporting first; and **profile export via a save dialog whose basename becomes the profile's `name`** plus auto-generated `notes` recording the sweep that produced it (v1.29). That last one closed a real trap: exports were named after the sweep timestamp and `name` — **not** the filename — is what `pimd_features` records as `profile_name` in every corpus row and what the cross-epoch guard reports, so every lock needed correcting by hand (and `cal_63_air_bat_v3` did, §10). Imports carry the source profile's notes forward attributed, so derivation rationale survives an epoch change. **Operational note:** signal-detect ceiling must be 5.0 V post-enclosure (§3 epoch note). **Settings-persistence trap (2026-07-24):** the persisted `delaycal_settings.json` is *not* anchored to the currently locked profile, so an operator who edits two fields and presses run inherits a stale baseline for everything else — one recal run silently reintroduced the excluded 6 µs band and an 8-value threshold ladder, and looked plausible enough to nearly lock. Nothing in the export path enforces or flags a departure from the §10 band plan. Standard procedure is therefore **Import Profile first** (USAGE §4) — load the locked profile, edit, then sweep. Open: accept as procedure, or add a warning on band-plan/threshold-count mismatch. **v1.30 — the fine step is back on the 8 ns grid at all three entry points.** The spinbox had shipped a default of **100 ns**, 12.5 grid steps, reintroducing *as a default* the off-grid condition v1.26 existed to remove. The stepper cannot produce an off-grid value, but three other routes can, and one is how 100 got there: `_load_settings()`'s v1.25 migration multiplies a stored µs value by 1000, so a persisted `0.1 µs` lands on exactly 100 ns; typing works too; and an off-grid value then **persists itself on the next save**, which is how it survived v1.26. Now: `PWM_GRID_NS` / `FINE_STEP_DEFAULT_NS` constants (default **96 ns**, nearest on-grid to the old 100), and a `_snap_step_ns()` applied on settings restore *and* where the value becomes a sweep parameter. The snap rounds **down**, not to nearest — a fine step is a resolution promise, so 104 would sweep coarser than asked while 96 only costs an extra sample. **No effect on the current bench state:** the persisted `step_ns` is **40**, already on-grid and the value §10 records for the `cal_63_air_bat_v3` sweep; this only bit a fresh install or a cleared settings file |
| `src/pimd_shape.py` | Shared signature-geometry feature maths (**v1**, pure NumPy + stdlib, **no Qt imports** — the same functions serve the Shape Space tab and a future classifier). Turns a baseline-corrected `delta_mV` signature into the scalars the 2026-07-23 corpus analysis found to separate targets: `unit_shape`/`amp_l2`/`snr`, `band_means`, `band_range_mean`, `crossing_us`, `decay_persistence`, `family`/`family_gated`. Geometry is always passed explicitly (`pulses_us`, `n_delays`) — nothing assumes 63 cells, and bands/thresholds are resolved by **value** (rows sorted pulse-ascending, threshold high→low) rather than by stored index, which is what makes a live frame and a stored capture comparable. `family` (sign) and `decay_persistence` (magnitude) are meant to be read together and neither may overrule the other: a ferrite toroid reads ferrous by sign and non-ferrous by decay, and both are true of it. `--selftest <corpus csv>` runs four acceptance groups against a known corpus |
| `src/pimd_features.py` | Session-CSV / gui_signatures-CSV → training-corpus builder (**v14**, offline CLI). Registry join (`target_id` + structured placement replace free text), hard geometry guard — one `(profile_name, profile_sha8)` per corpus build; direct-ingest path for classviz corpus CSVs; pre-v1.32 free-text inputs loudly rejected, no migration by design. **v8–v11:** parses mid-stream `# session_notes:` (v8, needed once classviz auto-started sessions and the operator's notes began arriving *after* the header); a **`pack_v` track** — `list[(datetime, volts, age_s)]`, a track and not a scalar because a 6S pack falls volts over a multi-hour run, with `pack_v_at()` interpolating per capture and refusing to guess at malformed lines — plus parsed `# stall:` and `# soak:` lines, and `pack_v` appended to `CORPUS_HEADER_FIELDS` (v9–v10). **v11 exposes `SessionData.fw_seconds`, the firmware clock**, which `parse_session_file()` had always read and then discarded, and **fixes `measure_frame_rate_hz()`**, which was being fed PC arrival timestamps: USB delivery is burst-batched, so the measured rate came out **73–290 Hz against a true 6.94 Hz**, and its consumers size segmentation windows in frames from it. It hid because the two clocks share the same *mean* — only the median is wrong, and the median is used deliberately since it survives stalls. **No corpus row on disk was ever built through that path** (all 166 captures come from classviz directly), so no rebuild was required — verified, not assumed. The `pack_v` **corpus column carries no staleness information** while the session track does: it stamps the field's current value, so a stale entry reads as confident. **v12–v13:** a `tilt_deg` column — tilt of `dim_a` away from the coil normal in degrees, **0 = down the coil axis** (same pose as `long_axis=z`), **90 = in the coil plane** (same pose as x/y), blank when not recorded; the two ends are deliberately redundant with `long_axis` and the column exists for the angles between. It is appended **last** in `CORPUS_HEADER_FIELDS`, and that is a constraint rather than a preference — `classviz._scan_editable_signature_file()` indexes positionally off this list while reading files that lack the column, so appending is safe and inserting would silently misread every corpus on disk; same reasoning for `_MARK_TARGET_KEYS`, which `parse_mark_target_line()` zips positionally. `format_tilt()` renders `None` and `''` identically as `''` while preserving a recorded **0**, which is the distinction the placement key depends on. v13 reads the `# capture:` line classviz v1.68 writes into `SessionData.captures` — `list[(datetime, dict)]` with the window bounds parsed to `(start, end)` pairs on the same clock as `t_seconds`, so a corpus row resolves to the exact frames it was reduced from; unknown keys are **kept rather than dropped**, because a join key whose reader silently discards a later-added field fails worse than one that carries it. Additive throughout: every pre-v1.68 dump parses as before with `captures=[]`. **v14:** `TOOL_VERSION` re-synced with the header — it had sat at `pimd_features.py v11` through the v12 and v13 edits, the same de-sync delaycal v1.25 fixed. It is **output, not a label**: it is stamped into every corpus row's `tool_version`, so anything built by v12/v13 was recorded as v11's work. Nothing on disk is affected (every corpus row to date comes from classviz directly, not through this path), and the bump to v14 rather than a quiet set to v13 keeps the corrected stamp distinguishable in any future corpus |
| `src/pimd_target_check.py` | Shared target-registry loader/validator (**v4**, CLI + library; named `pimd_targets.py` before v3). Reads `src/data/targets/targets_v3.csv`, collects all errors/warnings (ids, enums, numerics, dims order, mass plausibility); never writes the registry. `DEFAULT_REGISTRY_PATH` here is the single source of truth for the registry location — classviz and features both derive from it, so repointing it at v3 moved all three. Used by classviz (capture-time) and features (build-time). **v4:** the CLI's registry path default is **removed** — `-f/--file` is required, because with several registry versions on disk a defaulted path had become a trap (it still named v1 while the live registry was v3, so a clean run said nothing about the file in use), and the run now prints the absolute path it loaded. `wall_thickness_mm` gains an explicit **0 = solid / not applicable** sentinel, replacing v3's `na` (rejected as unparseable) and v1's empty cell; both legacy spellings still normalise to `0.0`, so the column is now always a float |
| `src/pimd_corpus_check.py` | Corpus-level acceptance checker (**v1.9**, offline CLI) — shape distance-invariance, split-half SNR, repeat consistency, falloff fit, optional `--baseline` cross-campaign comparison; one flat PASS/AMBER/FAIL/SKIP table, exit 1 on any FAIL, so it can gate a capture day. Reads the v1.32+ `target_id`/`distance_mm` schema only (legacy `target`/`distance_cm` cleanly rejected). Distances are data-driven — a target at ≥2 distances gets shape rows, ≥3 gets a falloff fit; repeats key off the `repeat_idx` column against the physical placement tuple; the old canary-drift check is retired (per-capture air bracketing does that correction in features). Air captures carry no distance: they appear in the SNR check as `@air` and are excluded from every distance-keyed check. **v1.7:** `placement_key()` normalises the three fields classviz v1.60 froze (`face_normal` → `na`, both offsets → 0) through a shared `placement_value()` **that classviz imports**, so the app and the checker cannot drift on what "the same placement" means — without it a corpus straddling that change splits one physical placement into two groups and repeat-consistency compares nothing against nothing (on the live corpus this took the run from 30 checks to 90, and made the distance-falloff fit run at all). **v1.8:** `pack_v` is an **optional** column — `REQUIRED_FIELDS` was the whole field list, so adding any column to `CORPUS_HEADER_FIELDS` would have failed every corpus written before it; additive schema growth belongs here rather than in a migration. **v1.9:** `tilt_deg` joins `PLACEMENT_FIELDS`, so 0°/30°/60° at one distance are three distinct placements with independent `repeat_idx` sequences rather than three repeats of one — the whole point of recording the angle. The delicate part is that an optional field *inside the placement key* can present as an absent column, a missing dict key, `None` or `''`, and all four are the same physical statement: new `PLACEMENT_BLANK_FIELDS` collapses them to `''`, and the key builders moved to `.get()`. This is the same failure `PLACEMENT_CONSTANT_FIELDS` was created to prevent, arriving by a different route — without it every historical placement would split in two and every `repeat_idx` restart. **A recorded `0` is not blank**: 0° is a real axial capture, and conflating it with "no angle recorded" would merge the oblique study's 0° base with every `long_axis=x/y` capture of the same target. Verified rather than argued — output on both corpora is byte-identical to the pre-change baseline across all 377 checks and 134 repeat-consistency rows |
| `src/data/targets/targets_v3.csv` | Human-authored registry, **current** — **27** physical target objects *(verified against the file 2026-07-31; the "26" recorded previously was the count at the 2026-07-26 validation run, before the solder stick was added on 07-28)*, single source of target physical metadata (id, material, shape, dims, mass, …). Human-owned data: tooling reads and validates only. Revision v3 added rocks, quartz and a water bottle, changed the solder roll, and later a weighed 56 g solder stick. Loads with **0 errors**; the one remaining warning is deliberate (see below). Two provenance notes worth keeping: the LibreOffice export had been written as **UTF-7**, arriving with every `_`/`-`/`#` as a `+AF8-`-style escape (decoded in place with `iconv`; the export dialog remembers the charset, so it needs setting back to UTF-8 or this recurs), and `Fe_heavy_pully` was reclassified `disc` → **`ring`** — its 66 mm wall was flagged as set on a solid shape, but the measurement is right (a real bore, 66 = (150−18)/2), so the row was a shape misclassification, not a bad number. Flagged, not changed: that id misspells "pulley" and ids are stable by the registry's own rule (renaming would orphan captures), and its `closed_loop=y` reads the flag as "supports a large circulating eddy path" rather than the header's stricter written rule — a registry-wide semantics decision left open. **Open data-integrity item (§14.14):** `Sn_Pb_solder_spool_01` names **two different physical objects** across the epoch boundary — the header's own "changed solder roll", confirmed by a cross-epoch mean-shape cosine of +0.143 against ≥ 0.95 for every other matched target. The new roll needs its own id (ids are never reused) with the v1 captures left on the old one; until then all cross-epoch comparison for that id is invalid. Its `magnet_test = none` is **correct** — operator-verified; the ferrous-looking broadside signature is a shorted-loop effect, not a registry error |
| `src/data/targets/targets_v1.csv` | **Superseded** registry of 22 objects, retained on disk and tracked. The 2026-07-23 corpus (§17.9) references it, so it is the registry that corpus must be read against |
| `src/data/profiles/` | Locked calibration profiles (firmware↔ML contract, §10). Only the **operating** profile is tracked in git — **`cal_63_air_bat_v3.json`**; the superseded `cal_63_air_v2.json`, `cal_63_air_v1.json`, `cal_72_air_v3.json`, `cal_72_air_v2.json` are retained on disk but untracked — each is listed individually in `.gitignore` as it is retired. delaycal writes candidate profiles here routinely; those stay visible as untracked until they are either locked (tracked) or retired (ignored). Nothing in the code loads a profile by name, and both Import Profile and Compare Profiles scan the directory off disk, so a retired profile stays usable as a comparison reference for as long as the file is kept |
| `src/data/corpora/` | Signature-corpus captures from classviz's Analysis tab (`gui_signatures_*.csv`, CORPUS_HEADER schema). `gui_signatures_targets_v1_20260723.csv` — 66 captures, 22 targets, 60–420 mm, under `cal_63_air_v2` (§17.9). `gui_signatures_targets_v3_20260728_142316.csv` — the v3-epoch corpus under `cal_63_air_bat_v3`, **188 captures / 11 844 rows / 25 targets, verified against the file 2026-07-31**, of which **100 carry a `pack_v`** spanning 21.08–24.4 V (those without it are the 07-28 captures, which predate voltage logging) and **13 carry a `tilt_deg`** (the oblique-orientation study, §17.14). *(§17.12/§17.13 quote 166 captures with `pack_v` on 10, and §17.14's main analysis 170 — those are the states at their own analysis times, and are the figures those results were computed from. This file grows with each capture day, so **any count in this document is a snapshot: check the file.**)* **Migrated in place 2026-07-31 for `tilt_deg`** — corpus append writes *the file's own* header columns, not the tool's (classviz v1.65), so appending an oblique capture to a file lacking the column would have silently dropped the angle and the feature would have appeared to work while recording nothing. Migrating rather than starting a fresh file keeps the corpus in one piece, which §17.14 supports directly: the between-session noise component measures **zero**, so captures either side of the line are comparable. Verified — every pre-existing column byte-identical across all rows, checker output identical to the pre-migration baseline; the v1 corpus and the scratch file are left unmigrated and read blank. Untracked in git while capture is underway (working data until a corpus is accepted), which means **git cannot restore a damaged corpus** — the two 2026-07-30 repairs each took a timestamped `.bak-` copy first and proved the write against it. One lesson from those: comparing a file against its own backup cannot detect damage that predates the backup, so row width is now asserted against the **header** |
| `src/data/sessions/` | Raw Mode 2 session dumps (`session_<ts>.csv`) — self-describing per-session CSV with embedded profile JSON, per-column map, marks, and the `# pack_v:` / `# soak:` / `# stall:` comment tracks. Written automatically whenever the stream runs (classviz v1.63), ~220 KB/min. Untracked, and **not reconstructable after the fact** — the 2026-07-29/30 pack-voltage result (§17.13) exists only because auto-logging captured windows nobody would have pressed Record for. **Every dump written before classviz v1.68 carries zero `# mark:` lines** (logging auto-started at v1.63 but marks only ever came from a button nobody pressed), so ~380 000 frames sat with no ground truth and no key to the corpus. Two things fixed that: v1.68's **`# capture:` line**, which stamps the exact frame window a corpus row was reduced from and is the lossless join key going forward; and `utilities/session_relabel/` (below), which recovered what it could from the dumps already on disk. **Five of those dumps now carry reconstructed marks**, each stamped `reconstructed cos=… src=…` in its notes — treat them as labelled by *shape match to a corpus capture*, not by observation, and note the match identifies the **target**, not the individual capture |
| `src/data/scratch/` | Scratch captures of **unregistered** objects from the Shape Space tab (`gui_scratch_<date>.csv`, same CORPUS_HEADER schema, `scratch_<slug>` ids). Deliberately never written into `src/data/corpora/`: a corpus build hard-errors on an unregistered `target_id` and that guard stays — promotion means registering the object in the current registry (`targets_v3.csv`) and recapturing properly. The air-anchor mode (`[anchor=flat]` / `[anchor=air2]`) is recorded in the notes, because a flat single-anchor capture is not drift-corrected and that must stay visible afterwards. Untracked |
| `src/pimd111.ui` | Qt Designer UI source for `pimd_gui.py` (sliders/QLineEdit fixed to match code, 2026-07-02) |
| `utilities/` | Local analysis tools that are **not** part of the PIMD toolset — one directory each, ordinary tools by convention (`TOOL_VERSION`, terse `# History:` header lineage, read-only with respect to the repo), with their history in `CHANGELOG.md` under a `### utilities/<name>/` heading like anything else. **The rule: a utility cited from `CHANGELOG.md` has to be tracked** — the 2026-07-30 result names `soakvolt.py` as the tool behind it, and had that file stayed local the project's headline finding would not have been reproducible from a clone. (A separate untracked `CHANGELOG.local.md` was tried and abandoned: two places to look, two formats to keep in step, and detail behind a tracked finding living where no clone would see it.) |
| `└─ soak_vs_voltage/soakvolt.py` | **v1** — reads every classviz session dump for a campaign and separates pack voltage from soak time, the two variables every session before 2026-07-30 confounded in the same direction (ρ 0.80–0.91 against either, identical magnitude, so no *within*-session correlation could have settled it). The tool behind §17.13. Four things it does that a one-off script would not: window hygiene as a **span test on the firmware clock** mirroring classviz's own guard, so it caught the §14.10 host stall without being told about it; **three provenance grades** on every voltage figure (`typed` / `held` / `note`, degrading to `interp` / `extrap`), never mixed silently, with a header `pack_v` of unknown age **dropped** as a settings restore rather than a reading; **loaded readings only**, never interpolating across a rest, because a rested pack rebounds; and the stream-start transient removed **by test** (every column above 5× its own session floor) rather than by duration, so it cannot silently eat real warm-up. Emits JSON |
| `└─ pack_discharge/` | **v3** (`packv.py` + `build_page.py`) — derives pack discharge rate, state of charge and remaining streaming runway from the `# pack_v:` lines a dump already carries, fitting in *streaming* minutes because the profile loop draws a fixed duty. Source of the §12 capacity figures. Three corrections the raw log requires, each of which changes the answer: `age_s` must be applied (a header `pack_v` is the spinbox value restored at session open — one was measured 95 min before the session existed); the axis must be **accumulated streaming time**, not wall clock (idle drain is ~15× lower, so wall clock flattens the slope through every gap); and readings within 5 min of load-on are rested, not settled, and sit high. **Two methodological traps recorded rather than buried.** (1) v1 claimed split-half cross-validation as evidence and it was **coincidence** — the split correlated with voltage range, and across too little voltage the two fitted parameters trade off freely; replaced with leave-one-out. Practical upshot: **constraining runtime needs curvature, not more points on the flat.** (2) v1/v2 named the second parameter `sag` and reported it as the pack's IR drop — **wrong by ~3×** against a direct measurement (0.29 V, §12); it is a curve-alignment constant absorbing mismatch between a nominal OCV shape and these cells. Renamed `offset`. The general lesson: a two-parameter fit gives a physically-named parameter a confident value whether or not the name is right, and **the residual does not complain** — RMSE stayed 46 mV throughout, a good fit of the wrong thing. Also v2: refuse to fit **across a recharge** (v1 fitted straight through a pack swap and reported a confident, nonsensical runtime; the only outward sign was a residual it computed and never surfaced) |
| `└─ session_relabel/relabel.py` | **v1** — retro-labels the mark-free dumps by matching plateaus against the corpus. **The one utility that is NOT read-only with respect to the repo:** `--apply` rewrites session dumps in place (default is a dry run). Plateaus come from the existing change-point approach; each is matched by **cosine on the unit shape**, with time used only to bound the candidate set and **never** to break a tie, because `captured_at` lags the frames by tens of seconds. The load-bearing detail is that the air baseline must be **interpolated between a reference before and one after**, exactly as `compute_plateau_stats()` does — a single earlier reference carries the full drift and was costing ~0.05 of cosine (§14.1); with interpolation the correct pairings score **0.996–1.000**. Applied at a 0.95 floor it recovered **39 mark pairs across 5 dumps**, rejecting 440 plateaus — most of them air, which shape matching cannot identify by construction and which the tool therefore declines to label rather than guess. Every injected mark carries `reconstructed cos=… src=…` provenance and a `# session_notes:` line records tool, date and floor. **Two limits worth knowing:** the match identifies the *target*, not the individual capture (repeated placements of one target at one distance are shape-identical, so two plateaus can cite the same `src=`), and injecting marks changes what `pimd_features --out` would produce from these dumps — it currently emits nothing for them and would now emit rows **duplicating** corpus captures under different ids. *Do not merge without deciding to.* Every file backed up and verified after writing: injection inserts comment lines only, and all 221 754 data lines came back byte-identical |
| `References/schematic-v604.jpg` | Schematic export, rev 6.04 (current front-end, R12/R13 = 0 Ω, field annotations) |
| `References/scope-pulse-baseline.jpeg` | Scope baseline, Mode 1, 10 kHz / 20 µs / 10 µs |
| `References/GUI-target-example.jpg` | App baseline, Mode 1 v4.07, 10 kHz / 20 µs / 10 µs / DS 1024 — positive spike = ferrous, negative spike = non-ferrous, noise < 500 µV |
| `References/GUI-steady-state-256-1024.jpg` | SoC steady-state reference capture — settled noise floor and thermal drift; Mode 1 at SoC conditions, first half DS 256 / second half DS 1024 |
| `References/GUI-noise-comp.jpg` | GUI noise comparison — DS 256 vs DS 1024 side-by-side, Mode 1 at SoC conditions |
| `References/early-discrimination-tests.JPEG` | Early discrimination test captures |
| `References/pcb-coil-baseline.JPEG` | Bench baseline setup, pre-enclosure — main board mounted on the v4 concentric TX/RX coil (epoxied to Perspex), battery supply via 18 V pack adapter |
| `References/warmup-with-8ns-steps.jpg` | Mode 1 GUI capture during warm-up — sample delay stepped in 8 ns grid increments at 25 kHz / 10.4 µs / DS 256; each grid step lands ≈ 5 mV apart on the steep decay, with warm-up drift visible as the slope between steps. Illustrates why calibrated delays snap to the 8 ns PWM grid |
| `References/new-training-data.jpg` | classviz v1.32 Analysis tab — first capture session under the structured target-metadata regime (cal_63_air_v1 loaded via Load & Run, registry-backed target combo + placement fields, Std Dev heatmap mode, per-pulse-width and per-delay profile charts) |
| `References/training-targets-v3.JPEG` | Target set v3 — the physical objects behind `src/data/targets/targets_v1.csv` laid out on the bench (pipes, brass block, solder roll, copper crimps, gear, ferrite ring, silver items, spanner, shackle, plates, …) |
| `References/training-results-v1a.jpg` | **Previous-epoch** (cal_72_air_v2 corpus): normalised 5 cm band responses grouping 17 targets into ferrous-rising / crossover (SS pipe, lead pipe) / non-ferrous families — the τ-fingerprint result behind §13's discrimination claims; findings historical since the epoch reset |
| `References/training-results-v1b.png` | **Previous-epoch**: staircase-session diagnostic (2026-07-03) — 5/10/15 cm plateau timeline, shape-change vs distance, amplitude falloff, per-target distance-invariance overlays |
| `References/training-results-v1c.png` | **Previous-epoch**: 17-target cosine-similarity matrix (three sessions combined, cal_72_air_v2) showing the two-family block structure plus SS pipe as the crossover outlier; amplitude-vs-distance and family panels |
| `References/Targets v1 Analysis/` | Offline analysis of the 2026-07-23 corpus (66 captures, `cal_63_air_v2`) — the evidence base for §17.9 and for `pimd_shape.py`'s feature set. Untracked working output; `pimd_v2_corpus_analysis.csv` carries the per-capture table (amplitude, SNR, gate pass, empirical vs consensus family, nearest neighbour + cosine) behind the five figures below |
| `└─ fig1_signature_atlas.png` | Best-SNR capture per target as a 7 × 9 tile (rows pulse 9→100 µs, cols threshold 4.9→0.5 V), each tile self-normalised, red = ferrous-positive / blue = non-ferrous-negative, titled with amplitude, distance and SNR. The whole target set's signatures at one glance — and the visual form of the polarity convention (§2) |
| `└─ fig2_family_plane.png` | The family plane — early-pulse (mean of 9 + 13.4 µs bands) vs late-pulse (mean of 67 + 100 µs) components of the unit shape, every capture at every distance; marker size ∝ log amplitude, hollow = SNR < 5. Shows the three quadrants (non-ferrous −/−, crossover −/+, ferrous +/+) and, directly, the §14.9 problem: the ferrous cluster sits hard against the x = 0 axis |
| `└─ fig3_similarity_matrix.png` | Pairwise cosine similarity of all 66 L2-normalised signatures, ordered non-ferrous \| crossover \| ferrous. Within-family shapes collapse toward 1.0 and the families separate as blocks; the NdFeB magnet is the visible outlier row/column, and the ferrite toroid anti-correlates strongly with the whole non-ferrous block |
| `└─ fig4_invariance_envelope.png` | Two panels. Left: measured within-target cosine across distance pairs vs the ceiling predicted from the captures' own SNRs — points on the line mean shape degradation is fully explained by noise, not by real shape change with distance. Right: amplitude vs distance per target on log axes, slope steepening from ≈ −1.2 in the near field toward ≈ −4…−6, with the SNR-5 ID floor (≈ 6 mV) drawn |
| `└─ fig5_crossing_axis.png` | Left: normalised band-mean profiles vs pulse width with each target's zero crossing marked. Right: the crossing point as a single coordinate — stable with distance, ordering the crossover family (D-shackle earliest ≈ 14 µs → cast-iron trivet latest ≈ 34 µs) between the "positive by 9 µs" rail (solid ferrous) and the "never crosses" rail (non-ferrous). The basis of `crossing_us` and its two sentinels |
| `References/V3/NEXT_SESSION_soak_vs_voltage.md` | Handover brief for the 2026-07-30 soak-vs-voltage analysis. Cited because its **§1 holds the pre-registered predictions** — written before any data was touched, because the operator did not accept the soak conclusion and re-arguing it was not going to settle it. Both hypotheses committed to a number for the same session in advance (soak: the 3.80 V column starts bad at 1700–2100 µV; voltage: starts clean at 200–400 µV; it read **742 µV**), which is what makes §17.13's result a test rather than a post-hoc reading. Untracked working document |
| `USAGE.md` | Per-app usage guide — intent, operation and pipeline flow for the firmware and each PC tool (replaces the former `docs/` cheat sheets) |
| `CHANGELOG.md` | Running change log — the source this DESIGN.md is consolidated from (logging conventions in `CLAUDE.md`); archive entries for previous consolidation passes are preserved below the marker line |
| `DESIGN.md` | **This file** — project reference (specs, design, measured values); a curated snapshot consolidated from `CHANGELOG.md` |
| `CLAUDE.md` | AI-agent working brief — how to behave when editing this repo (mindset, conventions, don'ts). Not project facts |

---

## 16. Build, run & deploy

**Don't commit yourself**

No build step for either the PC tools or the firmware. (Agent conventions — version
bumps, changelog discipline, the "don't edit this DESIGN.md" rule — live in `CLAUDE.md`.)

### Run / deploy (PC venv)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
cd src
python pimd_gui.py        # Mode 1 GUI (filtered telemetry)
python pimd_classviz.py   # Mode 2 signature visualiser
python pimd_delaycal.py   # delay-calibration sweep

# Offline (no board): feature-maths acceptance check against a known corpus.
# NOTE (2026-07-31, §14.15): this reads FAIL (46 problems) against the v3 corpus and
# PASS against v1. The expectations are hard-coded from the 2026-07-23 cal_63_air_v2
# analysis, and 38 of the 46 are the crossing ladder — a per-epoch quantity (§10,
# §17.14). Nothing is broken; the command points at the wrong-epoch corpus. Until
# §14.15 is decided, run it against v1 to exercise the feature maths:
python pimd_shape.py --selftest data/corpora/gui_signatures_targets_v1_20260723.csv

# Offline: registry validation (-f is required as of target_check v4 — there is no default)
python pimd_target_check.py -f data/targets/targets_v3.csv

# Offline: corpus acceptance checks (exit 1 on any FAIL, so it can gate a capture day).
# NOTE (2026-07-31, §14.15): currently 411 checks / 229 FAIL on the v3 corpus, undiagnosed.
# Read the per-check table, not the exit code, until that is understood.
python pimd_corpus_check.py data/corpora/gui_signatures_targets_v3_20260728_142316.csv
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
V                     → version / identify
L                     → list profiles
Q4  then  G           → Mode 2 streaming CLASSIFY_EP (W4 records, 45-ch, ≤100 Hz);  E to stop
*5000,40000,8400,256  then S → Mode 1 streaming (* records, ~20/s);    E to stop
A32                   → one raw boxcar average (R record), idle/Mode 1 only
```

---

## 17. Test log / observations (curated)

> **Epoch banner (2026-07-13):** §17.1–17.6 predate the shielded enclosure and fw v4.24
> (§17.7). They are kept as history — the methods and qualitative findings stand, but
> every quantitative value must be re-measured before reuse.
>
> **Supply note (2026-07-24, amended 2026-07-30):** the move to the 6S pack (§12) is
> deliberately **not** a second epoch reset, and §17.7–17.9 stand as taken. But the reason
> originally given — that the L7815 holds coil drive constant so state of charge never reaches
> the operating point — is **true only over the 0.55 V interval it was measured on** (§17.10).
> Over 21–25 V pack voltage moves the operating point at 43–51 mV/V (§17.13). What follows for
> reading this log: any measurement taken on battery is implicitly **conditioned on a pack
> voltage that was usually not recorded**, so a figure from §17.11–17.12 should be treated as
> holding at that session's state of charge rather than universally. Voltage is logged from
> classviz v1.64 onward (§15). Also changed: warm-up is longer (§14.1), and the free-air noise
> floor is now partly measured on battery (§14.3).

Per-entry: **date · fw/hw rev · one-line summary**, grouped by subject. Detailed changelogs
stay in source-file headers. This log is curated — it is refreshed from `CHANGELOG.md` at each
consolidation pass. When an observation **supersedes** an envelope value (§3), the envelope is
updated in place with a dated note and the raw observation is recorded in `CHANGELOG.md`.
(Logging conventions for agents live in `CLAUDE.md`.)

### 17.1 Power / current vs pulse width
"current" = average bench-supply current (at 20 V), not peak coil current. 

| Pulse (µs) | Rep rate (Hz) | Supply current (mA) | Note |
|---|---|---|---|
| 40 | 10 601 | 500 | rate raised until draw reached the 0.5 A target |
| 30 | 17 599 | 500 | as above |
| 20 | 29 201 | 410 | 0.5 A not reached — frequency/duty-cycle constrained |
| 10 | 43 003 | 201 | as above |
| 5 | 56 992 | 105 | as above |

*(Table repaired 2026-07-31. It previously had four columns — "Freq Req (Hz)", "Freq (actual)"
and "Current (mA)" — in which the 40 µs rate appeared as "10.6" (the kHz value left in an Hz
column), the 500/500/410/201/105 series sat under "Freq (actual)" although it is the **current
in mA**, and the current column held the procedural note. The values are unchanged; only the
column identities are corrected, from the 2026-06-17 bench entries. These are the measured
operating points of the power sweep — the rate was raised per pulse width until the supply
drew 0.5 A, which the two widest pulses reached and the three shortest did not.)*

### 17.2 Standard Operating Conditions / noise floor

*2026-06-18 · fw v4.19 · Mode 1 · bench supply 20 V · coil in air*

**SoC:** 10.0 kHz / 20.0 µs pulse / 10.0 µs sample delay / DS 256. Allow 4 min warm-up
from cold — expect ≈ 50 µV/s drop during this period. Do not take noise-floor readings
as representative before the 4-minute mark.

Reference capture: `References/GUI-steady-state-256-1024.jpg` — first half of plot at DS 256,
second half (after DS Factor toggle) at DS 1024. Shows the settled noise floor and slow
thermal drift; this is the trace future comparisons should be checked against.

### 17.3 Mode 2 — profile streaming

Acquisition bugs resolved in fw v4.20–v4.24 (boundary settling — made time-floored in
v4.24, §8/§17.7; cell-misattribution read/write ordering; IRQ critical section around
BUSY+SPI). Mode 2 streaming is functionally stable. Active development is now in the
tooling layer (`pimd_classviz.py`, `pimd_delaycal.py`).

### 17.4 Delay calibration sweep

*2026-06-20 · fw v4.23 · 20 kHz / 20 µs pulse · OBS P2006-113356.csv*

First data set with fw v4.23 integer Hz/ns protocol. 13 delay steps, 7088–8048 ns in 80 ns
increments (~5 s/step), warm-up 30 s. All delays land exactly on the 8 ns PWM grid.

| delay (ns) | delay (µs) | V mean (mV) | V σ (µV) | fw_sd (µV) | status |
|---:|---:|---:|---:|---:|:---|
| 7088 | 7.088 | 4877.3 | 1835 | 242 | settled — slow filter tail (rolling-window flush artefact) |
| 7168 | 7.168 | 4809.2 | 71 | 65 | **clean** |
| 7248 | 7.248 | 4736.3 | 378 | 125 | settled — moderate |
| 7328 | 7.328 | — | — | 500–1400 | **never settled** |
| 7408 | 7.408 | — | — | 500–1400 | **never settled** |
| 7488 | 7.488 | 4477.5 | 227 | 158 | settled — ok |
| 7568 | 7.568 | 4379.3 | 177 | 161 | settled — ok |
| 7648 | 7.648 | 4273.8 | 179 | 111 | settled — ok |
| 7728 | 7.728 | 4161.5 | 176 | 139 | settled — ok |
| 7808 | 7.808 | — | — | 500–1400 | **never settled** |
| 7888 | 7.888 | — | — | 500–1400 | **never settled** |
| 7968 | 7.968 | 3795.4 | 180 | 105 | settled — ok |
| 8048 | 8.048 | 3666.1 | 319 | 143 | settled — moderate |

Key findings: (1) 8 ns grid fix confirmed — no two-stage settling artefact seen (was present
in v4.21 off-grid dataset P2006-103607). (2) Four delays never settle: 7328+7408 and
7808+7888 — two 160 ns noisy zones exactly 480 ns apart, consistent with ~2.08 MHz LC ringing
in the coil/preamp persisting to 7–8 µs after TX cutoff. (3) 7088 ns: high V σ (1835 µV) but
low fw_sd (242 µV) — voltage drift ~5.6 mV/24 s from the 256-sample rolling window still
flushing the previous step (3.28 s flush time), not physical noise. (4) Best operating window
at 20 kHz / 20 µs: **7488–7728 ns** (320 ns clean band).

### 17.5 Profile redesign & calibration series (geometric ladders)

*2026-07-02/03 · fw v4.23 · delaycal v1.19 · cals 163936 → 165109 → 174257 → 180813 → 202505 → cal_72_air_v2*

Pulse widths moved from even-spread guesses (6/10/20/30/40/50/75/100 µs — bunched at
30–50 µs, gapped at 10–20) to a **geometric ×1.5 ladder** (6/9/13.44/20/30/45/67.2/100 µs);
thresholds moved from 0.5 V linear steps to **geometric ×0.766** (top cells were
near-duplicates). Findings from the series:

- **Decay is non-exponential across the sample window** — local τ shrinks monotonically from
  ≈ 3 µs near the top anchor to ≈ 1.2 µs near 0.5 V. Both linear- and geometric-threshold
  cals agree on the shape (two independent ladders, same curve). Suspected clamp-release
  proximity stretching apparent τ at the top.
- **Thermal warm-up fingerprint:** two cals 12 min apart — light bands repeat to ≤ 8 ns
  (one grid step); heavy bands drift monotonically with pulse width, up to −248 ns at 100 µs
  (decays arrive earlier warm). Basis of the ≈ 5 min Mode 2 warm-up (§3). After full soak,
  the freeze cal adjusted 13 delays of 72 — mostly a coherent +40 ns shift of the 4.5 V
  clamp-release column *(corrected 2026-07-31: this read "only 1 delay of 72 (+40 ns)")*.
- **31.25 kHz known-bad rep rate** — see §8. Band 2 moved to 25 kHz / 9 µs.
- **Top-anchor sensitivity:** the highest-threshold column is consistently the noisiest
  (clamp-release region, flattest curve, thermal drift appears there first); anchor stepped
  4.8 → 4.5 → 4.2 V, after which the column behaves normally.
- Recurring **67.2 → 100 µs plateau hint** — logged as open problem §14.6.

### 17.6 First 7-target Mode 2 session

*2026-07-02 21:24 · fw v4.23 · classviz v1.16 session dump · profile cal_20260702_202505 ·
2487 frames @ 7.3 Hz, 341 s, 0 flagged · air floor ≈ 0.55 mV/cell (drift-corrected)*

Targets at close range: spanner, copper pipe, silver-clad spoon (×2 approaches), gal steel
pipe, brass block, small steel piece, spanner+copper together. All detected; peak SNR 43–122×
air floor. Key findings:

- **Polarity convention holds** (ferrous +, non-ferrous −) with one important exception:
  the **small steel piece changes sign along the pulse ladder** — negative at 6–30 µs,
  zero-crossing near 45 µs, strongly positive at 100 µs (eddy response dominates before the
  pulse can magnetically energise it). A single-operating-point PI would classify this target
  by whichever sign its one pulse width landed on; the ladder resolves the full crossover.
- **Both matrix axes discriminate:** ferrous is flat along the threshold axis (perturbation
  persists late in decay); non-ferrous concentrates early, falling to ~0.25–0.4 by the 0.5 V
  cell. On the pulse axis the spoon saturates by ~45 µs while copper/brass keep climbing and
  both ferrous targets are still rising steeply at 100 µs — different targets go redundant in
  different cells, so no cell is globally redundant on this evidence.
- **Superposition approximately holds:** spanner+copper frame ≈ 1.49·spanner + 0.50·copper,
  corr 0.992 — the matrix is close to linear in targets (unmixing plausible). Caution: the
  steel piece *alone* also fits a spanner+copper mixture at corr 0.978 in band-mean space;
  the threshold axis breaks the tie (crossover target's decay-shape rises ~3× vs ~1.8× for
  the true mix) — an argument for keeping the full 72-cell matrix.
- **Shape-space distances** (normalized signatures): spoon repeat-approach floor 0.028;
  spoon↔copper 0.178, spoon↔brass 0.111, copper↔brass **0.077** (hardest pair).
  Spanner and gal-pipe shapes are near-identical (cosine 1.00), differing in amplitude only.

### 17.7 Enclosure, settling fix & threshold-zone mapping — epoch reset

*2026-07-13 · fw v4.24 · delaycal v1.24 · classviz v1.30 · new shielded enclosure*

- **Shielded enclosure installed.** The electronics now live in a new shielded enclosure.
  Combined with the fw v4.24 acquisition-timing change, this **voids most previous
  quantitative findings** — noise floors, drift rates, the §17.4 delay-zone map, and all
  previous-epoch target/corpus data (dropped from this document; the ML corpus will be
  rebuilt). §17.1–17.6 are retained as flagged history.
- **First-column noise root-caused and fixed.** The first cell of each band was noisy
  regardless of calibrated voltages, wandering on a seconds timescale. Cause: boundary
  settling was 15 PWM *periods* (period-scaled), giving 25/20 kHz bands only 600/750 µs
  against the ~1 ms+ the band-to-band energy-step transient needs; band 1's first cell
  escaped by accident because the ms-scale W-record print at loop index 0 donated extra
  settling every sweep. The ±1-period jitter in effective settle count became telegraph
  noise, smeared into seconds-scale wander by the 32-deep rolling average (32 sweeps, i.e.
  ~4.6 s at the later-measured 6.9 Hz; this was written as ~9.2 s from the ~3.3 Hz sweep-time
  assumption corrected in §8).
  fw v4.24 floors settling at SETTLE_FLOOR_US = 3 ms per boundary (§8) — bench-verified:
  first-column σ normalised, wander gone. Sweep time rose ≈ 12 ms *(the "≈ 289 → ~301 ms"
  figures once quoted here were modelled, not measured — see §8)*.
- **Threshold noise zone mapped: ~4.45–4.65 V.** Fine sweep 4.700 → 4.400 V in 37.5 mV
  steps, all 8 bands: endpoints clean (mostly ≤ 0.5 mV σ), interior 4.625–4.513 V columns
  elevated in nearly every band (up to 2.24 mV at 30 µs / 4.588 V). 4.7/4.8/4.9 V and
  ≤ 4.4 V both perform well — v2's "top column noisiest" story is reinterpreted: its
  4.5 V anchor sat inside this zone, and the rest was the settling artifact. The
  early-decay region is informative and now sampled densely (top-dense ladder, §10).
  Mechanism unknown (§14.7).
- **Post-enclosure top-of-decay ≈ 4.87–4.89 V** on heavy bands at short delays — below a
  4.9 V delaycal signal-detect ceiling, which made the coarse hunt false-trigger on its
  first step and fill start-delay values into the table. **Operational fix: ceiling =
  5.0 V** (no code change; §3 epoch note, §15 delaycal row).
- **cal_72_air_v3 locked** (§10): same band plan as v2, thresholds moved to the top-dense
  ladder 4.9/4.8/4.7/4.4/4.2/3.8/2.4/1.5/0.5 V straddling the keep-out zone.

### 17.8 Acquisition-fix pair, noise-zone edge & cal_63 recal

*2026-07-14 · fw v4.24 → v4.26 · classviz v1.31 → v1.32 · cal_63_air_v1 → v2 locked*

- **fw v4.25 — latched-cell fix.** The deepest-decay cell (ch72 of cal_72_air_v3, 100 µs /
  11.264 µs) sat flat at exactly zero regardless of target: the v4.21 outlier gate's
  threshold floored to ≤ 0 for near-zero/negative rolling means, rejecting every sample
  and freezing the cell at its warm-up value. Gate moved to `abs(mean)` + absolute floor
  (§8); cell tracks targets again.
- **6 µs band dropped → `cal_63_air_v1`** (63 cells): no unique target information,
  notoriously noisy; other 7 bands byte-identical to v3 (§10).
- **fw v4.26 — CC-write race closed, A/B verified.** The index-locked σ anomaly (band 1,
  cell 2 — ~8× neighbours' σ, followed sweep position when the band plan changed) was
  root-caused to post-emit USB-CDC IRQ bursts firing between the raw read and the CC
  write (§8). A/B under cal_63_air_v1 (v4.25: 114 frames / v4.26: 134 frames, ~10 min
  apart): **ch1 σ 3050 → 284 µV**; discrete corruption events 9 → 1 per session, the
  residual matching the low-rate ~±13 mV background seen on other channels under both
  firmwares. Occasional live flicker at that cell is this background — an order of
  magnitude smaller and rarer than before.
- **Noise-zone edge located.** Same A/B: ch56 (100 µs band, 4.70 V column) σ 605 →
  2693 µV with quantized ±64 mV single-sample events, identical size under both firmwares
  — a pre-existing bimodal phenomenon whose *rate* changed. Cause: thermal operating-point
  drift (heavy bands −20…−31 mV, monotonic with pulse width; light bands +9 mV) carried
  the cell from 4.673 to 4.669 V, across the §17.7 zone's **sharp upper edge ≈ 4.67 V**
  (event rate 1 → 10 per session for a 4 mV shift). Two-state character suggests a
  discrete mechanism (§14.7). Follow-ups in §14.7.
- **`cal_63_air_v2` locked**: delaycal re-run fully soaked under v4.26; delays −56…+16 ns
  vs v1 (heavy bands earliest — thermal signature). Retires the 4.70 V drift;
  bench-confirmed. New calibration epoch for corpus purposes (§10).
- **Corpus tooling landed** (2026-07-14): `targets.csv` registry (23 objects) +
  `pimd_targets.py` v1, classviz v1.32 structured capture, features v6 (§15). First test
  corpus captured to `src/data/corpora/`; the post-enclosure corpus rebuild ("audit
  first, train second") is under way.

### 17.9 First post-enclosure corpus campaign & the signature geometry it established

*2026-07-23 · fw v4.26 · classviz v1.39→v1.40 · `cal_63_air_v2` · 66 captures, 22 registered
targets, 60–420 mm · `src/data/corpora/gui_signatures_targets_v1_20260723.csv`*

The corpus rebuild called for at §17.8 was captured, and its offline analysis (figures in
`References/Targets v1 Analysis/`, §15) established the feature geometry the classification
layer is being built on. At an SNR ≥ 5 gate: **46 of 66 captures gated**, families splitting
**26 non-ferrous / 12 crossover / 8 ferrous**.

- **Three families separate as quadrants on an early-vs-late pulse plane** — the signed means
  of the unit shape over the 9 + 13.4 µs bands and the 67 + 100 µs bands. Non-ferrous −/−,
  crossover −/+, ferrous +/+. Cosine similarity of the L2-normalised signatures collapses
  within family and separates between families as visible blocks (fig3).
- **The zero-crossing pulse width is a stable third coordinate** and orders the crossover
  family: SS D-shackle earliest at 14.6 µs, gal pipe 14.9–21.1, gal RHS 20.8–23.4, SS perf.
  disc 26.4–30.9, cast-iron trivet latest at 33.9–34.4 µs. Every gated ferrous target crosses
  by ≤ 11 µs (i.e. is already positive at the bottom of the ladder) and every gated
  non-ferrous never crosses — so the two ends need sentinel values, not a crossing.
  ***Per-epoch, flagged 2026-07-31:** these are `cal_63_air_v2` values. Under v3 every crossing
  interior to the ladder moves **shorter, ratio 0.76 median** — trivet 34 → 24 µs, SS disc
  31 → 18, gal RHS 21 → 19, gal pipe 17 → 13 — because v3 samples 40–144 ns later (§10, §17.14).
  The **ordering is preserved**; the numbers are not portable and must be restated against the
  epoch in use. (The changelog entry recording this cites §17.6; the ladder lives here.)*
- **A threshold-axis "decay persistence" ratio is a second, independent readout to sign** —
  mean |Δ| over the two lowest-voltage threshold columns ÷ the two highest. Every gated
  **solid-metal** ferrous/crossover capture ≥ 2.44; every non-ferrous ≤ 1.75. **The ferrite
  toroid is the exception that defines the rule:** it is iron-bearing, reads ferrous by sign,
  and reads **1.37 by decay** — below the non-ferrous ceiling. So this ratio does *not* separate
  iron-bearing from non-ferrous as a class test; it separates by decay behaviour, and a ferrite
  behaves like a non-ferrous there while behaving like a ferrous by sign. Both readouts are
  true of it, which is why neither may overrule the other. *(Reworded 2026-07-31: the previous
  text claimed an iron-bearing/non-ferrous separation and quoted the ≥ 2.44 bound as covering
  every gated ferrous/crossover capture, which the ferrite in the same sentence contradicts.)*
- **Shape is distance-invariant to within the noise budget.** Measured within-target cosine
  across distance pairs sits on the ceiling predicted from the captures' own SNRs (fig4 left):
  what degrades with distance is amplitude, not shape. Amplitude falls with a slope steepening
  from ≈ −1.2 in the near field toward ≈ −4…−6, and the SNR-5 identification floor lands at
  ≈ 6 mV against the measured ≈ 1.2 mV L2 additive noise floor (fig4 right).
- **Family classification held at 97.8 %** under the SNR ≥ 5 gate in leave-one-out, but the
  misclassifications were **directional** — solid ferrous drifting toward crossover as SNR
  falls (`Fe_spanner_01` @240 mm). See §14.9: this is a real limit of the sign test, not a
  fitting artefact. ***Scope note added 2026-07-31:** this figure is not comparable to the v3
  corpus's 88.1 %, and the difference is not a regression. This corpus contains **no axial
  (`long_axis=z`) capture of any crossover target** — it sampled only the orientation in which
  the early-band sign happens to work, so it could not see the failure mode §17.14 exposes. Read
  97.8 % as "the sign test is reliable at transverse placements", which is what was measured.*
- **Corpus integrity:** the capture file was repaired in place after the classviz v1.40
  `capture_id`-reuse defect (three orphaned captures reissued by regrouping on `captured_at`;
  no measurement data lost, original kept as `.bak`). Any corpus captured with classviz
  ≤ v1.39 should be checked for folded captures before use.

### 17.10 6S battery epoch — heatmap survey, calibration series, drift ceiling

*2026-07-24 · fw v4.26 · classviz v1.42 · delaycal v1.25 · `cal_63_air_v2` loaded · 6S LiPo (§12)*

**Threshold-noise survey (22.4 V, Mode 2, Std Dev rolling-N heatmap).** The **4.40 V and
3.80 V threshold columns** read elevated across all seven bands at roughly 5× the §12 free-air
floor — at or near the 1284 µV display ceiling, only the 20 µs / 4.40 V cell falling short —
while **4.20 V read clean between them**. Follows the threshold axis, not the band axis. Full
reading and the two unresolved anomalies in §14.7.

> **Tension with the 2026-07-30 window, flagged 2026-07-31.** This survey was taken at
> **22.4 V**, and §17.13's rule says those columns are acceptable below 22.5 V. Both readings
> are direct measurements, so neither is discarded. The difference that is not controlled for
> is the **profile**: this ran `cal_63_air_v2`, whose delays sit 40–144 ns earlier than
> `cal_63_air_bat_v3`'s, and the zone's position is defined on the *decay*, which the two
> profiles sample at different points. That makes "the clean window" plausibly a property of
> **(pack voltage × profile delays)** rather than of pack voltage alone — a hypothesis, not a
> result, and untestable from logs because session auto-logging begins 2026-07-29. §14.7
> carries the experiment that would settle it.

**Calibration series — three runs, none locked.**

| Run | Time | Pack | Settings | Outcome |
|---|---|---|---|---|
| 1 | 20:23:51 | depleted, swapped out below 21 V | stale: 8 bands (6 µs present), 8 thresholds (4.2 absent) | **void** — two confounds (§15 delaycal row) |
| 2 | 21:10:06 | fresh, 23.6 V | corrected: 7 bands × 9 thresholds | still warming |
| 3 | 21:47:51 | 23.05 V | as run 2 | still warming, converging |

Runs 2 and 3 are 37 minutes apart with no hardware change, and give a delay shift monotonic in
pulse width (r = −0.95 against log pulse width):

| Band (µs) | 9 | 13.44 | 20 | 30 | 45 | 67.2 | 100 |
|---|---|---|---|---|---|---|---|
| mean shift (ns) | +14 | +9 | +1 | −11 | −27 | −48 | −84 |

Light bands later, heavy bands progressively earlier — the §14.1 thermal fingerprint,
reproduced under the new supply. Converging (smaller than the preceding interval) but a single
37-minute interval still moved the 100 µs band ~10 grid steps, so settling under 6S takes
longer than the historical case, consistent with roughly doubled 7815 dissipation (§12).

**Supply-regulation result — valid over this 0.55 V interval only; superseded as a general
claim by §17.13.** Across that interval the pack fell 0.55 V (23.60 → 23.05 V), yet the light
bands moved *later* — a direction a falling supply cannot produce, since less drive means a
smaller flyback reaching every threshold sooner across **all** bands. No supply-direction
component was visible, so this was read at the time as the L7815 holding coil drive constant
with **pack state of charge not reaching the operating point**.

> **Scoped 2026-07-30 (§17.13).** The reasoning is sound and the interval is real, but the
> conclusion does not generalise. Over 21–25 V state of charge moves the operating point at
> **43–51 mV/V**, which across 0.55 V predicts only ~25 mV — comfortably buried under the
> thermal drift this measurement was actually reading. So the null here is a **sensitivity
> limit, not an absence**. What survives, and is now independently re-supported: the inference
> that a fault tracking the *threshold* axis localises to the voltage domain (§14.7). The
> practical warning is general — **a regulated-window claim measured over a narrow interval
> should not be stated as a property of the supply.**

It argues for setting the capture-window floor from pulse-instant rail sag rather than gradual
discharge (§12, still unmeasured, and now the highest-value measurement outstanding).

**Reference age is a hard ceiling on any frozen-reference measurement.** At the §17.2 drift
rate of ~50 µV/s an air reference accumulates 0.5 mV/cell at 10 s, 3.0 mV at 60 s, 7.5 mV at
150 s. Against mean |Δ| from the 2026-07-23 corpus:

| Target | mean \|Δ\| (mV) | reference age that matches it |
|---|---|---|
| Cu_pipe_01 @60 mm | 6.52 | ~130 s |
| Fe_spanner_01 @60 mm | 3.28 | ~65 s |
| Cu_pipe_01 @180 mm | 1.05 | ~21 s |
| Fe_spanner_01 @240 mm | 0.36 | ~7 s |
| Cu_Zn_brass_dome_01 @180 mm | 0.35 | ~7 s |

Measured directly: a spanner @60 mm reads |Δ| 2.8 mV while 150 s of drift reads 5.2 mV — so
**removing the object makes |Δ| go up**. No magnitude test against a frozen reference can
detect removal, which is why auto-release was abandoned by direction. Retrospective: a static
baseline observed at 3381 s old carried ~169 mV/cell of accumulated drift — a live display
dominated entirely by thermal history. Consequences in §14.1.

Two rolling-window sizes were measured against this rather than assumed: a copper pipe
registered at 8 s with a 15-frame live window and **not at all** with 50; and a spanner @60 mm
read the correct family out to a 15 s hold with a 20–40-frame air buffer but was already wrong
at a 5 s hold with 80–120 (a rolling reference's median sits half a window in the past, and
that lag is baked into every measurement as drift).

**Family plane, live.** `Fe_spanner_01` was measured flipping ferrous → crossover at a ~15 s
hold, on an early-band mean of **+0.045 mV** — independently confirming the §17.9 offline
result and its mechanism. See §14.9.

**Bench observation, not a result:** with a candidate calibration running and
`cal_63_air_v2`-era signatures loaded — a deliberately mismatched profile — Shape Space still
tracked targets correctly on the family plane after a clean air grab. Consistent with the
band-axis features surviving a threshold re-anchoring, but it is an impression from a display,
not a measurement, and the sentinel recapture that would settle it has not been run.

### 17.11 `cal_63_air_bat_v3` locked — what the battery supply bought

*2026-07-26 · fw v4.26 · delaycal v1.26→v1.29 · pack 23.5 → 23.35 V · `cal_63_air_bat_v3`
locked, sha `4a2352d2` (§10)*

- **The supply change lowered the achievable convergence threshold, and this is the headline
  result of the epoch.** Convergence at a **0.3 mV** autonudge threshold was **never achievable
  under the bench PSU** — repeated attempts failed, which is why 0.5 mV became the working
  value. Under 6S the same sweep converged at 0.3 mV with **one cell of 63 needing a single
  −8 ns nudge**, where the nudge count would previously exceed 10 cells. Since that threshold
  is effectively a measure of how tightly a cell can be placed against the noise, this is a
  direct quantitative statement about the new supply. Contributing changes are **not separated**
  from one another: 6S pack, heavier cabling, ferrite common-mode chokes on power and USB, and
  100 nF across the pack.
- **A thermal convergence criterion replaces the thermistor check.** The TX damping-resistor
  thermistor is no longer fitted since the shielded case was built, so the old
  "calibrate once the resistor reaches ~80 °C" precondition **cannot be applied** *(that
  precondition is no longer stated in §14.1, which this bullet used to cite for it)*. Replaced by
  measuring the thing it was a proxy for — successive calibrations compared cell by cell:
  15 min after the first, differences up to **−24 ns** concentrated in the long-pulse bands;
  subsequent runs ~10 min apart, **±8 ns in 6 of 63 cells** and zero elsewhere. 8 ns is the PWM
  grid step, so those six cells are at the quantisation floor and the rig is as stable as the
  hardware can express. **Working criterion: converged when successive calibrations differ by
  no more than one grid step, watching the 100 µs band**, which is consistently the most
  drift-sensitive. delaycal's Compare Profiles tab (v1.28) is the tool for this.
- **The 4.40/3.80 V columns came back clean under battery**, which is why those two steps kept
  their original values while only the third moved (4.70 → 4.75 V, §10). Confirmed from a Std
  Dev rolling-N heatmap. Attributed at the time to the elevation having been "supply-borne" —
  meaning the failing bench PSU. **That attribution was later vindicated on much stronger
  evidence but for a different reason: it is pack voltage** (§17.13). The conclusion was right;
  the mechanism named was not. *(Precise 2026-07-31: the sweep ran at 23.5 → 23.35 V, which is
  in the **22.5–24.0 V transition band**, not in the 21.5–23.3 V window — this bullet used to
  say the pack "had drained into the good window". The reading is still explained, because soak
  is the second variable inside the transition and this rig was soaked; §17.13 measures 316 µV
  at 23.27 V soaked against 862 µV at 23.22 V freshly started. It does mean the "clean"
  confirmation was taken at the edge, which is why §10 recommends ~22.5 V for any re-lock.)*
- **Open at this point, resolved later:** whether the 4.70 V misbehaviour past ~30 min was drift
  into the ~4.45–4.65 V keep-out zone as the rig warmed (the §14.1 fingerprint) or a fresh
  mechanism. §17.13's moving-zone result supplies the explanation.

### 17.12 v3-epoch corpus campaign — the noise is a corner, and two supply nulls

*2026-07-28 · fw v4.26 · classviz v1.51→v1.62 · `cal_63_air_bat_v3` / `4a2352d2` · 6S battery ·
50 captures over four sessions 14:25–16:38 · `gui_signatures_targets_v3_20260728_142316.csv`*

- **The noise is a `(9 µs, 4.9 V)` corner, not a raised floor — 3 cells of 63.** Full result and
  the decision not to act on it in §14.11. **This corrects an earlier entry** which reported the
  floor as having doubled between the first two sessions of the day: that was drawn from 12
  captures and does not survive 50. Per-session `splithalf_floor` medians run 1.25 / 1.52 /
  1.77 / 1.67 mV — the floor sits at ~0.9 mV across the whole day. What actually changes is the
  **rate of excursions** (captures above 2.0 mV run 12 % → 25 % → 40 % → 47 %), while Spearman
  rank correlation against elapsed time is only **+0.10** over 133 min: the distribution is
  growing a tail, not shifting. Against amplitude the correlation is +0.15, so the metric is
  target-independent as intended. *(Caveat 2026-07-31: a rate rising monotonically across four
  consecutive sessions is itself a trend in the tail — the Spearman is computed over all
  captures and so tests the bulk, which is the thing it correctly reports as unchanged. It is
  not evidence that the tail growth is noise. Whether that growth is real is untested.)*
- **Two supply nulls, one of them acted on in advance.** Two batteries were swapped and left to
  settle partly on the strength of the retracted floor-doubling reading; **the swap changed
  nothing**, and the post-swap session is indistinguishable from the two before it. The pack
  also fell 23.77 → ~22.5 V across the day with no measurable effect — amplitude reproducibility
  for repeats of one placement held to ~6 %. The two **air** captures closing the day — the
  purest noise probe available, no target coupling — read **0.899 and 0.974 mV**, as clean as the
  best capture of the day. *(Both nulls are consistent with §17.13, with one correction made
  2026-07-31: the day **opened at 23.77 V, inside the 22.5–24.0 V transition band**, not
  "entirely inside the clean window" as this used to read, and dropped into the window as it
  went. A soaked rig reads clean through that band, which is the condition here, so the nulls
  stand — but the day was not the pure inside-the-window test it was described as.)*
- **Tested and rejected:** that the first capture at a placement is noisier than its repeat (the
  rig still settling after handling). Across 21 placements holding both r1 and r2, r1 was noisier
  in 10 and r2 in 11, medians 1.64 vs 1.67. No effect.
- **Air wander at the v3 operating point is 0.2–0.3 mV steady** and does not climb (pack
  21.59 V), against a working Detect of 0.5 mV — a ~2× margin, and better than the ~0.8 mV
  predicted from the §17.2 50 µV/s drift rate. This closed out the classviz v1.52 diagnosis: the
  same rig and setting read ~10 mV and creeping under v1.51, which was a ~200 s-old frozen air
  reference being displayed as a live deviation, **not** the detector (§14.1, §15).
- **Protocol adopted for the next session, and it paid off:** profile unchanged so both days sit
  in one epoch; a Std Dev heatmap before any target; and **an air capture at the start and end of
  every session** — the closing pair was the single most informative measurement of the day.
- **Corpus integrity.** Two in-place repairs were needed later (2026-07-30) and are recorded in
  `CHANGELOG.md`: eight captures renumbered for `repeat_idx` collisions caused by the classviz
  v1.62 bugs, and a ragged 26-field-under-25-column file caused by the features v9 column
  addition (migrated, not truncated — the orphaned field held a real pack voltage). Both are why
  the width check and the classviz v1.65 append fix exist (§15).

### 17.13 The pack-voltage result — state of charge reaches the operating point

*2026-07-29 19:17 → 2026-07-30 (last dump runs to 23:31) · **332 957 frames as analysed**, nine
session dumps, packs A and B ·
fw v4.26/v4.27 · classviz v1.63→v1.66 · `cal_63_air_bat_v3` / `4a2352d2` · free air ·
analysed with `pimd_features` v11 and `utilities/soak_vs_voltage/soakvolt.py` v1 ·
pre-registered predictions in `References/V3/NEXT_SESSION_soak_vs_voltage.md` §1 (§15)*

The most consequential measurement since the enclosure, and the one that corrects standing
ground truth in §12, §14.1 and §14.7. **Only possible because classviz v1.63 auto-logs** — these
are warm-up windows nobody would have pressed Record for.

> **Frame count is a snapshot** *(noted 2026-07-31)*: 332 957 is what the nine dumps held when
> the analysis ran, with the last dump still being written. The same nine files now hold
> **373 325** rows. Nothing downstream changes — the analysis is reproducible against the frames
> it used — but the figure is not a property of the campaign. *(A "435k frames" figure also
> appears in `CHANGELOG.md` for the same run and matches neither; see the errata entry.)*

> **Independently re-measured 2026-07-31, and it reproduces.** A drift-immune estimator
> (standard deviation of successive frame differences ÷ √2, which no warm-up slope can inflate)
> run over the same dumps returns the same structure: 3.80/4.40 V at 749/277 µV with 4.20 V
> clean at 83 µV on a fresh 24.90 V pack; the whole grid at one 57–72 µV floor mid-window; and
> at 21.08 V the trouble gone from 3.80/4.40 V (64/70 µV) and present at 4.20 V (173 µV).
> Absolute values run ~2.8× below the µV figures quoted in this section because the metric
> differs — compare ratios, not levels. The zone-migration model is now observed by two
> independent methods (§14.7).

**The metric was validated against the result it overturns before anything was concluded** — the
published column table reproduces at **r = 0.9960 across all 54 cells**. Same method, same
numbers: the disagreement was about **causation, not measurement**.

- **The transient lives in the 3.80 V and 4.40 V threshold columns; the other seven are flat
  from the first window to the last.** During warm-up those 14 cells of 63 contribute **68–75 %**
  of the whole `settle` figure — excluding them, the grid reads **0.141 mV cold, from minute one,
  unchanged for five hours.** 4.40 V clears in ~70 min and 3.80 V in ~2h50m, both landing on the
  same ~185 µV floor as their neighbours. **3.80 V is not a bad column** — it is where the
  warm-up shows up. This part stands unchanged from the first analysis.
- **The cause is pack voltage, not soak time.** The decisive measurement holds soak constant: the
  `# soak:` counters show `streamed_s` running continuously from the 17:10 session into the 20:52
  one, so the rig is at the **same thermal state, eleven minutes apart, 3.5 h into a continuous
  run**, and the only thing that changed is that the pack was swapped:

  | | 20:41:27 | 20:52:37 | |
  |---|---|---|---|
  | effective soak | 12 652 s | 12 963 s | +311 s — unchanged for this purpose |
  | pack (loaded) | **21.08 V** | **24.90 V** | pack A out, fresh pack B in |
  | **3.80 V column** | **189 µV** | **2090 µV** | **11.1× worse** |
  | 4.40 V column | 189 µV | 940 µV | 5.0× worse |
  | grid mean | 3404.0 mV | 3565.7 mV | +161.7 mV |

  A rig 3.5 h into a continuous run reading **worse than any cold start in the campaign** is not
  something soak time can produce — the soak hypothesis predicts ~185 µV there and is out by an
  order of magnitude. No model is needed to read this pair.
- **Ordered by voltage it is a threshold crossing, not a linear trend.** Above 24.0 V the 3.80 V
  column is *always* bad (1031–2090 µV) whatever the soak; below 22.5 V it is **usually**
  acceptable (189–502 µV); **22.5–24.0 V is the transition, and that is where soak is visible as
  the second variable** — at matched voltage, 23.27 V soaked 135 min reads 316 µV against
  23.22 V freshly started at 862 µV. So soak buys ~2.5–3× inside the transition band while
  voltage spans ~11× across its range. **Both are real; voltage dominates.**
  *(Softened from "*always* acceptable" 2026-07-31. Two measurements sit against the stronger
  claim: the 15:01 cold start, whose voltage corrects to ≈ 22.45 V — at or just below the edge —
  read 742 µV, ~4–5× its own floor by an independent estimator; and the 2026-07-24 survey read
  both columns elevated at 22.4 V, though under a different profile, §17.10. Below ~22.5 V the
  columns are usually at the floor, but a **cold** rig near the lower edge is not guaranteed
  clean.)*
- **The band signature identifies the mechanism, and the discriminator is the *sign*, not the
  correlation with pulse width** — both candidates have one:

  | | 9 | 13.44 | 20 | 30 | 45 | 67.2 | 100 | r vs log pw | sign |
  |---|---|---|---|---|---|---|---|---|---|
  | **pack 21.08 → 24.90 V** (mV) | +153 | +152 | +155 | +158 | +162 | +164 | +189 | +0.845 | **one sign, all bands** |
  | **post-stall thermal step** (mV) | −8.3 | −4.1 | +0.2 | +4.8 | +10.1 | +15.4 | +23.8 | +0.993 | **changes sign** |

  A supply change scales the whole decay so every band moves the same way; a thermal change
  re-times the drive so light and heavy bands move in **opposite** directions. Grid mean against
  pack voltage over all 17 slices: **43.3 mV/V, r = 0.962**; pack A alone (controlling for
  pack-to-pack internal resistance): **50.9 mV/V, r = 0.972**.
- **Pre-registered prediction, reported as the mixture it is.** For the 15:01 cold-start-on-a-flat
  -pack session, soak predicted the 3.80 V column starts bad at 1700–2100 µV; voltage predicted
  clean at 200–400 µV. It read **742 µV** — 2.3× better than soak predicted, 1.9× worse than
  voltage predicted. **Soak is falsified as the controlling variable, voltage is substantially
  right, and soak survives as a real secondary effect.** *(Voltage of this session corrected
  2026-07-31 to **≈ 22.45 V**, from ≈ 22.67 V. The load-settling correction had been taken from
  the 3.4-minute reading only; the session's own 25-minute point shows settling still running at
  0.88 V/h, ~3× the streaming drain, and back-extrapolating from the settled point gives
  22.45–22.47 V — which also reproduces the session's actual 15:36 reading, where 22.67 V does
  not. This puts the row at or just below the 22.5 V edge rather than inside the transition,
  which is why the "always acceptable below 22.5 V" wording above is softened. The prediction
  test itself is unaffected: 742 µV lies between the two predictions either way.)*
- **Operating window — the actionable result. Run the pack at 21.5 – 23.3 V** (3.58–3.88 V/cell).
  The missing constraint was the upper one: always-bad from ≈ 24.0 V, with 22.5–24.0 V a
  soak-sensitive transition, so ≈ 23.5 V is the practical onset to stay under rather than a
  hard edge. Floor ≈ 21.5 V is where trouble migrates
  to the 4.20 V / 4.75 V columns and the 9 µs band. Full numbers, capacity and the idle-drain
  consequence in §12. **A delay recalibration does not fix this** — a cal at 24.5 V re-anchors
  the delays so the zone falls between thresholds, but the zone moves with the pack, so the fix
  expires as the pack drains. **No profile change follows** (§10).
- **Why a careful analysis reached the wrong answer, recorded because the trap is general.** The
  effect is **non-monotonic in pack voltage** and all four of the original arguments were drawn
  from 22.3–24.4 V — the flat part, where the zone has already left the 3.80 V column and there
  is no sensitivity left to detect. Within one session soak and voltage are perfectly confounded
  (ρ 0.80–0.91 against either, identical magnitude), so **no within-session correlation could
  have separated them, and neither could more of the same data** — it needed a tool working
  *across* sessions that graded its own inputs. Of the four original arguments, one (the 47-min
  stall as an unintended cooling experiment) **survives and is genuinely thermal**; one was a
  zone signature misread as a refutation of the voltage domain — a uniform level shift cannot
  move two cells in opposite directions, but a zone sweeping the ladder does exactly that; and
  one remains **unexplained and open**: two sessions matched at 24.05 V and ~28 min still differ
  1.8×, most likely because DMM terminal voltage is not the pulse-instant rail (pack B measured
  25.04 no-load / 24.96 MCU-only / 24.75 V running). Nothing in the logs can separate a pack's
  internal resistance from its terminal voltage — that is §12's unmeasured quantity.
- **Nulls and negative results, recorded so they are not re-derived.** The **corpus cross-check
  is a null and cannot separate the two variables** — a property of the corpus, not the method:
  ρ(`splithalf_floor`, pack voltage) = −0.182 over mixed placements, the best-sampled placement
  sits inside a single morning session where voltage and soak still marched together, and the
  2026-07-28 captures **cannot be assigned a pack voltage at all** (they predate every reading,
  and are labelled `extrap` rather than silently used). `pack_v` is populated on only 10 of 166
  corpus captures, all the same held value. **`streamed_s` banks per classviz process, not across
  restarts** — which is *why* 17:10 and 20:52 form one continuous soak, so it is load-bearing
  rather than a footnote. The stall guard rejected 34 windows in the 07-29 dump on its own and
  **did not reproduce** the phantom 23:28 "noise relapse" an earlier pass had produced. The 08:28
  dump reads 14–16 mV on **all nine columns** in its opening minutes — a global stream-start
  event, excluded by an all-columns-elevated test rather than a hardcoded duration.
- **Next physical steps, in order.** (1) The **+15 V rail under scope during a TX pulse**, fresh
  pack vs near-flat — this analysis *infers* a supply mechanism from band geometry; that capture
  observes it directly and is the only way to settle the matched-voltage anomaly above (§12).
  (2) Repeat the §17.7 fine threshold sweep at **two stated pack voltages** (say 24.5 and
  22.0 V), which maps the zone's position on the decay and would turn this inference into a model
  (§14.7).

### 17.14 v3-corpus signature geometry — family is orientation, and the two-basis model holds

*2026-07-31 · `gui_signatures_targets_v3_20260728_142316.csv` · results 1–2 and 4–6 computed on
**170 captures / 25 targets** over eight sessions 07-28 → 07-30; result 3's oblique study was
captured the same day the Tilt input shipped and took the file to **188** ·
`cal_63_air_bat_v3` sha `4a2352d2` · fw 4.26 · 6S battery · gate = SNR ≥ 5 on `splithalf_floor`
unless stated. Compared throughout against the 2026-07-23 `targets_v1` corpus (66 captures,
`cal_63_air_v2`, bench PSU, §17.9). Tilt-recorded captures today: **13** — trivet at 0/30/60/90°
×2 reps, SS disc at 30/60/90°, all at 60 mm and `long_axis=z`, plus two axial solder-spool
captures.*

The corpus is 2.6× the first one and **deliberately spans orientation**, which is the whole
reason it says something new. Six results, the first two of which reframe §17.9.

- **1. "Ferrous vs crossover" is an orientation coordinate, not a material one.** The early-band
  sign — what separates the two in `pimd_shape.family()` — splits by *placement*: **90.9 %**
  accurate at `ax = y` (n = 22), **75.0 %** at `ax = x` (n = 16), **53.8 %** at `ax = z`
  (n = 13, i.e. chance). Every crossover→ferrous miss in the corpus is an axial capture.
  `Fe_Cast_iron_trivet_01` is the clean demonstration: flat (`ax = x`) it reads `crossover`,
  crossing 29–36 µs, early −50…−102 ×10⁻³; on edge (`ax = z`) it reads `ferrous`, crossing pinned
  at the 8 µs rail, early +7…+47 — and it is **2.4× louder on edge** (50.1 vs 20.9 mV L2 at
  60 mm). That is what a 3 mm-thick 75 mm disc must do: face-on the eddy loop has the full 75 mm
  of area and the fast negative term dominates the early bands; edge-on the loop area collapses
  to the 3 mm thickness and the magnetic term is left exposed. The spanner fails the other way,
  reading `crossover` broadside. So the early axis measures **presented eddy-loop area =
  geometry × orientation** and cannot be read as a material subclass. Decay persistence does not
  rescue the split (ferrous median 4.20, crossover 4.82, fully overlapping). Consequences in
  §14.9.
- **2. What survives is stronger than the old family verdict.** The *late*-band sign is the
  robust axis and does not need the gate:

  | tier | rule | accuracy |
  |---|---|---|
  | **1 — iron-bearing vs non-ferrous** | sign of late-band mean | **97.2 %** (141/145) **ungated**; 98.3 % gated |
  | 2 — ferrous vs crossover | sign of early-band mean | 76.5 % (39/51) gated — see result 1 |
  | combined 3-class (the v1 comparison) | current `family()` | 88.1 % gated, 85.5 % ungated |

  Decay persistence remains a clean independent second opinion on tier 1 — non-ferrous
  0.65–1.80, iron-bearing 2.12–9.02, **no overlap** (excluding the two contaminated captures of
  result 6). The `ferrite_toroid_01` contradiction **reproduces**: positive by sign, 1.51 by
  persistence — still the mineralised-ground preview, and still a case where both readouts are
  true (§17.9). A noise-scaled dead band on the early axis behaves as anticipated but is a
  coverage trade, not a fix: **1.5σ → 90.7 % on 92 % decided; 3σ → 95.7 % on 80 % decided.**
- **3. The Pasion–Oldenburg two-basis model is confirmed, including its actual content.**
  Placement records `long_axis` in the coil frame — z = axial, x and y = transverse (both in the
  coil plane, 90° apart). If a signature is a weighted mix of one axial and one transverse basis
  shape, x and y must be the *same* mix and every orientation set must be rank 2. Both hold:
  across the five targets holding both, **cos(x̄, ȳ) = 0.998 median, minimum 0.983** — the two
  transverse orientations are indistinguishable *even for a 210 mm spanner*, where a 90° in-plane
  rotation is a large physical change. All variation sits on the transverse↔axial contrast and is
  graded by geometry:

  | target | cos(transverse, axial) | rank-1 → rank-2 RMS residual | own repeat noise |
  |---|---|---|---|
  | Cu_pipe_01 (tube) | 0.991 | 0.137 → 0.109 | 0.114 |
  | Fe_Zn_gal_rhs_01 (tube) | 0.982 | 0.171 → 0.144 | 0.154 |
  | Fe_spanner_01 (irregular) | 0.986 | 0.183 → 0.131 | 0.144 |
  | Al_plate_01 (plate) | 0.950 | 0.153 → 0.099 | 0.042 |
  | Cu_Zn_brass_block_01 | 0.935 | 0.180 → 0.078 | 0.158 |
  | Fe_SS_disc_01 (thin disc) | 0.776 | 0.338 → **0.043** | 0.062 |
  | Fe_Cast_iron_trivet_01 (thin disc) | 0.736 | 0.446 → 0.266 | 0.320 |
  | Sn_Pb_solder_spool_01 (see result 6) | **−0.298** | 0.602 → 0.127 | 0.201 |

  Every anisotropic target collapses to its own electronics-noise floor at rank 2 and rank 3 buys
  nothing; rod-like targets are already rank 1, which the model permits. `Al_plate_01` is the
  only apparent counterexample and is not one — its residual correlates −0.82 with SNR and +0.54
  with distance, and within its best-sampled orientation (`ax = y`, n = 9) it is rank 1 at 0.048;
  the excess is marginal 300/360 mm captures sitting on the gate.

  **The model's actual content needed oblique captures, which no corpus had** — `long_axis` only
  takes x, y or z, so every capture sat at 0° or 90° and rank-2 structure alone is equally a
  consequence of "there are two placements and they differ". The Tilt input (classviz v1.67)
  closed that. Fitting each oblique capture as `v(θ) = a·v_axial + b·v_transverse` against the
  dipole prediction `a = cos²θ`, `b = sin²θ`, at 0/30/60/90° and 60 mm:

  | target | oblique fit error in `a` | in `b` | amplitude meas./pred. |
  |---|---|---|---|
  | `Fe_Cast_iron_trivet_01` | **−0.015 ± 0.036** | −0.010 ± 0.075 | 0.982 – 1.006 |
  | `Fe_SS_disc_01` | **+0.008 ± 0.048** | −0.035 ± 0.006 | 0.927 – 1.042 |

  Both coefficients land on the prediction within their scatter, and the **amplitude** — which
  the shape fit does not constrain — comes out right to within 2 % on the trivet. Every oblique
  capture is a **positive convex combination** of the two extremes (a, b ≥ 0 within noise,
  a + b ≈ 1): no extrapolation, no third component. Residuals run 4–21 % against a repeat-noise
  RMS of 9.4 % / 6.6 %. Every derived coordinate moves monotonically with tilt — trivet
  early-band mean **+35 → +17 → −22 → −58** (×10⁻³), crossing width **8.0 → 8.5 → 17.4 →
  30.8 µs**, amplitude 45.2 → 21.4 mV — so **the same object walks from `ferrous` to `crossover`
  as it is tipped**, confirming result 1 from a second direction.

  **Method warning, recorded because it is the kind of mistake that gets published: the fit must
  be done on raw vectors, not unit shapes.** Normalising each capture to unit length destroys the
  amplitude weighting the model predicts, and the unit-shape version reads *shallower* than
  cos²θ (0.83 / 0.46 at 30° / 60° against 0.75 / 0.25) — which would have been recorded as a
  partial failure of the model rather than an error of method.

  **What it changes:** orientation stops being a confound and becomes a *fitted parameter* —
  given a target's two basis shapes, θ is solvable from one capture, and an orientation-invariant
  descriptor (the 2-D subspace itself, not any signature in it) becomes well-defined. That is the
  foundation the τ-class + size tier needs. **Cost: two placements per target**, which were
  already being captured.
- **4. Placement variation is below the electronics noise floor — it is not the limiting factor.**
  Repeats at an identical placement tuple within a session were captured *without moving the
  target*, so they measure electronics alone; the same tuple recaptured in a later session
  necessarily involved re-placing it. The two distributions are the same, and the re-placed set
  is if anything tighter in the tail:

  | | n | median cos | p10 | min | median angle |
  |---|---|---|---|---|---|
  | same session (never moved) | 46 | 0.9894 | 0.9550 | 0.577 | 8.3° |
  | cross session (**re-placed**) | 37 | 0.9899 | 0.9675 | 0.948 | 8.1° |

  Across 11 tuples over four targets, **manual re-placement at a nominal (distance, orientation)
  contributes nothing measurable** on top of measurement noise. Amplitude repeatability at fixed
  placement: CV median 2.6 %, p90 9.6 %. Shape scatter does **not** saturate — it tracks SNR all
  the way down (13.4° at SNR 5–10, 7.8° at 10–20, 4.8° at 20–40, 2.6° at 40–100, 1.2° above 100)
  — but runs **2.4× the isotropic-additive-noise prediction** in 90 % of pairs. See §3: this is
  the same ~2× by which `splithalf_floor` understates reproducibility noise.
- **5. Noise — the 19 air captures are the best floor probe in the record.** The between-session
  component measures **zero** (within-session pooled per-cell σ 4.24 mV vs all-captures 4.03 mV
  across three days and eight sessions), so captures from different days are directly comparable
  (§3). The floor is **not flat**, and its dominant feature is **not** the §14.11 corner: **46 %
  of all noise energy sits in the 3.80 V column alone** (column L2 2.85 mV against 0.37–1.48 for
  the other eight), concentrated at long pulse widths, while the three corner cells carry 7 %.
  That is not a conflict with §17.12 — the corner came from matched target pairs within one
  afternoon, this is across-capture σ spanning the campaign — and the 3.80 V excess is **entirely
  confined to fresh-pack and cold-start captures** (24.40 V → 5.55 mV, 23.69 V → 4.39, cold pair
  4.85/6.15, against 0.64–2.06 for every settled capture in the 21.1–23.4 V window). §17.13's
  moving zone, showing up in target-free data: **a pack-state artefact operator discipline already
  removes, not a property of the profile.** The aggregate floor comparison against v1 looks
  unfavourable at face value (median `splithalf_floor` 1.245 → 1.784 mV, matched SNR ×0.73) but
  that is composition plus this tail, not a regression in the rebuilt supply — the 07-28 session
  *opens* at 1.25 median, indistinguishable from v1, and settled air captures close at 0.90–0.97.
- **6. Two data-integrity items, both isolated, both needing an operator decision.**
  `Sn_Pb_solder_spool_01` is a **different physical object across the epoch boundary** (§14.14,
  §15) — cross-epoch mean-shape cosine +0.143 against ≥ 0.95 for every other matched target, and
  the largest orientation effect in the corpus (cosine **−0.3 between its own two orientations**).
  Excluded from every aggregate above. And **one rogue capture** — `Fe_Cast_iron_trivet_01` @
  120 mm, `ax = x`, r1 — passes both quality gates at SNR 16.5 while sitting at cosine 0.33–0.68
  to every other trivet capture including its own r2 sibling (§14.13).

**The epoch change itself is benign**, and is written up where it is actionable: §10's
feature-portability paragraph. In short — coherent, one-parameter, predicted in sign and
direction by v3's later delay anchoring, and **no target changed its majority family verdict.**

### 17.15 The heatmap placement transient — instrumentation, not target physics

*2026-07-31 · answers the operator note at `TODO.md:112-115` · 41 timeable transitions from
9 targets across three relabelled dumps (`session_20260730_150124`, `_112854`, `_171026`)*

**The question.** Watching the Std Dev (rolling N) heatmap at 500/1000 µV while placing a target,
the grid "morphs to all yellow and back" — and *where the epicentre of that change sits appears
to vary with material*. Is it real, and is it being captured?

**It was not being captured, and it still is not, by design.** The transient is detected as a
single bit (`_sig_removal_armed`) and everywhere else defined as contamination — the settle gate
clears the buffer on any settle loss, `SETTLE_S_DEFAULT = 2.0` trims after every mark, and the
Settle tooltip says it outright: *"so target/air transitions … can't enter the window"*. The raw
material was on disk the whole time; nothing had ever read session frames as a per-cell time
series.

- **Most of the visible effect is the display, and this was predicted before measuring.** σ over
  a fixed 50-frame window straddling a step of per-cell amplitude `A` goes as `A·√(f(1−f))` —
  peaking at **`A/2`** half a window in (~3.6 s) and back to floor one window (~7.2 s) later. At
  the 500/1000 µV scale **any cell whose settled |Δ| exceeds ~2 mV saturates**, and a spanner at
  60 mm is 39 mV, i.e. peak σ ≈ 19 500 µV — **19× over the ceiling**. "All yellow" is guaranteed,
  and the apparent epicentre is the settled signature re-rendered through a saturating scale,
  which is material-dependent *by construction* with no time-domain physics required.
- **There is real per-cell structure, and it is scan order.** Timing each cell's 50 % crossing,
  the spread runs ~3× the noise prediction, and the trend is the sweep: slope of t50 against
  channel index **−5.6 ms/channel** (median), **−350 ms** across all 63 channels, against a
  144 ms sweep at 6.94 Hz, negative in **33 of 41** events. Cells are sampled sequentially within
  a sweep, so while the target is still moving, later-sampled cells see it closer and cross their
  halfway point earlier — direction and consistency both match. **The magnitude does not**:
  350 ms is 2.4× the sweep period, which sequential sampling alone does not explain. The 32-deep
  boxcar interacting with a monotonic per-channel offset is the obvious candidate but is
  **flagged, not asserted** — it cannot be settled without a controlled motion profile, which
  hand-placed captures are not.
- **The viscosity hypothesis is not supported, and the first answer was wrong.** Regressing out
  the scan-order trend and normalising by transition duration, the per-*event* test read iron
  0.090 vs non-ferrous 0.068, Mann-Whitney **p = 0.035** — apparently significant. It is not:
  those 41 events come from only **9 distinct targets** (one contributes 6, another 10), so the
  test was **pseudo-replicated**. Aggregating to one median per target first, the honest
  comparison is iron n=4 median 0.099 vs non-ferrous n=5 median 0.069, **p = 0.286**. With four
  iron targets the test has almost no power, so this is *"not shown"*, not *"shown absent"* — the
  direction is at least consistent with the hypothesis, and it would take a deliberate design
  (many targets, controlled placement) to say more.
- **No consistent placement/removal asymmetry either** — it runs both ways across targets and
  tracks transition duration rather than material.
- **What remains unexplained:** after scan-order removal the residual is still ~2.4–2.7× the
  noise prediction, for iron and non-ferrous alike. Something common to all materials is in
  there; hand-motion trajectory — which varies per event and is unrecorded — is the leading
  candidate.

**Bottom line for the operator: the effect is real to look at but is instrumentation, not target
physics. Nothing here justifies a new feature axis.** The one concrete change worth making was
unrelated to materials — the Std Dev heatmap's own defects, recorded as §14.12 and **fixed in
classviz v1.69** the same day.

## 18. Change Log Consolidation Pass.

You are performing a "human-run consolidation pass".
For THIS task only, you are authorised to edit DESIGN.md (the read-only rule is
suspended for this pass).

CHANGELOG.md is the source of truth for everything that has changed since the last
consolidation.  For this consolidation only focus on the lines in CHANGELOG.md above 
the marker: '<!-- Add new entries above this line. Format: ### <file> — v<N> — <short title> -->

IMPORTANT — the CHANGELOG is NOT in chronological order. Do not replay entries.
First determine the NET CURRENT STATE per file, then
synthesise. DESIGN.md is a consolidated snapshot, not a concatenation — keep the
existing "one-line summary, detail lives in source headers" philosophy.

Before editing, produce these for my review:
  1. Current version of each file (firmware, pimd_gui, pimd_classviz,
     pimd_delaycal) as you read them from the CHANGELOG.
  2. An asset mapping table: each existing DESIGN.md asset path → its Reference/
     target. Flag any old reference with no clear match, and any file in Reference/
     not yet cited anywhere — do NOT guess a match.
  3. Which DESIGN.md sections you'll change, and the net change for each (expect at
     least: header/Doc-rev line).
  4. Anything you plan to drop or significantly reword.

Preserve policy text and structure;  bump the Doc-rev line.  Fold new bench observations into §17. Do NOT delete content that is still accurate.

After I approve and you've updated DESIGN.md:
  - Reset CHANGELOG.md by moving the marker to the top of the file.
  - Adding  a line under the moved marker: '## Archive — consolidated YYYY-MM-DD'
