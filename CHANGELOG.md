
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

