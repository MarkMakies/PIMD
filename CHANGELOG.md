
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

<!-- Add new entries above this line. Format: ### <file> — v<N> — <short title> -->

<!-- Previous entries moved below this line and archived to ARCHIVE.md — consolidated into README.md Doc rev 1.2) -->


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

### src/pimd_classviz.py — v1.04 — profile dimensions to instance state; Profile Builder tab

`N_BANDS`, `N_CELLS`, `BANDS_META`, etc. moved from module-level constants to
instance state set by `_apply_profile()`, allowing the heatmap/stats table/
cell selectors to resize to match any active profile. Added a **Profile
Builder** tab to edit, save, load, and transmit band/pulse/delay profiles to
the board's `D` command (RAM-only dynamic profile, selectable via
`Q<DYNAMIC_PROFILE_INDEX>`) without reflashing. Default Q4-on-connect
behaviour unchanged.

---

### src/pimd_delaycal.py — v1.02 — fix double-send bug and _prev_delay accuracy

`_on_r_record()` no longer advances the state machine when
`_check_thresholds()` has already called `_advance_pair()` (double-advance
bug). Also saves `current_delay` before the threshold check so that
`_prev_delay` always reflects the actual measured delay, not the
post-reset `start_delay`.

---

