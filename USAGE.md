# PIMD — Usage Guide (USAGE.md) v1.7

Intent, operation and pipeline flow for each application in the repo — one page per
app. This is the working orientation document; **specs, measured values, the serial
protocol and invariants live in `DESIGN.md`**, which is ground truth. Version numbers
here reflect the source headers at the time of writing.

<!-- Changelog
v1.7 2026-07-24 classviz v1.39 → v1.42: new §5 Shape Space bullet (fourth tab,
                two-mode air reference, scratch captures) and the §1 diagram
                follows. §5 profile-switch diagnostic amended — the blank
                heatmap it described was largely the v1.42 glitch-buffer bug,
                not a lost `G`. New pimd_shape.py (v1) node in the §1 pipeline.
                §4: Import Profile promoted from optional convenience to the
                standard starting point for any recalibration, with the
                settings-persistence trap that motivates it. §6 note corrected —
                pimd_corpus_check.py is tracked and current, not local-only.
v1.6 2026-07-23 pimd_targets.py renamed pimd_target_check.py (v2 → v3) — §1
                diagram and §6 heading/body follow. Stale version references
                corrected: classviz v1.35 → v1.39 in the §1 diagram and the §5
                heading. Dropped the removed `notes` placement field from the
                §5 Analysis bullet and named the v1.38 per-parameter quality
                readout.
v1.5 2026-07-23 classviz v1.36 → v1.39, targets v1 → v2. Training Session tab
                removed (all capture is now the Analysis tab's Training group)
                — §5 bullet dropped and the intent line reworded. Target
                registry relocated to src/data/targets/targets_v1.csv; §7 path
                and the two targets.csv mentions updated.
v1.4 2026-07-22 classviz v1.34 → v1.35 (Training status labels name air/target;
                place/remove countdown flashes red in the final 5 s + beeps on
                the prompt). §5 Training bullet touched.
v1.3 2026-07-22 classviz v1.33 → v1.34 (Training group becomes an automated
                auto-detect cycle: one Space per cycle, auto place/remove
                detection, 30 s countdowns, Save/Ignore). §5 Training bullet
                rewritten.
v1.2 2026-07-21 classviz v1.32 → v1.33 (continuous Training group replaces the
                three-button quick-capture; Supply combo battery|psu), features
                v6 → v7 (doc-only supply vocabulary). §5 rewritten to match.
v1.1 2026-07-15 delaycal v1.24 → v1.25 (APP_VERSION constant re-sync, no
                functional change).
v1  2026-07-15  Initial version. Replaces the docs/ directory (PIMD.md and the four
                per-tool cheat sheets), consolidated into one file, one page per app,
                versions corrected to current source (fw v4.26, classviz v1.32,
                delaycal v1.24, gui v4.13, features v6, targets v1).
-->

---

## 1. Overview & pipeline flow

PIMD is a custom pulse-induction metal detector built for autonomous deployment on a
GPS-surveying rover. Unlike commercial PI detectors, which optimise a single operating
point, PIMD is a programmable multi-band measurement instrument: a drive pulse
energises the TX coil, and on cutoff the RX coil measures the decaying eddy-current
response. The firmware cycles a profile — a calibrated grid of (frequency,
pulse-width, sample-delay) operating points — and reports each complete frame over
USB-serial, producing a 2-D decay-space matrix (frequency band × decay amplitude)
suitable as direct input to an ML classifier. The current operating profile is
`cal_63_air_v2` (7 bands × 9 delays = 63 cells, locked 2026-07-14; DESIGN §10).

The toolchain forms one pipeline:

```
mcu/pimd_mcu.py (fw v4.26, RP2040)          — the measurement primitive
      │  USB-serial, ASCII records (DESIGN §9)
      ├─► src/pimd_delaycal.py (v1.25)      — calibrates sample delays,
      │        exports cal_*.json profiles ──► src/data/profiles/
      ├─► src/pimd_gui.py (v4.13)           — Mode 1 live telemetry / bench monitor
      └─► src/pimd_classviz.py (v1.42)      — Mode 2 heatmap; loads & runs saved
               profiles; captures signatures ──► src/data/corpora/ + src/data/sessions/
                     │        └─ uses src/pimd_shape.py (v1) — shared feature maths
                     │              (family / crossing / decay persistence)
                     ▼
          src/pimd_features.py (v7) + src/pimd_target_check.py (v3)
               — registry-validated training-corpus builder ──► ML corpus
```

Typical workflow: flash the firmware once (DESIGN §16) → run **delaycal** after a
full thermal soak to produce a calibrated profile → lock the profile JSON → run
**classviz**, Load & Run the locked profile, capture target signatures against the
`targets_v1.csv` registry → build the corpus with **features**. **gui** is the
independent Mode 1 bench monitor used for noise/drift investigation at a single
operating point.

Two acquisition modes (never run both at once; always `E` between mode switches):
**Mode 1** — interrupt-driven filtered path (LTC2508-32 SDOA, 32-bit), single
operating point, downsampled rolling mean + σ. **Mode 2** — interleaved rolling-
average sweep across the profile's cells, raw 14-bit path (SDOB), one `W` record per
complete sweep.

---

## 2. pimd_mcu — RP2040 firmware (v4.26)

**Intent.** The MCU is deliberately a *simple primitive* (DESIGN §11): it drives the
coil, times the ADC sample point with ns precision, averages, and streams labelled
ASCII records. No scan scheduler, no PC-driven engine, no flash writes in the hot
path. MicroPython, pure Python only (`mcu/pimd_mcu.py` + one-line `mcu/main.py`
launcher).

**Operation.**
- Generates phase-locked TX pulse + ADC sample trigger on GPIO4/GPIO5 — same PWM
  slice 2, ≈5 ns jitter (invariant: never split the pair across slices).
- Mode 1: filtered 32-bit acquisition (SPI1/SDOA), downsample 256/1024, `*` records.
- Mode 2: profile sweep on the raw 14-bit path (SPI0/SDOB), per-cell rolling average
  (32-deep for the operating profiles), one `W` record per sweep, ≤100 Hz emit.
- Commands (details DESIGN §9): `S`/`E` start/stop Mode 1 · `*f,p,d,ds` configure
  (pulse/delay in **ns**) · `Q<n>`+`G` select profile & start Mode 2 · `D…` define
  RAM-only dynamic profile (values in **µs** — mixed units, don't confuse) ·
  `A<n>` boxcar average · `V`/`L`/`B` identify / list profiles / diagnostics.
- Profiles: 5 compiled-in (0 FAST_TRACK, 1 CLASSIFY, 2 SCOPE_CAL, 3 TRACK_25K,
  4 CLASSIFY_EP) plus index 5 = dynamic via `D`, lost on reset. The operating
  profile is sent dynamically by classviz — compiled-in profiles are bring-up/debug
  tools.

**Robustness (v4.21→v4.26).** IRQ critical section around BUSY-sync + SPI read, now
held through the freq/CC hardware writes (v4.26 — closes the CC-write race that
poisoned the second cell of band 1); plausibility gate on raw reads with an absolute
floor so near-zero cells can't latch (v4.25); time-floored band-boundary settling,
SETTLE_FLOOR_US = 3 ms (v4.24); SAMPLE_PULSE_CORRECTION 0.904 µs baked into the duty
calculation.

**Deploy:** copy `pimd_mcu.py` + `main.py` to the board, then **power-cycle** (DESIGN
§16 — `mpremote reset` does not re-enumerate USB reliably). Bench-test over any
115200 serial terminal: `V` → identify, `Q4` `G` → stream, `E` → stop.

---

## 3. pimd_gui — Mode 1 telemetry GUI (v4.13)

**Intent.** The primary operator interface for **Mode 1 filtered telemetry** —
real-time voltage/noise monitoring at a single operating point. This is the bench
tool for noise-floor, drift and thermal investigations; it neither starts nor
consumes Mode 2 streams (`W` records are silently ignored).

**Operation.**
- Scrolling line chart of the filtered voltage; optional orange **boxcar
  raw-average** overlay (`A<n>` poll every 250 ms, default n = 64).
- Sends `*<freq_hz>,<pulse_ns>,<delay_ns>,<ds>` on every parameter change; Start
  sends `S` then the config in one press.
- Freq/pulse/delay entry snaps to the 8 ns PWM grid and clean 125 MHz divisors —
  **orange highlight** = off-grid value (the firmware would quantise silently).
- Rolling drift slope (µV/s) over the last 100 packets; V/div floor 200 µV.
- Every `*` record is logged to a per-run CSV (`src/data/P<DDMM-HHMMSS>.csv`).

**Notes.** No auto-connect — Connect first, then Start. Output buffer is flushed
before `E` so queued `A<n>` polls can't delay the stop at slow sample rates. The
UI fields display µs but the wire protocol is ns (conversion internal). Settings
(port, params, toggles, geometry) persist in `src/data/gui_settings.json`.

---

## 4. pimd_delaycal — delay calibration sweeper (v1.25)

**Intent.** Produces the calibrated profiles everything else depends on. For each
configured (freq, pulse) pair it finds the sample delay at which the decay crosses
each target voltage threshold (the clip-release / earliest-valid-sample point), and
exports the result as a classviz-compatible profile JSON
(`src/data/profiles/cal_<ts>.json`). Geometry from this tool is the firmware↔ML
contract (DESIGN §10) — profiles are locked after calibration, never edited in place.

**Operation.**
- **Sweep:** coarse hunt (1 µs steps) until signal appears below the signal-detect
  ceiling, back up one step, then fine steps (0.1 µs) interpolating each threshold
  crossing; delays snapped to the 8 ns grid, stored to 3 d.p. Live table: rows =
  freq/pulse pairs, columns = threshold voltages.
- **Thermal:** streams Mode 2 with the calibrated profile (via `D` + `Q5` + `G`),
  live latest-mean and rolling-σ per channel — used to verify thermal soak and
  drift before locking a profile.
- **Auto Nudge:** iterative per-channel delay adjustment to escape noisy zones —
  zigzag (− first, then +) on the 8 ns grid with a ±cap, ceiling latch (channels
  that hit no-signal territory are forced down-only), lock-on-pass, parallel or
  sequential evaluation; exports the profile automatically on finish.
- **Import Profile** loads an existing JSON — **start every recalibration here**, see
  below. Also used for re-checking a profile without a fresh sweep.

**Operational notes.** Post-enclosure, the top of decay sits at ≈4.87–4.89 V, so the
**signal-detect ceiling must be set to 5.0 V** (DESIGN §3 epoch note) or the coarse
hunt false-triggers. Calibrate only after a full warm-up soak — heavy-band delays
move tens of ns between cold and warm (see cal_63_air_v2 rationale, DESIGN §10).
Settings persist in `src/data/delaycal_settings.json`.

**Always Import Profile before recalibrating.** The persisted settings are *not*
anchored to the currently locked profile, so editing a field or two and pressing run
inherits a stale baseline for everything else — band plan included. This has already
produced a plausible-looking export carrying the excluded 6 µs band and a threshold
short of one value (2026-07-24; DESIGN §15 delaycal row). Nothing in the export path
flags a departure from the DESIGN §10 band plan, so the procedure is the guard: load
the current locked profile, edit what you mean to change, then sweep.

---

## 5. pimd_classviz — Mode 2 signature visualiser & capture (v1.42)

**Intent.** The Mode 2 workhorse: renders each sweep frame as a real-time heatmap of
signed per-cell deviation from an air baseline (blue = non-ferrous/opposing, red =
ferrous/reinforcing), and is the **only capture path for the ML corpus** — the
Analysis tab's automated Training cycle, with structured target metadata
validated against the target registry.

**Operation.**
- Connects over USB-serial; **Load & Run** on the top bar sends any saved profile
  JSON as a RAM-only dynamic profile (`E` → `D` → `Q5` → `G`) — no reflashing.
  Profile authoring lives in delaycal; this app only loads locked profiles.
- **Heatmap tab:** Δ deviation / Z-normalised / RAW display modes; static, rolling-
  median or nominal-threshold baselines; **Std Dev (rolling N) mode** = live noise
  monitor per cell; 64-frame median glitch filter (display path only — recordings
  stay faithful to the wire).
- **Stats tab:** per-cell Latest / Mean / Std with green/yellow/red thresholds.
- **Analysis tab:** live comparison charts, a **Signatures** group (signature file
  management, registry-validated target combo from `targets_v1.csv` via
  `pimd_target_check.py`, structured placement fields — distance_mm, axes, offsets,
  medium, repeat_idx — a per-parameter green/amber/red readout and Save/Delete)
  and a **Training** group
  (v1.35): an automated auto-detect capture cycle. Press **Start Training**; two
  status areas show **A** = state, naming air vs target (yellow SETTLING → blue
  COLLECTING with a frames-left countdown → green ACQUIRED; the leading air keeps
  rolling, the target is held once captured) and **B** = the next instruction.
  The place/remove countdowns in **B** flash (red in the final 5 s) with a beep
  when each prompt appears. Once the leading air is green, B says **Press Space** — the one
  Space press per cycle locks the last N frames as the leading air and starts a
  30 s **place target** countdown. The app **auto-detects** placement (signal
  re-settles with mean |Δ| from the locked air above the **Detect ≥ mV**
  threshold), profiles the target, then prompts **remove target** (another 30 s)
  and **auto-detects** removal (Δ back below Detect) to take the trailing air.
  The completed signature's metrics are presented with flashing **Save Sig /
  Ignore Sig**; meanwhile the trailing air keeps rolling as the next cycle's
  leading air, so after deciding you just press Space again. A missed 30 s
  countdown aborts that signature (session stays live). The **Space override**
  checkbox lets Space also force-advance a phase manually if auto-detect stalls.
  Collection stays settledness-gated (mean rolling σ ≤ **Settle ≤ mV**, default
  1.0) and glitch-excluded. Saves append to
  `src/data/corpora/gui_signatures_*.csv` with full provenance (profile_sha8,
  fw_version, tool_version, supply — `battery|psu`).
- **Shape Space tab (v1.42):** exploration, not capture. Every loaded signature is a
  point in a selectable 2-D feature space (X/Y/Colour combos), with the live frame
  moving through it as a yellow dot. Five docks — Scatter, Band Curves, Crossing
  Ladder, Tile Inspector, Gauges — are movable and floatable; the layout persists,
  and **Reset layout** restores the default. Feature maths comes from
  `pimd_shape.py`; family (a sign test) and decay persistence (a magnitude test) are
  always shown side by side and neither overrules the other.
  - **Two modes, and Space is the only thing that moves between them.** In **air**
    mode every clean frame feeds a rolling buffer and the cursor sits pinned at the
    origin; the indicator goes yellow → **green** once a full buffer is collected.
    **Space** snapshots that reference and enters **measure** mode, where the cursor
    moves against it. Space again returns to air, clearing the buffer. This tab does
    **not** use the Heatmap tab's baseline — on a static reference the whole tab is
    meaningless within a minute, because drift accumulates as a coherent term the SNR
    gate cannot catch (DESIGN §14.1). Nothing auto-detects a target arriving or
    leaving; that is deliberate and physical, not a missing feature.
  - **Air age matters more than it looks.** The gauge goes amber at 60 s because a
    60 s-old reference already carries ~1 mV/cell — the order of a weak target
    (DESIGN §17.10). Re-arm air often.
  - **Mixed profile geometries are allowed here and marked** — squares/diamonds and a
    standing banner for captures from another profile. They are comparable in kind,
    **not calibrated against each other**. Nothing here writes a corpus.
  - **Save Scratch…** captures an *unregistered* object to
    `src/data/scratch/gui_scratch_<date>.csv` — never into `src/data/corpora/`.
    Promotion means registering the object in `targets_v1.csv` and recapturing
    through the Analysis tab.
- **Session-dump recorder:** self-describing per-session CSV to
  `src/data/sessions/` — embedded profile JSON, per-column map, `# mark:` /
  `# mark_target:` lines — the input format for `pimd_features.py`.

**Notes.** Always `E` before switching profiles (Load & Run does this itself).
W-frames with a stale profile index are silently dropped, so a **persistently** blank
heatmap after a profile switch means `G` went out before the board confirmed the
profile. *(Amended v1.7: a heatmap reading ~0 for roughly the first 10 s after connect
or after a profile change was usually the glitch-buffer bug fixed in v1.42 — its
median started at zero, so every early frame was flagged as a glitch. On ≤ v1.41 that
is the more likely explanation, and any bench note resting on the older wording should
be treated as suspect.)* Settings persist in `src/data/classviz_settings.json`
(written on close only).

---

## 6. Corpus pipeline — pimd_features (v7) + pimd_target_check (v3)

**Intent.** Offline CLI stage that turns classviz output into the ML training
corpus, enforcing the two contracts that make the corpus trustworthy: every row
joins a **registry-validated target** with structured placement, and every corpus
build is **geometry-guarded** so frames from different profile geometries can never
mix (DESIGN §10 invariant).

**Operation — `pimd_target_check.py` (registry).**
- Loads and validates `src/data/targets/targets_v1.csv` — the human-authored
  registry of physical target objects (id, material, shape, dims, mass, …). Read
  only; the registry is human-owned data and is never written by tooling.
- Hard errors (duplicate/malformed `target_id`, bad enum, unparseable numeric) vs
  warnings (unsorted dims, implausible mass, …). CLI:
  `python pimd_target_check.py [--registry PATH]` — prints the target table and every
  issue; exit 1 on any error. Shared by classviz (capture-time validation) and
  features (corpus-build validation), so both agree on what a valid target is.

**Operation — `pimd_features.py` (corpus builder).**
- Inputs: classviz session dumps (`src/data/sessions/`, segmented via
  `# mark_target:` lines) and/or direct-ingest `gui_signatures_*.csv` files
  (already per-cell — registry join only).
- Output: long-format training-corpus CSV — one row per cell per capture, columns
  per `CORPUS_HEADER` (structured placement + provenance:
  profile_name/profile_sha8/fw_version/tool_version/supply).
- Guards: a build spanning more than one `(profile_name, profile_sha8)` group is a
  hard error naming every offending file; unknown `target_id` is a hard error;
  pre-v1.32 free-text-schema files are loudly rejected — **no migration path, by
  design** (the post-enclosure corpus is rebuilt from zero).

**Notes.** Run inside the venv (DESIGN §16). `pimd_corpus_check.py` (v1.6) is the
corpus-level acceptance checker — run it to gate a capture day; it is tracked and
maintained against the current schema (DESIGN §15). The previous-epoch analysis tools
(`pimd_classify.py`, `pimd_v2_findings.py`) are kept local-only and untracked pending
the new corpus.
