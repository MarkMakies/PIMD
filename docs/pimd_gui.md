# pimd_gui.py — Cheat Sheet (gui v4.13)

## What it is
PyQt6 desktop GUI for **Mode 1 filtered telemetry** — the primary operator interface
for real-time voltage/noise monitoring. Runs on PC; communicates with the MCU over
USB-serial at 115200 baud.

## What it does
- Displays the LTC2508-32 filtered (Mode 1) voltage as a scrolling line chart.
- Overlays an optional orange **boxcar raw-average** trace (A\<n> poll, every 250 ms).
- Sends `*` config commands on every parameter change; streams data to a timestamped CSV.
- Computes and shows rolling drift slope (µV/s) from the last 100 filtered packets.
- Persists port, all operating params, toggle states, V/H div, and window geometry across sessions.

## Modes of operation
Single display mode only: **Mode 1 filtered**. `W` records (Mode 2 stream) are
silently ignored if they arrive — the GUI does not start or stop Mode 2.

## Serial protocol (115200 baud, USB-CDC)

### Commands the GUI sends → MCU

| Token | When sent | Meaning |
|-------|-----------|---------|
| `S` | Start button / Space | Start Mode 1 streaming |
| `E` | Stop button / close / Space | Stop (universal); output buffer flushed first |
| `*<freq_hz>,<pulse_ns>,<delay_ns>,<ds>` | On every param change or Start | Configure Mode 1 — freq in **Hz**, pulse/delay in **ns** |
| `A<n>` | Every 250 ms while Boxcar ON and running | Request n-sample boxcar average; default n = 64 |

### Records the GUI consumes ← MCU

| Record | Format | What the GUI does with it |
|--------|--------|--------------------------|
| `*` | `*<t_ms>,<val_uV>,<sd_uV>,<freq_hz>,<pulse_ns>,<delay_ns>,<ds>` | Plots voltage; writes to CSV; updates dial + status bar |
| `R` | `R<t_ms>,<mean_uV>,<sd_uV>,<n>,<freq_hz>,<pulse_ns>,<delay_ns>[,<min_uV>,<max_uV>]` | Plots orange trace (if Raw Avg ON); updates status bar |
| `W` | `W<prof_idx>,<t_ms>,<ch0>,...` | **Silently ignored** |

## Key parameters / defaults

| Parameter | Default (SoC) | Notes |
|-----------|--------------|-------|
| Port | `/dev/ttyACM0` | Editable in UI; `/dev/` prefix stripped automatically |
| Frequency | 10 000 Hz | Slider snaps to 18 clean 125 MHz divisors (1–50 kHz) |
| Pulse width | 20.000 µs | 8 ns grid; slider range 5–40 µs |
| Sample delay | 10.000 µs | 8 ns grid; slider range 5–30 µs; `SAMPLE_PULSE_CORRECTION` = 0.904 µs applied in grid check |
| Downsample | 256 | Toggle button: 256 ↔ 1024 |
| Avg n | 64 | A\<n> sample count; clamped 1–1000; orange if n > freq\_hz / 30 |
| Boxcar mode | ON | Enables 250 ms A\<n> poll + orange trace |
| Raw Avg trace | ON | Show/hide orange overlay independently of Boxcar |
| Min V/div | 200 µV | 10/20/50/100 µV options removed (v4.12) |

## Gotchas / pertinent notes

- **No auto-connect** — user must press ENT or Connect before Start does anything.
- **Start sequence:** GUI sends `S` then immediately `*<params>` on the same Start press; config
  is applied before the first data record arrives.
- **Output buffer flushed before `E`** — prevents accumulated `A<n>` commands delaying the stop
  by 20–30 s at slow rates (e.g. 6250 Hz / DS 256). `waitForBytesWritten` = 500 ms.
- **`*` command uses ns** for pulse/delay (matches fw v4.23 protocol). The QLineEdit fields
  display µs; conversion happens in `change_parameters()`.
- **Orange highlight** on freq/pulse/delay fields = not on the 8 ns PWM grid or not a clean
  125 MHz divisor. Orange on Avg n = boxcar will exceed 80 % of the 250 ms poll budget.
- **Multi-packet drain:** on each `readyRead`, all buffered `*` lines are drained; only the
  last gets the full chart/UI update. Earlier ones still write to CSV. Prevents display lag
  at high SPS.
- **CSV files** written to `src/data/P<DDMM-HHMMSS>.csv`; new file opened on each Start.
- Settings saved to `src/data/gui_settings.json` on close; restored on next launch.
