# CLAUDE.md

Working brief for AI agents (Claude Code) editing the **PIMD** project.

This file is *how to behave* in this repo. It is **not** project documentation —
all specs, measured values, design rationale, the serial protocol, profiles and
invariants live in **`DESIGN.md`**, which is the ground truth. When you need a
fact, read `DESIGN.md` (section pointers below). 

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

Never violate the invariants in **DESIGN §11** without an explicit request. In
brief: same-slice PWM phase-locking (GPIO4/5, slice 2), the serial wire format
(§9), **no firmware scan-scheduler**, and **no flash writes in
the hot path** (they spike the noise floor ~10×). Read §11 before any change that
might touch one.

## Firmware / MCU conduct

- The MCU stays a **simple primitive** — no PC-driven scan engine, no scheduler
  beyond the fixed profile loop. (Invariant, §11.)
- Keep a single read-line / write-line **serial transport seam** (USB-serial).
- `mcu/pimd_mcu.py` is **MicroPython, pure-Python only** — no CPython-only libs.
- Ensure that Invariants, **DESIGN.md §11**, are ALWAYS respected.  Flag if there is a conflict.

## Environment & deploy

- **Always work inside a venv.**
- Exact run / deploy / firmware-flash / bench-test commands are in **DESIGN §16** —
  use those, don't improvise. 

## Versioning & changelog (important)
- Stage everything as commits I can review before they land; **don't push without explicit instruction.**
- **Version number tracks functional change.** On every behaviour-changing edit,
  bump the file's version — the `APP_VERSION`/`TOOL_VERSION` constant and/or the
  title line in the header. Pure comment/doc/reformat edits don't bump.
- **File headers carry a terse one-line-per-version lineage, not prose.** Under a
  `# History (full detail in CHANGELOG.md):` heading in the header, add one line
  per version — `#   v<N> <short phrase>`, newest first. **No paragraphs in
  headers** — the full narrative lives only in `CHANGELOG.md`. Leave the
  non-changelog reference content (purpose, protocol/interface notes, schema
  docstrings) untouched.
- **Record every change in `CHANGELOG.md`** — firmware, PC tools, hardware, or new
  findings. One entry per change, added above the marker line, in the format at the
  foot of `CHANGELOG.md`: `### <file> — v<N> — <short title>`, then a short
  paragraph covering *what changed · why · (date)*. This is the **single source of
  detailed history** and the curated feed `DESIGN.md` is regenerated from.
- **Do not edit `DESIGN.md` directly.** It is a curated snapshot, regenerated from
  `CHANGELOG.md` by a periodic human-run consolidation pass, see DESIGN.md section 18. Treat it as stable
  reference, not a scratchpad. (Only exception: a deliberate, human-directed
  restructuring — and then bump the Doc-rev line at the top of DESIGN.md.)
