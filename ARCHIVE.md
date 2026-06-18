# PIMD CHANGELOG Archive

---

## Archive — consolidated 2026-06-18

*The following block was the complete CHANGELOG.md at the time of the §16 README consolidation pass (Doc rev 1.2). README.md has been updated from this content; this file preserves the raw entries for reference.*

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

**TODO: roll this section into README.md §3 ("Measured operating envelope")
once confirmed stable — README is read-only for agents, left here per
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
`AI refs/` folder — move into `pics/` if it's to become a permanent README
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
in Mode 1 (README §8 documents ~15–20 ns for the static-PWM baseline).

**First diagnostic (no code):** the existing `A32` raw boxcar-average command
(same raw SPI0 ADC path as Mode 2, but with a static, never-rewritten PWM
config) measured ~100 µV–1 mV at the same parameters — ruled out "raw vs
filtered ADC path" as the dominant cause (README §7 already expected ~350 µV
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
each period → ~310 µV, matching the A32/README expectation) against an n=2
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
conversions (README §7: raw SDOB single-sample noise ≈ ±1400 µV) — but it
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

### src/pimd_delaycal.py — v1.02 (new tool, not yet in README §15)

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

### Project policy

- `CLAUDE.md` removed 2026-06-17.
- `README.md` is **read-only for agents**. Do not edit it.
- All agent-driven changes are logged here (`CHANGELOG.md`) and will be merged into
  `README.md` manually by the user at a later date.
