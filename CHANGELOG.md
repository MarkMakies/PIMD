## [unreleased] — 2026-06-17

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
| 4 | 56992/clear Hz   |  5 µs | 6.03 6.43 6.78 7.12  7.46  7.84  8.28  8.85  9.71 |

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
