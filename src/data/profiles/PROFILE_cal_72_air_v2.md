# PIMD Operating Profile — `cal_72_air_v2` (LOCKED)

**Frozen:** 2026-07-03 · **Cal run:** `cal_20260703_100838.json` (delaycal v1.19, fw v4.23, hw 6.04, coil v4)
**Status:** canonical Mode 2 operating profile. All 72 cells passed, 1 delay adjusted (+40 ns, ch9).
Air calibration, bench supply, fully warmed. Geometry change vs all earlier profiles — frames are
**not** comparable with data logged under `cal_profile_8b` or the 4.5 V-anchored interim cals.

---

## 1. Band plan

Pulse widths geometric ×≈1.5 (6 → 100 µs); frequencies snapped to the CLEAN_FREQS
125 MHz-divisor list; duty absorbs the quantisation.

| Band | Freq (kHz) | Period (µs) | Pulse (µs) | Pulse (ns ÷8) | Duty | Pulse step ratio | Band time / frame* |
|---|---|---|---|---|---|---|---|
| 1 | 50.0 | 20 | 6.00 | 6000 ✓ | 30.0 % | — | 5.8 ms (2.0 %) |
| 2 | 25.0 | 40 | 9.00 | 9000 ✓ | 22.5 % | 1.500 | 11.5 ms (4.0 %) |
| 3 | 20.0 | 50 | 13.44 | 13440 ✓ | 26.9 % | 1.493 | 14.4 ms (5.0 %) |
| 4 | 15.625 | 64 | 20.00 | 20000 ✓ | 31.25 % | 1.488 | 18.4 ms (6.4 %) |
| 5 | 10.0 | 100 | 30.00 | 30000 ✓ | 30.0 % | 1.500 | 28.8 ms (10.0 %) |
| 6 | 6.25 | 160 | 45.00 | 45000 ✓ | 28.1 % | 1.500 | 46.1 ms (15.9 %) |
| 7 | 4.0 | 250 | 67.20 | 67200 ✓ | 26.9 % | 1.493 | 72.0 ms (24.9 %) |
| 8 | 3.125 | 320 | 100.00 | 100000 ✓ | 31.25 % | 1.488 | 92.2 ms (31.9 %) |

\* 9 delays × 32 averages × period. Full-sweep refresh ≈ **289 ms**; W-record stream rate
observed ≈ 7.3 Hz. Bands 7+8 consume ~57 % of acquisition time — retained deliberately:
2026-07-02 target session showed both ferrous targets and copper still rising steeply at the
top of the ladder, so band 8 carries real long-τ information.

## 2. Threshold ladder (columns)

Geometric, anchor 4.2 V → floor 0.5 V, ratio (0.5/4.2)^(1/8) ≈ **0.766** per step.

| Cell | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Threshold (V) | 4.20 | 3.22 | 2.47 | 1.89 | 1.45 | 1.11 | 0.85 | 0.65 | 0.50 |
| Step ratio | — | 0.767 | 0.767 | 0.765 | 0.767 | 0.766 | 0.766 | 0.765 | 0.769 |

Each cell sees the same fractional amplitude drop; time spacing self-adjusts to the local
decay rate (decay measured non-exponential: local τ ≈ 3 µs near the top of the window
falling to ≈ 1.2 µs near 0.5 V).

**Why 4.2 V, not 4.5 V (or the original 4.8 V):** the top anchor sat too close to the
~4.7 V clamp rail. At 4.8 V the first cell was effectively in clip; at 4.5 V it passed but
was consistently the noisiest column in every cal and in air (clamp-release region, flattest
part of the curve — small amplitude error = large time error, and thermal drift appears
there first). Dropping to 4.2 V gave the column normal σ (0.08–0.57 mV in the freeze cal)
at negligible cost in dynamic range.

## 3. Calibrated delays (µs after TX cutoff, all ÷8 ns grid)

| Band (kHz/µs) | 4.20 V | 3.22 V | 2.47 V | 1.89 V | 1.45 V | 1.11 V | 0.85 V | 0.65 V | 0.50 V | Span |
|---|---|---|---|---|---|---|---|---|---|---|
| 50 / 6 | 6.272 | 6.872 | 7.328 | 7.736 | 8.104 | 8.448 | 8.784 | 9.088 | 9.376 | 3.104 |
| 25 / 9 | 6.800 | 7.376 | 7.832 | 8.240 | 8.608 | 8.960 | 9.296 | 9.608 | 9.904 | 3.104 |
| 20 / 13.44 | 7.256 | 7.872 | 8.336 | 8.744 | 9.120 | 9.472 | 9.808 | 10.128 | 10.424 | 3.168 |
| 15.625 / 20 | 7.728 | 8.352 | 8.824 | 9.232 | 9.616 | 9.968 | 10.312 | 10.632 | 10.936 | 3.208 |
| 10 / 30 | 8.216 | 8.848 | 9.320 | 9.744 | 10.120 | 10.480 | 10.824 | 11.152 | 11.448 | 3.232 |
| 6.25 / 45 | 8.776 | 9.416 | 9.888 | 10.312 | 10.696 | 11.056 | 11.400 | 11.728 | 12.032 | 3.256 |
| 4 / 67.2 | 9.328 | 9.968 | 10.448 | 10.872 | 11.248 | 11.616 | 11.960 | 12.288 | 12.584 | 3.256 |
| 3.125 / 100 | 9.752 | 10.384 | 10.856 | 11.272 | 11.656 | 12.016 | 12.352 | 12.680 | 12.976 | 3.224 |

First-delay (clip-release) increment band-to-band: 0.528 / 0.456 / 0.472 / 0.488 / 0.560 /
0.552 / **0.424** µs — the smallest step is again 67.2 → 100 µs, the recurring
coil-current-plateau hint (open question; needs a scope on coil current vs pulse width).

## 4. Why band 2 runs at 25 kHz, not 31.25 kHz

The ladder's duty rule pointed to 31.25 kHz for the 9 µs pulse. In practice the entire
31.25 kHz row was unusable: three cells never settled (σ 2–5 mV) and even the "passing"
tail cells sat 5–10× noisier than every other band, with non-monotonic means — ringing-like
structure superimposed on the decay. Moving the band to **25 kHz with the pulse unchanged**
collapsed the whole row to normal (σ 0.02–0.10 mV). The noise followed the repetition rate,
not the pulse/decay alignment: 31.25 kHz is a bad rep rate for this system, consistent with
the long-standing finding (DESIGN §8) that rate choice interacts with periodic processes
(beat frequencies); the specific mechanism at 31.25 kHz is unconfirmed. Cost of the fix:
band 2 duty drops to 22.5 % (slightly cooler than its neighbours) — harmless. 31.25 kHz
should be treated as a known-bad rate for future profiles.

## 5. Operating notes

- **Warm-up: ≈ 5 min running Mode 2 in ClassViz** before data is representative — until
  thermal drift settles to a reasonable level. (Supersedes the 4-min Mode 1 SoC figure for
  Mode 2 use; established by repeated-cal deltas: heavy bands drift up to ~250 ns cold-ish,
  collapsing to ≤ 40 ns once soaked.)
- Averages 32 per cell · raw path (SDOB) · µV scaling per DESIGN §9.
- Air noise under this geometry (drift-corrected): ≈ 0.55 mV median per cell;
  top three threshold columns noisiest (~1.0–1.3 mV), 0.5 V column quietest (~0.6 mV).
- Watch item: band 8 remains the slowest-settling, highest-σ band.
- Known-good target SNR at close range (2026-07-02 session): 43–122× air floor.

## 6. Provenance

| Stage | File | Note |
|---|---|---|
| Old profile | `cal_profile_8b` | linear-ish pulses, 4.8 V linear thresholds |
| Geometric pulses, linear V | `cal_20260702_163936` | first run of new ladder |
| Geometric V (4.5 anchor) | `cal_20260702_165109` | non-exponential decay found |
| 31.25 kHz problem found | `cal_20260702_174257` | band 2 red cells |
| Band 2 → 25 kHz | `cal_20260702_180813` | all 72 passed |
| Target session profile | `cal_20260702_202505` | 7-target validation data |
| **LOCKED** | **`cal_72_air_v2`** (from run `cal_20260703_100838`) | 4.2 V anchor, all passed, 1 nudge |
