# PIMD — Usage Guide (USAGE.md) v1.28

Intent, operation and pipeline flow for each application in the repo — one page per
app. This is the working orientation document; **specs, measured values, the serial
protocol and invariants live in `DESIGN.md`**, which is ground truth. Version numbers
here reflect the source headers at the time of writing.

<!-- Changelog
v1.28 2026-08-04 gui v4.13 → v4.14. §3 rewritten around the pack/board-temp gauges,
                the wider pulse/delay range and its period-fit readout, session
                logs moving to data/sessions/, and Connect/Start matching the
                other apps; the .ui file is gone. §1 diagram.
v1.27 2026-07-31 classviz v1.66 → v1.67, features v11 → v12, corpus_check v1.8 → v1.9.
                §5's Analysis bullet: the new Tilt (°) input and the tilt_deg column —
                zero reference, the enabled-only-when-z rule, its place in the
                placement tuple, and the pre-v1.67 corpus migration it needs.
v1.26 2026-07-30 classviz v1.65 → v1.66, features v9 → v10. §5's Pack V sub-bullet:
                the logged line now carries age_s. New §5 sub-bullet for the
                '# soak:' run/idle lines and what idle_before_s does NOT mean.
v1.25 2026-07-30 classviz v1.64 → v1.65. §5's Pack V sub-bullet: appending to a corpus
                captured before features v9 keeps that file's own columns, so pack_v is
                simply not recorded there — start a new file if you want it per capture.
v1.24 2026-07-30 classviz v1.61 → v1.64, features v8 → v9, corpus_check v1.7 → v1.8,
                fw v4.26 → v4.27. §5's Session-dump bullet rewritten: auto-logging
                (v1.63, previously undocumented here), the pack-voltage track, stall
                lines, and the window span guard. §5 gains a chart-pause note. §2 and
                §6 version numbers follow.
v1.23 2026-07-28 classviz v1.60 → v1.61. §5's Analysis bullet: signature rows now
                carry long axis and repeat, and the row colour is per target
                (one hue per target_id, shaded per capture). §1 diagram.
v1.22 2026-07-28 classviz v1.57 → v1.60. §5's Analysis bullet: face_normal and the
                X/Y offsets are no longer capture inputs (written na/0/0; the CSV
                schema is unchanged). Note the targets_v1.csv → targets_v3.csv
                registry reference. §1 diagram.
v1.21 2026-07-28 classviz v1.56 → v1.57. §5's Training paragraph: the central-60%
                trim is now named, A carries the surviving count, and Frames
                defaults to 100 (below which every capture is stamped 'short').
                §1 diagram.
v1.20 2026-07-28 classviz v1.55 → v1.56. §5's Training paragraph rewritten around
                the A/B status text: each state now names the gate holding it up
                (σ vs Settle, Δ vs Detect) and the frame count, so a stalled
                phase says why. §1 diagram.
v1.19 2026-07-28 classviz v1.54 → v1.55. §5's Training paragraph: a Space-forced
                placement now auto-detects removal as well (the v1.41 latch is
                lifted), with Space still the fallback for a target too weak for
                either direction. §1 diagram.
v1.18 2026-07-28 classviz v1.50 → v1.54. §5 gains a Trigger Levels bullet (the
                five-gauge column, draggable thresholds, what each Detect mode
                measures) and an Auto-start bullet. §5's Training paragraph:
                removal auto-detect now requires an unsettle transient and tests
                the target snapshot, not the aged leading air (§17.10). §1 diagram.
v1.17 2026-07-26 delaycal v1.28 → v1.29 (Export Profile save dialog: filename sets the
                profile `name`, plus an editable auto-generated notes field). §4's
                intent, Auto Nudge, Import and new Export bullets; §1 diagram.
v1.16 2026-07-26 delaycal v1.25 → v1.28 (Compare Profiles tab; fine step now in ns
                down to the 8 ns grid; THERMAL auto-starts on sweep completion).
                §1 diagram and §4 updated.
v1.15 2026-07-25 classviz v1.49 → v1.50. §5's SNR-gate sub-bullet: a below-gate
                frame now leaves no trail at all rather than a yellow one, and
                still ages the trail window along. §1 diagram follows.
v1.14 2026-07-25 classviz v1.48 → v1.49 (custom band pair restore fix). Version
                references only — §1 diagram and §5 heading.
v1.13 2026-07-25 classviz v1.47 → v1.48. §5's Scale sub-bullet gains the
                rank-axis grid rule and the zero rails following the curve.
                §1 diagram follows.
v1.12 2026-07-25 classviz v1.46 → v1.47. §5's Family Plane bullet gains a Scale
                sub-bullet (four spacing curves, why no log) and an axis
                sub-bullet explaining what a band-range-mean axis is and why
                the middle of the plane is empty. §1 diagram follows.
v1.11 2026-07-25 classviz v1.45 → v1.46. §5's Family Plane bullet gains a Save
                Scratch… sub-bullet (plotted immediately, as a triangle, listed
                under △ alongside any loaded corpus); star → triangle in the
                symbol legend. §1 diagram follows.
v1.10 2026-07-25 classviz v1.44 → v1.45. §5's heatmap colour-scale sub-bullet is
                rewritten around the colorbar working as a real range slider
                (handles at Min/Max, saturation tails); the Family Plane bullet
                and its SNR-gate sub-bullet now say the live cursor is yellow
                below the gate and green at or above it. §1 diagram follows.
v1.9 2026-07-24 classviz v1.43 → v1.44. §5 gains the Analysis heatmap's explicit
                Min/Max colour scale (and why Auto is wrong for Std Dev) and the
                signature dialogs' remembered directory. §1 diagram follows.
v1.8 2026-07-24 classviz v1.42 → v1.43. The fourth tab is renamed Shape Space →
                Family Plane Analysis; §5's bullet renamed and extended with
                material tags, the per-axis custom band ranges and the
                clickable Crossing Ladder. §1 diagram version follows.
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
      ├─► src/pimd_delaycal.py (v1.29)      — calibrates sample delays,
      │        exports cal_*.json profiles ──► src/data/profiles/
      ├─► src/pimd_gui.py (v4.14)           — Mode 1 live telemetry / bench monitor
      └─► src/pimd_classviz.py (v1.61)      — Mode 2 heatmap; loads & runs saved
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

## 2. pimd_mcu — RP2040 firmware (v4.27)

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

## 3. pimd_gui — Mode 1 telemetry GUI (v4.14)

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
- **Pulse 4–150 µs, delay 4–250 µs** (v4.14) — the full range the widest tracked
  profile uses, so Mode 1 can sit on any cell Mode 2 sweeps. The readout under
  the sliders gives drive duty and `pulse+delay` against the period, and turns
  red when the pair no longer fits inside one period — the config the firmware
  rejects outright.
- **Pack and board-temperature gauges** (v4.14, needs firmware v4.28+) — battery
  icon showing state of charge with the measured pack volts and which DESIGN §12
  data-quality zone they sit in, plus a board-temp bar. Fed by the firmware's
  unsolicited `P` telemetry and a 10 s `V` poll. A latched low-voltage lockout
  turns the gauge red, stops the run, and is spelled out in the alert line.
  The temperature scale is a **placeholder** until the thermistor front end
  exists — read it as a trend, not a calibrated figure.
- Rolling drift slope (µV/s) over the last 100 packets; V/div floor 200 µV.
- Every `*` record is logged to a session CSV
  (`src/data/sessions/gui_<YYYYmmdd_HHMMSS>.csv`), opened on **Start** — a short
  `#` header, then the records verbatim, with `# sensor:` lines interleaved as
  pack/temp telemetry arrives.

**Notes.** No auto-connect — Connect first (Start stays disabled until there is a
port), then Start. Connect sends `E` then `V`, as classviz and delaycal do. Output
buffer is flushed before `E` so queued `A<n>` polls can't delay the stop at slow
sample rates. The UI fields display µs but the wire protocol is ns (conversion
internal). Settings (port, params, toggles, geometry) persist in
`src/data/gui_settings.json`. There is no `.ui` file — the window is built in
code, like every other app here (v4.14).

---

## 4. pimd_delaycal — delay calibration sweeper (v1.29)

**Intent.** Produces the calibrated profiles everything else depends on. For each
configured (freq, pulse) pair it finds the sample delay at which the decay crosses
each target voltage threshold (the clip-release / earliest-valid-sample point), and
exports the result as a classviz-compatible profile JSON in
`src/data/profiles/`. Geometry from this tool is the firmware↔ML contract
(DESIGN §10) — profiles are locked after calibration, never edited in place.

**Operation.**
- **Sweep:** coarse hunt (1 µs steps) until signal appears below the signal-detect
  ceiling, back up one step, then fine steps (set in ns, down to the 8 ns PWM grid;
  100 ns default) interpolating each threshold crossing; delays snapped to the 8 ns
  grid, stored to 3 d.p. Live table: rows = freq/pulse pairs, columns = threshold
  voltages.
- **Thermal:** streams Mode 2 with the calibrated profile (via `D` + `Q5` + `G`),
  live latest-mean and rolling-σ per channel — used to verify thermal soak and
  drift before locking a profile. Starts automatically when a sweep finishes
  (**Auto on completion**, default on), which also measures every cell for the
  Compare Profiles tab.
- **Auto Nudge:** iterative per-channel delay adjustment to escape noisy zones —
  zigzag (− first, then +) on the 8 ns grid with a ±cap, ceiling latch (channels
  that hit no-signal territory are forced down-only), lock-on-pass, parallel or
  sequential evaluation. On finish it auto-saves under a timestamp name without
  prompting (an unattended run must not block on a dialog) — press **Export Profile**
  afterwards to save it under the locked name with notes.
- **Export Profile** asks for the filename, then shows the profile's **notes** for
  editing before writing. The JSON's `name` field is set from the filename you
  choose — `name` is what corpora record as `profile_name` and what the cross-epoch
  guard reports, so naming the file names the epoch. The notes are pre-filled with
  the sweep's start/end time and duration, the sweep and Auto Nudge parameters
  (including std-dev N), the Auto Nudge outcome, the geometry, and the notes of any
  profile imported this session, attributed — add your own conditions (thermal state,
  soak time, pack voltage) before saving. Nothing else is reproducible without them.
- **Import Profile** loads an existing JSON — **start every recalibration here**, see
  below. Also used for re-checking a profile without a fresh sweep. Its notes and
  filename are carried forward to the next export.
- **Compare Profiles tab:** pick any two profiles — including
  `<current calibration table>`, so a sweep can be checked against a reference before
  it is exported — and read the timing convergence per cell. Rows are cells the two
  share at the *same* band and intended target voltage; columns give both delays, the
  **Δ in ns** (green within one 8 ns step, yellow within five, red beyond), both
  measured voltages, their difference, and each profile's error against target. Voltages
  come from THERMAL / Auto Nudge soaks run this session and show `—` where a delay has
  never been streamed — they are not stored in the profile JSON and do not survive a
  restart. Footer reports mean/RMS/max |Δ| and any cells present in only one profile.

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

## 5. pimd_classviz — Mode 2 signature visualiser & capture (v1.66)

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
  `pimd_target_check.py`, structured placement fields — distance_mm, long_axis,
  tilt_deg, medium, repeat_idx — a per-parameter green/amber/red readout and Save/Delete;
  each signature row reads `target @distance  axis  r<n>  amp=… SNR=… [quality]`,
  v1.61, so the several captures that share a target and distance are tellable
  apart, and its **colour is per target** — one hue per `target_id`, shaded and
  jittered slightly across that target's captures, so a target reads as one family
  while its individual overlay curves stay separable on the charts. The hue is
  derived from the target_id itself, so it is the same colour in every session and
  does not shift as the list grows)
  and a **Training** group
  (v1.35): an automated auto-detect capture cycle. Press **Start Training**; two
  status areas show **A** = state and **B** = the next instruction. Since v1.56 both
  carry the numbers behind the state, so a phase that is not advancing says why:
  **A** pairs the live measurement with the gate currently blocking it —
  `SETTLING air — σ0.512 > 0.400` while unsettled, `WAITING target — Δ0.028 < 0.500`
  once settled but short of Detect, `COLLECTING target — 47/120 (28 central)` while a
  window fills, `HOLDING target — lift it to release` when nothing has moved yet, then
  `MOVING`/`MOVED` through a removal. **B** carries the instruction plus either the
  guard countdown or the frame count. The colour ladder is unchanged (yellow settling
  or waiting → blue collecting → green acquired); the leading air keeps rolling and the
  target is held once captured.
  The place/remove countdowns in **B** flash (red in the final 5 s) with a beep
  when each prompt appears. Once the leading air is green, B says **Press Space** — the one
  Space press per cycle locks the last N frames as the leading air and starts a
  30 s **place target** countdown. The app **auto-detects** placement (signal
  re-settles with mean |Δ| from the locked air above the **Detect ≥ mV**
  threshold), profiles the target, then prompts **remove target** (another 30 s)
  and **auto-detects** removal (v1.54: the signal must first *unsettle* — lifting
  the object is a physical event — and then re-settle more than Detect away from
  the **target** snapshot taken moments earlier). Removal used to be tested as
  "Δ back below Detect" against the *leading air*, a reference by then a whole
  target window older; DESIGN §17.10 measured that as unable to work, since at
  ~50 µV/s a 150 s-old air reference reads more deviation than the target does,
  so removing the object made |Δ| go **up**. Both halves of the new test matter:
  drift can pass Detect on magnitude alone, but it never unsettles the signal.
  The completed signature's metrics are presented with flashing **Save Sig /
  Ignore Sig**; meanwhile the trailing air keeps rolling as the next cycle's
  leading air, so after deciding you just press Space again. A missed 30 s
  countdown aborts that signature (session stays live). The **Space override**
  checkbox lets Space also force-advance a phase manually if auto-detect stalls.
  A Space-forced *placement* still gets removal auto-detect (v1.55 — the v1.41 latch
  that blocked it existed for the old removal rule, which could fire on the first
  settled frame); Space stays permitted through the rest of that cycle without the
  override checkbox, because a target too weak to clear Detect going on will not
  clear it coming off either.
  Collection stays settledness-gated (mean rolling σ ≤ **Settle ≤ mV**, default
  1.0) and glitch-excluded.
  **Not every collected frame is used (v1.57).** `pimd_features` trims 20% off each
  end of the window — target *and* both air anchors — before taking stats
  (`CENTRAL_FRACTION` 0.60), so 120 frames give 72 central. The `(N central)` in **A**
  is what would survive if the window were committed *now*, so it doubles as the
  warning before a Space force-advance; the row stays yellow until that count clears
  `MIN_CENTRAL_FRAMES` (60), then goes blue and green. **Frames** therefore defaults to
  **100**, the smallest value whose central 60% reaches 60 — below that the spinbox
  turns amber, because every capture at that setting is stamped `short` in the corpus. Saves append to
  `src/data/corpora/gui_signatures_*.csv` with full provenance (profile_sha8,
  fw_version, tool_version, supply — `battery|psu`).
  **`face_normal` and the X/Y offsets are not capture inputs (v1.60).** They were never
  set, and `face_normal` being a *persisted* combo meant a value chosen once silently
  rode along on every later capture — all 12 captures of a tube in the first v3 corpus
  carry `face_normal=z`, which is meaningless for that shape. They are still written to
  the CSV, the session dump's `mark_target:` line and the placement tuple, at `na`/0/0:
  the schema and `pimd_corpus_check.PLACEMENT_FIELDS` are unchanged, and older corpora
  keep their real values. **`long_axis`** stays, and is the direction the registry's
  `dim_a` points: `x` = coil long axis (520 mm), `y` = coil short axis (360 mm, the rover's
  direction of travel), `z` = coil normal (vertical, target standing at right angles to
  the coil plane).
  **`Tilt (°)` records oblique poses (v1.67).** `long_axis` can only say 0° or 90° to the
  coil axis, which is why the 2026-07-31 analysis could confirm the two-basis model's
  rank-2 structure but not its mixing law. The spinbox is enabled only when **Long axis
  is `z`** (a tilt is defined relative to the coil normal) and *a signature file is open*,
  and it writes the new `tilt_deg` corpus column: **0 = `dim_a` straight down the coil
  axis** — the same pose as `long_axis=z` — **90 = `dim_a` lying in the coil plane**, the
  same pose as `x`/`y`. The two ends are deliberately redundant with `long_axis`; the
  value of the column is the angles in between.
  `tilt_deg` **joins the placement tuple**, so 0°/30°/60° at one distance are three
  placements with independent `Repeat #` sequences rather than three repeats of one.
  It is written **blank** for any other `long_axis`, and blank/absent/unset all key
  alike (`pimd_corpus_check.PLACEMENT_BLANK_FIELDS`) so adding the column re-grouped
  nothing in the corpora written before it — but a **recorded `0` is a real axial
  capture and is not the same as blank**. Like `pack_v` it is an **optional** column
  (`OPTIONAL_FIELDS`), so older corpora still load. It is deliberately **not persisted
  to settings** — it reopens at 0 every launch, so an angle set once cannot silently
  ride along into a later session the way `face_normal` did.
  **A corpus file written before v1.67 must be migrated before it can record a tilt:**
  corpus append writes the *file's own* header columns (v1.65), so appending to a file
  with no `tilt_deg` column silently drops the angle. `gui_signatures_targets_v3_20260728_142316.csv`
  has been migrated (backup kept as `.bak-*-pre-tilt`); any other file needs the column
  appended to its header and a blank cell to every row, or start a fresh file.
  - **Trigger Levels (v1.51–v1.54).** A five-gauge column at the top-left of the
    Analysis tab's chart area, for setting the Training thresholds against the live
    signal instead of guessing and then debugging a cycle. Each bar carries a dashed
    marker you can **drag** to set the underlying value: **Settle ≤** (mean rolling σ,
    the gate itself), **Detect ≥**, **Amp (log)** (the Green-when Amp threshold) and
    **SNR** (the Family Plane gate). **Air age** is read-only.
    The **Detect** row names its own reference in the unit column, because it changes
    with the phase: `mV vs air` while waiting for placement, `mV vs target` while
    waiting for removal, and `mV wander` the rest of the time — the latter being how
    far the air moves on its own over one settle window, i.e. the floor the Detect
    level has to clear. Green always means "the thing you are waiting for": air
    quieter than Detect in wander mode, a crossing in the two gated phases.
    **Air age** is how long ago the leading air was locked, against the budget for one
    healthy cycle (two collecting windows plus two 30 s guards, scaled by the measured
    sweep rate) — red means the cycle is dragging, not that anything is wrong with the
    reading. On the bench in clean air expect wander around 0.2–0.3 mV, comfortably
    under a working Detect of 0.5.
  - **Auto-start (v1.53).** Launching the app connects to the remembered port and
    loads & runs the remembered profile, so it comes up streaming. No remembered port,
    a port that will not open, or no remembered profile each leave it idle exactly as
    before with the reason in the status bar.
  - **Heatmap colour scale (v1.44).** The Analysis heatmap's **Scale** is either
    **Auto** or an explicit **Min**/**Max** in µV. Auto fits the whole data range,
    which is the wrong window for **Std Dev (rolling N)**: a rolling σ field sits in
    a narrow band well above zero, so an auto range anchored at 0 spends most of the
    ramp on values that never occur and every cell reads the same colour. Unchecking
    Auto seeds Min/Max from what is currently on screen; tighten to just either side
    of the quiet-cell level and the noisy columns separate out. The limits persist.
  - **The colorbar is the same control, as a slider (v1.45).** Its two handles sit at
    **Min** and **Max**, and the axis under it spans a little more than that window —
    the pale flat tails outside the handles are the values the scale saturates on.
    Drag either handle to set that limit; the spinboxes follow, and vice versa. The
    bar re-scales only when the window no longer fits it sensibly, so a handle stays
    where it is put. In **Auto** the bar spans exactly the fitted range and the
    handles are hidden — there is nothing outside the window to show, and a drag
    would not survive the next frame.
  - **Load signatures… / Open for editing…** reopen in the last directory used,
    across sessions. **New file…** still defaults into `src/data/corpora/`, since
    that is where the capture pipeline expects a corpus to live.
- **Family Plane Analysis tab (v1.43; called Shape Space in v1.42):** exploration, not
  capture. Every loaded signature is a
  point in a selectable 2-D feature space (X/Y/Colour combos), with the live frame
  moving through it as a dot that reads **yellow below the SNR gate and green at or
  above it** (v1.45) — the one verdict the cursor makes about itself; it never takes a
  family colour. Five docks — Scatter, Band Curves, Crossing
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
  - **SNR gate.** Amp(L2)/splithalf below which a shape is not interpreted — below
    it the unit shape is normalised noise that still moves around the plane
    convincingly. Loaded captures below the gate draw hollow; the live cursor draws
    yellow rather than green; and **a below-gate frame leaves no trail at all**
    (v1.50), so the trail is green throughout and shows only the part of a sweep that
    was worth reading. Those frames still age the trail window along, so holding
    below-gate fades the trail out rather than freezing the last good pass on screen.
    Moving the gate re-selects and repaints the trail already on screen. Default 5.0,
    the same line that stamps a capture `noisy`.
  - **Air age matters more than it looks.** The gauge goes amber at 60 s because a
    60 s-old reference already carries ~1 mV/cell — the order of a weak target
    (DESIGN §17.10). Re-arm air often.
  - **Marker shape says where a capture came from** — circle for a registered target
    on the live profile, **triangle for a scratch object**, square for another
    profile's geometry (diamond if both), plus a dashed outline and a standing banner
    for the foreign ones. Filled = above the SNR gate, hollow = below. They are
    comparable in kind,
    **not calibrated against each other**. Nothing here writes a corpus.
  - **Material tags (v1.43).** Each point carries its target's material beside it
    (`Al`, `Fe`, `SS`, `Fe/Zn` for a plated target…), taken from `targets_v1.csv`;
    the same tag is appended to every Crossing Ladder row. A capture whose
    `target_id` is not in the registry reads `?` — that includes every scratch
    object. The tag takes the marker's colour, so under Colour = family a red `Al`
    is a non-ferrous material reading ferrous. Uncheck **Material tags** to clear
    them; they also drop out on their own above 200 drawn points.
  - **Custom band range is per axis (v1.43).** X and Y have their own lo/hi band
    spins, so "custom band range" on both axes compares two different ranges rather
    than plotting a feature against itself. Colour-by "custom band range" reads the
    X pair.
  - **What a band-range axis actually is.** `early`/`mid`/`late`/`custom` are all the
    same quantity — the plain mean of the **unit shape** (`vec` ÷ ‖vec‖₂, so amplitude
    and therefore distance are divided out) over a range of bands. `custom bands 4–6`
    on the 7×9 profile is the mean of 27 of the 63 unit-shape cells, those being the
    three longest pulse widths across all nine threshold columns. Sign follows DESIGN
    §2: ferrous positive, non-ferrous negative. Two consequences worth knowing:
    - It is **hard-bounded** at ±1/√(k·n_delays) — ±0.1925 for 3 of 7 bands — and the
      2026-07-23 corpus reaches 0.160, 83% of that ceiling. Clusters press against a
      wall, which is what the **Scale** control below is for.
    - The empty band across the middle is **the family decision boundary, not a data
      gap**: Colour = family is read off the signs of these same two axes, so points
      near zero are marginal calls and there are few real objects there.
  - **Scale, per axis (v1.47).** Changes the *spacing* along one axis only. Every
    option maps the drawn set's min and max onto themselves — a point keeps its value,
    the ticks still read real feature units, and switching never moves the view.
    - **Expand ends (cube)** and **(atanh)** stretch the two extremes and squeeze the
      middle, which is the right way round for a bounded axis with the decision
      boundary in the void. On the corpus above, the dead middle goes from 48% of the
      Y axis to 15% (cube) or 14% (atanh); atanh is the stronger of the two.
    - **Rank** spaces the drawn points evenly — the most spread of all (dead middle 6%)
      but position stops meaning anything physical and shifts as the drawn set changes.
    - **There is no log option, deliberately.** Log expands near zero and compresses
      the extremes; here nothing lives near zero and everything lives at the extremes,
      so it is backwards — measured, it drives the dead middle from 48% to **85%**.
    - A non-linear axis says so in its label (`custom bands 4–6 [cube]`). The Scale
      combo greys out on **crossing µs**, which already owns its own log-µs ticks.
    - **A rank axis drops its gridlines** (v1.48) — a rank axis is ordinal, so a grid
      over it would draw a metric that is not there. Per axis: rank on Y alone keeps
      the vertical gridlines. The two **zero rails stay** either way, and they follow
      the spacing curve, so the family decision boundary is drawn where the value 0
      actually lands rather than at the middle of the plot. A rail whose axis has no
      zero in range (log₁₀ amplitude, distance) simply stays off-view.
  - **Clicking either the scatter or the ladder** opens that capture in the Tile
    Inspector and rings it in both panels. The ladder holds gated captures only, so
    a below-gate selection rings on the plane and nowhere on the ladder.
  - **Save Scratch…** captures an *unregistered* object to
    `src/data/scratch/gui_scratch_<date>.csv` — never into `src/data/corpora/`.
    Promotion means registering the object in `targets_v1.csv` and recapturing
    through the Analysis tab.
    - **It is plotted the moment it is saved (v1.46)**, as a **triangle**, and joins
      the Analysis tab's signature list under a `△` prefix (the way an editable file's
      rows carry `✎`). It sits *alongside* any loaded reference corpus rather than
      replacing it — which is the point: a scratch grab is taken to see where the
      object lands against that corpus. Saving again re-reads the whole day's scratch
      file, so every scratch taken today stays on the plane.
- **Session-dump recorder:** self-describing per-session CSV to
  `src/data/sessions/` — embedded profile JSON, per-column map, `# mark:` /
  `# mark_target:` lines — the input format for `pimd_features.py`.
    - **A dump opens by itself when the stream starts (v1.63)** — `Auto-log`, on by
      default. Forgetting to press Record is silent and the raw stream cannot be
      reconstructed afterwards; the cost of the opposite mistake is ~13 MB/hour of
      gitignored CSV. This is why the 2026-07-29/30 warm-up sessions could be analysed
      at all. An explicit **Stop** stays stopped until the stream is next started.
    - **Pack V + Log V (v1.64).** Enter the measured pack voltage; `Log V` timestamps
      it into the dump as a `# pack_v:` line, and the current value is stamped into
      every signature capture's `pack_v` column. Log it **every ~20 min** — the status
      bar nags with the reading's age. Analysis interpolates between entries, so what
      you are building is a voltage *track*: one reading cannot describe a run over
      which a 6S pack falls ~2.5 V. 0.00 reads `—` and means not measured. Note the
      corpus column takes the field's **current value**, not a fresh reading — so
      re-enter it as you go, or captures hours apart all carry the same voltage.
      Appending to a corpus captured before v9 keeps that file's own columns, so
      `pack_v` is not recorded there at all (v1.65); start a new signature file if you
      want it per capture. The logged comment line carries **`age_s`** (v1.66) —
      seconds since you last *typed* the value, so the dump distinguishes a fresh
      meter reading from one carried over. A value restored from the last session
      reads `age_s=unknown`, never a confident zero.
    - **`# soak:` lines (v1.66)** record the rig's own run history:
      `streamed_s` (seconds the stream has actually run, banked across stop/start —
      *not* wall-clock elapsed), `stalled_s` (seconds lost to firmware-time gaps, so
      **effective soak = streamed_s − stalled_s**), and `idle_before_s`. Written at
      stream start and stop, every 60 s while streaming, and once per dump header.
      This is the variable to regress against when testing whether an effect tracks
      soak or supply — and unlike pack voltage it is measured, not typed.
      **`idle_before_s` is classviz-*observed* idle, not rig idle.** If the app was
      closed, the board unplugged, or the rig left powered with the stream merely
      stopped, it describes what the tool saw. It reads `unknown` after a crash
      (settings save on close). Treat it as a hint, not a measurement.
    - **`# stall:` lines (v1.64).** Written automatically when the firmware clock shows
      a gap ≥ 2 s, i.e. the MCU stopped emitting — which on 2026-07-29 also meant the
      rig cooled (the PWM free-runs on one band while the emit is blocked). The Rate
      readout latches `⛔ N stalls` for the run. If you see it, the stream is losing
      frames *and* the thermal state moved; frames either side of a stall are not one
      measurement.
    - **Settle reads `—` during a stall, by design (v1.64).** The metric averages σ
      over N *frames*, which is only a window of time while frames arrive; a stalled
      window reads drift as noise. The readout now shows the window's real duration
      (`0.597 [6.9 s]`) or `STALLED 93 s`. The value itself is unchanged when the
      stream is healthy, so the 0.4 mV gate and older captures stay comparable.
    - **Pause (v1.64)** on the Pulse Width Mean, Cell Profiles (8-grid) and Band
      Profiles (9-grid) groups stops those charts redrawing, freeing event-loop time
      for draining the serial port — worth doing on a long unattended run, since
      losing that race is what leads to the MCU blocking. Recording, gating and the
      dump are unaffected; pausing all three also skips the shared matrix behind
      them. Not persisted.

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

## 6. Corpus pipeline — pimd_features (v10) + pimd_target_check (v3)

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
