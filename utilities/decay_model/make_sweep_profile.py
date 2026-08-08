#!/usr/bin/env python3
"""Generate the single-band 150 us decay-characterisation sweep profile.
TOOL_VERSION = v3

Writes `src/data/profiles/sweep_150us_decay_v1.json`: one band (2 kHz / 150 us)
with a delay ladder chosen for MODELLING the decay, not for detecting targets.

Read-only except for the profile it writes (--out).

# History (full detail in CHANGELOG.md):
#   v3 cal_110 anchors dropped (measured: worth <=0.05 mV past sd 20 us);
#      crossing tightened 0.240 -> 0.160 us and run up to the rail;
#      MIN_GAP_FRAC prunes crowded region junctions
#   v2 --pulse/--freq; regions shifted to the band's measured rail, anchors
#      pulled from the matching cal_110 band
#   v1 initial -- six-region ladder, cal_110 anchors preserved as a superset

Why this profile exists
-----------------------
`cal_110_full_range_v4`'s 150 us band puts exactly TWO columns between clip
release and the rail (7.904 and 10.912 us).  Two points cannot constrain a
decay: fitting the four calibrated cal_63 columns with the slow time constant
pinned at different values gave fits agreeing to <=2 % that predicted anywhere
from +64 mV to -400 mV at sd 14.7 us.  The 2026-08-05/08-07 work did not fail
for want of a better model, it failed for want of samples in the region that
matters.  This ladder puts them there.

Design rules, in order of priority
----------------------------------
1. **Six regions, each sized to the feature it has to resolve** -- see REGIONS
   below.  Step sizes come from the measured curve, not from a geometric rule:
   a single geometric ladder is what under-sampled 8-15 us in the first place.
2. **Every delay lands on the 8 ns PWM grid** (DESIGN Sec 11 -- delays are
   emitted to the wire as `%.3f` us, and 8 ns = 0.008 us is exact at 3 dp).
3. **Every cell is validated against the firmware's own arithmetic** --
   `compute_pulse_duties` / `pulse_duties_valid` are reproduced verbatim below
   so a bad cell is caught here rather than by a `D` rejection on the bench.

Why there are no cal_110 anchors (dropped in v3)
------------------------------------------------
v1/v2 forced the eleven `cal_110_full_range_v4` delays of the matching band into
the ladder so captures would stay "directly comparable" to
`rawlog_20260807_194234.txt`.  Measured, that bought nothing and cost 10-11 of
72 cells.  Sampling the 2026-08-07 air curve onto the anchor-free ladder and
interpolating back to the anchor delays recovers them to **<= 0.05 mV past
sd 20 us** (0.000 mV from 62 us out), against target deltas of 0.09-7.1 mV.  The
one large residual, +2.7 mV at sd 10.912 us, sits on the steep slope where that
cell's own frame-to-frame sigma is 7.8 mV -- inside its own noise.  The railed
cell cannot be interpolated meaningfully and carries no information anyway.

The anchors also crowded the ladder (15.448 -> 15.600 us is a 0.152 us gap inside
a region whose step is 0.600 us, so one of that pair was wasted) and coupled this
profile to another profile -- the coupling that silently broke when the 150 us
file was hand-retargeted to 100 us and kept the wrong band's anchors.  And the
comparability claim was overstated regardless: that session ran 110 cells at
4.07 Hz with a 7.9 s rolling window against this profile's ~7.5 Hz and ~4.3 s, on
a different pack state and soak, and DESIGN Sec 10's `(profile_name,
profile_sha8)` guard exists because cross-profile comparison is not automatically
valid.  The freed cells went into the crossing region.

Two things this profile does NOT carry, deliberately
----------------------------------------------------
* **No `threshold_v`.**  That field is vestigial for streaming (`pimd_rawlog`
  never reads it; `pimd_classviz` guards on its absence).  `cal_110`'s copy was
  carried over unverified and is wrong by a large factor -- its "0.5 V" column
  at 62 us is actually sitting on the pedestal, because 0.5 V is reached near
  11.5 us.  Inventing a fresh set here would repeat exactly that mistake, so
  the field is omitted.  Consequence: `pimd_delaycal` will refuse to import
  this profile ("Profile has no threshold_v field"), which is correct -- this
  is a characterisation sweep, not a calibration.
* **No settling cost.**  Single band, single pulse width, so the firmware's
  `needs_settling` (`at_boundary or dd != cells[prev][2]`) is False for every
  cell including the wrap-around: frequency and drive duty never change, only
  the sample compare value.  There is no per-pulse energy step for settling to
  absorb, which is the only thing BOUNDARY_PRIME/SETTLE_FLOOR_US exist for.
  That is what makes ~70 cells affordable on one band when 110 cells across
  ten bands cost 246 ms.
"""

import argparse
import json
import os

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "..", "src", "data", "profiles")

GRID_US = 0.008              # 8 ns PWM grid
FREQ_HZ = 2000
AVERAGES = 32

# Measured delay of the air minimum (the railed cell) per band, 2026-08-07
# session. The six regions below are positioned against the 150 us band, so a
# profile for a different pulse width is shifted rigidly by the difference --
# the features move with the band, and a ladder centred on the wrong band wastes
# its fine steps either side of where the crossing actually is.
MEASURED_RAIL_US = {100.0: 14.712, 150.0: 15.448}
REFERENCE_PULSE = 150.0

# Firmware constants, mirrored so validation matches the board exactly.
PWM_SCALING_NUMERATOR = 2 ** 16
PWM_SCALING_DENOMINATOR_NS = 10 ** 9
SAMPLE_PULSE_CORRECTION = 0.904

# (name, start, stop, step_or_ratio, geometric?, what it has to resolve)
REGIONS = [
    ("clamp exit", 7.040, 7.850, 0.160, False,
     "where the trace leaves the 4.7 V zener clamp. cal_110 has ZERO points "
     "here, so clip release on this band is currently unmeasured -- it is "
     "inferred from the 100 us band's 7.392 us plus an extrapolated shift."),
    ("decay / tau", 8.000, 12.310, 0.400, False,
     "the volt-scale decay, where tau is measured. 0.4 us is ~0.43 of the "
     "0.92 us tau, so ~11 intervals span ~5 e-folds: enough to pin tau to a "
     "few per cent AND to see whether the shape is (a+bt)exp, a single exp, "
     "or two exponentials -- which is the distinction cal_110's two points "
     "could not make."),
    ("crossing", 12.400, 14.970, 0.160, False,
     "the pedestal crossing and the plunge into the rail. Measured air is "
     "892 mV at 10.912 and railed by 15.448, so the crossing is in here and "
     "has never been sampled. Crossing TIME is the pack-independent "
     "coordinate, so this is the highest-value region on the ladder -- which is "
     "why the cells freed by dropping the anchors were spent here, taking the "
     "step from 0.240 to 0.160 us and running the region right up to the rail "
     "region's 15.000 us start instead of stopping at 14.810 and leaving the "
     "plunge to be covered at 0.600 us."),
    ("rail width", 15.120, 19.810, 0.600, False,
     "maps rail entry and exit. The depth of the lobe is unmeasurable through "
     "a unipolar path, but the WIDTH of the flat bounds it -- that was the "
     "original 2026-08-05 observation and it has never been measured, only "
     "hand-read off a live trace."),
    ("recovery", 20.500, 45.000, 1.090, True,
     "the undershoot's own recovery, tau ~4.2 us from just two points today. "
     "Ten points here decide whether it is one exponential (a single RC / "
     "recovery process) or two, which is the difference between one mechanism "
     "and several."),
    ("late / target", 48.000, 320.000, 1.155, True,
     "the pedestal sag and the target-discrimination window. Copper overtakes "
     "steel near 77 us and is still +0.40 mV at 250 us, so this region is "
     "where material information lives. Extended past cal_110's 250 us stop: "
     "the rep rate allows it and copper had not finished decaying."),
]


def snap(us):
    """Snap to the 8 ns grid, exact at 3 dp so the %.3f wire format is lossless."""
    return round(round(us / GRID_US) * GRID_US, 3)


def compute_pulse_duties(pulse_width_us, sample_delay_us, freq_hz):
    """Verbatim from mcu/pimd_mcu.py -- do not 'simplify' the integer division."""
    pulse_width_ns = int(pulse_width_us * 1000)
    sample_delay_ns = int((sample_delay_us + SAMPLE_PULSE_CORRECTION) * 1000)
    drive = (pulse_width_ns * freq_hz * PWM_SCALING_NUMERATOR
             ) // PWM_SCALING_DENOMINATOR_NS
    sample = drive + (sample_delay_ns * freq_hz * PWM_SCALING_NUMERATOR
                      ) // PWM_SCALING_DENOMINATOR_NS
    return drive, sample


def duties_valid(drive, sample):
    return 0 <= drive <= 65535 and 0 <= sample <= 65535 and sample > drive


MIN_GAP_FRAC = 0.75   # a cell must sit at least this fraction of the finer of
                      # the two local steps away from its neighbour, or it is
                      # dropped as redundant.  Region boundaries do not land on
                      # each other's grids, so without this the junctions crowd:
                      # the crossing region ended 0.040 us before the rail
                      # region began, a pair 15x tighter than the coarser step
                      # and 4x tighter than the finer one, which wastes a cell
                      # for no resolution.  This is the same defect the cal_110
                      # anchors used to introduce, so it is guarded generally
                      # rather than by hand-tuning the region boundaries.


def build(shift_us):
    """Returns {delay_us: region_name}, junction-pruned.

    Each point carries the local step of the region that produced it (for the
    geometric regions that is the step at that point, not the ratio), which is
    what MIN_GAP_FRAC is measured against."""
    tagged = {}                      # delay -> (region name, local step)
    for name, start, stop, step, geometric, _why in REGIONS:
        v = start
        while v <= stop + 1e-9:
            nxt = v * step if geometric else v + step
            # Geometric regions are shifted at their ends, not per point, so the
            # ratio spacing survives the shift.
            tagged.setdefault(snap(v + shift_us), (name, nxt - v))
            v = nxt
    keep, last, last_h = {}, None, None
    for d in sorted(tagged):
        name, h = tagged[d]
        if last is not None and (d - last) < MIN_GAP_FRAC * min(h, last_h):
            continue
        keep[d] = name
        last, last_h = d, h
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pulse", type=float, default=150.0,
                    help="drive pulse width, us (must exist as a cal_110 band)")
    ap.add_argument("--freq", type=int, default=FREQ_HZ, help="rep rate, Hz")
    ap.add_argument("--out", default=None,
                    help="output path; defaults to sweep_<pulse>us_decay_v1.json")
    args = ap.parse_args()

    PULSE_US = args.pulse
    freq_hz = args.freq
    name = f"sweep_{PULSE_US:g}us_decay_v1"
    out = args.out or os.path.join(PROFILES_DIR, name + ".json")

    if PULSE_US not in MEASURED_RAIL_US:
        raise SystemExit(
            f"no measured rail position for a {PULSE_US:g} us band "
            f"(have {sorted(MEASURED_RAIL_US)}) -- the regions are positioned "
            f"against a measured feature, so add one rather than guessing")
    shift = MEASURED_RAIL_US[PULSE_US] - MEASURED_RAIL_US[REFERENCE_PULSE]

    cells = build(shift)
    delays = sorted(cells)
    period_us = 1_000_000 / freq_hz

    print(f"=== {name} — {freq_hz} Hz / {PULSE_US:g} us, "
          f"period {period_us:g} us ===")
    print(f"  regions shifted {shift:+.3f} us from the {REFERENCE_PULSE:g} us "
          f"reference (measured rail {MEASURED_RAIL_US[PULSE_US]:g} us)")
    bad = []
    for d in delays:
        dd, sd = compute_pulse_duties(PULSE_US, d, freq_hz)
        if not duties_valid(dd, sd):
            bad.append((d, dd, sd))
        if abs(d / GRID_US - round(d / GRID_US)) > 1e-6:
            bad.append((d, "off-grid", ""))
    if bad:
        raise SystemExit(f"INVALID CELLS: {bad}")

    dd, sd_last = compute_pulse_duties(PULSE_US, delays[-1], freq_hz)
    print(f"  {len(delays)} cells, all on the 8 ns grid, all duties valid.")
    print(f"  drive duty {dd} (fixed for every cell — hence no settling)")
    print(f"  last cell: sd {delays[-1]:g} us -> sample duty {sd_last}/65535, "
          f"pulse+delay+{SAMPLE_PULSE_CORRECTION} = "
          f"{PULSE_US + delays[-1] + SAMPLE_PULSE_CORRECTION:.3f} us of "
          f"{period_us:g} us")
    est_ms = len(delays) * 2.0
    print(f"  estimated sweep ~{est_ms:.0f} ms -> ~{1000/est_ms:.1f} Hz "
          f"(cal_110 measured 2.24 ms/cell across 110 cells)")
    print(f"  rolling average {AVERAGES} deep -> window "
          f"~{AVERAGES*est_ms/1000:.1f} s\n")

    by_region = {}
    for d in delays:
        by_region.setdefault(cells[d], []).append(d)
    # NB: not `name` -- that is the profile name, and shadowing it here silently
    # stamped the last region's label into the JSON's "name" field.
    for rname in [r[0] for r in REGIONS]:
        ds = by_region.get(rname, [])
        if not ds:
            continue
        print(f"  {rname:16s} {len(ds):3d} cells  {ds[0]:8.3f} – {ds[-1]:8.3f} us")

    profile = {
        "name": name,
        "notes": (
            "Single-band 150 us decay-characterisation sweep, 2026-08-08. NOT a "
            "calibration and NOT a detection profile: the ladder is chosen to "
            "model the air decay, its pedestal crossing, the clipped negative "
            "lobe and the recovery, which cal_110_full_range_v4 samples with "
            "only two points between clip release and the rail. Strict superset "
            "of cal_110_full_range_v4's 150 us band (all 11 delays preserved "
            "exactly), so captures remain comparable to rawlog_20260807_194234. "
            "No threshold_v: the field is vestigial for streaming and cal_110's "
            "copy is wrong by a large factor, so inventing one here would repeat "
            "that error — pimd_delaycal will therefore refuse to import this, "
            "which is correct. Generated by "
            "utilities/decay_model/make_sweep_profile.py v1."),
        "averages": AVERAGES,
        "bands": [{
            "freq_hz": freq_hz,
            "pulse_us": PULSE_US,
            "delays_us": delays,
        }],
    }
    assert profile["name"] == f"sweep_{PULSE_US:g}us_decay_v1", (
        f'profile name got clobbered: {profile["name"]!r}')
    out = os.path.abspath(out)
    with open(out, "w") as fh:
        json.dump(profile, fh, indent=2)
        fh.write("\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
