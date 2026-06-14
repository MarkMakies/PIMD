# CC_PROMPT.md — Claude Code run prompt for PIMD

Paste the block below into Claude Code from the repo root (with `CLAUDE.md`, `README.md`,
and `REVIEW.md` present). This detector already works, so the run is incremental and
bench-testable: firmware safety fixes, the raw-acquisition primitive, fixed scan
profiles built on that primitive, and one analysis question — not a blanket rewrite.
Progress one step at a time; each firmware step is independently testable before the
next.

---

```
Read CLAUDE.md and README.md first, then REVIEW.md. This is a working, field-tested
pulse induction metal detector. Do NOT redesign or "modernise" anything that works —
in particular never move the TX pulse and sample trigger off the same PWM slice, and
never change the serial wire format or the uV scaling constant. Treat the measured
operating envelope in CLAUDE.md as ground truth; if your reasoning implies the device
can't work as built, you are missing context — flag it, don't assert it.

TASK 0 - Baseline and test current systems that have been neglected and left in storage undocumentated.
work with user to verify current functionality.   

TASK 1 — Firmware safety fixes in pimd_mcu_302.py (make the edits):
  a) The DRL interrupt handler (filtered_data_callback) does a 4-byte SPI read and
     calls print() inside the ISR. Refactor so the ISR only sets a flag / captures
     minimal state, and the SPI read + any logging happen in the main loop (or via
     micropython.schedule()). Remove the progress-dot prints entirely. Preserve the
     existing group-delay / settling behaviour.
  b) drive_duty and sample_duty are written to duty_u16() with no range check and can
     wrap past 65535 at high pulse-rate + wide-pulse combinations. Add validation:
     reject or clamp commands where the computed duties are out of 0..65535 or where
     sample_duty <= drive_duty, and report the rejection back over serial in the
     existing '*'/text style. Do not change behaviour inside the normal envelope.
  Keep both changes minimal and reversible. Show a diff and explain each change.

TASK 2 — Raw-path acquisition PRIMITIVE (the building block, make the edits):
  The raw no-latency output (SDOB, 14-bit) is set up (adc_raw_spi, GPIO0/2/15) but never
  read. Per CLAUDE.md and README §13, the raw path — NOT the 32-bit filtered path — is
  the chosen route for decay-curve / multi-delay capture and moving-platform tracking
  (the filtered path has ~0.5 s settling and ~2.4 Hz bandwidth). Implement ONLY the
  single-point primitive here; the multi-point scan is composed from it in Task 3.
  a) Read SDOB on SPI0 (raw 14-bit differential; note the 22-bit composite = 14-bit diff
     + 8-bit common-mode per the LTC2508 datasheet — extract the differential field).
  b) Boxcar-average x raw samples at the current (held) sample_delay to recover
     resolution (noise ∝ 1/√x; raw floor ≈ 1400 µV, so x=32 → ~250 µV in 3.2 ms at
     10 kHz). Make x a settable parameter. Expose this as ONE command:
     "acquire one averaged raw value at the current pulse_width/delay" → returns one
     self-describing line. No sweeps, no loops over delays/pulse widths here.
  c) Validate against the period budget (Appendix A): reject a pulse_width/delay/freq
     combination that overflows the period, and report the rejection over serial.
  Keep the existing filtered path intact for held-baseline use. Do NOT move the TX/sample
  PWM off the same slice. Keep the '*' manual interface and the legacy '*' telemetry line
  working untouched; the averaged-raw acquisition is a NEW record type. Show a diff and
  explain. This primitive must be bench-testable on its own (I confirm noise drops ~1/√x)
  before Task 3.

TASK 3 — Fixed scan PROFILES (compose the primitive locally; cut serial chattiness):
  GOAL: replace chatty per-point PC orchestration with compiled-in scan PROFILES. A
  profile is a self-contained recipe the MCU runs LOCALLY, returning the whole scan as
  one streamed result — so a y×z decay matrix costs ONE command + ONE reply instead of
  dozens of round-trips. This is the main speed win and it is transport-independent (helps
  even more over a future LoRa/UART link). NOTE: profiles are a control-plane change only
  and do NOT affect the noise floor (that is electrical — power/ground/flash, README §8).
  DO NOT write to flash (flash writes spike the noise floor ~10×); profiles are
  compiled-in constants, RAM only.

  PROFILE MODEL:
  - Profiles are a FIXED table compiled into the firmware, selected by index. Changing
    one means reflashing — accepted; keeps it dead simple and deterministic.
  - Each profile fully defines a scan: frequency, list of pulse widths (z), per-pulse-
    width sample delays (y, log-spaced via e^(0.3n)−1), and averaging count(s) (x; allow
    per-point/adaptive x — light on high-SNR points, heavy on near-floor points).
  - Define 2–3 starting profiles from Appendix A: e.g. (i) a FAST TRACKING profile =
    single pulse_width/delay for localisation; (ii) a CLASSIFICATION profile = x≈32,
    y≈8 over ~5–40 µs, z=3 at 8/20/40 µs. Each validates against the period budget.
  - The only new MCU logic is a fixed loop walking the compiled profile table (built on
    the Task 2 primitive). No PC-defined logic, no scheduler, no flash.

  COMMANDS (additive; the '*'/'S'/'E' manual interface STAYS for debug/tuning):
  - 'P<n>' : select + run profile n; MCU executes the full local scan and streams the
             result as a new self-describing record type (NOT the legacy '*' line).
  - 'L'    : list profiles (index + short description + grid shape) so the PC/app learns
             what's compiled in without hardcoding it.
  - 'V'/'?': identify + report (fw rev, board id, active profile, current config).

  OUTPUT FORMAT:
  - The profile result is one record carrying the full y×z matrix PLUS the profile index
    and grid metadata, so each record is self-describing and the ML side knows the exact
    geometry without guessing. Line-based and parseable.
  - Because geometry is FIXED per profile, the ML feature-vector shape is constant per
    profile. State in a comment: classifiers are trained PER PROFILE, and 'L'/the record
    metadata is the contract between firmware and ML.

  TRANSPORT: stays USB-serial for now, but keep the command parser and output writer
  transport-agnostic (a single read-line / write-line seam) so swapping to UART/LoRa
  later is a one-place change, not a rewrite.

  ROLLOUT (smallest first; I bench-test each before the next; give a 2-line serial-
  terminal test recipe per step; do NOT chain steps in one turn):
  1. 'V'/'?' identify + report (pure observability, no behaviour change).
  2. 'L' + the compiled profile table (data only, not yet runnable) — I verify the table.
  3. 'P<n>' running a SINGLE-point profile (proves run+stream end to end).
  4. 'P<n>' running a full y×z profile streaming the matrix (the real feature).
  Preserve the '*' manual path working at every step. Show diffs; keep them minimal.

TASK 4 — Analysis only, write to NOISE_NOTES.md (no code changes): from the schematic
  netlist (PIMD601.kicad_sch) and README §8, reason about why RP2040 USB power measures
  ~50% quieter than the onboard LM7805-from-supply path. Enumerate concrete, testable
  hypotheses (ground-return paths, 7805 output noise/PSRR, shared-rail coupling into the
  +2V5/ADC reference chain, the +3V3 onboard LDO source, decoupling gaps near U6/U3/U5).
  Rank them and propose specific bench measurements to confirm/refute each. State every
  point you cannot verify from text and exactly which file (PCB layout, Gerbers, scope
  capture) would resolve it.

RULES:
  - Cite file:line for every firmware claim.
  - Do not edit the schematic, the PC GUI, or any read-only file.
  - Same-slice TX/sample PWM is sacred; the legacy '*' telemetry/command format stays
    valid; no flash writes; no scan scheduler in firmware beyond the fixed profile loop.
  - Write TASK 4 output to NOISE_NOTES.md; after each firmware step leave a short chat
    summary: the diff applied and the 2-line serial-terminal test recipe.
```

---

## Appendix A — Scan-parameter spec for Task 2 (10 kHz, slow movement)

Definitions: **x** = raw samples averaged per point; **y** = number of sample delays
(decay-curve points); **z** = number of pulse widths.

**Period budget (hard constraint).** At 10 kHz the period is 100 µs and must hold
`pulse_width + max_sample_delay + flyback/recovery`. So at this rate:
delays span ~5–40 µs and pulse widths cap at ~40–50 µs. Wide ferrous-favouring pulses
(50–100 µs) do NOT fit at 10 kHz — they need a separate low-rate pass (see below).

**Thermal duty (the real binding constraint at slow speed).** Heat drives the
≈ −89 µV/s drift. A 30 µs pulse at 10 kHz is 30% duty — more average heating than the
5 kHz/40 µs operating point (20%). Keep z small and avoid dwelling on the widest pulse.

**Averaging vs noise (raw floor ≈ 1400 µV, noise = 1400/√x):**
| x | noise | time/point @10kHz |
|---|-------|-------------------|
| 16 | ~350 µV | 1.6 ms |
| 32 | ~250 µV | 3.2 ms |
| 64 | ~175 µV | 6.4 ms |

**Recommended starting grid:**
- **x = 32** (~250 µV, near the filtered path's real-world floor; drift within a point
  ~0.3 µV, negligible). Tune 16–64.
- **y = 8** delays, log-spaced ~5–40 µs via the `e^(0.3n) − 1` law. 8 captures the time
  constant + any sign-flip without redundant correlated points; go 10–12 only if ML
  wants finer shape.
- **z = 3** pulse widths: **8 / 20 / 40 µs**. Defines the pulse-width response slope
  (the ferrous/non-ferrous discriminant). A 4th adds heat/time for marginal gain.

**Frame time:** x·y·z·100 µs = 32·8·3 = **~77 ms** → ~13 frames/s. At 0.2 m/s over a
~0.3 m coil zone a target dwells ~1.5 s → ~20 frames/target (≈8 even at 0.5 m/s). Time
is comfortable — spend it on signal quality (x) and low z/heat, not speed.

**Two refinements (higher value than tweaking the numbers):**
- **Adaptive x:** average lightly (x≈8) on high-SNR early-delay / wide-pulse points,
  hard (x≈64) on near-floor late-delay points. Same curve quality, less time and heat.
- **Two cadences:** a cheap single (pulse_width, delay) point every cycle for fast
  position tracking/localisation, and the full y×z matrix every few hundred ms for
  classification. Decouples "where is it" (needs speed) from "what is it" (needs the
  matrix); matches the diary's raw-track-then-characterise instinct.

**Wide-pulse ferrous option:** if wide-pulse ferrous discrimination proves important,
add a separate burst pass at ~2.5–3 kHz (≈330–400 µs period) to allow 50–100 µs pulses,
interleaved occasionally (not continuous) to limit heating. Impossible inside a 10 kHz
period.

**What feeds where:** the **x averaging is the filter** (firmware boxcar replacing the
on-chip decimation; cleanup/ground-subtraction sits on top). The **y×z matrix per frame
is the ML feature source** → reduce to features: per-pulse-width decay time constant,
early/late ratio, polarity, sign-flip presence, pulse-width response slope. z-axis =
ferrous/non-ferrous discriminant; y-axis = decay-shape / time-constant.

TASK 0 - do first.  cleanup file names and directory structure to follow best practice