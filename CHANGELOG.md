### src/pimd_classviz.py — v1.62 — FIX repeat_idx stuck at r1

Bench report: `Fe_spanner_01` rows reading `r1` where they should read `r2` — three rows
showing `@180mm  x  r1`, same placement *and* same repeat. Confirmed in the corpus: every
pair captured in the 15:39 session was stuck at r1. Two independent causes, and only one of
them was recent.

**The suggestion was never recomputed after a save — latent, not a regression.**
`_update_sig_repeat_idx_suggestion()` is connected in exactly one place, to placement-*widget*
change signals. `_reload_editable_signature_list()` rebuilds `_editable_repeat_counts` after
every save and then never re-ran the suggestion, so the spinbox kept its stale value: two
captures of one placement with nothing touched in between both saved as r1. Earlier sessions
hid this by alternating placements between repeats (c13 x → c14 y → c15 x), where each widget
change fired the signal; the 15:39 session did back-to-back repeats and exposed it. Fixed by
calling the suggestion at the end of `_reload_editable_signature_list()` — save, delete and
file-open all land on that one seam, so no second signal connection was needed.

**The placement key split across the v1.60 boundary — this one v1.60 caused.** Rows captured
before it carry `face_normal=z`; `_placement_from_widgets()` now yields `na`; both are in the
placement tuple. So returning to any pre-v1.60 placement failed to match its own history and
restarted at r1. It had already happened — c20 (`@180 x r1`, `z`) and c23 (`@180 x r1`, `na`)
are the same physical placement. `_placement_tuple_key()` now takes both its field list and
its per-field normalisation from `pimd_corpus_check` (below) instead of restating them, so
the app and the checker cannot drift on what "the same placement" means — which was the
constraint the v1.60 design turned on in the first place.

Verified offscreen: `z` and `na` (and a non-zero offset) key identically while `long_axis`
still separates; classviz's tuple equals `pimd_corpus_check.placement_key()` for the same
dict; asking for `Fe_spanner_01 @180 y` after a reload suggests **r3** against two captures on
file where it previously stayed at 1; a placement with no history still gives r1; and the
cross-boundary case — `Cu_pipe_01 @60 z`, whose file rows carry `face_normal=z` — now counts
them and suggests r3. Nine harnesses pass under `-W error::DeprecationWarning`.

**Not yet run on the bench**: capture twice at one placement without touching a control; the
second must save as r2. (2026-07-28)

---

### src/pimd_corpus_check.py — v1.7 — placement key normalises the fields v1.60 froze

`placement_key()` and `target_key()` route each field through a new `placement_value()`, which
substitutes the not-applicable constant for the three fields classviz v1.60 stopped accepting
as inputs (`PLACEMENT_CONSTANT_FIELDS` = `face_normal` `na`, both offsets `0`). Without it a
corpus straddling that change splits one physical placement into a `z` group and an `na`
group, so a repeat reads as a fresh base and the repeat-consistency check compares nothing
against nothing. classviz imports both the field tuple and this helper, so there is one
definition rather than two that agree by inspection.

Honest about the cost, in the constant's own comment: this discards information in principle
— a corpus with genuinely different offsets would collapse to one placement. It does not in
practice, since no corpus on disk has a non-zero offset or a `face_normal` other than
`z`/`na`, and neither can be entered any more.

Effect on the live corpus, with the repaired repeat_idx values: the run goes from **30 checks
to 90**. Repeat-consistency now pairs a base against a repeat for the spanner placements
instead of seeing duplicates, and **distance-falloff runs at all** — it had been SKIPping for
want of a target at ≥3 distances, and now fits copper pipe at n = 2.05 / 1.81 and the spanner
at n = 1.42 / 1.63. The FAIL count rises with the check count; those are the noise-floor
problem already recorded for this corpus, not a metadata one. (2026-07-28)

---

### findings — 8 captures renumbered in the v3 corpus (repeat_idx collisions)

Data repair, recorded because it edits captured data. Eight captures in
`gui_signatures_targets_v3_20260728_142316.csv` carried a `repeat_idx` colliding with another
capture at the same placement, caused by the two v1.62 bugs above:

| capture | target | placement | was | now |
|---|---|---|---|---|
| `..._153912_c22` | Fe_spanner_01 | @180 y | r1 | r2 |
| `..._153912_c23` | Fe_spanner_01 | @180 x | r1 | r2 |
| `..._153912_c25` | Fe_spanner_01 | @120 y | r1 | r2 |
| `..._153912_c27` | Fe_spanner_01 | @120 x | r1 | r2 |
| `..._153912_c29` | Fe_spanner_01 | @120 z | r1 | r2 |
| `..._153912_c31` | Fe_spanner_01 | @60 z | r1 | r2 |
| `..._153912_c33` | Fe_spanner_01 | @60 y | r1 | r2 |
| `..._153912_c35` | Fe_spanner_01 | @60 x | r1 | r2 |

`c23` is the cross-version one: it pairs with `c20`, which carries `face_normal=z` from before
v1.60, and only groups with it under the v1.7 normalisation.

Method: group by the normalised placement key, order by `captured_at`, assign 1..n. Idempotent
where the data was already right — Cu_pipe's existing r1/r2 pairs were untouched — and a
re-run reports no changes. `src/data/corpora/` is gitignored, so a timestamped `.bak-` copy was
taken first; git could not have restored it. The write proved itself rather than being trusted:
same header, same 2205 rows, and **only** the `repeat_idx` column differing from the backup
(504 cells = 8 captures × 63 cells).

Assumption made visible rather than buried: renumbering by capture time presumes no repeat_idx
was deliberately set out of order. Every affected value was the default 1, so nothing suggests
otherwise. (2026-07-28)

---

### src/pimd_classviz.py — v1.61 — signature rows carry long axis + repeat; colour is per target

Reported as detail the signature list had lost. It had not: `git log -S` finds no commit
that ever carried it, and the label format is unchanged since **v1.30**. The detail existed
in the v1.58/v1.59 build that ran on the bench today and is not on disk (see the v1.60
entry). So this is a restore from description rather than a revert, and worth recording as
such — the repo was never the source it was lost from.

**Rows now identify their capture.** `✎ Cu_pipe_01 @120mm  z  r2   amp=24 SNR=27.4 [ok]`.
Today's corpus is one target across four distances × three orientations × two repeats, so
six captures shared the string `Cu_pipe_01 @120mm` and nothing on the row separated them.
`long_axis` and `repeat_idx` already arrived from `_scan_editable_signature_file()` for the
editable and scratch sources; they were simply not formatted in. A `long_axis` of `na`
carries nothing and is omitted, as is the whole pair for the legacy 3-tuple key shape.

**Colour is now per target, not per row.** It was `pg.intColor(i, hues=…)` on the row's
index, so a target's colour changed whenever the list grew or re-sorted and two captures of
one target looked unrelated. New `_template_color()` takes the hue from the target_id and
steps **value** (230 → 140) across that target's captures, with a ±10° hue jitter alongside.

Three things that shaped it:

- The colour is not only the list row. It is stored into `_analysis_templates[key]['color']`
  and is the pen for the **chart overlay curves** and the **Family Plane markers**, so a flat
  per-target colour would have made two overlaid orientations of the same target
  indistinguishable. Hue-per-target with shade-per-capture serves both.
- The hue comes from **`zlib.crc32`, not the builtin `hash()`**. Python salts str hashing per
  process, so `hash()` would repaint every target on each launch — a subtler version of the
  instability being fixed, and one that passes every in-process check. There is a test that
  runs the helper in two subprocesses under different `PYTHONHASHSEED` values, because that
  is the only place the trap is visible.
- Value alone cannot separate many captures of one target: at 17 captures the steps are ~5
  units apart. The hue jitter helps and is honestly not a full answer — 17 distinct shades of
  one hue do not exist. The label is what identifies a row; the colour groups.

`_merge_template_list()` splits into two passes, because the shade needs each capture's
ordinal within its target and that is not known until every key is resolved. Pass 1 only
hoists the existing key-shape branch unchanged; pass 2 builds the items. Group sizes are per
source batch exactly as the old row index was, and the hue does not depend on them.

Verified offscreen against the real corpora: every v3 row carries its axis and `r<n>`, and
the six rows sharing `Cu_pipe_01 @120mm` are now six distinct strings; `Cu_pipe_01`'s 17
captures occupy hues 10–30 and values 140–230 while `Fe_spanner_01`'s occupy 320–340, with
the two bands asserted not to overlap; the helper returns identical colours under
`PYTHONHASHSEED` 0 and 12345; and overlays rebuild over a checked selection with every stored
colour valid. Noted while testing: `pimd_corpus_check.load_corpus()` dropped legacy-schema
support at v1.5 and **both** corpora on disk are v1.32+, so `_merge_template_list`'s 3-tuple
branch is defensive dead code for any real file — it is exercised synthetically rather than
left untested. All eight harnesses pass under `-W error::DeprecationWarning`. **Not yet run
on the bench.** (2026-07-28)

---

### USAGE.md — v1.23 — classviz v1.60 → v1.61

§5's Analysis bullet gains what a signature row reads and what its colour means (one hue per
target_id, shaded per capture, stable between sessions because it is derived from the id).
§1 diagram version follows. (2026-07-28)

---

### src/pimd_classviz.py — v1.60 — remove the face_normal / offset X / offset Y capture inputs

Three of the structured placement inputs were never used, and one of them was actively
writing junk. `face_normal` is a *persisted* combo (`sig_face_normal`), so a value chosen
once silently rode along on every later capture: all 12 captures in the first v3 corpus —
`Cu_pipe_01`, a **tube** — carry `face_normal=z`, a field its own tooltip reserves for the
dim_a × dim_b face of plates/discs/sheets and defines as `na` where meaningless. The X/Y
offsets were 0 throughout, which is the correct "centred" value, but nobody was setting
them either.

The three widgets are gone from `_build_target_placement_widget_set()`. Row B now reads
Long axis · Medium · Repeat #, absorbing Repeat # from the row the offsets used to share —
on its own it did not earn a row, so the form drops from three rows to two.

**The schema does not change, and that is the point of the design.**
`_placement_from_widgets()` still returns all eight keys, now with `face_normal='na'` and
both offsets `0` as literals, so the corpus CSV columns, the session dump's `mark_target:`
line, `_placement_tuple_key()` and the `pimd_features.Plateau` construction are all
untouched. Removing the columns would have broken
`pimd_corpus_check.PLACEMENT_FIELDS`, which keys repeat-consistency grouping on all seven
placement fields, and stranded the two existing corpora that carry real values in them. The
placement tuple keeps all seven fields for the same reason: three are constant now, so it is
effectively (target, distance, long_axis, medium), but it must stay field-for-field aligned
with the checker's or the two tools would disagree about what "the same placement" is.

Settings save/restore for the three keys is deleted rather than migrated. A stale
`sig_face_normal` sitting in an existing `classviz_settings.json` is simply never read
again, which is precisely what ends the leak.

**Version skips 1.58 and 1.59, deliberately.** Ten captures in the current v3 corpus are
stamped `pimd_classviz.py v1.59`, and that version is in no commit, stash or reflog entry.
Investigated rather than assumed: there is exactly one `pimd_classviz.py` on the machine, and
the app producing those captures is a process launched at ~14:58 that has been running since,
so it loaded this file at a moment when it read `1.59`; the file has since been restored to
`1.57` with no git trace, and `git diff` confirms nothing but this change is uncommitted, so
no work was lost. Releasing a v1.58 *after* captures stamped v1.59 would make version order
contradict time order in exactly the provenance field that exists to record it, so the next
release is **1.60**. The gap is this paragraph, not an accident.

Verified offscreen: the three widgets are absent while target/distance/long_axis/medium/
repeat_idx remain; `_placement_from_widgets()` still returns all eight keys with `na`/0/0;
`_placement_tuple_key()` is asserted equal to `tuple(str(p[f]) for f in
pimd_corpus_check.PLACEMENT_FIELDS)` — against the checker's own constant, not a copy, so the
two cannot drift; `pimd_features.CORPUS_HEADER` still carries all three columns; both
existing corpora still scan (66 and 18 captures, `face_normal='z'` preserved on read); and a
settings file containing the six removed keys loads without error and saves without them.
All seven harnesses pass under `-W error::DeprecationWarning`, and the rendered form reads
Target/Distance on one row, Long axis/Medium/Repeat # on the next. **Not yet run on the
bench** — the check is that a new capture writes `face_normal=na, offset_x_mm=0,
offset_y_mm=0` and that `pimd_corpus_check.py` groups it as expected. (2026-07-28)

---

### USAGE.md — v1.22 — classviz v1.57 → v1.60

§5's Analysis bullet: the placement field list drops `axes, offsets` for `long_axis`, and
gains a paragraph on why `face_normal`/offsets are no longer inputs but are still written
`na`/0/0, plus the `long_axis` x/y/z convention spelled out in physical terms (coil long
axis / coil short axis and rover travel / coil normal) — that convention was queried on the
bench and is worth stating where it is used, not only in a tooltip. §1 diagram version
follows. (2026-07-28)

---

### src/pimd_classviz.py — v1.57 — show the surviving central-frame count; Frames default 60 → 100

Prompted by the question "aren't some of those 120 profiling frames discarded?". They are —
`pimd_features.CENTRAL_FRACTION` is 0.60, so `central_frames()` trims **20% off each end**
(not 25%) of the target window *and* both air anchors before stats. At 120 frames, 72 feed
the result. Nothing on screen said so.

It is not a live "profiling but not sampling" phase, and the display does not pretend
otherwise: every frame is sampled and buffered, and the trim is applied retrospectively to
the finished window in `_compute_sig_stats()`. Which frames get dropped depends on where the
window ends up, so the only honest live number is **how many of the frames held right now
would survive** — which is also precisely the warning wanted before a Space force-advance.
A now reads `COLLECTING target — 47/120 (28 central)`, and the colour follows that count:
yellow below `MIN_CENTRAL_FRAMES`, then the existing blue/green. That extends the ladder
rather than fighting it — yellow already meant "not ready" — so a phase reads yellow → blue
→ green as frames bank up, and an `ACQUIRED` row still yellow means the Frames setting
itself is too low. New `_central_frame_count()` routes through
`pimd_features.central_frames()` with the same throwaway `Plateau` the stats path builds,
so the trim keeps one definition and cannot drift from the corpus builder.

**A defect found while checking it.** `quality_flags()` stamps `short` when
`n_central < MIN_CENTRAL_FRAMES` (60), and the Training Frames default *was*
`MIN_CENTRAL_FRAMES` itself — 60 frames trims to 36 central, below the very constant it was
taken from, so a default-Frames capture was stamped `short` every single time. The Family
Plane scratch path had already solved this at v1.46 by sizing its window to
`ceil(MIN_CENTRAL_FRAMES / CENTRAL_FRACTION)` = 100, with a comment naming the problem; the
Training group never got the same treatment. That expression is now the named constant
`SIG_CAPTURE_N_DEFAULT`, used as the Frames default (fresh settings only — a persisted value
still wins, so an existing 120 is untouched) and at the scratch call site in place of the
inline `ceil`. Below it the spinbox turns amber and its tooltip states the arithmetic for the
current value (`60 frames give 36 central`) plus the consequence. Not blocked: a deliberately
short capture is still allowed, just marked.

Flagged, not changed: `_sig_can_commit()` still accepts any window of ≥2 frames, so a Space
force-advance can commit a tiny capture — the likeliest origin of the short capture in the v3
corpus. The live count now warns before the press, and hard-blocking an override is a
separate decision.

Verified offscreen. `_central_frame_count()` is cross-checked against
`pimd_features.central_frames()` directly for 0/2/10/60/100/120 → 0/2/6/36/60/72, with the
old default (60 → 36 → `short`) and the new one (100 → 60 → `ok`) asserted as the defect and
its fix. The Frames warning is checked at 60/99/100/120 for both the style and the tooltip
numbers. The label walk asserts `(N central)` tracks the buffer and that the colour crosses
exactly at `MIN_CENTRAL_FRAMES` — observed yellow at 1/120 (1 central), blue at 100/120
(60 central). All six harnesses pass under `-W error::DeprecationWarning`; longest label is
still 36 characters against the 52 ceiling. **Not yet run on the bench** — the check there is
that a 120-frame cycle reads `(72 central)` when full and saves `quality=ok`, and a 60-frame
one stays yellow at `ACQUIRED` and saves `short`. (2026-07-28)

---

### findings — one capture in the v3 corpus is stamped 'short'; the Frames default caused it

Quality-flag census of the two tracked corpora, prompted by the v1.57 investigation:

| corpus | rows | quality |
|---|---|---|
| `gui_signatures_targets_v1_20260723.csv` | 4158 | 2898 ok, 1260 noisy, **0 short** |
| `gui_signatures_tragets_v3_20260727_171813.csv` | 819 | 756 ok, **63 short** |

63 rows is exactly one capture at 63 cells, so **one of that session's 13 captures** carries
the flag. The v1 corpus has none, so whatever produced it is new to the v3 session.

Two candidate causes, not separated: the Frames default of 60 (which cannot clear
`MIN_CENTRAL_FRAMES` at all — see the v1.57 entry), or a Space force-advance committing a
partly-filled window, which `_sig_can_commit()` permits down to 2 frames. Either way the flag
was only discoverable after the save; v1.57 surfaces the count live so the next one is
visible before committing.

Noted, not acted on: that corpus filename misspells "targets" as **`tragets`**. It is
captured data carrying provenance, so renaming is the owner's call, not a tidy-up.
(2026-07-28)

---

### USAGE.md — v1.21 — classviz v1.56 → v1.57

§5's Training paragraph gains the central-60% trim: what it discards, what `(N central)`
means and why it is the pre-commit warning, the yellow→blue→green ladder, and the Frames
default of 100 with the reason for the amber warning below it. §1 diagram version follows.
(2026-07-28)

---

### src/pimd_classviz.py — v1.56 — Training A/B labels name the gate holding each phase up

The two await phases each rendered one fixed string — `WAITING for target…` and `ACQUIRED
target — captured, remove now` — so an operator watching a 30 s countdown had no way to tell
whether the rig was still settling, or settled and simply short of Detect. Those are
different problems with different fixes (stop touching the bench / move the target closer),
and nothing on screen distinguished them. Between "place target now" and "profiling target"
there was no visible state at all.

**A** now pairs the live measurement with whichever gate is currently blocking the
transition, and **B** keeps the instruction plus either the guard countdown or the frame
count:

| state | A | B |
|---|---|---|
| leading air, unsettled | `SETTLING air — σ0.512 > 0.400` | `Acquiring leading air — waiting for settle` |
| air ready | `ACQUIRED air — 20/20 (rolling)` | `Press Space` |
| awaiting target, settled | `WAITING target — Δ0.028 < 0.500` | `Place target now — need Δ≥0.50 mV — 30s` |
| awaiting target, disturbed | `MOVING — σ19.153 > 0.400` | as above |
| profiling | `COLLECTING target — 47/120 (73 left)` | `Profiling target — 47/120 frames` |
| awaiting removal, untouched | `HOLDING target — lift it to release` | `Remove target now — 30s` |
| awaiting removal, disturbed | `MOVING — σ19.682 > 0.400` | as above |
| awaiting removal, re-settled short | `MOVED — Δ0.119 < 0.500` | as above |

`HOLDING target` is the v1.54 transient latch made visible: until something physically moves,
removal cannot fire whatever the magnitude reads, and the label now says so rather than
implying the app is waiting on a threshold. `_update_sig_train_indicator()` takes the
deviation alongside the settle value; `_sig_train_ingest()` passes what it already computed,
and it stays `None` while unsettled, which is what selects the σ form over the Δ form. The
settle value falls back to measuring itself when a phase-transition call site does not supply
one — otherwise every state change flashed a placeholder, which is the failure being fixed.

Two wording decisions worth recording. `await_target`'s disturbed state is `MOVING`, not
`SETTLING`: the collecting phases already use `SETTLING <subject>` and a bare `SETTLING`
read as the same state. And the filling note is `waiting for settle`, not "window cleared" —
the status is identical on a first fill, where nothing was cleared.

Verified offscreen by walking a synthetic cycle through `_sig_train_ingest()` frame by frame
and asserting the label at each of ten states an operator can sit in, including that A names
σ-vs-Settle while unsettled and Δ-vs-Detect once settled, and that the manual-placement
wording survives. Longest label rendered is 36 characters, checked against a 52-character
ceiling so neither label can widen the Training group. One fixture bug found and fixed on the
way (the synthetic clock outran the wall-clock guard deadline, aborting the cycle mid-walk),
which is why the walk now asserts the phase after locking rather than trusting it.
(2026-07-28)

---

### USAGE.md — v1.20 — classviz v1.55 → v1.56

§5's Training paragraph rewritten around the A/B status text: each state now names the gate
holding it up, with the actual label strings quoted, since the point of the change is that
the operator reads these rather than guesses. §1 diagram version follows. (2026-07-28)

---

### src/pimd_classviz.py — v1.55 — lift the v1.41 manual latch on removal auto-detect

v1.41 blocked removal auto-detect whenever placement had been forced by Space. That was
correct for the removal rule of the day: it was the placement comparison inverted, so for a
target that had never cleared Detect going on, "|Δ| below Detect" was already true on the
first settled frame of `await_remove` and the cycle skipped the removal wait outright (the
v1.40 field failure). The latch was a guard on a test that could fire on arrival.

v1.54 replaced that test — removal now needs a settle-loss transient **and** a departure
from the target snapshot — and neither half can be satisfied on arrival, so the failure the
latch existed to prevent is no longer reachable. The block is lifted: a Space-forced
placement gets removal auto-detect like any other. `_sig_target_manual` is *not* retired; it
still keeps Space permitted through the rest of that cycle without the override checkbox,
which is the fallback for a target too weak for either direction to fire. The `await_remove`
instruction reads `Remove target — auto, or Space` for a manual placement rather than
promising auto-detect alone, since that is the case most likely to need the fallback.

Verified offscreen, two new cases beside the four from v1.54. A manual placement followed by
a real removal (transient, then re-settle at air) now advances to `air_trail` where it
previously stalled — and, at the top of that case, `await_remove` is asserted still current
on arrival, which is the v1.40 regression under test. A **weak target** case covers the
other side: 0.2 mV against a 0.5 mV Detect, transient seen and latch armed, removal
correctly *declines* at 0.215 mV of departure and falls through to Space. The v1.54 cases
are unchanged and still pass, including the decisive one (1.66 mV of drift-driven deviation
with no transient does not advance). **Not yet run on the bench.** (2026-07-28)

---

### USAGE.md — v1.19 — classviz v1.54 → v1.55

§5's Training paragraph gains the lifted latch: a Space-forced placement now auto-detects
removal too, with Space still permitted as the fallback and the reason why (a target too
weak to clear Detect going on will not clear it coming off). §1 diagram version follows.
(2026-07-28)

---

### src/pimd_classviz.py — v1.54 — FIX removal auto-detect; Air age against the cycle budget

Acts on the concern flagged (deliberately unfixed) at v1.52, now confirmed on the bench:
the Air-age marker does go red during `await_remove`, so the removal test was being asked
to resolve a target against more accumulated drift than target.

**Removal auto-detect reworked.** It tested whether the signal had come back to within
Detect of the **leading air** — a reference by then a whole target-collection window older.
DESIGN §17.10 measured that as unable to work: at ~50 µV/s a 150 s-old air reference reads
5.2 mV where a spanner @60 mm reads 2.8 mV, so *removing the object makes |Δ| go up*. The
new test has two halves, and both are load-bearing:

- **A transient must have happened.** Lifting the object unsettles the signal before it
  re-settles elsewhere; drift never does. `_sig_removal_armed` latches a settle-loss seen
  during `await_remove` and the transition requires it. This is what separates "target
  lifted" from "reference aged", and it is why a magnitude test alone was not enough.
- **Then a departure from a *fresh* reference.** New `_current_dev_from_target()` compares
  the settle window against `_sig_target`, the snapshot taken in `_sig_finish_target()`
  moments before `await_remove` began — seconds old, not minutes. Removal fires on
  dev > Detect, so both gated phases now share one shape of test (settled, and |Δ| from a
  fresh reference above Detect), each against its own reference.

The v1.41 manual latch is untouched: a Space-forced placement still requires Space to leave
`await_remove`. It could now arguably be lifted, since the target snapshot exists however
the phase was entered — left alone as a separate decision.

**Air age now measures the cycle budget, not the drift budget.** The old limit,
Detect / 0.05 mV/s, was 10 s at Detect 0.5 — red long before a 120-frame target window could
finish, so it said nothing. That number described whether a magnitude test against the
frozen reference could still work; with removal no longer using that reference, nothing
gates on its age and the useful question became "is this cycle dragging".
`_sig_cycle_budget_s()` returns what one healthy cycle owes after the lock — two collecting
windows plus two 30 s guards — using the **measured** sweep rate (`_fps_hz`) where there is
one, because a 63-cell profile sweeps slower than a 45-cell one and a hardcoded period would
be wrong on half the profiles. 132 s at 120 frames and ~3.3 Hz. `AIR_DRIFT_MV_PER_S` is
removed rather than left dead; the figure and its §17.2/§17.10 citation live in the new
method's docstring.

The Detect gauge gained a third mode to match (`_sig_dev_is_gated()` → `_sig_dev_mode()`,
returning `air` / `target` / `wander`), so the unit column reads `mV vs target` through
`await_remove` and the gauge always names the reference it is showing. Green still means
"the thing you are waiting for", which is now a crossing *above* Detect in both gated
phases.

Verified offscreen, five state-machine cases driven through `_sig_train_ingest()` frame by
frame. The decisive one: a target sitting still under 50 µV/s of drift reaches **1.66 mV of
deviation from its own target reference — well past a 0.5 mV Detect — and the cycle does not
advance**, because no transient occurred. A magnitude-only fix would have false-fired there.
Also covered: a real removal (unsettle → re-settle at air) advances to `air_trail`; a knock
that arms the latch but leaves the target in place does not advance; the v1.41 manual latch
still blocks auto-advance; and `_sig_finish_target()` clears a stale arm so it cannot carry
into the next cycle. Gauge-side: all three Detect modes assert the right source, unit text
and value across a full phase walk, and the Air-age limit tracks Frames and the measured
rate.

**Bench-confirmed 2026-07-28**: cycles run through place and remove without operator
intervention, and Air age no longer goes red inside a normal 120-frame cycle. Known
remaining failure mode, unobserved so far: a target removed smoothly enough never to break
the Settle gate will not arm the transient latch, and that cycle times out to Space override
— the same fallback as before, but now this is the specific way it can happen. At the
working Settle of 0.4 mV σ any real movement should trip it. (2026-07-28)

---

### USAGE.md — v1.18 — classviz v1.50 → v1.54

§5 gains a **Trigger Levels** bullet (the five-gauge column, which thresholds are draggable,
and what each of the Detect row's three modes measures — the phase-dependent reference was
the thing that confused a reading on the bench, so it is spelled out) and an **Auto-start**
bullet. §5's Training paragraph corrected: it still described removal as "Δ back below
Detect" against the leading air, which v1.54 replaced — the new wording carries the §17.10
reason, since the old rule looks more sensible than it is. §1 diagram version follows.
(2026-07-28)

---

### findings — air wander at the v3 operating point: 0.2–0.3 mV, and the v1.52 fix confirmed

Bench check of the classviz v1.52 Detect gauge, `cal_63_air_bat_v3`, pack at **21.59 V**:
clean air with no cycle running reads **0.2–0.3 mV steady** on the `mV wander` reading, and
does not climb. That closes the loop on the v1.52 diagnosis — the same rig and the same
setting read ~10 mV and creeping under v1.51, which was a Training air reference roughly
200 s old being displayed as a live deviation, not the detector.

Two things worth recording beyond the fix.

**The Detect margin is wider than assumed.** 0.2–0.3 mV against the working Detect of
0.5 mV is a factor of ~2, and better than the ~0.8 mV predicted from the §17.2 50 µV/s drift
rate over a 50-frame (~16 s) window. Either the settle window in use is shorter than 50
frames, or drift at this operating point is below the §17.2 figure — that figure is a
pre-enclosure number on the §14 re-measurement backlog. Not separated here.

**Pack was at 21.59 V.** §17.10's regulation result — coil drive constant, state of charge
not reaching the operating point — is measured down to 23.05 V, and §12's working floor is
21.0 V. A clean, steady air reading at 21.59 V is consistent with regulation still holding
most of the way to that floor, but **it is not the same measurement**: §17.10's evidence is
the direction of per-band delay shift under a falling pack, and air wander is drift plus
noise over one window. It does not extend the regulated-window result on its own. The
outstanding check remains the unmeasured pulse-instant rail sag (§12). (2026-07-28)

---

### src/data/targets/targets_v3.csv — registry — solder stick added

New row `Sn_Pb_solder_stick_01` — solder stick, `rod`, 145 × 8 × 8 mm, solid (`wall_thickness_mm`
0), `closed_loop` n, `magnet_test` none, `material_class` solder_sn_pb. **Mass 56 g, weighed**
— it was first entered as a 62 g geometric estimate (a ø8 × 145 cylinder at the
`pimd_target_check.py` table density of 8.5 g/cm³) and that placeholder is now replaced by
the measured value.

Noted, not acted on: 56 g over the 7.288 cm³ cylinder volume implies **7.68 g/cm³**, against
the 8.5 the registry's density table carries for `solder_sn_pb` — which is what the
mass-plausibility check tests against. It stays well inside the check (the solid *bounding
box* at 8.5 is 78.9 g, and the row passes with 0 errors), so nothing is flagged. The gap is
about 10 %, consistent with a higher-tin alloy than Sn60/Pb40 — pure tin is 7.31, Sn96/Ag
7.4 — or with a stick slightly under its nominal 8 mm. Alloy is unconfirmed; the registry
records the object as `solder_sn_pb` on the owner's identification, and the measured mass
governs regardless. (2026-07-28)

---

### src/pimd_classviz.py — v1.53 — auto-start at launch; gauge row spacing; np.bool_ warning

**Auto-start.** The app now connects and runs the remembered profile on launch, instead of
waiting for Connect and then Load & Run — two clicks that were the invariable opening move
of every session. `_autostart()` fires from a `QTimer.singleShot(0, …)` in the constructor,
so the window is up and the event loop running before any serial I/O, then defers the
profile send by `AUTOSTART_PROFILE_MS` (600 ms) so the `D`/`Q`/`G` burst does not race the
`E`/`V`/`Q4` connect handshake — the same beat an operator leaves between the two clicks.
Nothing is forced: no remembered port, a port that will not open, or no remembered profile
each leave the app sitting exactly as it did before, with the reason in the status bar and
the Connect button reddened by the existing `connect_port()` path.
`_autostart_run_profile()` re-checks the port because the operator can disconnect inside the
delay window.

**Gauge row spacing.** The gauge column's row spacing goes 1 px → 8 px. With the v1.52
two-line rows (name over readout) against a boxed plot, 1 px ran the five rows together into
a single block and left the eye hunting for the boundaries. Analysis row 1 opens at 320 px
to fit five 46 px rows plus the new gaps and the group title.

**`np.bool_` DeprecationWarning.** `_set_gauge()` computed `has_value` as the bare
`np.isfinite(value)` result — an `np.bool_`, not a `bool` — and fed it through to
`QGraphicsItem.setVisible()`, which takes it as an *index*. NumPy warns on that, and at the
~30 Hz redraw rate across five gauges it was thousands of `DeprecationWarning` lines per
session on the console. Wrapped in `bool()`. A scan of every `setVisible`/`setEnabled`/
`setChecked` call site for other numpy-bool leaks found none.

**Also fixes a defect in v1.52 (never committed, caught on the render).** The Detect gauge
painted its verdict `good_above=True` in both modes, so quiet air — 0.049 mV of wander
against a 1.0 mV Detect, the *ideal* state — rendered red. The verdict direction has to
follow the mode, because "good" does: gated, dev at or above Detect means the target
registered; in wander mode the air moving *less* than Detect is what you want, because that
is the trigger level clearing the noise floor, which is the entire reason to look at the
row. Now `good_above=gated`.

Verified offscreen: the v1.52 suite re-run under `-W error::DeprecationWarning` passes, which
is the warning fix under test rather than eyeballed; new assertions cover all four
verdict-direction cases (quiet air green, air past Detect red, gated dev under Detect red,
gated dev over Detect green); a new autostart suite covers no-port, unopenable-port,
disconnected-inside-the-delay and no-saved-profile degradation plus the happy path, asserting
the exact command sequence `E,V,Q4` then `E, D…, Q5, G` onto `cal_63_air_bat_v3`. Both gauge
columns re-rendered and inspected. **Auto-start is not yet exercised against the board** —
the 600 ms handshake gap is reasoned from the manual click cadence, not measured; if the
first frames arrive on the wrong profile, that constant is the thing to raise. (2026-07-28)

---

### src/pimd_classviz.py — v1.52 — FIX Detect gauge read a stale air reference; Air age gauge

**Bench report:** the v1.51 Detect gauge read ~10 mV in clean air with no target and crept
steadily higher, against a Detect setting of 0.5 mV that has always worked. Settle read
0.2 mV σ at the same time. Diagnosed as a display fault, not a detector change.

`_current_dev_from_air()` measures mean per-channel |Δ| against `_sig_air_ref`, the leading
air a Training cycle locked. That reference is cleared on Start Training, Stop and
timeout-abort — but **`_sig_finish_air_trail()` never cleared it**, so after a normal cycle
completion it survived into the next cycle's `air_lead` and kept ageing. Harmless while
nothing read it: the state machine consults dev only in `await_target`/`await_remove`, both
entered from `_sig_lock_leading_air()` and so always against a fresh lock. v1.51 then put
the number on screen and called it every redraw regardless of phase.

DESIGN §17.10 already quantifies the result: at the §17.2 ~50 µV/s rate an air reference
accumulates 0.5 mV/cell at 10 s, 3.0 mV at 60 s, 7.5 mV at 150 s. **10 mV ⇒ a reference
about 200 s old.** Settle at 0.2 mV σ corroborates it — the rig is quiet frame to frame, so
that was a slow ramp, not noise. "Sometimes it behaves as previously" fits too: straight
after a Space lock, or after an abort/Stop, the reference is fresh or `None`. Detect 0.5 mV
was never wrong and the placement path is unchanged.

Three fixes. **(1)** `_sig_finish_air_trail()` now clears `_sig_air_ref` — the reference dies
with its cycle rather than being routed around. **(2)** The Detect gauge picks its source by
phase (`_sig_dev_is_gated()`): in `await_target`/`await_remove` it shows
`_current_dev_from_air()`, the very number being tested; everywhere else it shows a new
`_current_air_wander_mv()` — mean per-channel |Δ| between the current settle window and the
one immediately before it. Same reduction and units, so it is directly comparable to the
Detect setting, but it reads the drift *rate* rather than an accumulating total: a planted
0.05 mV/s ramp holds steady at ~0.48 mV instead of climbing without limit. The unit text
names which is on screen (`mV vs air` / `mV wander`) — reading "vs air" when nothing was
locked was the whole confusion. `_current_dev_from_air()` is deliberately **not** refactored
into a shared window helper: it is on the state machine's gating hot path, and a few
duplicated lines are cheaper than touching it. **(3)** New fifth gauge, **Air age**, with
`_sig_air_ref_ts` recorded at the lock. Read-only marker (binding `None` — the limit is
derived, not a setting) at the drift budget `Detect / AIR_DRIFT_MV_PER_S`, the age at which
thermal drift alone equals the Detect threshold. New module constant
`AIR_DRIFT_MV_PER_S = 0.05` carries the §17.2/§17.10 citation so the figure is auditable.

**Flagged, not changed.** `_sig_train_ingest()` detects target *removal* by the same
magnitude test against the leading-air reference, which by then is a whole
target-collection window old. §17.10 measured this head-on — "a spanner @60 mm reads |Δ|
2.8 mV while 150 s of drift reads 5.2 mV, so removing the object makes |Δ| go up. No
magnitude test against a frozen reference can detect removal, which is why auto-release was
abandoned by direction." That is a plausible mechanism for removal timeouts and it predates
v1.51 (v1.34+). Left alone: the 30 s guard and Space override are the existing fallback, and
this wants a bench observation before a design change. The Air-age gauge is what will show
whether it is actually biting — if the age marker is red before the target comes off, the
removal test cannot succeed on that cycle.

Layout, both gauge columns: the numeric readout moved from its own column right of the bar
to a second line under the row label, which gives every bar ~110 px back (~130 px → ~230 px
at a 300 px column) and stops the tick labels colliding. One uniform left-block width still
keeps all the bars starting at the same x, now measured on the whole two-line block rather
than the label alone; the separate unit-width pass is gone since nothing follows the bar.
Analysis row 1 opens at 300 px for the fifth row.

Verified offscreen (no board): flat air reads 0.04 mV wander and stays there; a planted
0.05 mV/s ramp reads 0.48 mV steady across three window-lengths rather than accumulating —
the reported regression, inverted into a test; the unit text and value switch to
`_current_dev_from_air()` in exactly `await_target`/`await_remove` across a full phase walk;
a planted +4 mV step reads 4.008 mV against the locked reference; Air age reads its age with
the marker tracking `Detect/0.05` and flipping green/red about it; `_sig_finish_air_trail()`
leaves both reference and timestamp `None` and Air age at `—`; all v1.51 checks (drag
write-back, clamping, spinbox→marker, Family Plane values) still pass. Both columns rendered
and inspected. **Not yet run on the bench** — item 7 of the plan (clean air must read
~0.8 mV steady, not 10 and climbing) is the confirmation. (2026-07-28)

---

### src/pimd_classviz.py — v1.51 — Analysis-tab Trigger Levels gauges (draggable thresholds)

New **Trigger Levels** column on the Analysis tab, leftmost in the top-right pane
(`row1_split`, left of Band Mean vs Time): four bar gauges — **Settle · Detect · Amp ·
SNR** — each with a dashed threshold marker you can **drag** to set the underlying
spinbox. The Training group's two auto-detect gates were previously set blind. Their
metrics drive the state machine every frame but were never plotted; the only visible
number was a settle reading smuggled into the status-label text (`SETTLING air — 0.412
mV`). Picking a level meant guessing, running a cycle, and watching it stall or
false-trigger. Now the bar shows the live quantity, the marker shows the gate, and the
gate is dragged to wherever the noise stops.

Settle and Detect read the *exact* helpers `_sig_train_ingest()` gates on —
`_current_settle_mv()` (Stats-tab window) and `_current_dev_from_air()` — so the bar
crossing the marker and the cycle advancing are one event rather than two things that
ought to agree. That mattered: a straight copy of the Family Plane column would have been
wrong twice over. Its `Settled` gauge uses the *Shape* window (`sp_shape_win_n`, 15
frames), not the Stats window (50) the training gate applies, so the displayed number
would not have been the gated number; and its `Amp ‖Δ‖₂` is a different quantity from the
mean per-channel |Δ| that Detect compares against, so a Detect marker on the Amp bar
would have been numerically meaningless. Hence Detect is its own row and the
Family-Plane-only `Air age` row is dropped.

Amp and SNR are context, not gates, and are measured against the Training cycle's **locked
leading air** (`_sig_air_ref`) over the Stats window — new `_analysis_gauge_features()`,
via `_shape_live_window(ref=, n_win=)`, which gained those two optional arguments and
defaults to its previous behaviour for every existing caller. Without that they would have
come from `_shape_live`, whose reference is the Family Plane's own and is *rolling* unless
Space was pressed on that tab, so both would have sat at ~0 here. They still fall back to
`_shape_live` before a cycle locks a reference. Their markers move
`sp_sig_q_amp_mv` (log₁₀ axis, so a dragged position goes back through `10**x`) and
`sp_shape_gate`.

Implementation is a shared column, not a clone: `_build_shape_gauges_dock` /
`_shape_set_gauge` were generalised into `_build_gauge_column(specs, store, value_w)` /
`_set_gauge(store, key, …)`, and the Family Plane keeps its four gauges as read-only specs
(`binding=None`). A spec's binding is `(spinbox_attr, to_axis, from_axis)` — the spinbox is
named rather than passed because the Analysis column is built before the Family Plane tab
exists, so `sp_shape_gate` cannot be resolved at build time. Two guards keep a drag from
fighting its own redraw: `_set_gauge` skips repositioning a line while `gate.moving`, and
`_gauge_marker_drag` suppresses the re-render triggered by the spinbox's own
`valueChanged`. Dragged values are clamped to the spinbox range, rounded to its decimals,
and the line is snapped to where the spinbox actually landed; `setBounds()` keeps a line on
its own axis. A draggable gate stays visible with no reading (Detect has none until a cycle
locks air — exactly when you want to pre-position it), while a read-only gate still hides
with its value, so Family Plane behaviour is unchanged.

Bar axes here are anchored on the **threshold** (`_gauge_hi`: `max(2×thr, 1.25×value,
0.2)`), not on the reading the way the Family Plane's settle gauge is (`max(value*2,
1.0)`) — a value-scaled axis slides the marker around under the cursor, and here the marker
is the control being grabbed.

Cosmetic, applied to both columns: row labels and unit suffixes are each given one uniform
width, so every bar starts and ends at the same x. Per-row minimums could not do this — the
widest name shortened its own bar and a unit-less row (`SNR`) ran 46 px longer than its
neighbours. Analysis row 1 now opens at 260 px tall rather than 220 (four 46 px gauge rows
plus the group title need ~210; at 220 they opened squashed to their 26 px minimum), and the
row-1 splitter sizes persist as `analysis_row1_split_sizes` alongside the existing left-split
entry.

Verified offscreen (no board) against synthetic frames: Settle matches
`_current_settle_mv()` to 3 d.p.; Detect stays `—` with no `_sig_air_ref` and then tracks a
planted 3.0 mV step; verdict colours flip green/red about the marker; drags write back
through both transforms (Amp to `10**pos`, not the raw log) and clamp at the spinbox
minimum and the axis bound; typing into `sp_sig_settle_mv` / `sp_shape_gate` moves the
marker the same frame; and the Family Plane column still renders and updates. Not yet
exercised on the bench — the coincidence of Detect crossing its marker with the cycle
advancing to `ACQUIRED target` is the check to make there. (2026-07-28)

---

### src/pimd_target_check.py — v4 — CLI requires `-f`; `wall_thickness_mm` 0 = solid

The CLI no longer defaults its registry path: `-f/--file` is now required (`--registry`
kept as an alias), so `python pimd_target_check.py` with no arguments is a usage error
instead of a silent check of whichever file the default happened to name. With several
registry versions on disk that default had become a trap — it still pointed at
`targets_v1.csv` while the live registry had moved to v3, so a clean run said nothing
about the file actually in use. Relative paths resolve against the current working
directory as usual (`-f data/targets/targets_v3.csv` from `src/`), and the run now prints
the absolute path of the registry it loaded before the table.

`wall_thickness_mm` gained an explicit "solid / not applicable" value of **0**, replacing
the `na` the v3 registry carried (which the tool rejected outright as unparseable) and the
empty cell v1 used. Both legacy spellings are still accepted and normalise to `0.0`, so
older registry files keep loading, and the column is now always a float — `Target.
wall_thickness_mm` is never `None`. The shape-mismatch warning fires on `> 0` rather than
"is set", so a solid `plate`/`disc`/`bolt` no longer trips it just for carrying the
sentinel; a negative wall is a new error.

`DEFAULT_REGISTRY_PATH` repointed to `targets_v3.csv`. It remains the single source of
truth for the *library* default, so `pimd_classviz.py` (`TARGETS_REGISTRY_PATH`),
`pimd_features.py` (`--registry` default) and `pimd_corpus_check.py` (no-arg
`load_targets()`) all follow it onto v3 unchanged — only the CLI lost its default.

Verified: all four PC tools `py_compile` clean; `-f` missing exits 2 with usage; v3 loads
26 targets / 0 errors / 2 pre-existing warnings (`ferrite_toroid_01` closed_loop, and
`Fe_heavy_pully`'s 66 mm wall on a `disc`); v1 still loads clean with its 12 blank walls
normalised to `0.0`; planted `abc` and `-2` walls both error. Note for downstream:
`pimd_features.py:745` writes `wall_thickness_mm` as `''` when `None`, which can no longer
happen — solid targets will now appear as `0` in newly built corpus CSVs rather than
blank. (2026-07-26)

---

### src/data/targets/targets_v3.csv — registry v3 — re-exported from UTF-7, data fixes

New registry revision (solder roll changed; rocks, quartz piece and water bottle added;
existing rows reviewed). The LibreOffice export had been written with the character set
left on **Unicode (UTF-7)**, so every `_`, `-`, `#`, `"`, `—` and `>=` in the file arrived
as a `+AF8-`-style modified-base64 escape — `targets+AF8-v3`, `dim+AF8-a +AD4APQ-
dim+AF8-b`. Decoded in place with `iconv -f UTF-7 -t UTF-8`; row count and content
otherwise unchanged. LibreOffice remembers the last charset used, so the export dialog
needs setting back to UTF-8 on the next Save As or this recurs.

Data fixes in the same pass: header typos (`reviwed`, `measuremnents`) and a duplicated
`dim_a >= dim_b >= dim_c.` cell on the units line; `Quartz_piece_01` had a shifted row —
`dim_c_mm` empty with its `40` sitting in `wall_thickness_mm` — corrected to
`60,50,40`; `material_class` for `Quartz_piece_01` and `Sandstone_rock_01` set from `?`
to `mineral`. All 37 lines now parse to exactly 13 fields and every row satisfies the
header's sorted-bounding-box invariant.

`wall_thickness_mm` migrated from `na` to `0` for the 15 solid targets, matching the
sentinel `pimd_target_check.py` v4 now understands; the header comment block documents
`0 = solid / not applicable`.

`Fe_heavy_pully` reclassified `disc` → `ring`, which was the last registry warning. Its
66 mm `wall_thickness_mm` was flagged as being set on a shape the registry treats as
solid, but the measurement is right — the pulley has a real bore and 66 is the radial
wall, `(150 − 18) / 2`. So the row was a shape misclassification, not a bad number: a
shape carrying a radial wall is a `ring`. That matches the three existing `ring` rows
(`Cu_Zn_brass_gear_01`, `ferrite_toroid_01`, `Fe_SS_shackle_01`), which all pair a radial
wall with `closed_loop=y`, and the mass agrees (a steel ring OD 150 / ID 18 × 28 is
3829 g against 3700 g measured). Dims were never at issue — `dim_a = dim_b = 150`,
`dim_c = 28` is the correct bounding box, same convention as the pipe rows.

Left alone deliberately: `Fe_heavy_pully` misspells "pulley" in both `short_name` and
`target_id`, and ids are stable by the registry's own rule — renaming one would orphan
any capture referencing it. Flagged, not changed: `closed_loop=y` is kept on the pulley,
which reads the flag as "supports a large circulating eddy-current path" rather than the
header's written rule (a bore comparable to object size; an 18 mm bore in a 150 mm body
doesn't meet it). Under that broader reading `Fe_Cast_iron_trivet_01` and `Fe_SS_disc_01`
are arguably mislabelled `n` and the header wording needs updating — a registry-wide
semantics decision left for a separate pass. (2026-07-26)

---

### repo — `cal_63_air_v2` retired; `cal_63_air_bat_v3` is the sole operating profile

`cal_63_air_v2.json` untracked (`git rm --cached`, still on disk) and added to the superseded
list in `.gitignore`, restoring the one-tracked-profile-at-a-time rule from the 2026-07-23
hygiene pass. From here everything runs under battery on `cal_63_air_bat_v3` — v2 is the
previous supply epoch and is no longer a thing new work should be anchored to.

Nothing in the code loads a profile by name, so this is a tracking change only: delaycal's
Import Profile and Compare Profiles both scan `data/profiles/*.json` off disk, so v2 stays
available as a comparison reference for as long as the file is kept. One stale reference
corrected — `pimd_shape.py`'s `default_band_ranges()` docstring named v2 as "the 7-band
operating profile"; the band plan is common to v2 and v3, so the derived early/mid/late split
is unchanged and only the naming needed updating (comment only, no version bump).

Note for corpus work: `gui_signatures_targets_v1_20260723.csv` was captured under v2, so the
only tracked profile no longer matches the only corpus on disk. That is expected across an
epoch boundary and is what the `(profile_name, profile_sha8)` guard exists to catch, but it
does mean a v3 corpus has to be recaptured before the two can be worked with together.
(2026-07-26)

---

### USAGE.md — v1.17 — delaycal v1.28 → v1.29

§4's intent no longer claims exports land at a fixed `cal_<ts>.json` path. New **Export
Profile** bullet: the filename sets the profile's `name`, and `name` — not the filename —
is what corpora record as `profile_name` and what the cross-epoch guard reports, so naming
the file names the epoch. Lists what the generated notes contain and says plainly that the
operator's own conditions (thermal state, soak time, pack voltage) have to be added there or
the calibration isn't reproducible. The Auto Nudge bullet now says its auto-save is
unattended and timestamp-named, with Export Profile as the follow-up step; the Import bullet
notes that notes and filename carry forward. §1 diagram: delaycal v1.28 → v1.29. (2026-07-26)

---

### src/pimd_delaycal.py — v1.29 — profile save dialog and auto-generated notes

Locking `cal_63_air_bat_v3` exposed two gaps in the export path. **Filename:** exports went
silently to `PROFILES_DIR/cal_<sweep timestamp>.json` with `name` set to the same stamp, so
every locked profile had to be renamed by hand afterwards — and renaming the *file* left the
`name` field, which is what `pimd_features.py` records as `profile_name` in every corpus row
and what the cross-epoch guard reports, still holding the stamp. Export Profile now opens a
save dialog (`.json` appended if omitted) and takes `name` from the basename chosen, so the
profile identifies itself by the name it is referred to by. The dialog is pre-filled from the
last save, else the imported profile's filename, else the timestamp.

**Notes:** profiles carried no record of the sweep that produced them. `_compose_notes()`
generates a `notes` field — sweep start → end and duration, sweep parameters (start, coarse
step, fine step, max delay, averages N, signal detect), Auto Nudge parameters (threshold,
step, soak, max iter, mode, std-dev N), the Auto Nudge outcome line, and the geometry — shown
in an editable multi-line dialog before writing so operator conditions (thermal state, soak
time, pack voltage) can be added. Notes and delays with no sweep behind them say so rather
than implying a run. **Carry-forward:** `_import_profile()` keeps the source profile's `notes`
and appends them attributed (`Carried forward from <name>: …`), so the v1/v2-style derivation
rationale survives an epoch change instead of being retyped; since USAGE §4 makes Import
Profile the standard start of a recalibration, this is the normal path.

`_build_profile()` gains optional `name`/`notes`; called bare (Compare tab, thermal, Auto
Nudge) it behaves exactly as before and emits no `notes` key. Field order is `name, notes,
averages, bands`, matching the hand-written v1/v2 profiles. `export_profile()` gains
`interactive`: the Auto Nudge completion save passes `interactive=False` and keeps the old
unattended timestamped behaviour — a finished long run must not block on a modal dialog —
and logs a pointer to Export Profile for the named save. The Export Profile button is
connected through a lambda because `clicked()` would otherwise pass `checked` into
`interactive`.

Exercised headless (offscreen Qt) against the real profiles: import of `cal_63_air_v2`
carries its 641-character notes forward attributed; a simulated completed sweep renders the
timestamp/duration line; interactive export writes the chosen basename into `name` with
operator text appended; both cancel paths (file dialog, notes dialog) write nothing;
`_build_profile()` bare still returns the three original keys. (2026-07-26)

---

### src/data/profiles/cal_63_air_bat_v3.json — v3 — new locked profile: battery supply epoch

New epoch **v3**, marking the move from bench PSU to the 6S 16650 battery pack. Locked
profile `src/data/profiles/cal_63_air_bat_v3.json`.

**Band plan is unchanged from `cal_63_air_v2`** — 7 bands (9 → 100 µs), 63 cells, verified
band for band. **The threshold ladder is not:** it moves in one position, to
4.9 / 4.8 / **4.75** / 4.4 / 4.2 / 3.8 / 2.4 / 1.5 / 0.5 V against v2's 4.70 in third place.
The 4.70 column started misbehaving after ~30 minutes in classviz, so the profile was
re-swept with that step raised. Of the 4.75/4.35/3.70 ladder trialled on 2026-07-24 only the
4.75 step is adopted — 4.40 and 3.80 keep their original values, having come back clean under
battery power. The two are unrelated observations: that trial's 4.40/3.80 elevation was
supply-borne (see the §14.7 entry below), this 4.75 move is separate and later.

Delays re-anchored for the supply change: **+40…+144 ns** against v2, band means +90 ns
(100 µs) to +125 ns (30 µs). The third column is the outlier at +40…+72 ns and is **not** a
like-for-like delta — that cell targets a different voltage, so its shift is threshold move
plus supply change, and the two are not separated here.

So this is **both a new calibration epoch and a threshold-geometry change**, which is weaker
than a clean epoch change. Corpora stay in separate files and the
`(profile_name, profile_sha8)` guard still hard-errors across them; cross-epoch comparison is
interpretable for the eight columns whose target voltage is unchanged, but the third column is
not comparable to v2's even feature-wise. That is exactly the §13 feature-level-portability
question the 1.10 consolidation deferred, now live rather than hypothetical.

Calibration conditions: pack 23.5 → 23.35 V, [FILL: thermal state / soak time].

**Revised delaycal parameters** (record these — without them the calibration isn't
reproducible): fine sweep 80 → 40, autonudge threshold 0.5 → 0.3 mV, nudge step 16 → 8 ns,
soak 20 → 40 s, std dev n = 16.

**Profile `name` corrected before locking.** As exported, the internal `name` field carried
the sweep stamp `cal_20260726_122638` rather than the filename — and that field is what
`pimd_features.py` records as `profile_name` in every corpus row, so it is the epoch identity
the cross-epoch guard reports. Set to `cal_63_air_bat_v3` to match the filename and the v1/v2
convention. The underlying trap — delaycal naming every export after the sweep timestamp, so
this needed correcting by hand at every lock — is fixed in delaycal v1.29 above.

**`notes` field written**, matching the v1/v2 convention (v3 as exported had none): epoch and
lock date, fw v4.26, pack voltage across the sweep, the 4.70 → 4.75 change and its reason,
what is and is not unchanged from v2, the re-anchoring figures with the third column called out
as not like-for-like, the sweep and Auto Nudge parameters, the 0.3 mV convergence result, the
grid-step thermal criterion, and the corpus rule. Recorded honestly as unknown: thermal soak
time at lock, and the originating cal-run stamp for the re-sweep.

All three edits (rename, notes, re-sweep) landed before any corpus was captured under v3, so no
existing capture is invalidated by the `profile_sha8` changes they cause. Final `profile_sha8`
for the locked file: **`4a2352d2`**. (2026-07-26)

---

### findings — battery supply lowered the achievable convergence threshold

The headline result of the epoch change. **Convergence at a 0.3 mV autonudge threshold was
never achievable under the bench PSU** — repeated attempts in earlier work failed to converge
at that setting, which is why 0.5 mV became the working value. Under 6S battery power the same
sweep converged at 0.3 mV with **only one cell of 63 requiring a single −8 ns nudge**; the
nudge count would often exceed 10 cells before.

Since the autonudge threshold is effectively a measurement of how tightly a cell can be placed
against the noise, this is a direct quantitative statement about the new supply: the floor
improved enough to make a previously unreachable calibration tolerance routine. Contributing
changes, not separated from one another: 6S pack, heavier cabling, ferrite common-mode chokes
on power and USB, 100 nF across the pack. (2026-07-26)

---

### findings — thermal convergence criterion replaces the thermistor check

The TX damping-resistor thermistor is no longer fitted since the shielded case was built, so
the documented "calibrate once the resistor reaches ~80 °C" precondition (§14.1) can't be
applied. Replaced with a direct measurement of the thing it was a proxy for — successive
calibrations compared cell by cell:

- 15 min after the first calibration: differences up to **−24 ns**, concentrated in the
  long-pulse bands.
- Subsequent runs ~10 min apart: **±8 ns in 6 of 63 cells**, all others zero.

8 ns is the PWM grid step, so those six cells are at the quantisation floor and the rig is as
stable as the hardware can express. Working criterion going forward: **converged when
successive calibrations differ by no more than one grid step, watching the 100 µs band**,
which is consistently the most drift-sensitive. Delaycal's Compare Profiles tab (v1.28) is the
tool for this. (2026-07-26)

---

### findings — the elevated threshold columns were supply-borne (partial §14.7 answer)

The 4.40 V and 3.80 V columns that read ~5× the free-air noise floor on 2026-07-24 (with the
bench PSU failed and an interim pack fitted) are **clean under the v3 battery supply**, which
is why **those two steps** could revert to their original values. Confirmed from a Std Dev
(rolling N) heatmap under v3. This narrows §14.7: that elevation was supply-borne, not
intrinsic to the front end or the 1N4732 clamp.

It does not close §14.7 — the original ~4.45–4.65 V keep-out zone is a separate,
longer-standing observation and is unaffected. Nor does the ladder revert wholesale: the third
step went to 4.75 V in the re-sweep after the 4.70 column misbehaved past ~30 minutes in
classviz, which is a *different* symptom on a different column and is not addressed by this
finding. [FILL: is the 4.70 misbehaviour drift into the ~4.45–4.65 keep-out zone as the rig
warms — i.e. the §14.1 fingerprint — or a fresh mechanism? A Std Dev heatmap on the old 4.70
cell after a 30 min soak would separate them.] (2026-07-26)

---

### USAGE.md — v1.16 — delaycal v1.25 → v1.28

Follows the three delaycal changes below. §4's Sweep sub-bullet now says the fine step is
set in ns down to the 8 ns PWM grid (100 ns default) rather than "0.1 µs"; the Thermal
sub-bullet notes it auto-starts on sweep completion and why that matters; and a new
Compare Profiles sub-bullet covers the tab — what a row is (same band, same intended
target V), the Δ-in-ns colouring against the grid, and the fact that the measured voltages
come from this session's soaks and do not survive a restart. §1 diagram: delaycal v1.25 →
v1.28. (2026-07-26)

---

### src/pimd_delaycal.py — v1.28 — Compare Profiles tab

There was no way to see how a freshly-swept profile differs from an earlier one short of
exporting the JSON and eyeballing it. A second tab now answers the question that actually
matters — **timing convergence**: for every cell the two profiles share, how far apart are
the delays, and does that gap move the measured voltage?

The window's content moved into a `QTabWidget` ("Calibration" / "Compare Profiles"); the
top bar (port, Run, Stop, exports) stays global above the tabs, and splitter/geometry
persistence is untouched. Two selectors list `data/profiles/*.json` plus a
`<current calibration table>` entry backed by `_build_profile()` — so a sweep can be
compared against a reference without exporting first, which is the point of doing this
in-app rather than as a CLI. The list rescans on tab activation.

Cells are matched on `(freq_hz, pulse_us, threshold_v)` — **matched rows only**, so every
row is a genuine like-for-like comparison at the same intended target voltage. Columns:
cell ident, target V, both delays (µs, 3 d.p.), **Δ in ns**, both measured voltages, their
difference in mV, and each profile's error against the intended target. The Δ cell is
coloured against the PWM grid — green within one 8 ns step, yellow within five, red
beyond — reusing the existing palette. A footer carries matched count, mean/RMS/max |Δ|
with the worst cell named, how many cells are measured on both sides, and a named list of
cells present in only one profile. Degenerate cases (unloadable profile, empty current
table, same profile twice, no shared cells) each set an explanatory footer instead of
rendering an empty table. The comparison exports to CSV.

Profiles store only `delays_us` and the intended `threshold_v` — no measured voltage — so
the voltage columns come from a new in-memory `_meas_cache`, keyed on `(freq_hz, pulse_us,
delay_ns)`. Keying on the physical cell rather than on a filename means a saved profile
whose delays match a run that was streamed this session picks its measurements up for
free. `_capture_measurement()` fills it at the end of every THERMAL run and every Auto
Nudge soak, averaging the last `Std dev N` frames rather than the single latest frame so
the value has settled. With v1.27 auto-starting THERMAL, a fresh sweep is measured without
asking. Cells never streamed show `—` on a grey background; nothing is fabricated.

Exercised headless against the real `cal_63_air_v1/v2` profiles: 63 matched cells, deltas
hand-checked against the JSON, mean |Δ| 17.0 ns / max 56 ns; voltage columns populate from
an injected capture and stay `—` where no measurement exists; CSV round-trips; all four
degenerate cases produce their message. (2026-07-26)

---

### src/pimd_delaycal.py — v1.27 — THERMAL auto-starts on sweep completion

A finished sweep left the board idle until THERMAL was pressed by hand, which also meant
the cells were never measured unless someone remembered. `_finish()` now starts thermal
monitoring itself, gated on a new "Auto on completion" checkbox beside the THERMAL button
(default on, persisted as `auto_thermal`). The call sits after the existing button/label
updates so `_start_thermal` gets the last word on button state, and is additionally gated
on the port being open; `_start_thermal`'s own guards on `_fp_pairs`/`_targets_v` are
unchanged. Nothing new goes to the wire — it is the same `E`/`D`/`Q`/`G` sequence the
button has always sent. Beyond saving the keypress this feeds the v1.28 measurement
cache, so every fresh profile arrives with its measured voltages. (2026-07-26)

---

### src/pimd_delaycal.py — v1.26 — fine step in ns, down to the 8 ns grid

The fine sweep step was a µs spinbox with a 0.01 µs floor — 10 ns, which is both off the
8 ns RP2040 PWM grid and unable to reach a single grid step. It is now a `QSpinBox` in ns:
range 8–5000, 8 ns increments, displayed with a ` ns` suffix, matching the existing
`sp_auto_nudge_ns` control. The sweep still carries `_step_size` internally in µs
(converted once in `run_calibration`), so the coarse/fine phase decision, the step-count
rebase after a coarse back-up, and the delay reconstruction are all untouched.

Settings persistence moves to a new `step_ns` key. The old `step_size` key held µs, and
loading `0.10` straight into a ns spinbox would clamp to 8 ns and silently change how a
sweep runs, so `_load_settings` migrates a `step_size` value by ×1000 when `step_ns` is
absent. Verified on the real settings file: a stored `0.08` µs comes back as 80 ns.
(2026-07-26)

---

### USAGE.md — v1.15 — below-gate frames leave no trail

Follows classviz v1.50. §5's SNR-gate sub-bullet now says a below-gate frame leaves no
trail at all rather than a yellow one, and notes that every frame still ages the trail
window along, so holding below-gate fades the trail out. §1 diagram and §5 heading:
classviz v1.49 → v1.50. (2026-07-25)

---

### src/pimd_classviz.py — v1.50 — below-gate frames leave no trail at all

v1.45 coloured trail points by their own SNR, yellow below the gate and green at or
above it. The yellow half is now dropped entirely: **a below-gate frame leaves no mark**,
so the trail draws only the part of a sweep that was worth reading and is green by
construction. Below the gate the unit shape is normalised noise that still wanders the
plane convincingly, and a trail drawn through it says "the target moved this way" about
a frame carrying no target — the same reasoning that already draws below-gate captures
hollow.

Two details that make it behave well on a real sweep. Below-gate frames still enter the
buffer and still **age the trail window along**, so a surviving mark keeps fading as
they push it back and holding off-target fades the whole trail out within `Trail`
frames — rather than freezing the last good pass on screen at full brightness, which is
what re-basing the fade on the drawn subset would have done. And membership, like the
cursor's colour, is decided against the **current** gate rather than the `gated` flag
stamped at ingest, so moving the SNR gate spinbox re-selects the trail already on
screen instead of only affecting later frames.

The live cursor is unchanged: still yellow below the gate, green at or above it. The
gate test moved out of `_shape_live_colour()` into `_shape_above_gate()`, which both
now share. The tab's header comment and the SNR-gate and Trail tooltips follow.

Exercised headless: a sweep of SNR 2→12→1.5 draws 4 of 10 frames, all green, with
alphas reflecting their true age in the window; an all-below-gate buffer draws nothing
while the cursor still shows yellow; an all-above-gate buffer draws every frame; three
good frames followed by five below-gate keep their three marks but at faded alpha; and
sliding the gate 5.0 → 3.0 → 1.0 → 20.0 re-selects 2 → 3 → 4 → 0 spots from an
unchanged buffer. (2026-07-25)

---

### USAGE.md — v1.14 — classviz v1.49 version references

Follows classviz v1.49. Version references only — §1 diagram and the §5 heading. The
custom band range behaves as §5 already described it; nothing user-facing changed.
(2026-07-25)

---

### src/pimd_classviz.py — v1.49 — FIX the custom band pair was lost on restart, clamped by the startup profile's narrower spin range

**Bench report:** the Family Plane's Y custom band range, set to 4–6, comes back as
4–4 after a restart. The settings file was innocent — it held `shape_band_y_hi: 6`
correctly. The restore was destroying it.

The band spinboxes are ranged `0 .. n_bands-1` of the **live** profile. At
`_load_settings()` time the app is still on the built-in startup profile
**CLASSIFY_EP, which has 5 bands**, so the spins are ranged 0..4 and
`setValue(6)` silently clamps to 4 — QSpinBox does that without complaint.
`_rebuild_shape_axes()` later widens the range to 0..6 when the real 7-band profile
arrives, but by then the value is 4 and there is nothing left to widen it back from.
The X pair survived only because 0..2 happens to fit inside 0..4, which is why this
looked like a Y-specific fault.

Worse, and the half that would have kept biting: `_save_settings()` wrote the
**spinbox**, so merely launching the app and quitting — without ever loading the
7-band profile — overwrote the saved 6 with the clamped 4. One clean start was enough
to lose the setting permanently.

The chosen pair is now held as a **preference** in `_shape_band_pref`, separate from
what the spinboxes are currently able to represent. `_load_settings()` records the raw
saved integers (after the `setValue` calls, which fire the range handler and would
otherwise overwrite it with the clamped values); `_rebuild_shape_axes()` re-applies the
preference clamped to whatever the live profile can show, so the pair reappears in full
the moment a wide enough profile lands, and clamping stays display-only; and
`_save_settings()` persists the preference rather than the spinbox. An operator edit
replaces the preference for **that pair only** — the shared range handler is scoped to
the edited pair, so adjusting X can no longer collapse a Y pair that is sitting clamped
under a narrow profile.

Exercised headless against a copy of the real settings file: the Y pair restores to 4–6
once the 7-band profile lands, a save taken from the 5-band startup profile still
writes 4–6, an operator edit to Y updates only Y's preference, a subsequent edit to X
leaves Y's alone, and the whole lot round-trips. (2026-07-25)

---

### USAGE.md — v1.13 — no gridlines on a rank axis

Follows classviz v1.48. §5's **Scale** sub-bullet gains the rank-axis grid rule and the
note that the two zero rails follow the spacing curve. (2026-07-25)

---

### src/pimd_classviz.py — v1.48 — Family Plane: no gridlines on a rank axis; the zero rails follow the spacing curve

**No gridlines on a rank axis (bench request).** Under the other scales a gridline
still marks a real feature value at its real position, so it stays. A rank axis is
ordinal — a grid over it draws a metric that is not there. Applied **per axis**, since
the scales are: rank on Y alone keeps the vertical gridlines. The two zero rails stay
in both cases; they are the family decision boundary, which is exactly the reference
worth keeping when the grid goes.

**The zero rails were in the wrong place under any curve.** They were static
`InfiniteLine`s pinned at *plot* coordinate 0, added at build and never touched — but a
v1.47 spacing curve maps the *feature* value 0 to wherever it falls between the drawn
min and max, which is generally not 0. On the 2026-07-23 corpus with X = custom bands
0–2 the X rail belonged at +0.064 under rank and −0.012 under cube, against the 0.0 it
was drawn at: the boundary line was visibly off, and it was off by more the more
skewed the drawn set. They are now held as attributes and repositioned on every static
redraw. A rail whose axis does not contain 0 (log₁₀ amplitude, distance) stays at a
literal 0 and therefore off-view — transforming an off-domain zero would clamp it to
the edge of the plot and draw a boundary where there is none.

**Colliding tick labels thinned.** The v1.47 ticks are round feature values, evenly
spaced in VALUE but not in position, so a curve that compresses the middle printed
−0.050 / 0.000 / 0.050 on top of each other — worst under rank, which is where the
dead middle collapses hardest. Candidates are now kept greedily by priority rather
than left to right, with 0 going in first so it always survives (it is the boundary and
carries a drawn rail). The minimum separation is measured in **pixels** off the
viewbox, because what collides is label text: a fixed fraction of the domain is either
wasteful on a wide dock or still overlapping on a narrow one. The fraction survives as
the fallback for the first pass, before layout has run.

Exercised headless against the real corpus: gridlines follow each axis's own scale
across the six linear/cube/rank combinations, each rail sits exactly where its axis
draws feature 0, an axis whose domain excludes 0 keeps its rail at a literal 0, and the
rank/rank view renders with readable non-overlapping ticks at both a wide and a narrow
dock size. (2026-07-25)

---

### USAGE.md — v1.12 — the Family Plane's per-axis Scale, and what those axes are

Follows classviz v1.47. §5's Family Plane bullet gains a **Scale** sub-bullet (the four
curves, the range-preserving invariant, ticks staying in real feature units, and why
no log is offered) and an **axis** sub-bullet spelling out what a band-range-mean axis
actually is — mean of the unit shape over a band range, hard-bounded at ±1/√(k·n_delays),
with the family colouring read off the signs of those same two numbers, which is why
the middle of the plane is empty. §1 diagram and §5 heading: classviz v1.46 → v1.47.
(2026-07-25)

---

### src/pimd_classviz.py — v1.47 — Family Plane per-axis Scale combo (expand-ends / rank spacing)

**The problem (bench report).** On the family plane both families pile up against
opposite ends of an axis with a wide void between them, so within-cluster structure is
unreadable. Measured on `src/data/corpora/gui_signatures_targets_v1_20260723.csv`
(66 drawn captures, cluster shares over the 55 gated 7×9 ones), Y = custom bands 4–6,
as a percentage of plot height:

| Y scale | non-ferrous | crossover | ferrous | dead middle |
|---|---|---|---|---|
| linear (was the only option) | 17.8 | 30.7 | 7.8 | **47.9** |
| signed log — measured, NOT shipped | 4.4 | 10.4 | 1.7 | 84.6 |
| cube | 36.7 | 38.5 | 20.0 | 14.9 |
| atanh | 39.9 | 17.4 | 33.8 | 14.3 |
| rank | 50.8 | 32.3 | 20.0 | 6.2 |

Two facts explain the squash, and both are in the maths rather than the drawing.
`band_range_mean()` over 3 of 7 bands is a mean of 27 elements of a **unit-L2**
63-vector, so it cannot exceed ±1/√27 = ±0.1925 — and the corpus reaches 0.160, 83% of
that ceiling. The clusters are pressed against a wall. And the empty middle is not a
data gap: `pimd_shape.family()` is read off the **signs of these same two axes**, so
the void is the decision boundary itself.

**A log axis was asked for and is deliberately not offered.** Log expands near zero and
compresses the extremes; here nothing lives near zero and everything lives at the
extremes, so it is exactly backwards — measured above, it drives the dead middle from
48% to 85%. What this data needs is expansion near the **ends**.

**What shipped.** A `Scale:` combo per axis — Linear, Expand ends (cube), Expand ends
(atanh), Rank — on one invariant that makes the rest tractable: *every curve maps the
drawn captures' [min, max] onto itself, and only the interior spacing changes.* So
auto-range is untouched, switching scales never moves the view, and a tick can always
be labelled with its true feature value. Implemented as normalise to [−1, 1] → curve
(t³, atanh(0.999t)/atanh(0.999), or ECDF position) → denormalise, all four verified
monotone and range-preserving against the real corpus.

The whole thing hangs off one seam: `_shape_plot_value()` already fed the capture
spots, the live cursor, the trail and the selection ring, so applying the curve there
needed no other wiring. The domain comes from the **captures only**, never the live
frame — the cursor moves every frame and folding it in would rescale the plane under
itself several times a second — and it spans every *drawn* capture, below-gate ones
included, since those are on the plot too. `rank` interpolates into the drawn set's
ECDF rather than taking a literal rank, so the live cursor and the selection ring,
neither of which is in that set, still land somewhere consistent; out-of-domain values
clamp to the edge rather than going infinite. The air-mode live-dot pin goes through
the curves as well — 0 maps to itself only when the drawn range happens to be
symmetric, which it generally is not.

The `crossing` axis is excluded and its combo greys out: it owns its ticks (the
profile's pulse ladder plus the `≤pos` / `never` sentinel rails) and a second transform
would leave those labels pointing at the wrong rails.

**Axis labelling.** A non-linear axis gets explicit ticks at round *feature* values
placed through the curve, so a tick reading `-0.150` sits wherever −0.150 actually
landed, and the label names the curve (`custom bands 4–6 [cube]`). That forces
`enableAutoSIPrefix(False)` on those axes: pyqtgraph had latched a `(x0.001)` suffix
that now flatly contradicts full-value tick strings. The standing warning in this file
— that the flag does not clear `autoSIPrefixScale` — still holds and is now recorded
as harmless in this case, because that scale only ever reaches `tickStrings()`, which
explicit ticks bypass. Linear axes get the prefix back.

Both selections persist (`shape_scale_x` / `shape_scale_y`). Colour-by continuous
ranges deliberately keep reading the raw linear value: spacing is an axis concern.

Exercised headless (offscreen Qt) against the real corpus with the live profile set to
`cal_63_air_v2`: every curve monotone in the raw value and range-preserving, the table
above reproduced, every tick sitting at the transformed position of the value it names,
a live frame landing exactly where a capture of the same value lands, out-of-range
values clamping without NaN, `crossing` keeping its sentinel ticks and greying the
combo, the SI prefix off on scaled axes and back on linear ones, and both combos
round-tripping through settings. No bench hardware involved. (2026-07-25)

---

### USAGE.md — v1.11 — a scratch save lands on the plane

Follows classviz v1.46. §5's Family Plane bullet gains a **Save Scratch…** sub-bullet:
the capture is plotted the moment it is written, as a **triangle**, and joins the
Analysis tab's signature list under a `△` prefix alongside any loaded corpus rather
than replacing it. The symbol legend in the mixed-geometry sentence changes star →
triangle. §1 diagram and §5 heading: classviz v1.45 → v1.46. (2026-07-25)

---

### src/pimd_classviz.py — v1.46 — a scratch save plots immediately, as a triangle

Saving a scratch capture wrote it to `src/data/scratch/` and nowhere else. The whole
reason for grabbing one — see where this object lands against the loaded corpus —
therefore needed a **Load signatures…** round trip to answer, and that round trip
would have replaced the reference corpus being compared against.

A save now merges the scratch file back into the shared template store under its own
**`scratch`** source. Its own source, not `loaded` or `editable`: `_merge_template_
list()` replaces a source wholesale, so reusing either would silently drop the corpus
the scratch is being compared against. All three now coexist in one list, and scratch
rows carry a `△` prefix the way editable rows carry `✎`. The whole file is re-read
rather than just the row written — the store is keyed per capture and re-reading is
also the only check that what went to disk reads back as a signature; a file that
cannot be re-read says so in the status bar instead of silently plotting nothing. The
new capture is marked auto-check first, so it lands ticked in the Analysis tab's
overlays too, matching the corpus save path (v1.38). The Family Plane scatter draws
every loaded capture regardless of tick state, so the point appears there either way.

**Scratch objects are triangles.** `_SHAPE_SYMBOLS[(live profile, scratch)]` goes
`star` → `t1`. Foreign-geometry scratch stays a diamond, so the geometry distinction
survives; the mixed-geometry banner and the Save Scratch tooltip name the new symbol.

Exercised headless (offscreen Qt, scratch dir redirected to a temp dir, two saves into
one file with a pre-loaded reference capture in the store): both land as triangles
with the reference still a circle, the second save does not clobber the first, the
`loaded` entry survives both merges, and both scratch rows come back ticked.
(2026-07-25)

---

### USAGE.md — v1.10 — the colorbar reads as a range slider; the live cursor's SNR colour

Follows classviz v1.45. §5's **Heatmap colour scale** sub-bullet is rewritten around
what the bar now shows — handles that sit at Min and Max, pale saturation tails
outside them, a domain wider than the window so a handle can be dragged either way —
replacing the v1.44 sentence that called the drag handles and the spinboxes "the same
control" when the handles could not in fact show where the limits were. §5's Family
Plane bullet: the live cursor is described as **yellow below the SNR gate, green at or
above it** rather than flatly "a yellow dot", and the SNR-gate sub-bullet says so too.
§1 diagram and §5 heading: classviz v1.44 → v1.45. (2026-07-25)

---

### src/pimd_classviz.py — v1.45 — FIX the heatmap colorbar's handles never showed Min/Max; live shape cursor and trail go green above the SNR gate

**The colorbar handles could not show the range (bench report).** With **Scale** on
Min 500 / Max 1000, the two handles under the bar sat at the same place they always
sit, showing nothing about the limits just typed. Not a wiring fault: `ColorBarItem`'s
handles are *relative* adjusters, not level markers — `_regionChanged()` calls
`setRegion((63, 191))` after every drag, hard-snapping them back to 25%/75% of the
bar. They encode drag *rate*, not value, so no amount of pushing levels at the widget
would have moved them.

The bar is now an absolute range slider. It is built with `interactive=False` and
driven by our own `LinearRegionItem`: the axis spans a **domain** wider than the
Min/Max window, the two handles sit at the values of Min and Max within it, and the
pale flat tails outside them are the values the scale saturates on. The strip is
painted clipped exactly as the image is (flat below Min, ramp across the window, flat
above Max), written onto the bar pixmap directly rather than through
`setColorMap()` — which would have pushed both the clipped map and the bar's domain
levels into the heatmap image. Dragging either handle writes straight into the
Min/Max spinboxes, rounded to what those spinboxes display so the two can never
disagree.

The domain is the window unioned with the data on screen, quantised, then held between
50% and 90% of the bar — never so wide that a tight window on a Δ field reaching
~500000 µV becomes an unreadable sliver, never so narrow that the handles pin to the
bar's ends with nowhere to be dragged outwards to. It is **sticky**: an existing domain
that still holds the window at a workable size is kept. Refitting every tick would
re-centre the window after each drag and spring the handles back to 25%/75% — the
exact behaviour being replaced. It is also frozen for the duration of a drag, so the
value under the cursor does not move while the window is being dragged, and it is
never taken unrounded off the live matrix, which would walk the axis a pixel a frame.
In **Auto** the bar spans exactly the auto-computed range and the handles are hidden:
there are no tails to show, and a drag would not survive the next tick anyway.

**Live cursor and trail colour the SNR gate.** On the Family Plane scatter the live
cursor and every trail point drew yellow unconditionally. They now draw **green at or
above the SNR gate and yellow below it**, so a sweep shows where the frame crossed
into being worth reading. This is not a family verdict — that still belongs to the
loaded captures the cursor is compared against, and the cursor still takes no family
colour. Colour is re-tested against the gate *as it stands at redraw*, not against the
`gated` flag stamped at ingest, so moving the **SNR gate** spinbox repaints the trail
already on screen. An infinite SNR (splithalf collapsed to zero) reads green; NaN
reads yellow. The Band Curves and Crossing Ladder live markers are unchanged. The
tab's header comment and the SNR-gate tooltip, both of which still described a live
dot that "greys out and stops trailing" below the gate, now match the code.

Exercised headless (offscreen Qt, synthetic 80-frame rolling buffer with two noisy
threshold columns): handles land on Min and Max to within a µV across Std Dev and Δ
modes, a drag writes back and the handles stay put across the following redraw ticks,
the domain holds still while the data moves, the painted strip is verifiably flat
outside the window, Auto hides the handles and leaves the image on the auto range —
and a trail spanning SNR 2→12 colours y,y,y,G,G at gate 5.0, repainting to y,G,G,G,G
at gate 3.0 and all-yellow at gate 20. No bench hardware involved. (2026-07-25)

---

### USAGE.md — v1.9 — the heatmap's Min/Max scale and the remembered signature directory

Follows classviz v1.44. §5 gains two sub-bullets under the Analysis tab: the explicit
**Min/Max** colour scale with the Std Dev reasoning (Auto anchors a rolling-σ field at
0 and flattens it), and the signature dialogs reopening in the last directory used —
with the note that **New file…** deliberately still defaults into
`src/data/corpora/`. §1 diagram and §5 heading: classviz v1.43 → v1.44. (2026-07-24)

---

### src/pimd_classviz.py — v1.44 — Analysis heatmap manual scale is an explicit Min/Max; signature dialogs remember their directory

**Min/Max colour scale.** The Analysis heatmap's manual scale was a single ± half-range
spinbox: symmetric about 0 for the diverging modes, and `(0, val)` for RAW and Std Dev.
That is the wrong window for **Std Dev (rolling N)**, which is where it matters most —
a rolling σ field lives in a narrow band well above zero (quiet cells ~600 µV, a noisy
threshold column ~3000 µV on the bench), so a range anchored at 0 spends most of the
colour ramp on values that never occur and the whole heatmap reads as one shade. It is
now two spinboxes, **Min** and **Max**, both signed and both stepping adaptively (one
fixed step cannot serve a Δ range of ~500000 µV and a σ range of ~500 µV). Unchecking
**Auto** seeds them from the levels currently on screen, so manual mode starts from
what the operator is already looking at rather than a stale pair saved under some
other display mode; the seed is on `clicked`, not `toggled`, so it cannot fire during
`_load_settings` and eat the restored values.

The spinboxes are now the single source of truth in manual mode and are re-applied
every redraw tick. That is safe with the colorbar's drag handles because a drag writes
the dragged values straight back into the spinboxes — what the tick re-applies is what
was just dragged. The mode-dependent floor is gone with the half-range: whether a
scale is symmetric or unipolar is the operator's call now, not a rule inferred from
the display mode. A v1.43-or-earlier settings file has only the old
`analysis_hm_scale_manual`, and migrates to the symmetric `(-half, +half)` pair it
used to mean.

**Signature dialogs remember their directory.** `Load signatures…` and `Open for
editing…` opened on the process CWD every time. They now start in the last directory a
signature file was picked from, persisted as `last_signature_dir` and validated at use
time (not at load — a directory that exists at startup can be gone or unmounted by the
time the dialog opens), falling back to `src/data/corpora/`. Only the directory is
remembered, never a file path: a remembered path is the stale-pointer foot-gun
`_load_settings` already refuses for the editable-file path. **New file…** still
defaults into `src/data/corpora/` regardless — that is where the capture pipeline
expects a corpus, and the last-used directory may well be somewhere a read-only corpus
was browsed from.

Exercised headless with a synthetic 80-frame rolling buffer carrying two deliberately
noisy threshold columns: Auto gives (0, 3657) µV and flattens the field, Min/Max at
(500, 3200) separates the noisy columns; a colorbar drag survives the next redraw
tick; min ≥ max nudges the other spinbox instead of snapping back; and the settings
round-trip, the v1.43 migration and the directory fallbacks all behave. (2026-07-24)

---

### USAGE.md — v1.8 — the fourth tab renamed, and its v1.43 additions

Follows classviz v1.43. §5's tab bullet is renamed **Shape Space → Family Plane
Analysis** (with the old name kept in parentheses, since every §5/§1 reference written
before today says Shape Space) and gains three sub-bullets: material tags and what `?`
means, the per-axis custom band ranges, and that a click on either the plane or the
ladder drives the Tile Inspector. §1 diagram and the §5 heading: classviz v1.42 →
v1.43. (2026-07-24)

---

### src/pimd_classviz.py — v1.43 — Shape Space renamed Family Plane Analysis; material tags, per-axis custom bands, ladder click

**Renamed.** The tab is now **Family Plane Analysis** (`SHAPE_TAB_TITLE`), in the tab
bar, its group box and the status lines it emits. Internal names stay `shape`/`_shape_*`
and `pimd_shape.py` is untouched — the rename is what the operator reads, not a
refactor. The v1.42 entries below, `DESIGN.md` §15/§17.9 and `USAGE.md` §5 all still
say "Shape Space"; they describe the same tab.

**Material on the plane.** Every capture now carries a material tag derived from the
target registry (`material_class`, plus `plating_material` as `base/plating` — `Fe/Zn`
for gal pipe, `SS/Ag` for the plated server). It is drawn beside the scatter point and
appended to each Crossing Ladder row, and added to the hover tip and the Tile
Inspector title in long form. Tags are drawn as text rather than as extra marker
shapes because marker shape is already spoken for: `_SHAPE_SYMBOLS` encodes
(foreign profile, scratch object), and colour encodes family/colour-by. Tag colour
follows the marker, so under colour-by family a red `Al` is visibly a non-ferrous
material reading ferrous — the comparison the tab exists to support. One tag per
(target, distance) group, not per capture, or repeats redraw the same string in the
same few pixels; suppressed above `SHAPE_LABEL_MAX` = 200 drawn points, and behind a
"Material tags" checkbox (persisted). A capture whose `target_id` is not in the
registry reads `?` rather than a guessed material — scratch objects are unregistered
by design and another rig's corpus may carry ids this registry has never seen.

**Custom band range is now per axis.** X and Y have their own inclusive lo/hi spin
pairs. With the single shared pair, selecting "custom band range" on both axes plotted
a feature against itself — every point on the y=x diagonal, which reads as a finding
and is an artefact. Colour-by "custom band range" reads the X pair (it has no third
pair). Axis labels now name the range they are reading (`custom bands 2–4`), since
"custom band range" on both axes says nothing about what is being compared. A v1.42
settings file restores the plane it was drawing: the new Y pair defaults to the saved
X values.

**Ladder points are clickable.** `shape_ladder_points` shares the scatter's
`sigClicked` handler and carries the same `key` payload, so the panel where an outlier
is spotted is now the panel it can be opened from. The selection ring is mirrored into
the ladder (`shape_ladder_sel`, keyed off a new `target_id -> row` map, since row order
is by median crossing width and cannot be derived anywhere else); a below-gate
selection has no ladder row and correctly rings nothing. `_shape_redraw_static()` calls
`_update_shape_selection_marker()` a second time after the ladder rebuild — the
scatter's earlier pass ringed the previous layout's row.

Exercised headless (offscreen Qt, synthetic captures across 12 registry targets plus a
scratch id, an unregistered id and `air`): tags resolve as expected, custom-vs-custom
gives two genuinely different axes, a ladder click drives the Tile Inspector and both
rings, and the tag checkbox clears both the scatter tags and the row suffixes. No
bench hardware involved. (2026-07-24)

---

### DESIGN.md — 1.10 — consolidation pass (§18)

Human-directed, read-only rule suspended per §18. Consolidates everything above the
previous marker that was not already folded in by the 1.9.1/1.9.2 correction passes.

**Supply epoch.** §4 diagram and §12 rewritten for the 6S LiPo pack (19.8–25.2 V,
working floor 21.0 V), with the dropout-headroom rationale for adding a cell rather
than replacing like-for-like, the ≈2.5 W → ≈4.6 W dissipation cost, and the
never-measured pulse-instant rail-sag check recorded as outstanding. §3's SoC bullet
gets a supply note. Deliberately **not** treated as a second measurement epoch: the
§17.10 regulation result shows the L7815 holds the operating point across the
regulated window, so §17.7–17.9 stand as taken — the §17 banner says so explicitly
rather than leaving a reader to assume the worst.

**Tooling.** §15: classviz row v1.39 → v1.42 (four tabs, Shape Space, mixed-geometry
marking, the tab's own two-mode air reference, scratch captures); new rows for
`src/pimd_shape.py` v1 and `src/data/scratch/`; delaycal row gains the
settings-persistence trap; corpora row updated from "rebuild in progress" to the
captured 66-capture corpus. §16 gains the `pimd_shape --selftest` invocation.

**Findings.** New §17.9 (the 2026-07-23 corpus campaign and the family-plane /
crossing-axis / decay-persistence geometry it established) and §17.10 (the 6S trial:
threshold-column survey, three-run calibration series, the regulation result, the
reference-age drift ceiling, the live family-plane knife-edge). §14.1 gains the 6S
thermal reproduction and the reference-age consequence; §14.3 flags the noise floor
as doubly stale; §14.7 gains the operating-point dependence and its two unresolved
anomalies; **new §14.9** — the family verdict must not be a hard sign test.

**Assets.** Six new §15 rows citing `References/Targets v1 Analysis/` — the analysis
CSV and five figures, captioned from the figures themselves rather than their
filenames.

§10 records the in-progress recalibration and the two things the next lock must carry
(a state-of-charge window; an explicit warning that identical cell count does not
imply comparability) but **no new profile section** — nothing is locked yet. Also
deferred for want of bench facts, and listed in the Doc-rev line so the next pass
picks them up: feature-level portability across a threshold-geometry change (§13) and
the delaycal fix-or-procedure decision. Header versions and the stale `targets v2`
reference corrected; Doc-rev 1.9.2 → 1.10 with the full prior history preserved.
(2026-07-24)

---

### USAGE.md — v1.7 — Shape Space, the amended profile-switch diagnostic, Import-Profile-first

Follows the 1.10 consolidation. New §5 bullet for the **Shape Space** tab covering the
parts an operator can get wrong: the two-mode air reference and that Space is the only
thing that moves between them, that the tab deliberately ignores the Heatmap tab's
baseline, that nothing auto-detects a target, why air age matters at 60 s rather than
600, that mixed geometries are marked but not calibrated against each other, and that
scratch saves never reach `src/data/corpora/`. §1 diagram: classviz v1.39 → v1.42 plus
a `pimd_shape.py` v1 node.

**§5's profile-switch diagnostic corrected.** It advised that a blank heatmap after a
profile switch means `G` went out before the board confirmed the profile. An unknown
share of those observations were the glitch-buffer bug fixed at v1.42 — the 64-frame
median started at zero, so every frame in the first ~10 s was flagged a glitch. The
note now distinguishes a *persistently* blank heatmap from the first ~10 s, and says
past bench notes resting on the old wording are suspect.

**§4:** Import Profile promoted from an optional convenience to the standard starting
point for any recalibration, with the settings-persistence trap that motivates it.
**§6:** corrected a stale note that listed `pimd_corpus_check.py` among the untracked
previous-epoch tools — it is tracked, v1.6, and current. (2026-07-24)

---

<!-- Add new entries above this line. Format: ### <file> — v<N> — <short title> -->

## Archive — consolidated 2026-07-24

### hardware/power — 6S LiPo supply — bench PSU failed, moved to 6-cell pack

The 1990s bench supply failed 2026-07-24. The detector moved to a 6-series LiPo pack
(19.8–25.2 V) in place of the documented 5-cell pack (§12, 16.5–21 V). Rationale for adding a
cell rather than replacing like-for-like: at 5S the pack falls below the L7815's dropout
headroom over the back half of its discharge, so coil drive — and therefore decay amplitude,
and therefore the voltage each amplitude-anchored delay actually lands on — sags with state of
charge. 6S holds the +15 V rail in regulation across the whole usable discharge. Cost is
roughly double the dissipation in the 7815 (≈2.5 W → ≈4.6 W at the §17.1 measured ~0.5 A
average) inside a sealed shielded enclosure, on a project whose first open problem is thermal
drift; warm-up is correspondingly longer than the historical 5S/bench-supply case. Field
deployment is battery-powered regardless, so this brings forward a supply epoch change the
soil phase would have forced anyway.

Working discharge floor **21.0 V** (3.5 V/cell), comfortably above the ≈18 V at which the 7815
loses headroom and coincident with the cells' own useful-capacity limit — there is no region
where the electronics still work but the pack is being damaged.
[FILL: scope measurement of the +15 V rail during a TX pulse, fresh pack vs near-flat, to
establish the real floor — a depleted pack's internal resistance may sag the rail at the pulse
instant in a way a DMM on the pack cannot show. This number has never been measured.]
(2026-07-24)

---

### findings — threshold noise zone is operating-point dependent, not fixed-voltage

First movement on §14.7 since the enclosure epoch. Running Mode 2 on the 6S pack at 22.4 V
with `cal_63_air_v2` loaded, the Std Dev (rolling N) heatmap showed the **4.40 V and 3.80 V
columns elevated across all seven bands** at roughly 5× the §12 free-air floor (values at or
near the 1284 µV display ceiling; only the 20 µs / 4.40 V cell fell short). The defect followed
the *threshold* axis, not the band axis — bands share the threshold ladder but sample it at
different absolute delays and different pulse energies, so a fault tracking the voltage label
localises the mechanism to the voltage domain (front end / 1N4732 clamp / preamp) rather than
to timing or drive energy.

Two observations resist the simple "the zone moved" reading and are recorded unresolved: the
**4.20 V column read clean between the two elevated columns** (a single shifted or widened
zone cannot produce noisy–clean–noisy), and **3.80 V sits well below the 1N4732 knee**, where
the clamp should not be participating. Either a second mechanism is present or the zone is
structured rather than contiguous. Needs a scope on the front end plus a fine threshold sweep
(§17.7 method, 4.70 → 3.60 V, all bands).
(2026-07-24)

---

### src/pimd_delaycal.py — [FILL: version if a code change is made] — stale settings silently reintroduced an excluded band plan

Run 1 of the 2026-07-24 recalibration exported a profile carrying an **eighth band (6 µs /
50 kHz)** — excluded back in `cal_63_air_v1` as carrying no unique target information and being
noisy — together with an **8-value threshold ladder missing 4.2 V**. Neither was intended: the
operator edited two threshold voltages and pressed run, and `delaycal_settings.json` supplied a
stale baseline for everything else. The result looked plausible and was nearly locked.

Both anomalies share one root cause: **delaycal's persisted settings are not anchored to the
currently locked profile.** The band-plan exclusion is a project decision recorded in DESIGN
§10, and nothing in the export path enforces or flags a departure from it. Documented
workaround is the existing **Import Profile** path (USAGE §4) — load the current locked profile
first, edit, then sweep — which produced the corrected runs 2 and 3.
[FILL: accept as an operator procedure, or add a warning when an exported band plan or
threshold count differs from the loaded/locked profile? If the latter, this entry needs a
version bump.]
(2026-07-24)

---

### findings — 6S warm-up reproduces the §14.1 thermal fingerprint; pack voltage does not reach the operating point

Two successive calibrations 37 minutes apart (runs 2 and 3 of the 2026-07-24 series), same
settings, no hardware change, pack falling 23.6 → 23.05 V, give a delay shift monotonic in
pulse width (r = −0.95 against log pulse width):

| Band (µs) | 9 | 13.44 | 20 | 30 | 45 | 67.2 | 100 |
|---|---|---|---|---|---|---|---|
| mean shift (ns) | +14 | +9 | +1 | −11 | −27 | −48 | −84 |

Light bands later, heavy bands progressively earlier, overall range −96…+16 ns. This reproduces
the §14.1 post-enclosure thermal fingerprint closely — that recalibration moved delays −56…+16
ns with heavy bands earliest and light bands high — confirming the signature survives the supply
change and that the rig was still warming. Magnitude is smaller than the preceding interval,
i.e. converging, but a single 37-minute interval still moved the 100 µs band ~10 grid steps
(order 100 mV of operating point), so settling under 6S takes longer than the historical case,
consistent with roughly doubled 7815 dissipation.

**Supply-regulation result (new).** Across that interval the pack fell 0.55 V, yet the light
bands moved *later* — a direction a falling supply cannot produce, since less drive means a
smaller flyback reaching every threshold sooner across all bands. No supply-direction component
is visible. Within the regulated window the L7815 is therefore holding coil drive constant and
**pack state of charge is not reaching the operating point**, at least down to 23.05 V. This
supports setting the capture-window floor from pulse-instant rail sag (the pending scope
measurement in the 6S supply entry above) rather than from gradual state of charge.
(2026-07-24)

---

### USAGE.md — [PENDING] — profile-switch diagnostic invalidated by the v1.42 glitch-buffer fix

`pimd_classviz v1.42` fixed a pre-existing defect: the 64-frame glitch-filter buffer
(`_ch_glitch_buf`) was zero-filled on first use, so its median sat near 0 until 33 real frames
had arrived and every one of those frames was flagged `|raw − 0| > 100 mV`, i.e. a glitch.
The consequence recorded there is display-side — the heatmap showed ~0 for roughly the first
10 s after connect or after a profile change.

The consequence **not** recorded is documentary: USAGE §5 currently advises that a blank heatmap
after a profile switch means `G` went out before the board confirmed the profile. An unknown
share of those observations were this bug, not a lost `G`. The diagnostic needs amending, and
any past bench note resting on it should be treated as suspect. **USAGE.md is not yet edited** —
this entry records the defect in the documentation, not its repair.
[FILL: were any corpus captures taken within ~10 s of a connect or profile change? The Training
cycle excludes glitch-flagged frames, so the failure mode would be a slow-filling air buffer
rather than corrupted data — but confirm rather than assume.]
(2026-07-24)

---

### findings — reference age sets a hard ceiling on measurement validity; quantified against real targets

Building the Shape Space air model produced a general measurement constraint that was not
previously written down. At the §17.2 drift rate of ~50 µV/s, an air reference accumulates
**0.5 mV/cell at 10 s, 3.0 mV at 60 s, 7.5 mV at 150 s**. Against mean |Δ| from the 2026-07-23
corpus:

| Target | mean \|Δ\| (mV) | reference age that matches it |
|---|---|---|
| Cu_pipe_01 @60 mm | 6.52 | ~130 s |
| Fe_spanner_01 @60 mm | 3.28 | ~65 s |
| Cu_pipe_01 @180 mm | 1.05 | ~21 s |
| Fe_spanner_01 @240 mm | 0.36 | ~7 s |
| Cu_Zn_brass_dome_01 @180 mm | 0.35 | ~7 s |

So a reference older than ~10 s already rivals a weak target and one minute exceeds a strong
target at close range. Measured directly on the bench during the build: a spanner @60 mm reads
|Δ| 2.8 mV while 150 s of drift reads 5.2 mV — **removing the object makes |Δ| go up**, which is
why no magnitude test against a frozen reference can detect removal, and why the auto-release
logic was abandoned by direction.

This is a property of the instrument, not of any one tab. It is the quantitative justification
for the Analysis tab's air-bracketed Training cycle (§17.5) — corpus captures are protected
because they bracket air on both sides — and it means any procedure that does not bracket is
unreliable beyond ~10 s. Retrospective note: a static baseline observed at 3381 s old carried
~169 mV/cell of accumulated drift, i.e. a live display dominated entirely by thermal history.
(2026-07-24)

---

### findings — family-plane early-band axis needs a confidence band, not a sign test

Two independent lines of evidence converge. Offline, in the 2026-07-23 corpus analysis, family
classification held at 97.8% under an SNR ≥ 5 gate, but the misclassifications were
directional: solid ferrous targets drift toward *crossover* as SNR falls, because the early-pulse
cells are a ferrous target's smallest signal and lose their sign first (`Fe_spanner_01` @240 mm
misread as crossover in leave-one-out). Live, during the Shape Space build, `Fe_spanner_01` was
measured flipping ferrous → crossover at a ~15 s hold, its early-band mean being just
**+0.045 mV** — a fraction of a millivolt from the axis.

The two agree on mechanism and on which targets are exposed. Consequence for the classification
layer: the family verdict must not be a hard sign test on the early-band axis. A "too close to
call" band around zero, scaled to the capture's own noise floor, is required — and the same
band is what a live cursor should display rather than asserting a family. Recorded now so the
classifier inherits it rather than rediscovering it a third time.
(2026-07-24)

---

### src/pimd_shape.py — v1 — shared signature-geometry feature maths

New module. Pure NumPy + stdlib, deliberately free of Qt/pyqtgraph imports so the
same functions serve both the ClassViz Shape Space tab and a future classifier.
Turns a baseline-corrected `delta_mV` signature into the small set of scalars the
2026-07-23 corpus analysis found to separate targets: `unit_shape` /`amp_l2` /`snr`,
`band_means`, `band_range_mean` (backs the early/mid/late and custom-range axes
alike), `crossing_us`, `decay_persistence`, and `family` /`family_gated`.

Conventions are fixed and documented in the header: `vec` is band-major, pulse
ascending, thresholds high→low — the same row sort `pimd_features` writes and
`pimd_corpus_check.load_corpus` /`pimd_classviz._scan_editable_signature_file` read,
which is what makes a live frame and a stored capture comparable at all. Geometry
is always passed explicitly (`pulses_us`, `n_delays`); nothing assumes 63 cells, and
`default_band_ranges()` derives early/mid/late from `n_bands` (outer thirds), which
reproduces the analysis's 0-1 / 2-4 / 5-6 split for the 7-band operating profile
without hard-coding it.

`crossing_us` interpolates log-linearly between bracketing bands — the pulse ladder
is geometric (DESIGN §10), so equal information sits in equal log-width steps — and
takes the *first* neg→pos transition so a noisy late band cannot move the answer.
The two outcomes that are not a crossing get sentinel values rather than NaN:
`CROSS_ALREADY_POS = 8.0` (band 0 already positive — a solid ferrous target) and
`CROSS_NEVER = 200.0` (non-ferrous). Both sit just outside the 9–100 µs ladder so
they land on their own rails on a log axis instead of dropping out of the plot.

`family` is a sign test and `decay_persistence` a magnitude test, and they are meant
to be read together: a ferrite toroid reads ferrous by sign and non-ferrous by decay,
and both readouts are true of it. Neither is allowed to overrule the other anywhere
in the tooling.

`--selftest <corpus csv>` runs the four acceptance groups against a known corpus.
Verified against `gui_signatures_targets_v1_20260723.csv` (cal_63_air_v2, 66 captures):
66 points / 46 gated / 20 below gate at SNR 5.0; families 26 non-ferrous, 12 crossover,
8 ferrous; crossing widths within ±1.5 µs of the analysis figures (trivet 34.35/33.85,
SS disc 26.4–30.9, gal RHS 20.8–23.4, gal pipe 14.9–21.1, D-shackle 14.61 as the
earliest crossover), every gated ferrous ≤ 11 µs, every gated non-ferrous at
CROSS_NEVER, ferrite at CROSS_ALREADY_POS; decay persistence ferrous/crossover
min 2.44, non-ferrous max 1.75, ferrite 1.37. (2026-07-24)

---

### src/pimd_classviz.py — v1.42 — Shape Space tab + scratch captures

New fourth tab, **Shape Space**: every loaded signature as a point in a selectable
2-D feature space, with the current frame moving through it as a live dot. Purpose is
human exploration of signature geometry — the 2026-07-23 corpus analysis's family
plane, crossing axis and decay-persistence separation, live instead of in static PNGs.
All feature maths comes from the new `pimd_shape.py`; this file is plumbing and drawing.

Layout is a `pyqtgraph.dockarea.DockArea` with five movable/floatable docks — Scatter,
Band Curves, Crossing Ladder, Tile Inspector, Gauges — rather than the Analysis tab's
nested splitters: each panel wants the whole screen at some point, so they need to be
re-orderable, not merely resizable. Layout persists as `shape_dock_state` in
`classviz_settings.json` (restored inside its own try, so a state written by a build
with different dock names degrades to the default instead of taking startup down);
"Reset layout" replays the default `addDock` sequence, which re-homes placed docks and
pulls floated ones back. Control bar: X/Y/Colour combos, custom band-range spin pair,
SNR gate, trail length, Load signatures…, Reacquire Air, Save Scratch…, Reset layout —
all except the buttons persisted.

**One store, one loader.** Points come from `self._analysis_templates`, the set the
Analysis tab already loads; the Shape Space "Load signatures…" button is wired to the
existing `_on_load_signatures_clicked` handler. `_scan_editable_signature_file` now also
returns each capture's own `pulses_us` /`n_delays` /`profile_name` (read off its rows,
not assumed), and `_merge_template_list` carries `target_id` /`distance_mm` /`short_name`
/geometry/profile into the template dict — they were previously formatted into the
display label and discarded.

**Mixed profile geometries are allowed here, and marked.** This is the one place in the
app that plots captures from more than one profile together, so the reasoning is worth
stating. `_refresh_analysis_overlays()` must keep refusing, because it draws raw
cell-by-cell curves where cell index N is a different (pulse, threshold) pair under a
different profile — superimposing those is meaningless. These features are not that:
every `pimd_shape` function takes its geometry explicitly and normalises through it, so
a crossing width is µs either way and a family verdict is a sign either way. They are
comparable in *kind*. They are **not** calibrated against each other — a crossing is
interpolated on that profile's own pulse ladder, and decay persistence reads that
profile's own threshold columns — so every foreign capture is marked on sight:

- **Marker shape** carries it, because colour is spoken for (family / colour-by) and
  fill is spoken for (gated). Circle = live profile, square = other profile; star and
  diamond are the respective scratch forms. A dashed outline was tried alone first and
  reads fine on a hollow marker but is nearly invisible on a filled 9 px one, so shape
  does the work and the dash stays as reinforcement.
- **A standing banner** in the Scatter dock, not a transient status line, naming the
  counts and profiles actually on screen ("66 from cal_45_other_v1 (5×9)"), the live
  profile, and the not-calibrated caveat. While foreign geometries are on the plane the
  fact has to stay visible, because the numbers look perfectly ordinary.
- **Tooltip, Tile Inspector title and Band Curves** each say so too. The tile's threshold
  axis falls back to bare column indices labelled "own ladder" for a foreign capture —
  the voltage labels come from the live profile and would otherwise be a quiet lie. Its
  band curve is dashed for the sharper reason that its vertices sit on its own pulse
  ladder and need not touch the live profile's x ticks at all.

DESIGN §10's "frames from different profile geometries must never be mixed in one
dataset" governs corpus builds; nothing in this tab writes one, and scratch saves still
refuse a geometry mismatch outright. Genuinely unusable captures — a shape that isn't a
rectangular n_bands × n_delays, or too few bands/delays for the features to be defined —
are still dropped, now with a message that says that rather than citing §11.

**Two rules the panels exist to enforce.** Below the SNR gate the unit shape is
normalised noise — it still has a family verdict and still wanders the plane
convincingly — so below the gate the live dot greys, shrinks and drops its trail, and
the Crossing Ladder omits ungated captures entirely. And `family` (sign) and
`decay_persistence` (magnitude) are always shown side by side, never reconciled.

**The air reference — the tab's own, and why a static baseline cannot serve.** First
bench run of the tab reported the live dot wandering across the plane, confidently
family-coloured, with nothing in front of the coil. Root-caused to referencing the shared
static air capture: thermal drift (DESIGN §3 ≈ −50 µV/s; §14.1 heavy bands −20…−31 mV,
monotonic with pulse width) accumulates into the delta as a large **coherent** term, and
the SNR gate cannot catch that *by construction* — `splithalf` measures short-timescale
scatter, so drift inflates `amp` while leaving `splithalf` flat. Simulated at the
documented rate against a fresh static baseline, coil in air:

| time since air capture | amp | splithalf | SNR | gated? |
|---|---|---|---|---|
| 30 s | 9.8 mV | 1.15 | 8.6 | **yes** |
| 90 s | 27.2 mV | 1.25 | 21.7 | **yes** |
| 270 s | 79.3 mV | 1.18 | 67.2 | **yes** |

The first round of offline verification could not have caught this: its synthetic stream
was stationary, so the drift term never existed. Any future test of this tab has to drift.

Replaced with a Shape-Space-owned rolling air reference, the same drift-cancelling
principle as the Analysis tab's air-bracketed Training cycle (DESIGN §17.5). Shape Space
no longer consults `_get_current_baseline()` at all — with the Heatmap tab's Baseline
combo on Rolling or Nominal the whole tab was silently meaningless.

**Two modes, and Space is the only thing that moves between them.**

- **air** — every glitch-free frame feeds a `frames`-deep buffer and the reference is its
  running median, so the live delta is ~0 by construction and the cursor sits at the
  origin. The indicator carries the frame counter and goes **yellow → green** the moment
  a full `frames` is collected.
- **measure** — Space snapshots that median as a fixed, timestamped reference and the
  cursor moves against it. Space again returns to air, clearing the buffer so the counter
  restarts at 0 and the indicator goes back to yellow: the mode is then unambiguous from
  across the room. Refused below 2 frames (a median needs two); the green indicator is
  what says the reference is properly deep.

Nothing auto-detects a target arriving or leaving. An intermediate revision did — a
settle gate, a Detect threshold, auto-freeze on arrival, auto-release on removal — and it
is gone by direction. One measured fact from building it is worth keeping, because it
says the auto-release half was never going to be reliable: an absolute |Δ| against a
frozen reference **cannot** detect removal under drift, since after a long hold the
accumulated drift exceeds the target's own |Δ| — a spanner @60 mm reads |Δ| 2.8 mV while
150 s of drift reads 5.2 mV, so taking the object away makes |Δ| go *up*.

**The cursor is always yellow**, one constant size, in both modes — no family colour, no
gated/ungated tint, no size change. The family verdict belongs to the loaded captures it
is being compared against; a cursor that recolours as it moves reads as the instrument
asserting something it was not asked to assert. The trail, the Crossing Ladder's LIVE
diamond and dashed line, and the Band Curves live trace follow the same rule. Stroked
elements use a darkened shade of the same hue (`_hl_ink`), because `_HL_YELLOW` is a
background colour — pale enough to be near-invisible as a 2 px line on pyqtgraph's white
canvas.

Pinning the air-mode cursor to the origin matters: its magnitude is ~0 but its unit shape
still has a definite direction (the reference's half-window drift lag), which parked it
at a consistent off-centre spot — measured, right inside the non-ferrous cluster. It is
pinned only on the signed-mean axes where 0 is the origin of anything, and hidden on the
others.

Fixed while testing the frame counter, in code that predates this tab: the 64-frame
glitch-filter buffer (`_ch_glitch_buf`) was zero-filled on first use, so its median sat
near 0 until 33 real frames had arrived and every one of those frames was flagged
`|raw − 0| > 100 mV`, i.e. a glitch. The heatmap therefore displayed ~0 for its first
~10 s after connect or after a profile change, and the air buffer — which excludes glitch
frames — filled at a crawl over the same window (10 of 40 frames in 44 sweeps). Seeded
with the first frame instead.

**Two frame counts, both Shape Space's own and persisted separately.** `window` sizes the
live cursor position and its split-half noise floor; `frames` sizes the air buffer and the
counter. Both defaults are deliberately unlike the Analysis tab's, for measured reasons:

- **Window 15 frames, not the Stats tab's 50.** A 50-frame window is ~15 s at the sweep
  rate, so a target does not fully register for 15 s — by which time drift has already
  spoiled the reading. Measured: a copper pipe registered at 8 s with a 15-frame window
  and not at all with 50.
- **Air buffer 40 frames, not the Analysis tab's 120.** A rolling reference is
  single-ended, so its median sits half a window in the past and that lag is baked into
  every measurement as drift. Measured against a spanner @60 mm: family read correctly out
  to a 15 s hold at 20–40 frames, and was already wrong at a 5 s hold at 80–120.

The Air-age gauge reads the age of the snapshot in measure mode and `air mode` otherwise,
amber past `SHAPE_AIR_AMBER_S` (60 s, not the 600 s a static baseline suggested: at
50 µV/s a 60 s-old reference already carries ~1 mV/cell, the order of a weak target). The
Settled gauge survives as a plain readout with no threshold line and a neutral bar —
there is no settle threshold to draw any more, but "is the rig quiet right now" is still
useful context.

**"Reacquire Air" → "Re-arm Air"**, and it no longer calls `_start_capture()`. This
departs from the task brief, which specified the shared static capture here; the bench
showed that baseline is the wrong reference for this tab, and a Shape Space button
mutating the Heatmap/Analysis tabs' baseline as a side effect is worse than not.

**Scratch captures.** "Save Scratch…", live in measure mode once enough frames have
arrived since the snapshot and blocked in air mode, takes a label/note/distance/medium
plus an air-anchor choice: the snapshotted air reference as a single flat anchor (quick),
or the Analysis tab's two-anchor training
capture (drift-corrected, offered only when one is pending). Both run through the same
`pimd_features` plateau/quality routines and the same `build_rows` provenance columns as
the corpus save path. Label slugifies to `scratch_<slug>`, validated against
`pimd_target_check.TARGET_ID_RE`. Rows append to `src/data/scratch/gui_scratch_<date>.csv`
in the CORPUS_HEADER schema, never into `src/data/corpora/` — a corpus build hard-errors
on an unregistered target_id and that guard is deliberate; promotion means registering
the object in `targets_v1.csv` and recapturing properly. Same channel-count guard as the
corpus path. The schema has no anchor column, so the anchor mode is recorded as an
`[anchor=flat]` /`[anchor=air2]` suffix in the free-text notes: a flat single-anchor
capture is not drift-corrected and that has to stay visible afterwards.

There is no hidden SNR or settledness threshold on the button: you save what you can see,
and a thin or noisy capture is stamped honestly by `pimd_features.quality_flags()`
instead of the button greying out for a reason the cursor does not show.

The flat path takes its target frames from the moment the air was snapshotted onward, capped
at `ceil(MIN_CENTRAL_FRAMES / CENTRAL_FRACTION)`. Two things a plain "last N frames" got
wrong: the window could reach back past the freeze and pick up air (it was stamping
captures `noisy` because it straddled the placement transient), and at the tab's short
live window it was always stamped `short`. A patient capture now clears
`MIN_CENTRAL_FRAMES` honestly and an impatient one is still told it is thin.

The Crossing Ladder shows the live frame on its own reserved **LIVE** row at the top
(family-coloured diamond, hover tip carrying family/crossing/decay/amp/SNR) with a
matching family-coloured line running down through the target rows, so the live
crossing can be read straight against every target's dots. The earlier plain black
dashed line alone was indistinguishable from grid. Below the gate both are hidden
rather than greyed — unlike the scatter, where a grey dot still usefully says "here is
the frame, don't trust it", an ungated crossing width placed on an ordered ladder would
imply a rank that isn't there.

One live-SNR defect, caught while testing that live row and worth spelling out because
it was silent: the live amplitude was taken from `_compute_analysis_matrix()` — a mean
over the Analysis tab's Avg-N frames, **default 1** — while the live noise floor came
from a 50-frame split-half. Amplitude and noise must be averaged over the same number of
frames or their ratio is not an SNR; the mismatch inflated it by roughly
√(N_window/N_avg), and in an offline sweep across the noise levels DESIGN §3/§17.8
reports, plain air cleared the 5.0 gate on its own. The live dot would have gone
confidently family-coloured, with a trail, on nothing at all — precisely what the gate
exists to prevent. Replaced by a single `_shape_live_window()` deriving both from one
window, mirroring `compute_plateau_stats` exactly: median frame minus baseline for the
shape, split-half of the same window for the noise. Air now reads SNR ≈ 1.0–1.3 at every
noise level from 0.05 to 2.0 mV (the correct answer for pure noise under matched
averaging) and stays ungated with no trail, while a presented spanner reads gated and
ferrous throughout; live amplitude reproduces the stored capture's 38.88 mV.

One performance defect, also caught offline: the Band Curves dock initially rebuilt
every curve — selection, all checked signatures, and the live frame — on each redraw
tick. With the full 66-capture corpus checked that measured **66 ms per tick against
the 33 ms REDRAW_MS budget**, i.e. a visible stall whenever the live dot moved. Split
into a static half (selection + checked, rebuilt only on load/selection/control
changes) and a single persistent live curve item updated in place: 66 ms → 0.5 ms per
tick, independent of how many signatures are checked.

One capture-identity defect found during offline verification, worth recording
separately because it is the **same class as the v1.40 corpus-path failure**: the
scratch save initially derived its session id from a `%Y%m%d_%H%M%S` timestamp and
used a fixed `_c01`, so two saves inside the same second produced identical
`(session, capture_id)` keys, `_scan_editable_signature_file()` folded their rows
into one capture, and the second save silently vanished. Reproduced (126 rows, 1
capture) before the fix. Now one session per scratch *file* (`scratch_<date>`, matching
the filename) with a running `_cNN` resumed above the highest already in the file,
plus the same collision while-loop the corpus path uses.

Three rendering defects found and fixed during the same pass, all worth recording
because each was silently wrong rather than broken: `QColor('#RRGGBB' + '22')`
is read by Qt as `#AARRGGBB`, so the ladder's shaded sentinel rails came out dark grey
and green instead of translucent red and blue (now `setAlpha`); the empty-state
`setXRange`/`setYRange` latched the scatter off auto-range, so switching axes put nearly
every point off screen (now re-enabled whenever there are points); and the gauge strips
were sized such that the GraphicsLayout margins plus the scale axis left the viewbox
4.5 px tall, rendering each bar as a hairline. Also noted, deliberately not "fixed":
pyqtgraph's `enableAutoSIPrefix(False)` does not clear the already-latched
`autoSIPrefixScale`, it only stops the label disclosing it — so the auto prefix is left
on (its default here and in every other plot in this file), and the axis says "(x0.001)"
rather than silently showing 150 for 0.15.

Verified offline against `gui_signatures_targets_v1_20260723.csv` under cal_63_air_v2:
66 points, 46 filled / 20 hollow at gate 5.0; 26/12/8 family split; ladder ordered by
median crossing; `Fe_spanner_01` @60 renders red intensifying toward 100 µs (7 of 63
cells marginally negative, ≤0.61 mV against a +14.16 mV peak, so they render near-white
— the brief's "all-positive" is a visual claim, not a literal one), `Cu_pipe_01` @60
strictly all-negative; dock layout survives a save/restore cycle byte-for-byte and Reset
restores the default; a scratch save round-trips back through "Load signatures…" and
renders with the scratch marker. Live-dot behaviour was exercised with a synthetic frame
stream: air reads below gate with no trail, a presented spanner shape reads gated,
ferrous, with its trail. Mixed geometry was exercised against a synthetic 5×9
`cal_45_other_v1` corpus folded down from the same captures: 132 points (66 native, 66
foreign) all plotting, foreign features sane on their own ladder (spanner ferrous /
already-positive / decay 6.76, copper pipe non-ferrous / never / decay 1.55), 66 squares
vs 66 circles, banner naming the profile and clearing again on unload, foreign band
curve carrying its own five vertices at 9/20/30/45/100 µs.

The two-mode air model has its own drifting-air harness, which is now the regression that
matters, since a stationary stream cannot see the defect that prompted all of this. Over
six simulated minutes of air at the DESIGN §3 rate the cursor stays exactly at the origin,
yellow, with no trail and no mode change (a static baseline reached SNR 67 on the same
input); the counter fills one frame per sweep and the indicator flips yellow→green
precisely at `frames`; a target appearing and then leaving changes nothing without Space;
Space enters measure and the cursor moves into the right quadrant for a spanner (ferrous)
and a copper pipe (non-ferrous) with the reference provably unchanged during the
measurement, every live marker yellow; Space returns to air with the buffer cleared and
the trail, ladder marker and live band curve gone; Space is refused with 0 frames and
accepted with 5, announcing the reference as thin; and taking the air *with* a target in
place then measuring it reads ~0 — asserted so that consequence of removing auto-freeze
is a known property rather than a surprise.

Reading accuracy against hold time was characterised rather than asserted, since it is
bounded by physics rather than code: four of five targets read correctly out to a 40–60 s
hold, and `Fe_spanner_01` flips ferrous→crossover at ~15 s because its own early-band mean
is +0.045 mV — a knife-edge on that plane, so a fraction of a mV of drift moves it.

Noted while running these: under `QT_QPA_PLATFORM=offscreen` this environment segfaults at
interpreter exit with no Python frame on the stack, reproducibly (10/10) in a script that
only constructs the window and feeds frames on the Heatmap tab — nothing to do with this
tab, and it happens after all work has completed. The harnesses now `os._exit()` so their
exit codes stay meaningful.

Confirmation on the bench with a real target is outstanding — everything above is
simulated. (2026-07-24)

---

### src/pimd_classviz.py — v1.41 — FIX Space-forced placement skipped the removal wait

Reported from the bench: on a target weak enough to need the Space override to get
out of `await_target`, the cycle jumped straight from the acquired target into the
trailing-air phase, with no chance to lift the target off the coil.

Deterministic, not intermittent. Both auto-detect transitions test the same
quantity — `_current_dev_from_air()`, mean |Δ| between the live settle window and
the locked leading air — against Detect: placement on `dev > Detect`, removal on
`dev < Detect`. The override is only ever needed because a target's |Δ| *never*
crosses Detect, so the removal test is already satisfied the moment `await_remove`
is entered, and the first settled frame advances to `air_trail`. Every target that
needs the manual placement was therefore guaranteed to skip the removal wait, and
any signature saved from that cycle has target frames in its trailing air —
corrupting the split-half floor and the SNR.

Fixed by latching the reason: `_sig_enter_target(manual=True)` from the Space
handler records that auto-detect never saw this target, and `await_remove` then
ignores the `dev < Detect` transition and waits for Space. Instruction B reads
"Remove target, then press Space" in that mode. The latch clears at every cycle
boundary (`_sig_finish_air_trail`, abort, start, reset), so a cycle whose placement
*was* auto-detected keeps full automation — that path is unaffected, since a
present target holds `dev` above Detect and cannot mis-fire on entry.

Untick-mid-cycle guard: once latched, Space keeps working for the rest of the cycle
even if "Space override" is cleared, which otherwise leaves no way out of
`await_remove` but the 30 s timeout abort. The countdown itself is unchanged — a
manual removal must still be done inside the same 30 s window. (2026-07-23)

---

### src/pimd_classviz.py — v1.40 — FIX capture_id reuse silently swallowed training saves

Field failure during a targets_v1 training capture: four targets saved and listed
fine, then the fifth (and every one after it) vanished — Save Sig cleared the
readout as if it had worked, but nothing appeared in the signature list.

The rows *were* written. `_reload_editable_signature_list()` set the next capture
sequence number to `len(sigs)`, the count of captures in the file. That is only
equal to the highest `_cNN` while the numbering is gap-free. Deleting a capture
opens a gap, after which the count hands the next save an id that already exists.
Nothing rejects a duplicate: the append succeeds, `_scan_editable_signature_file()`
groups on `(session, capture_id)` and folds the new rows into the existing capture,
`len(sigs)` doesn't move — so the same id is reissued forever and every subsequent
save disappears into it. In the failing file `c05` had accumulated 4 × 63 = 252
rows under one id.

Three changes. The sequence number now resumes above the highest `_cNN` actually
present (`_capture_id_seq()` parses the trailing index) rather than counting
captures, so a gap is harmless. `_on_sig_save_clicked()` additionally skips past any
id already in the file before writing, so a collision cannot happen even if the
seed is wrong. And the pre-save channel-count check now walks every capture instead
of sampling only the first — a folded capture has a wrong-length shape, so that
check now catches an already-corrupted file (it previously passed, because the
first capture was intact).

The affected corpus (`gui_signatures_targets_v1_20260723.csv`) was repaired in
place: the three orphaned captures — brass gear, and two crank-handle repeats —
were reissued as `c06`/`c07`/`c08` by regrouping on `captured_at`, and the second
crank-handle capture got `repeat_idx` 2 (both had been written as repeat 1, since
the repeat auto-increment reads the same merged scan). No measurement data was
lost; only `capture_id` and one `repeat_idx` changed. Original kept as `.bak`
alongside. (2026-07-23)

---

### .gitignore / DESIGN.md 1.9.2 — superseded profiles listed individually

The profiles rule was `src/data/profiles/*` plus `!src/data/profiles/cal_63_air_v2.json`.
Git handles that correctly — `git check-ignore -v` named the rule, and
`git status --ignored` reported the three superseded locks as `!!` — but VS Code's
Explorer kept showing all four profiles in normal (tracked) text rather than
greying the ignored three. The `dir/*` + negation idiom renders unreliably in some
editors' ignore decorations, and a working tree you can't trust at a glance is a
foot-gun in a repo where "which profile is the operating one" is a §10 contract.

Replaced with three explicit paths (`cal_63_air_v1`, `cal_72_air_v2`,
`cal_72_air_v3`). Net tracking is identical — only `cal_63_air_v2.json` is tracked,
all four stay on disk. The trade-off is deliberate and documented in both files:
new delaycal candidate profiles are **no longer ignored by default**, so they show
up as untracked until they are either locked (tracked) or retired (added here).
Arguably the safer default anyway — a new profile appearing in `git status` is a
prompt to decide about it, not noise.

DESIGN.md §15's `src/data/profiles/` row was describing the old mechanism, so it is
reworded to state the policy rather than the `.gitignore` implementation, and
Doc-rev bumped 1.9.1 → 1.9.2.

Verified: the three report `!!` under `git status --ignored` and `check-ignore -v`
names their new individual rules; `cal_63_air_v2.json` reports not-ignored and stays
tracked; a scratch `cal_TEST_new.json` correctly appears as `??` rather than being
silently hidden. (2026-07-23)

---

### src/pimd_target_check.py — v3 — renamed from pimd_targets.py

Module renamed `pimd_targets.py` → `pimd_target_check.py`, aligning it with
`pimd_corpus_check.py` (the two validators of the two human/tool data contracts).
`git mv` plus a mechanical `pimd_targets` → `pimd_target_check` rewrite across the
three consumers — `pimd_classviz.py`, `pimd_features.py`, `pimd_corpus_check.py` —
covering the `import`, every qualified call (`load_targets`,
`DEFAULT_REGISTRY_PATH`) and the user-facing strings that name the CLI. No
behaviour change: the import contract is the only thing that moved, so the
consumers are **not** version-bumped (CLAUDE.md: version tracks functional
change). The module keeps its dual library + CLI role — the new name reads
checker-ish, but it is still what classviz and features import at runtime to
validate the registry.

Verified: all four PC tools `py_compile` clean; `python pimd_target_check.py`
loads the 22-target registry with no issues; `pimd_features.py --help` resolves
its `--registry` default through the renamed module; `pimd_corpus_check.py` runs a
real corpus to a full table; the four headless suites pass 115/115.
(2026-07-23)

---

### Repo hygiene — profiles, profile8b captures and a stray delaycal CSV

Three tracking changes, all keeping files on disk except where noted:

- **`src/data/profiles/` is now tracked by exception.** Only the current
  operating profile, `cal_63_air_v2.json`, is in git; `cal_63_air_v1.json`,
  `cal_72_air_v2.json` and `cal_72_air_v3.json` are untracked but retained
  locally. `.gitignore` uses `src/data/profiles/*` + `!…/cal_63_air_v2.json`
  rather than listing the three, because delaycal writes candidate profiles into
  that directory routinely — the default should be "not repo source". Locking a
  new operating profile is a deliberate act: `git add -f` it and move the
  exception.
- **`References/profile8b-*` (3 previous-epoch captures) untracked**, kept on
  disk. Their DESIGN.md §15 rows were already dropped at Doc-rev 1.8, so they
  were tracked but uncited — flagged in the 1.9 consolidation pass.
- **`src/data/delaycal_1706-104844.csv` deleted.** A stray 2026-06-17 sweep
  output that predates the epoch reset; `src/data/delaycal*` was already
  gitignored, so it was only still tracked because it was added before that rule.

(2026-07-23)

---

### DESIGN.md — 1.9.1 — post-consolidation corrections

Human-directed, read-only rule suspended per §18. Follows the four changes above:
§15's registry row becomes `src/pimd_target_check.py` (**v3**, noting the former
name) and the classviz row's reference to it follows; the `src/data/profiles/` row
records the new track-by-exception policy. Doc-rev bumped 1.9 → 1.9.1 with the
existing history preserved. Nothing else touched — §3 and §17 remain untouched, as
in the 1.9 pass. (2026-07-23)

---

### USAGE.md — v1.6 — rename follow-through + stale version fixes

`pimd_targets` → `pimd_target_check` (v3) in the §1 pipeline diagram, the §6
heading and the §6 body/CLI examples. Two stale references corrected while there:
classviz v1.35 → v1.39 in the §1 diagram and the §5 heading, and the §5 Analysis
bullet no longer lists the `notes` placement field (removed at classviz v1.38) —
it now names the v1.38 per-parameter green/amber/red readout instead. (2026-07-23)

---

## Archive — consolidated 2026-07-23

### src/pimd_corpus_check.py — v1.6 — FIX air captures aborted the whole run

An **air** capture legitimately has no distance: classviz forces
`distance_mm=None` when `target_id == 'air'`, and `pimd_features.format_distance
(None)` writes an empty `distance_mm` column. v1.5's loader parsed that column
unconditionally (`int(round(float(...)))`), so a single air capture anywhere in
a corpus killed the entire run with an opaque
`ValueError: could not convert string to float: ''` — before a single check
could execute. Found while testing the classviz v1.39 work: the Analysis tab's
Training cycle can save air captures into the corpus, so the next re-profiling
run would have produced a corpus the checker refused to read at all.

New `_parse_distance_mm()` returns `None` for a blank column. Fixing the parse
alone only moved the crash, though: `check_splithalf_snr()` sorts every capture
by `distance_mm`, and one `None` among the ints raises
`TypeError: '<' not supported between instances of 'NoneType' and 'int'` as soon
as a corpus holds both an air capture and an object one — i.e. every real
corpus. Its sort key now substitutes -1 for a missing distance (real distances
are >= 0) so air sorts first within a label, and the row is labelled `@air`
rather than `@Nonemm`.

Air keeps its SNR row deliberately — its split-half floor is the most directly
meaningful noise reading in the corpus — and stays excluded from every
distance-keyed check (shape-invariance, falloff, repeat, cross-campaign), which
it already was via `NON_OBJECT_TARGET_IDS`. `one_per_distance()` additionally
skips any capture whose distance is `None`, so a hand-edited object row with a
blank distance is dropped from those checks instead of blowing up the
`sorted(grp)` every caller does.

Verified: a 14-check suite over synthetic corpora shaped like a real
re-profiling run (air anchors interleaved with an object at 60/120/180 mm plus a
repeat) — the air-only corpus that reproduced the v1.5 crash now loads; both air
captures appear as `@air` in the SNR check and nowhere else; no `None` leaks
into any label; the object still gets its shape-invariance rows, its repeat
comparison and a falloff fit recovering n=2.00 from an r^-2 fixture; a blank
distance on an object row is skipped without crashing; and the CLI exits 0 with
a full table. Against both real `src/data/corpora/gui_signatures_*.csv` files
(no air rows) v1.6's output is byte-identical to v1.5's, so this is a pure fix
with no behaviour change on existing data. (2026-07-23)

---

### src/pimd_targets.py — v2 — registry relocated to data/targets/targets_v1.csv

The target registry lived at `src/data/training_lists/targets.csv` — a directory
that otherwise held the Training Session tab's saved run-list JSONs, and that
classviz v1.39 has just made dead by removing that tab. The registry is not
training-list data and never was, so it moves to its own home:
`src/data/targets/targets_v1.csv` (moved with `git mv`, contents untouched — 22
targets, no validation issues).

One line changes: `DEFAULT_REGISTRY_PATH` in this module. `pimd_classviz.py`
(`TARGETS_REGISTRY_PATH`) and `pimd_features.py` (the `--registry` default) both
already derived from it, so neither needed a source edit and neither is version
bumped. The `--registry` CLI flag still overrides, and its help text prints the
new default. Header/docstring references updated; the CLI help no longer names
the file literally, since the filename now carries a version suffix.

Verified: `pimd_targets.py` CLI loads all 22 targets from the new path with no
issues; `pimd_features.--registry` resolves to it; classviz builds headless with
a 23-entry target combo (22 + air) and reports "Target registry loaded: 22
target(s)". (2026-07-23)

Note for the next DESIGN.md consolidation pass: §15 has two rows and one
`References/` caption still pointing at `src/data/training_lists/targets.csv`,
and the `src/pimd_targets.py` row still says v1. (2026-07-23)

---

### USAGE.md — v1.5 — Training Session tab removed; registry path updated

Follows classviz v1.39 and targets v2. The §5 "Training Session tab" bullet is
dropped and the classviz intent line no longer offers "quick signature captures
and guided training sessions" as two paths — the Analysis tab's automated
Training cycle is the only capture path now. The §7 registry path and the two
other `targets.csv` mentions become `src/data/targets/targets_v1.csv`. (2026-07-23)

---

### src/pimd_classviz.py — v1.39 — remove the Training Session tab

All corpus capture now happens through the Analysis tab's own Training group
(the automated auto-detect air/target/air cycle from v1.34–v1.35, refined in
v1.38), so the separate **Training Session** tab is redundant and is gone: the
guided run-list table, Start/Pause/Stop, Space step-advance, the per-row
Placement… dialog and the saved target-list JSON templates. That is one
contiguous 505-line block (`_build_training_session_tab` through
`_on_training_save_list`, 26 methods), plus the module-level
`TRAINING_LISTS_DIR` and its three saved-list file helpers, the `__init__`
state `_training_current_row` / `_training_row_start_wall` /
`_training_pause_started`, and the now-unused `QAbstractItemView` / `QDialog`
imports. Every removed method was verified to have no caller outside the block.

**Deliberately kept:** the session-recording machinery the tab shared with the
rest of the app — `_session_start` / `_session_stop` / `_append_mark` /
`_append_mark_target` and the `_recording` / `_session_file` state — which the
Analysis tab's Session sub-panel and the Stats tab's Record Session button both
drive. `_build_target_placement_widget_set()` also stays despite dropping to a
single call site: the field set *is* the corpus schema's placement tuple and
deserves one definition.

**Tab-index hazard fixed.** `_redraw` gated the Analysis charts on a hardcoded
`ANALYSIS_TAB_INDEX = 3` while `eventFilter` used the `_analysis_tab_index`
that `addTab()` actually returned. Removing a tab above Analysis moves it to
index 2, so the constant would have silently stopped matching and frozen the
charts. The constant is deleted and both sites now use the live index.

**Latent bug fixed as a consequence.** `_training_paused` (renamed to
`_session_paused`, now that no "training session" sets it) was only ever
cleared on stop by `_reset_training_ui()`, which ran solely when a *Training
Session tab* run was active. An Analysis-tab session that was paused and then
stopped therefore left the flag set — `_set_sig_session_active_ui(False)`
unchecks the Pause button with signals blocked, so the toggle handler never
fires — and the next recording silently wrote no frames, since process_packet
gates on it. Deleting the tab would have removed the only reset path entirely,
so `_session_stop()` now clears the flag directly.

Space is now bound only to an active Analysis training cycle while that tab is
visible (unchanged condition); with no Training Session step-advance to fall
through to, Space is otherwise left alone and reaches the focused widget as
normal. Settings drop `training_list` and `training_settle`; stale keys in an
existing settings file are ignored by `.get()`, so no migration. Also folds in
a v1.38 leftover: `_on_sig_session_mark()`'s dangling-target message still said
"reload targets", naming the button v1.38 deleted.

Verified headless (`QT_QPA_PLATFORM=offscreen`, 99 checks across three scripts,
all passing): three tabs remain in Heatmap/Stats/Analysis order with the
Analysis index now 2 and the stale constant gone; no `_training_*` attribute or
module-level list helper survives; a v1.38 settings file carrying the dropped
keys still loads and still applies the rest; and the shared session recorder
still starts, marks (writing both `# mark:` and `# mark_target:`), refuses a
mark while paused, resets the pause flag on stop, and records on the following
session. The v1.38 suites still pass unchanged. Bench confirmation of a full
Analysis training cycle and a Stats-tab Record Session still to be done.

Note for the next DESIGN.md consolidation pass: §15's `pimd_classviz.py` row
still advertises the Training Session tab. (2026-07-23)

---

### src/pimd_classviz.py — v1.38 — Analysis-tab capture ergonomics

Seven bench annoyances from using the Analysis tab as the primary capture
workbench (it grew into that role over v1.31–v1.37, but its layout still
reflected the older heatmap-first arrangement). No acquisition, wire-format or
profile-geometry change — DESIGN §11 untouched; `pimd_features.py` is read-only
here, imported for its constants only.

**(1) Shrinkable heatmap / growable signature list.** The heatmap owned a fixed
share of the left column (`addWidget(..., stretch=1)`) while the signature list
was capped at 46 px — ~2 visible rows, which made a 10+ capture corpus
unpickable for overlays. The left column is now a vertical `QSplitter`
(`self.analysis_left_split`): Controls/Signatures/Training above, heatmap below,
default `[620, 380]`. The heatmap child is collapsible and `analysis_gw` gained
a `setMinimumHeight(80)` so it can be dragged down to nothing; the controls
child is not collapsible. The list's 46 px maximum became a *minimum* and it now
takes the recovered space (`addWidget(..., stretch=1)` inside the Signatures
group). Sizes persist as `analysis_left_split_sizes`, guarded by a child-count
check on restore.

**(2) New captures land checked.** A freshly saved signature was unchecked, so
it wasn't on the charts until it had been found in that 2-row list. A new
in-memory `self._sig_autocheck_keys` set records each `(session, capture_id)`
saved this app session; `_merge_template_list` uses membership as the per-item
*default* check state. Only a default — `prev_checked` still wins for any item
already in the list, so unticking a fresh capture sticks across Save/Delete
reloads. Loading a reference corpus or reopening a file is unaffected (they
default unchecked), and the set is cleared on New file… / Open for editing… so
switching away and back brings rows back as they are on disk. This deliberately
covers the automated Training cycle too, which saves through the same handler —
everything captured this session is on the charts, with "Clear signatures" as
the way back out.

**(3) Black live traces.** The four "current" curves (chart-2, the 8- and
9-grids, the band-mean strip) were blue, the same visual family as whatever blue
`pg.intColor()` handed a template overlay, making live-vs-corpus ambiguous.
They're now black; overlays keep their intColor dashed pens.

**(4) Emphasised Target combo.** `_build_target_placement_widget_set()` takes an
`emphasise_target` kwarg, set only for the Analysis tab's inline capture set:
bold 12 pt label + combo, 300×30 minimum. That one combo decides what every Save
writes into the corpus and picking the wrong one silently mislabels a capture —
it shouldn't look like just another dropdown. The Training tab's Placement
dialog keeps the plain look.

**(5) Per-parameter quality colouring.** The readout was one flat string whose
*whole* label went yellow when `quality != 'ok'`, so "is this a good capture?"
meant mental arithmetic against constants living in `pimd_features`. Each field
now carries its own green/amber/red `<span>` background (QLabel renders HTML;
the palette rgb strings are factored into module-level `_HL_GREEN/_HL_YELLOW/
_HL_RED` that the `MY_*` stylesheet constants are now built from, so the two
can't drift). Bands come from three new "Green when:" spinboxes, defaulted from
`pimd_features` and persisted as `sig_q_amp_mv` / `sig_q_mean_mv` /
`sig_q_split_ratio`: Amp(L2) ≥ `AIR_THRESHOLD_MV_DEFAULT × √n_channels` (the L2
equivalent of the air threshold, per the L2 ≈ √n·mean|·| relation documented in
`compute_plateau_stats`); Mean|Δ| ≥ `AIR_THRESHOLD_MV_DEFAULT` (literally "below
this → air"); Splithalf ≤ `NOISY_RATIO_THRESHOLD` × Amp (the exact
`quality_flags()` 'noisy' rule). Amplitudes amber at half-threshold; Splithalf
and SNR share one verdict (same quantity, read two ways) with amber to 1.5× the
ratio; Quality is green on 'ok', amber with the flag text otherwise. Editing a
spinbox repaints the cached stats immediately. The None/'error' branches and the
"single air anchor" note are unchanged. *Flagged, not addressed:* the bands read
"more signal is better", so an intentional **air** capture — where a large
Amp/Mean|Δ| is the bad outcome — still colours green; inverting the sense for
`target_id == 'air'` is a separate decision.

**(6) Notes box removed** from the shared placement widget set, so it's gone
from both the Analysis tab and the Training Placement dialog — nothing was being
typed into it. `_placement_from_widgets()` returns `'notes': ''`, so the key,
the corpus `notes` column and the session dump's `# mark_target:` line keep
their exact shape (verified: `pimd_features.parse_mark_target_line()` still
round-trips the line). `sig_notes` is dropped from settings; a stale key in an
existing settings file is ignored by `.get()`.

**(7) Reload-targets button removed** along with `_on_reload_targets_registry_
clicked()`. The registry is a slow-moving reference file, not worth a permanent
control; `_load_targets_registry()` still runs at UI-build time. The
dangling-target message on Save now says to restart ClassViz to pick up registry
edits.

Verified headless (`QT_QPA_PLATFORM=offscreen`, 63 checks across two scripts):
UI builds; splitter collapses the heatmap to 0 and its sizes survive a restart;
thresholds default from the `pimd_features` constants, persist, and repaint the
readout live; good/mid/bad stats colour each field as specified; all four live
curves are black; a real Save writes an unchanged CORPUS_HEADER with an empty
`notes` column, is read back by `pimd_corpus_check.load_corpus()`, and lands
**checked** in the list, while a file-switch round-trip brings it back
unchecked. On-bench visual confirmation and live-capture colouring still to be
done by Mark. (2026-07-23)

---

### src/pimd_classviz.py — v1.37 — FIX Load signatures / Open for editing rejected the app's own files

Both Analysis-tab load buttons delegated schema sniffing/reading to
`pimd_corpus_check.py`, which is deliberately frozen on the legacy
`target`/`distance_cm` schema and hard-`SystemExit`s on the v1.32+
`target_id`/`distance_mm` schema — the exact schema this app now writes. So
`_on_load_signatures_clicked` (`load_corpus`) and `_on_sig_open_for_edit_clicked`
(`sniff_format` gate) both failed on every `gui_signatures_*.csv` the Training
flow produces, surfacing only a `Load failed:`/`Open failed:` line in the status
bar — i.e. nothing loaded. Confirmed against a real capture file. Fix: a new
`_sig_file_is_new_schema()` (checks the header for target_id/distance_mm/delta_mV)
dispatches both handlers to the app's own already-correct
`_scan_editable_signature_file()` reader for new-schema files. Load signatures
falls back to `pimd_corpus_check.load_corpus()` for legacy reference corpora
(still overlay-able read-only); Open for editing now requires the new schema
(editing appends v1.32+ rows via Save, so the file must already be that schema)
and gives a clear message pointing at New file… / Load signatures… otherwise.
`_merge_template_list` already handled the new schema's (session, capture_id)
2-tuple keys, so no list-rendering change was needed. Verified headless against
the real failing file: both buttons now parse its 3 signatures; a legacy-schema
header is correctly routed to the `pimd_corpus_check` path. (2026-07-22)

---

### src/pimd_classviz.py — v1.36 — persist the remaining preference controls

Audit of `_save_settings`/`_load_settings` after Mark noticed the top-bar
**Saved profile** dropdown wasn't remembered across launches. Four genuine
preference controls had no persistence and are now saved/restored: the
`cb_profile_file` (Saved profile) and `cb_training_list` (Training Session
Saved list) selectors, the Stats-tab Std colour thresholds
(`sp_std_lower`/`sp_std_upper`, 0.50/1.00) and the Training-tab settle window
(`sp_training_settle`, 50). Both dropdowns are already populated from disk in
`_build_ui` before `_load_settings` runs, so restore uses `findText` and falls
back to the default index if the saved file has since been deleted (verified);
restoring a profile selection only sets the dropdown — it does not auto Load &
Run, which still needs a live connection and an explicit click. Deliberately
left unpersisted (documented, not oversights): `cb_continuous` (Log
Continuously — an action toggle; auto-starting logging on launch is a foot-gun,
same stance as not restoring an in-progress recording or the editable-file
pointer), `le_csv` (its default is intentionally date-stamped per launch), and
`le_label` (per-capture free text). Everything else the operator sets was
already persisted. Verified headless: a five-value round-trip through a temp
settings file restores all five, and a settings blob naming a non-existent
profile leaves the combo at its default index without error. (2026-07-22)

---

### src/pimd_classviz.py — v1.35 — Training status labels + place/remove flash & beep

Two UX fixes to the v1.34 Training status line, in `_update_sig_train_indicator`
and the phase-entry/exit helpers. (1) The A (status) labels now name their
subject — `SETTLING air/target`, `COLLECTING air/target — k left`, `ACQUIRED air
— N/N (rolling)` — and the `await_remove` label, which wrongly read `ACQUIRED —
target on (rolling)`, is corrected to `ACQUIRED target — captured, remove now`:
the target signature is frozen at `_sig_finish_target` (the `await_remove` ingest
branch never appends to the buffer), so "rolling" was misleading; only the
leading air genuinely rolls. (2) The 30 s place/remove countdowns now signal
imminent action — the B instruction flashes (yellow, turning red in the final
5 s) via a new `_sig_await_flash_timer`, and `QApplication.beep()` fires once
when each prompt first appears (`_start_await_flash`, called from
`_sig_lock_leading_air` and `_sig_finish_target`; stopped by `_stop_await_flash`
on entering target/air_trail, on abort, and on Stop). No capture/stats change.
The beep uses the OS system bell, which is silent if the desktop bell is
disabled — a guaranteed tone would need a bundled audio asset + Qt Multimedia.
Verified headless (offscreen-Qt): the subject labels render per phase, the
target-held label has no "rolling", the await flash timer is active only during
await_target/await_remove (and stops on target-entry/abort/Stop), and
`_await_flash_style` returns red for ≤ 5 s remaining, yellow above. (2026-07-22)

---

### src/pimd_classviz.py — v1.34 — Training auto-detect capture cycle

Reworks the v1.33 Training group from a manual space-toggle into an automated
cycle per Mark's bench spec. The operator presses **Space once per cycle** to
lock the leading air; target **placement and removal are auto-detected**, with
30 s guard countdowns and a Save/Ignore decision. Layout: row 1 =
Start/Stop · Frames · Settle ≤ mV · new **Detect ≥ mV** · **Space override**
checkbox; row 2 = two status areas, **A** (colored state) and **B**
(instruction); row 3 = **Save Sig / Ignore Sig** (flash while a signature is
pending). The Acquire button is gone — Space is handled in `eventFilter`.

State machine (`_sig_train_phase`): `air_lead` (roll the leading air) →
`await_target` → `target` → `await_remove` → `air_trail`. Colour ladder for the
collecting phases is remapped from v1.33: yellow SETTLING → **blue COLLECTING**
(frames-left countdown) → **green ACQUIRED** (rolling). Auto-detect
(`_current_dev_from_air`): a transition fires only when the signal is settled
(the unchanged v1.31 `_current_settle_mv` gate) AND the mean per-channel |Δ|
from the locked leading-air reference crosses **Detect** — above for placement,
below for removal — so the hand transient (unsettled) is skipped naturally. The
30 s countdowns (`_sig_await_deadline`) show in B and, on expiry, **abort** the
in-progress signature (discard slots, flash red, restart the buffer, session
stays live). The trailing air **keeps rolling** as the next cycle's leading air
(same deque, never reset across the decision), so "space locks the last N frames
prior to space" holds and after Save/Ignore the next air is already good. The
**Space override** checkbox (default on, persisted) lets Space also force-advance
any phase as a manual fallback; a `_sig_can_commit` guard (≥2 frames) stops an
override of a barely-started window from snapshotting an empty buffer.

Capture math is untouched — `_compute_sig_stats`, `central_frames`,
`compute_plateau_stats`, `quality_flags`, glitch exclusion, the channel-count
guard (DESIGN §11) and the CSV save path (`_on_sig_save_clicked`) are all reused
verbatim; Save Sig routes through `_on_sig_save_clicked`, whose training-branch
tail now retires the decision and resets the readout (works for a direct
Signatures-group Save too). Two new persisted settings: `sig_detect_mv` (0.5),
`sig_train_override` (true). Verified headless (offscreen-Qt, synthetic frames):
full auto cycle place→profile→remove→signature with rolling reuse, Save writes
CSV rows + retires the decision, Ignore writes nothing, a past deadline aborts to
`air_lead` with slots cleared, Space override force-advances every phase, and
Stop preserves an unsaved signature for a manual Save. Not verified on hardware:
auto-detect behaviour under real placement/removal transients and noise.
(2026-07-22)

---

### Repo-wide — header changelogs slimmed to a terse version lineage; CLAUDE.md rule updated

The full-prose changelog embedded in every `.py` header duplicated `CHANGELOG.md`
paragraph-for-paragraph — `pimd_classviz.py` alone carried ~500 comment lines / 35
version paragraphs before any code (mcu 323, features 191, delaycal 180, gui 101).
On a solo, AI-driven repo that is triple-bookkeeping (git + header + this file) with no
reader. Headers now carry only a terse one-line-per-version lineage under a
`# History (full detail in CHANGELOG.md):` heading; the full narrative lives here alone,
which is also the curated feed `DESIGN.md` is regenerated from. The `CLAUDE.md`
"Versioning & changelog" section was rewritten to match: version number tracks functional
change (pure doc/reformat edits don't bump), headers stay terse, `CHANGELOG.md` is the
single detailed record. Non-changelog header content (purpose, protocol/interface notes,
`pimd_features.py`'s CORPUS_HEADER schema docstring) left untouched. No functional/code
change and no per-file version bump — this is a documentation reformat. Any version whose
prose lived only in a header was migrated here first so nothing is lost: `pimd_mcu.py`
v4.00/v4.01/v4.02, `pimd_delaycal.py` v1.00/v1.01, and `pimd_gui.py` v4.00/v4.01 (all absent
from this file, which began each of those tools at the next version) are added to the
archive — mcu beside its v4.03 entry, delaycal/gui in a "migrated from file headers" block
at the foot of this file. All other files' header versions (classviz v1.00–v1.33, features
v1–v7, classify v1.0–v1.2, targets v1) were already fully covered here. (2026-07-22)

---

### src/pimd_classviz.py — v1.33 — continuous training capture (Training group, space-bar air/target toggle)

Reworks the Analysis tab's signature capture per Mark's bench feedback: the
three capture buttons (Air before / Target / Air after, v1.26–v1.32) are
replaced by a dedicated **Training** QGroupBox beside Signatures (which
keeps the file row, placement metadata, readout and Save/Delete). Start
Training begins a continuous session alternating AIR and TARGET phases,
driven by a single Acquire button that the Space bar mirrors while the
Analysis tab is visible (the app-wide eventFilter now dispatches: active
Analysis training + Analysis tab visible → Acquire, otherwise the Training
Session tab's step-advance, unchanged; starting either session while the
other runs is refused). A colored status label steps yellow SETTLING →
green COLLECTING → blue READY, reusing the v1.31 settle-gate metric
verbatim; in READY the capture window is a rolling deque so Acquire always
commits the freshest N clean frames, and losing settledness mid-window
clears the whole window back to SETTLING (a disturbance contaminates the
window — same philosophy as the gate itself). Each committed air anchor
closes the pending target (air_after → stats snapshot → readout/Save) and
immediately shifts to become air_before for the next target, so the
operator just alternates place/remove target and taps Space — the app
works out the before/after airs; the shift happens at acquire-time with a
stats snapshot (not at save-time) because Save reads only the cached stats
+ placement widgets, making the flow race-free if the next target is
acquired before Save is pressed. Save no longer resets a running session;
Stop preserves an unsaved capture's readout so it can still be saved.
Stats math (`_compute_sig_stats`), glitch exclusion (incl. the >20 %
warning), the channel-count guard (DESIGN §11) and the CSV save path are
untouched. Also: the Supply combo becomes battery/psu ('usb' removed —
bench practice has moved off USB power; a persisted 'usb' setting silently
falls back to battery), and the Repeat # spinbox + label tooltip now
explains it is provenance-only metadata (same-placement disambiguator,
auto-suggested count+1, not used in matching). Verified headless
(QT_QPA_PLATFORM=offscreen) with injected frames: full air → target → air
cycle produces correct stats and the slot shift, settle-loss clears the
window, Start refusal without an editable file, Stop preserves unsaved
stats, gating and Space dispatch behave. Not verified on hardware: live
settle behaviour under real noise. (2026-07-21)

---

### src/pimd_features.py — v7 — doc-only: supply vocabulary battery|psu

Companion to classviz v1.33 dropping the 'usb' supply option: the module
docstring's `supply` column description now reads `battery|psu` and notes
the column stays free text, so older corpora with `supply=usb` remain
readable — no validation or behaviour change. TOOL_VERSION re-synced to v7.
(2026-07-21)

---

### USAGE.md — v1.2 — §5 rewritten for classviz v1.33's Training group

Pipeline diagram and §5/§6 headings follow classviz v1.32 → v1.33 and
features v6 → v7; the Analysis-tab bullet now describes the continuous
Training workflow (Start Training, space-bar Acquire, yellow/green/blue
status ladder, shared air anchors) and the battery|psu supply vocabulary.
(2026-07-21)

---

### DESIGN.md — 1.8.2 — §15 rows for all seven previously uncited References/ images

Human-directed §15 addition (read-only rule suspended for this task per
Mark's instruction): `pcb-coil-baseline.JPEG` (pre-enclosure board-on-coil
bench setup), `warmup-with-8ns-steps.jpg` (Mode 1 warm-up with 8 ns-grid
delay steps ≈ 5 mV apart), `new-training-data.jpg` (classviz v1.32
Analysis tab, first structured-regime capture session under cal_63_air_v1),
`training-targets-v3.JPEG` (physical target set behind targets.csv), and
`training-results-v1a/b/c` (previous-epoch cal_72_air_v2 17-target family/
staircase/cosine-similarity analyses, flagged historical). Captions written
from viewing the images, not guessed from filenames. (2026-07-15)

---

### References/ — asset reorganisation committed (2026-07-13/15 epoch)

All reference images now tracked in `References/` (the former `assets/`
directory is gone). Renamed: `scope-baseline.jpeg` →
`scope-pulse-baseline.jpeg` (same image; §15 row updated at Doc-rev 1.8).
Removed: `delaycal-screenshot.JPEG`, `profile8b-air.jpg` (previous-epoch;
the remaining profile8b captures stay on disk but their §15 rows were
dropped at Doc-rev 1.8). Added, not yet cited in DESIGN.md:
`new-training-data.jpg`, `training-results-v1a.jpg` / `v1b.png` / `v1c.png`,
`training-targets-v3.JPEG`, `warmup-with-8ns-steps.jpg`. (2026-07-15)

---

### .gitignore — TODO.md private; src/data/corpora/ untracked for now

`TODO.md` joins REDO.md under # Private. `src/data/corpora/` (classviz
signature captures) stays untracked while the post-enclosure corpus rebuild
is in progress — capture files are working data until a corpus is accepted.
(2026-07-15)

---

### USAGE.md — v1.1 — delaycal version references 1.24 → 1.25

Pipeline diagram and §4 heading follow the delaycal APP_VERSION re-sync.
(2026-07-15)

---

### src/pimd_corpus_check.py — v1.4 — re-tracked in the repo (.gitignore entry removed)

Untracked 2026-07-13 as a previous-epoch ML tool alongside pimd_classify.py
and pimd_v2_findings.py, but unlike those two it has been maintained since:
v1.4 (2026-07-14) is a deliberate companion to the v1.32 target-registry
schema change, and re-homing its consistency checks onto the new
target_id/repeat_idx columns is planned work (bounded follow-up). A tool
that is current-pipeline and documented in this changelog belongs in the
repo. No code change — v1.4 content as-is; .gitignore comment notes the
re-track. pimd_classify.py and pimd_v2_findings.py remain local-only.
(2026-07-15)

---

### src/pimd_delaycal.py — v1.25 — APP_VERSION constant re-synced with header

`APP_VERSION` was stuck at `'1.19'` while v1.20–v1.24 bumped the header
changelog only, so the window title has been reporting v1.19 since. Constant
now matches the header (bumped to 1.25 for this edit per convention). No
functional change. (2026-07-15)

---

### src/pimd_corpus_check.py — v1.5 — migrate to the v1.32+ target-registry schema

Real migration onto the v1.32+ `target_id`/`distance_mm` corpus schema that
pimd_classviz.py (Training capture) and pimd_features.py (corpus builder) both
write, replacing v1.4's deliberate stopgap `SystemExit` rejection of it. The
tool now reads that schema exclusively — legacy `target`/`distance_cm` files are
cleanly rejected with a message stating support was intentionally dropped (the
previous-epoch corpora were reset, so there is nothing legacy left to validate).
`load_corpus()` regroups per-cell rows into one signature per `(session,
capture_id)` and sorts each capture's cells by `pulse_us` then descending
`threshold_v` — the same regrouping as `pimd_classviz._scan_editable_signature_
file()` — and asserts the header carries `pimd_features.CORPUS_HEADER_FIELDS`.
The old `sniff_format`/`load_long`/`load_wide`/`dist_key` and the wide-format
path are gone.

Check changes: (1) the **canary-consistency check is retired entirely**
(`check_canary`/`strip_canary_suffix`/`CANARY_SUFFIX_RE`/`CANARY_*` removed, plus
its `CHECK_ORDER` entry) — per-capture air-before/after bracketing now does the
drift *correction* automatically in `pimd_features`, so the canary's audit role
is subsumed by the structured repeat check. (2) **Repeat consistency now keys
off the `repeat_idx` column**, not a `(rpt)` name suffix: captures are grouped by
the physical placement tuple `(target_id, distance_mm, long_axis, face_normal,
offset_x_mm, offset_y_mm, medium)` (mirror of `_placement_tuple_key`),
`repeat_idx == 1` is the base and `repeat_idx >= 2` are repeats compared against
it; this subsumes the old within-session and cross-session repeat checks in one
(the placement tuple is session-independent). A repeat with no base emits a
clear SKIP. `REPEAT_MARK_RE`/`find_repeat_base`/`check_repeat_cross_session` are
gone. (3) **Distances are data-driven** — a physical target (placement minus
distance) seen at ≥2 distances gets shape-invariance rows, ≥3 gets a falloff fit;
the hardcoded 5/10/15 cm logic is generalised to whatever `distance_mm` values
were captured, with a near-field/far-field split preserving v1.3's AMBER verdict
and all labels in mm. (4) **Cross-campaign** keys by the stable `target_id` (not
free-text name) per `(target_id, distance_mm)`, and joins the registry
(`pimd_targets.load_targets`, best-effort/optional) for a material-class label.

Verified: `py_compile` clean; runs against the real
`src/data/corpora/gui_signatures_*.csv` files printing the check table with no
`SystemExit` and no canary rows; the `repeat_idx` repeat path, orphan-repeat
SKIP, cross-campaign `--baseline` match, distance-falloff (r^-2 fixture → n=2.00)
and the AMBER near-field path were each exercised; a legacy `target`/
`distance_cm` file is cleanly rejected. (2026-07-22)

---


## Archive — consolidated 2026-07-15

### USAGE.md — v1 — new single-file usage guide; docs/ directory removed

New top-level USAGE.md: intent, operation and pipeline flow for every app —
overview/pipeline, pimd_mcu (fw v4.26), pimd_gui (v4.13), pimd_delaycal
(v1.24), pimd_classviz (v1.32), and the corpus pipeline (pimd_features v6 +
pimd_targets v1) — one page per app, versions taken from current source
headers. Replaces the five docs/ files (PIMD.md and the four per-tool cheat
sheets), which had drifted stale (mcu doc said v4.23, classviz v1.15,
delaycal v1.19, and the classviz sheet still described the removed Profile
Builder tab); `git rm -r docs/`. Facts point to DESIGN.md rather than
duplicating measured values. (2026-07-15)

---

### README.md — docs/ references repointed to USAGE.md

Repository-layout block, protocol note (now points at DESIGN.md §9),
Documentation list and the CC BY-SA licence scope updated from the removed
docs/ directory to USAGE.md. (2026-07-15)

---

### .gitignore — private-notes ignore renamed MM-NOTES.md → REDO.md

The private working-notes file was renamed by Mark; the ignore entry follows.
The `assets` entry is retained (directory currently deleted, may be
recreated). (2026-07-15)

---

### src/pimd_corpus_check.py — v1.4 — loud rejection of the v1.32+ target-registry schema

Companion to the target-metadata capture regime (pimd_classviz.py v1.32,
pimd_features.py v6): `sniff_format()` now detects a `target_id`/
`distance_mm`-schema file and raises `SystemExit` immediately, naming the
file and stating this tool doesn't support it yet. Without this, such a
file still passes the existing 'long'-format check (`pulse_us`/
`threshold_v`/`delta_mV` are unchanged column names) and only fails much
later with an opaque `KeyError` inside `load_long()`'s
`groupby(['session','target','distance_cm'])`, since those two columns no
longer exist. Deliberately **not** a full migration — a scope decision,
not an oversight: this tool's canary-consistency (`CANARY-START`/`END`
suffix matching on the target name) and repeat-consistency
(`REPEAT_MARK_RE`/`(rpt)` suffix, same column) both encode metadata into
the free-text target string, which the new schema replaces with a stable
`target_id` plus a separate structured `repeat_idx` column — re-homing
those checks onto the new columns is a real but bounded follow-up task,
deferred rather than bundled into this change. Old `target`/
`distance_cm`-schema files are completely unaffected; every existing
check still runs exactly as before (verified: a hand-built old-schema
fixture produces the same check table/exit behavior pre- and post-change).
`_on_sig_open_for_edit_clicked()` in `pimd_classviz.py` already wraps its
`sniff_format()` call in a `try/except SystemExit` and surfaces the
message in the status bar, so this fix also improves that call site for
free, with no code change needed there. (2026-07-14)

---

### src/pimd_classviz.py — v1.32 — structured target-metadata capture regime (registry-backed Analysis/Training capture)

Replaces the Analysis tab's free-text target field + distance_cm spinbox
with a registry-backed target combo (`pimd_targets.py`) plus structured
placement (distance_mm/long_axis/face_normal/offset_x_mm/offset_y_mm/
medium/repeat_idx/notes), built once by a new shared
`_build_target_placement_widget_set()` and reused both inline (Analysis
tab) and inside a new Training-tab "Placement…" dialog — one
implementation, not two. New `_load_targets_registry()` covers a
missing/broken registry: missing file → air-only with a status-bar
message; load errors → a dialog plus only the non-erroring targets
selectable; warnings-only → status-bar summary, fully populated. A
"Reload targets" button re-runs it on demand.
`gui_signatures_*.csv`'s column set moves to `pimd_features.py` v6's new
`CORPUS_HEADER` end-to-end (`target`/`distance_cm` dropped, not aliased)
and is now written via `csv.writer(QUOTE_MINIMAL)` instead of hand
comma-joining, since `notes`/`short_name` are free text and will contain
commas — `_scan_editable_signature_file()`'s grouping key also moves from
`(session, target, distance)` to `(session, capture_id)`, and the old
visit-count `(rpt)`-suffix scheme is replaced by a `repeat_idx`
auto-increment keyed on the full placement tuple (still user-editable).
A new `# mark_target:` session-dump comment line is written alongside the
existing `# mark:` line (byte-identical, untouched — zero risk to
`pimd_features.py`'s existing consumers) for both the Training tab's
row-advance marks and the Analysis tab's session-mark button, carrying
the same structured fields `pimd_features.py` v6 now parses. Training-tab
table: "Target" column becomes "Target ID" (validated against the loaded
registry, `_validate_training_table()` red-flags unknown ids), "Distance"
becomes mm; a new per-row `_training_row_placement` dict (keyed by a
stable token surviving Add/Remove Row, not row index) holds the remaining
placement fields, edited via the new Placement dialog. Training-list JSON
rows without `target_id` are loudly rejected on load, not migrated — the
4 existing `learn-v2-*.json` lists (old `target`/`distance_cm` schema)
need manual re-authoring against the registry as a follow-up.
New session-level `Supply` combo (battery/usb, top bar, DESIGN §12) feeds
both capture paths and is embedded in session-dump headers
(`# supply:`). `profile_sha8` (first 8 hex chars of SHA-256 of the
literal loaded profile JSON bytes) is computed once per profile load
(`_set_profile_dims`, now also caching the raw bytes via
`_load_profile_file`'s new `(profile, raw_bytes)` return) and threaded
through both capture paths and into session-dump headers
(`# profile_sha8:`); the built-in `_default_profile()` fallback (no file
on disk) uses a documented canonical-JSON surrogate since there's nothing
to hash literally. `fw_version` is parsed read-only from the existing raw
V-identify reply (`_parsed_fw_version()`), no protocol change. Settings
persistence of last-used `target_id` + placement is added, reversing the
v1.11-era "don't persist target/distance" decision — safe now because the
registry-validated combo makes a dangling `target_id` detectable (a dict
lookup against the freshly-loaded registry) and falls back to `air`
silently on a miss, rather than restoring stale free text.
Verified headless (`QT_QPA_PLATFORM=offscreen`): MainWindow construction,
registry load/degrade paths, a full Analysis-tab save (registry join,
quoted-comma notes round-trip through `_scan_editable_signature_file`,
`repeat_idx` auto-increment across two saves, delete), Training-tab
validation (unknown target_id rejected, missing air row rejected),
mark-target dict construction, list save/load round-trip, legacy-schema
list loud rejection, the Placement dialog's read-back into both the table
and the stored dict, and settings persistence including the
stale-target-falls-back-to-air path. Not verified (needs a physical
board or a mocked serial-frame injector): the live settledness-gated
capture flow itself and `fw_version` from a real `V` reply.
(2026-07-14)

---

### src/pimd_features.py — v6 — structured target-metadata capture regime (registry join + geometry guard rewrite)

Replaces the free-text `target`/`distance_cm` corpus columns with a
registry-backed `target_id` plus structured placement
(distance_mm/long_axis/face_normal/offset_x_mm/offset_y_mm/medium/
repeat_idx/notes) and capture provenance
(profile_name/profile_sha8/fw_version/tool_version/supply) — see
CORPUS_HEADER/JOINED_CORPUS_HEADER in the module docstring for the exact
column list. `Plateau` is redesigned around target_id/placement instead of a
free-text label; a plateau with no resolvable target_id (a no-marks
change-point segment, or an old-style '@distance' mark with no structured
`mark_target:` companion line) is loudly warned and excluded from output —
there is no free-text → target_id migration path, by design. New
`mark_target:` comment-line parsing is additive alongside the existing
`mark:` line (untouched, so pre-v1.32 session dumps stay readable);
`segment_from_marks()` nearest-timestamp-matches the two and retires the old
visit-count `(rpt)`-suffix scheme in favor of the structured `repeat_idx`
column. The profile-geometry gate is no longer a `--profile` reference-file
comparison that `[SKIP]`s mismatches (`load_reference_profile`/
`validate_profile`/`DEFAULT_PROFILE`/`--profile` removed) — every input
file's `(profile_name, profile_sha8)` is now grouped, and a corpus build
spanning more than one group is a hard error naming every offending file.
`profile_sha8` is SHA-256 of the profile JSON bytes as loaded, truncated to
8 hex chars; classviz computes and embeds it directly (a new
`# profile_sha8:` session-dump header line, or a literal gui_signatures
column) since only classviz has the literal loaded bytes — a session dump's
embedded `# profile_json:` text is a re-serialization that would hash
differently, so re-hashing it here is only a fallback for dumps predating
that line. New direct-ingest path for classviz's `gui_signatures_*.csv`
files (already at full per-cell granularity — no segmentation math, just
registry join); a pre-v1.32 file (`target`/`distance_cm` columns) is a hard,
clearly-worded error, no migration code. Unknown `target_id` is a hard
error naming the file and id; registry errors abort the whole run before
any file is processed. Row writing switches from hand `','.join()` with a
comma→semicolon replace to `csv.writer(quoting=QUOTE_MINIMAL)`, since
`notes`/`short_name` are free text and will contain commas — an intentional
on-disk convention change. No-marks change-point sessions can no longer
produce named corpus rows (a `segment_NN` placeholder was never a valid
registry `target_id`) — flagged as a real, forced consequence of the schema
redesign, not a bug. Verified against synthetic session-dump and
gui_signatures fixtures: registry join, quoted-notes round-trip, the
geometry guard (two sessions with different profile_sha8 correctly
refused), and the unknown-target_id and legacy-schema hard errors all fire
correctly; `pimd_corpus_check.py` is deliberately left unmigrated (see its
own changelog entry) — building a corpus from new-schema inputs works, but
`pimd_corpus_check.py` won't yet accept the result. (2026-07-14)

---

### src/pimd_targets.py — new — shared target registry loader/validator (v1)

New module: loads and validates `data/training_lists/targets.csv` (23
human-authored target objects), shared by `pimd_classviz.py` and
`pimd_features.py` as the single source of target physical metadata. Reads
and validates only — never writes the registry, which is human-owned data.
Errors: missing/misordered required column, empty/duplicate `target_id`,
`target_id` not matching `^[a-z0-9_]+$`, unparseable numeric, enum value
outside the documented sets. Warnings: dims not sorted
(`dim_a >= dim_b >= dim_c`), `wall_thickness_mm` present on a shape outside
the expected hollow-section set, `closed_loop=y` on a non-conductive
material, and a mass-plausibility check (`mass_g` vs. `1.05 ×
density × bounding-box volume`, converting mm³→cm³ before applying the
g/cm³ density table). CLI (`python pimd_targets.py [--registry PATH]`)
prints the full target table plus every issue found, exit 1 on any error,
0 on warnings-only. Verified against the real registry: correctly surfaces
`brass_block_01`'s dims-unsorted and mass-implausibility warnings and
`ferrite_toroid_01`'s closed_loop-on-non-conductive warning (plus several
legitimate bonus warnings on `cu_crimps_01`/`shackle_01`/`magnet_nd_01`),
0 errors, exit 0; a hand-crafted malformed registry (duplicate id, bad
regex, missing column, bad enum, unparseable numeric) correctly surfaces
all 5 planted errors in one pass; a missing `--registry` path produces a
clean error message and exit 1. (2026-07-14)

---

### src/data/profiles/cal_63_air_v2.json — new — locked; fresh soaked recal under fw v4.26

New locked operating profile from the 2026-07-14 delay recalibration (fully
warmed, fw v4.26). Same band plan and threshold ladder as cal_63_air_v1;
delays re-anchored — shifts of −56…+16 ns vs v1, heavy bands earliest
(thermal signature, decays arrive earlier warm). This retires the drift
that had pushed the 100 µs / 4.70 V cell onto the ~4.67 V upper edge of the
§17.7 threshold noise zone (σ 2.7 mV in session B); bench-confirmed fixed.
The delaycal export contained the full 8-band plan; the 6 µs / 50 kHz band
was stripped per the cal_63_air_v1 rationale before locking, and the name
field normalised. Same cell geometry as v1 but different delays — treat as
a new calibration epoch for corpus purposes. (2026-07-14)

---

### Bench observations — 2026-07-14 — fw v4.26 A/B verified; 100 µs / 4.70 V cell has drifted to the noise-zone edge

A/B session recordings under cal_63_air_v1 (`sessions/A.csv` fw v4.25
114 frames, `sessions/B.csv` fw v4.26 134 frames, ~10 min apart):

- **v4.26 fix verified.** Channel 1 (band 1, cell 2): σ 3050 → 284 µV.
  Discrete corruption events (single-frame jumps in the 32-deep rolling
  mean, threshold 400 µV ≈ a 13 mV single sample) fell from 9 per 114
  frames — up to ±5.7 mV jumps, i.e. single samples ~180 mV off — to 1
  small event (−477 µV) per 134 frames. The residual matches the low-rate
  ~±13 mV background events also seen on ch9/ch54/ch55 (1–6 each per
  session, both firmwares), so the CC-write race is closed; occasional
  live sightings of a small flicker at that cell are this background, an
  order of magnitude smaller and rarer than before.
- **New dominant σ cell is NOT a firmware artifact.** ch56 (100 µs band,
  4.70 V column, delay 7.6 µs): σ 605 (A) → 2693 µV (B). Its events are
  quantized at ±~2.0 mV in the rolling mean = single samples of ±64 mV,
  identical size under v4.25 (1 event) and v4.26 (10 events) — a
  pre-existing bimodal phenomenon whose RATE changed, not a new mechanism.
  Cause: operating-point drift into the §17.7 threshold noise zone. The
  cell is calibrated to sample at 4.70 V but sits at 4.673 V (A) / 4.669 V
  (B); heavy bands have drifted −20…−31 mV below nominal (monotonic with
  pulse width — thermal signature), light bands +9 mV high. Going 4.673 →
  4.669 V took the event rate 1 → 10 per session: the zone's upper edge is
  sharp and sits near ≈ 4.67 V on this band (the 2026-07-13 mapping used
  37.5 mV steps — 4.700 clean, 4.625 elevated — so an edge at 4.67 is
  consistent with it). The ±64 mV two-state character suggests the zone
  mechanism is discrete (ringing-phase-like), not broadband; mechanism
  still unknown (§14.7).
- **Follow-ups:** (1) confirm thermal state / warm-up and re-run delaycal
  fully soaked so the 4.7 V column re-anchors; (2) consider fine-mapping
  4.65–4.70 V on the heavy bands to locate the zone edge; (3) if the edge
  crowds 4.70 V warm, move the third threshold up (e.g. 4.75 V) in the
  next profile rev; (4) watch item: ch9 (13.44 µs band, first cell) shows
  6 small quantized events per session under v4.26 — band-head related,
  minor. (2026-07-14)

---

### mcu/pimd_mcu.py — v4.26 — post-emit IRQ burst mis-timed cell[1]'s CC write (channel-1 σ anomaly)

Root cause of the index-locked σ anomaly on the Analysis heatmap: channel 1
(band 1, cell 2) showed ~8× the σ of its neighbours, and stayed at the same
heatmap position when the first band changed from 6 µs/50 kHz (v3 profile)
to 9 µs/25 kHz (cal_63_air_v1) — i.e. locked to sweep position, not to the
physical band. PC side ruled out (the σ heatmap is a uniform per-channel
std over unfiltered W frames); the v3-era corpus
(`gui_signatures_20260713_212807.csv`) independently shows gross mean bias
at sweep positions 0–1 (e.g. copper ch1 +15.5 mV against a −1.2 mV band
trend). Mechanism: the W-record `print()` at sweep index 0 leaves USB CDC
TX-drain IRQs pending; `read_raw_sample()` re-enables IRQs immediately
after the SPI read, so at i==1 the queued burst (10–50 µs each, v4.21
measurement) fires exactly between the read and cell[1]'s `duty_u16` write
— and the outlier-gate/rolling bookkeeping added tens of µs of interpreter
time in the same gap for every cell. The RP2040 CC register is not
double-buffered (v4.13/v4.04): a write landing past the wrap leaves the
next conversion sampling at the previous cell's compare point (112 ns early
on the steep 4.8–4.9 V decay ≈ +100 mV raw — inside the outlier gate),
poisoning rolling[1] every sweep. The 6 µs band's 20 µs period gave the
tightest write budget of all bands — likely a contributor to its
"notoriously noisy" reputation. Fix: new `read_raw_bytes_hold()` keeps IRQs
disabled from the BUSY-synced read through the freq/CC writes (~2–6 µs on
top of the ≤36 µs v4.21 blackout), bookkeeping moved after the hardware
writes (the two identical branch copies deduplicated into one), decode
split into `raw14_from_bytes()` shared with `read_raw_sample()`. Read still
precedes all CC writes (v4.13). Needs bench A/B: channel 1's σ should
collapse to ~100 µV; `overrun_count` (B command) should not grow faster
than on v4.25. (2026-07-14)

---

### src/data/profiles/cal_63_air_v1.json — new — 6 µs band dropped from the operating profile

New operating profile derived from `cal_72_air_v3` (locked 2026-07-13): the
6 µs / 50 kHz band is removed on bench judgment — it contains no additional
target information not already present in the other bands and is notoriously
noisy. The remaining 7 bands are byte-identical to v3 (delays from cal run
`cal_20260713_210057`, top-dense threshold ladder 4.9 → 0.5 V), giving
7 bands × 9 delays = 63 cells. Shipped as a new file rather than an in-place
edit of v3 because the profile is the firmware↔ML contract (DESIGN §10) and
signature captures already exist under the v3 geometry — frames must never be
mixed across the two. `cal_72_air_v3.json` is retained unchanged as the
superseded locked profile. A `notes` field in the JSON records the rationale
(all loaders read only `averages`/`bands`; extra keys are ignored, and all
runtime code is geometry-driven, so no code changes were needed). (2026-07-14)

---

### mcu/pimd_mcu.py — v4.25 — outlier gate could permanently latch small-signal cells

Root cause of the "last cell flat at zero regardless of target" seen on the
Analysis-tab grids (channel 72 of cal_72_air_v3 — 100 µs band, 11.264 µs
delay, the deepest-decay cell): the v4.21 plausibility gate rejects samples
deviating more than `mean_raw // OUTLIER_GATE_FRAC` from the rolling mean,
but raw14 is signed. For a near-zero mean the threshold floors to 0 (any
nonzero deviation rejected); for a negative mean, floor division makes the
threshold negative, so `dev ≥ 0` always exceeds it and every sample is
rejected. The substituted mean is written back into the rolling buffer, so
once count ≥ 8 the cell freezes at its warm-up value forever — the plotted
baseline-delta is exactly 0 no matter the target. Fix: gate on
`abs(mean_raw)` with an absolute floor `OUTLIER_GATE_MIN = 164` raw14 counts
(≈ 100 mV, 1 % FS) — the bit-truncation glitches the gate exists for are
volts-scale and still caught, but a cell can no longer latch. Needs bench
verification: flash, run the operating profile, confirm the last cell tracks
a target. (2026-07-14)

---

### README.md — profile references updated to cal_63_air_v1 / 63 cells

Mode 2 description, highlights, bench-test example and Phase 3 roadmap
updated from `cal_72_air_v2` / 72 cells to the new `cal_63_air_v1` 63-cell
profile (6 µs band dropped, top-dense 4.9 → 0.5 V threshold ladder, keep-out
zone noted). Historical image caption and docs/PIMD.md's demo-profile band
table left unchanged — they describe profiles that really did have the 6 µs
band. (2026-07-14)

---

### src/pimd_classviz.py — v1.31 — Analysis-tab signature captures hardened to pipeline rigor

The first post-enclosure corpus test run (gui_signatures_20260713_212807.csv,
7 captures) showed split-half SNR of only 5–7 on several targets while the
best captures hit 10–20. The stats/baseline math is shared verbatim with
`pimd_features.py`, so the gap was in window collection, where the GUI
quick-capture skipped two robustness steps the session pipeline applies:
frames were collected the instant a capture button was pressed (the pipeline
trims `settle_s` = 2 s after every mark; the firmware's 32-deep rolling
average ramps for ~10 s after a target change, and ramp inside a window
inflates `splithalf_floor` directly since it compares first half vs second
half), and the window took raw unfiltered frames (the 64-frame-median glitch
mask was display-only; the pipeline drops flagged frames via
`drop_flagged()`). Two additions: (1) a settledness gate — pressing a
capture button now shows "Settling… X.XXX mV" and collection only opens once
the mean per-channel rolling std (the Training tab's Settledness metric,
window = the Stats tab's shared "Std dev N") drops to the new
"Settle ≤ (mV)" spinbox threshold (default 1.0 mV, persisted as
`sig_settle_mv`, raise to 50 to disable); (2) glitch-flagged frames are
excluded during collection and the window keeps filling until N clean
frames, with a status-bar warning if more than 20 % were skipped. Clicking
the active capture button now cancels the capture (no cancel existed).
Verified with an offscreen-Qt simulation: gate holds under 5 mV noise, opens
at 0.3 mV, an injected 500 mV glitch frame is excluded while the window
still reaches N clean frames, the >20 % warning fires, and cancel resets
state. (2026-07-13)

---

### src/pimd_targets.py — new — v1: shared target-registry loader/validator

New module, first of a three-file change replacing free-text `target`/
`distance_cm` capture metadata with a structured `target_id` + placement
regime (mission: rebuild the post-enclosure ML corpus from zero against
`src/data/training_lists/targets.csv`, the new human-maintained registry of
23 physical target objects). `load_targets()` parses the registry with the
`csv` module (not a hand `split(',')` — the file has a quoted comment line
containing a literal comma) and validates every row, collecting every issue
rather than stopping at the first: hard errors for missing/duplicate/
malformed `target_id`, unparseable numerics, and enum violations; warnings
for unsorted dims, `wall_thickness_mm` on an unexpected shape, `closed_loop`
on a non-conductive material, and mass implausible for the material's
density vs. the bounding box. Verified against the real registry: 0 errors,
7 warnings, including the three the task explicitly called for
(`brass_block_01` dims-unsorted + mass, `ferrite_toroid_01` closed_loop on
ferrite) plus four more genuine ones the generic rules also catch
(`cu_crimps_01`'s wall_thickness/mass on a `collection` shape,
`shackle_01`'s wall_thickness on an `irregular` shape, `magnet_nd_01`'s mass
narrowly exceeding its bounding-box limit). Also exercised against
hand-crafted malformed CSVs (bad id regex, duplicate id, empty id, bad enum,
short row, unparseable numeric) to confirm every error branch fires
correctly — an early cut treated any row with a blank first field as a
blank line, which silently ate the "empty target_id" error case entirely;
fixed to only skip rows where every field is blank. CLI:
`python pimd_targets.py [--registry PATH]`, prints a target table + all
issues, exit 1 on any error. Registry path note: the task brief named
`src/data/targets.csv`; the real, human-created file is at
`src/data/training_lists/targets.csv` (confirmed via `git status`) — this
and the other two files in the change use that real path as the shared
default. (2026-07-14)

---

## Archive — consolidated 2026-07-13

### Bench observations — 2026-07-13 — fw v4.24 verified; noisy threshold zone is ~4.45–4.65 V, not the whole top of the range

fw v4.24's time-floored boundary settling is confirmed on hardware: the
first-column noise (elevated σ in the first cell of each band regardless of
calibrated voltages, wandering on a seconds timescale) is gone.

With the position-dependent artifact removed, the remaining noise is tied to
the absolute threshold *voltage*, not the column position — but NOT as a
simple "avoid the top of the range" rule. Two captures:

1. Coarse list 4.90/4.80/4.70/4.50/3.80/3.20/2.40/1.50 V
   (`assets/Screenshot_2026-07-13_17-26-53.jpg`): the 4.50 V column is the
   noisiest across multiple bands (up to ~1.2 mV σ); 3.80 V down uniformly
   quiet.
2. Fine sweep 4.700 → 4.400 V in 37.5 mV steps, all 8 bands
   (`assets/Screenshot_2026-07-13_17-33-36.jpg`): the *endpoints* are clean —
   4.700/4.662 V and 4.438/4.400 V mostly ≤ 0.5 mV σ — while the interior
   4.625–4.513 V columns carry the noise (σ 0.5–2.24 mV, worst 2.24 mV at
   30 µs / 4.588 V and 1.85 mV at 100 µs / 4.513 V, elevated in nearly every
   band). The bad zone is roughly **4.45–4.65 V**; values above it (4.7, 4.8,
   4.9) and below it (≤ 4.4) both perform well.

This refines the earlier anchor-step-down story (4.8 → 4.5 → 4.2 V, DESIGN
§10/§17.5): the top of the curve is not inherently noisy — 4.5 V simply sat
inside this newly-mapped bad zone. The high-voltage/early-decay region is
informative and worth sampling: a reverse-geometric target progression
(steps densest near the top) gives more consistent patterns, and a list with
4.8/4.7/4.3/4.0 in the top region performs well. Practical rule for
calibration target lists: sample the top freely but keep targets out of
~4.45–4.65 V. Mechanism of the bad zone not yet identified (clamp-release
region; further tests planned). (2026-07-13)

---

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

### src/pimd_delaycal.py — v1.24 — Auto Nudge: down-only search past the signal-detect ceiling

Auto Nudge's zigzag search (v1.20) could keep alternating +offset/-offset
attempts even after a nudge pushed a channel's monitored voltage up to the
signal-detect ceiling (sp_signal_v, default 4.9 V — the same threshold used
by the coarse hunt, v1.15, to mean "no real signal present"). Once mean_v on
a channel reaches that ceiling, further +offset nudges just walk deeper into
no-signal territory, so it's a wasted (and potentially misleading) attempt.
New `_auto_check_ceiling(ch, mean_v)` latches a per-channel
`_auto_ceiling_flat` flag the first time this happens, and `_auto_nudge_channel()`
now checks that flag: once set, it drops the alternating sign and forces all
subsequent nudges for that channel to `-1` (down), with the magnitude
(`_auto_down_mult_flat`) continuing to grow by one nudge-step each attempt
from wherever the zigzag left off — no repeats, no jumps. Wired into both
evaluators (`_auto_evaluate_channel` for Sequential mode,
`_auto_evaluate_parallel` for Parallel mode). (2026-07-13)

---

### src/pimd_classviz.py — v1.30 — Fix: noisy reference cell contaminating whole-band normalize

User reported the Analysis tab's 8-grid (Per Pulse Width Cell Profiles)
showing ±5-10mV swings concentrated in the 9µs/13µs band panels, while Band
Mean vs Time showed only ~100µV of oscillation over the same period —
suspected as a bug. Investigation (code tracing, then 3 live screenshots
taken ~1 minute apart) found the data pipeline, reshape, and band/cell
ordering all correct; the swings traced to one genuinely noisy channel —
band=9µs, cell=0 (shortest delay / highest threshold) — independently
confirmed as the single highest-std-dev cell in the entire 8×9 grid via the
v1.28 Std Dev heatmap mode. That same cell is the literal subtraction
reference for `_normalize_group()`'s "Auto (− first element)" mode, shared
by the strip/chart2/8-grid/9-grid charts — so that one cell's frame-to-frame
jitter was being imposed at full strength onto every other point in its
group, producing the "whole curve translates as a block" pattern the user
correctly identified as diagnostic. Not a software defect — normalization
was doing exactly what it was built to do, against a genuinely noisy
reference — but worth hardening: `_normalize_group()`'s Auto mode now
subtracts the group's own mean instead of its first element, diluting one
outlier's contribution by ~1/group-size (verified: a 3.0mV reference-cell
jump between two frames now only moves its bandmates by ~0.33mV, down from
the full 3.0mV before) while still auto-zeroing each curve for at-a-glance
comparison. One shared `@staticmethod` fixes all four live-data consumers
plus the signature template-overlay path (same helper) in a single edit;
renamed the four "Auto (− first sample/point/cell/band)" checkbox labels to
"Auto (− group mean)" to match. No settings-persistence keys changed.

### src/pimd_classviz.py — v1.29 — Analysis heatmap colorbar legend + interactive range

Added a horizontal `pg.ColorBarItem` legend below the Analysis tab heatmap's
x-axis (via `setImageItem(insert_in=analysis_plot)`), answering "match value
with colour" — and, since the user asked for something that also lets them
set a threshold, made it double as an interactive range control: dragging
its handles sets the image's levels directly. This slots into the existing
Auto/Manual scale convention already used throughout the Analysis tab — the
Auto branch still recomputes and drives both the image and the bar every
redraw tick as before, but the Manual branch now leaves levels alone
(`autoLevels=False`) so a drag, or a typed value in the pre-existing
manual-range spinbox, survives across ticks instead of being stomped ~30x/
sec; a new `sigLevelsChanged` handler mirrors a drag back into the spinbox
and `_analysis_hm_manual_range_uv` so both stay consistent and the chosen
range persists across a settings save. Along the way, worked around a
pyqtgraph 0.14 quirk: `ColorBarItem.setImageItem()` calls the image's
`setLevels()` before it has any data, which pyqtgraph defers
(`ImageItem._defferedLevels`) and replays at the end of the *next*
`setImage()` call — silently clobbering the first real frame's computed
levels back to the colorbar's construction-time placeholder. A throwaway
zero-filled `setImage()` immediately after linking flushes that deferred
replay before any real data arrives, so the first live frame renders with
correct levels instead of a one-tick flash of the wrong scale.

### src/pimd_classviz.py — v1.28 — Heatmap Std Dev display mode + live throughput readout

Two additions. (1) A "Std Dev (rolling N)" display mode, added alongside the
existing Δ deviation/Z normalised/RAW abs modes on both the main Heatmap tab
and the Analysis tab's decoupled heatmap variant — shows each cell's
raw-signal std dev over the last N samples as a live noise/jitter monitor,
independent of any baseline capture. N is the Stats tab's existing "Std dev
N" spinbox (`sp_stats_window`), now documented as shared via tooltip rather
than duplicating a second N control; a new `_compute_rolling_stddev_nxn()`
reuses `_update_stats_table`'s exact rolling-window computation so the
heatmap and stats-table std dev always agree for the same N. Rendered with
the same sequential colormap and 0…max autoscale convention as RAW mode.
(2) A top-bar "Rate: X.X Hz (Y cells/s)" readout, visible on every tab
regardless of which is active, recomputed once/sec from an exact
frames-received-in-the-last-second delta (not a smoothed average, so a
stall reads as 0 Hz immediately instead of decaying into view) — added to
answer whether Mode 2 streaming is actually running at its ~100 Hz nominal
rate or has stalled somewhere. `read_from_serial()` now also counts how
many complete lines it drains in a single `readyRead` callback; a burst
of more than 3 (the GUI briefly falling behind the incoming stream between
events, with lines queuing up in Qt's internal serial buffer) appends a
"⚠ burst×N" warning to the readout instead of that backlog going unnoticed.

### src/pimd_classviz.py — v1.27 — Analysis tab: left-column grouping + 3-row right side

Cosmetic-only regrouping of the Analysis tab, no data/logic changes. The
Controls and Signatures boxes used to span the full tab width above
everything else; they now stack with the Heatmap group in one resizable
left column sharing the heatmap's width (reusing the existing `main_split`
`QSplitter`, previously the heatmap was its sole left-pane widget). That
frees the right side to start at the top of the tab and reorganizes its 4
stacked chart rows into 3: row 1 is a new nested horizontal `QSplitter`
holding "Band Mean vs Time" and "Pulse Width Mean" side by side (previously
2 separate stacked rows), rows 2/3 stay the unchanged 8-grid/9-grid.
Several rows in the narrower Signatures box (files, capture-inputs,
readout-save, session) and the two row-1 chart control rows (strip,
chart2 — now roughly half their old width) were wider than the columns
they'd land in; Qt's per-row minimum-content-width would otherwise refuse
to let the splitter shrink that far, so each of those rows was split onto
two stacked sub-rows to make the width reduction real instead of blocked.

### src/pimd_classviz.py — v1.26 — Analysis tab: settings persistence + in-GUI signature editor

Two additions. (1) All ~20 existing per-group Auto/Manual normalize+scale
controls (plus Avg N frames and the new signature capture-N) now persist to
`classviz_settings.json` and reload on launch, matching the convention
already used by `pimd_classify.py`/`pimd_delaycal.py` and this file's own
Heatmap-tab controls — the Analysis tab was the one place in the app that
still reset to defaults every restart. (2) An in-GUI signature file editor,
as a faster interactive alternative to the existing Record Session →
`pimd_features.py` CLI pipeline: "New file…"/"Open for editing…" make a
corpus CSV the active editable target (the existing read-only "Load
signatures…" stays browse-only — a loaded reference corpus and an active
editable file now coexist in one list, both overlay-able, since comparing a
new capture against an already-loaded reference was the point); "Capture Air
(before)"/"Capture Target"/"Capture Air (after)" capture a live N-frame
window into each of 3 slots (air-after optional — with only air-before, the
baseline flat-extrapolates, the same single-anchor fallback
`pimd_features.py` itself already has); "Save Signature" reuses
`pimd_features.Plateau`/`central_frames`/`compute_plateau_stats`/
`quality_flags`/`build_rows` verbatim to compute a real
`plateau_amp_mV`/`splithalf_floor`/`quality` from that live window, linearly
interpolating between the air anchors by timestamp like the CLI's own
thermal-drift correction — over a live 1-2 point window instead of a whole
recorded session's air visits, a real rigor trade-off flagged to the user
rather than presented as equivalent. "Delete Selected" only allows deleting
from the active editable file, by literal on-disk
`(session,target,distance_cm)` string match (not
`pimd_corpus_check.load_long()`'s `dist_key()`, which lossily casts distance
to `int`). Repeat target+distance saves in the same file auto-suffix
`(rpt)`/`(rpt3)` matching `pimd_features.segment_from_marks()`'s convention.
New files default into a new `data/corpora/` dir; GUI-captured signatures get
a `gui_YYYYMMDD_HHMMSS` session-id stamp so they're distinguishable from the
CLI pipeline's `session_...` stamp in any future audit. The signature list
now shows amp/SNR/quality per row (previously read from the file and
silently discarded) and shrank to a compact scrollable list to make room for
the new controls. Also added a peer alternate path — Session:
Start/Pause/Stop/Mark — recording a full raw session CSV byte-identical to
the Training Session tab's own output, for later conversion through
`pimd_features.py` exactly as today, driven from the Analysis tab's live
charts instead of the separate guided-list workflow; reuses
`_session_start`/`_session_write_row`/`_session_stop`/`_append_mark`/
`self._recording`/`self._training_paused` verbatim, so only one of the three
recording entry points (Stats tab, Training Session tab, Analysis tab) can
be active at a time. (2026-07-12)

### src/pimd_classviz.py — v1.25 — Analysis tab: relayout, single averaged strip, chart-2 controls

More bench feedback on the Analysis tab: (1) "Band Mean vs Time" moved above
"Pulse Width Mean" in the right-hand column and collapsed from two strips
(highest/lowest pulse width) to one showing the whole matrix's average
delta_mV vs time, with its own Auto/Manual normalize + Auto/Manual scale
controls and a Reset time button, matching the other chart groups — its
corpus overlay is now one reference line (the template's overall average)
instead of two per-band lines. (2) "Pulse Width Mean" (chart 2) gained the
same Auto/Manual normalize+scale controls as the two grids — previously
always auto-normalized with no manual override. (3) The 5 chart areas
(heatmap + the 4 in the right column) now fill all remaining vertical space
under the Controls box, no separate bottom section. (4) Renames: "Per-Band
Cell Profiles" → "Per Pulse Width Cell Profiles", "Per-Cell Band Profiles" →
"Sample Delay Band Profiles", "Band Mean vs Pulse Width" → "Pulse Width
Mean". (5) 8-grid's first panel no longer shows an x-axis title; 8-grid/
9-grid's first panel and chart 2 no longer show a y-axis label ("norm.") —
ticks still render, just without the title text repeated across 3 adjacent
charts. (6) Fixed 3 leftover "Auto (÷ first ...)" checkbox labels still
describing v1.23's divide/ratio convention after v1.24 switched the actual
math to subtract/offset — now "Auto (− first ...)". (7) Tightened layout
margins/spacing throughout the tab to reduce whitespace given the added
chart area. (2026-07-12)

### src/pimd_classviz.py — v1.24 — Analysis tab: per-group controls, bordered chart areas, Y-lock fix

Bench feedback on the new v1.23 Analysis tab, six changes: (1) the single
global "Normalize to first point" checkbox is replaced with independent
Auto/Manual normalize + Auto/Manual scale controls for each of the
heatmap/8-grid/9-grid chart groups. Per a follow-up clarification, "normalize
to first point" means an **offset** (first value → 0, rest referenced to it),
not the ratio/divide-by-first-point convention used elsewhere in this repo —
Auto subtracts each curve's own first point, Manual subtracts one shared,
user-entered reference value instead so the comparison scale doesn't drift
as the live first point moves. The heatmap's own Normalize control decouples
it from the main Heatmap tab's Δ/Z/raw display mode instead of always
mirroring it. (2) Every chart area is now a titled, bordered `QGroupBox`
with its controls inside that same box. (3) The two bottom strips' Reset
buttons are merged into one. (4) 8-grid's x-axis now shows each cell's
delay_us averaged across all bands (1 d.p.) instead of threshold_v; 9-grid's
per-panel titles show that same cell's delay_us *range* across bands
(matching the heatmap's threshold sub-label format) instead of threshold_v —
the two grids now surface different identifying dimensions instead of both
duplicating volts. (5) 8-grid/9-grid Y axes are locked to the first panel in
that row: tried pyqtgraph's `setYLink` first, but `ViewBox.linkedViewChanged()`
aligns ranges by on-screen pixel geometry rather than copying identical
numeric bounds — a scripted check showed genuinely different ranges across
same-size side-by-side panels — so replaced it with an explicit
`_lock_group_yaxis()` that copies panel 0's resulting range (auto-fit or
manual ±) onto every sibling panel every redraw tick; verified to match
exactly (both modes) in an offscreen-Qt re-test. (6) Fixed "Load signatures…"
opening a completely blank window — the native GTK/portal file dialog
doesn't render in this environment; added
`options=QFileDialog.Option.DontUseNativeDialog` to use Qt's own dialog
widget instead. (2026-07-12)

### src/pimd_classviz.py — v1.23 — new Analysis tab: real-time comparison charts + corpus overlay

New fourth tab, laid out to fill an ultrawide display with many small
pyqtgraph charts fed from the same live acquisition state the Heatmap tab
already maintains (no new serial/acquisition code): a heatmap variant
(y-axis renamed 'Pulse Width', integer µs, frequency dropped; x-axis stays
'Threshold' in volts at 2 d.p., with each column's delay_us range across all
8 bands added as a second tick-label line, since delay_us -- unlike
threshold_v -- isn't constant per column across bands, confirmed against
cal_72_air_v2.json); a normalized band-mean-vs-pulse-width curve; two
small-multiple grids (one panel per band showing its 9-cell profile, one
panel per cell showing its 8-band profile, each normalized to its first
point) decomposing the heatmap along each axis; two independently-resettable
band-mean-vs-time strips (highest/lowest pulse width); and a corpus-signature
overlay (Load signatures… button, reuses `pimd_corpus_check.load_corpus()`,
checkable per-target list, one colour per template) drawn on every chart
except the heatmap, skipped with a status-bar note rather than crashing if a
template's channel count doesn't match the live profile (DESIGN §11 — never
mix profile geometries). New `self._pulse_sort_order`/`_pulse_us_sorted`
(added to `_set_profile_dims()`) order all of these charts by pulse_us
ascending rather than assuming raw profile/channel order is already
pulse-ascending — the live default CLASSIFY_EP profile's band order is
actually pulse-*descending* (40→5µs), so that assumption would have silently
mis-ordered every one of these charts under the profile ClassViz connects
with by default. `_update_heatmap()` now also feeds a second heatmap image
(`self.analysis_img`) whenever it exists, from the exact same matrix/levels/
colormap already computed for the main Heatmap tab, so the two heatmaps
can't drift apart. New `_style_compact()` helper (small tick font, minimal
padding, optional small title) applied to all ~20 new plots, and axes hidden
on all but the leftmost panel of each small-multiple row, so the many panels
fit one screen. Verified end-to-end with a scripted offscreen-Qt run:
injected synthetic frames, switched to the `cal_72_air_v2` profile, captured
a baseline, confirmed chart 2 / both grids / both strips populate correctly
and the reset buttons work independently, then loaded the real
`PIMD_target_corpus_signatures_v2.csv` (44 signatures) and confirmed overlay
curves/lines draw on check and clear on uncheck. (2026-07-12)

### src/pimd_classify.py — v1.2 — configurable strip charts, per-delay normalized mode

The 4 lower strip charts are now independently configurable instead of
fixed to amp/continuum/cosine/baseline-band-8: each gets a mode combo
(module-level `STRIP_MODES`) and a band combo (shown only when the mode
needs one). The previous fixed content (amp, continuum, top-1 cosine,
baseline band-8) is preserved as the default selection for slots 1-4
respectively, generalized so any band can be picked, not just the last one.
Two new modes: "Band mean (mV)" (a chosen band's mean signal delta over
time -- the same quantity as one point on the existing snapshot band-mean
chart, now trackable over time) and "Per-delay normalized (9 cells)" (that
band's 9 individual cell readings, each divided by its own first sample so
all 9 curves start at 1.0 and separate as the session progresses -- shows
which delay cell drifts/responds most/least). Per-delay reads raw
(pre-baseline) per-cell values, not delta: delta's first sample is always
exactly 0 by construction (`BaselineTracker.bootstrap()` sets the baseline
to that very first frame), which would make "normalize to first entry"
degenerate -- discovered and fixed by scripted verification before
shipping (first sample would print 0.0 instead of 1.0 for every cell).
Slot mode/band selections persist to `classify_settings.json`
(`strip_modes`/`strip_bands`, -1 == last band). Verified end-to-end via a
scripted offscreen-Qt replay of `session_20260707_143723.csv`: all 6 modes
render correct data, per-delay-normalized curves all start at 1.0, and
switching a slot back to a single-curve mode correctly clears its other 8
curves. (2026-07-11)

### src/pimd_classify.py — v1.1 — heatmap range/axes, band-chart ticks, event log fix

Four fixes/additions from bench feedback on the Classify GUI: (1) added a
±mV range spinbox + Autoscale checkbox for the signature heatmap, mirroring
the existing band-mean chart's range control (persisted to
`classify_settings.json` as `heatmap_range_mV`/`heatmap_autoscale`,
defaulting to autoscale on so behaviour is unchanged unless the operator
turns it off). (2) Heatmap axes now show real values/labels instead of bare
pixel indices — bottom axis "Threshold" ticked with each cell's `threshold_v`
(4.2V…0.5V for cal_72_air_v2), left axis "Band" ticked with each band's
`freq_hz`/`pulse_us`, reusing the exact convention `pimd_classviz.py`'s
`_rebuild_heatmap_axes()` already established. (3) Band-mean chart's
log-scale x-axis now ticks only the profile's actual pulse widths (e.g.
6.0, 9.0, 13.44… µs) instead of generic log-decade ticks. (4) Fixed the
Event Log tab only ever populating the first row correctly, with every
event after it landing with blank cells in later columns — root cause was
`QTableWidget.setSortingEnabled(True)` re-sorting the table mid-way through
a new row's per-column `setItem()` calls (triggered once any column sort
was active, e.g. after the operator clicks a header), so later `setItem()`
calls landed on whichever row the resort moved into that row index instead
of the row being built. Reproduced in isolation (sort by column 1, append
rows one at a time -> later columns land on an already-populated row,
leaving the new row blank) and confirmed the fix (disable sorting for the
duration of each row's insert+populate, re-enable after) eliminates it.
Verified end-to-end via a scripted offscreen-Qt replay of
`session_20260707_143723.csv`: all 6 events now populate every column
correctly. (2026-07-11)

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

### src/pimd_classviz.py — v1.20 — replace Profile Builder tab with top-bar Load & Run

Removed the editable Profile Builder tab (`_build_profile_tab` and its band-table
editor/validation/save machinery — `_populate_profile_editor`, `_read_profile_from_editor`,
`_validate_profile_editor`, `_on_add_band_row`/`_on_remove_band_row`,
`_on_save_profile_file[_as]`/`_save_current_editor_as`, plus module-level
`_save_profile_file`/`_pad_json_floats`, now dead since `pimd_delaycal.py` already owns
profile authoring/saving independently). In its place, the top bar (above the tabs) now
has a "Saved profile:" `QComboBox` (populated from `data/profiles/*.json` via the existing
`_list_profile_files`/`_load_profile_file`) and a single "Load && Run" button
(`_on_load_run_profile`) that loads the selected file, sends it as a dynamic RAM-only
profile (`E`/D-command/`Q<DYNAMIC_PROFILE_INDEX>`/`G`), and calls `_apply_profile` —
collapsing the old two-step Load-then-Send&Run flow into one action, since there's no
longer an in-app editing step in between. `_build_d_command` is unchanged and reused as-is.
Editing a profile's bands/delays/thresholds is now delaycal-only. (2026-07-07)

### src/pimd_classviz.py — v1.21 — Training Session tab for guided corpus capture

Added a "Training Session" tab (index 2) to replace the ad hoc Stats-tab mark hotkeys
(`1`/`2`/`3`/`0`/Space, hardcoded to 5/10/15cm) with a proper guided-capture workflow for
building an ML signature corpus. A 5-column table (Index/Target/Distance(cm)/Time-at-
Target/Settledness; Index and the two live columns are read-only, Target/Distance are
double-click-editable) lets the operator build an ordered list of targets/distances (default
single row: `air`/`0`). Start/Pause/Stop buttons plus a Space-bar step-advance drive the
capture: Start opens a session (reusing `_toggle_record_frames`/`_session_start` verbatim,
same as the existing Record Session button) and immediately writes the first row's
`# mark: <iso-ts>, <text>` line (reusing `_append_mark` verbatim); each Space press writes
the next row's mark and advances, so every row's mark lands at the *start* of its own dwell
window (`pimd_features.py`'s `segment_from_marks` needs this — a mark written on *leaving* a
target would silently lose that target's own dwell data). Mark text is the literal `air`
(no `@` suffix — exact-match requirement of the downstream parser's `is_air` check) when
Target is "air", else `<target> @<distance>`. Pressing Space on the last row auto-finalizes
and saves the session (the explicit "ensure session is saved" requirement) by toggling the
same `pb_record` checkbox the Stats tab's Record Session button uses. Pause freezes the
Time-at-Target column and gates `process_packet`'s frame-row write (`and not
self._training_paused`) so a pause doesn't attribute movement-artifact frames to the current
target's plateau, while Settledness (rolling per-channel std over a tunable frame window,
same statistic `_update_stats_table` already uses, aggregated to one mV number) keeps
updating live so the operator can watch the signal restabilize before resuming. Validation
(green ✓/red ✗ label) requires every row have a non-empty target and numeric distance, and
at least one row's target be exactly "air" (case-insensitive) — a hard requirement of
`pimd_features.py`, which skips any session with zero air marks entirely.

Target lists are independently saveable/loadable as reusable templates
(`data/training_lists/*.json`, mirrors the existing Saved-profile pattern:
`_list_training_list_files`/`_load_training_list_file`/`_save_training_list_file`) — Save
does not require an "air" row (a template is just a shape; the air-row rule is about a
session being valid for the extractor, checked at Start).

`_session_stop()` now centrally resets the Training tab's UI state (`_reset_training_ui`)
whenever a training session was active, regardless of which of its three call sites
triggered the stop (the Stats-tab toggle, `_apply_profile`'s force-stop on a profile change,
`start_stop`'s force-stop on serial disconnect) — a single source of truth instead of
duplicating the reset at each site, so a profile switch or disconnect mid-training-session
can't leave the tab stuck showing "started" with a closed file underneath it.

Also: merged the top bar's separate "Saved profile" row into the same row as
Port/Connect/Start (one row instead of two), and removed the Stats tab's manual mark UI
(`le_mark_label`, `lbl_mark_log`, `_on_mark_hotkey`, `_update_mark_log_display`, `_mark_log`
deque) now that the Training Session tab's Space-bar workflow replaces it — `eventFilter`'s
Space dispatch is repurposed to `_on_training_space()` (the `1`/`2`/`3`/`0` dispatch is
removed outright; new `QAbstractItemView` import for the table's `DoubleClicked`-only edit
trigger, chosen specifically so a table-focused Space keypress can never enter cell-edit
mode). (2026-07-07)

### src/pimd_features.py — v3 — fix parser dropping every marked session (0 rows)

`parse_session_file()`'s single pass flipped `header_done = True` on the first non-`#`
line (the CSV data-header row) and never checked for a leading `#` again afterward. But
`# mark: ...` lines are written live as the operator advances targets mid-recording
(`pimd_classviz.py`'s hotkey feature since v1.19, and its Training Session tab since
v1.21), so in any real session they land interspersed among data rows, not batched before
the first one. Every mark after the first data row was therefore comma-split as if it were
a data row and crashed on `int(' air')` / `int(' copper pipe @5')`, causing the whole
session to be `[SKIP]`ped with 0 rows written and no hard error — surfaced when a user ran
the tool against the first real Training-Session-tab-recorded session
(`session_20260707_125642.csv`) and got a header-only output file. Fixed by recognizing
and parsing `#`-prefixed mark lines in the post-header data-row branch too (new shared
`_parse_mark_content()` helper used by both the pre- and post-header branches, so they
can't drift apart). Verified against that session (13 marks, 9 non-air plateaus × 72
channels = 648 rows, correct target/distance breakdown) and against all pre-existing
no-marks sessions (no regression). This bug predates the file's v1 and had never been
exercised against a genuinely marked session before now. (2026-07-07)

### src/pimd_corpus_check.py — v1.0 — corpus-level acceptance checks

Brought over from the separate `pca-explore-fix` worktree/branch (commits `0038810`,
`e4ed27a`, both 2026-07-04), where it was originally authored — not a new change, just
merging it onto `main`. New script (Stage 1 of `ML/PIMD_v2_acceptance_checklist.md`). Runs
six checks against one or two corpus CSVs (long format like
`assets/PIMD_target_corpus_signatures.csv`, or the wide `c00..c71` format, auto-detected):
shape distance-invariance (cosine 5v10/5v15 per capture, plus a per-corpus pass count),
split-half SNR per signature, canary-session consistency (`CANARY-START`/`CANARY-END`
target rows), repeat consistency (targets marked `(rpt)` or `REPEAT`, matched to their base
capture by name — falls back to a first-word + shared-weight-token match since real corpus
naming isn't always a clean suffix strip, e.g. "brass block 370g (rpt)" vs "brass 370g"),
distance falloff (log-log power fit over 5/10/15 cm plus an explicit solder 5cm/15cm
contamination ratio), and cross-campaign 5cm shape repeatability (only when two corpora are
given). Everything prints as one flat table (check, metric, value, pass band, PASS/FAIL/SKIP);
exits nonzero on any FAIL so it can gate a capture day. Re-verified on `main` against
`assets/PIMD_target_corpus_signatures.csv`: 128 checks, 109 PASS/18 FAIL/1 SKIP, reproducing
the same figures as the original run (e.g. solder's 1.21x 5→15cm amplitude ratio) — no path
or behavior differences between the two branches. Plain numpy/pandas only. (2026-07-07)

### src/requirements.txt — add pandas, scikit-learn, matplotlib

Also brought over from the same worktree/branch (commit `0038810`, 2026-07-04).
`pimd_pca_explore.py`, `pimd_knn_baseline.py`, and now `pimd_corpus_check.py` import
`pandas`/`sklearn`/`matplotlib`, but `src/requirements.txt` never listed them on `main` —
`pip install -r src/requirements.txt` in a clean venv would leave all three scripts failing
on the first import. (2026-07-07)

### src/pimd_features.py — v4 — auto-suffix repeat visits within a session

A guided Training Session run can legitimately revisit the same target/distance more than
once in one session (e.g. running a saved target list twice to check repeatability), but
`segment_from_marks()` gave every plateau's target label only `(session, target,
distance_cm)` as its identity in the output corpus. A second visit to, say, "copper pipe"
@5cm therefore had the exact same identity as the first, and any groupby-style corpus tool
would silently merge the two into one 144-cell group instead of two distinct 72-cell
captures. Surfaced by `pimd_corpus_check.py`'s `load_corpus()` correctly refusing a real
two-visit session (`session_20260707_125642.csv`: "copper pipe" visited twice, "steel
spanner" once) with "mixed cell counts across rows [72, 144] — refusing to mix profile
geometries (DESIGN §11)" — that guard was doing its job; the underlying data was genuinely
ambiguous, not a false positive. Fixed: repeat visits within a session are now auto-suffixed
`(rpt)` for the 2nd visit, `(rpt3)`/`(rpt4)`/... beyond that — `(rpt)` for the 2nd visit
matches the pre-existing hand-corpus naming convention `pimd_corpus_check.py`'s repeat-
consistency check already looks for, so the common two-visit case needs no other tool
changes. Verified: re-running against that session now gives three distinct 72-row groups
(`copper pipe` / `copper pipe (rpt)` / `steel spanner`) and `pimd_corpus_check.py`'s
repeat-consistency check correctly compares the repeat against its base capture at all 3
distances instead of crashing. (2026-07-07)

### src/pimd_corpus_check.py — v1.1 — recognize numbered repeat suffixes

Companion to the `pimd_features.py` v4 fix above: widened `REPEAT_MARK_RE` from `\(rpt\)`
to `\(rpt\d*\)` so `(rpt3)`, `(rpt4)`, etc. (3rd+ same-session repeat visits) are also
recognized by the repeat-consistency check, not just a bare `(rpt)` for the 2nd visit.
(2026-07-07)

### src/pimd_corpus_check.py — v1.2 — remove solder-specific falloff sub-check

Removed the solder-specific 5cm/15cm amplitude-ratio sub-check from check 5
(distance falloff): it always printed a row — PASS/FAIL when a "solder"-named
target was present, else an uninformative "n/a (no solder target)" SKIP on
every other corpus — which read as clutter on any corpus not built around
that specific canary. The general per-target falloff fit (n exponent, worst
fit/measured ratio) is unaffected and still runs for every target regardless
of name, solder included — verified against `assets/PIMD_target_corpus_signatures.csv`
(128 → 127 checks, 18 → 17 FAIL, exactly the one removed row; "solder roll
260g"'s own falloff-fit rows unchanged). Removed `SOLDER_FALLOFF_MIN` along
with it. (2026-07-07)

### src/pimd_classviz.py — v1.22 — clear stale columns + auto-derive session notes

Two Training Session tab fixes. First: pressing Start no longer leaves the previous run's
Time-at-Target/Settledness values sitting in rows the new run hasn't reached yet — new
`_clear_training_live_columns()` resets every row's Time and Settledness cells to `—`
before the run begins (`_reset_training_ui()` on stop/finalize cleared the button/table
*enablement* state but never touched these cell values, so a re-run of the same saved list
showed stale numbers until the operator physically stepped past each row again). Second:
Start no longer pops up the interactive "Session notes" `QInputDialog` — there's nothing to
type that isn't already in the table, so notes are now auto-derived from the run list itself
(new `_build_training_notes()`: "Training Session run list:" followed by one "N. target
@distancecm" line per row) and passed straight through a new optional `notes` parameter on
`_session_start()` (still prompts interactively when called with `notes=None`, unchanged for
the plain Stats-tab "Record Session" button, which has no run list to derive anything from).
Since `_session_start()` is now called directly rather than triggered indirectly via
`pb_record.setChecked(True)`, the checkbox's checked state is synced afterward through
`blockSignals` so a later click still reads as "stop" rather than double-firing
`_session_start()`. Verified headlessly: `QInputDialog.getMultiLineText` is never invoked
during a Training start, the auto-derived notes lines land correctly in the session CSV's
`# session_notes:` header, and a row not yet reached in a fresh run shows `—`/`—` rather than
a previous run's leftover values. (2026-07-07)

### src/pimd_features.py — v5 — plateau_amp_mV restored to v1 L2-norm convention

`plateau_amp_mV` was emitting `mean(|delta_mV|)` per cell while the v1 hand-built corpus
and the canary-strength unit definition (1 unit ≡ copper pipe 120g @10cm ≡ 45 mV L2) use
the L2 norm of the 72-cell drift-corrected delta vector — the same column name, two
different quantities, ~9x apart (measured: copper pipe 120g @5cm read 4.96 here vs. 113.7
(L2) in the v1 corpus, a ~23x apparent gap — only ~9x of which was this bug; the remaining
~2.3–3x is a separate, already-known, out-of-scope bench-geometry difference between the
v1/v2 setups). This corrupted any cross-campaign amplitude comparison and the canary-unit
definition. Restored the L2 convention; `splithalf_floor` changed to match (L2 norm of the
split-half-median difference vector, still halved) so floor/amp stays a meaningful,
consistent fraction for the noisy-quality gate. The old `mean(|delta_mV|)` quantity is
still useful, so it's kept — appended as a new `amp_mean_abs_mV` column at the end of both
the long and wide row schemas (existing readers that select columns by name are
unaffected). Documented in a comment block above `compute_plateau_stats()` and in
`wide_header_lines()`'s `# columns:` comment.

Checked `pimd_corpus_check.py` for absolute-mV thresholds assuming the old convention: none
exist — every amplitude-adjacent check is ratio- or cosine-based, so no threshold values
needed changing; no code edit made there. Verified against `session_20260707_134922.csv`
(regenerated corpus, before/after this fix): all 29 `pimd_corpus_check.py` verdicts
(PASS/FAIL/SKIP) are identical before vs. after. Flagging honestly: not all the underlying
ratio *values* are identical — SNR (amp/splithalf), the falloff n-exponent, and repeat
amp-ratios shifted somewhat (e.g. copper pipe @5cm SNR: 67.0 → 34.5, still comfortably
above the 10.0 gate), because L2 norm and mean-abs aren't exactly proportional between two
*different* vectors (amp's delta_mV vs splithalf's half-difference vector, or the same
target's vector at a different distance) — only cosine-similarity checks and same-vector
ratios are exactly convention-invariant; these particular ratios are empirically
verdict-stable on this dataset, not mathematically guaranteed to stay so on all future data.

One row, before → after (`session_20260707_134922, copper pipe, 5cm`):
```
before: ...,delta_mV=-7.105,plateau_amp_mV=4.957, splithalf_floor=0.074,quality=ok,amp_mean_abs_mV=4.957
after:  ...,delta_mV=-7.105,plateau_amp_mV=49.503,splithalf_floor=1.436,quality=ok,amp_mean_abs_mV=4.957
```
(2026-07-07)

### campaign — C2 — rig change declared

The bench rig changed since the v1 campaign (builder-confirmed, 2026-07-07). Per the
never-mix-geometries principle (DESIGN §10), captures made on the new rig start a new
campaign: campaign 2 (rig 2). Measured consequences, from `session_20260707_134922` and
`session_20260707_143723`: absolute amplitudes ~2.3× below v1 at nominal distances, falloff
exponents 1.0–1.15 vs v1's 1.3–1.6, uniformly across all targets; and extended targets
(spanner, cast iron trivet, galvanized pipe) show a real, repeatable @5cm shape change
(cos(5,15) 0.936–0.969) while cos(10,15) stays high, absent from v1 at the same nominal
distances (compact copper unaffected, cos(5,15) 0.990). Consequence: v1-derived absolute
constants (F1's 12/17 statistic, F9's falloff exponents, the 45 mV canary-unit constant,
acceptance-checklist row 1.6) are rig-1 facts, not predictions for rig 2 — retired as such,
detailed in `ML/V2/ML_FINDINGS.md` F11. The v1 corpus itself is untouched and remains valid
for rig 1. The physical question of *what* changed on the rig is declared, not diagnosed —
out of scope here. (2026-07-07)

### src/pimd_corpus_check.py — v1.3 — campaign 2 support: canary pairing, cross-session repeat, near-field AMBER, --baseline gating

Four changes, all driven by the campaign 2 (rig change) declaration above. **(A)** Fixed
`check_canary()`: it matched target names by bare exact-match against `{"CANARY-START",
"CANARY-END"}`, so real canary rows named `"copper pipe CANARY-START"`/`"copper pipe
CANARY-END"` (`train-s1.csv`) were invisible to it ("0 pairs found") even though the SNR
check already proved both were captured. Now matches by suffix (new `strip_canary_suffix()`
helper, replaces `CANARY_LABELS`) so any `"<base> CANARY-START"`/`"<base> CANARY-END"` pairs
correctly, and adds a `drift status` row per pair reporting protocol v2's drift-flag
criterion (either the shape-cos or amp-ratio check failing ⇒ session drift-flagged, 15cm
rows downgraded — `pimd_features.py`'s quality column handles the actual downgrade, this
just reports). Canary rows are now also excluded from `check_shape_invariance()` and
`check_falloff()` (5cm-only; would otherwise pollute per-target checks). **(B)** New
`check_repeat_cross_session()`: the same target+distance captured in two different sessions
(e.g. a capture plan revisiting "copper pipe" in session s1 and again in s4) now gets its
own shape-cos/amp-ratio repeat-consistency rows labelled with both session IDs — additional
to, and independent of, the existing within-session `(rpt)` handling (unchanged). **(C)**
`check_shape_invariance()` adds a `cos(10v15)` row per target. Extended objects genuinely
change shape at 5cm on this rig while agreeing at 10/15cm — physics, not capture error — so
`cos(5,15) < 0.97` but `cos(10,15) >= 0.97` now verdicts `AMBER (near-field @5, extended
target?)` instead of `FAIL`; both low is still `FAIL`. The `cos(5,15)` roll-up is now
report-only; a new `cos(10,15)` roll-up is the real per-corpus gate. AMBER is tracked
alongside PASS/FAIL/SKIP in the summary line and never contributes to the exit code.
**(D)** Cross-campaign comparison is now gated behind an explicit `--baseline <corpus_csv>`
argument (replaces the old ambiguous positional 2nd-corpus-file convention — only the
primary corpus gets the full acceptance suite). No baseline (default): one SKIP row,
"cross-campaign checks skipped (campaign 2; no rig-1 baseline applicable)". With one:
results are labelled "(informational, cross-rig)" and excluded from the exit-code gate — a
different rig/campaign is a reference point, not a same-rig acceptance criterion. Checked
for absolute-mV thresholds elsewhere in this file assuming the old `plateau_amp_mV`
mean-abs convention (per `pimd_features.py` v5): none exist, every amplitude-adjacent check
here is already ratio- or cosine-based.

Verified against `train-s1.csv` (`session_20260707_143723`): canary shape-cos=0.9983/amp
ratio=0.952 now report real values (previously invisible/SKIPped); spanner/trivet/galvanized
`cos(5,15)` FAILs correctly flip to AMBER (their `cos(10,15)` = 0.9887/0.9863/0.9963, all
≥ 0.97); copper pipe/SNR/falloff rows are byte-for-byte identical to the pre-this-change run
(diffed directly against a saved copy of the prior file version); `--baseline
PIMD_target_corpus_signatures_v1.csv` runs without error (0 common 5cm target names — v1
uses weight-suffixed names like "copper pipe 120g", a naming-convention mismatch between
corpora, not a code defect; fixing that fuzzy-matching is out of scope here). (2026-07-07)

### ML/V2/ML_FINDINGS.md — v1.1 — F11: rig change declared, v1 constants retired

Added F11 (see the "campaign — C2" entry above for the full context): the v2 capture rig
differs from v1's, uniformly across all targets in amplitude, falloff exponent, and a
repeatable extended-target near-field shape change at 5cm. Retires v1's absolute-constant
predictions (F1's 12/17 statistic, F9's exponents, the 45 mV canary-unit constant,
acceptance-checklist row 1.6) as rig-1 facts, not rig-2 predictions — v1's corpus and
shape/ratio findings are untouched and remain valid for rig 1. Canary strength unit
redefined on rig 2: 1 unit ≡ copper pipe @10cm = 26.123 mV (`plateau_amp_mV`, L2 convention,
`train-s1.csv`). (2026-07-07)

### src/pimd_v2_findings.py — v1.0 — replaces pimd_knn_baseline.py / pimd_pca_explore.py

`pimd_v2_findings.py` is the reproduction script for `ML_Findings_v2.md` — every number in
findings F12-F21 is printed by this script from the campaign-2 corpus alone, closing the
"open gaps" pattern flagged in `ML_FINDINGS.md` v1.0 (open gap 3: "v2 comparison run").
Removed `src/pimd_knn_baseline.py` (v1.1, LODO/LOTO 1-NN and logistic-regression baseline
classifiers) and `src/pimd_pca_explore.py` (v1.0, PCA scree/loading/PC1-PC2 exploration) —
both were v1-corpus-specific one-off analysis scripts superseded by this single script's
campaign-2 reproduction of the same PCA/classification-adjacent findings plus the new F12-F21
material; keeping the old scripts around next to a v1-only corpus they were written against
would be dead weight. Neither file was imported by anything else in the repo (verified: no
other reference across `*.py`/`*.md` outside their own headers and their own historical
`CHANGELOG.md` entries above, which are left untouched as history). (2026-07-07)

### src/pimd_classify.py — v1.0 — new PyQt6 live/replay Mode 2 signature classifier

New tool, fourth in the gui/classviz/delaycal/classify family: classifies Mode 2 frames from
either a live serial port or a recorded ClassViz session CSV through one shared, Qt-free
pipeline (`Engine.process_frame`), so replay and live are provably the same code path — a
`--headless <session.csv>` CLI mode runs the identical `Engine` with zero PyQt6/pyqtgraph
import at runtime, for CI/no-hardware testing. Implements the two-stage architecture from
`ML_Findings_v2.md`'s "Consequences for pimd_classify" section: Stage A is a causal EMA air
baseline (F2) feeding an amplitude-hysteresis + min-duration event state machine; Stage B1 is
`pimd_v2_findings.py`'s continuum rule (F13/F16, reused verbatim — not reimplemented) reporting
family + the ladder-clamped continuum value; Stage B2 is 1-NN cosine against the corpus usable
set (SNR≥10 gate, F12), reporting margin in repeat-floor units (0.0062, F15) with pile-level
fallback below 2× floor and open-set "unknown object" reject above 8× floor (K, F15/F17).
Canary rows are folded into their base target name in the identity pool (design decision,
flagged for review — canaries are the same physical object and F20 shows high repeatability,
so folding adds real samples rather than discarding them). Reuses rather than reimplements:
`pimd_features.py`'s session parser (marks-anywhere-safe, the v3 fix), profile-geometry guard
(DESIGN §11), and wide-format signature writer (feeds "Dump signatures" straight back into
`pimd_corpus_check.py`); `pimd_corpus_check.py`'s corpus loader, cosine primitive, and
canary-suffix stripper; `pimd_v2_findings.py`'s band-mean/crossing/continuum functions.

Verification: `--headless` replay of all four 2026-07-07 sessions gives 6/6/5/5 (all-events)
family-correctness against `pimd_v2_findings.FAM3` (verification-only, never consulted by the
live classifier itself, which stays a physics rule with no fixed target list) — a perfect
score. Event counts (6, 6, 6, 4) match each session's real object-visit groups; the amplitude
hysteresis correctly merges a single visit's 5/10/15cm distance changes into one event (the
target is never fully removed between distances) rather than splitting per mark, which is the
physically correct behaviour for a threshold detector, not a segmentation bug. Tuned
`enter_amp_mV`/`exit_amp_mV`/`min_duration_s`/`exit_debounce_s` empirically against these four
sessions (no spec-given seed values existed for these, unlike the floor/K/canary/SNR-gate
constants) — found and fixed a baseline-staleness interaction during tuning: the EMA baseline
freezes while non-air, so thermal drift accumulated during a long detection run must not
exceed the exit threshold or the detector can never register a genuine return to air; the
final defaults (enter=6.0, exit=4.0 mV, min_duration=0.5s, exit_debounce=0.3s) clear this
session set's measured air-noise floor (~1.2-2mV) and drift-during-typical-dwell margin.
Confirmed via a LODO-style sweep across the whole corpus that with only 26-34 usable rows
across ~10 objects, individual-row 1-NN margins are frequently thin project-wide (top-1 label
is correct roughly half the time per row-level LODO, matching the ballpark of F17's own
pooled 58%; comfortable 2×-floor margins are rare) — the "identified" bucket firing rarely in
favour of the deliberately conservative "pile-level" fallback is the open-set safety margin
working as designed against a still-small corpus, not a classifier bug; documented rather than
loosened, since forcing more "identified" verdicts would risk overconfident misclassification.
Confirmed `--speed` (a headless test aid that sleeps between `process_frame()` calls without
touching the timestamps fed to the pipeline) produces byte-identical event logs, proving
replay speed cannot change a decision. Confirmed "Dump signatures" output round-trips cleanly
through `pimd_corpus_check.sniff_format`/`load_wide`. Confirmed a hand-edited mismatched
profile is cleanly refused (exit code 2, no traceback) in headless mode. GUI smoke-tested
under `QT_QPA_PLATFORM=offscreen`: full session load + frame-by-frame replay + all three
exports + Settings dialog + seek-driven engine rebuild, all exception-free; caught and fixed a
real crash found this way (`_redraw()`'s "current frame" heatmap branch read a placeholder
zero-vector expression that blew up with a reshape error before the engine had processed its
first frame — now tracks the actual last-computed per-frame delta and guards the no-frame-yet
case). Live-serial and interactive visual correctness were not (and cannot be) exercised here
and still need a human bench test — the code is structured so the session-replay path already
exercises the entire pipeline above the frame-source adapter. (2026-07-11)

Live-hardware bench test surfaced two real bugs the offscreen smoke test couldn't reach.
(1) `_on_start_live_clicked` sent a bare `Q<n>`/`G` against a placeholder profile index instead
of loading cal_72_air_v2 onto the board first -- cal_72_air_v2 is not one of the board's
compiled static profiles (those are the 45-channel CLASSIFY_EP family), so a bare `Q<n>` either
selected the wrong, already-active (lighter-duty) profile or nothing at all. Measured effect:
~50mA supply draw instead of cal_72_air_v2's expected ~200mA, and every incoming `W` frame
silently dropped because its profile index never matched the placeholder. Fixed by adding
`build_d_command()`/`DYNAMIC_PROFILE_INDEX=5` (ported verbatim from `pimd_classviz.py`'s
`_build_d_command`/`_on_load_run_profile`) and a new `LiveFrameSource.load_and_start(profile)`
that sends the same `E` / `D<cmd>` / `Q5` / `G` sequence ClassViz's "Load and Run" uses --
pushing the profile as a RAM-only dynamic profile (no flash writes, DESIGN §11) rather than
guessing at a pre-existing static index. (2) The Start button never reflected running state
(stayed yellow/"Start" regardless) and firmware `V`/`L` responses were parsed and then silently
discarded (`line_received` had no connected slot) -- made it checkable with proper
Running/green ↔ Start/yellow toggling and wired `line_received` to surface raw board responses
on the status bar, since there was previously no live feedback at all that the board was
talking back. (2026-07-11)

The D-command fix alone did not resolve a live bench report of unchanged (low) supply current
and no data reaching the GUI, and no exception was raised, so the fault sits somewhere between
"bytes never leave the PC" and "bytes arrive but never make it to a rendered frame" with no
visibility into which. Added counter-based diagnostics rather than guessing further:
`LiveFrameSource` now counts every raw line received, every `W`-prefixed line seen, and splits
non-matches by cause (wrong profile index / wrong channel count / parse error); `send()` now
checks its `QSerialPort.write()` return value against the encoded length and reports short
writes; a new `command_sent` signal echoes each transmitted command to the status bar; and
`_redraw()` shows the running `rx N lines, M W-frames (...)` counter summary in the status bar
whenever Start is checked, independent of whether any frame has been fed to the pipeline yet
(the previous code path only updated the footer after a frame reached the engine, so a fully
silent link looked identical to a working one that just hadn't rendered yet). This turns "no
data" into one of: rx 0 lines (nothing coming back at all -- port/wiring/firmware-not-running),
rx N lines but 0 W-frames (board responding but not streaming, or a different frame type),
W-frames arriving but all wrong-idx (profile index still mismatched), or W-frames matched but
still nothing on screen (a GUI-side rendering bug, now isolated from the link itself). Not yet
confirmed against hardware -- next bench attempt should report which bucket the counters land
in. (2026-07-11)


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

### mcu/pimd_mcu.py — v4.02 / v4.01 / v4.00 — migrated from the file header (2026-07-22)

These three earliest entries predated `CHANGELOG.md` and lived only in the file's
header changelog; migrated verbatim here when the per-file headers were slimmed to a
terse version lineage (see the 2026-07-22 header-slim entry above the marker line).

**v4.02** — `acquire_raw_average`: discard the first 5 samples (priming) so the PWM
wrap-register glitch after a frequency change settles before the averaged window begins;
fixes near-zero readings on `A<n>` when the frequency changes between `*` commands. (Also
recorded in the v4.03 entry above as "carried into v4.03".)

**v4.01** — `acquire_mode2`: CC written first at period start (~1–2 µs) before the SPI
read — eliminates the CC-write race on multi-cell profiles; precompute `cell_duties`;
prime now fires `cell[n-1]` (removes the startup transient in `rolling[n-1]`); command
poll moved out of the W-emit gate so `E` stops within one `n_pulses*n_delays` cycle.

**v4.00** — complete serial protocol rewrite: two non-concurrent modes, `W` streaming,
`Q`/`G` commands; file renamed from `pimd_mcu_302.py` to `pimd_mcu.py`.

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

## Archive — migrated from file headers (2026-07-22)

These earliest entries predated `CHANGELOG.md` and lived only in their file's header
changelog; migrated here verbatim when the per-file headers were slimmed to a terse
version lineage (see the header-slim entry above the marker line at the top of this file).

### src/pimd_delaycal.py — v1.01 / v1.00 — migrated from the file header

**v1.01** — freq and pulse width are now paired as tuples (freq/pulse input field, e.g.
`25/10`).

**v1.00** — initial version.

### src/pimd_gui.py — v4.01 / v4.00 — migrated from the file header

**v4.01** — added an editable port field (mirrors `pimd_classviz.py`); was hardcoded to
`ttyACM0`. `serial_open()` now reads `self.le_port.text()`, stripping a leading `/dev/`
if present.

**v4.00** — renamed from `pimd302.py`; `W` (Mode 2 stream) records silently ignored; window
title updated.

---

