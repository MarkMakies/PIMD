# Pulse Induction Metal Detector (PIMD)

**Author:** Mark Makies (Australia) · **Licence:** CC BY-SA 4.0
**Hardware rev:** 6.04 + shielded enclosure (2026-07-13) + 6S Li-ion supply (2026-07-24) + pack-voltage sense & DS18B20 board temperature (2026-08-07) + **RX front-end +97 mV bias (2026-08-10)** · **Firmware:** v4.35 · **PC tools:** gui v4.17 · classviz v1.73 · delaycal v1.48 · rawlog v1.16 · features v14 · shape v1 · target_check v4 · corpus_check v1.9 · **Coil:** v4 · **Operating profile:** `cal_3x10_v5` (2026-08-11, 3 × 10 = 30 cells, **not locked, no corpus**). Bump this line on every edit.
**Last bench update:** 2026-08-11 (bias mod fitted and characterised; fw v4.35 bench-verified; `cal_3x10_v5` hand-tuned)
**Doc rev:** 1.16 (2026-08-11) — **§18 consolidation.** The front end is **biased +97 mV** (§7), so
its negative lobe now sits inside the linear window instead of on the output rail. That reverses the
constraint the last three profiles were built around: **"no profile may sample inside the rail" is
retired**, and the null it protected against is measured to be the **best-SNR region on the ladder**
with a discriminant of its own (§2). The operating profile is **`cal_3x10_v5`** (§10) — hand-tuned,
nothing railed, two cells placed *on* the null, and the first four cells amplitude-anchored to the
**same voltages in all three bands**. Firmware **v4.35** removes the outlier gate's absorbing state
(§8). **All pre-mod front-end voltages are void** and §7's 2026-08-08 scope fit needs re-taking on
its own account (§14.2). Every superseded profile is **cut as design material** — the `cal_3x10_v1…v4`,
`cal_72*` and `cal_110*` locks are out of the working tree and recoverable from git history only;
the two `cal_63*` files that remain exist solely because the two corpora were captured against them.

*Rev lineage (detail in `CHANGELOG.md`):*
*1.15.7 — content already carried by `CHANGELOG.md` cut · 1.15.6 — the 2026-07-13 enclosure is not a
measurement epoch · 1.15.5 — §10 epoch ledger dropped; §3 epoch tags condensed · 1.15.4 — §13/§10
design principles corrected, they described the retired profile · 1.15.3 — staleness audit; R1 is
1.5k ∥ 10k as built; ζ shown independent of R · 1.15.1 — legacy critical-damping figure withdrawn as
corroboration · 1.15 — §18 consolidation and deep trim, 2190 → 828 lines.*

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

**Where the project is, 2026-08-11.** The RX front end has been **biased ~97 mV** so the whole
transient sits inside the amplifier's linear window (§7). That reversed a design decision three
profiles had been built around: the front end's negative lobe was treated as a hole to step over,
and measured properly it is the **highest-SNR region on the ladder** and carries a discriminant the
rest of the decay does not (§2). The operating profile is `cal_3x10_v5` — 3 bands × 10 cells, no
cell railed, two cells placed *on* the null, and the first four cells anchored to the same voltages
in every band. **It is not locked and no corpus exists for it.** Capture is the immediate next task
and one measurement gates it (§14.8).

**Epoch discipline.** The rule each time is the same: frames from different profile geometries are
never mixed, and a measured value is only valid inside the epoch it was taken in (§10).

| epoch | opened | what it voided |
|---|---|---|
| fw v4.24 — Mode 2 boundary settling made time-floored | 2026-07-13 | Mode 2 per-cell values and delay tables |
| 6S pack replaces bench PSU | 2026-07-24 | *not* a measurement reset, but warm-up lengthened and pack voltage became an operating variable |
| **RX front-end +97 mV bias**, and `cal_3x10_v5` with it | 2026-08-10 | **every pre-mod voltage in the signal path** — the whole threshold ladder, §7's scope fit, and the two 63-cell corpora (already void at the 3 × 10 change) |

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

**Three separate discriminants sit at three places on the decay, and the profile is cut to reach
all three** *(§10)*. Which one is available is a property of *where you sample*, not of the targets.

**1 — Early: polarity.** Before the front end's negative lobe, sign splits the families. On the
100 µs band that window is **sd 7.97–12.30 µs**, widest at 9.57 µs — steel **+46.5 mV**, copper
**−74.4 mV** against air. *(Measured pre-bias. A DC offset does not move a target−air delta, so
these should carry, but they have not been re-taken since the mod.)* The crossing where a
non-ferrous target stops reading negative and starts reading positive **marches earlier with
shorter pulse** — brass crosses at **~12.3 µs** on the 50 µs band and **~11.7 µs** on the 10 µs.

**2 — Through the null: fill depth.** Inside the lobe **both families read positive against air**,
because air is the thing that dips and both targets fill the dip in. Sign is useless there; depth
is the measurement. Defining **fill = 1 − (target dip depth / air dip depth)**, each depth taken
against that trace's own late level *(measured 2026-08-10, targets at 0 cm — see §14.8)*:

| band | brass fill | steel fill |
|---|---|---|
| 100 µs | 52 % | **100 %** — monotonic, no dip at all |
| 50 µs | 38 % | **100 %** — monotonic |
| 10 µs | **8 %** | 62 % |

The families are **7× apart on the shortest pulse and 2× on the longest**; the metric saturates at
100 %, so the two steel figures are floors. This is a τ probe read through the null rather than
through amplitude. Two riders: **on the 10 µs band brass and air are only 3–5 mV apart across the
whole null**, at or below that band's fit RMS, so the 7× ratio there is carried by the ferrous side
alone — and **past the bottom, steel's slope is opposite to air's and brass's** (100 µs band: air
67 → 91 mV and brass 94 → 111 mV over the following 4 µs while steel falls 254 → 223 mV). **The
sign of the slope is a cleaner discriminator than the levels**, and reading it needs at least two
cells past each band's null bottom — a placement constraint nothing else here implies.

**3 — Late: decay rate.** Out on the pedestal both families read positive and only decay rate
separates them (copper outlasts steel, crossing at ~44 µs on the coil and ~77 µs at 60 mm — the
crossover moves with coupling). A ferrous target adds a genuine **second, slow pole** of its own
that air and non-ferrous do not have *(§7)*.

---

## 3. Measured operating envelope — treat as ground truth

> **Epoch — read this before quoting a number.** **`[prev-epoch]`** marks a value measured on the
> retired 63-cell grid: epoch-bound (§10), untested on `cal_3x10_v5`. **Anything describing a
> voltage in the signal path predates the +97 mV bias mod unless it says otherwise** (§7, §14.2).
> Everything else stands as current. Some figures are old even so — §14.2 lists what is worth
> re-measuring on the present hardware.

- **Flyback** *(measured, 10 kHz / 40 µs)*: TX coil **−18 V to +265 V**, RX coil
  **−15 V to +135 V**. Gate turn-off **11.47 V → 0.44 V in 733 ns**.
- **FET Q1 limits:** < 10 A, < 300 µs, < 2 % duty. The detector deliberately runs above the duty
  note (§14.3).
- **RX front-end node** after R9: **−0.48 / +5.11 V**; ADC input settles
  **~5.0 V**; edge ring peaks **+5.30 / −0.69 V** (brief, current-limited, harmless). Topology in §7.
- **Post-bias, air never goes below 67.2 mV** *(measured 2026-08-10, worst case = 100 µs band)*
  against the amplifier's 2.441 mV output floor — every cell in the previously-railed window, on
  all three bands, now has ≥ 65 mV of headroom underneath it (§7).
- **Signal-detect ceiling must be 5.0 V** in delaycal — the settled top of decay
  reads ~4.87–4.89 V on the heavy bands, and a 4.9 V ceiling false-triggers the coarse hunt.
  **Top-end headroom is now tighter**: the bias lifts everything ~97 mV, so what read 4.85 V reads
  ~4.95 V against 5.000 V full scale. `cal_3x10_v5` deals with this by anchoring its top cell at
  **2.4 V** instead (§10); any re-cut must not put a cell back up against the rail.

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
**70–130 ps** **[prev-epoch]**; the exceptions (top thresholds, shortest and longest bands) reach
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
  `cal_3x10_v5`*)*. Cold heavy bands drift up to ~250 ns in calibrated delay; soaked, repeat cals
  agree to ≤ 40 ns.
- **Board temperature moves the operating point, and it moves it *up* on cooling** *(measured
  2026-08-10/11)*: the same cell that sat 46.7 % of the time at positive full scale on a 52.5 °C
  board was **100 % railed at 31.5 °C**. Together with pack scaling (§12) this means **which cells
  are usable is a function of board temperature and state of charge, not a static property of the
  ladder** — the direct cost of amplitude anchoring (§13).
- **`splithalf_floor` understates reproducibility noise by ≈ 2×** *(measured)* **[prev-epoch]**. It is a
  within-capture statistic and does not see what moves between two captures. Across-capture L2 is
  **4.03 mV** against a median `splithalf_floor` of **1.82 mV**. Practical consequence: **the
  SNR ≥ 5 gate is really a reproducibility gate of ≈ 2.5–3.5**, which is why raising it keeps
  paying.
- **The between-session noise component measures zero** *(measured)* **[prev-epoch]**: within-session pooled σ
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
                      └─ 47R ─┬─► U3A LT6203 +input, pin 3 (single +12V supply)
                              │
    U5 pin 7 (5V-REF) ─[240k 1% metal film]─┘   +97 mV bias — fitted 2026-08-10, NOT on the
                                                schematic (§14.5)
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

### The front-end transient — measured at the amplifier input

A scope on the LT6203 input (CH1 post-R8; CH2 on MCLK, whose rising edge is the ADC sample instant,
so scope t = 0 *is* the sample delay) measures the whole decay including the part the ADC cannot
see. **This is the reference description of the front end; the ADC-side ladder constrains only the
volt-scale region and does not extrapolate past it.**

**Shape — from the 2026-08-08 fit, and the shape is what survives:**

- **Two real poles with opposite-sign residues**, `V = A·e^(−t/τf) − B·e^(−t/τs) + V_q`:
  **τ_fast = 1.125 µs, τ_slow = 2.270 µs** *(measured)*, fit RMS 0.87 mV over 894 points. Exactly
  **one zero crossing** — it is not ringing.
- **ζ = 1.06 — mildly over-damped**, not critically damped. *(Do not re-derive this by assuming
  the critically-damped form and fitting τ = 2RC: that construction can only ever report ζ = 1.00,
  and it did, on 2026-08-07, before the two-pole fit replaced it.)*
- **The negative lobe is real, it is in air, and it is on every band.** It is **not** amplifier
  overload recovery: it is present *before* the LT6203, and it **responds to metal** — a steel
  spanner on the coil removes the zero crossing entirely (minimum +15.5 mV, difference up to
  +48.9 mV). Damping is the wrong knob: changing R1 moves the poles apart or together but does not
  remove the crossing.
- **The pedestal is a front-end DC level**, not amplifier Vos and not ADC offset. **Input → ADC
  gain = 1.149** *(measured)*.

⚠ **The 2026-08-08 *voltages* are void; only the shape and the gain carry.** Between that capture
and 2026-08-10 the air lobe deepened **29.3 → 38.2 mV below quiescent**, and the bias cannot do
that — a 240 k shunt attenuates ~2 %, which makes a lobe shallower, not deeper. **The replaced 7815
is the likely cause**, which means the pole fit itself wants re-taking on its own account,
independently of the mod (§14.2). *(That regulator swap has no changelog entry of its own; it is
known only as an aside in the 2026-08-10 bias-mod findings.)*

### The +97 mV bias mod — built and characterised *(2026-08-10)*

**The problem it solves.** U3A is a unity-gain follower on a single +12 V rail and its output cannot
go below **2.441 mV**, so air's excursion below quiescent was clipped flat. Any cell in that window
reported **Δ = target − air compressed by up to ~3.5×**, non-linearly and by an amount depending on
target strength — so three successive profiles were cut to step over the region entirely.

**The fix is one resistor, no track cuts, fully reversible:** 240 k 1 % metal film from U5 pin 7
(5V-REF) to U3A pin 3. Pin 3's DC path to ground is `R8 + R9 + RX coil` ≈ **4.77 kΩ** (the coil's
19.9 Ω shorts out R1, so R1 barely features), giving 5.0 × 4770/244770 = **97.4 mV**. Taken from
5V-REF rather than +5 V or +12 V so that offset and full scale drift together and the code does not
move. Signal-node loading is **1.9 %**.

**It met its design number.** Predicted biased quiescent **+111.7 mV**, measured **+112.8 mV**. The
timing chain checked itself in the same capture: scope t = 0 was assumed to be sd 15.504 µs and the
CH2 rising edge landed at **15.512 µs** — one 8 ns PWM grid step.

**⚠ It moved every voltage in the signal path.** LTC2508 pin 6 (IN−) is grounded, so the ADC reads
`IN+ − 0` and the bias appears in the data: the pedestal goes ~16.5 → **~110 mV**, every
`threshold_v` in the old ladder is meaningless, and this is **a new measurement epoch** (§1).

**The rail constraint is retired.** Air's worst case is now **67.2 mV** (100 µs band) against the
2.441 mV floor, so nothing clips and no profile has to avoid anything. The null bottoms are
band-dependent — deeper and later on more energetic bands, because the lobe's *depth* scales with
band energy while the zero crossing itself does not:

| band | air null bottom | depth below quiescent |
|---|---|---|
| 100 µs @ 3.125 kHz | 67.2 mV at **sd 17.52 µs** | 38.2 mV |
| 50 µs @ 5 kHz | 75.0 mV at **sd 16.10 µs** | 33.7 mV |
| 10 µs @ 25 kHz | 84.5 mV at **sd 13.99 µs** | 30.3 mV |

**The null is now the best-SNR region in the profile, which is the case for sampling it.** The
steel:brass magnitude ratio through the null is **6–8× on every band**, against 5.8× out at
sd 30 µs — much the same discrimination. What differs is amplitude: **Δsteel is +187 mV at sd 17.5
against +78 mV at sd 30**, for a noise floor that does not change with delay. The discriminant
available there is fill depth, not sign (§2).

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

**Still to measure — and now more valuable, since the corroboration above was withdrawn and the
2026-08-08 voltages are void:** a **direct** RX self-resonance measurement, which is the only thing
that would confirm L and C independently of the transient fit. Also **R9 clamp current** (§14.5),
**D3's reverse leakage now that it is permanently back-biased by ~100 mV** (Schottky leakage roughly
doubles per 10 °C, and a few hundred nA through R9's 4.7 kΩ at a 55–70 °C board is a few mV of
temperature-dependent error — probably lost in the noise, worth a bench look, not an assumption),
and whether the **MCLK-edge ring** (70 ns FWHM, ~250 ns tail) exists in the circuit as well as
between scope channels — the ADC samples on that edge, so if the coupling is real the converter
captures the kick.

---

## 8. Digital / timing (RP2040)

- **MCU:** Waveshare RP2040-Zero (U10), MicroPython. Firmware `mcu/pimd_mcu.py` **v4.35**.
- **Pulse + sample generation:** two PWM channels on the **same slice** (GPIO4 = PWM2A drive,
  GPIO5 = PWM2B sample). Same slice ⇒ both rising edges align at period start; drive falls at
  `pulse_width`, sample falls at `pulse_width + sample_delay`. **This phase-locking is the core
  timing mechanism — never split these onto different slices** (§11). Timing precision ≈ 5 ns
  *(measured)*.
- **Pulse width** 5–50 µs typical (profiles reach 100 µs). **Sample delay** software-set, with an
  empirical `SAMPLE_PULSE_CORRECTION = 0.904 µs` offset between the PWM edge and the ADC trigger.
  Every delay the hardware can produce is a multiple of the **8 ns PWM grid**; an off-grid request
  is silently rounded. **8 ns is also the hard minimum spacing between two cells** — the `dd`/`sd`
  CC-write skip means two cells closer than that collapse silently into one.
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
- **The raw-read outlier gate must never become a state** *(v4.35 — the defect it fixes cost a
  bench session)*. The gate exists for the §7 bit-truncation artefacts, which land at exactly 1/2
  and 1/4 of the true value and are volts-scale. Its threshold is
  `max(|mean_raw| // 10, OUTLIER_GATE_MIN = 164)` raw14 counts (≈ 100 mV). Until v4.35 a rejected
  sample was **substituted with the rolling mean and written back into the ring**, which made
  "every slot equals the mean" an exact fixed point, made floor division walk it down one code per
  frame, and made the rejection self-reinforcing once the mean sat outside the band. Measured:
  eleven of thirty channels froze byte-identical and stayed frozen for 1813 frames; an offline
  differential over 400 random cases latched **382/400** on v4.34 and **0/400** on v4.35. Four
  properties now hold and must be preserved:
  - **A rejected sample is dropped, never substituted** — no ring write, no sum update, no index
    advance. The reported mean simply holds for that sweep.
  - **`OUTLIER_GATE_MAX_RUN = 4` bounds a rejection run.** On the fourth consecutive rejection the
    gate yields, empties the cell's ring and takes the sample, so the cell re-converges in
    `avg_depth` sweeps. Costs at most ~0.24 s on a genuine step.
  - **The gate arms only on a full ring** (`cnt >= avg_depth`), so a settling cell cannot seed it.
    This makes it inert at `averages == 1`, which is correct — profile 2 is the single-sample
    scope-correlation profile and must not be filtered.
  - **The fill branch adds without subtracting** — correct only for a zero-initialised first fill,
    and a re-prime is not that.

  *(v4.25's `OUTLIER_GATE_MIN` fixed a **different** latch — near-zero or negative means flooring
  the threshold to ≤ 0. It did not touch the write-back. Do not read the v4.25 line and assume this
  was covered.)*
- **Rejected `D` commands leave the previous dynamic profile live.** The firmware refuses the
  *whole* `D` on any invalid cell; a following `Q5`/`G` then streams the **old** geometry. Every PC
  tool that sends `D` must wait for `D OK` before committing to the new profile (delaycal since
  v1.41, classviz since v1.73). `D` bounds `averages` to **1..128** *(v4.35)* — 0 builds zero-length
  rings and kills the sweep; 256 is the v4.14 memory crash.
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
- **`overrun_count` ≈ 88.6 % of `busy_high_count` is structural, not a fault** *(measured, both
  fw v4.34 and v4.35)*. Per-cell interpreter cost is ~2.3 ms against band periods of 320 / 200 /
  40 µs, so `remaining` is negative on every non-boundary cell by construction; the cells that do
  *not* overrun are essentially the ones receiving the boundary settle budget.
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

### Operating profile — `cal_3x10_v5` (2026-08-11)

**3 bands × 10 cells = 30 channels**, `averages` 32, raw path (SDOB).
**Pack-voltage window: full charge down to 21.5 V** — the whole usable pack (§12).
⚠ **NOT LOCKED and no corpus exists against it.** It was **hand-tuned in `pimd_delaycal` v1.48
Manual Nudge, not swept** — no threshold crossing was measured for any cell. The delays are the
operator's placements, verified live against the measured means below over a 1866 s run.

| band | freq (kHz) | pulse (µs) | delays (µs) |
|---|---|---|---|
| 1 | 3.125 | 100.0 | 10.792 · 13.032 · 13.912 · 14.816 · 16.92 · 21.16 · 32.656 · 50.392 · 77.76 · 120.0 |
| 2 | 5.0 | 50.0 | 10.016 · 12.256 · 13.144 · 14.08 · 16.08 · 19.36 · 27.152 · 38.088 · 53.432 · 75.0 |
| 3 | 25.0 | 10.0 | 8.04 · 10.208 · 11.064 · 11.984 · 13.8 · 16.16 · 18.704 · 21.648 · 25.056 · 29.0 |

**Cell *n* means the same point on the decay in every band, to within ~0.2 %.** Cells 1–4 are
amplitude-anchored and matched **across** the three bands, not merely within one — which is what
makes a cross-band comparison a measurement rather than an alignment problem:

| cell | anchor | measured (100 / 50 / 10 µs) |
|---|---|---|
| 1 | 2.4 V | 2396 / 2400 / 2401 mV |
| 2 | 0.5 V | 498 / 499 / 499 mV |
| 3 | 250 mV | 248 / 250 / 249 mV |
| 4 | 125 mV | 124 / 125 / 124 mV |
| 5 | **null minimum** | 59 / 64 / 69 mV |
| 6 | rising out of the null | 91 / 90 / 90 mV |

Cells 7–9 are a **geometric ladder** interpolated between cell 6 and cell 10 (constant ratio
1.5431 / 1.4027 / 1.1574 per band, all on the 8 ns grid), landing on the **~110 mV air pedestal** by
cell 7–8 — so they carry **decay rate**, not amplitude. Cell 10 is the band's longest delay.

**Nothing rails, and that is the headline.** The largest reading is 2.4 V against 5.000 V full
scale, so every cell is a measurement rather than a limit — **the first `cal_3x10_*` profile for
which that is true**. It also leaves real headroom rather than sitting just under the limit, which
matters because the operating point moves with pack state *and* board temperature (§3, §12).

**The null is sampled deliberately at its minimum** (cell 5) with cell 6 on the way out, rather than
skipped. Cell 5 independently corroborates the band-dependence of the null: **deepest at 59 mV on
the 100 µs band, shallowest at 69 mV on the 10 µs**, matching the scope measurement by a different
route (§7).

**⚠ The anchors are verified at ONE corner only.** Tuning conditions were **pack 21.89 V (22 % SoC —
the *low* end of the §12 window) and board 70.3 °C**, nearly the opposite corner from that morning's
23.5 V / 31.5 °C. Amplitude-anchored delays move with both (§12), so cells 1–4 will not sit on those
voltages at full charge or on a cold board. Std dev across the whole 30-cell table was
**0.00–0.10 mV, every cell green**, so the table is quiet — quiet at that corner.

**`threshold_v` is a PLACEHOLDER ORDERING KEY, not a voltage.** It is a plain **5.0 → 0.5 V
countdown in 0.5 V steps**. `pimd_shape` and `pimd_corpus_check` sort cells by `-threshold_v` and
`pimd_delaycal` keys on `(freq_hz, pulse_us, threshold_v)`; strict descent is all any of them needs.
**Do not mine that column** — the real voltages are the measured means in the table above.

**Headroom note:** only the 10 µs band is at the hardware limit — 29.0 µs against a max valid delay
of **29.095 µs**, ~95 ns before the 16-bit PWM duty overflows. The 100 and 50 µs bands sit at 120
and 75 µs against limits of 219.091 and 149.093 µs, so both have room to extend.

### Design principles — as they stand at `cal_3x10_v5`

- **Three widely-spaced bands, not a geometric pulse ladder.** Pulse widths are **100 / 50 / 10 µs**
  — ratios **2× and 5×**, deliberately uneven. Three bands cannot tile log target-τ evenly; this
  plan was chosen on the bench as the smallest set that still spans the target range. **The trade is
  resolution in τ for sweep rate**, a bench judgement rather than a derived optimum.
- **Frequencies from the CLEAN_FREQS 125 MHz-divisor list** — 3125 / 5000 / 25000 Hz are all exact
  divisors, so `WRAP` is integer and the pulse ladder stays exact with duty absorbing the grid
  quantisation. Duties are 31.25 / 25 / 25 % (mean 27.1 %), keeping per-band heating roughly even.
  *This principle carries across every epoch.*
- **The delay ladder is a hybrid of two anchoring schemes, because the two halves of the decay
  carry different physics** (§2). Conventionally a PI profile picks one; using one here would sample
  the wrong quantity in one half.
  - **Cells 1–4 amplitude-anchored** on the volt-scale decay, cross-band matched. This is where
    target **polarity** separates the families, so voltage is the right anchor. They inherit the
    cost of amplitude anchoring: which cells are good is a function of pack state and board
    temperature, not a static property of the profile (§3, §12).
  - **Cells 5–6 on the null**, which the +97 mV bias made reachable (§7). Sign is not the
    discriminant there — **fill depth** is, and it is the highest-SNR region on the ladder. Cell 6
    is the second cell past the bottom that reading the *slope* through the null requires (§2).
  - **Cells 7–10 time-anchored** on the pedestal, geometric so that resolution is constant per
    decade of delay. Past the lobe both families read positive and only **decay rate** separates
    them; time, not amplitude, is the right anchor for that.
- **Fewer cells and fewer band boundaries is faster** — the settle budget is paid once per band
  boundary per sweep (§8), so band count costs more than cell count:

| geometry | sweep rate |
|---|---|
| 3 × 10 = 30 cells | **12.30 Hz** (fw v4.34) · **12.45 Hz** (fw v4.35) |
| 3 × 11 = 33 cells | **11.49 Hz** (fw v4.34) |

  *(Rates from firmware earlier than v4.34 are **not comparable** — v4.34 delivers the full boundary
  settle it had previously been short-changing (§8). The two 30-cell figures are the same delays on
  the same rig either side of the v4.35 change, so **v4.35 costs nothing in sweep rate**; the
  0.15 Hz is run-to-run variation.)*

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

**Board temperature is the second operating variable, and it moves the same knob.** Cooling moves
the operating point **up** — the same cell was 46.7 % railed at 52.5 °C and **100 % railed at
31.5 °C** *(measured 2026-08-10/11)*. So the pair (pack voltage × board temperature) sets where an
amplitude-anchored ladder actually lands, and `cal_3x10_v5`'s anchors are verified at one corner of
that plane only (§10).

**The data-quality window is a property of (pack voltage × profile delays), not of voltage alone.**
A noisy region sits at a **fixed place on the decay waveform** while pack voltage **scales the
decay**, so which threshold columns intersect it moves with the pack — and each profile's delays cut
the decay at different points.

- **Under `cal_3x10_v5`** the window is **full charge → 21.5 V**, the whole usable pack — a bench
  judgement for a profile whose delays are new and were cut against the biased front end, so it has
  no reason to inherit an older ladder's window. **Consistent with the mechanism above, not
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

- **Sampling high on the flyback decay rather than the usual bottom ~700 mV.** The early-decay
  region carries the most discrimination information and sits well above the noise floor. This is
  the oldest unconventional choice in the project and it still holds.
- **The profile spans the whole decay with no gaps.** `cal_3x10_v5` runs from **2.4 V down to the
  ~110 mV pedestal** in ten cells, and there is nothing it has to avoid.
- **Two anchoring schemes in one profile — amplitude early, time late.** Conventionally a PI profile
  picks one. Here the early cells are anchored to *voltages* on the decay, because that is where
  target **polarity** separates families; the late cells are anchored to *delays* out on the tail,
  because past the front end's lobe both families read positive and only **decay rate** separates
  them (§2). Using one scheme for both halves would sample the wrong quantity in one of them.
- **Cell *n* is the same point on the decay in all three bands.** The amplitude anchors are matched
  *across* bands, not just within one, so a cross-band comparison is a direct measurement of how
  pulse width changes the response at a fixed point on the decay rather than an alignment exercise.
- **The cost of amplitude anchoring, which was not anticipated:** the ladder is a fixed set of
  voltages sampling a decay whose scale moves with **both** pack state and board temperature, so
  "which cells are good" is not a static property of a profile (§3, §12). This applies to the four
  early cells; the rest are time-anchored and do not inherit it.
- **Biasing the front end into its own artefact rather than stepping over it — a reversal, and the
  measurement is what reversed it** (§7). Three profiles were cut to avoid the negative lobe,
  because the unipolar output clipped air there and compressed every target delta computed over it.
  One 240 k resistor lifted the whole transient into the linear window, and the region that had been
  a hole turned out to be the **best-SNR cells on the ladder**, carrying a third discriminant —
  **fill depth** — that neither the polarity split nor the decay-rate tail provides (§2).
- **The signature is a two-basis object, measured rather than assumed** *(established on the
  previous epoch's corpora — conceptually intact, but unverified on this geometry)*. Each target's orientation
  set is **rank 2** — one axial and one transverse basis shape — and an oblique pose is a positive
  convex combination landing on the arc between, with weights on the dipole prediction
  `cos²θ / sin²θ`. So the matrix carries enough structure to *solve for* orientation instead of
  being confounded by it, and an orientation-invariant descriptor is the 2-D subspace rather than
  any signature in it.

---

## 14. Open problems

1. **Thermal drift — now with a second reason to care.** Wider pulses heat the TX damping/gate
   resistors; the drive circuit drifts and the RX side drifts with it. **Fingerprint:** heavy bands
   drift low, light bands high, monotonic with pulse width; warm recalibration moves delays by tens
   of ns. **The sign test that separates it from a supply shift:** a thermal shift moves light and
   heavy bands in *opposite* directions (r = +0.99 across bands); a supply shift moves all bands the
   same way. Mitigation: calibrate fully soaked. *(The historical "≈ 3 h warm-up" was mostly pack
   discharge, not thermal soak — the two were perfectly confounded before 2026-07-30.)* **What is
   new is that board temperature demonstrably moves the operating point** — 46.7 % → 100 % railed on
   the same cell between 52.5 °C and 31.5 °C (§3, §12) — so it is no longer only a drift term, it
   decides where an amplitude-anchored ladder lands.

2. **Re-measurement backlog. First item is now the front end itself.** §7's 2026-08-08 scope
   voltages are **void**: the air lobe deepened 29.3 → 38.2 mV between that capture and 2026-08-10,
   which the bias cannot cause, and the replaced 7815 is the suspect. **The two-pole fit wants
   re-taking on the current hardware**, and the regulator swap itself has no changelog entry — so
   there is no record of when it happened or which part went in. Also open, in order: the **filtered
   path's two unreconciled figures** (§3's ≈ ±200 µV against §7's ≈ ±450 µV for the same SDOA path,
   2.25× apart, with §7's boxcar arithmetic built on the larger — nothing downstream depends on it,
   which is how it survived, but one of them is wrong); the §12 supply-noise table's **5S battery
   rows**; the 7805-vs-USB noise mystery (onboard 7805 path ~50 % noisier than USB); and the
   flash-penalty rows. **When re-measuring, record which floor is being measured** — amplitude or
   timing (§3).

3. **Q1 duty headroom.** Present operating points run well above the schematic's < 2 % FET duty
   note; Q1 (IRF610) is being pushed past its noted SOA. A higher-rated replacement is probably
   warranted.

4. **C18 under-rated.** 4700 µF **25 V** on a rail that reaches 25.2 V on a fresh pack. 35 V
   replacement identified, not fitted.

5. **The schematic no longer matches the build in three places, all at the RX front end.**
   *(a)* **The 240 k bias resistor from 5V-REF to U3A pin 3 is not drawn at all** *(§7)* — the
   single most consequential undrawn part on the board, since it moves every voltage in the signal
   path. *(b)* **R1 is two resistors in parallel — 1.5 kΩ ∥ 10 kΩ, 1304 Ω effective — where the
   schematic draws a single 1.3k** *(§7)*. Electrically it is the value the fit assumes, to 0.33 %,
   so no measured result moves; but the schematic is what a future reader will trust. While updating
   it, consider a single 1 % part — the ±5 % pair's upper corner sits ~10 Ω from critical damping
   (§7 ζ table). *(c)* **R9's clamp current is unreconciled:** §7's +50 V "damped peak" implies
   ~9.6 mA through 4.7k, but §3 measures **+135 V at the RX coil**, which would imply ~28 mA. Either
   they are measured at different points or under different damping; a scope at the post-R9 node
   settles it. *Not* a claim the front end is out of spec — it has run for months.

6. **The host can block the MCU, and did — for 47 minutes.** The Mode 2 emit is a blocking `print()`
   to USB CDC (§8). v4.27 counts these on `B` but does not prevent them. Any PC tool that stops
   draining the serial pipe stalls acquisition. Watch `emit_block_count`.

7. **Possible TX coil-current plateau above ~67 µs.** In every calibration of the retired ×1.5
   geometric pulse ladder the 67 → 100 µs band-to-band clip-release increment was the smallest on
   the ladder, consistent with coil current flattening (τ_coil = L/R never measured). **The evidence
   is epoch-bound and the comparison cannot be repeated** — the current profile has no 67 µs band —
   but the question matters more now, not less: the 100 µs band is one of three rather than one of
   seven, so it carries a third of the profile. Needs a scope on coil current vs pulse width, which
   does not depend on any profile.

8. **⚠ The null's discrimination is measured at 0 cm only, and that gates the next capture.**
   Every fill-depth and slope figure in §2 comes from targets pressed as close to the coil as
   possible, where coupling dominates. **A feature that only exists on contact is not corpus
   material.** One repeat at 50 mm on the 100 µs band answers it, and **nothing should be captured
   against a null-sampling profile until it is.** This is the highest-priority open item.

9. **`cal_3x10_v5` is not locked, and its anchors are verified at one corner.** Tuned at pack
   21.89 V / board 70.3 °C; cells 1–4 will land on different voltages at full charge or on a cold
   board (§10). Nothing has been captured against it. Locking it means a sweep or a second
   verification pass at the opposite corner, not just a rename.

10. **Plan C — differential bias onto the ADC's IN− — is designed but not built, and Plan A's
    success is the argument for it.** Plan A (the fitted 240 k) puts the offset in the data, so it
    costs a measurement epoch every time it changes. Buffering the same bias onto IN− through the
    spare half of the same DIP-8 (sheet 2's `U18B`, whose pin 7 lands on TP24) would make the offset
    cancel differentially: the ladder would stay valid, only the newly visible middle would need
    sweeping, and the drift would be common-mode. It costs three cuts — `R80`/`R82` links out, IN−
    lifted from GND, RX cold end floated onto V_b — and one unknown, whether R1 is through-hole.
    **The decision belongs before the corpus, not after**, because Plan A as a permanent fitting
    spends an epoch for no reason.

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
| `src/pimd_delaycal.py` | **v1.48** — delay-calibration sweeper and the only profile author. Coarse+fine two-phase sweep per (freq, pulse) pair, threshold-crossing delays snapped to the 8 ns grid, thermal soak monitoring, auto-nudge, Compare Profiles tab, pack/temperature gauges and a conditions span recorded into every exported profile's notes. **Manual Nudge cells take a typed delay in µs**, not just −/+ steps — the path `cal_3x10_v5` was hand-tuned through; typed and stepped values share one apply path so neither can bypass the 8 ns snap or the duty-limit pre-check. **Import Profile first** when recalibrating — persisted settings are not anchored to the operating profile, so editing a field and pressing Run inherits a stale baseline, band plan included. |
| `src/pimd_rawlog.py` | **v1.16** — deliberately dumb raw logger: loads a profile, streams it, writes every firmware line **verbatim** to `data/sessions/rawlog_<ts>.txt`. No tables, no derived values, so it cannot develop display-layer defects. **Ground truth for offline work.** Acquisitions are self-bracketing. Geometry-agnostic. |
| `src/pimd_shape.py` | **v1** — shared signature-geometry maths (pure NumPy, **no Qt**). `unit_shape` / `amp_l2` / `snr`, `band_means`, `band_range_mean`, `crossing_us`, `decay_persistence`, `family`. Geometry always passed explicitly; bands and thresholds resolved **by value**, never by stored index. `family` (sign) and `decay_persistence` (magnitude) are read together and neither overrules the other. |
| `src/pimd_features.py` | **v14** — session-CSV → training-corpus builder (offline CLI). Registry join, **hard geometry guard: one `(profile_name, profile_sha8)` per corpus build**. Parses the dump's `# pack_v:` / `# soak:` / `# stall:` / `# capture:` / `# mark:` comment tracks; `pack_v_at()` interpolates a voltage per capture. |
| `src/pimd_target_check.py` | **v4** — target-registry loader/validator (CLI + library). `DEFAULT_REGISTRY_PATH` here is the single source of truth for registry location. `-f` is required — there is no default path. |
| `src/pimd_corpus_check.py` | **v1.9** — corpus-level acceptance checker. Shape distance-invariance, split-half SNR, repeat consistency, falloff fit. One flat PASS/AMBER/FAIL/SKIP table, exit 1 on any FAIL, so it can gate a capture day. |
| `src/data/profiles/` | **Three files, and each earns its place.** `cal_3x10_v5.json` is the operating profile (§10, the firmware↔ML contract). `cal_63_air_v2.json` and `cal_63_air_bat_v3.json` are retained **only** because the two corpora were captured against them and §16's `pimd_shape --selftest` runs against the first — **a corpus whose profile is gone cannot be interpreted.** Every other lock (`cal_3x10_v1…v4`, `cal_3x10_v4_railtest`, `cal_63_air_v1`, `cal_72_air_v2/v3`, `cal_110_full_range_v4`, `sweep_100us_decay_v1`) is **out of the working tree, recoverable from git history only.** None had a corpus; every remaining mention of them in `src/*.py` is a comment, since no tool loads a profile by name. |
| `src/data/targets/targets_v3.csv` | Human-authored target registry, **current**, 27 objects — `pimd_target_check`'s `DEFAULT_REGISTRY_PATH` and what `pimd_classviz` / `pimd_features` use. Human-owned: tooling reads and validates only, never writes. `targets_v1.csv` is retained for reading the 2026-07-23 corpus. ⚠ `targets_v4.csv` is also tracked and is what **`pimd_rawlog` alone** reads (23 rows, different field set); despite the name it is **not** a successor to v3. |
| `src/data/corpora/` | Signature corpora (`gui_signatures_*.csv`). Both files on disk are **previous-epoch 63-cell** and cannot be mixed into the current 30-cell epoch. Untracked, so **git cannot restore a damaged corpus** — back up before any in-place edit. |
| `src/data/sessions/` | Raw Mode 2 session dumps — self-describing CSV with embedded profile JSON, per-column map, marks and comment tracks; plus rawlog's verbatim `.txt`. Written automatically whenever the stream runs, ~220 KB/min. Untracked and **not reconstructable after the fact.** |
| `src/data/scratch/` | Scratch captures of **unregistered** objects. Never written into `corpora/` — a corpus build hard-errors on an unregistered `target_id` and that guard stays. |
| `References/images/` | Schematics, scope and GUI reference captures (§15 note below). |
| `References/scope/` | Raw scope CSVs, tracked again as of `20260810_bias_mod/` — nine traces (air / brass / steel RHS × three bands, all at 0 cm) plus `plot_bias.py` and `plot_delay.py`. This is the primary evidence behind §2's fill fractions and §7's post-bias measurements, and the one place they can be re-derived. |
| `USAGE.md` | Per-app usage guide — intent, operation and pipeline flow for the firmware and each PC tool. |
| `CHANGELOG.md` | Running change log — **the source this file is consolidated from**, and where all history and rationale lives. |
| `DESIGN.md` | **This file** — curated snapshot. Do not edit directly outside a consolidation pass (§18). |
| `CLAUDE.md` | AI-agent working brief — how to behave in this repo. Not project facts. |

**Key reference images** (all in `References/images/`): `schematic-v604.jpg` and
`schematic-v604-sheet2.jpg` (rev 6.04 — **does not show the bias resistor**, §14.5) ·
**`bias_mod_delay_plot_20260810.png`** (the current front end: three bands, air / brass / steel with
the §7 fits overlaid) · `6S-pack-discharge-curve.jpg` (§12) · `GUI-steady-state-256-1024.jpg` (the
SoC reference capture) · `warmup-with-8ns-steps.jpg` (why delays snap to the 8 ns grid).

**Pre-bias-mod images, kept as history only:** `lobe_at_amp_input_20260808.png`,
`spanner_fills_the_null_20260808.png` and `decay_model.png` show the front end before 2026-08-10 —
the shape is still the right picture of the mechanism, the **voltages are void** (§7).
`profile_3x10_timing.png` renders a retired geometry and no longer describes any live profile.

**Retired 2026-08-09** and recoverable from git history only: `utilities/` (decay model, pack
discharge, soak-vs-voltage, session relabel, mode-2 noise tools), `ML/`,
`References/Targets v1 Analysis/`, `src/pimd_classify.py`, `src/pimd_v2_findings.py`. Their
**findings stand** — they are in `CHANGELOG.md` — but are no longer re-runnable from a clone. The
former rule that a utility cited from `CHANGELOG.md` must be tracked is retired with the directory
it guarded. *(`References/scope/` was on this list and has since come back — see the table above.)*

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
# the 2026-07-23 63-cell analysis, so this FAILs against any other epoch. This is
# why cal_63_air_v2.json is still in the repo (§15).
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
> **Any figure taken under a retired profile is epoch-bound** (§1, §10).

| # | Fact | Epoch |
|---|---|---|
| 17.1 | **Power draw ~0.5 A average** streaming; drive current and heating scale with pulse width and duty. Measured on the previous 63-cell profile (mean band duty 28.1 %); the current mean band duty is **27.1 %**, so the figure should carry — *inferred from duty, not re-measured*. The §12 capacity numbers depend on it. | prev → current |
| 17.2 | **The front end is two real poles with opposite-sign residues** — τ_fast 1.125 µs, τ_slow 2.270 µs, ζ 1.06 — giving exactly one zero crossing, and it is not ringing. **The shape stands; the 2026-08-08 voltages do not** (§7, §14.2). | shape current, voltages void |
| 17.3 | **The null responds to metal.** A steel spanner on the coil removes the zero crossing entirely. It is real coil physics, not an amplifier artefact — which is what made biasing it into view worth doing. | current |
| 17.4 | **Fill depth through the null is a third discriminant**, independent of the early polarity split and the late decay rate: brass fills 52 / 38 / 8 % and steel 100 / 100 / 62 % of the air dip on the 100 / 50 / 10 µs bands — **7× apart on the shortest pulse**. Measured at 0 cm only (§2, §14.8). | current |
| 17.5 | **The null is the best-SNR region on the ladder.** Steel:brass magnitude ratio through the null is 6–8× on every band against 5.8× at sd 30 µs — the same discrimination at **+187 mV instead of +78 mV**, against a noise floor that does not change with delay (§7). | current |
| 17.6 | **A ferrous target adds a genuine slow pole of its own** — τ_s 19.0 µs (100 µs band), 23.4 µs (50 µs) — which air and non-ferrous do not have, and which vanishes on the 10 µs band because a 10 µs pulse barely excites it (§7). | current |
| 17.7 | **The +97 mV bias mod met its design number**: predicted quiescent +111.7 mV, measured +112.8 mV, and air's worst case moved from clipped to **67.2 mV** above the 2.441 mV floor (§7). | current |
| 17.8 | **Sweep rate is set by cell count and band count:** 30 cells **12.3–12.5 Hz** · 33 cells 11.49 Hz, fw v4.34/v4.35. **v4.35 costs nothing** over v4.34 on identical geometry (§10). | current |
| 17.9 | **The outlier gate was an absorbing state until fw v4.35** — substituting the rolling mean back into the ring made "every slot equals the mean" an exact fixed point. Eleven of thirty channels froze byte-identical for 1813 frames; offline, 382/400 random cases latched on v4.34 and 0/400 on v4.35 (§8). | current |
| 17.10 | **A railed cell does not provoke gate rejections** — pinned samples all read the same code, so deviation from the rolling mean is ~zero. Railing and latching are separate failures with separate fixes: the ladder for one, the firmware for the other (§8). | current |
| 17.11 | **Board temperature moves the operating point, upward on cooling** — the same cell was 46.7 % railed at 52.5 °C and 100 % railed at 31.5 °C. Which cells are usable is a function of (pack × temperature), not a static property of the ladder (§3, §12). | current |
| 17.12 | **Pack voltage reaches the operating point at 43–51 mV/V over 21–25 V**, r = 0.96–0.97; does not generalise beyond that span (§12). | 6S |
| 17.13 | **Pack capacity ≈ 5.2 Ah / 10.33 streaming-hours** full to empty; idle drain is ~15× lower than streaming, so a fresh pack cannot be idled into a window (§12). | 6S |
| 17.14 | **Thermal and supply drift are separable by sign:** thermal moves light and heavy bands in opposite directions (r = +0.99 across bands); supply moves all bands the same way (§14.1). | all |
| 17.15 | **Reference age is a hard ceiling on frozen-reference measurement** — ~0.5 mV/cell at 10 s, 7.5 mV at 150 s. Air must be bracketed both sides; interpolation takes correct pairings to cos 0.996–1.000 (§3). | all |
| 17.16 | **31.25 kHz is a bad rep rate** — an entire band unusable at 31.25 kHz / 9 µs, restored by moving to 25 kHz with the pulse unchanged. Noise followed the rep rate, not the decay alignment (§8). | all |
| 17.17 | **Boundary settle was being under-delivered until fw v4.34** — measured from the loop top rather than the config write, so a 3 ms budget could deliver ~0.6 ms (§8). | current |
| 17.18 | **The cell-0 outlier population is caused by the blocking emit**, not by the band boundary, settling or dwell. A within-run factorial gave 151 events at sweep position 0 and zero at position 30 in the same sweeps. Remaining candidate is USB TX burst coupling into the front end — a scope question (§14.6). | current |
| 17.19 | **`splithalf_floor` understates reproducibility noise ≈ 2×**, so the SNR ≥ 5 gate is really a reproducibility gate of ≈ 2.5–3.5 (§3). | prev-epoch |
| 17.20 | **The between-session noise component measures zero** (4.24 vs 4.03 mV over three days, eight sessions) — captures from different days are directly comparable (§3). | prev-epoch |
| 17.21 | **Family is an orientation coordinate, not a material one.** The early-band sign splits by *placement*: 90.9 % accurate transverse, 53.8 % axial. The **late**-band sign — iron-bearing vs non-ferrous — is the robust axis at **97.2 % ungated**. | prev-epoch |
| 17.22 | **The signature is rank 2 in orientation** and the Pasion–Oldenburg two-basis mixing law is confirmed on oblique captures, so orientation becomes a fitted parameter rather than a confound (§13). | prev-epoch |
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
