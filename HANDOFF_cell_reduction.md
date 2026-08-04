I'm working on PIMD (pulse-induction metal detector) — read `CLAUDE.md` first for how to
work in this repo, then `DESIGN.md` (ground truth for specs/protocol/invariants — §9 serial
protocol, §10 profiles, §11 invariants, §16 run commands) and the tail of `CHANGELOG.md` for the
last few entries (dated 2026-08-03) covering delaycal v1.43/v1.44 and the new `src/pimd_rawlog.py`
tool.

Goal: `src/data/profiles/cal_110_full_range_v4.json` is our current working/testing profile —
10 bands x 11 thresholds = 110 cells, geometric delay ladder out to 200 µs (or max for channel). Before starting any
ML training against it, I want to work out which rows (bands) and/or columns (thresholds) can
be dropped without losing information, to cut sweep/frame time and thermal exposure.

Tool: `src/pimd_rawlog.py` (v1.00) — a deliberately minimal PyQt6 logger. Load Profile, Start
(streams the profile via the documented `E`/`D`/`Q5`/`G` sequence), and every raw line from the
firmware gets appended verbatim to a timestamped file in `src/data/sessions/`. 

Use targets_v4.  user will select target as well as one additional parameter - distance from coil in mm.  
note that all measurement will be taken in a position near the inner coil, any long opjects alligned with coil
and flat ones on there flat edge.  Like a free-text Note field — use it to bracket every target placement/removal with a timestamped
note, since the analysis segments the log by those markers.

there should be a button indicating that i am placing a target, and removing the target.  and an indicator
showing enough data is collected, either air or target and i can move on, proabably like to settle and detect in classviz, but use you're own metrics for this (adjustable) don't borrow its code.  it will also be beneficial to determine when rig is sufficientlty settled and warm and ready for action

I'll work at my own pace.  i may need to stop and restart occassionally so we will need to be able to load and cont previous session.



Analysis once we have enough data: segment the log by NOTE markers, take each cell's settled
mean per window, then score each of the 110 cells on (a) discriminative power — variance across
different target conditions versus its own repeat noise — and (b) redundancy — correlation with
neighbouring cells. Rank cells, propose a reduced profile, and write it up as a new
`CHANGELOG.md` entry so the reasoning is preserved. Final cutoff is my call once you show me the
ranking.


