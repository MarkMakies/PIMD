# pimd_delaycal.py — Cheat Sheet (v1.19)

## What it is
PyQt6 desktop app that sweeps the sample delay across configured freq/pulse pairs,
finds the delay at which the ADC reading crosses each target voltage threshold (the
clip-release / earliest-valid-sample point), and exports calibrated delay profiles
for use by `pimd_classviz.py`.

## What it does
- Coarse+fine two-phase sweep per freq/pulse pair: fast coarse hunt to find signal
  entry, then fine-step sweep to interpolate threshold crossings.
- Threshold-crossing delays snapped to 8 ns PWM grid; stored and exported to 3 d.p. (µs).
- Exports calibrated profiles as classviz-compatible JSON (`data/profiles/cal_<ts>.json`).
- Thermal monitoring: streams Mode 2 with the calibrated profile, shows live
  latest-mean and rolling-σ per channel.
- Auto Nudge: iteratively adjusts per-channel delays to escape noisy LC-ringing zones.
  Two sub-modes — Parallel (default) or Sequential — selectable via checkbox.

## Modes of operation

| Mode | How entered | Exits when |
|------|-------------|------------|
| **Idle** | startup / stop pressed | — |
| **Sweeping** | Run button | all pairs complete, Stop, or max delay reached |
| **Thermal** | THERMAL button (post-sweep) | countdown expires or Stop |
| **Auto Nudge** | Auto button (post-sweep) | all channels pass / max iterations / Stop Auto |

Thermal and Auto Nudge both use Mode 2 streaming internally; they cannot run concurrently.

## Serial protocol — commands sent / records consumed

| Dir | Token / format | Meaning |
|-----|---------------|---------|
| → MCU | `E` | Universal stop — sent on connect, stop, done, close |
| → MCU | `*<freq_hz>,<pulse_ns>,<delay_ns>,256` | Configure Mode 1 params (ds hardcoded 256) |
| → MCU | `A<n>` | Request one boxcar average of n raw samples |
| → MCU | `D<avg>;<freq_hz>,<pulse_us>,<d0_us>,...;...` | Define dynamic profile (profile 5); pulse/delays in **µs**, freq in Hz |
| → MCU | `Q5` | Select dynamic profile (index 5 always) |
| → MCU | `G` | Start Mode 2 streaming |
| ← MCU | `R<t_ms>,<mean_uV>,<sd_uV>,<n>,<freq_hz>,<pulse_ns>,<delay_ns>,<min_uV>,<max_uV>` | Boxcar result — drives sweep logic |
| ← MCU | `W<prof_idx>,<t_ms>,<mean_ch0>,<mean_ch1>,...` | Mode 2 frame — drives thermal / Auto Nudge |

⚠ `*` command takes pulse/delay in **ns**; `D` command takes pulse/delays in **µs** — different units for the same physical quantities.

## Key parameters / defaults

| Parameter | Default | Notes |
|-----------|---------|-------|
| Freq/Pulse pairs | `25/10, 20/20, 5/40` kHz/µs | Rows of the calibration table |
| Target voltages | `4.5, 4.0 … 0.5` V (9 levels) | Columns; sorted descending at run time |
| Start delay | 5.0 µs | Beginning of each sweep |
| Coarse step | 1.0 µs | Hunt step until signal < Signal detect V |
| Signal detect | 4.9 V | ADC level below which real signal is present |
| Fine step | 0.10 µs | Step after coarse hunt backs up to last clean position |
| Max delay | 45.0 µs | Cell marked N/R if not reached within this limit |
| Averages N | 100 | Samples per `A<n>` call |
| Thermal duration | 240 s | Countdown for thermal monitoring session |
| Std dev N | 50 frames | Rolling window for σ (shared by Thermal and Auto Nudge) |
| Auto soak | 20 s | Settle time per Auto Nudge iteration |
| Auto threshold | 0.50 mV | σ above which a channel is considered noisy |
| Nudge step | 80 ns | Delay shift per Auto Nudge attempt (8 ns grid) |
| Cap ± | 960 ns | Max total deviation from calibrated delay |
| Sequential | unchecked | Parallel (all bad channels nudged together) is default |

Settings are persisted to `src/data/delaycal_settings.json` on exit.

## Gotchas / pertinent notes

- **Import Profile** loads a JSON profile directly into the table, enabling Thermal / Auto
  Nudge without running a sweep — useful for re-checking a previously calibrated set.
- **Auto Nudge needs ≥ 2 channels** (≥ 2 target voltages or ≥ 2 freq/pulse pairs); single-
  channel Mode 2 has ~25 mV noise and is useless for σ comparison.
- **1-second settling gate** after each `G` command: W records are discarded for 1 s to let
  the signal settle before σ accumulation begins — avoids false yellow flicker.
- **Coarse hunt backs up one step** when signal first appears, not to the start delay.
  If signal appears on step 1, it backs up to start_delay.
- **N/R cells are excluded from Auto Nudge** (skip list built from table text on Auto start).
- **Auto Nudge exports profile automatically on finish** (calls `export_profile()`).
- **Nudge direction: −ns first** (toward earlier delays); flips to +ns when the cap is hit
  in the negative direction; flags the channel if both directions are capped.
- **Thermal table rows sorted ascending by pulse_us** (shortest pulse first); calibration
  table stays in run order. Flat channel index = `band × n_cells + cell`.
