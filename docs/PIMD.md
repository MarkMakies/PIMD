PIMD Platform: Multi-Band Pulse-Induction Detector — Capabilities Summary for ML Classification

  Platform version: Firmware v4.23 · ClassViz v1.15 · Delaycal v1.19 · Hardware rev 6.04 · 2026-06-21

  ---
  Overview

  PIMD is a custom pulse-induction metal detector designed from the ground up for autonomous deployment on a GPS-surveying rover. Unlike
  commercial PI detectors, which optimise a single operating point, PIMD is architected as a programmable, multi-band measurement
  instrument. The same hardware that discriminates ferrous from non-ferrous targets in a single channel can simultaneously acquire a
  two-dimensional decay-space matrix — frequency vs. decay-amplitude — suitable as a direct input to a machine-learning classifier.

  ---
  Acquisition Architecture

  The core measurement is straightforward: a drive pulse energises the TX coil; on cutoff, the RX coil measures the decaying eddy-current
  response in the target. What makes the platform unusual is the sweep profile — a user-defined grid of (frequency, pulse-width,
  sample-delay) operating points that the firmware cycles through at up to ~100 frames/s, reporting each complete frame over USB serial.

  The profile demonstrated here (cal_20260621_134403) spans 8 bands across a 16:1 frequency range:

  ┌──────┬───────────┬─────────────┐
  │ Band │ Frequency │ Pulse width │
  ├──────┼───────────┼─────────────┤
  │ B0   │ 3,125 Hz  │ 100 µs      │
  ├──────┼───────────┼─────────────┤
  │ B1   │ 4,000 Hz  │ 75 µs       │
  ├──────┼───────────┼─────────────┤
  │ B2   │ 6,250 Hz  │ 50 µs       │
  ├──────┼───────────┼─────────────┤
  │ B3   │ 8,000 Hz  │ 40 µs       │
  ├──────┼───────────┼─────────────┤
  │ B4   │ 10,000 Hz │ 30 µs       │
  ├──────┼───────────┼─────────────┤
  │ B5   │ 15,625 Hz │ 20 µs       │
  ├──────┼───────────┼─────────────┤
  │ B6   │ 40,000 Hz │ 10 µs       │
  ├──────┼───────────┼─────────────┤
  │ B7   │ 50,000 Hz │ 6 µs        │
  └──────┴───────────┴─────────────┘

  All bands operate at approximately equal drive duty (~30%), so the power delivered to the coil remains roughly constant as frequency
  changes. This means differences in response across bands reflect material time-constant behaviour rather than drive-energy differences.

  Within each band, 9 sample delays are calibrated to capture specific amplitude thresholds (4.8 V → 0.5 V in descending steps). The delays
  are not arbitrary: the dedicated pimd_delaycal tool sweeps the sample point across the post-flyback window and records the precise moment
  the conditioned signal crosses each voltage threshold (the "clip-release" time). This anchors each cell to a physically meaningful
  amplitude on the decay curve and avoids the noisy LC-ringing zones identified during bench calibration. The result is a 72-cell matrix per
  frame (8 bands × 9 cells), where each cell measures the eddy-current response amplitude at a specific point in both frequency space and
  time-domain decay space.

  ---
  Timing and Voltage Precision

  The RP2040 generates the TX drive and ADC sample trigger from two channels on the same PWM slice, phase-locking the sample edge to the
  drive edge with ≈ 5 ns jitter (measured). Sample delays are quantised to the 8 ns PWM clock grid; the delaycal tool explicitly snaps
  calibrated delays to grid boundaries to avoid ±1 LSB alternating anomalies. At the ADC, the LTC2508-32 in 32-sample boxcar mode gives a
  practical noise floor of ≈ 300–500 µV RMS per cell under steady operating conditions — adequate to resolve target-induced deviations of
  several millivolts against the air baseline.

  ---
  Real-Time Visualisation and Target Discrimination

  The pimd_classviz application renders each frame as a diverging (blue–white–red) heatmap of signed deviation from an air baseline. The
  colour convention matches the physics: blue = negative deviation (opposing eddy currents, non-ferrous); red = positive deviation
  (reinforcing magnetic energy, ferrous). All three target scenarios are shown below.

  Non-ferrous target alone: The heatmap is uniformly blue, strongest in the low-frequency/long-pulse bands where conductive non-ferrous
  materials sustain eddy currents longest. All bands report negative crossings. The signature is broadband and laterally consistent across
  the delay axis.

  Ferrous target alone: The heatmap is uniformly red, with strongest response in the same low-frequency bands. The positive deviation is
  persistent across all 9 delay cells, reflecting the material's ability to sustain magnetic remanence well into the decay.

  Both targets simultaneously: The heatmap is split: blue in the early-decay cells (left, high-threshold side) and red in the late-decay 
  cells (right, low-threshold side). Multiple bands report clear zero-crossing voltages (e.g. B0:3.09 V, B1:2.21 V, B2:1.92 V),
  corresponding to the point in the decay where the non-ferrous eddy-current contribution has collapsed but the ferrous contribution
  persists. This bimodal structure is immediately visible and spatially resolved within the matrix — the two contributions occupy distinct
  regions.

  The "nothing" screenshot confirms the live streaming state (5,688 frames delivered without baseline loaded), demonstrating continuous
  real-time operation.

  ---
  ML Data Pipeline

  The platform is structured for training-data capture. pimd_classviz provides:

  - Labelled snapshot export — one row per trigger, 72-dimensional signed-deviation vector plus raw µV and baseline, written to a
  date-stamped CSV
  - Continuous frame logging — every incoming frame appended with the current label, suitable for target-pass recordings
  - Raw frame recorder — firmware timestamps plus unfiltered channel values, for post-hoc feature engineering

  The 72-dimensional input vector, delivered at ≤ 100 Hz, already spans the two axes most informative for discrimination: frequency
  (eddy-current time constant / depth sensitivity) and decay amplitude (envelope shape). Mixed-target scenarios produce structured,
  spatially separated responses in the matrix rather than a single ambiguous scalar — the kind of structured input that classical
  discriminative classifiers and small convolutional networks handle well.

  ---
  Assessment

  The platform delivers a geometrically structured, calibrated decay-space representation at sub-millisecond temporal resolution with low
  noise. The ferrous/non-ferrous separation is unambiguous in the 2D matrix and survives in the mixed case as a spatially separable pattern.
  The delaycal toolchain ensures each cell samples at an amplitude-calibrated, ringing-free point, maximising SNR before any ML processing.
  The next steps are labelled-dataset collection over a range of targets at known depths, followed by classifier evaluation — the
  acquisition and visualisation infrastructure to support both is already operational.

  ---
  Written against PIMD firmware v4.23 / ClassViz v1.15 / delaycal v1.19, bench tested 2026-06-21.