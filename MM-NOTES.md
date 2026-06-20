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

19/6/26 13:28 anomolies whilst stepping pules up or down.  due to rounding / 8ns resolution edge
gui fixed 
SYS_CLK_HZ = 125_000_000
CLEAN_FREQS_HZ = frozenset(f for f in range(1000, 65001) if SYS_CLK_HZ % f == 0)
# {5000, 6250, 8000, 10000, 12500, 15625, 20000, 25000, 31250, 40000, 50000, 62500} in 5â65 kHz
SAMPLE_PULSE_CORRECTION_NS = 904  # = 113 Ã 8 ns exactly


splitting and cleaning readme and claude.md4


gui changes: 
1. box car average and raw avg on buttons should be on be default
2. for three sliders and +/- buttons, i want to ensure that these can only land on indentified 'good' frequencies and delays exact multiples of 8ns.


read @README.md for context.  a recent update to gui version 4.08 was intended to fix problems with comms overruns and unresponsiveness of app after running for a while.  analyse what went wrong.

src/pimd_gui.py — v4.08 changes, specifically (e) and (f).  see @CHANGELOG.md

The Proposed Plan was

Fix 1 â Drain buffer in a loop (critical, ~2 lines)
Change read_from_serial() to use while self.serial.canReadLine(): exactly as pimd_scope.py does. This eliminates the event storm: one event loop turn drains all available lines, leaving the serial buffer empty and no pending re-firings.

Fix 2 â Add closeEvent for clean shutdown (~6 lines)
Override closeEvent to: send 'E', call raw_poll_timer.stop(), call serial.waitForBytesWritten(200), close serial port, close log file. Remove the fragile aboutToQuit lambda. Matching pimd_scope.py pattern exactly.

Fix 3 â Close file before reopening in setup_file_logging() (~2 lines)
Before self.file = open(...), check if self.file: self.file.close(). The call from my_init() at startup was unnecessary anyway â only start_stop() needs it â but the guard is the safe fix either wa


**Calibration Session**

read @README.md and @src/pimd_delaycal.py.  add features to the app for continued debugging and calibration  

1. profile export button.  after a run is complete, a profile export button  will then take the freq/pulse/and new delays, create a profile in the same form as used in @src/pimd_classviz.py, and autosaves it  with date time stamp in data/profiles directory.

2. A new button called 'THERMAL' with a number box for seconds, defaulting at 240.  This function will then run this profile in the same exact fashion as pimd_classvis for the set amount of seconds, counting down.  there also needs to be a stop button.

3. Whilst this is occuring display two tables, very similar to the existing value one.  place these below.  first table is latest mean in mV, no decimal.  second table  the std dev over x (settable) values.

4. make left column on containing text and boxes a little bigger

My operating principle is: do a quick run, save profile, reuse that profile and warm up electronics using the profile that will be used,  watch variation in values and std dev, once warm and stable take another measurement and save that as the final profile.

