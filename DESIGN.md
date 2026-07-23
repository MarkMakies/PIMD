# Pulse Induction Metal Detector (PIMD)

**Author:** Mark Makies (Australia) · **Licence:** CC BY-SA 4.0
**Hardware rev:** 6.04 + shielded enclosure (2026-07-13) · **Firmware:** v4.26 · **PC tools:** gui v4.13 · classviz v1.39 · delaycal v1.25 · features v7 · targets v2 · corpus_check v1.6 · **Coil:** v4 · **Operating profile:** cal_63_air_v2 (locked 2026-07-14)
**Last bench update:** 2026-07-14 (fw v4.26 CC-write fix A/B-verified; soaked recal → cal_63_air_v2 locked)
**Doc rev:** 1.9.2 (2026-07-23) — §15 `src/data/profiles/` row: the superseded locks are now listed file-by-file in `.gitignore` rather than excluded by a `dir/*` + negation pair (git handled the wildcard form correctly, but that idiom renders unreliably in some editors' ignore decorations). Net tracking is unchanged — only `cal_63_air_v2.json` is tracked — but new delaycal candidates now stay visible as untracked instead of being ignored by default. (Previous: 1.9.1 (2026-07-23) — post-consolidation corrections (human-directed): `pimd_targets.py` renamed **`pimd_target_check.py`** (v2→v3; import-contract change only, no functional change) — §15 row and the classviz row's reference follow. Repo hygiene, all files kept on disk: `src/data/profiles/` is now gitignored except the operating `cal_63_air_v2.json` (superseded locks untracked), the three previous-epoch `References/profile8b-*` captures untracked, and the stray `src/data/delaycal_1706-104844.csv` deleted; §15 profiles row records the new tracking policy; 1.9 (2026-07-23) — consolidation pass, **PC-tooling only**: no hardware, firmware, profile or measured-value change, and no new bench observations (§3 and §17 untouched — every entry consolidated here is tooling work). classviz v1.32→v1.39: the **Training Session tab is gone**, all corpus capture is now the Analysis tab's automated Training cycle, plus capture ergonomics (shrinkable heatmap split, auto-visible new captures, per-parameter quality colouring) and two latent-bug fixes. features v6→v7 (doc-only); targets v1→v2 — registry relocated to `src/data/targets/targets_v1.csv`; corpus_check v1.4→v1.6 — migrated onto the `target_id`/`distance_mm` schema and fixed so an air capture no longer aborts the run (§15). §15 corrections: registry path and object count (22, not 23). Next phase: systematic target signature/profile capture under the existing `cal_63_air_v2` profile and `targets_v1` registry, both deliberately left untouched; 1.8.2 (2026-07-15) — §15: added rows for the seven previously uncited `References/` images (pcb-coil-baseline, warmup-with-8ns-steps, new-training-data, training-targets-v3, training-results-v1a/b/c — the last three flagged previous-epoch), captions written from the images; 1.8.1 (2026-07-15) — post-consolidation corrections: delaycal v1.25 (`APP_VERSION` constant re-synced with its header — no functional change); `pimd_corpus_check.py` re-tracked and its §15 row restored (v1.4 is maintained against the current schema regime; `pimd_classify.py`/`pimd_v2_findings.py` remain local-only); 1.8 (2026-07-15) — consolidation pass: fw v4.25 outlier-gate latch fix + v4.26 post-emit CC-write race fix, both bench-verified (§8, §17.8); 6 µs band dropped → 63-cell profiles, soaked recal locked as **cal_63_air_v2** (§10); threshold-noise-zone upper edge located ≈ 4.67 V on the 100 µs band, thermal operating-point drift mapped (§14.7, §17.8); structured target-metadata capture regime landed — `targets.csv` registry + `pimd_targets.py` v1, classviz v1.31→v1.32, features v6 (§15); `USAGE.md` added, `docs/` removed; §15 asset rows: scope baseline renamed `scope-pulse-baseline.jpeg`, four previous-epoch profile8b rows dropped; 1.7.1 (2026-07-13) — §15: removed `pimd_corpus_check.py` row (untracked from the repo along with `pimd_classify.py`/`pimd_v2_findings.py` — previous-epoch ML tools kept local-only); 1.7 (2026-07-13) — consolidation pass: **measurement epoch reset** — electronics moved into a new shielded enclosure and fw v4.24 changed Mode 2 acquisition timing, so pre-2026-07-13 quantitative findings are historical until re-measured (§3, §17); first-column noise root-caused to period-scaled boundary settling, fixed in fw v4.24 (§8, §17.7); threshold noise zone ~4.45–4.65 V mapped (§10, §14, §17.7); cal_72_air_v3 locked with top-dense threshold ladder (§10); classviz v1.17→v1.30 (Analysis tab, Training Session tab, Std Dev heatmap mode, top-bar Load & Run — §15); delaycal v1.20→v1.24 (§15); ML/corpus findings from the previous epoch dropped from this document — corpus to be rebuilt.) Bump this line on every edit.

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
**Systematic target signature capture is the current phase**, running against the locked
`cal_63_air_v2` profile and the `targets_v1` registry — both deliberately left untouched
so the corpus is captured under one fixed hardware/profile/target state.

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

- **Noise:** *(measured, DF256)*: filtered path ≈ **±200 µV**; raw ≈ **±400 µV**; warmed-up
- **Sample-timing precision: ** ≈ **5 ns** *(measured)*. **Thermal drift** ≈ **−50 µV/s**
  at 10 kHz / 20 µs *(measured)* 

- **Standard Operating Conditions (SoC)** *(established 2026-06-18)*: Mode 1 · 10.0 kHz /
  20.0 µs pulse / 10.0 µs sample delay / DS 256 · coil in air, no targets · 20 V bench
  supply · allow **4 min warm-up** from cold (expect ≈ 50 µV/s drop during warm-up; do not
  take noise-floor readings before this point). Reference capture: `References/GUI-steady-state-256-1024.jpg`.

- **Mode 2 warm-up ≈ 5 min** *(established 2026-07-02/03)*: the profile duty is much heavier
  than Mode 1 SoC; run the profile in ClassViz until thermal drift settles before calibrating
  or recording. Cold-ish, heavy bands drift up to ~250 ns in calibrated delay; soaked, repeat
  cals agree to ≤ 40 ns (one 8 ns grid step for the light bands). See §17.5.

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
  ≈ +12 ms on the 72-cell profile (~289 → ~301 ms refresh).
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
- **rate:** min(100 Hz, profile_freq / n_cells); `S` rejected while Mode 2 runs

**Both modes:**
- `V`/`v`/`?` identify → `V<fw>,<board_id>,<num_profiles>,<active_idx>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>`
- `L` list profiles → one `L<idx>,<freq_hz>,<n_bands>,<n_cells>,<averages>,<name>` line each
- `A<n>` raw boxcar average (idle / Mode 1 only) → one `R<time_ms>,<mean_uV>,<std_uV>,<count>,<freq_hz>,<pulse_ns>,<delay_ns>,<min_uV>,<max_uV>` line
- `E` is the universal stop. Modes are mutually exclusive.

**µV scaling (invariant):** filtered (Mode 1) `raw32 * 5_000_000 // 2**31`; raw (Mode 2 / `A`)
`raw14 * 10_000_000 / 2**14`.

---

## 10. Scan profiles

Profiles are fixed/compiled-in RAM constants (no flash writes). Geometry is constant per
profile, so any future ML classifier is trained per profile and the table is the
firmware↔ML contract. **Frames from different profile geometries must never be mixed in
one dataset.**

### Operating profile — `cal_63_air_v2` (locked 2026-07-14)

**7 bands × 9 delays = 63 cells**, averages 32 per cell, raw path (SDOB). This is
`cal_72_air_v3`'s band plan and top-dense threshold ladder (all design principles below
carry over) with two changes:

- **The 6 µs / 50 kHz band is dropped** (first as `cal_63_air_v1`, 2026-07-14): bench
  judgment — it carried no target information not already present in the other bands and
  was notoriously noisy (its 20 µs period gave the tightest CC-write budget of all bands,
  §17.8; likely a contributor to that reputation). The remaining 7 bands were
  byte-identical to v3.
- **Delays re-anchored fully warmed under fw v4.26** (v1 → v2, same cell geometry):
  shifts of −56…+16 ns vs v1, heavy bands earliest — the thermal signature (decays arrive
  earlier warm). This retired the drift that had pushed the 100 µs / 4.70 V cell onto the
  ≈ 4.67 V upper edge of the §17.7 threshold noise zone (bench-confirmed fixed, §17.8).

**Treat v2 as a new calibration epoch for corpus purposes** — same geometry as v1 but
different delays; frames must never be mixed across profiles (contract above).

| Band | Freq (kHz) | Pulse (µs) | Duty | Band share of sweep |
|---|---|---|---|---|
| 1 | 25.0 | 9.00 | 22.5 % | 4.1 % |
| 2 | 20.0 | 13.44 | 26.9 % | 5.1 % |
| 3 | 15.625 | 20.00 | 31.25 % | 6.5 % |
| 4 | 10.0 | 30.00 | 30.0 % | 10.2 % |
| 5 | 6.25 | 45.00 | 28.1 % | 16.3 % |
| 6 | 4.0 | 67.20 | 26.9 % | 25.4 % |
| 7 | 3.125 | 100.00 | 31.25 % | 32.5 % |

Full-sweep refresh slightly under v3's ≈ 301 ms (one 5.8 ms band and one boundary-settle
fewer). Full delay table lives in `src/data/profiles/cal_63_air_v2.json`;
`cal_63_air_v1.json` (cold-anchored delays) and `cal_72_air_v3.json` are retained as
superseded locked profiles.

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

Full-sweep refresh ≈ 301 ms with fw v4.24's time-floored boundary settling (was ≈ 289 ms).
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

Input: 5× LiPo (16.5–21 V), F1 2 A, D4 1N4004 reverse protection, FB1 ferrite bead. A
**dedicated** battery powers the detector (the rover's 40 V supply was too noisy).

**Known supply-noise facts** *(measured, free-air, 10-sample σ):* ~200 µV USB / no flash ·
~250 µV battery / no flash · ~900 µV USB / using flash · ~4000 µV battery / using flash.  Writing to
flash raises the noise floor ~10×.

---

## 13. What makes this design unusual (deliberate, validated choices)

- Sampling the **0.5 V – 4.9 V** band of the flyback decay rather than the usual bottom ~700 mV —
  found to carry more discrimination information and sit well above the noise floor. The
  early-decay top of that range (4.7–4.9 V) is sampled densely, avoiding only the measured
  ~4.45–4.65 V noise zone — see §10.
- **Geometric pulse ladder (×1.5) + top-dense amplitude thresholds** — every band
  interrogates a distinct, evenly spaced slice of log target-τ; the threshold ladder is
  densest where the decay carries the most information (§10). Amplitude-anchored delays
  make the matrix self-normalising across bands.

---

## 14. Open problems

1. **Thermal drift.** Wider pulses heat the TX damping/gate resistors; the drive circuit
   drifts and the sensitive RX side drifts with it. *(Pre-enclosure numbers — re-measure,
   the enclosure may have changed thermal behaviour.)* Post-enclosure signature (§17.8,
   2026-07-14): heavy bands drift −20…−31 mV below their calibrated operating point,
   monotonic with pulse width; light bands ≈ +9 mV high; warm recalibration moves delays
   −56…+16 ns. Mitigation: calibrate fully soaked (cal_63_air_v2).
2. **7805-vs-USB supply-noise mystery.** Onboard 7805 path ~50 % noisier than USB;
   unresolved. *(Re-measure post-enclosure — shielding may have changed the picture.)*
3. **General supply noise floor** (battery vs USB, flash penalty — partially mitigated).
   *(Re-measure post-enclosure.)*
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
8. **Post-enclosure re-measurement backlog.** Noise floors, drift rates, the settled
   top-of-decay level (~4.87–4.89 V observed on heavy bands — bears on the delaycal
   signal-detect ceiling, now 5.0 V), and the §17.4 delay-zone map all predate the
   enclosure and need redoing on the new hardware state.

---

## 15. Repository / file inventory

| File | Role |
|------|------|
| `mcu/pimd_mcu.py` | RP2040 MicroPython firmware (**v4.26**) — both modes, all profiles; BUSY edge sync (v4.19); IRQ critical section + 10 % plausibility gate on raw reads (v4.21); SAMPLE_PULSE_CORRECTION 0.904 µs (v4.22); protocol: freq in Hz, pulse/delay in ns (v4.23); time-floored Mode 2 boundary settling, SETTLE_FLOOR_US 3000 (v4.24); outlier gate on abs(mean) with OUTLIER_GATE_MIN floor — no more latched cells (v4.25); IRQ hold through freq/CC writes via `read_raw_bytes_hold()` — CC-write race closed (v4.26) |
| `mcu/main.py` | One-line board launcher: `import pimd_mcu` |
| `src/pimd_gui.py` | PC PyQt6 GUI **v4.13** — Mode 1 filtered telemetry display; boxcar toggle; 8 ns grid snapping with orange-highlight warnings; no auto-connect; sub-200 µV V/div removed; settings persistence |
| `src/pimd_classviz.py` | PC PyQt6 Mode 2 signature visualiser (**v1.39**) — real-time heatmap + stats table + 64-frame glitch filter; top-bar saved-profile **Load & Run** (sends RAM-only dynamic profile via `D`, replaces the old Profile Builder tab — profile authoring lives in delaycal); session-dump recorder (self-describing per-session CSV to `src/data/sessions/`, embedded profile JSON + per-column map + marks); **Std Dev (rolling N) heatmap mode** (live noise monitor); settledness-gated, glitch-excluding signature captures (v1.31); **registry-backed structured target-metadata capture** — target combo + placement fields from `pimd_target_check.py`, `# mark_target:` session-dump lines, capture provenance (profile_sha8 / fw_version / supply), corpus CSVs to `src/data/corpora/` (v1.32); settings persistence. **Three tabs: Heatmap / Stats / Analysis** — the Analysis tab is the sole capture workbench (live comparison charts, decoupled heatmap + colorbar range control, per-group normalize/scale) and carries the **automated Training cycle** (v1.34–v1.35: one Space press per cycle, auto place/remove detection, 30 s guard countdowns, Save/Ignore) plus capture ergonomics (v1.38: splitter-resizable heatmap vs signature list, new captures auto-checked onto the charts, black live traces, per-parameter green/amber/red quality colouring against editable thresholds). The separate guided **Training Session tab was removed at v1.39** — all capture goes through Analysis |
| `src/pimd_delaycal.py` | PC PyQt6 delay-calibration sweeper (**v1.25**). Coarse+fine two-phase sweep per freq/pulse pair via `*`+`A<n>`; records threshold-crossing delays (clip-release / earliest-valid-sample); 3-d.p. voltage headers; profile export/import; thermal monitoring; zigzag auto-nudge (parallel or sequential) with ceiling latch + lock-on-pass; activity log; settings persistence. **Operational note:** signal-detect ceiling must be 5.0 V post-enclosure (§3 epoch note) |
| `src/pimd_features.py` | Session-CSV / gui_signatures-CSV → training-corpus builder (**v7**, offline CLI). Registry join (`target_id` + structured placement replace free text), hard geometry guard — one `(profile_name, profile_sha8)` per corpus build; direct-ingest path for classviz corpus CSVs; pre-v1.32 free-text inputs loudly rejected, no migration by design |
| `src/pimd_target_check.py` | Shared target-registry loader/validator (**v3**, CLI + library; named `pimd_targets.py` before v3). Reads `src/data/targets/targets_v1.csv`, collects all errors/warnings (ids, enums, numerics, dims order, mass plausibility); never writes the registry. `DEFAULT_REGISTRY_PATH` here is the single source of truth for the registry location — classviz and features both derive from it. Used by classviz (capture-time) and features (build-time) |
| `src/pimd_corpus_check.py` | Corpus-level acceptance checker (**v1.6**, offline CLI) — shape distance-invariance, split-half SNR, repeat consistency, falloff fit, optional `--baseline` cross-campaign comparison; one flat PASS/AMBER/FAIL/SKIP table, exit 1 on any FAIL, so it can gate a capture day. Reads the v1.32+ `target_id`/`distance_mm` schema only (legacy `target`/`distance_cm` cleanly rejected). Distances are data-driven — a target at ≥2 distances gets shape rows, ≥3 gets a falloff fit; repeats key off the `repeat_idx` column against the physical placement tuple; the old canary-drift check is retired (per-capture air bracketing does that correction in features). Air captures carry no distance: they appear in the SNR check as `@air` and are excluded from every distance-keyed check |
| `src/data/targets/targets_v1.csv` | Human-authored registry of 22 physical target objects — single source of target physical metadata (id, material, shape, dims, mass, …). Human-owned data: tooling reads and validates only. Relocated here from `src/data/training_lists/` at targets v2 (that directory held the removed Training Session tab's run-lists and is gone) |
| `src/data/profiles/` | Locked calibration profiles (firmware↔ML contract, §10). Only the **operating** profile is tracked in git — **`cal_63_air_v2.json`**; the superseded `cal_63_air_v1.json`, `cal_72_air_v3.json`, `cal_72_air_v2.json` are retained on disk but untracked — each is listed individually in `.gitignore` as it is retired. delaycal writes candidate profiles here routinely; those stay visible as untracked until they are either locked (tracked) or retired (ignored) |
| `src/data/corpora/` | Signature-corpus captures from classviz's Analysis tab (`gui_signatures_*.csv`, CORPUS_HEADER schema) — post-enclosure corpus rebuild in progress; untracked in git while capture is underway (working data until a corpus is accepted) |
| `src/pimd111.ui` | Qt Designer UI source for `pimd_gui.py` (sliders/QLineEdit fixed to match code, 2026-07-02) |
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
  the freeze cal adjusted only 1 delay of 72 (+40 ns).
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
  noise, smeared into seconds-scale wander by the 32-deep (~9.2 s) rolling average.
  fw v4.24 floors settling at SETTLE_FLOOR_US = 3 ms per boundary (§8) — bench-verified:
  first-column σ normalised, wander gone. Sweep refresh ≈ 289 → ~301 ms.
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
