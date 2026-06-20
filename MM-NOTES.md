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
{5000, 6250, 8000, 10000, 12500, 15625, 20000, 25000, 31250, 40000, 50000, 62500} in 5â65 kHz
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


**/rename calibration**
/clear

read @README.md and @src/pimd_delaycal.py.  add features to the app for continued debugging and calibration  

1. profile export button.  after a run is complete, a profile export button  will then take the freq/pulse/and new delays, create a profile in the same form as used in @src/pimd_classviz.py, and autosaves it  with date time stamp in data/profiles directory.

2. A new button called 'THERMAL' with a number box for seconds, defaulting at 240.  This function will then run this profile in the same exact fashion as pimd_classvis for the set amount of seconds, counting down.  there also needs to be a stop button.

3. Whilst this is occuring display two tables, very similar to the existing value one.  place these below.  first table is latest mean in mV, no decimal.  second table  the std dev over x (settable) values.

4. make left column on containing text and boxes a little bigger

My operating principle is: do a quick run, save profile, reuse that profile and warm up electronics using the profile that will be used,  watch variation in values and std dev, once warm and stable take another measurement and save that as the final profile.

delay calibratioin now more featured, with warm up function.  interestingly very noisy on 4.0 and 4.5V samples.  Need to investigate further, maybe fine comb

lets continue debugging noise at 4/4.5V.  to that end ive used the gui to observe noise at these voltages.  Use gui, start at 20/20/8.2 (about 3.4V) the decrement delay in 80ns increments, wait a bit for settle and then increment again.  I did this about every 10s.  I certainly saw noise at about 4 and 4.5V settings.  but i think i may have seen some clean ones as well in between.  this correlates with the results seen in delaycal, so it ios not a problem in delaycal.  Now analyse the data.  create a table of delay setting vs noise.  speculate on cause and/or solutions.  

confirmed, eg 20/20 7.248uS 4.7V s=60uV, 7.328 4.6V s=600uV  .  theere are very specific problem combinations


**commit**: stable but need more decimal places out of gui

Â I think you have not seen the correct data.  all the return parameters from the mcu are to 1 decimal place, so you cant see the actual exact timing setting in that data
  set.
  we need to fix this first before you can anlyse data.  i think that the mcu returning frequency in Hz and pulse/delay in ns without decimal points would be best so we
  are sure there are no rounding errors.  As well as the mcu, i believe you will ahve to modify the other apps as well.  step 1, last start with mcu and gui.  also rename
  in title to PIMD GUI with version and my name - all apps should share a similar title format.  After we have validated gui and mcu, we will work on the other apps.


Add in CHANGELOG real observations  

read @README.md and the beginning of @CHANGLOG.md
we have identified increase noise on some very particular pulse/delay combinations.  cause may be due to ringing or a PWM quirk, at the moment the cause is not important.
modify @src/pimd_delaycal.py.  
add functionality to improve delay value selection as explained below.  
dont break or modify existing functionality
propose best way/s to do this.  i think the procedure would be:

new button - auto which then ...

1. run first sweep
2. run thermal for 20s (adjustable).
3. analyse results, flag bad those values whos std dev > 0.5 (adjustable) over 100 samples.
4. next adjust all bad values, say by -80ns (adjustable)
5. repeat thermal with new values
6. repeat until all std dev's meet requirements
7. this then becomes the new profile.




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


another problem when running slow rates.  6250Hz 50us .  once i quit the gui the data continues to stream for another 20-30sec.  i saw this when i changed 

another problem when running slow rates say  6250Hz 50us
once i quit the gui the data continues to stream for another 20-30sec, dependent on how long it has been running
i can clearly see it continue in that App in the footer or another App if i connect
additionaly a new command, when running at this speed, like delay change,  sometimes takes up to 2 minutes until i can see an in return. ive tried running in the repl with *6250,50000,8760,256 and it starts and stops fine.
maybe something to do with A32, component.

frames-base looking good  
D32;50000,5.0,5.660,6.080,6.470,6.770,7.070,7.400,7.790,8.300,9.070;40000,10.0,6.480,6.820,7.220,7.590,7.900,8.240,8.640,9.160,9.950;20000,25.0,7.470,7.920,8.320,8.620,8.940,9.360,9.700,10.310,11.150;6250,50.0,8.620,8.910,9.330,9.630,9.950,10.300,10.730,11.280,12.220;2500,75.0,9.200,9.420,9.910,10.220,10.540,10.900,11.340,11.900,12.780


 in pimd_delaycal remind me how we get the samples at 'RUN' mode?  i can see incoming packets prefixed with R, and I cantr see that format in the readme, maybe in changelog?


That's the full picture. During the calibration sweep (RUN mode) in pimd_delaycal, no Mode 1 streaming is used at all. The sequence at each delay step is:

1. *<freq_hz>,<pulse_ns>,<delay_ns>,256 â configure PWM (no streaming started)
2. A<n> â single-shot raw boxcar average, where n comes from the "Avg" spinbox in the config panel

The firmware responds with one R record per A<n> call. That R record is what _on_r_record() parses.

The R record format is documented in the firmware (pimd_mcu.py) â it's the same format pimd_gui.py also consumes:

R<t>,<mean_uV>,<std_uV>,<n>,<freq_hz>,<pulse_ns>,<delay_ns>[,<min_uV>,

- t â firmware timestamp (ms)
- mean_uV â boxcar mean (ÂµV) â the calibration sweep uses this for threshold crossing
- std_uV â std dev of the n samples (ÂµV)
- n â actual sample count used
- freq_hz, pulse_ns, delay_ns â echo of current settings
- min_uV, max_uV â min/max spread (firmware v4.15+, parsed defensively in pimd_gui)                                                                                       
pimd_delaycal only reads parts[1] (mean) and parts[2] (std) from the record at line 671â672, ignoring the rest.                                                           
So the delaycal sweep is purely request-response: send *config + A<n>, get one R, check against thresholds, advance delay, repeat. No timer-driven polling â it naturally has no queue buildup.


A<n> - there doesnt seem to be a place to change this for 'RUN' mode .  Is that correct?  Dont code.

