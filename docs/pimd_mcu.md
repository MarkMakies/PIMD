# pimd_mcu.py — Cheat Sheet (fw v4.23)

## What it is
MicroPython firmware for the RP2040-Zero. Drives the TX coil via PWM, times the
ADC sample trigger, and streams acquisition data to the PC over USB-serial.

## What it does
- Generates phase-locked TX pulse + sample trigger on GPIO4/GPIO5 (same PWM slice 2).
- Reads the LTC2508-32 in two paths: filtered 32-bit (SPI1/SDOA) and raw 14-bit (SPI0/SDOB).
- Mode 1: interrupt-driven filtered acquisition, downsampled rolling mean + σ.
- Mode 2: interleaved rolling-average sweep across a fixed scan profile (multi-cell, multi-band).
- Accepts ASCII commands over USB-serial (115200 baud); emits labelled ASCII records.

## Modes of operation

| State | Entered by | Exits by |
|-------|-----------|---------|
| `ready` | power-on / after stop | — |
| `mode1_running` | `S` | `E` |
| `mode2_running` | `G` (after `Q<n>`) | `E`, or profile change via `Q` |
| `stop` | `E` from either mode | auto-returns to `ready` |

`S` rejected while Mode 2 running. `G`/`A`/`*`/`D` rejected while Mode 1 running.
**Always send `E` before switching modes.**

## Serial protocol (115200 baud, USB-CDC)

### Commands → MCU

| Token | When valid | Meaning |
|-------|-----------|---------|
| `S` | ready / mode1 | Start Mode 1 streaming |
| `E` | any | Stop (universal) |
| `*<freq_hz>,<pulse_ns>,<delay_ns>,<ds>` | not mode2 | Configure Mode 1 params (freq Hz; pulse/delay in **ns**) |
| `G` | ready / mode2 | Start Mode 2 streaming (profile must be selected) |
| `Q<n>` | any | Select profile n; if mode2 running, restarts sweep |
| `D<avg>;<hz>,<pw_us>,<d1_us>,...;...` | not mode2 | Define RAM-only dynamic profile (pulse/delays in **µs**, freq in Hz) |
| `A<n>` | not mode2 | Boxcar-average n raw samples (1–1000) at held config |
| `V` / `v` / `?` | any | Identify / firmware version |
| `L` | any | List all profiles |
| `B` | any | Report + reset diagnostic counters |

### Records ← MCU

| Record | Source | Format |
|--------|--------|--------|
| `*` | Mode 1 | `*<t_ms>,<val_uV>,<sd_uV>,<freq_hz>,<pulse_ns>,<delay_ns>,<ds>` |
| `W` | Mode 2 | `W<prof_idx>,<t_ms>,<mean_ch0>,<mean_ch1>,...` (µV, one per cell) |
| `R` | `A<n>` | `R<t_ms>,<mean_uV>,<sd_uV>,<n>,<freq_hz>,<pulse_ns>,<delay_ns>,<min_uV>,<max_uV>` |
| `V` | `V`/`v`/`?` | `V<fw>,<board_id>,<n_profiles>,<active_idx>,<freq_hz>,<pulse_ns>,<delay_ns>,<ds>` |
| `L` | `L` | `L<idx>,<freq_hz>,<n_bands>,<n_cells>,<avg>,<name>` (one line per profile) |
| `Q` | `Q<n>` | `Q<n> OK: <name>` |
| `D` | `D` | `D OK: <n_bands> bands x <n_delays> delays, averages=<n>` |
| `B` | `B` | `B<busy_high_count>,<overrun_count>` |

µV scaling: Mode 1 → `raw32 × 5_000_000 // 2³¹`; Mode 2 / A → `raw14 × 10_000_000 / 2¹⁴`.

## Key parameters / defaults

| Parameter | Default | Notes |
|-----------|---------|-------|
| `sample_frequency_hz` | 10 000 Hz | SoC: 10 kHz |
| `pulse_width_us` | 20.0 µs | SoC: 20 µs |
| `sample_delay_us` | 10.0 µs | SoC: 10 µs |
| `down_sample` | 256 | SEL0 pin; 1024 also valid |
| `SAMPLE_PULSE_CORRECTION` | 0.904 µs | Measured PWM-edge → ADC-trigger offset; baked into duty calc |
| Active profile | 0 (FAST_TRACK) | Profiles 0–4 compiled in; index 5 = dynamic (D cmd) |
| `BOUNDARY_PRIME` | 15 periods | Extra settling periods at band boundaries in Mode 2 |
| Mode 2 max emit rate | 100 Hz | `MIN_EMIT_MS = 10` |

## Profiles (compiled-in)

| Idx | Name | Config | Cells | Avg |
|-----|------|--------|-------|-----|
| 0 | FAST_TRACK | 5 kHz / 40 µs / 8.4 µs | 1 | 8 |
| 1 | CLASSIFY | 10 kHz / 3 pulse × 8 delays | 24 | 32 |
| 2 | SCOPE_CAL | 5 kHz / 10 µs / 8 delays | 8 | 1 |
| 3 | TRACK_25K | 25 kHz / 10 µs / 7.6 µs | 1 | 16 |
| 4 | CLASSIFY_EP | 5 equal-power bands × 9 delays | 45 | 32 |
| 5 | DYNAMIC | set by `D` command; RAM only, lost on reset | — | — |

## Gotchas / pertinent notes

- **`*` command uses ns for pulse/delay; `D` command uses µs.** Mixed units — do not confuse.
- **Raw effective sample rate ~1.6 kHz** (not 10 kHz): BUSY-edge sync in MicroPython catches
  ~1-in-6 BUSY-high pulses; accepted tradeoff for bit-accuracy.
- **Mode 2 single-cell = high noise (~25 mV).** Use Mode 1 for single-point measurement.
  Multi-cell profiles unaffected (~310 µV at avg=32).
- **10 % plausibility gate** on raw samples: outliers > 10 % from rolling mean are replaced
  with the mean (secondary defence; primary is the IRQ critical section around BUSY+SPI).
- **No flash writes in the hot path** — flash writes spike noise floor ~10×.
- **Phase-locked PWM:** GPIO4 + GPIO5 must stay on the same PWM slice (slice 2). Never split.
- `B` diagnostic counters are temporary; `B` resets them on read.
