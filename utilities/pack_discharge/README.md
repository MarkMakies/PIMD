# pack_discharge — 6S pack discharge rate from classviz session dumps

Works out how fast the pack drains under classviz streaming load, and how much
streaming time is left before the **21.0 V working floor** (DESIGN §12) and the
**18.0 V** allowable-discharge / L7815-dropout limit.

Everything comes from the `# pack_v:` comment lines a session dump already
carries. Pack voltage is **not telemetry** — there is no voltage field anywhere
in the serial protocol (DESIGN §9) and no sensing in firmware, so every data
point is a DMM reading typed into classviz's **Pack V** box and committed with
**Log V**. More Log V presses, spread across a wider voltage range, is the only
thing that improves the result.

## Status: a local utility, tracked, logged in `CHANGELOG.md`

Lives at `<repo>/utilities/pack_discharge/`. Not part of the PIMD toolset — it consumes
session dumps and produces analysis, and nothing in `src/` imports it — but it **is**
tracked, because `CHANGELOG.md` cites it and anything cited has to be reproducible from
a clone.

- **History goes in `CHANGELOG.md`**, under `### utilities/pack_discharge/ — v<N>`, same
  format and discipline as every other entry. There is no separate local change log; one
  briefly existed and was folded back in. Record behaviour-changing edits there.
- The scripts carry `TOOL_VERSION` and a terse `# History:` header lineage, as house style
  requires.
- Generated output — `packv_cycle0.json`, `pack-discharge.html`, `__pycache__` — is
  gitignored. Everything here regenerates from the session dumps in one command.
- Nothing writes to the repo; the dumps are opened read-only.
- No `DESIGN §15` inventory row: that section inventories the toolset, and this is not part
  of it. If it ever becomes something `src/` depends on, that is when it earns a row.

## Running it

Needs the project venv (for nothing exotic — stdlib only, but keep it consistent):

```bash
cd ~/Projects/PIMD/utilities/pack_discharge
../../.venv/bin/python packv.py --out packv.json
../../.venv/bin/python build_page.py
```

The sessions directory is resolved relative to the script, so no path flag is
needed while it sits in the repo.

That writes `packv.json` (all derived numbers) and `pack-discharge.html`
(self-contained page — open it directly, or publish it as an artifact).

Useful flags:

| flag | effect |
|---|---|
| `--date YYYYMMDD` | which day's sessions to read (default: today) |
| `--sessions-dir DIR` | override the dump location |
| `--end-cell 2.75` | deeper allowable floor than the 3.00 V/cell default |
| `--rested-min 8` | widen the post-load-on exclusion window |
| `--cycle 0` | analyse a specific charge cycle (default `latest`; `all` spans everything) |
| `--recharge-v 0.5` | voltage rise that counts as a recharge (default 0.8 V) |

**One run = one charge cycle**, and since v2 the tool enforces this rather than
trusting you. A voltage rise beyond `--recharge-v` (0.8 V, comfortably above the
+0.29 V that rest recovery can produce) opens a new cycle; streaming time re-zeros
per cycle, and by default the **latest** one is analysed. `--cycle 0` reaches the
first of the day, `--cycle all` restores the old span-everything behaviour.

This matters because v1 got it wrong in exactly the way that is hardest to notice:
it fitted across a 20:52 pack swap and reported a confident runtime that was pure
artefact, with the only evidence a residual it never surfaced. Fit-quality warnings
now go to stderr *and* onto the page — more than one cycle, fitted span under 0.5 V,
fewer than 5 readings, or residual RMS over 200 mV.

## How the model works

The classviz profile loop draws a fixed duty, so pack current is constant, so
charge drains **linearly in time**. State of charge is therefore a straight line
in *streaming* time by construction — which is why that, not wall clock, is the x
axis, and why the chart's y axis is linear in SoC while the voltage scale on the
right is not. The voltage ticks bunching up through the plateau *is* the pack's
plateau, made visible.

Rather than trusting a datasheet curve, two parameters are fitted to the readings:

- `T` — streaming minutes from a full pack to the empty-cell voltage
- `offset` — a constant volts/cell aligning the assumed curve to these readings

```
V_pack(t) = 6 * ( Vcell_ocv(100 * (1 - t/T)) - offset )
```

`Vcell_ocv` is a nominal Samsung **ICR18650-26C** open-circuit shape. The two
parameters stretch and offset that shape but **cannot change it** — the main
structural limit of the model.

### The offset is not internal resistance

Worth stating plainly, because it looks like it should be and was described that way
until 2026-07-30. Measured directly, this pack sags **0.29 V** under load — the
operator read pack B at 25.04 V no-load / 24.96 MCU-only / 24.75 V running, recorded
in `CHANGELOG.md`'s 2026-07-30 findings entry. The fit wants **~0.95 V** (159 mV/cell),
roughly three times that. So most of the offset is the nominal curve not matching
these cells, not anything electrical.

Consequence for how the output should be read: **trust the runtime the fit implies,
not the shape of the curve it draws.** The runtime is cross-checked and holds up (see
below); the voltage axis is an alignment of a nominal curve, not a measured one.

## Three corrections the raw log requires

Skip any of these and the answer is wrong, not just noisy:

1. **`age_s` must be applied.** The `# pack_v:` line in a dump's *header* is the
   spinbox value restored from settings at session open, not a fresh reading.
   True measurement time is `logged - age_s`. On 2026-07-30 the live session
   opened with `22.25, age_s=5659` — measured 95 min *before* that session
   existed. Applying this recovers a genuine reading and collapses phantom
   duplicates. A header line with **no** `age_s` (pre-v1.66 two-field form, or
   `age_s=unknown`) cannot be dated and is dropped.
2. **The x axis must be accumulated streaming minutes.** Idle drain measured
   ~0.019 V/h against ~0.27 V/h streaming — a ~14× ratio. Wall clock would
   flatten the slope through every gap between sessions. Per-session streaming
   time comes from each dump's first→last data-row span, because `# soak:` lines
   (which carry `streamed_s`) only exist in recent dumps and one reported
   `streamed_s=0`.
3. **Readings within 5 min of load-on are rested voltage**, not
   settled-under-load, and sit high — 15:01:45 read 22.85 V, *above* 12:38's
   22.56 V, after a 2 h rest. Excluded from the fit, drawn hollow on the chart.

## Reading the robustness numbers

- **`loo`** — leave-one-out: refit dropping each reading in turn. This is the
  check that means something. On 2026-07-30 it held T within 612–626 min (2.3%).
- **`subsets`** — per-session-group fits, reported **with each subset's voltage
  span**, and kept for diagnosis rather than validation. Splitting the day in
  half is *not* a valid cross-check: a subset confined to the plateau spans too
  little voltage to separate `T` from `sag` (they trade off), so it can return a
  wildly different T with a compensating sag and no real disagreement. On
  2026-07-30 the newest session alone spanned 0.99 V and returned T ≈ 1030 min
  with a +307 mV/cell sag, while 3 earlier readings sitting where the curve bends
  gave 608 min. **Constraining the runtime needs curvature, not more points on
  the flat** — so if you want a better number, take readings early in a charge
  cycle, not just near the floor.
- **`fit.T_min_lo/hi`** — the span over which RMSE stays within +10 mV of best.

## Known limitations

- **`x = 0` assumes the pack was full when the day's first session began.** If it
  wasn't, `T` is not full-pack capacity but a scaled equivalent, and every
  projection shifts with it. Nothing in the data can confirm it — on 2026-07-30
  no voltage was logged before 11:29, ~3 h into the day's streaming.
- **The terminal knee is extrapolated, not observed.** Readings stop well above
  the floor; everything below is the curve's shape. The straight
  voltage-vs-time extrapolation (`linfit.h_to_floor`) is the optimistic bound.
- **Pack construction is inferred, not known.** The implied Ah (`T` × ~0.5 A from
  DESIGN §17.1) only *suggests* a cell configuration.
- Readings are 10 mV resolution; curve-shape mismatch dominates that anyway
  (residual RMS was ~51 mV on 2026-07-30).

## Files

| file | what |
|---|---|
| `packv.py` | parses dumps, applies the corrections, fits, emits JSON |
| `build_page.py` | renders that JSON to a self-contained HTML page |
| `packv.json` | derived numbers (regenerable — safe to delete) |
| `pack-discharge.html` | the rendered page (regenerable) |

Colours in the chart are the two validated palette slots (series blue, status
critical) plus documented neutral chrome; the set clears every check of the
data-viz palette validator in both light and dark mode. Keep it that way if you
edit the styling.
