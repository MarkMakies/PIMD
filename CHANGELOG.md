### mcu/pimd_mcu.py — v4.24 — FIX: boundary settling now time-floored, not period-scaled

Root cause of the "first heatmap column is always noisy, whatever voltages I
calibrate" report (and of classviz v1.30's independently-confirmed noisiest
cell, band=9µs/cell=0): `acquire_mode2`'s band-boundary settling was
`BOUNDARY_PRIME = 15` PWM *periods*, so its absolute duration scaled with
band frequency — 25 kHz and 20 kHz bands got only 600/750 µs, below the
~1 ms+ the band-to-band energy-step transient needs (v4.20 itself measured
470 µs insufficient, 1.41 ms adequate — on a 94 µs-period band, which is why
the constant looked fine when it was set). The first cell of each band was
therefore sampled on a partially-decayed transient; ±1-period jitter in the
effective settle count turned that into telegraph-level alternation, which
the 32-deep (~9.2 s) rolling average smeared into the observed seconds-scale
oscillation. Band 1's first cell was clean only by accident: the 72-field
W-record print() at i==0 runs between that cell's CC write and its read
(after the settling sleep — the v4.20 comment claiming the print overlaps
the sleep was wrong, and has been corrected), donating milliseconds of
free-running settling every sweep. Fix: new `SETTLE_FLOOR_US = 3000`;
per-band settle periods are `max(BOUNDARY_PRIME, ceil(SETTLE_FLOOR_US /
period_us))`, precomputed into the flattened cell list, so every boundary
(including the band8→band1 wrap, whose old 320 µs budget could be entirely
consumed by the up-to-320 µs band-8 MCLK wait inside read_raw_sample) gets
≥ 3 ms of real settling. Sweep cost ≈ +12 ms on cal_72_air_v2 (289 → ~301 ms
refresh). No wire-format, PWM-slice, or profile changes. (2026-07-13)

---

### src/pimd_knn_baseline.py — v1.1 — fix crash when output dir doesn't exist

`main()` now calls `os.makedirs(outdir, exist_ok=True)` before `fig.savefig()`.
Previously, running the script with a non-existent `<output_dir>` (e.g.
`python pimd_knn_baseline.py corpus.csv test`) ran the full LODO/LOTO
classification and printed all results, then crashed with
`FileNotFoundError` at the very last step trying to save the confusion
matrix PNG. (2026-07-04)

### src/pimd_features.py — v2 — add wide-format signatures output

Added `--out-wide <path>`: one row per (session, target, distance_cm)
plateau instead of one row per cell -- `session,target,distance_cm,
plateau_amp_mV,splithalf_floor,quality,c00..c71`, with `c00..c71` the
plateau's delta_mV vector. Long-format `--out` remains the canonical
output; wide rows are built in the same pass from the exact `delta_mV`/
`plateau_amp_mV`/`splithalf_floor`/`quality` values already computed for
the long rows in `process_session()` (now returns `(rows, wide_rows)`) --
never re-parsed or recomputed, so the two outputs can't drift apart for
the same plateau. Checked whether `c00..c71` needed reordering to satisfy
"pulse ascending / threshold descending within band": it doesn't --
`cal_72_air_v2.json`'s 8 bands are already stored pulse_us-ascending, and
each band's 9 cells are already stored threshold_v-descending, so the
existing channel index (`band_index*9+cell_index`, used everywhere else
in the file) already satisfies that ordering. New `wide_header_lines()`
(writes `# profile: <name>` plus a column-order comment line before the
CSV header), `open_wide_writer()` (same refuse-unless-`--append`
semantics as the long writer), and `build_wide_row()`. Verified: wide row
count = long row count / 72 across all 3 real sessions, and every c00..c71
value matches its corresponding long-row delta_mV exactly (scripted
cross-check, all 27 plateaus x 72 cells). (2026-07-03)

### src/pimd_features.py — v1 — session-CSV -> training-corpus feature extractor

New offline PC-side script (no GUI, no firmware touch): turns a raw ClassViz
session-dump CSV (pimd_classviz.py v1.16+ "Record Session" output) into rows
matching the existing hand-built PIMD_target_corpus_signatures.csv schema.
Validates each session's embedded profile_json against cal_72_air_v2
structurally (refusing, not crashing, on any mismatch, and continuing with
the rest of a multi-session batch -- DESIGN §11: never mix profile
geometries), drops glitch-filter-flagged frames, and segments the frame
stream into air/target plateaus: from '# mark:' ground-truth lines when
present (pimd_classviz.py v1.19+ hotkeys), else a rolling-window mean-abs-
diff change-point fallback with generic placeholder target labels (no
ground truth for *which* target a run is without marks, so it never guesses
from the free-text session_notes). Builds a piecewise-linear per-channel
baseline anchored on air segments to correct the thermal drift documented
in DESIGN §3/§17.5, and computes per-plateau delta_mV / plateau_amp_mV /
splithalf_floor / quality. Also emits one diagnostic PNG per session
(band-mean vs time, drift-corrected, with segment boundaries and the
session's free-text notes) for eyeballing a capture before trusting it.

Change-point defaults were hand-tuned against the 3 real sessions currently
in data/sessions/ (none of which have marks yet) -- the initially-spec'd
0.5 mV transition threshold found zero transitions in one 272 s session;
settled on 0.15 mV/1 s window/4 s min-segment after inspecting raw band-mean
traces. The no-marks air/target classifier assumes the standard capture
protocol (recording starts in air, before the first target) and anchors on
the chronologically first detected run; a session-wide median-of-segment-
medians was tried first and rejected as unreliable on real, sparsely-
segmented captures. Verified against all 3 real sessions plus a synthetic
marked session (marks path) and a deliberately profile-mismatched file
(refusal path). Noted for the record: plateau_amp_mV in the existing
PIMD_target_corpus_signatures.csv (e.g. 190.0 for steel pipe @5cm) is not
reproducible as mean(|delta_mV|) over the 72 cells (that computes to ~16.6
for the same row) -- this script implements the mean(|delta_mV|) definition
as specified, so --append-ing new rows into the legacy corpus will mix two
different plateau_amp_mV scales until that's reconciled. CLI takes one or
more session CSVs plus --out/--append. Plain numpy + matplotlib only, no
pandas, no csv module -- consistent with the rest of the repo. (2026-07-03)

### src/pimd_knn_baseline.py — v1.0 — first classifiers for the signature corpus

New offline analysis script (numpy/pandas/scikit-learn/matplotlib, no GUI):
two classification tasks over `PIMD_target_corpus_signatures.csv` — (a)
family classification (ferrous-rising / crossover / non-ferrous), (b)
per-target ID (16 classes). Models compared: 1-NN with cosine distance on
L2-normalized 72-cell shape vectors; multinomial logistic regression (L2,
C=1) on the same features; and a 2-feature physics baseline for family
(zero-crossing pulse width + band-8 sign). Validation is leave-one-distance-
out (LODO) for both tasks, plus leave-one-target-out (LOTO) for family — an
unseen-object test, never a random split (DESIGN/ML_FINDINGS convention:
random splits overstate accuracy on this corpus size). Outputs confusion
matrices and per-fold accuracy to `<output_dir>`. (2026-07-03)

### src/pimd_pca_explore.py — v1.0 — PCA exploration of the signature corpus

New offline analysis script (numpy/pandas/scikit-learn/matplotlib, no GUI):
loads `PIMD_target_corpus_signatures.csv`, applies the audited exclusion
policy (solder roll 260g dropped entirely — distance falloff only ~1.7x even
after drift correction; SS shackle 62g keeps 5cm only; brass 370g drops
15cm; SS disk 35g @15 and steel RHS 140g @15 kept but flagged low-confidence,
late-session drift-heaviest stretch), builds L2-normalized 72-cell shape
vectors, and runs PCA to produce: variance-explained scree plot + PC loading
heatmaps in the 8x9 matrix layout (so components read like signatures);
a PC1-PC2 scatter of all usable signatures coloured by family and sized by
distance; and a check of the engineered zero-crossing pulse-width feature
against PC1 score, to see whether blind statistics rediscover the bench-
derived material parameter. (2026-07-03)

### src/pimd_classviz.py — v1.19 — mark hotkey for session ground-truth timing

While recording a session (Record Session), the only way to know which
physical target was in front of the sensor at a given moment was to
reverse-engineer it after the fact from the signal shape. Added a persistent
"Mark label" text field (Stats tab) plus single-key hotkeys active during
capture: `1`/`2`/`3` append `<label> @5`/`@10`/`@15` (cm) to the open session
CSV as a `# mark: <iso-timestamp>, <text>` comment line; `0`/`Space` append
literal `air` (ignores the label). Hotkeys are suppressed while any QLineEdit/
QSpinBox/QDoubleSpinBox has focus (so normal typing is unaffected), are a
no-op with a status-bar message if no session is recording, and a distance
mark is skipped (with a message) if the label is empty. A small recent-marks
readout (last 5) was added below the label field so the user can confirm a
mark landed without opening the file. The write reuses the exact
write()+flush() pattern already used for per-frame rows, on the same open
file handle, so it can't stall the ~7.3 Hz frame-logging path. Purely
additive to the CSV format — `#`-prefixed lines are already skipped by every
existing parser; no change to colmap, profile_json, or per-frame columns.
(2026-07-03)

### src/pimd_classviz.py — v1.18 — pad saved profile JSON floats to 3 d.p.

Follow-up to v1.17: that fix made the Profile Builder's *display* and *editing*
consistently 3 d.p., but `_save_profile_file()`'s `json.dump()` still serialised
floats at Python's trimmed `repr()` precision (`6.8`, `9.0`, `3.22`) — confirmed
against a freshly re-exported `cal_72_air_v2.json`. `json.dump()` has no float-
formatting hook (its C encoder calls `float.__repr__` directly, so a float
subclass with a custom `__repr__` is silently ignored — verified empirically).
Added `_pad_json_floats()`, a regex pass over the `json.dumps()` text that pads
every decimal-point number to `.3f`; integer fields (`freq_hz`, `averages`) have
no decimal point so are untouched. `_save_profile_file()` now writes through it.
(2026-07-03)

### src/pimd_classviz.py — v1.17 — 3-decimal precision for voltage/timing fields

Profile export was silently losing precision: `_populate_profile_editor()` formatted
`delays_us`/`threshold_v` to `.2f` when loading a profile into the Profile Builder
table, so any profile that passed through the editor (loaded, or loaded-then-saved)
got re-saved at 2 d.p. instead of the source precision. Confirmed against
`cal_72_air_v1.json` (2 d.p., editor round-tripped) vs. a delaycal-direct export
(3 d.p., bypassed the editor). Fixed the editor's format strings to `.3f`, and made
3 d.p. the consistent default for every other voltage/timing readout in the app:
`_fmt()` mV columns, `_band_labels` pulse_us, `_cell_labels` threshold_v (heatmap
axis / Stats "Threshold" column / mouse tooltip), Stats "Std" column, the crossings
label, the heatmap tooltip's delay readout, `_build_d_command()`'s pulse_us field
(was a bare `str()`, now `.3f`), and the Δ/Z/raw scale labels. Left UI-control
fields (rolling-window seconds, std colour thresholds, manual µV range,
baseline-age labels) at existing precision since they aren't calibration data.
(2026-07-03)

### README.md — Fixed broken build diary link

Both "Build diary" links pointed to `https://makies.com.au/pimd/`, which 404s.
Corrected to `https://makies.com.au/pulse-induction-metal-detector/`, the
actual live URL. Checked all other `*.md` files in the repo for broken links —
none found. (2026-07-01)

### src/pimd111.ui — v4.08's slider/QLineEdit changes applied for real

The v4.08 changelog entry (below, "8 ns grid snapping") claimed `pimd111_ui.py
also updated`, but `pimd111.ui` was never actually edited — none of the three
sub-changes ((a) QLineEdit fields, (b) frequency slider re-range, (c)
pulse/delay slider re-range) landed in the Designer source. This went
unnoticed for 5 versions because most of the mismatch was silent or benign
until now:

- **(a)** `lFreq`/`lPulse`/`lSample` stayed `QLabel`. `.text()`/`.setText()`
  work on both classes, but `editingFinished` (QLineEdit-only) doesn't — app
  crashed on startup (`AttributeError: 'QLabel' object has no attribute
  'editingFinished'`) since it's wired in `_setup_ui_connections()`.
- **(b)** `slFreq` stayed ranged 40–400 (old 0.1 kHz-unit scheme, default
  250) instead of 0–17 (index into `CLEAN_FREQS_KHZ`, default 10). Any slider
  move raised `IndexError: list index out of range` in the
  `valueChanged` lambda (`CLEAN_FREQS_KHZ[value]`).
- **(c)** `slPulse`/`slSample` stayed ranged in old 0.1 µs units (50–400/50–300)
  instead of 8 ns counts (625–5000/625–3750). This one was silent but wrong:
  the Python side reads the slider integer directly as an 8 ns count, so an
  old-scheme value like `slPulse=100` would have been sent to the MCU as
  0.8 µs instead of the intended 10.0 µs — a real pulse-width hazard, not just
  a display bug.

Fixed by changing `lFreq`/`lPulse`/`lSample` to `QLineEdit` (dropping
`lFreq`'s QLabel-only `textFormat` property) and correcting the three
sliders' `minimum`/`maximum`/`value` to match `apply_soc_defaults()`
(`slFreq`: 0–17, default 10 → 10.0 kHz; `slPulse`: 625–5000, default 2500 →
20.0 µs; `slSample`: 625–3750, default 1250 → 10.0 µs). `pimd111_ui.py`
regenerated from the corrected `.ui` via `pyuic6` (previously PyQt6-generated;
found already regenerated with `pyside6-uic`/PySide6 imports mid-session by
an untraced process — possibly an IDE auto-compile-on-save watcher pointed at
the wrong tool — which would have been its own crash: `pimd_gui.py` imports
PyQt6, not PySide6. Worth checking your editor's Qt tooling config if this
recurs.) Verified via `QT_QPA_PLATFORM=offscreen python pimd_gui.py`: starts
clean, no traceback, process stays up. (2026-07-02)

---

### src/pimd_delaycal.py — v1.20 — 3-decimal voltage headers + zigzag Auto Nudge

**(a)** Voltage column headers (main results table, both thermal tables, CSV export)
now show 3 decimal places (`4.000 V`) instead of 1 (`4.0 V`), for finer-grained
target-voltage sets. Three call sites updated: `_rebuild_table()`,
`_rebuild_thermal_tables()`, `export_csv()`. `_ch_label()`'s voltage formatting
(used only in activity-log messages, not a column header) left at 1 decimal.

**(b)** Auto Nudge's per-channel search direction was effectively one-directional:
`_auto_nudge_channel()` walked cumulatively further in the same direction each
attempt (`cur += d * nudge_us`) until exceeding the cap from the calibrated delay,
then flipped direction exactly once and gave up if that was also capped. Replaced
with an expanding zigzag measured from the calibrated delay every attempt:
`+nudge, -nudge, +2×nudge, -2×nudge, +3×nudge, ...`, continuing until the offset
exceeds the cap (existing best-std fallback in `_auto_finish()` still applies) or
the outer loop's max iterations/attempts is reached (unchanged). Per-channel state
`_auto_dir_flat`/`_auto_dir_flipped` replaced by a single attempt counter
`_auto_attempt_flat`. (2026-07-02)

### cal profile — cal_20260702_165109 — new profile geometry: geometric pulse ladder + geometric thresholds

Replaced the old profile (cal_profile_8b, pulse widths 6/10/20/30/40/50/75/100 µs,
linear thresholds 4.8→0.5 V) with a geometric pulse ladder
6/9/13.44/20/30/45/67.2/100 µs (×1.5 per step) and geometric thresholds
4.5→0.5 V (×0.76 per step). Frequencies snapped to the CLEAN_FREQS list
(50/31.25/20/15.625/10/6.25/4/3.125 kHz), duty held at 26.9–31.25%.
Rationale: pulse width and threshold each sample log-space; constant-ratio
spacing removes near-duplicate cells (old profile bunched 30–50 µs bands and
the top three threshold cells). NOTE: geometry change — frames from this
profile are not comparable with data logged under cal_profile_8b; per
DESIGN §10 the profile is the firmware↔ML contract. (2026-07-02)

### bench finding — decay is non-exponential across the sample window

Delay-cal data (runs 16:39 and 16:51, 2026-07-02) shows local decay time
constant shrinking monotonically from ≈3 µs near 4.5 V to ≈1.2 µs near
0.5 V; both linear- and geometric-threshold cals agree on the shape.
Suspected clamp-release proximity stretching the apparent τ at the top of
the window. (2026-07-02)

### open question — possible coil-current plateau above ~67 µs

In both cals the 67.2→100 µs band-to-band first-delay increment is the
smallest on the ladder (0.44–0.51 µs vs 0.56+ mid-ladder), consistent with
TX coil current flattening. Not confirmed — needs a scope measurement of
coil current vs pulse width (τ_coil). Bears on whether the 100 µs band
justifies its frame-time and thermal cost. (2026-07-02)

### src/pimd_delaycal.py — v1.21 — Auto Nudge log lines now identify the channel

Auto Nudge's zigzag nudge log (added in v1.20) printed `nudge #k: ±N ns from cal →
... µs` with no channel identifier. In parallel mode, several channels nudge per
iteration and each has its own independent attempt counter, so lines like
`nudge #11: +240 ns from cal → 7.480 µs` and `nudge #11: +240 ns from cal →
6.760 µs` appeared back-to-back with no way to tell which channel was which.
Both log lines in `_auto_nudge_channel()` (the nudge line and the "cap reached"
line) now prefixed with `self._ch_label(ch)`, matching the convention already
used elsewhere in the file (`_auto_evaluate_initial`, `_auto_finish`, etc.).
(2026-07-02)

### src/pimd_delaycal.py — v1.22 — Auto Nudge locks a channel's delay once it passes

In parallel mode, `_auto_evaluate_parallel()` re-measured every active channel's
std-dev on every iteration, including channels that had already passed. If a
passed channel's live std later drifted above threshold — noise, thermal drift,
or cross-talk while other channels were still being nudged and re-soaked — it
was pushed back into `still_bad` and re-nudged, silently moving a delay that had
already been accepted as good. New per-channel `_auto_locked_flat` sticks the
first time a channel passes; locked channels are excluded from `still_bad` and
`_auto_nudge_channel()` for the rest of the run, so their delay is frozen for
good. Their cell colour still tracks live pass/fail for visibility: green
(`_COL_DONE`) while still reading within threshold, new lavender
`_COL_AUTO_DRIFTED` if the live reading drifts back above threshold post-lock.
Sequential mode is unaffected — `_auto_evaluate_channel()` already permanently
advances past a channel the moment it passes and never revisits it. (2026-07-02)

### src/pimd_delaycal.py — v1.23 — Max iterations range raised 20 → 100

`sp_auto_max_iter`'s range was 1–20; raised to 1–100. The zigzag nudge search
(v1.20) needs more attempts than a single-direction walk to sweep out to the
cap at small step sizes — Sequential mode's per-channel max-attempts use in
particular was capping out before reaching the cap. (2026-07-02)

### cal profile — cal_2-7-26-base.json — FROZEN as operating profile

Final calibration of the new geometry (geometric pulse ladder
6/9/13.44/20/30/45/67.2/100 µs, geometric thresholds 4.5→0.5 V ×0.76/step).
Renamed from cal_20260702_180813 to cal_2-7-26-base.json. Conditions:
coil in air 500 mm above floor, bench-top PSU, extended warm-up to
thermal stability (repeat-cal deltas collapsed to within 8–32 ns of the
8 ns grid across all bands, vs up to −248 ns when run after only
minutes). All 72 cells passed auto-cal, 13 delays adjusted (mostly a
coherent +40 ns shift of the 4.5 V clamp-release column). This profile
supersedes cal_profile_8b; frames are not comparable with earlier
geometry (firmware↔ML contract, DESIGN §10). (2026-07-02)

### bench finding — 31.25 kHz is a noisy rep rate; band 2 moved to 25 kHz

With the 9 µs pulse unchanged, band 2 at 31.25 kHz showed row-wide noise
(σ 2–5 mV, three cells never settled); moving only the frequency to
25 kHz cured it (σ 0.02–0.10 mV). Noise followed the operating point,
not pulse/decay alignment — consistent with DESIGN §8 rep-rate/beat
sensitivity. Band 2 duty is now 22.5%. (2026-07-02)

### watch list — 4.5 V column and band 8 (3.125 kHz/100 µs)

4.5 V column sits at clamp-release (flattest part of decay): highest σ
and the column that needed the +40 ns nudge; fallback is a 4.4 V top
anchor if it misbehaves in the field. Band 8 means run a few % above
the column family with the highest band σ — heaviest, slowest-settling
band, same band as the suspected coil-current plateau (see earlier
open-question entry). No action; to be judged by labelled target data.
(2026-07-02)

### pimd_classviz.py — v1.16 — session dump recorder

Reworked the existing v1.06 "Record Frames" toggle (RAM-buffered raw W-frame
capture, flushed once on stop to `data/frames_*.csv`) into a self-describing
"Record Session" recorder for an AI analyst to work from as a standalone
file — no external profile file or operator memory required. Extended in
place per the request rather than adding a parallel recording path: same
button, same tap point (raw values before the 64-frame glitch filter and
before any baseline/display scaling), same auto-stop-on-profile-change/
stream-stop guards.

Saves to `data/sessions/session_YYYYMMDD_HHMMSS.csv`. Rows are now written
and flushed incrementally as each W frame arrives instead of buffered in RAM
and flushed once at stop — a crash or serial dropout mid-session loses at
most the last unflushed row, and because the file's lifecycle is tied only
to the explicit Start/Stop toggle, a transient gap in the frame stream never
restarts the file (it just shows up as a `firmware_time_ms` gap). The file
opens with a `#`-prefixed comment header: session start time, tool version,
the raw firmware `V` response (a `V` command is now sent on connect,
alongside the existing `E`/`Q4`, and parsed in `process_packet`), the
complete active profile embedded as one-line JSON, an explicit per-column
band/freq/pulse/delay/threshold map, and free-text session notes entered via
a small dialog when recording starts. Data rows: `pc_wallclock_iso`,
`firmware_time_ms`, all cell means in µV as received, plus a new `flagged`
column (1 if the existing 64-frame glitch filter marked any channel that
frame — previously computed and discarded, now surfaced instead of the
frame being dropped). Button text and status bar show frame count + elapsed
time while recording. (2026-07-02)

<!-- Add new entries above this line. Format: ### <file> — v<N> — <short title> -->

### src/pimd_classviz.py — v1.15 — Stats: Std colour bands + row-height +/−

Stats tab controls row: two QDoubleSpinBox widgets (lower/upper, default 0.50/1.00 mV)
set colour thresholds for the Std (mV) column — green (< lower), yellow (between), red
(> upper) using the same RGB values as MY_GREEN/YELLOW/RED used throughout the app.
Two +/− QPushButtons adjust `tbl_stats` default row section height in 4 px steps
(clamped 12–48 px) so all rows stay visible at any density.  QBrush/QColor imported
from PyQt6.QtGui. (2026-06-21)

---

## Archive — consolidated 2026-06-21

### src/pimd_scope.py — removed — superseded by pimd_classviz.py

pimd_scope.py (v4.02, Mode 2 streaming visualiser) removed from the repository.
All functionality is covered by pimd_classviz.py. (2026-06-21)

---

### src/pimd_delaycal.py — v1.19 — Auto Nudge parallel / sequential toggle

Re-introduces parallel Auto Nudge mode (the v1.07 architecture) alongside the
existing sequential mode, selectable with a new "Sequential" checkbox in the
Auto row.  Default (unchecked) = parallel: all bad channels are nudged together
before each shared soak, completing in 1 + max_iterations soaks regardless of
how many channels are bad (vs 1 + N×max_attempts for sequential).  New
`_auto_evaluate_parallel()` evaluates all active channels, tracks best-std/delay
per channel, nudges all still-bad channels via the existing `_auto_nudge_channel()`
(which handles direction, cap, and flip), then re-soaks.  The "Max att/cell:"
label dynamically renames to "Max iterations:" in parallel mode.  Mode is logged
at run start and persisted in settings as `'auto_sequential'`. (2026-06-21)

---

### src/pimd_delaycal.py — v1.18 — draggable left/right splitter

Left column (config panel + activity log) was fixed at 420 px and did not grow
when the window was resized.  Replaced the `QHBoxLayout` content row with a
horizontal `QSplitter` (`h_splitter`); the left column is now a `QWidget` with
`setMinimumWidth(300)` and the right pane takes `stretchFactor=1`.  Removed both
`setFixedWidth(420)` calls from `cfg_box` and `log_box_grp`.  Splitter position
is saved as `'h_splitter'` in settings and restored on startup alongside the
existing vertical splitter. (2026-06-21)

---

### src/pimd_delaycal.py — v1.17 — thermal monitoring tables rows in ascending pulse_us order

"Latest mean" and "Std dev" thermal monitoring tables now display rows sorted
ascending by pulse_us (shortest delay first); the calibration table row order is
unchanged (run order).  `_rebuild_thermal_tables()` computes `_thermal_display_order`
(display_row → protocol_band) and `_thermal_proto_to_display` (inverse) and uses
the sorted order for row labels.  `_update_thermal_tables()` iterates by display
row `d` (mapping back to protocol band `b` for channel data), so value and colour
updates remain correct.  `_auto_color_cell()` applies colour to the calibration
table at row `b` and to the thermal tables at row `d = _thermal_proto_to_display[b]`,
preserving Auto Nudge cell highlighting. (2026-06-21)

---

### src/pimd_classviz.py — v1.14 — stats table and profile editor rows in ascending delay order

Stats table and Profile Builder table rows are now sorted by first delay value
ascending (lowest delay / highest frequency first).  Added `_band_stats_order`
and `_stats_band_labels` to `_set_profile_dims()` (ascending, the reverse of
`_band_display_order`); `_rebuild_stats_table()` and `_update_stats_table()` now
use these, preserving the correct row↔protocol-channel mapping so per-cell values
continue to track the right channel.  `_populate_profile_editor()` sorts bands by
`delays_us[0]` ascending before filling the table.  Heatmap display order is
unchanged (still descending, highest delay at top). (2026-06-21)

---

### src/pimd_classviz.py — v1.13 — remove single-cell isolation tab section

Removed the Single-cell isolation group box from the Stats tab (now renamed 'Stats'
from 'Stats && Isolation') and all supporting code: `_rebuild_single_cell_combos()`,
`_on_sc_band_changed()`, `_update_sc_info()`, `_run_single_cell()`, `_resume_sweep()`,
`_update_sc_button_states()`, and the Mode-1 `*` packet branch in `process_packet()`.
`self._mode` and `self._sc_buf` state removed from `__init__()`.  `start_stop()`
and `_on_send_run_profile()` simplified — no longer need to exit single-cell mode
before starting/stopping.  `sc_ds` removed from settings persistence. (2026-06-21)

---

### src/pimd_classviz.py — v1.12 — heatmap row sort by delay descending + updated band label format

Added `_band_display_order` (sorted by `delays_us[0]` descending) so that heatmap
rows are always shown in decreasing delay order regardless of the profile's stream
order — required for new profiles that interleave high/low pulse-width bands to
flatten thermal characteristics.  `_display_band_labels` is the display-ordered
copy used by the heatmap axes, stats table, and mouse tooltip; `_band_labels` and
`_bands_meta` remain in protocol order so single-cell commands and CSV logging are
unaffected.  `_redraw()` applies the permutation to raw data, mean, and std before
passing to `_compute_display_matrix()`; `_update_crossings()` maps display band
index back to protocol index when accessing `_nominal_baseline_uv`.  Band label
format changed from `'40.000µs/10.601kHz'` to `'10,601Hz / 40.0µs'` (freq in Hz
with thousands separator, pulse in µs to 1 d.p.), matching pimd_delaycal.py.
(2026-06-21)

---

### src/pimd_delaycal.py — v1.16 — row-label format: Hz with thousands separator, pulse to 1 d.p.

_row_label() rewritten: converts freq_khz × 1000 to an integer Hz value, formats
it with Python's {:,} thousands separator, and formats pulse_us to exactly 1
decimal place.  Produces labels like '31,250Hz / 6.2us' instead of the previous
'31.25kHz/6us'.  All three tables (calibration, thermal mean, thermal std-dev)
and the activity-log / progress-label references update automatically as they all
call _row_label(). (2026-06-21)

---

### src/pimd_delaycal.py — v1.15 — coarse+fine two-phase sweep per freq/pulse pair

For each freq/pulse pair, a fast coarse hunt (new sp_coarse_step spinbox, default
1 µs) now steps up from the start delay until the ADC reading drops below a
configurable signal-detect voltage (new sp_signal_v spinbox, default 4.9 V),
indicating real signal is present.  The sweep then backs up to the last clean
coarse position and switches to the existing fine step for accurate threshold
interpolation.  This avoids tens of wasted serial round-trips for long-pulse pairs
(e.g. 1.6 kHz / 100 µs) where the first real signal may only appear at 10 µs or
beyond.  If signal appears at the very first coarse step, the backup target falls
back to start_delay.  When coarse_step <= fine step, the coarse phase is skipped
entirely (pure fine scan, backward compatible).  Log lines show 'COARSE' prefix
during hunt; progress label shows "Coarse scan" instead of threshold count.
_advance_pair() now resets _coarse_phase for each new pair.  'Step size:' label
renamed 'Fine step:' for clarity.  Settings keys 'coarse_step' and 'signal_v'
added to _load_settings() / _save_settings(). (2026-06-21)

---

### src/pimd_gui.py — v4.13 — settings persistence (port, freq, pulse, delay, toggles, scale, geometry)

Added _load_settings() / _save_settings() following the identical pattern used
by pimd_delaycal.py.  Saves to data/gui_settings.json on close; restores on
startup at end of my_init() (after apply_soc_defaults()) so saved values
override SOC defaults.  Fields persisted: port, freq_hz (exact lFreq text),
pulse_us, delay_us, down_sample factor, avg_n, Boxcar and Raw-Avg toggle states,
VoltageButtonGroup and TimeButtonGroup checked IDs, and window width/height/x/y.
Added json and os imports; added SETTINGS_PATH constant. (2026-06-21)

---

### src/pimd_classviz.py — v1.11 — settings persistence (port, heatmap controls, geometry)

Added _load_settings() / _save_settings() following the identical pattern used
by pimd_delaycal.py.  Saves to data/classviz_settings.json on close; restores
at end of __init__() after _build_ui().  Fields persisted: port, capture N,
rolling T, display mode index, baseline mode index, stats std-dev window,
single-cell downsample, manual range µV, autoscale flag, and window
width/height/x/y.  Removed the hardcoded window.resize(1100, 900) from
__main__ — first-run default is now handled by the except branch of
_load_settings(). (2026-06-21)

---

### src/pimd_delaycal.py — v1.14 — dynamic thermal-table minimum height; all rows always visible

_rebuild_thermal_tables now computes each table's minimumHeight as
28 px (header) + n_rows × 30 px + 4 px (border), floored at 120 px.  With 6
freq/pulse bands the minimum becomes 212 px, ensuring all rows are visible
without a scrollbar regardless of band count.  Previously the static 120 px
floor was not enough to show > 4-5 rows and the bottom row(s) were cut off.
(2026-06-21)

---

### src/pimd_delaycal.py — v1.13 — 'Latest delay (us):' label; top-pane-first splitter shrink

Added a bold 'Latest delay (us):' label directly above the calibration table to
match the 'Latest mean (mV):' and 'Std dev (mV):' labels already present on the
lower two tables.  Changed splitter stretch factors from (2, 1) to (1, 0) so the
top (calibration) pane absorbs all window-resize slack first — when the window is
made smaller the empty space inside the calibration table compresses before the
monitoring section is touched, so the lower thermal tables never need scrollbars
at typical band counts.  Thermal table minimum height raised from 80 to 120 px to
enforce enough room for header + 3–5 rows without a scrollbar. (2026-06-21)

---

### src/pimd_gui.py — v4.12 — Avg n field; no auto-connect; remove sub-200uV V/div; fix A<n> serial backlog

Root-cause fix for the A<n> serial write-buffer backlog that caused streaming to continue
20–30 s after quitting and parameter changes to be delayed up to 2 minutes at slow rates
(e.g. 6250 Hz / DS 256). At that rate the firmware takes ~245 ms per A256 — barely inside
the 250 ms poll timer — so any latency let queued A<n> commands pile up. closeEvent and the
start_stop stop path now call serial.clear(Direction.Output) before sending E, and
waitForBytesWritten is extended from 200 ms to 500 ms.

Root cause also addressed: A<n> sample count is now a user-editable "Avg n" field
(default 64) between the Boxcar and Raw Avg toggles. Field turns orange whenever the current
n > freq/30, meaning A<n> would exceed 80 % of the 250 ms poll timer (re-evaluated on every
frequency change as well as on direct n edits).

App no longer auto-connects at startup — user presses ENT / Connect explicitly, consistent
with pimd_classviz and pimd_delaycal. The 10 uV, 20 uV, 50 uV and 100 uV V/div options are
removed from the left sidebar (minimum is now 200 uV/div); v_div arrow-key clamp updated
from −15 to −11 accordingly. (2026-06-20)

---

### src/pimd_delaycal.py — v1.12 — QSplitter; uniform table colours; window/splitter geometry persistence

Four UI fixes. (1) Calibration table and "Live Monitoring & Auto Nudge" section now share a QVSplitter (2:1 default ratio), so the bottom section maintains its size when the window shrinks — the user drags the handle to adjust the split; splitter state is persisted in settings. (2) _auto_color_cell extended to update all three tables (cal + mean + std) identically; _update_thermal_tables likewise mirrors calibration table cell background to both thermal tables during Auto, replacing the previous independent value-based std-dev colouring; _auto_finish uses _auto_color_cell so the final colours are also applied consistently to all three tables. (3) Window width, height, x, y saved on close and restored on startup via settings JSON; QTimer.singleShot(0,...) defers splitter size restoration until after first layout pass. (4) Section labels "Latest mean (mV):" and "Std dev (mV):" set to bold weight for visual parity. Minimum table height increased 60→80 px. Noted in v1.12 header: "nudging every cell" is expected behaviour — calibrated delays sit at threshold crossings with nonzero signal slope, converting amplitude noise to σ > 0.5 mV; Auto Nudge relocates to quieter nearby delays, which is its design purpose. (2026-06-20)

---

### src/pimd_delaycal.py — v1.11 — post-nudge settling gate eliminates false yellow flicker

After each nudge the rolling std-dev buffer mixes transition frames (delay still changing) with settled frames, causing most cells to briefly go yellow before settling — a false noise signal. Fix: _auto_run_soak now sets _auto_settling=True and arms QTimer.singleShot(1000, _auto_settle_done) immediately after sending G. While the flag is set, _on_thermal_w_record discards all incoming W records and skips display updates. _auto_settle_done clears the flag and calls _thermal_buf.clear() to ensure std-dev accumulation begins from clean post-settle frames only. _stop_auto also resets _auto_settling. The 1 s gate is fixed; minimum soak is 5 s so effective measurement window is always ≥ 4 s. (2026-06-20)

---

### src/pimd_delaycal.py — v1.10 — wider log; thermal box resizable; live table colours; settings persistence

Four enhancements. (1) Left column widened 320→420 px and window grown 1200×1000→1440×1200 so activity log entries (which include long ch-label strings and µs/ns values) fit on one line without wrapping. (2) GroupBox renamed "Live Monitoring & Auto Nudge"; setMaximumHeight(140) removed from both thermal tables and replaced with setMinimumHeight(60) and stretch=1 inside the layout — the box now occupies half the right-column height and resizes with the window. (3) During Auto Nudge (tracked by new _auto_running flag set True in _start_auto, False in _auto_finish/_stop_auto), _update_thermal_tables mirrors the calibration table's status colour onto the mean table (queued/amber/green/red) and colours each std-dev cell green if ≤ threshold, yellow if ≤ 2× threshold, red otherwise. (4) All parameter fields (port, delays, freq/pulse, targets, thermal secs, std-dev N, auto soak/iter/threshold/nudge/cap) saved to data/delaycal_settings.json via _save_settings() in closeEvent and restored via _load_settings() called at the end of __init__ after _build_ui(). (2026-06-20)

---

### src/pimd_delaycal.py — v1.09 — real-time Auto cell colours; Import Profile; adjusted-delays summary

Three enhancements to pimd_delaycal. (1) Real-time cell colouring during Auto Nudge: after the initial soak, cells in the calibration table are immediately coloured yellow (queued for nudging) or green (already within threshold); the cell being actively soaked turns amber; it turns green on pass or red on flag — giving a live progress view without waiting for the final summary pass. (2) "Import Profile" button in the top bar loads any JSON profile (same format as Export Profile) directly into the calibration table, setting _fp_pairs / _targets_v / _thresholds and enabling Thermal / Auto / Export without requiring a full calibration sweep first. (3) At the end of Auto Nudge, _auto_finish now appends a compact "Adjusted delays" block to the activity log listing only the channels whose delay actually changed (cal → best µs, Δ ns, PASS/FLAGGED), and updates progress_label with the one-line summary plus the count of adjusted cells. (2026-06-20)

---

### src/pimd_delaycal.py — v1.08 — activity log panel; sequential Auto Nudge

Scrolling activity log panel (QPlainTextEdit, read-only) added to the left column
below the Configuration group box, reporting calibration steps (each delay tested,
each threshold crossing), thermal start/stop, and auto-nudge decisions per channel.
Auto Nudge logic changed from parallel to sequential per-channel processing: an
initial soak identifies bad channels, then each bad channel is tackled one at a
time — up to "Max attempts/cell" nudges — before advancing to the next. The
_auto_iter global iteration counter is replaced by _auto_phase / _auto_targets /
_auto_target_idx / _auto_ch_attempts. "Max iter" spinbox label changed to "Max
attempts/cell". Window height bumped 950→1000 px. (2026-06-20)

---

### src/pimd_delaycal.py — v1.07 — Auto Nudge: iterative per-cell delay correction

New "Auto" button in the Thermal Monitoring panel.  After calibration, Auto runs
soak→evaluate iterations using the existing Mode 2 / D+Q5+G / W-record path:
streams the calibrated profile, measures per-cell std dev over the last N W-frames
(reuses the existing Std dev N spinbox), then nudges cells whose std dev exceeds
the threshold (default 0.5 mV) by a configurable step (default 80 ns) toward
earlier delays.  On cap hit (default ±960 ns from calibrated delay), resets to
the calibrated delay and explores the opposite direction; flags the cell if both
directions are capped.  Best-std delay kept per cell across all soaks.  At finish,
calibration table updated (green = passed, red = still bad after max_iter); ΔV per
nudged cell logged in status; Export Profile runs automatically.  N/R cells
excluded.  All I/O via QTimer.singleShot + W-record callbacks — no blocking loops.
Window height bumped 850→950 px. (2026-06-20)

---

### OBS — P2006-113356.csv — 80 ns delay sweep, 20 kHz / 20 µs pulse, v4.23 firmware

First data set recorded with MCU v4.23 (freq Hz / pulse+delay ns protocol). Warm-up 30 s,
then 13 delay steps from 7088 ns to 8048 ns in 80 ns increments, ~5 s per step.
All 13 delays land exactly on the 8 ns PWM grid (total_ns = delay_ns + 904 divisible by 8).

| delay (ns) | delay (µs) | V mean (mV) | V σ (µV) | fw_sd (µV) | status |
|---:|---:|---:|---:|---:|:---|
|  7088 | 7.088 | 4877.3 | 1835 |  242 | settled — slow filter tail |
|  7168 | 7.168 | 4809.2 |   71 |   65 | **clean** |
|  7248 | 7.248 | 4736.3 |  378 |  125 | settled — moderate |
|  7328 | 7.328 |    —   |   —  | 500–1400 | **never settled** |
|  7408 | 7.408 |    —   |   —  | 500–1400 | **never settled** |
|  7488 | 7.488 | 4477.5 |  227 |  158 | settled — ok |
|  7568 | 7.568 | 4379.3 |  177 |  161 | settled — ok |
|  7648 | 7.648 | 4273.8 |  179 |  111 | settled — ok |
|  7728 | 7.728 | 4161.5 |  176 |  139 | settled — ok |
|  7808 | 7.808 |    —   |   —  | 500–1400 | **never settled** |
|  7888 | 7.888 |    —   |   —  | 500–1400 | **never settled** |
|  7968 | 7.968 | 3795.4 |  180 |  105 | settled — ok |
|  8048 | 8.048 | 3666.1 |  319 |  143 | settled — moderate |

Key findings: (1) Grid fix confirmed — no two-stage settling artefact seen in previous
dataset (P2006-103607.csv, v4.21 off-grid). (2) Four delays never settle: 7328+7408 and
7808+7888, forming two 160 ns wide noisy zones exactly 480 ns apart. This points to a
~2.08 MHz LC ringing in the coil/preamp after TX cutoff: the ring-down still has enough
amplitude at 7–8 µs to cause persistent fw_sd > 400 µV when the sample point lands near
a ringing peak. (3) 7088 ns shows high V σ (1835 µV) but low fw_sd (242 µV) — slow
voltage drift of ~5.6 mV over 24 s, consistent with the 256-sample rolling window still
flushing the previous step (3.28 s flush time); not physical noise. (4) Best operating
window at this freq/pulse: 7488–7728 ns (320 ns clean band). (2026-06-20)

---

### src/pimd_delaycal.py — v1.06 · src/pimd_classviz.py — v1.10 · src/pimd_scope.py — v4.02 — protocol update and title standardisation

* command in delaycal and classviz (single-cell Mode 1) updated to match MCU v4.23:
freq now sent as integer Hz (was kHz to 1 d.p.), pulse and delay now sent as integer ns
(was µs to 1 d.p.). All four PC apps now share the same title format:
'PIMD <AppName> v<N> by Mark Makies'. Scope has no protocol changes — title only. (2026-06-20)

---

### mcu/pimd_mcu.py — v4.23 · src/pimd_gui.py — v4.11 — serial protocol: freq in Hz, pulse/delay in ns

Protocol change to eliminate decimal-place rounding ambiguity in the serial wire format.
All timing fields previously reported in kHz (1 d.p.) or µs (1 d.p.) now use exact integers:
freq in Hz, pulse and delay in ns. No decimal points, no conversion arithmetic on the PC side.
At the 8 ns PWM grid, all values are exact multiples of 8, so integer ns is both lossless and
unambiguous. Affects * record output, R record output, V response, L response, and the inbound
* config command. GUI title standardised to 'PIMD GUI v4.11 by Mark Makies'. (2026-06-20)

---

### src/pimd_gui.py — v4.10 — fix display lag and file-write spam after stop

Two serial-handling bugs fixed:

**(a) Growing display lag** — `read_from_serial` now collects all available
lines before dispatching rather than calling `process_packet` inside the drain
loop.  Only the last `*` packet per `readyRead` call gets the full chart/UI
update (`skip_display=False`); earlier packets in the burst still write to file
then return early (`skip_display=True`).  At 39 SPS the event loop previously
had to complete a full chart redraw per packet; if any redraw took >25 ms the
backlog grew, producing 10–30 s display lag after extended running.  Now display
cost is O(1) per `readyRead` regardless of burst size.

**(b) "File write error, probably last packet after stop" spam** — `start_stop`
stop branch, `closeEvent`, and `setup_file_logging` all now set `self.file =
None` immediately after `self.file.close()`.  A closed file object is truthy so
`if self.file:` previously passed and triggered `ValueError: I/O operation on
closed file` for every lingering buffered packet after stop. (2026-06-20)

---

### src/pimd_classviz.py — v1.09 — 3 d.p. for pulse width, frequency and delay in stats table

_band_labels format changed from `{:.0f}µs/{:.1f}kHz` to `{:.3f}µs/{:.3f}kHz` so pulse
width and frequency are displayed to 3 decimal places throughout (heatmap axis labels,
stats table Band column, single-cell combo, status bar).  Stats table Delay (µs) column
changed from 2 d.p. to 3 d.p.  All three now consistent with the 8 ns PWM grid
(0.008 µs precision). (2026-06-20)

---

### src/pimd_delaycal.py — v1.05 — snap calibrated delays to 8 ns PWM clock grid

Interpolated threshold-crossing delays are now snapped to the nearest 8 ns boundary
(the RP2040 PWM clock period) before being stored in the results table and exported
to profiles.  Formula: round the delay to the nearest 8 ns integer count.  Off-grid
values cause ±1 LSB alternating PWM jitter, documented in pimd_gui.py v4.08 and
pimd_mcu.py v4.22 — the same fix applied there for the GUI sliders is now applied
to the calibration output.  Table cells now display to 3 decimal places (0.008 µs
resolution) instead of 2.  The belt-and-suspenders snap in _build_profile() also
covers the N/R fallback (max_delay). (2026-06-19)

---

### src/pimd_classviz.py — v1.08 · src/pimd_delaycal.py — v1.04 — std dev window: samples not seconds; 2 d.p.

Stats-tab std dev window in classviz changed from time-based (QDoubleSpinBox 0.5–60 s,
filtering `_rolling_buf` by timestamp cutoff) to sample-count-based (QSpinBox 2–2000,
default 50, slicing the last N entries) to match the equivalent control in pimd_delaycal.py
— both now show "Std dev N:" so values are directly comparable. Std dev column in classviz
and the thermal std table in delaycal both now display to 2 decimal places (was 1 d.p.
in classviz, integer in delaycal). (2026-06-19)

---

### src/pimd_delaycal.py — v1.03 — profile export + thermal monitoring mode

Three additions to close the calibration-to-measurement loop:

**(a) Export Profile button** — builds a classviz-compatible JSON profile from the
calibrated delay table: one band per freq/pulse pair, `delays_us` from the crossing
cells (N/R cells fall back to max_delay), `threshold_v` from the target voltages list.
Autosaves to `data/profiles/cal_YYYYMMDD_HHMMSS.json` with no file dialog.
Format is identical to `pimd_classviz.py`'s `_default_profile()` so the file loads
directly in the classviz Profile Builder tab.

**(b) THERMAL button** — streams Mode 2 using the calibrated profile (sends `D` +
`Q5` + `G`, same as classviz's dynamic-profile mechanism), counts down from a
configurable duration (default 240 s), then stops automatically. Lets the user warm
up the electronics on the exact profile that will be used for the final measurement run.
Stop button aborts early.

**(c) Two live monitoring tables** — displayed below the calibration results while
THERMAL is running: Latest mean (mV, no decimal) and Std dev over the last N samples
(N settable, default 50). W-record parsing added to `read_from_serial`; updates
rate-limited to 10 Hz to avoid UI lag.

Also: config panel widened 280→320 px; window resized 1050×620→1200×850.
(2026-06-19)

---

### src/pimd_gui.py — v4.08 — 8 ns grid snapping; boxcar defaults ON; responsiveness fixes

Six changes in one version bump:

**(a) QLineEdit precision display** (pimd111_ui.py also updated): `lFreq`, `lPulse`,
`lSample` replaced as editable QLineEdit fields. Frequency shown as integer Hz;
pulse/delay shown in µs to 3 dp. Orange highlight when not on the 8 ns PWM clock
grid (or, for frequency, not a clean 125 MHz divisor). `change_parameters()` reads
from QLineEdit text; sliders remain for coarse adjustment.

**(b) Frequency slider re-ranged to 18 clean 125 MHz divisors, 1–50 kHz** (index
0–17 in `CLEAN_FREQS_KHZ`): 1.0, 1.25, 1.6, 2.0, 2.5, 3.125, 4.0, 5.0, 6.25,
8.0, 10.0, 12.5, 15.625, 20.0, 25.0, 31.25, 40.0, 50.0 kHz. The +/- buttons
and keyboard shortcuts (E/W, R/Q) step through this list by index; every position
is an exact clean frequency. `apply_soc_defaults()` sets index 10 (10.0 kHz).

**(c) Pulse/delay sliders re-ranged in 8 ns counts** (1 unit = 8 ns = 0.008 µs):
`slPulse` 625–5000 (5–40 µs), `slSample` 625–3750 (5–30 µs). Every slider
position is inherently on-grid; +/- buttons step by one 8 ns count. SOC defaults:
slPulse 2500 (20 µs), slSample 1250 (10 µs). `_on_pulse_edited` / `_on_delay_edited`
sync with `round(us * 125)`. Motivation: `pimd_mcu.py v4.22` shows that off-grid
values (old 0.1 µs steps = 12.5 × 8 ns) caused ±1 LSB alternating anomalies.

**(d) Boxcar and Raw Avg default ON** — both toggle buttons `setChecked(True)` at
startup; the poll timer only starts once Running, so no side-effect at init.

**(e) `read_from_serial` drains buffer in a `while canReadLine` loop** — the
previous single-line read caused a serial-buffer backlog and readyRead event storm
at ~39 SPS that progressively froze the UI and made Ctrl+C / window-close
unresponsive. Fixed to match the pattern already used in `pimd_scope.py`.

**(f) `closeEvent` added; fragile `aboutToQuit` lambda removed** — on window
close or F12 quit, stops the poll timer, sends `E`, flushes serial with
`waitForBytesWritten(200)`, closes port and log file. Also fixes a file-handle
leak in `setup_file_logging()` (previous handle now closed before opening new one)

---

### src/pimd_gui.py — v4.09 — fix quit_app: self.close() instead of QApplication.exit()

`quit_app()` (F12 shortcut) called `QApplication.instance().exit()`, which exits
the event loop without sending a `QCloseEvent` to the window. `closeEvent()` —
added in v4.08 to replace the removed `aboutToQuit` lambda — was therefore never
triggered by F12. Result: F12 exited without stopping `raw_poll_timer`, sending `E`
to firmware, flushing serial, or closing the log file.

Changed to `self.close()`, which sends a `QCloseEvent` → `closeEvent()` runs
cleanup → `super().closeEvent(event)` accepts → window destroyed → app exits via
`quitOnLastWindowClosed=True`. The OS × button path was already correct and is
unchanged.

---

### mcu/pimd_mcu.py — v4.22 — SAMPLE_PULSE_CORRECTION 0.908 → 0.904 µs

Updated `SAMPLE_PULSE_CORRECTION` from 0.908 µs to 0.904 µs. At the 10 µs
GUI delay setting, total delay is now 10.904 µs = 1363 × 8 ns exactly —
landing on a clean PWM clock-count boundary. The previous value placed the
delay exactly halfway between two adjacent 8 ns counts (1363.5 × 8 ns),
causing `delay_CC` to alternate ±1 LSB on every 0.1 µs GUI step and producing
an every-other-step ~13 mV / ~0 mV alternating anomaly in pulse-width sweep
recordings.


### mcu/pimd_mcu.py — v4.21 — IRQ critical section in read_raw_sample; plausibility gate

Wrapped the BUSY poll + SPI read in `machine.disable_irq()` /
`machine.enable_irq()` to prevent USB CDC IRQs firing between the BUSY-low
edge and the SPI clock start. Eliminates two Mode 2 anomaly types confirmed
in a quiet 45-channel recording (8 events, all exactly 32 frames = M=32
rolling-buffer depth):

- **Type 1 — SDOB bit-truncation** (value ≈ 50 % of true): USB IRQ delays
  SPI start past the next MCLK; partial conversion shifts into the read,
  producing half/quarter values. IRQ blackout ≤ 36 µs; safe for USB SOF.
- **Type 2 — Cell-value bleed** (value > normal): USB IRQ starves the
  BUSY-high poll long enough to miss the current cell's MCLK; lands on the
  previous cell's SDOB output.

Also adds a per-cell 10 % plausibility gate: if `raw14` deviates > 10 % from
the rolling mean (after ≥ 8 samples), the mean is substituted. All 8 observed
events caught. `FW_VERSION` constant synced to file header (was stuck at 4.15).

---

### mcu/pimd_mcu.py — v4.20 — FIX acquire_mode2: boundary settling and first/last cell timing

Two bugs fixed:

1. `BOUNDARY_PRIME` 5 → 15 (470 µs → 1410 µs): shorter period was
   insufficient for the 5 µs → 40 µs wrap-around thermal transient (8×
   pulse-energy step), producing a 3.1 → 1.6 → 0.6 mV gradient in band-0
   cells 0–2.

2. `emit/poll` moved from after the for-loop to inside it at `i == 0`:
   previously `print()` ran between cell[n-1]'s write and its read; USB CDC
   IRQs (10–50 µs) exceed the 2.5 µs BUSY-LOW window at 57 kHz, causing §7
   bit-truncated outliers in cell[n-1]. Cell[n-1] now reads cleanly; USB noise
   overlaps the already-running cell[0] settling sleep.

---

### src/pimd_classviz.py — v1.07 — 64-frame circular median glitch filter on display path

`process_packet`: added a 64-frame circular buffer per channel. When a
channel's latest value deviates > 100 mV from its 64-frame median, the median
is substituted for `_latest_raw` (→ heatmap, stats tab). `_rolling_buf` and
`_record_buf` retain unfiltered raw values. The 64-frame window ensures ≥ 33
clean frames remain throughout any 32-frame glitch event, keeping the median
stable. Targets the 32-frame flat-step ADC artifacts (fw v4.21 is the primary
fix; this is the independent PC-side complementary layer).

---

### src/pimd_classviz.py — v1.06 — Record Frames toggle button

Stats tab: added "Record Frames" toggle button. When active, raw W-record
frames (`fw_time_ms`, `wall_time_s`, `ch0`…`chN-1` in µV) are appended to
`data/frames_YYYYMMDD_HHMMSS.csv`. Recording auto-stops when streaming stops
or the active profile changes.

---

### src/pimd_classviz.py — v1.05 — fix _fmt(): CSV thousands-separator bug

Removed the thousands-separator from `_fmt()`'s format string. Saved CSV
files previously contained values like `4,373.6` instead of `4373.6`,
breaking machine parsing.

---

## Archive — consolidated 2026-06-18

---

### src/pimd_gui.py — v4.04 — min/max range from R record

`acquire_raw_average()` now returns `(mean_uV, std_uV, min_uV, max_uV)` (see
mcu v4.15 below). The GUI parses the two new fields from the R record
defensively (falls back to `None` if the firmware is older). When available,
the footer raw-path status string now shows `min…max uV` alongside mean and
std dev, making it immediately visible whether a single outlier sample (e.g.
a bimodal distribution within one boxcar window) explains the large reported
std dev and oscillating mean. No chart changes.

---

### mcu/pimd_mcu.py — v4.19 — revert v4.18; re-apply BUSY edge sync; fix missing data_bytes

Reverted v4.18's `sleep_us` pacing + post-read-retry approach — it reintroduced
the outlier corruption that v4.17 had solved. Re-applied v4.17's full BUSY edge
sync (`while not busy_pin.value(): pass` → `while busy_pin.value(): pass` → read).
Also fixed a `NameError` introduced during the revert edit: the `data_bytes =
adc_raw_spi.read(4)` line had been accidentally dropped from `read_raw_sample()`.

Accepted known side-effect (carried from v4.17): BUSY-high pulse at 10 kHz is
≈ 15 µs — MicroPython polling catches ≈ 1-in-6, giving ≈ 1.6 kHz effective raw
sample rate (vs 10 kHz configured). Accepted tradeoff for accuracy over rate.

---

### src/pimd_gui.py — v4.07 — remove range from footer; fix horizontal grid line color

- Footer raw status: removed `range: <min> to <max> uV` field (and associated
  `raw_min_uV`/`raw_max_uV` instance vars and R-record parsing). Footer now
  shows only `Raw avg: ... uV, sd: ... uV (N=...)`.
- Chart: `axis_z` (right/horizontal-grid axis) `setGridLineColor` changed from
  `QColor("blue")` back to `QColor("#cccccc")` (light gray), matching the
  vertical grid lines from `axis_x`.

---

### src/pimd_gui.py — v4.06 — range-based chart trim, boxcar mode button, remove Raw σ

Three changes bundled:

1. **Chart polyline corruption fix** — `series_v` and `series_raw_mean` are now
   trimmed by x-axis range (`axis_x.min()`) instead of a point-count threshold.
   The old `removePoints(0, 100)` when count > 5000 left warmup-spike points just
   outside the visible window; QLineSeries drew a connecting segment from the last
   removed point's neighbour to the newest point, producing a large vertical
   artifact early in each run. The range-based trim removes all points whose
   x-coordinate is less than the current left edge of the axis, so no off-screen
   point can ever produce a phantom segment.

2. **Boxcar mode toggle** — new `pb_boxcar_mode` button ("Boxcar: OFF/ON") in the
   bottom-left area (formLayout_10). When OFF (default), the A<n> poll timer does
   not start when Mode 1 starts — raw boxcar data is not collected and the orange
   trace is not shown. When ON, poll timer starts (or resumes) on Mode 1 start.
   The F1/F2/F3/F4 preset labels (label_9, label_11, label_8, label_12, label_14,
   label_15, label_18, label_19) are removed programmatically; `pb_show_raw_mean`
   ("Raw Avg") is moved into formLayout_10 alongside the new boxcar button.
   F1–F4 QShortcut bindings and `f1()`–`f4()` handler methods are removed.

3. **Remove Raw σ** — `pb_show_raw_stddev`, `show_raw_stddev`, `_raw_stddev_max_seen`,
   `series_stddev`, `series_stddev_slope`, `axis_stddev`, `_on_toggle_raw_stddev()`,
   and `STDDEV_MAX_SCALE` are all removed. The raw std dev value (`raw_stddev_uV`)
   parsed from the R record is still shown in the footer status string.

---

### src/pimd_gui.py — v4.05 — clear raw series on Mode 1 start

`series_raw_mean` and `series_stddev` are now cleared every time Mode 1 starts
(Start button → S command), not only on DEL/Clear or toggle-off. Previously,
stale data from the previous session remained in the series; when the new
session started, the QLineSeries polyline connected the last old point (at an
old x-timestamp, off the visible window) to the first new point, drawing
diagonal phantom traces that appeared as multiple overlapping orange plots on
the chart.

---

### mcu/pimd_mcu.py — v4.18 — restore sleep_us pacing, add post-read retry

v4.17's full BUSY edge sync (`while not busy_pin.value()` → `while busy_pin.value()`)
was correct in principle but the BUSY-high pulse at 10 kHz is only ~15 µs —
too short for MicroPython's polling loop to catch reliably. Only ~1 in 6 pulses
were detected, dropping effective sample rate from ~10 kHz to ~1.6 kHz (Sa/s
fell from 9.8 to 6.4; footer showed "Rx 1.6 kHz" instead of "10.0 kHz").

**Fix:** restore `sleep_us(period_us)` pacing in `acquire_raw_average()` and
change `read_raw_sample()` to:
1. Wait for BUSY low before reading (handles landing mid-conversion)
2. Read SDOB
3. Post-read check: if BUSY went high during the 3.2 µs SPI transfer (MCLK
   fired mid-read), wait for BUSY low and read again once. This catches the
   "just-before-MCLK" case that caused the 1/4 and 1/2 discrete outliers.

Double-retry probability is negligible (retry happens right after BUSY falls,
well before the next MCLK). `busy_high_count` (B command) now counts mid-SPI
races rather than edge-sync calls.

---

### mcu/pimd_mcu.py — v4.17 — BUSY-edge sync in read_raw_sample()

v4.16 guarded against reading SDOB while BUSY was already high, but left a
second corruption window: when `read_raw_sample()` is called just before MCLK
fires, BUSY is low (previous conversion done), the guard passes, and the SPI
read starts — then MCLK fires mid-transfer and the LTC2508-32 invalidates the
SDOB register, producing a bit-truncated result.

**Evidence:** v4.15/v4.16 min/max showed outliers at ~375k µV and ~750k µV
alongside normal samples at ~1511k µV — ratios of exactly 1/4 and 1/2,
consistent with 1–2 bits of the SPI transfer being cut off mid-read and the
remaining bits being zero-filled. The partial v4.16 fix (direction constraint
lifted but discrete outliers persisted) confirmed the mid-read corruption
theory.

**Fix:** replace "wait only if BUSY already high" with full edge sync:
1. `while not busy_pin.value(): pass` — wait for MCLK to fire (BUSY rises)
2. `while busy_pin.value(): pass` — wait for conversion complete (BUSY falls)
3. Read SDOB — maximum margin from both edges, fully hardware-locked

`acquire_raw_average()`'s `sleep_us(period_us)` removed — each
`read_raw_sample()` call now naturally takes exactly one MCLK period via the
BUSY waits, so the software timer is no longer needed and can't drift.

---

### mcu/pimd_mcu.py — v4.16 — fix BUSY race in read_raw_sample()

`read_raw_sample()` was checking `busy_pin.value()` but reading SDOB immediately
regardless — the `if` only incremented a counter. The `sleep_us()`-paced loop in
`acquire_raw_average()` drifts relative to the free-running PWM hardware; when
drift places the software read mid-conversion, BUSY is high and SDOB returns
corrupt/low data.

**Evidence (v4.15 diagnostic):** under SoC conditions, min/max in the R record
showed the occasional sample dropping from the normal cluster of ~1,511,000 µV
to ~375,000 µV — a ~1,136,000 µV (75%) drop. A handful of such outliers per
256-sample window are enough to swing the boxcar mean by several mV and produce
the sawtooth oscillation visible in `pimd_gui.py`'s "Raw Avg" chart toggle. The
mean never *exceeded* the Mode 1 filtered value because all outliers go low, not
high (an incomplete conversion reads a partial/stale register, never an inflated
one).

**Fix:** add `while busy_pin.value(): pass` immediately after the existing counter
increment. The counter (`busy_high_count`, read via `B`) now measures how often
the wait was needed rather than how often a bad read occurred — useful for
confirming drift rate drops to near zero with the fix applied.

No change to `acquire_mode2()` — its SPI reads are done inline with their own
timing (not via `read_raw_sample()`).

---

### mcu/pimd_mcu.py — v4.15 — per-call min/max in R record

`acquire_raw_average(n_samples)` now computes and returns `min_uV` and
`max_uV` across the `n_samples` collected in one call (converted to µV via the
same `RAW_FULL_SCALE_UV / 2**14` scale as mean and std). The `R` record format
gains two trailing fields:

```
R<t>, <mean_uV>, <std_uV>, <n>, <freq_kHz>, <pulse_us>, <delay_us>, <min_uV>, <max_uV>
```

**Motivation**: the raw boxcar-average path (`A<n>`) shows a sawtooth oscillation
in reported mean (up to ±mV scale) and std dev up to 70,000 µV under SoC
conditions, while the filtered path stays at ~50 µV. If even a handful of the
`n` samples are wildly off (bimodal distribution), `max − min` will be
disproportionately large relative to the std dev, pinpointing the same
read-before-write race suspected from the v4.13 Mode-2 fix but now in the
static-config `sleep_us()`-paced loop. No functional change to acquisition
logic — diagnostic only.

---

### src/pimd_gui.py — v4.03 — visualise the raw boxcar-average path

Under SoC conditions, the top-right Std Dev box (filtered path) reads ~50 µV
as expected, but the footer's raw-path figure (`A<n>` boxcar average) was
seen up to 70,000 µV — far beyond what the oversampling-mismatch fix in v4.02
explains. This is now suspected to be the **same unresolved mechanism** as
the Mode 2 single-cell noise investigated earlier (mcu/pimd_mcu.py v4.08-
v4.14): both are a static/unchanging PWM config read repeatedly via
`read_raw_sample()` in a `sleep_us()`-paced loop, with no `BUSY` check. That
investigation was closed with "use Mode 1 instead" — but Mode 1's own `A<n>`
path showing the same magnitude of anomaly suggests the earlier conclusion
was premature and there's a real, shared bug still to find.

**Added two chart toggles** to make the anomaly visible for further
diagnosis, reusing existing-but-previously-unused chart infrastructure:
- **"Raw Avg"** — overlays `raw_value_uV` (orange) on the existing voltage
  axis next to the filtered-path blue trace, for visually comparing the two
  means.
- **"Raw σ"** — plots `raw_stddev_uV` (red) on the existing `series_stddev`/
  `axis_stddev`, previously wired up but never actually fed data. The axis
  range now auto-expands (`_raw_stddev_max_seen`) as larger values are seen,
  since the old fixed 0-1000 µV range can't show a 70,000 µV spike — was a
  silent display ceiling, not just a stddev problem.

Both default off; `DEL`/Clear resets them along with the rest of the chart.
No firmware change yet — this is the visualisation step before attempting a
fix, per the plan to look at the pattern before guessing at the mechanism
again.

---

### Standard Operating Conditions (SoC) — established 2026-06-18

**TODO: roll this section into DESIGN.md §3 ("Measured operating envelope")
once confirmed stable — DESIGN.md is read-only for agents, left here per
existing policy.**

For repeatable bench testing/comparison, the reference test condition is:

- **Mode 1**, 10.0 kHz / 20.0 µs pulse / 10.0 µs sample delay / 256 decimation
- Coil in air, no targets
- 20 V bench supply
- **From cold, allow 4 minutes to settle** — expect roughly a 50 µV/s drop
  during this warm-up. Don't take noise-floor readings as representative
  before this point.
- `src/pimd_gui.py` now defaults to these values at startup (v4.02, below).

**Reference capture:** `AI refs/SteadyState.jpg` — first half of the plot at
256 decimation, second half (after a DS Factor toggle) at 1024. Shows the
settled noise floor and the slow thermal drift; this is the trace future
comparisons should be checked against. (File currently lives in the scratch
`AI refs/` folder — move into `pics/` if it's to become a permanent DESIGN.md
asset.)

---

### mcu/pimd_mcu.py — v4.14 — same-freq boundary leakage + averages=256 crash

User testing of a 2-band, same-frequency-different-pulse-width dynamic
profile (`D128;5000,50.0,<9 delays>;5000,10.0,<9 delays>`) found two issues:

**1) Cross-band leakage at same-frequency boundaries.** First cell of each
band showed std dev 55-65 mV vs 2-12 mV for the rest of that band (user's
`stats_20260617_212108.csv`) — the same signature as the original v4.06
cross-band leakage. Cause: `needs_settling` (the flag that triggers
`BOUNDARY_PRIME` extra coil-settling periods) was gated on `at_boundary`,
which only checks for a *frequency* change. This profile's two bands share
5000 Hz but differ in pulse width (50 µs vs 10 µs) — a real drive-energy
change that `at_boundary` didn't see, so settling never applied. Fix:
`needs_settling = at_boundary or dd != cells[prev][2]` — also fires when
drive duty (`dd`, which `pulse_us` feeds into) changes, independent of
frequency. `pwm.freq()` itself is still only called when frequency actually
changes (unrelated concern, unchanged). Verified: re-running the same profile
post-fix, the first-cell std devs dropped to 1.7-5.7 mV, in line with the
rest of each band.

**2) Board crash at averages=256** (averages=128 was fine — a scaling issue).
`acquire_mode2`'s rolling buffers were plain Python lists using
`append()`+`pop(0)`, an O(avg_depth) shift on every sample, for every cell,
every period — scaling badly and almost certainly the cause (heap churn /
CPU starvation) of an unhandled exception that previously crashed the board
outright (the main loop only caught `KeyboardInterrupt`, nothing else). Fix:
replaced with pre-allocated fixed-size circular buffers (`rolling_idx`) and
an incrementally-maintained `rolling_sum`/`rolling_count` per cell — O(1) per
sample regardless of `averages`, no list resizing. Also wrapped the Mode 2
call in the main loop in `try/except Exception` so any future unhandled
error reports over serial (`Mode 2 ERROR: ...`) and returns to a safe state
instead of crashing silently. Verified: the exact profile that crashed before
now runs cleanly for 5+ seconds at averages=256 with the board remaining
responsive afterward (`V` command still answers normally).

---

### mcu/pimd_mcu.py — v4.13 — Mode 2 cell-misattribution bug found and fixed

**The real bug, found after v4.08–v4.12 investigated and ruled out PWM-rewrite
jitter, command-poll overrun, BUSY-violation rate, and overrun rate (none
correlated with the anomaly — see that section below for the full trail).**

LTC2508-32 datasheet review (`LTC2508-32.pdf`, "MCLK Timing" p.20) plus a raw
(`averages=1`) capture revealed the real signature: a 2-cell dynamic profile's
two channels weren't *noisy* — at 57 kHz they reported **exactly swapped**
values (deterministic, not random), and at 25 kHz they **randomly flipped**
between the two cells' true values. Reversing the delay order in the `D`
command reversed which channel reported which value, proving array-order-
following mis-indexing rather than measurement noise. Averaging blended the
two true values into a clean-looking but wrong mean with deceptively low std
dev — worse than visible noise, because it hides the error.

**Root cause:** `acquire_mode2()`'s non-boundary cells wrote the new CC (duty)
value *before* reading SDOB (a deliberate v4.01 design choice). Writing a new
compare value while the PWM counter has already passed it can fire an
immediate spurious trigger — the same family of issue as the already-fixed
v4.04 freq/WRAP bug, but for `duty_u16`'s compare register instead of `freq`'s
WRAP register. The read immediately after a write-first then captures *this*
cell's own just-triggered conversion instead of the *previous* cell's
already-completed one — a clean off-by-one that only shows up when consecutive
cells' duty values actually differ (explaining why the single-cell case was
immune — nothing to swap with — and why this was missed for so long).

**Fix:** read SDOB before writing new CC values for *all* cells, not just
boundary cells (which already did this for a different reason — the v4.04
WRAP race). Verified margin: read (~6-7 µs) + write (~2 µs) ≈ 9 µs must precede
the new cell's own trigger; the smallest delay in any compiled profile is
band4's ≈11.8 µs (drive_duty + 6.03 µs + 0.752 µs correction), so all existing
profiles are safe.

**Verification:**
- 57 kHz, delays 6.03/9.71 µs, both array orders: now correctly tracks
  delay→value regardless of position (was backwards/order-following before).
- 25 kHz, delays 7.6/10.0 µs: stable per-cell values (~3518 mV / ~820 mV), no
  more bimodal swapping (was randomly flipping between the two before).
- Full CLASSIFY_EP sweep (Q4): values now track nominal thresholds tightly
  across nearly every cell (e.g. 5 µs/57.0 kHz band: 4480/3994/3515/2987/2510
  mV vs nominal 4500/4000/3500/3000/2500), std devs mostly single-digit to
  ~20 mV (down from up to 58 mV pre-fix). Band 0 (10.6 kHz) still shows some
  elevated std dev (22–138 mV) — not yet investigated, lower priority since
  absolute values are sane.
- The original single-cell (n=1) noise (~24–30 mV) is **unchanged** by this
  fix, as expected — a never-changing duty value can't trigger this race.
  That remains a separate, lower-priority gap: Mode 1 already covers genuine
  single-point measurement well (<100 µV), so Mode 2's dynamic single-cell
  profiles aren't the right tool for that use case.

`busy_high_count` (v4.11) and `overrun_count` (v4.12) diagnostics are kept
(harmless) but did not correlate with this bug — candidates for removal in a
future cleanup pass.

---

### mcu/pimd_mcu.py — v4.08–v4.10 — Mode 2 single-cell noise investigation

**Trigger:** a 1-band/1-cell dynamic profile (`averages=16`, 25 kHz/10 µs/7.6 µs
— built via the new Profile Builder tab) showed std dev up to 30 mV, vs Mode 1's
<100 µV at the *identical* parameters (waveforms verified identical on scope).
Scope-measured pulse-to-sample delay jitter: 60 ns in this Mode 2 case vs <10 ns
in Mode 1 (DESIGN §8 documents ~15–20 ns for the static-PWM baseline).

**First diagnostic (no code):** the existing `A32` raw boxcar-average command
(same raw SPI0 ADC path as Mode 2, but with a static, never-rewritten PWM
config) measured ~100 µV–1 mV at the same parameters — ruled out "raw vs
filtered ADC path" as the dominant cause (DESIGN §7 already expected ~350 µV
for M=16 raw averaging).

**v4.08 (hypothesis 1, falsified):** theorised that rewriting `duty_u16()` with
unchanged values every period was adding PWM edge jitter. Added `last_dd`/
`last_sd` tracking to skip the rewrite when unchanged. Re-tested: std dev
unchanged (~24 mV). Disproved by direct A/B.

**v4.09 (hypothesis 2, falsified):** theorised that `check_for_commands()`
running on every single 40 µs period (unique to n=1, normally amortized over
many cells) could occasionally exceed the period's time budget and cause
`read_raw_sample()` (no BUSY check) to catch a stale value. Throttled the poll
to once per `COMMAND_POLL_MS` (1 ms). Re-tested: std dev unchanged (~24 mV).
Also disproved.

**Isolated by elimination — the actual finding:** compared n=1 (~24–30 mV)
against an n=2 profile with two *different* delays (different `sample_duty`
each period → ~310 µV, matching the A32/DESIGN expectation) against an n=2
profile with two *identical* delays (same `dd`/`sd` every period, just like
n=1 → back to ~25 mV). The deciding factor is not n=1 vs n>1, write-frequency,
or poll-throttling — it is specifically whether the **PWM compare value
actually changes between periods**. Holding it constant (whether by skipping
the write or rewriting the identical value) gives high noise; alternating
between genuinely different values gives the expected low noise. The exact
RP2040 PWM hardware mechanism for *why* isn't confirmed (would need datasheet/
register-level investigation beyond what code reading and serial A/B testing
can establish) — this is documented as the empirical, reproducible finding.

**Practical conclusion:** Mode 2 (interleaved sweep) is not suited to genuine
single-point / repeated-identical-cell measurement — that's exactly what Mode 1
already does well (<100 µV, confirmed). Multi-cell sweeps (Mode 2's actual
purpose, including CLASSIFY_EP) are unaffected since cells legitimately differ
period to period — confirmed by both the n=2-different-delays test above and
the original 45-cell CLASSIFY_EP testing (v4.06).

v4.08/v4.09's code changes are kept (harmless, mildly beneficial) but their
in-file comments have been corrected in v4.10 to not claim a fix they didn't
provide; no functional code changed in v4.10.

---

### src/pimd_classviz.py — v1.04

**Profile dimensions are now runtime state, not module constants.** `N_BANDS`,
`N_CELLS`, `N_CHANNELS`, `BANDS_META`, `BAND_LABELS`, `CELL_LABELS`,
`THRESHOLDS_V`, `NOMINAL_BASELINE_UV`, `PROFILE_IDX` all moved into instance
attributes set by `_set_profile_dims()`/`_apply_profile()`. The heatmap axes, 3D
surface, stats table, and single-cell band/cell combos all rebuild from these
(`_rebuild_heatmap_axes`, `_rebuild_3d_surface`, `_rebuild_stats_table`,
`_rebuild_single_cell_combos`). Default on-connect behaviour is unchanged — it
still sends `Q4` and shows the same 5×9 CLASSIFY_EP view.

**New "Profile Builder" tab.** Lets you edit a profile's bands (freq Hz / pulse
µs / delays µs / optional threshold V, one row per band — all bands must share
the same delay count), save/load named profiles as JSON in `src/data/profiles/`,
preview the exact `D...` command that will be sent, and **Send & Run** it: `E`,
`D<averages>;<bands...>`, `Q{DYNAMIC_PROFILE_INDEX}` (=5, must match firmware's
`NUM_PROFILES`), `G`, then resizes the whole UI to match via `_apply_profile()`.
Seeded with `src/data/profiles/CLASSIFY_EP_baseline.json` — the current
profile-4 band/delay data, the same one used to diagnose the v4.06 leakage fix —
so a known-good profile is the first thing you can load, tweak, and re-send
without editing firmware or reflashing.

`_resume_sweep()` / single-cell auto-exit now send `Q{self._active_profile_idx}`
instead of a hardcoded `Q4`, so resuming after a single-cell run correctly
returns to whichever profile (static or dynamic) was actually running.

---

### mcu/pimd_mcu.py — v4.07

**New `D` command — RAM-only "dynamic" profile.** Lets a PC app define a new band/
pulse/delay/averages combination and run it immediately without editing `PROFILES`
and reflashing. Motivated by the v4.06 leakage fix requiring a reflash per
`BOUNDARY_PRIME` trial — too slow for iterating on profile shapes generally.

```
D<averages>;<freq_hz>,<pulse_us>,<d1>,<d2>,...;<freq_hz>,<pulse_us>,<d1>,...;...
```

Parses into the same `{'name', 'bands', 'averages'}` shape as a `PROFILES` entry,
rejects bands with differing delay counts (rectangular only), validates with the
existing `validate_profile()` (unchanged — already iterates generically), and
stores the result in a new `dynamic_profile` global. **Not persisted** — lost on
reset, exactly like Mode 1's `*` configure command. Select it with
`Q<DYNAMIC_PROFILE_INDEX>` (= `NUM_PROFILES`, currently 5) same as any static
profile; `G`/`E` behave identically once selected.

**`get_profile(idx)`** added as the single profile-lookup point — `PROFILES[idx]`
for static indices, `dynamic_profile` for `DYNAMIC_PROFILE_INDEX`, else `None`.
Replaces direct `PROFILES[active_profile_index]` indexing in the main loop and the
`Q`/`G` command handlers. `L` listing includes the dynamic profile (if defined) as
an extra line at index `DYNAMIC_PROFILE_INDEX`.

---

### src/pimd_gui.py — v4.02

**Defaults to Standard Operating Conditions at startup** (see SoC section
above): 10.0 kHz / 20.0 µs pulse / 10.0 µs delay / 256 decimation. New
`apply_soc_defaults()` sets the slider/DS-factor state (same pattern as the
existing F1-F4 presets); the `*` command itself still only goes out when
Start is pressed, unchanged.

**Removed the footer's redundant "std dev: ... uV" entry.** It duplicated
the top-right **Std Dev** box — both were showing the firmware's own
filtered-path `p_stddev` (from the `*` record's 3rd field), just via two
different code paths (`luVsd` direct vs. a GUI-side recomputation over its
own `voltage_buffer` of the same incoming values). The GUI-side
recomputation added no information, so the whole `voltage_buffer`/
`computed_stddev` mechanism behind it was removed too (`NUMBER_STDDEV_POINTS`,
the buffer, the calc, and its `clear_chart()` entry).

**Raw-path boxcar average (`A<n>`) sample count now tracks DS Factor**
instead of a hardcoded `A32`. This was the real cause of "the std dev values
should be a lot closer": the footer's `Raw avg: ..., sd: ... uV (x32)` figure
comes from a *different* acquisition path than the Std Dev box — `(x32)` is
literally the `n_samples` argument echoed back from firmware's `A<n>`
handler, i.e. how many raw (undecimated) SDOB samples were boxcar-averaged —
relabelled `(N=...)` in the footer since `(x32)` wasn't self-explanatory.
At a 256 or 1024 DS Factor, the **filtered** path (Std Dev box) gets 8-32×
more oversampling than the raw path's fixed 32 samples — noise scales as
1/√N, so that alone predicts the raw figure being several × higher even with
identical underlying noise. `poll_raw_average()` now sends
`A{min(down_sample, 1000)}` (firmware caps `A<n>` at 1000, so 1024 clamps to
1000) so the two paths use comparable oversampling, making the comparison
meaningful instead of measuring mostly-unrelated averaging depths. Expect
the raw-path figure to still run somewhat higher than the filtered figure —
the LTC2508's onboard decimation filter is a proper sinc/FIR design, more
effective per sample than a plain boxcar average of single-shot raw
conversions (DESIGN §7: raw SDOB single-sample noise ≈ ±1400 µV) — but it
should no longer be off by orders of magnitude.

Values like "30,000 µV" seen before this fix were likely the combination of
the 32-sample raw average *and* not yet being past the 4-minute SoC warm-up
window (large thermal transients land harder on a smaller sample count) —
worth re-checking under SoC conditions now that both are addressed.

**v4.01:** Added editable port field, mirroring `pimd_classviz.py`'s pattern. Was
hardcoded to `'ttyACM0'`; now a `QLineEdit` (default `/dev/ttyACM0`) sits below the
existing Connect/Start/filename rows in the same grid layout. `serial_open()` reads
`self.le_port.text()`, stripping a leading `/dev/` if present, same as classviz.

---

### mcu/pimd_mcu.py — v4.06

**`acquire_mode2()` inter-band leakage fix.** Bands 3 and 4 showed systematic
~500 mV underreads on cells 0–7 and elevated std devs (25–58 mV) compared to
single-cell mode (<4 mV). The last cell of each band (cell 8) read correctly.

**Root cause — cascade contamination:** the sweep visits cells in band-major
order. Cell 8 of each band has its SDOB read at the start of the *next* cycle's
boundary processing (before the frequency changes), giving it a full sweep cycle
(~2 ms) to reach steady state — hence it reads correctly. Cells 0–7 of each
band have their SDBOs read within the same sweep cycle, only 1 PWM period after
the frequency change. When power drops sharply at a boundary (e.g. B3→B4:
P ∝ 10²×43003 → 5²×56992, a 3× drop), the previous band's excess coil energy
contaminates cell 0's initial conditions; cell 0's corrupt drive output then
feeds cell 1's initial conditions, and so on — cascading through cells 0–7. The
rolling average (depth 32) permanently locks in this contaminated value because
the contamination is fresh on every sweep cycle.

**Fix:** add `BOUNDARY_PRIME = 5` extra PWM periods of sleep at each band
boundary. Cell 0 of the new band now runs for 6 total periods before its SDOB
is read, giving the coil time to settle at the new frequency. This breaks the
cascade at source; subsequent cells chain from good initial conditions.

**Tuning:** `BOUNDARY_PRIME` is a named constant at the top of the file (near
`MIN_EMIT_MS`). Increase to 10 or 15 if std dev remains elevated after flashing.
The overhead scales with `period_i`, so the constant works for all boundaries.

**Performance:** 5 boundaries × 5 extra periods × ~35 µs avg ≈ 875 µs/cycle
overhead; cycle rate ~344 Hz; `MIN_EMIT_MS = 10 ms` means emit rate unchanged
at 100 Hz.

---

### src/pimd_classviz.py — v1.03

**Stats tab:** added "Save table CSV…" button. Saves whatever is currently displayed in
the 45-row table (Band, Threshold, Delay, Latest mV, Mean mV, Std mV) — works correctly
when the table is frozen, capturing the snapshot at the time of freeze. Default filename
`src/data/stats_YYYYMMDD_HHMMSS.csv`; file dialog allows changing path.

---

### src/pimd_classviz.py — v1.02

**Resume Sweep now auto-restarts** — previously sent `E` + `Q4` but left the user to click
Start manually, so the sweep never came back. Now also sends `G` and sets the Start button
to Running immediately.

---

### src/pimd_classviz.py — v1.01

Added Stats & Isolation tab.

**Stats table:** 45-row table (band-major, one row per cell) showing Band, Threshold,
Delay (µs), Latest (mV), Mean (mV), Std (mV). Values update at ~30 Hz from the rolling
buffer; window configurable (default 3 s). Freeze button. All values in mV to 1 d.p.
with comma thousands separators (e.g. `4,597.6`).

**Single-cell isolation mode:** stops the Mode 2 profile-4 sweep and fires a single
fixed freq/pulse/delay via Mode 1 (`*<kHz>,<pulse>,<delay>,<ds>` + `S`). Selectable
from Band + Cell combos (dropdown shows `threshold/delay` pairs per band); Downsample
spinbox (default 256). Parses Mode 1 `*` output records and displays:
- **Value** — current averaged reading (mV)
- **HW σ** — per-reading std dev reported by firmware (intra-average noise)
- **Run mean / Run σ** — running mean and std over up to 1000 readings (inter-reading
  drift and noise)
- **N** — count since last Run Single Cell click

"Resume Sweep" sends `E`, re-selects `Q4`, and re-enables the Start button. Clicking
Start while in single-cell mode also auto-resumes. Purpose: isolate noise per cell
without frequency switching, to determine whether noise is frequency-change-induced.

---

### src/pimd_classviz.py — v1.00

New PC tool: real-time signature visualiser + labelled-data logger for Mode 2
profile 4 (CLASSIFY_EP).

- **5×9 pyqtgraph heatmap** (bands = rows, threshold-voltage cells = columns) of
  signed cell deviations (Δ = raw − baseline). Per-band delay shown in status bar
  on mouse hover.
- **Display modes:** Δ deviation (default) | Z normalised | RAW abs µV.
  Δ and Z use a diverging blue–white–red colormap centred at zero so polarity and
  sign-flips across cells/bands are immediately visible; RAW uses sequential.
- **Symmetric autoscale** (±max|value|) toggled by checkbox; manual range entry when off.
- **Baseline source modes:**
  - *Static capture* — average N frames (default 64), stores per-cell mean + std.
  - *Rolling median* — per-cell median over last T seconds (default 3 s),
    continuously recalculated; drift-corrects bench without user intervention.
  - *Nominal thresholds* — (4.5 − 0.5·j) V × 1e6 µV per cell, all bands.
  Baseline info label shows mode, frame count, and age.
- **Freeze toggle.** Zero-crossing display: per-band polarity sign and interpolated
  threshold voltage where Δ flips sign — useful ML feature (silver/stainless crossover).
- **ML bridge:** label field + "Record Snapshot" appends one CSV row; "Log Continuously"
  toggle appends every incoming W4 frame with the current label (for target passes).
  Configurable CSV path (default `src/data/signatures_YYYYMMDD.csv`); stable header
  written once; header comment documents all 137 columns.
- **Phase 2 — 3D surface:** GLSurfacePlotItem of the current display matrix (Δ by
  default), orbit camera. Toggled with "Switch to 3D Surface" button. The 5-band axis
  is coarse — interpolation is cosmetic only.
- Serial seam matches `pimd_scope.py` exactly (QSerialPort `readyRead` signal, editable
  port field defaulting to `/dev/ttyACM0 @115200`). On connect sends `E` then `Q4`;
  on close/disconnect sends `E`.

---

### mcu/pimd_mcu.py — v4.05

**CLASSIFY_EP (profile 4) band frequencies updated to prime-ish actuals.** Round numbers
replaced with the PWM-achievable prime-ish frequencies from the §17.1 equal-power sweep:

| Band | Old Hz | New Hz | Pulse |
|------|--------|--------|-------|
| 0 | 10600 | **10601** | 40 µs |
| 1 | 17600 | **17599** | 30 µs |
| 2 | 29200 | **29201** | 20 µs |
| 3 | 43000 | **43003** | 10 µs |
| 4 | 57000 | **56992** | 5 µs |

These are the measured operating points from the bench power sweep (2026-06-17). Using
prime-ish rates avoids beat-frequency noise (same principle as the 3719 Hz choice noted
in §8). Delays and averages unchanged.

---

### mcu/pimd_mcu.py — v4.04

**`acquire_mode2()` band-boundary SDOB corruption fix.** The last delay cell of each band
(d8 for P0–P3 in CLASSIFY_EP) read an incorrect, unstable value while all other cells were
clean and monotonic.

**Root cause:** when `pwm.freq()` increases the PWM frequency, the RP2040 hardware shrinks
the WRAP register. If the running counter already exceeds the new WRAP it wraps immediately,
generating a spurious falling edge on GPIO5 (MCLK). The LTC2508 treats this as a new
conversion trigger, overwriting the previous cell's SDOB result before the firmware reads it.
The four increasing-freq boundaries (bands 0→1, 1→2, 2→3, 3→4) were all affected; the
decreasing-freq wrap-around (band 4→0, i=0) was immune because enlarging WRAP never causes
an immediate wrap.

**Fix:** at band boundaries, read SDOB **before** calling `pwm.freq()`, then change freq,
then write CC. Non-boundary cells retain the original CC-write-first order unchanged.
Timing margin at the tightest boundary (band 4, 5 µs pulse): CC is written ~2 µs after the
counter resets on the freq change; drive trigger fires at 5 µs — 3 µs margin, safe.

---

### mcu/pimd_mcu.py — v4.03

**Profile structure changed** — replaced flat `freq_hz` / `pulses_us` / `delays_us` top-level
keys with `bands: [(freq_hz, pulse_us, delays_us), …]` to support per-band frequencies
within a single profile. All existing profiles (0–3) converted; profile structure is now a
tuple of `(freq_hz, pulse_us, delays_us_tuple)` per band.

**New profile 4 — CLASSIFY_EP** (5 equal-power bands × 9 calibrated sample delays = 45 cells).
Delays sourced from `src/data/delaycal_1706-104844.csv` (voltage-threshold crossing times
at 4.5 V → 0.5 V in 0.5 V steps).

| Idx | Freq | Pulse | Sample delays (µs) |
|-----|-----------|-------|--------------------|
| 0 | 10601 Hz | 40 µs | 8.56 8.98 9.37 9.72 10.08 10.49 10.96 11.57 12.53 |
| 1 | 17599 Hz | 30 µs | 8.12 8.54 8.92 9.27  9.63 10.02 10.50 11.10 12.03 |
| 2 | 29201 Hz | 20 µs | 7.62 8.03 8.40 8.75  9.11  9.50  9.96 10.55 11.46 |
| 3 | 43003 Hz   | 10 µs | 6.80 7.22 7.58 7.93  8.28  8.66  9.11  9.70 10.57 |
| 4 | 56992/Hz   |  5 µs | 6.03 6.43 6.78 7.12  7.46  7.84  8.28  8.85  9.71 |

**`acquire_mode2()` rewritten** — flattens all bands into a single cell list at entry;
updates PWM freq only at band boundaries (detected by comparing `cells[i][0]` to
`cells[(i-1)%n][0]`); the interleaved one-period-per-cell rolling-average loop is
otherwise unchanged.

**`validate_profile()`** updated to iterate over `bands` tuples.

**L command** updated: record format now emits `n_bands` and `n_cells` in place of the
former `n_pulses` / `n_delays` fields:
```
L<idx>,<first_freq_khz>,<n_bands>,<n_cells>,<averages>,<name>
```

**`acquire_raw_average()` primed** (v4.02, carried into v4.03) — 5-sample discard at the
start of each `A<n>` call to allow PWM + front-end to settle after any freq/duty change
from a prior `*` command. Overhead ≤ 5% at 10 kHz; negligible at higher frequencies.

---

### src/pimd_scope.py — v4.01

- `PROFILES_META` converted from flat per-profile dict to `{bands: [(freq_khz, pulse_us,
  delays_us), …]}` format, matching firmware v4.03 structure.
- Profile 4 `CLASSIFY_EP` added to `PROFILES_META`.
- `_update_titles()` updated: detects multi-band profiles; header shows `multi-freq` when
  bands have different frequencies; each subplot labelled `{freq}kHz/{pulse}us d={delay}us`
  for multi-band profiles, `d={delay}us` for single-band; fontsize=7 when >12 channels.

---

### src/pimd_delaycal.py — v1.02 (new tool, not yet in DESIGN §15)

New PC tool for calibrating `A<n>` delay pairs. Sends sequential `*` + `A<n>` commands
across user-specified (freq_kHz, pulse_us) pairs and delay ranges, records threshold
crossings, and exports a CSV.

**Double-send bug fixed (v1.01 → v1.02):** `_on_r_record()` was calling `_send_next_step()`
twice on pair transitions — once via `_check_thresholds()` → `_advance_pair()`, and again
at the end of `_on_r_record()`. Result: `_prev_delay` was reset to `start_delay` on every
other pair; rows 3, 5 showed all cells equal to start_delay. Fix: save `current_pair_idx`
and `current_delay` before calling `_check_thresholds()`; only advance state if `_pair_idx`
is unchanged after the call.

**Known cosmetic issue:** docstring title line still reads "v1.01"; `APP_VERSION = '1.02'`
and the inline changelog entries are correct. Reconcile on next edit.

---

### Bench observations — 2026-06-17

**CLASSIFY_EP (profile 4) confirmed streaming:** firmware flashed, 45-channel W4 records
verified. Two consecutive records (50 ms apart):

```
W4,47439,4597625,4120578,...,562667,227699
W4,47489,4597492,4120426,...,562667,227699
```

Values in µV. Channels decrease monotonically across each band's delay sweep (shortest
delay → highest signal ~4.5 V; longest delay → lowest signal ~0.23 V). Values stable
between records. All 5 bands × 9 cells populated correctly.

---

