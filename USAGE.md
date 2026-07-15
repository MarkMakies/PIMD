# PIMD — Usage Guide (USAGE.md) v1

Intent, operation and pipeline flow for each application in the repo — one page per
app. This is the working orientation document; **specs, measured values, the serial
protocol and invariants live in `DESIGN.md`**, which is ground truth. Version numbers
here reflect the source headers at the time of writing.

<!-- Changelog
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
      ├─► src/pimd_delaycal.py (v1.24)      — calibrates sample delays,
      │        exports cal_*.json profiles ──► src/data/profiles/
      ├─► src/pimd_gui.py (v4.13)           — Mode 1 live telemetry / bench monitor
      └─► src/pimd_classviz.py (v1.32)      — Mode 2 heatmap; loads & runs saved
               profiles; captures signatures ──► src/data/corpora/ + src/data/sessions/
                     │
                     ▼
          src/pimd_features.py (v6) + src/pimd_targets.py (v1)
               — registry-validated training-corpus builder ──► ML corpus
```

Typical workflow: flash the firmware once (DESIGN §16) → run **delaycal** after a
full thermal soak to produce a calibrated profile → lock the profile JSON → run
**classviz**, Load & Run the locked profile, capture target signatures against the
`targets.csv` registry → build the corpus with **features**. **gui** is the
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

## 4. pimd_delaycal — delay calibration sweeper (v1.24)

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
- Import Profile loads an existing JSON for re-checking without a fresh sweep.

**Operational notes.** Post-enclosure, the top of decay sits at ≈4.87–4.89 V, so the
**signal-detect ceiling must be set to 5.0 V** (DESIGN §3 epoch note) or the coarse
hunt false-triggers. Calibrate only after a full warm-up soak — heavy-band delays
move tens of ns between cold and warm (see cal_63_air_v2 rationale, DESIGN §10).
Settings persist in `src/data/delaycal_settings.json`.

---

## 5. pimd_classviz — Mode 2 signature visualiser & capture (v1.32)

**Intent.** The Mode 2 workhorse: renders each sweep frame as a real-time heatmap of
signed per-cell deviation from an air baseline (blue = non-ferrous/opposing, red =
ferrous/reinforcing), and is the **only capture path for the ML corpus** — both
quick signature captures and guided training sessions, with structured
target metadata validated against the target registry.

**Operation.**
- Connects over USB-serial; **Load & Run** on the top bar sends any saved profile
  JSON as a RAM-only dynamic profile (`E` → `D` → `Q5` → `G`) — no reflashing.
  Profile authoring lives in delaycal; this app only loads locked profiles.
- **Heatmap tab:** Δ deviation / Z-normalised / RAW display modes; static, rolling-
  median or nominal-threshold baselines; **Std Dev (rolling N) mode** = live noise
  monitor per cell; 64-frame median glitch filter (display path only — recordings
  stay faithful to the wire).
- **Stats tab:** per-cell Latest / Mean / Std with green/yellow/red thresholds.
- **Analysis tab:** live comparison charts and signature capture — target chosen
  from the registry combo (`targets.csv` via `pimd_targets.py`), structured
  placement fields (distance_mm, axes, offsets, medium, repeat_idx, notes),
  settledness gate (collection opens only once mean rolling σ ≤ threshold, default
  1.0 mV) and glitch-frame exclusion. Captures append to
  `src/data/corpora/gui_signatures_*.csv` with full provenance (profile_sha8,
  fw_version, tool_version, supply).
- **Training Session tab:** guided, marked capture runs from a training-list JSON;
  rows validated against the registry; per-row placement via the Placement dialog.
- **Session-dump recorder:** self-describing per-session CSV to
  `src/data/sessions/` — embedded profile JSON, per-column map, `# mark:` /
  `# mark_target:` lines — the input format for `pimd_features.py`.

**Notes.** Always `E` before switching profiles (Load & Run does this itself).
W-frames with a stale profile index are silently dropped — blank heatmap after a
profile switch means `G` went out before the board confirmed the profile. Settings
persist in `src/data/classviz_settings.json` (written on close only).

---

## 6. Corpus pipeline — pimd_features (v6) + pimd_targets (v1)

**Intent.** Offline CLI stage that turns classviz output into the ML training
corpus, enforcing the two contracts that make the corpus trustworthy: every row
joins a **registry-validated target** with structured placement, and every corpus
build is **geometry-guarded** so frames from different profile geometries can never
mix (DESIGN §10 invariant).

**Operation — `pimd_targets.py` (registry).**
- Loads and validates `src/data/training_lists/targets.csv` — the human-authored
  registry of physical target objects (id, material, shape, dims, mass, …). Read
  only; the registry is human-owned data and is never written by tooling.
- Hard errors (duplicate/malformed `target_id`, bad enum, unparseable numeric) vs
  warnings (unsorted dims, implausible mass, …). CLI:
  `python pimd_targets.py [--registry PATH]` — prints the target table and every
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

**Notes.** Run inside the venv (DESIGN §16). The previous-epoch analysis tools
(`pimd_classify.py`, `pimd_corpus_check.py`, `pimd_v2_findings.py`) are kept
local-only and untracked pending the new corpus.
