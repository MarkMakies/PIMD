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

SCOPE DECISIONS (already made — follow exactly):
- Dynamic profiles stay CHANGELOG-ONLY. Do NOT document the `D` command or
  DYNAMIC_PROFILE_INDEX (=5) anywhere in the README — not in §9, not in §10, and
  don't describe the Profile Builder's dynamic-send as a README feature.
- Profile 4 (CLASSIFY_EP) IS a fixed compiled-in profile — promote it into §10.
- All reference assets now live in a single `Reference/` folder. Current contents:
  DiscriminationTests.JPEG, GUI-TargetExample.jpg, "Schematic Baseline.jpg",
  GUI-SteadyState.jpg, LTC2508-32.pdf, ScopeBaseline.jpeg
  Repoint every asset reference in the README (old `pics/`, root-level, and
  `AI refs/` paths) to its counterpart in `Reference/`. Note "Schematic Baseline.jpg"
  contains a space — quote/escape it correctly in any markdown path. This also
  retires the old `pics/Scematic_Baseline.jpg` typo.

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