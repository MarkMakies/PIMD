# Pulse Induction Metal Detector (PIMD)

**Author:** Mark Makies (Australia) · **Licence:** CC BY-SA 4.0
**Hardware rev:** 6.04 · **Firmware:** v4.19 · **PC tools:** gui v4.07 · scope v4.01 · classviz v1.04 · delaycal v1.02 · **Coil:** v4
**Last bench update:** 2026-06-18 (CLASSIFY_EP confirmed; BUSY-sync fix; SoC established)
**Doc rev:** 1.3 (2026-06-19) — split agent-facing guidance out to `CLAUDE.md`: removed the §16 working brief and the scattered reviewer/agent notes (§1, §17 intro); repurposed §16 as Build/Run/Deploy; added `CLAUDE.md` and `ARCHIVE.md` to the §15 inventory. No project facts changed. (Previous: 1.2 (2026-06-18) — consolidation pass: versions fw v4.19 + all tools; Profile 4 CLASSIFY_EP §10; SoC §3; BUSY-sync §7; §9 records; §15 inventory; §17.) Bump this line on every edit.

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

- **Flyback** *(measured, 2026-06-16, 10 kHz / 40 µs)*: TX coil **−18 V to +265 V**,
  RX coil **−15 V to +135 V**. Gate turn-off **11.47 V → 0.44 V in 733 ns**.

- **FET Q1 limits:** < 10 A, < 300 µs, < 2 % duty. *(The detector deliberately
  runs above the 2 % duty note — see §17 power table and §14.)*
- **RX front end** : R1 1.3k damp · R9 4.7k clamp-limit · D2 1N4732
  (4.7 V zener) · D3 1N5819 (Schottky) · 47 Ω into ADC · LT6203 on single +12 V.
  Node after R9 **−0.48 / +5.11 V**; ADC input settles **~5.0 V**, edge ring peaks
  **+5.30 / −0.69 V** (brief, harmless, current-limited). Detail in §7.

- **Noise:** *(measured, DF256)*: filtered path ≈ **±200 µV**; raw ≈ **±400 µV**; warmed-up
- **Sample-timing precision: ** ≈ **5 ns** *(measured)*. **Thermal drift** ≈ **−50 µV/s**
  at 10 kHz / 20 µs *(measured)* 

- **Standard Operating Conditions (SoC)** *(established 2026-06-18)*: Mode 1 · 10.0 kHz /
  20.0 µs pulse / 10.0 µs sample delay / DS 256 · coil in air, no targets · 20 V bench
  supply · allow **4 min warm-up** from cold (expect ≈ 50 µV/s drop during warm-up; do not
  take noise-floor readings before this point). Reference capture: `References/GUI-SteadyState.jpg`.

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

 RP2040 ─ serial (USB-CDC / UART) ─► PC tools (PyQt6) 
```
---

## 5. Coils

Separate TX and RX windings (a two-winding "transformer", **not** a shared mono coil). 

**Coil v4:** two coils slotted into 12 mm Perspex, RX shielded with copper tape,
both embedded for mechanical stability (earlier coils shifted under rover vibration;
epoxy/Perspex fixed the resulting drift). Faraday shield on RX with **no closed loop**.

TX 520 × 360 mm, 10 turns 0.5 mm (24 AWG) enamelled, 17.6 m, 1.7 Ω ·
RX 430 × 265 mm, 50 turns 0.25 mm (30 AWG) Teflon silver-plated wire-wrap, 30.8 m, 22.9 Ω.
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

- **R1 = 1.3k (shunt) is the RX damping resistor. **critically damps at ≈ 1.3–1.4k** *(measured)*, which also
  cleans up TX via mutual coupling.
- **R9 = 4.7k (series) is clamp current-limit only**, not damping — it holds clamp current
  to ≈ 9.6 mA at the +50 V damped peak, well inside the LT6203 rating.
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
≈ 310 µV std dev — matching the M=32 boxcar expectation (≈ 1400 µV / √32). A degenerate
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
  `SAMPLE_PULSE_CORRECTION = 0.908 µs` offset between the PWM edge and the ADC trigger.
- **Pulse rate:** 5-50 kHz typical. A **prime-ish** rate  halved noise by
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
- **rate:** min(100 Hz, profile_freq / n_cells); `S` rejected while Mode 2 runs

**Both modes:**
- `V`/`v`/`?` identify → `V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_kHz>,<pulse_us>,<delay_us>,<downsample>`
- `L` list profiles → one `L<idx>,<freq_kHz>,<n_bands>,<n_cells>,<averages>,<name>` line each
- `A<n>` raw boxcar average (idle / Mode 1 only) → one `R<time_ms>,<mean_uV>,<std_uV>,<count>,<freq_kHz>,<pulse_us>,<delay_us>,<min_uV>,<max_uV>` line
- `E` is the universal stop. Modes are mutually exclusive.

**µV scaling (invariant):** filtered (Mode 1) `raw32 * 5_000_000 // 2**31`; raw (Mode 2 / `A`)
`raw14 * 10_000_000 / 2**14`.

---

## 10. Scan profiles (WIP)

Profiles are fixed/compiled-in RAM constants (no flash writes). Geometry is constant per
profile, so any future ML classifier is trained per profile and the table is the
firmware↔ML contract.

### Scan-grid sizing (WIP)
A profile *is* a scan grid: **averages** raw samples per cell, across **n_delays** sample
delays, for **n_pulses** pulse widths. Sensible starting point:
- **averages ≈ 32** → ~250 µV (raw floor ≈ 1400 µV, noise = 1400/√averages), ~3.2 ms/cell.
- **n_delays ≈ 8**, log-spaced ~5–40 µs via `e^(0.3n)−1`.
- **n_pulses ≈ 3**: 8 / 20 / 40 µs (the ferrous/non-ferrous discriminant axis).
- Frame ≈ averages·n_delays·n_pulses·100 µs ≈ 77 ms (~13 frames/s); at 0.2 m/s a target
  dwells ~20 frames.

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

Input: 5× LiPo (16.5–21 V), F1 2 A, D4 1N4004 reverse protection, FB1 ferrite bead. A
**dedicated** battery powers the detector (the rover's 40 V supply was too noisy).

**Known supply-noise facts** *(measured, free-air, 10-sample σ):* ~200 µV USB / no flash ·
~250 µV battery / no flash · ~900 µV USB / using flash · ~4000 µV battery / using flash.  Writing to
flash raises the noise floor ~10×.

---

## 13. What makes this design unusual (deliberate, validated choices)

- Sampling the **0.5 V – 4.5 V** band of the flyback decay rather than the usual bottom ~700 mV —
  found to carry more discrimination information and sit well above the noise floor.

---

## 14. Open problems

1. **Thermal drift.** Wider pulses heat the TX damping/gate resistors; the drive circuit
   drifts and the sensitive RX side drifts with it.
2. **7805-vs-USB supply-noise mystery.** Onboard 7805 path ~50 % noisier than USB; unresolved.
3. **General supply noise floor** (battery vs USB, flash penalty — partially mitigated).
4. **Q1 duty headroom.** Present operating points run well above the schematic's < 2 % FET
   duty note (see §17) — Q1 (IRF610) is being pushed past its noted SOA; a higher-rated
   replacement FET is probably warranted.
5. **Coil mechanical stability** — largely solved (epoxy + Perspex).

---

## 15. Repository / file inventory

| File | Role |
|------|------|
| `mcu/pimd_mcu.py` | RP2040 MicroPython firmware (**v4.19**) — both modes, all profiles; BUSY edge sync required for SDOB accuracy |
| `mcu/main.py` | One-line board launcher: `import pimd_mcu` |
| `src/pimd_gui.py` | PC PyQt6 GUI **v4.07** — Mode 1 filtered telemetry display; boxcar-mode toggle for raw SDOB overlay |
| `src/pimd_scope.py` | PC PyQt6 scope **v4.01** — Mode 2 raw streaming visualiser; supports CLASSIFY_EP and multi-band profiles |
| `src/pimd_classviz.py` | PC PyQt6 Mode 2 signature visualiser (**v1.04**) — real-time 5×9 heatmap of CLASSIFY_EP cell deviations, stats table, ML CSV logger, single-cell isolation mode |
| `src/pimd_delaycal.py` | PC PyQt6 delay-calibration sweeper (**v1.02**; header title line still reads v1.01 — reconcile). Steps `sample_delay` per freq/pulse pair via `*`+`A<n>` and records the delay at which the ADC reading crosses each target voltage — i.e. measures clip-release / earliest-valid-sample |
| `src/pimd302.py` | Legacy PC GUI v3.02 (superseded; kept for reference) |
| `src/pimd111.ui` | Qt Designer UI source for `pimd_gui.py` |
| `src/requirements.txt` | Python deps for PC tools |
| `References/Schematic%20Baseline.jpg` | Schematic export, rev 6.04 (current front-end, R12/R13 = 0 Ω, field annotations) |
| `References/ScopeBaseline.jpeg` | Scope baseline, Mode 1, 10 kHz / 20 µs / 10 µs 
| `References/GUI-TargetExample.jpg` | App baseline, Mode 1 v4.07, 10 kHz / 20 µs / 10 µs / DS 1024 — positive spike = ferrous, negative spike = non-ferrous, noise < 500 µV |
| `References/GUI-SteadyState.jpg` | SoC steady-state reference capture — settled noise floor and thermal drift; Mode 1 at SoC conditions, first half DS 256 / second half DS 1024 |
| `References/LTC2508-32.pdf` | ADC datasheet — source for the settling/bandwidth math |
| `References/DiscriminationTests.JPEG` | *Not yet cited in text* |
| `CHANGELOG.md` | Running change log — the source this README is consolidated from (logging conventions in `CLAUDE.md`) |
| `ARCHIVE.md` | Older `CHANGELOG.md` entries, preserved verbatim at each consolidation pass |
| `README.md` | **This file** — project reference (specs, design, measured values); a curated snapshot consolidated from `CHANGELOG.md` |
| `CLAUDE.md` | AI-agent working brief — how to behave when editing this repo (mindset, conventions, don'ts). Not project facts |

---

## 16. Build, run & deploy

**Don't commit yourself**

No build step for either the PC tools or the firmware. (Agent conventions — version
bumps, changelog discipline, the "don't edit this README" rule — live in `CLAUDE.md`.)

### Run / deploy (PC venv)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
cd src
python pimd_gui.py        # Mode 1 GUI (filtered telemetry)
python pimd_scope.py      # Mode 2 scope (raw streaming)
python pimd_delaycal.py   # delay-calibration sweep
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
*5,40,8.4,256  then S → Mode 1 streaming (* records, ~20/s);    E to stop
A32                   → one raw boxcar average (R record), idle/Mode 1 only
```

---

## 17. Test log / observations (curated)

Per-entry: **date · fw/hw rev · one-line summary**, grouped by subject. Detailed changelogs
stay in source-file headers. This log is curated — it is refreshed from `CHANGELOG.md` at each
consolidation pass. When an observation **supersedes** an envelope value (§3), the envelope is
updated in place with a dated note and the raw observation is recorded in `CHANGELOG.md`.
(Logging conventions for agents live in `CLAUDE.md`.)

### 17.1 Power / current vs pulse width
"current" = average bench-supply current (at 20 V), not peak coil current. 

| Pulse (µs) | Freq Req (Hz) | Freq (actual) | Current (mA) |
|---|---|---|---|
| 40 | 10.6 | 500 | raise freq until 0.5 A |
| 30 | 17599 | 500 | as above |
| 20 | 29201 | 410 | now frequency/duty-cycle constrained |
| 10 | 43003 | 201 | as above |
| 5 | 56992 | 105 | as above |

### 17.2 Standard Operating Conditions / noise floor

*2026-06-18 · fw v4.19 · Mode 1 · bench supply 20 V · coil in air*

**SoC:** 10.0 kHz / 20.0 µs pulse / 10.0 µs sample delay / DS 256. Allow 4 min warm-up
from cold — expect ≈ 50 µV/s drop during this period. Do not take noise-floor readings
as representative before the 4-minute mark.

Reference capture: `References/GUI-SteadyState.jpg` — first half of plot at DS 256,
second half (after DS Factor toggle) at DS 1024. Shows the settled noise floor and slow
thermal drift; this is the trace future comparisons should be checked against.

### 17.3 Mode 2 — profile streaming

WIP - fixing bugs atm to ensure data consistency

## 18. Change Log Consolidation Pass.

You are performing a "human-run consolidation pass".
For THIS task only, you are authorised to edit README.md (the read-only rule is
suspended for this pass).

CHANGELOG.md is the source of truth for everything that has changed since the last
consolidation.  For this consolidation only focus on the lines in CHANGELOG.md above 
the marker: '<!-- Add new entries above this line. Format: ### <file> — v<N> — <short title> -->

IMPORTANT — the CHANGELOG is NOT in chronological order. Do not replay entries.
First determine the NET CURRENT STATE per file, then
synthesise. The README is a consolidated snapshot, not a concatenation — keep the
existing "one-line summary, detail lives in source headers" philosophy.

Before editing, produce these for my review:
  1. Current version of each file (firmware, pimd_gui, pimd_classviz,
     pimd_delaycal) as you read them from the CHANGELOG.
  2. An asset mapping table: each existing README asset path → its Reference/
     target. Flag any old reference with no clear match, and any file in Reference/
     not yet cited anywhere — do NOT guess a match.
  3. Which README sections you'll change, and the net change for each (expect at
     least: header/Doc-rev line).
  4. Anything you plan to drop or significantly reword.

Preserve policy text and structure;  bump the Doc-rev line.  Fold new bench observations into §17. Do NOT delete content that is still accurate.

After I approve and you've updated README.md:
  - Reset CHANGELOG.md by moving the marker to the top of the file.
  - Adding  a line under the moved marker: '## Archive — consolidated YYYY-MM-DD'
