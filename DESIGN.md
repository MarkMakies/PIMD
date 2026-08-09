# Pulse Induction Metal Detector (PIMD)

**Author:** Mark Makies (Australia) · **Licence:** CC BY-SA 4.0
**Hardware rev:** 6.04 + shielded enclosure (2026-07-13) + 6S Li-ion supply (2026-07-24) + pack-voltage sense & DS18B20 board temperature (2026-08-07) · **Firmware:** v4.34 · **PC tools:** gui v4.17 · classviz v1.72 · delaycal v1.47 · rawlog v1.16 · features v14 · shape v1 · target_check v4 · corpus_check v1.9 · **Coil:** v4 · **Operating profile:** `cal_3x10_v2` (locked 2026-08-09, sha `def96704`, 3 × 10 = 30 cells). Bump this line on every edit.
**Last bench update:** 2026-08-09 (3×10 epoch opened; pack/temperature telemetry on all four PC tools)
**Doc rev:** 1.15.6 (2026-08-09) — **all "pre-enclosure" staleness framing removed.** The 2026-07-13
shielded-enclosure fit is **no longer treated as a measurement reset** — it did not materially move
what was being measured at the time *(operator assessment)*. §3's values stand as current; the epoch
row in §1 is re-attributed to **fw v4.24**, which changed Mode 2 boundary settling on the same day
and *did* void Mode 2 per-cell values and delay tables. Two enclosure references are kept because
they are build facts rather than staleness claims: the Hardware rev line, and §12's note that the
dissipation is trapped **inside a sealed enclosure**, which is the one place the enclosure genuinely
bites (§14.1). §12's supply-noise table keeps its **5S** caveat — a different supply, a real reason.
§14.2 is retitled and rescoped accordingly. The Doc-rev block itself is compressed to a terse
lineage, per the header convention in `CLAUDE.md`; full detail for every rev is in `CHANGELOG.md`.

*Rev lineage (detail in `CHANGELOG.md`):*
*1.15.5 — §10 epoch ledger dropped; §3 epoch tags condensed · 1.15.4 — §13/§10 design principles
corrected, they described the retired profile · 1.15.3 — staleness audit; R1 is 1.5k ∥ 10k as built;
ζ shown independent of R · 1.15.2 — post-consolidation audit fixes · 1.15.1 — legacy
critical-damping figure withdrawn as corroboration · 1.15 — §18 consolidation and deep trim,
2190 → 828 lines · 1.14 — the front end measured rather than inferred.*

> This file is self-contained: a new reader — human or AI agent — should be able to pick up the
> project cold from here alone. Empirically measured values are marked *(measured)*; everything
> else is nominal or design intent. **Detail, rationale and history live in `CHANGELOG.md`** —
> if you want to know *why* something is the way it is, search there, not here.

---

## 1. What this is, and current status

A pulse-induction (PI) metal detector designed and built from scratch since November 2023 by a
maker with no prior analogue-electronics background. It is **not** a clone; several choices are
deliberately unconventional (§13).

The detector is one payload of a larger system: it is towed on a trailer behind **Roverling**, an
autonomous RTK-GPS ground robot, so detection events can be tagged with centimetre-level position
and streamed over LoRa. It therefore has to be quiet, stable and remotely controllable, not merely
sensitive.

**Status — working and field-tested, not a bring-up project.** It discriminates ferrous from
non-ferrous targets in real soil, reliably to ~20 cm before the noise floor dominates.
**Mode 1 (filtered)** is mature and was used for all baselines and field tests. **Mode 2 (raw
profile sweep)** — the decay-curve / future-ML path — is operational and is where all current work
sits. Remaining work is **refinement** (thermal drift, supply noise) and the ML/classification
layer, not redesign.

**Where the project is, 2026-08-09.** The front end is now *measured* rather than inferred (§7),
and that measurement drove a new operating profile: `cal_3x10_v2`, 3 bands × 10 cells, whose ladder
steps over the front end's negative lobe entirely. The previous 63-cell epoch and its two corpora
are closed. **No corpus exists for the current epoch** — capture starts from zero, and that is the
immediate next task.

**Epoch discipline.** The rule each time is the same: frames from different profile geometries are
never mixed, and a measured value is only valid inside the epoch it was taken in (§10).

| epoch | opened | what it voided |
|---|---|---|
| fw v4.24 — Mode 2 boundary settling made time-floored | 2026-07-13 | Mode 2 per-cell values and delay tables |
| 6S pack replaces bench PSU | 2026-07-24 | *not* a measurement reset, but warm-up lengthened and pack voltage became an operating variable |
| `cal_3x10_v2`, front end measured | 2026-08-09 | both 63-cell corpora; all per-cell and crossing-ladder quantities |

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

**This convention holds only on cells sampled *before* the front end's negative lobe** *(§7)*. On
the 100 µs band that window is **sd 7.97–12.30 µs**, widest at 9.57 µs — steel **+46.5 mV**, copper
**−74.4 mV** against air. Past the lobe **both families read positive**, so sign is not a
discriminant there; the late window separates them by **decay rate** instead (copper outlasts
steel, crossing at ~44 µs on the coil and ~77 µs at 60 mm — the crossover moves with coupling). A
profile whose cells all sit past the lobe would show no polarity split at all. That is a property
of the sampling, not of the targets.

---

## 3. Measured operating envelope — treat as ground truth

> **Epoch — read this before quoting a number.** **`[63-cell]`** marks a value measured on the
> retired `cal_63*` grid: epoch-bound (§10), and its status on `cal_3x10_v2` is untested.
> Everything else stands as current. Some of these figures are old even so — §14.2 lists what is
> worth re-measuring on the present hardware.

- **Flyback** *(measured, 10 kHz / 40 µs)*: TX coil **−18 V to +265 V**, RX coil
  **−15 V to +135 V**. Gate turn-off **11.47 V → 0.44 V in 733 ns**.
- **FET Q1 limits:** < 10 A, < 300 µs, < 2 % duty. The detector deliberately runs above the duty
  note (§14.3).
- **RX front-end node** after R9: **−0.48 / +5.11 V**; ADC input settles
  **~5.0 V**; edge ring peaks **+5.30 / −0.69 V** (brief, current-limited, harmless). Topology in §7.
- **Signal-detect ceiling must be 5.0 V** in delaycal — the settled top of decay
  reads ~4.87–4.89 V on the heavy bands, and a 4.9 V ceiling false-triggers the coarse hunt.

**Noise — and the slope it was measured on.** A noise figure without the slope it was taken on is
not comparable to another one; on the decay slope what is measured is *slope × timing jitter*, not
amplifier noise.

| where | filtered (SDOA) | raw single sample (SDOB) |
|---|---|---|
| on the decay slope, DS 256 | ≈ **±200 µV** | ≈ **±1400 µV** |
| where slope vs delay ≈ 0 (past the lobe) | **14–15 µV** at DS 256 | per-sample σ **709 µV** at sd 30 µs |

⚠ **The two filtered-path figures in this document are not reconciled.** §3 gives ≈ ±200 µV on the
slope; §7 gives ≈ ±450 µV for SDOA and the boxcar arithmetic there is built on it. They differ by
2.25× apart. Neither has been re-measured on the current hardware; this is the first item on
the §14.2 backlog. The **raw** figure (±1400 µV) is consistent throughout and is what every boxcar
calculation in this document rests on.

The 13–30× spread between the two rows is the point: **the amplitude floor and the timing floor are
separate specifications.** Equivalent timing jitter across most of the grid is a near-uniform
**70–130 ps** **[63-cell]**; the exceptions (top thresholds, shortest and longest bands) reach
260–400 ps.

- **Sample-timing precision** ≈ **5 ns** *(measured)*.
- **Thermal drift** ≈ **−50 µV/s** at 10 kHz / 20 µs *(measured)*. The one direct check implies
  ≈ 35 µV/s, so 50 is an upper bound. **Reference age is therefore a hard ceiling on any
  frozen-reference measurement:** ~0.5 mV/cell at 10 s, 3.0 mV at 60 s, 7.5 mV at 150 s — a
  reference older than ~10 s already rivals a weak target. Always bracket air on both sides;
  interpolating between a reference before and after takes correct pairings to cos 0.996–1.000
  where a single earlier reference costs ~0.05 of cosine.
- **Standard Operating Conditions (SoC):** Mode 1 · 10.0 kHz / 20.0 µs pulse / 10.0 µs delay /
  DS 256 · coil in air, no targets. Reference capture:
  `References/images/GUI-steady-state-256-1024.jpg`. Two caveats, both live: the **4 min warm-up**
  figure was established on the **20 V bench supply that no longer exists** and **warm-up is longer
  on the 6S pack** (§12, §14.1) — treat 4 min as a floor, not a spec; and **on battery, SoC is not
  fully specified without a pack-voltage range**, because pack voltage reaches the operating point
  at 43–51 mV/V (§12).
- **Mode 2 warm-up ≈ 5 min** *(established 2026-07-02/03, on a light profile and on the bench
  supply — it did **not** hold for a 63-cell profile on battery, and is **untested on
  `cal_3x10_v2`*)*. Cold heavy bands drift up to ~250 ns in calibrated delay; soaked, repeat cals
  agree to ≤ 40 ns.
- **`splithalf_floor` understates reproducibility noise by ≈ 2×** *(measured)* **[63-cell]**. It is a
  within-capture statistic and does not see what moves between two captures. Across-capture L2 is
  **4.03 mV** against a median `splithalf_floor` of **1.82 mV**. Practical consequence: **the
  SNR ≥ 5 gate is really a reproducibility gate of ≈ 2.5–3.5**, which is why raising it keeps
  paying.
- **The between-session noise component measures zero** *(measured)* **[63-cell]**: within-session pooled σ
  **4.24 mV** vs all-captures **4.03 mV** across three days and eight sessions. Captures made on
  different days are directly comparable — which is what a training corpus needs.

---

## 4. System block diagram (text)

```
 6S Li-ion (19.8–25.2 V, working floor 21.0 V)
        │  F1 2A ─ D4 reverse-prot ─ FB1
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
  duty limits + damping (§14.3).
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
         │                              schematic v6.04 still draws a single 1.3k — §14.5)
         └─ R9 4.7k ──┬─ D2 1N4732 (4.7V zener) ─┐  (positive clamp)
                      │  D3 1N5819 (Schottky) ───┘  (negative clamp)
                      └─ 47R ─► LT6203 +input (single +12V supply)
```

- **R1 (shunt) is the RX damping resistor**, which also cleans up TX via mutual coupling.
  ⚠ **As built it is TWO resistors in parallel, and the schematic does not show this** *(§14.5)*:
  **1.5 kΩ ∥ 10 kΩ** (brown-green-red-gold ∥ brown-black-black-red-gold, both ±5 %) =
  **1304 Ω effective**. Schematic v6.04 still draws a single `R1 1.3k`. The value was evidently
  trimmed to land there, which is also the likeliest origin of the legacy "≈ 1.3–1.4k" bench note.
  1304 Ω is within **0.33 %** of the 1300 Ω the §7 fit assumes, so nothing downstream moves.
  By that fit the network sits at **ζ = 1.06 — just into over-damping**, which is the intent (§5).
  *(Treat the legacy "critical damping at ≈ 1.3–1.4k" band as **historical, not a range to pick
  from**: it is undated, predates the June 2026 front-end rework, and by the fitted values 1.4k is
  under-damped — see the ζ table.)*
- **R9 = 4.7k (series) is clamp current-limit only**, not damping.
- **D2 / D3** sit in series across the post-R9 node and conduct only outside ~0–5 V; between the
  rails the diodes are off and R1 does the damping.
- **47 Ω** between LT6203 output and ADC input limits over-range current into the ADC's protection.

### Preamp / ADC / references

- **U3 LT6203** dual high-speed op-amp, single +12 V.
- **U6 LTC2508-32**, 32-bit oversampling SAR with a configurable decimation filter **and** a
  no-latency raw output:
  - **SDOA (SPI1):** 32-bit filtered/decimated, `DRL` data-ready-low — the precision path
    *(≈ ±450 µV — **but see §3: this is unreconciled with §3's ≈ ±200 µV for the same path**)*.
  - **SDOB (SPI0):** no-latency raw 14-bit *(≈ ±1400 µV)* — the acquisition path.
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

**BUSY edge sync is required for accurate SDOB reads** *(fw v4.19)*: wait for BUSY-high (conversion
starts), then BUSY-low (complete), then read SDOB. Without it, reads landing mid-conversion produce
bit-truncated outliers at exactly **1/4 and 1/2** of the true value. Side effect: the BUSY-high
pulse at 10 kHz is ≈ 15 µs and MicroPython's polling loop catches ≈ 1-in-6, reducing effective raw
sample rate to ≈ 1.6 kHz. Accepted trade for accuracy.

**Mode 2 single-cell noise:** normal multi-cell sweeps give ≈ **310 µV** σ, matching the M = 16
boxcar expectation. A degenerate single-cell run where the PWM compare value never changes gives
≈ **24–30 mV** σ. Mechanism unconfirmed, finding reproducible. **Use Mode 1 for single-point
measurement; Mode 2 is for multi-cell sweeps.**

**Clip-release** — the instant the conditioned signal leaves the clamp rail (~4.7 V) and enters the
linear 0–5 V window — is the true earliest-valid sample time. `pimd_delaycal.py` measures it
directly.

### The front-end transient — measured at the amplifier input *(2026-08-08)*

A scope on the LT6203 input (CH1 post-R8; CH2 on MCLK, whose rising edge is the ADC sample instant,
so scope t = 0 *is* the sample delay) measures the whole decay including the part the ADC cannot
see. **This is the reference description of the front end; the ADC-side ladder constrains only the
volt-scale region and does not extrapolate past it.**

- **Two real poles with opposite-sign residues**, `V = A·e^(−t/τf) − B·e^(−t/τs) + V_q`:
  **τ_fast = 1.125 µs, τ_slow = 2.270 µs** *(measured)*, fit RMS 0.87 mV over 894 points. Exactly
  **one zero crossing** — it is not ringing.
- **ζ = 1.06 — mildly over-damped**, not critically damped. *(Do not re-derive this by assuming
  the critically-damped form and fitting τ = 2RC: that construction can only ever report ζ = 1.00,
  and it did, on 2026-08-07, before the two-pole fit replaced it.)*
- **The negative lobe is real, it is in air, and it is on every band.** At the input it spans
  **sd 14.3 → 18.0 µs**, bottoming **≈ −15 mV** *(measured)*. It is **not** amplifier overload
  recovery: it is present *before* the LT6203, and it **responds to metal** — a steel spanner on
  the coil removes the zero crossing entirely (minimum +15.5 mV, difference up to +48.9 mV).
  Damping is the wrong knob: changing R1 moves the poles apart or together but does not remove the
  crossing.
- **The ~16.5 mV pedestal is a front-end DC level**, not amplifier Vos and not ADC offset: input
  quiescent **+14.34 mV** *(measured, sd > 60 µs)* against **16.472 mV** at the ADC, so
  **input → ADC gain = 1.149**.
- **The output rails at 2.441 mV.** The signal path is unipolar, so everything below is clipped.
  Reconstructed through the gain, air really reaches **−16.9 mV in ADC terms** and is **below the
  rail for 4.21 µs, sd 14.23–18.44**.

### ⚠ Design constraint: no profile may sample inside the rail

Where air is clipped onto the 2.441 mV floor, **Δ = target − air understates the target by up to
~3.5×** (at sd 17.3 µs the ADC records **+6.3 mV** where the input shows **~+22 mV**). The
compression is non-linear and depends on target strength, so any band mean, crossing width or
amplitude feature computed over such a cell inherits that bias.

**The test is whether *air* is railed at that cell**, not whether the cell ever reads low — a close
ferrous target lifts the whole trace clear, so the same cell is live on a strong target and dead in
air.

**`cal_3x10_v2` samples no cell in that window** (§10), which closes this as a feature-maths problem
by construction — there is no guard in the feature code and none is needed while the geometry holds.
**Any new profile must clear sd 14.23–18.44, or exclude those cells from feature maths.**

### RX L and C — pinned *(2026-08-08)*

**ζ is the one number here that does not depend on R at all.** For a parallel RLC the two fitted
poles alone fix it:

> **ζ = (τ_f + τ_s) / (2 √(τ_f · τ_s)) = 1.0622**

L and C individually *do* scale with the assumed R (C ∝ 1/R, L ∝ R), but √(L/C) scales with R too,
so it cancels. **The over-damped verdict is therefore immune to the R1 uncertainty** — it would be
1.06 whether R1 is 1300 Ω, the as-built 1304 Ω, or either ±5 % corner. That is why it can be stated
flatly while the L and C below carry a caveat.

Taking the fitted poles with R1 = 1300 Ω gives **C = 579 pF**, **L = 4.41 mH**, √(L/C) = 2762 Ω and
**R_crit = ½√(L/C) = 1381 Ω**. *(With the as-built 1304 Ω these become 577 pF / 4.43 mH /
R_crit 1385 Ω — a 0.33 % shift, far inside the fit's own uncertainty, so the published pair is kept.
The old 3.9 mH / 311 pF was inferred from a resonance and is retired.)*

**Substitution sensitivity** — what happens if R1 is *changed*, holding the fitted L and C. Damping
is a **shunt**, so **lower R means more damping**. (Unlike ζ above, this table inherits the R = 1300
assumption through L and C, so read it as a guide to picking a resistor, not as a measurement.)

| R1 | ζ | |
|---|---|---|
| 1239 Ω — as-built pair, −5 % corner | 1.11 | over-damped |
| **1304 Ω — as built, nominal (1.5k ∥ 10k)** | **1.06** | **over-damped, the intent (§5)** |
| 1370 Ω — as-built pair, +5 % corner | **1.01** | over-damped, but **effectively critical** |
| 1380 Ω | 1.00 | critical |
| 1400 Ω | 0.99 | under-damped — ring returns |

**Read that table as design margin for a *future* substitution, not as uncertainty in the current
build.** This board's ζ is measured at 1.06 from its own poles regardless of what R1 turns out to
be. But if either part is replaced, the ±5 % pair spans **1239–1370 Ω**, and at the upper corner the
network would sit ~10 Ω from critical — so a worst-case pair has almost no margin. A single 1 %
part would remove that concern (§14.5).

**These values rest on the 2026-08-08 scope fit alone** — 894 points, residual RMS 0.87 mV, taken
at the amplifier input on the current hardware. *(An earlier rev cited the legacy "1300–1400 Ω
critical damping" bench note as independent corroboration and called that agreement the reason to
trust the fit. **That claim is withdrawn** (2026-08-09): the note is undated, predates the June 2026
front-end rework, and describes an RX network that may not be this one. It is not a check on the
current values, and the fit does not need it.)*

**Still to measure — and now more valuable, since the corroboration above was withdrawn:** a
**direct** RX self-resonance measurement, which is the only thing that would confirm L and C
independently of the transient fit. Also **R9 clamp current** (§14.5), and whether the
**MCLK-edge ring** (70 ns FWHM, ~250 ns tail) exists in the circuit as well as between scope
channels — the ADC samples on that edge, so if the coupling is real the converter captures the kick.

---

## 8. Digital / timing (RP2040)

- **MCU:** Waveshare RP2040-Zero (U10), MicroPython. Firmware `mcu/pimd_mcu.py` **v4.34**.
- **Pulse + sample generation:** two PWM channels on the **same slice** (GPIO4 = PWM2A drive,
  GPIO5 = PWM2B sample). Same slice ⇒ both rising edges align at period start; drive falls at
  `pulse_width`, sample falls at `pulse_width + sample_delay`. **This phase-locking is the core
  timing mechanism — never split these onto different slices** (§11). Timing precision ≈ 5 ns
  *(measured)*.
- **Pulse width** 5–50 µs typical (profiles reach 100 µs). **Sample delay** software-set, with an
  empirical `SAMPLE_PULSE_CORRECTION = 0.904 µs` offset between the PWM edge and the ADC trigger.
  Every delay the hardware can produce is a multiple of the **8 ns PWM grid**; an off-grid request
  is silently rounded.
- **Pulse rate** 5–50 kHz. A **prime-ish** rate halved noise by avoiding beat frequencies — the
  choice is deliberate. **Known-bad rate: 31.25 kHz** *(measured)* — at 31.25 kHz / 9 µs an entire
  band was unusable (three cells never settled, σ 2–5 mV); moving to 25 kHz with the pulse
  unchanged restored σ 0.02–0.10 mV. The noise followed the rep rate, not the pulse/decay
  alignment. Mechanism unconfirmed; **avoid 31.25 kHz in profiles.**
- **Mode 2 boundary settling is time-floored:** `max(BOUNDARY_PRIME = 15 periods,
  ceil(SETTLE_FLOOR_US = 3000 µs / period))`, and as of **v4.34** it is measured from the **config
  write (`t_cfg`)**, not from the top of the loop iteration. Before v4.34 the ~2.3 ms spent at the
  *previous* cell's configuration was deducted from this cell's budget, so delivered settle was as
  low as ~0.6 ms of an intended 3 ms — `SETTLE_FLOOR_US` was never an absolute floor on any band
  whose period is shorter than the per-cell interpreter time, i.e. every band in every profile.
- **Raw-read outlier gate is floored** *(v4.25)*: the plausibility gate compares against
  `abs(mean_raw)` with an absolute floor `OUTLIER_GATE_MIN = 164` raw14 counts (≈ 100 mV).
  Without the floor, a near-zero or negative rolling mean made the threshold ≤ 0, every sample was
  rejected, and the substituted mean froze that cell at its warm-up value forever.
- **IRQs stay disabled through the freq/CC writes** *(v4.26)*: `read_raw_bytes_hold()` extends the
  critical section from the BUSY-synced SPI read through the PWM freq/CC register writes. **The
  RP2040 CC register is not double-buffered**, so a late write leaves one conversion sampling at
  the previous cell's compare point, poisoning that cell's rolling average every sweep.
- **The Mode 2 emit can block, and the host can cause it** *(v4.27)*: the emit is a blocking
  `print()` to USB CDC, so a host that stops draining the pipe stalls the MCU *inside* it —
  observed for 47 minutes (§14.6). v4.27 **counts** rather than prevents: calls over
  `EMIT_BLOCK_WARN_MS = 50` increment `emit_block_count` / `emit_block_ms_max`, reported on `B`.
  Making the emit non-blocking is **deliberately not done** — it sits in the acquisition hot path
  and needs bench proof that MicroPython's rp2 port reports stdout writability at all.
- **Board temperature: DS18B20 on GP6** *(v4.33)*. 1-Wire, SKIP ROM, CRC-checked, 30 s cadence,
  3V3 normal 3-wire mode — **not** parasite power. An **external 4.7 kΩ pull-up is required**: the
  RP2040's internal pull-up is ~50–80 kΩ and fails intermittently once the lead is dressed
  *(measured)*. Cost is CPU-only (~2.2 ms to kick `CONVERT T`, ~7.6 ms to read the scratchpad, so
  one sweep in ~200 runs ~5 % long); the 750 ms conversion is never waited on inline.
  **`board_temp_dC = -32768` is the NO-READING sentinel** — the part's range is −55…+125 °C so
  there is no collision. RV7 on GP27 is retired as the temperature source.
- **SPI map:** SPI0 raw (SCKB GPIO2 / SDOB GPIO0 / BUSY GPIO15); SPI1 filtered (SCKA GPIO10 /
  SDOA GPIO8 / DRL GPIO9); SEL0 = GPIO12.

---

## 9. Serial protocol (both modes) — the firmware↔tooling contract

Two **mutually exclusive** acquisition modes over one serial link (115200 baud). Starting one
requires `E` first. *(Literal field separator is `", "` — comma-space — shown comma-only below;
parsers tolerate either. All timing fields are exact integers: freq in Hz, pulse and delay in ns.)*

**Mode 1 — filtered / interrupt-driven** (mature; all baselines & field tests):
- **in:** `S`/`s` start · `E`/`e` stop · `*<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>` configure
- **out:** `*<time_ms>,<value_uV>,<stddev_uV>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>`
- **rate:** pulse_freq / downsample (~20/s at 5 kHz / 256)

**Mode 2 — raw interleaved moving-average sweep** (the active path):
- **in:** `Q<n>` select profile · `G`/`g` start streaming · `E`/`e` stop ·
  `D<avg>;<freq_hz>,<pulse_us>,<d0>,…;…` define the RAM-only dynamic profile (index 5)
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
- `B` diagnostic counters, **reset-on-read** →
  `B<busy_high_count>,<overrun_count>,<emit_block_count>,<emit_block_ms_max>`. No parser exists in
  `src/` — read by a human over a serial terminal.
- `E` is the universal stop. Modes are mutually exclusive.

**µV scaling (invariant):** filtered (Mode 1) `raw32 * 5_000_000 // 2**31`; raw (Mode 2 / `A`)
`raw14 * 10_000_000 / 2**14`.

---

## 10. Scan profiles

Profiles are fixed/compiled-in or RAM constants (no flash writes). **Geometry is constant per
profile**, so any classifier is trained per profile and the table is the firmware↔ML contract.
**Frames from different profile geometries must never be mixed in one dataset.** An identical cell
count does *not* imply comparability — comparability rests entirely on the
`(profile_name, profile_sha8)` guard in `pimd_features`, **which must not be relaxed**.

**A profile is only fully specified together with a pack-voltage range.** On a bench supply the
operating point is fixed; on battery it is defined only inside a stated window, because pack voltage
scales the decay that the amplitude-anchored delays are cut against (43–51 mV/V, §12). Every lock
records the voltage it was swept at; every capture campaign states the window it ran in.

**Locked profiles are never edited in place.** A change means a new file and a new `name` — the
`name` field inside the JSON, not the filename, is what corpora record and what the cross-epoch
guard reports.

### Operating profile — `cal_3x10_v2` (locked 2026-08-09, sha `def96704`)

**3 bands × 10 cells = 30 channels**, `averages` 32, raw path (SDOB).
**Pack-voltage window: full charge down to 21.5 V** — the whole usable pack (§12).

| band | freq (kHz) | pulse (µs) | delays (µs) |
|---|---|---|---|
| 1 | 3.125 | 100.0 | 7.48 · 9.4 · 10.4 · 11.32 · 12.24 · 13.0 ⟦skip⟧ 30.0 · 45.0 · 60.0 · 120.0 |
| 2 | 5.0 | 50.0 | 6.912 · 8.816 · 9.824 · 10.832 · 11.664 · 12.352 ⟦skip⟧ 24.0 · 30.0 · 41.0 · 75.0 |
| 3 | 25.0 | 10.0 | 5.16 · 7.0 · 8.0 · 8.84 · 9.68 · 10.36 ⟦skip⟧ 18.44 · 20.0 · 23.0 · 29.0 |

**The shape is 6 early samples, a skipped span, then 4 late samples.** The skip is the front end's
negative lobe and rail (§7): 13→30 µs on the 100 µs band, 12→24 on the 50 µs, 10.36→18.44 on the
10 µs. **No cell sits inside sd 14.23–18.44**, which is the whole reason the profile exists — the
10 µs band's first late cell sits exactly on the measured rail exit.

**`threshold_v` semantics — read this before mining that column.** The six **early** values
(`4.85, 2.17, 1.05, 0.48, 0.19, 0.07`) are *measured* voltages at those delays. The four **late**
values (`0.017, 0.016, 0.015, 0.014`) are **placeholders for the ~16.5 mV pedestal, not
measurements**; the 1 mV steps exist only to keep the ladder monotonic. They are not four distinct
readings and must not be treated as such.

**Headroom note:** the 10 µs band's largest delay (29.0 µs) sits against a max valid delay of
**29.095 µs** — about 95 ns of margin before the 16-bit PWM duty overflows.

### Design principles — as they stand at `cal_3x10_v2`

⚠ **Two long-standing principles were dropped at this epoch.** Text describing the ×1.5 geometric
pulse ladder and a uniformly amplitude-anchored matrix describes `cal_72*`/`cal_63*` and **is not
true of the current profile.**

- **Three widely-spaced bands, not a geometric ladder.** Pulse widths are **100 / 50 / 10 µs** —
  ratios **2× and 5×**, deliberately uneven. The retired 63-cell profile used a **×1.5 geometric**
  ladder over seven bands, on the principle that constant-ratio spacing gives equal discrimination
  information per slice of log target-τ. That principle is **not in force here**: three bands cannot
  tile log-τ evenly, and this plan was chosen on the bench as the smallest set that still spans the
  target range. **The trade is resolution in τ for sweep rate**, and it is a bench judgement rather
  than a derived optimum.
- **Frequencies from the CLEAN_FREQS 125 MHz-divisor list** — 3125 / 5000 / 25000 Hz are all exact
  divisors, so `WRAP` is integer and the pulse ladder stays exact with duty absorbing the grid
  quantisation. Duties are 31.25 / 25 / 25 % (mean 27.1 %), keeping per-band heating roughly even.
  *This principle does carry across every epoch.*
- **The delay ladder is a hybrid, and that is the substantive change.** Two schemes in one band,
  for two different physics (§2):
  - **6 early cells, amplitude-anchored** on the volt-scale decay (4.85 → 0.07 V measured). These
    carry the polarity split, and they inherit the cost of amplitude anchoring — which cells are
    good is a function of pack state of charge, not a static property (§12). *Worth checking on the
    bench: §2's measured polarity window on the 100 µs band is **sd 7.97–12.30 µs**, and two of that
    band's six early cells sit outside it — **7.48 µs** (before) and **13.0 µs** (after). Not
    necessarily wrong, since that window was measured against one target pair and the ends are where
    the split narrows rather than vanishes, but it means the polarity split is carried by four cells
    on that band, not six.*
  - **4 late cells at fixed delays** out on the tail, landing on the ~16.5 mV pedestal. Past the
    front end's lobe both target families read positive, so sign is not a discriminant there and
    **decay rate** is what separates them. Time, not amplitude, is the right anchor for that.
  - **Nothing in between**, because the front end rails there (§7).
- **Fewer cells and fewer band boundaries is faster**, measured on one bench, one day, fw v4.34:

| geometry | sweep rate |
|---|---|
| 3 × 11 = 33 cells | **11.49 Hz** |

  *(Measured on **fw v4.34**, and rates from earlier firmware are not comparable: v4.34 delivers the
  full boundary settle it had previously been short-changing (§8), and that cost is paid once per
  band boundary per sweep — so it falls hardest on profiles with the most bands. `cal_3x10_v2` has
  30 cells in 3 bands and **has not been measured yet**.)*

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

- **Working discharge floor 21.0 V** (3.5 V/cell) — comfortably above the ≈ 18 V at which the 7815
  loses headroom, and coincident with the cells' own useful-capacity limit.

### Pack-voltage sense and failsafe — built and calibrated *(fw v4.29–v4.32)*

- **Divider 22 kΩ / 2.7 kΩ** off the `+20V` rail into GP26, 1 µF across the bottom leg, 1 kΩ +
  100 nF at the pin, all MCU-local, in RV8's vacated footprint. Thevenin 2.4 kΩ, drain 1.02 mA
  (≈ 0.2 % of pack), 23 mW in R_top.
- **`+20V` is the correct sense node** — D4 is a **shunt** clamp, not a series element, so there is
  no forward drop to correct for *(measured)*.
- **Calibrated on the bench, not from nominals:** divider ratio **9.18293** *(measured)* and
  **ADC_VREF = 3.2777 V** — the RP2040-Zero's own 3V3 LDO sits **0.67 % low**, worth 221 mV at full
  scale. **`PACK_VOLTAGE_FULLSCALE_MV = 30 083`**. **The LDO term is per-module — redo this
  calibration if the RP2040 module is swapped.**
- **Settling:** divider RC **τ = 2.9 ms measured**, ~22 ms to one LSB, hence
  `PACK_SENSE_SETTLE_MS = 100`.
- **Behaviour:** hard latch below **21.0 V**, **absent-suspend below 6 V** (so USB-only bench work
  is not blocked), and **re-arm requires 21.5 V** — not merely clearing the trip. Expect a
  `LOCKOUT:` line on the way down as the rail decays; it self-clears. The sweep stops during a pack
  swap — restart with `G`/`S`.
- ⚠ **C18 is a 4700 µF 25 V part on `+20V`**, at ~100 % of rating against a 25.2 V fresh pack. A
  35 V replacement is identified and **not yet fitted** (§14.4).


### Pack state of charge is an operating variable

**Pack voltage reaches the operating point: 43–51 mV/V over 21–25 V**, one sign across all bands,
r = 0.96–0.97 *(measured)*. 

**The data-quality window is a property of (pack voltage × profile delays), not of voltage alone.**
A noisy region sits at a **fixed place on the decay waveform** while pack voltage **scales the
decay**, so which threshold columns intersect it moves with the pack — and each profile's delays cut
the decay at different points.

- **Under `cal_3x10_v2`** the window is **full charge → 21.5 V**, the whole usable pack — a bench
  judgement for a profile whose delays are new and were cut against the front-end model, so it has
  no reason to inherit the old ladder's window. **Consistent with the mechanism above, not
  confirmation of it.** Every capture records the voltage it ran at (classviz writes `# pack_v:`
  automatically), so if the wide window costs quality at the top end, the track will show it.

**Capacity and drain, pack A** *(one full discharge, 21 settled readings)*: **620 streaming-minutes
(10.33 h) full to empty** at ~0.5 A average, implying **≈ 5.2 Ah** — about the rating of a 6S2P
ICR18650-26C pack. **Trust the runtime, not the curve's voltage axis**, which is an alignment of a
nominal OCV shape rather than a measured one.

**Known supply-noise facts** *(measured, free-air, 10-sample σ; taken on the **5S** pack that the
6S supply replaced, so the battery rows are stale — §14.2)*: ~200 µV USB no flash · ~250 µV battery no flash · ~900 µV USB using flash ·
~4000 µV battery using flash. **Writing to flash raises the noise floor ~10×** (§11).

---

## 13. What makes this design unusual (deliberate, validated choices)

- **Sampling high on the flyback decay — up to 4.85 V — rather than the usual bottom ~700 mV.**
  The early-decay region carries the most discrimination information and sits well above the noise
  floor. This is the oldest unconventional choice in the project and it still holds.
- **The profile spans almost the whole decay, and skips only the middle.** `cal_3x10_v2` runs from
  **4.85 V down to the ~16.5 mV pedestal** . The
  omitted region is not a design preference: it is where the unipolar front end rails (§7), and
  it is cut out of the *geometry* so that no downstream consumer has to know about it.
- **Two anchoring schemes in one profile — amplitude early, time late.** Conventionally a PI profile
  picks one. Here the early cells are anchored to *voltages* on the decay, because that is where
  target **polarity** separates families; the late cells are anchored to *delays* out on the tail,
  because past the front end's lobe both families read positive and only **decay rate** separates
  them (§2). Using one scheme for both halves would sample the wrong quantity in one of them.
- **The cost of amplitude anchoring, which was not anticipated:** the ladder is a fixed set of
  voltages sampling a decay whose scale moves with the pack, so "which cells are good" is not a
  static property of a profile (§12). This applies to the **six early cells**; the four late ones
  are time-anchored and do not inherit it.
- **Stepping over the front end's own artefact rather than correcting for it** (§7, §10). The null
  is real coil physics and it does carry target signal, but air is clipped there, so any cell in it
  biases every amplitude feature derived from it. Removing those cells from the geometry is cheaper
  and safer than teaching every downstream consumer about the rail.
- **The signature is a two-basis object, measured rather than assumed** *(established on the 63-cell
  corpora — conceptually intact, but unverified on this geometry, §14.9)*. Each target's orientation
  set is **rank 2** — one axial and one transverse basis shape — and an oblique pose is a positive
  convex combination landing on the arc between, with weights on the dipole prediction
  `cos²θ / sin²θ`. So the matrix carries enough structure to *solve for* orientation instead of
  being confounded by it, and an orientation-invariant descriptor is the 2-D subspace rather than
  any signature in it.

--

## 14. Open problems

1. **Thermal drift.** Wider pulses heat the TX damping/gate resistors; the drive circuit drifts and
   the RX side drifts with it. **Fingerprint:** heavy bands drift low, light bands high, monotonic
   with pulse width; warm recalibration moves delays by tens of ns. **The sign test that separates
   it from a supply shift:** a thermal shift moves light and heavy bands in *opposite* directions
   (r = +0.99 across bands); a supply shift moves all bands the same way. Mitigation: calibrate
   fully soaked. *(The historical "≈ 3 h warm-up" was mostly pack discharge, not thermal soak —
   the two were perfectly confounded before 2026-07-30. Thermal drift is real but the smaller
   effect.)*

2. **Re-measurement backlog.** Noise floors and drift rates are old, and the §12 supply-noise
   table's battery rows were taken on the **5S** pack the 6S supply replaced, so those are stale for
   a definite reason. **First item: the filtered path has two unreconciled figures** — §3's
   ≈ ±200 µV against §7's ≈ ±450 µV for the same SDOA path, 2.25× apart, and §7's boxcar arithmetic
   is built on the larger one. Nothing downstream depends on the filtered figure (the acquisition path
   is raw, where ±1400 µV is consistent throughout), which is why this has survived — but one of the
   two is wrong and the document should not carry both. Also open: the 7805-vs-USB noise mystery
   (onboard 7805 path ~50 % noisier than USB) and the flash-penalty rows. **When re-measuring,
   record which floor is being measured** — amplitude or timing (§3).

3. **Q1 duty headroom.** Present operating points run well above the schematic's < 2 % FET duty
   note; Q1 (IRF610) is being pushed past its noted SOA. A higher-rated replacement is probably
   warranted.

4. **C18 under-rated.** 4700 µF **25 V** on a rail that reaches 25.2 V on a fresh pack. 35 V
   replacement identified, not fitted.

5. **Schematic v6.04 does not match the build at R1, and R9's clamp current is unreconciled.**
   Two separate front-end documentation defects, both at the same node.
   *(a)* **R1 is two resistors in parallel on the board — 1.5 kΩ ∥ 10 kΩ, 1304 Ω effective — and the
   schematic draws a single 1.3k** *(§7)*. Electrically it is the value the fit assumes, to 0.33 %,
   so no measured result moves; but the schematic is the thing a future reader will trust, and it is
   wrong. **Update the schematic**, and while doing so consider whether a single 1 % part is
   preferable — the ±5 % pair's upper corner sits ~10 Ω from critical damping (§7 ζ table).
   *(b)* §7's +50 V "damped peak" implies ~9.6 mA through 4.7k, but §3 measures **+135 V at the RX
   coil**, which would imply ~28 mA. Either they are measured at different points or under different
   damping. A scope at the post-R9 node settles it. *Not* a claim the front end is out of spec — it
   has run for months.

6. **The host can block the MCU, and did — for 47 minutes.** The Mode 2 emit is a blocking `print()`
   to USB CDC (§8). v4.27 counts these on `B` but does not prevent them. Any PC tool that stops
   draining the serial pipe stalls acquisition. Watch `emit_block_count`.

7. **Possible TX coil-current plateau above ~67 µs.** In every calibration of the retired **×1.5
   geometric ladder** the 67 → 100 µs band-to-band clip-release increment was the smallest on the
   ladder, consistent with coil current flattening (τ_coil = L/R never measured). **The evidence is
   epoch-bound — `cal_3x10_v2` has no 67 µs band, so the comparison cannot be repeated on the
   current profile** — but the question matters more now, not less: the 100 µs band is one of three
   rather than one of seven, so it carries a third of the profile. Needs a scope on coil current vs
   pulse width, which does not depend on any profile.

---

## 15. Repository / file inventory

**One line per file: what it is, not what it has been.** Version history and design rationale live
in `CHANGELOG.md` and in each file's own header lineage.

| Path | Role |
|------|------|
| `mcu/pimd_mcu.py` | RP2040 MicroPython firmware (**v4.34**) — both modes, all profiles, the RAM-only dynamic profile (index 5), pack sense and board temperature. MicroPython **pure-Python only**. |
| `mcu/main.py` | One-line board launcher: `import pimd_mcu` |
| `src/pimd_gui.py` | **v4.17** — Mode 1 filtered-telemetry GUI. Pack SoC / board-temperature gauges; session logs to `data/sessions/gui_<ts>.csv`. |
| `src/pimd_classviz.py` | **v1.72** — Mode 2 signature visualiser and the **corpus-capture workbench**. Four tabs (Heatmap / Stats / Analysis / Family Plane). Loads and runs saved profiles as RAM-only dynamic profiles; auto-logs a self-describing session dump whenever the stream runs; registry-backed structured capture writing `src/data/corpora/`; pack/temperature telemetry written to the dump automatically. Profile *authoring* is not here — it is in delaycal. |
| `src/pimd_delaycal.py` | **v1.47** — delay-calibration sweeper and the only profile author. Coarse+fine two-phase sweep per (freq, pulse) pair, threshold-crossing delays snapped to the 8 ns grid, thermal soak monitoring, auto-nudge, Compare Profiles tab, pack/temperature gauges and a conditions span recorded into every exported profile's notes. **Import Profile first** when recalibrating — persisted settings are not anchored to the locked profile (§16). |
| `src/pimd_rawlog.py` | **v1.16** — deliberately dumb raw logger: loads a profile, streams it, writes every firmware line **verbatim** to `data/sessions/rawlog_<ts>.txt`. No tables, no derived values, so it cannot develop display-layer defects. **Ground truth for offline work.** Acquisitions are self-bracketing. Geometry-agnostic. |
| `src/pimd_shape.py` | **v1** — shared signature-geometry maths (pure NumPy, **no Qt**). `unit_shape` / `amp_l2` / `snr`, `band_means`, `band_range_mean`, `crossing_us`, `decay_persistence`, `family`. Geometry always passed explicitly; bands and thresholds resolved **by value**, never by stored index. `family` (sign) and `decay_persistence` (magnitude) are read together and neither overrules the other. |
| `src/pimd_features.py` | **v14** — session-CSV → training-corpus builder (offline CLI). Registry join, **hard geometry guard: one `(profile_name, profile_sha8)` per corpus build**. Parses the dump's `# pack_v:` / `# soak:` / `# stall:` / `# capture:` / `# mark:` comment tracks; `pack_v_at()` interpolates a voltage per capture. |
| `src/pimd_target_check.py` | **v4** — target-registry loader/validator (CLI + library). `DEFAULT_REGISTRY_PATH` here is the single source of truth for registry location. `-f` is required — there is no default path. |
| `src/pimd_corpus_check.py` | **v1.9** — corpus-level acceptance checker. Shape distance-invariance, split-half SNR, repeat consistency, falloff fit. One flat PASS/AMBER/FAIL/SKIP table, exit 1 on any FAIL, so it can gate a capture day. |
| `src/data/profiles/` | Locked profiles (§10). **Only the operating profile is tracked** — `cal_3x10_v2.json`; each superseded lock is added to `.gitignore` as it is retired but kept on disk and stays usable as a delaycal comparison reference. |
| `src/data/targets/targets_v3.csv` | Human-authored target registry, **current**, 27 objects. Human-owned: tooling reads and validates only, never writes. `targets_v1.csv` is retained for reading the 2026-07-23 corpus. |
| `src/data/corpora/` | Signature corpora (`gui_signatures_*.csv`). Both files on disk are **63-cell previous-epoch** and cannot be mixed into the current 30-cell epoch. Untracked, so **git cannot restore a damaged corpus** — back up before any in-place edit. |
| `src/data/sessions/` | Raw Mode 2 session dumps — self-describing CSV with embedded profile JSON, per-column map, marks and comment tracks; plus rawlog's verbatim `.txt`. Written automatically whenever the stream runs, ~220 KB/min. Untracked and **not reconstructable after the fact.** |
| `src/data/scratch/` | Scratch captures of **unregistered** objects. Never written into `corpora/` — a corpus build hard-errors on an unregistered `target_id` and that guard stays. |
| `References/images/` | Schematics, scope and GUI reference captures (§15 note below). |
| `USAGE.md` | Per-app usage guide — intent, operation and pipeline flow for the firmware and each PC tool. |
| `CHANGELOG.md` | Running change log — **the source this file is consolidated from**, and where all history and rationale lives. |
| `DESIGN.md` | **This file** — curated snapshot. Do not edit directly outside a consolidation pass (§18). |
| `CLAUDE.md` | AI-agent working brief — how to behave in this repo. Not project facts. |

**Key reference images** (all in `References/images/`): `schematic-v604.jpg` and
`schematic-v604-sheet2.jpg` (rev 6.04, current front end) ·
`lobe_at_amp_input_20260808.png` and `spanner_fills_the_null_20260808.png` (the §7 front-end
measurement, and a steel target filling the null) · `decay_model.png` (the fitted front-end model) ·
`6S-pack-discharge-curve.jpg` (§12) · `GUI-steady-state-256-1024.jpg` (the SoC reference capture) ·
`warmup-with-8ns-steps.jpg` (why delays snap to the 8 ns grid).

**Retired 2026-08-09** and recoverable from git history only: `utilities/` (decay model, pack
discharge, soak-vs-voltage, session relabel, mode-2 noise tools), `ML/`, `References/scope/` (the
raw scope CSVs behind §7), `References/Targets v1 Analysis/`, `src/pimd_classify.py`,
`src/pimd_v2_findings.py`. Their **findings stand** — they are in `CHANGELOG.md` — but are no longer
re-runnable from a clone. The former rule that a utility cited from `CHANGELOG.md` must be tracked
is retired with the directory it guarded.

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

# Offline: feature-maths acceptance check. NOTE (§14.9): expectations are hard-coded
# from the 2026-07-23 cal_63_air_v2 analysis, so this FAILs against any other epoch.
python pimd_shape.py --selftest data/corpora/gui_signatures_targets_v1_20260723.csv

# Offline: corpus acceptance checks (exit 1 on any FAIL, so it can gate a capture day).
# NOTE (§14.9): the v3-corpus FAILs were never diagnosed. Read the table, not the exit code.
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
B                     → diagnostic counters (reset-on-read)
Q4  then  G           → Mode 2 streaming, static CLASSIFY_EP profile;  E to stop
*5000,40000,8400,256  then S → Mode 1 streaming (~20/s);  E to stop
A32                   → one raw boxcar average (R record), idle/Mode 1 only
```

---

## 17. Standing measured facts

> Everything here is a *conclusion*, with the epoch it belongs to. The experiments, the reasoning
> and the results that were superseded along the way are in `CHANGELOG.md` — search by date.
> **Any figure taken under a retired profile is epoch-bound** (§1, §10).

| # | Fact | Epoch |
|---|---|---|
| 17.1 | **Power draw ~0.5 A average** streaming; drive current and heating scale with pulse width and duty. Measured on the 63-cell profile (mean band duty 28.1 %); `cal_3x10_v2`'s mean band duty is **27.1 %**, so the figure should carry — *inferred from duty, not re-measured*. The §12 capacity numbers depend on it. | 63-cell → current |
| 17.2 | **The front end is two real poles with opposite-sign residues** — τ_fast 1.125 µs, τ_slow 2.270 µs, ζ 1.06 — giving exactly one zero crossing, a negative lobe at sd 14.3–18.0 µs, a 16.5 mV pedestal and a 2.441 mV output rail. Measured on a scope at the amplifier input, not inferred from the ladder (§7). | current |
| 17.3 | **The null responds to metal.** A steel spanner on the coil removes the zero crossing entirely (min +15.5 mV, difference up to +48.9 mV at sd 13.57 µs). It is real coil physics, not an amplifier artefact. | current |
| 17.4 | **Where air is railed, measured target delta is compressed up to ~3.5×**, non-linearly and by an amount depending on target strength. Closed by geometry in `cal_3x10_v2` (§7). | current |
| 17.5 | **Sweep rate is set by cell count and band count:** 63 cells 6.49 Hz · 45 cells 8.77 Hz · 33 cells 11.49 Hz, one bench, one day, fw v4.34 (§10). | current |
| 17.6 | **Pack voltage reaches the operating point at 43–51 mV/V over 21–25 V**, r = 0.96–0.97; does not generalise beyond that span (§12). | 6S |
| 17.7 | **Pack capacity ≈ 5.2 Ah / 10.33 streaming-hours** full to empty; idle drain is ~15× lower than streaming, so a fresh pack cannot be idled into a window (§12). | 6S |
| 17.8 | **The data-quality noise zone sits at a fixed place on the decay while pack voltage scales the decay** — so which threshold columns it hits is a function of state of charge, not a static profile property. Mechanism of *why that region is noisy* remains open (§14.8). | 63-cell |
| 17.9 | **Thermal and supply drift are separable by sign:** thermal moves light and heavy bands in opposite directions (r = +0.99 across bands); supply moves all bands the same way (§14.1). | all |
| 17.10 | **Reference age is a hard ceiling on frozen-reference measurement** — ~0.5 mV/cell at 10 s, 7.5 mV at 150 s. Air must be bracketed both sides; interpolation takes correct pairings to cos 0.996–1.000 (§3). | all |
| 17.11 | **`splithalf_floor` understates reproducibility noise ≈ 2×**, so the SNR ≥ 5 gate is really a reproducibility gate of ≈ 2.5–3.5 (§3). | 63-cell |
| 17.12 | **The between-session noise component measures zero** (4.24 vs 4.03 mV over three days, eight sessions) — captures from different days are directly comparable (§3). | 63-cell |
| 17.13 | **Family is an orientation coordinate, not a material one.** The early-band sign splits by *placement*: 90.9 % accurate transverse, 53.8 % axial. The **late**-band sign — iron-bearing vs non-ferrous — is the robust axis at **97.2 % ungated**. | 63-cell |
| 17.14 | **The signature is rank 2 in orientation** and the Pasion–Oldenburg two-basis mixing law is confirmed on oblique captures, so orientation becomes a fitted parameter rather than a confound (§13). | 63-cell |
| 17.15 | **The cell-0 outlier population is caused by the blocking emit**, not by the band boundary, settling or dwell. A within-run factorial (the same band duplicated at sweep positions 0 and 30) gave 151 events at position 0 and zero at position 30 in the same sweeps. Remaining candidate is USB TX burst coupling into the front end — a scope question (§14.6). | current |
| 17.16 | **31.25 kHz is a bad rep rate** — an entire band unusable at 31.25 kHz / 9 µs, restored by moving to 25 kHz with the pulse unchanged. Noise followed the rep rate, not the decay alignment (§8). | all |
| 17.17 | **Boundary settle was being under-delivered until fw v4.34** — measured from the loop top rather than the config write, so a 3 ms budget could deliver ~0.6 ms. `SETTLE_FLOOR_US` was never an absolute floor on any band whose period is shorter than the per-cell interpreter time (§8). | current |

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
