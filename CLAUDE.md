# CLAUDE.md

Working brief for AI agents (Claude Code) editing the **PIMD** project.

This file is *how to behave* in this repo. It is **not** project documentation —
all specs, measured values, design rationale, the serial protocol, profiles and
invariants live in **`README.md`**, which is the ground truth. When you need a
fact, read `README.md` (section pointers below). 

## Mindset

- **It already works — refine, don't redesign.** This is a field-tested detector,
  not a bring-up. No "you should have used X" rewrites without a concrete defect.
- If your analysis implies the detector **"can't work"** the way it's built, you
  are missing context — **flag the concern, don't assert a contradiction.** The
  builder has scope captures proving otherwise.
- When you **cannot** determine something from text alone (analogue behaviour, PCB
  layout, scope data), **say so explicitly** rather than guessing.
- Keep changes **minimal and reversible.** Prefer a flagged main-loop fix over
  restructuring the ISR / acquisition model unless asked.

## Don't break the invariants

Never violate the invariants in **README §11** without an explicit request. In
brief: same-slice PWM phase-locking (GPIO4/5, slice 2), the serial wire format
(§9), **no firmware scan-scheduler**, and **no flash writes in
the hot path** (they spike the noise floor ~10×). Read §11 before any change that
might touch one.

## Firmware / MCU conduct

- The MCU stays a **simple primitive** — no PC-driven scan engine, no scheduler
  beyond the fixed profile loop. (Invariant, §11.)
- Keep a single read-line / write-line **serial transport seam** (USB-serial).
- `mcu/pimd_mcu.py` is **MicroPython, pure-Python only** — no CPython-only libs.

## PC tools

- PC tools are **PyQt6**. See **README §15** for the file inventory and which file
  owns which mode. `pimd302.py` is the superseded v3.x GUI — don't extend it.

## Environment & deploy

- **Always work inside a venv.**
- Exact run / deploy / firmware-flash / bench-test commands are in **README §16** —
  use those, don't improvise. (Firmware deploys by copy-then-power-cycle, *not*
  `mpremote reset`.)

## Versioning & changelog (important)

- **On every file edit: bump that file's version number and add an entry to
  the file's header changelog.** Required, not optional.
- **Record every change in `CHANGELOG.md`** — firmware, PC tools, hardware, or new
  findings. One entry per change, added above the marker line, in the format at the
  foot of `CHANGELOG.md`: `### <file> — v<N> — <short title>`, then a short
  paragraph covering *what changed · why · (date)*.
- **Do not edit `README.md` directly.** It is a curated snapshot, regenerated from
  `CHANGELOG.md` by a periodic human-run consolidation pass. Treat it as stable
  reference, not a scratchpad. (Only exception: a deliberate, human-directed
  restructuring — and then bump the Doc-rev line at the top of the README.)
- **Test-log observations go in `CHANGELOG.md` too**, not into README §17 directly —
  they are folded into §17 at consolidation.
