18/6/26 10:31

1. Lets set a standard operating conditions for our further tests.  Therough GUI, mode1, 10kHz, 20us pulse, 10us delay, 256 decimation, coil in air, no targets, 20V bench supply.  From cold it takes 4min to settle.  expect a 50uV/s drop during this stage.  Once settled the plot will look like   @/home/mark/Projects/PIMD2/AI refs/SteadyState.jpg.  This plot shows 256 filter in first half and 1024 in latter. save this SoC information in changelog, making a note that it needs to be rolled into README later.  when testing we need to ensure that the unit is up to temp, so during this session, let me run the tools that launch the apps.

2. modify gui to default to these SoC parameters at start up. the std dev entry on the footer, that is the same as in the top right can go.

3. When decimation is set to either 256 or 1024 the StdDev in the gui always shows under 100uV, which appears to correlate to the graphic plot.  However the std dev uV reported from the mcu to the gui footer shows values for 1000 to 30000 uV.   I also note that in the footer, after the value it says '(x32)', im not sure what that means or if it is significant.  These std dev valuse should be a lot closer, investigate.

12:24 still working on box car average differences to mode 1 in GUI
15:33 appears to be fixed, consolidating

You are performing the §16 "human-run consolidation pass" described in README.md.
For THIS task only, you are authorised to edit README.md (this is the documented
consolidation process, not a normal agent edit — the §16 read-only rule is
suspended for this pass).

CHANGELOG.md is the source of truth for everything that has changed since the last
consolidation, including the now-resolved raw-boxcar / Mode-2 anomaly
(firmware v4.13 + v4.16–v4.18).

IMPORTANT — the CHANGELOG is NOT in chronological order. Do not replay entries.
First determine the NET CURRENT STATE per file (latest version of each), then
synthesise. The README is a consolidated snapshot, not a concatenation — keep the
existing "one-line summary, detail lives in source headers" philosophy.


Before editing, produce these for my review:
  1. Current version of each file (firmware, pimd_gui, pimd_scope, pimd_classviz,
     pimd_delaycal) as you read them from the CHANGELOG.
  2. An asset mapping table: each existing README/SoC asset path → its Reference/
     target. Flag any old reference with no clear match, and any file in Reference/
     not yet cited anywhere (e.g. DiscriminationTests.JPEG) — do NOT guess a match.
  3. Which README sections you'll change, and the net change for each (expect at
     least: header/Doc-rev line, §3 + the SoC block, §7/§14 boxcar resolution,
     §9 protocol, §10 profiles incl. profile 4, §15 inventory incl. pimd_classviz.py).
  4. Anything you plan to drop or significantly reword.

Preserve §16 and §17's policy text and structure; just bump the Doc-rev line and
fold new bench observations into §17. Do NOT delete content that is still accurate.

After I approve and you've updated README.md:
  - Append the entire current CHANGELOG.md to ARCHIVE.md (create it if absent),
    under a dated heading for this consolidation.
  - Reset CHANGELOG.md to a fresh empty skeleton (just an [unreleased] header).

Stage everything as commits I can review before they land; don't commit yourself.




**/rename calibration**
/clear



Read @README.md (esp. §3 envelope + SoC, §7 Mode-2 single-cell noise & thermal
drift, §9 serial protocol, §11 invariants, §15 inventory, §17.2 warm-up) and the
top of @CHANGELOG.md — the P2006-113356 noise dataset and the recent
src/pimd_delaycal.py entries (v1.02–v1.06). Follow @CLAUDE.md conduct.

SCOPE
- PC-side only. Modify ONLY src/pimd_delaycal.py. No firmware/MCU changes, and no
  PC-driven scan logic pushed into firmware (§11 invariant).
- REUSE what's already in this file — the calibration sweep, the THERMAL Mode-2
  streamer (D + Q5 + G), the Export-Profile JSON builder, the W/A-record parsing
  and the live std-dev table. Don't reimplement them.
- Don't break or change existing behaviour. Minimal, reversible changes.
- Per CLAUDE.md: bump this file's header version + add a CHANGELOG.md entry above
  the marker. Do NOT edit README.md.

GOAL
A new "Auto" button that, per profile cell, finds a sample-delay close to its
calibrated target-voltage crossing AND with acceptable std dev, by iteratively
nudging cells sitting in a noisy delay zone (ringing / PWM quirk — cause out of
scope) off that zone. Result becomes the new profile.

PROPOSED PROCEDURE (every threshold an adjustable UI field; defaults shown):
1. Run the existing calibration sweep → seed the per-cell delay table/profile.
2. THERMAL soak the current profile for [20 s].
3. Per cell, compute std dev over the last [100] samples; flag "bad" if
   std dev > [0.5 mV / 500 µV] (setable). (Match the unit the existing std-dev table uses.)
4. Nudge each bad cell by [−80 ns], snapped to the 8 ns PWM grid; cap total
   deviation from the calibrated delay at [±960 ns (setable)].
5. Re-soak THERMAL with the updated delays.
6. Repeat 3–5 until all cells pass OR [max 5 (setable)] iterations.
7. Cells still failing → keep their best-std delay seen and flag them. Export via
   the existing Export-Profile path.

BEFORE CODING: give me a plan and flag concerns first — don't edit yet. Address:
- Measurement method & units. Which std dev defines "bad"? The P2006 bad zones
  were found on held single-delay measurements, but THERMAL is Mode-2 multi-cell
  streaming. Per README §7 a degenerate single-cell Mode-2 run reads 24–30 mV std
  (vs ~310 µV for a proper sweep) — ensure the routine measures real noise, not
  that artifact, or it flags everything and never converges.
- Thermal drift. §3/§17.2: ~−50 µV/s and a 4-min warm-up; a 20 s soak is far
  shorter, and the P2006 note (3) shows drift inflating σ to 1835 µV with no real
  noise. Decide: pre-warm, detrend the window, or a drift-robust metric — don't
  mis-flag drift as ringing.
- Accuracy cost of nudging. Moving the delay moves the sample point off its
  calibrated target voltage (~100–130 mV of V-mean per 80 ns in the P2006 table).
  Report ΔV per nudged cell, respect the deviation cap, flag cells where escaping
  noise costs too much voltage.
- Zone width. Bad zones are ~160 ns wide (not confirmed), so one 80 ns step may not clear them —
  hence iteration, direction toward the nearest clean delay, the cap and fallback.
- Non-blocking. Drive it as a QTimer / W-record-callback state machine like the
  existing THERMAL countdown — no synchronous while-loop or sleep. This file/GUI
  have an event-loop-freeze history; keep the existing UI-update rate limiting.

After I confirm the plan, implement it.

21 July

consolidating


You are writing ONE single-page cheat sheet for the PIMD project, for the module: pimd_mcu.

GROUND TRUTH
- Read @mcu/pimd_mcu.py as the authority for behaviour, modes, and serial commands.
- Use README.md (§9 protocol, §15 inventory) only for framing/context.
- If the source and README disagree, follow the source and add a one-line "⚠ README §X says
  otherwise" note. Do NOT invent or smooth over gaps — if something isn't in the source, say
  "not specified in source" rather than guessing.

SCOPE
- Create exactly one new file: docs/cheatsheets/<<MODULE>>.md
- Do NOT edit README.md, CLAUDE.md, CHANGELOG.md, or any source file. Do NOT bump any version
  or Doc-rev line. Create nothing else.

LENGTH
- One page: target ~400–500 words, must fit one side of A4 when rendered. Be dense and
  scannable — prefer a compact command/record TABLE over prose for the protocol section.

TEMPLATE (use these exact headings, in this order):
1. What it is — 1–2 sentences (the role of this module in the system).
2. What it does — 3–5 bullets of core function.
3. Modes of operation — the modes/states this module runs in; if only one, say so.
4. Serial protocol — a table. For the firmware: commands ACCEPTED and records EMITTED.
   For an app: commands it SENDS to the MCU and records it CONSUMES. Columns:
   Direction | Token/format | Meaning. Keep to what THIS module actually uses.
5. Key parameters / defaults — anything an operator sets (freq, pulse, delay, downsample,
   profile, etc.) with default/SoC values where the source defines them.
6. Gotchas / pertinent notes — non-obvious behaviour, ordering requirements, known limits.

PROCESS
- First, list the serial tokens you found by reading the source (just the list).
- Then write the file.

Current versions per README: fw v4.23 · gui v4.13 · classviz v1.14 · delaycal v1.19.
Audience: maker, future me & operator.