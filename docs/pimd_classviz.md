# pimd_classviz.py — Cheat Sheet (app v1.15)

⚠ DESIGN §15 says v1.14; source `APP_VERSION = '1.15'`.

## What it is
PyQt6 desktop app that connects to the PIMD board, runs a Mode 2 profile sweep, and displays
a real-time heatmap of signed cell deviations from a captured air baseline. Also provides a
Stats table with per-cell noise metrics and a Profile Builder for sending dynamic profiles to
the board without reflashing.

## What it does
- Connects to board over USB-serial; sends `Q4` + `G` on connect to start CLASSIFY_EP sweep.
- Renders a 2D heatmap (or 3D surface) of per-cell deviations from a user-captured baseline.
- Applies a 64-frame circular median glitch filter to display path (≥100 mV shifts suppressed).
- Stats tab: per-cell Latest / Mean / Std (mV), colour-coded green/yellow/red vs thresholds.
- Profile Builder tab: edit bands/delays/averages, preview the `D` command, send & run without
  reflashing; save/load profiles as JSON in `src/data/profiles/`.
- ML bridge: label snapshots and append to a date-stamped CSV; optional continuous logging;
  frame recorder auto-saves raw W-record frames to `src/data/frames_YYYYMMDD_HHMMSS.csv`.

## Modes of operation
Single acquisition path: **Mode 2 only** (single-cell Mode 1 isolation was removed in v1.13).
The board is either Stopped or Streaming; the app tracks this via the Start/Stop button.

| App state | Board state | Trigger |
|-----------|------------|---------|
| Stopped | idle | power-on / after `E` |
| Streaming | Mode 2 running | `G` sent (profile must be selected first) |

Three **display modes** (Heatmap tab): Δ deviation (default) · Z normalised · RAW abs µV.  
Three **baseline modes**: Static capture (default) · Rolling median · Nominal thresholds.

## Serial protocol (commands this app sends / records it consumes)

| Dir | Token / format | Meaning |
|-----|---------------|---------|
| → MCU | `E` | Stop — sent before every mode switch, on disconnect, on stop |
| → MCU | `Q<n>` | Select profile (Q4 = CLASSIFY_EP on connect; Q5 = dynamic after `D`) |
| → MCU | `G` | Start Mode 2 streaming |
| → MCU | `D<avg>;<hz>,<pw_us>,<d_us>[,...];...` | Define RAM-only dynamic profile (Profile Builder) |
| ← MCU | `W<prof_idx>,<t_ms>,<ch0>,...,<chN-1>` | One sweep frame — µV per cell; idx must match active profile or frame is silently dropped |

Notes: `*` (Mode 1) was used pre-v1.13 for single-cell isolation; removed. `V` / `L` are
**not** sent by this app — it assumes profile layout from its own Python constants.

## Key parameters / defaults

| Parameter | Default | Notes |
|-----------|---------|-------|
| Port | `/dev/ttyACM0` | Saved to `src/data/classviz_settings.json` |
| Default profile | 4 (CLASSIFY_EP) | Sent as `Q4` automatically on connect |
| Dynamic profile index | 5 | Must match `NUM_PROFILES` in firmware |
| Baseline capture N | 64 frames | `sp_capture_n` |
| Rolling baseline T | 3.0 s | `sp_rolling_t` |
| Stats std-dev window | 50 samples | `sp_stats_window` |
| Std colour thresholds | 0.50 / 1.00 mV | Green < lower; yellow = mid; red > upper |
| Glitch filter window | 64 frames | 100 mV threshold vs median; display path only |
| Redraw rate | ~30 Hz | `REDRAW_MS = 33` |
| Settings file | `src/data/classviz_settings.json` | Written on close; restored on startup |
| Profile files dir | `src/data/profiles/*.json` | Saved/loaded by Profile Builder tab |

CLASSIFY_EP (profile 4): 5 bands × 9 delays = 45 cells; freqs 10 601 / 17 599 / 29 201 /
43 003 / 56 992 Hz; pulses 40 / 30 / 20 / 10 / 5 µs. Delays 6.03–12.53 µs (band-dependent).

## Gotchas / pertinent notes

- **Always send `E` before switching profiles or restarting.** `_on_send_run_profile()` does
  this automatically; manual sequences must too.
- **W-frame index must match active profile.** Frames with a mismatched index are silently
  dropped — if the heatmap is blank after a profile switch, check that the board confirmed the
  new profile before `G` was sent.
- **Dynamic profile (index 5) is lost on board reset.** Must re-send `D` command each session.
- **Single-cell / Mode 1 path removed in v1.13.** Use `pimd_delaycal.py` for single-point
  Mode 1 measurement.
- **Glitch filter is display-only.** `_rolling_buf` and `_record_buf` hold unfiltered raw µV;
  ML CSV and frame recordings are faithful to the wire.
- **`D` command uses µs for pulse/delay; `*` command (not sent by this app) uses ns.** Do not
  mix up if constructing manual serial commands.
- **Settings not saved mid-session** — only written on `closeEvent`. A crash loses changes.
- Stats table is only recomputed when the Stats tab is visible (performance optimisation).
