# PIMD — Pulse Induction Metal Detector

*A from-scratch, multi-band pulse-induction metal detector built for autonomous, position-tagged ground survey.*

![Mixed ferrous + non-ferrous target — the 8×9 decay-space matrix splits into non-ferrous (blue, early decay) and ferrous (red, late decay)](References/profile8b-spanner-copper.jpg)

> Above: a single live frame with a steel spanner **and** a copper pipe under the coil. The two
> materials separate *spatially* inside the decay-space matrix — non-ferrous (blue) collapses early,
> ferrous (red) persists late. Getting that separation out of a pulse-induction detector is the whole point.

**Up to date Build diary:** <https://makies.com.au/pulse-induction-metal-detector/>

---

## What it is

A pulse-induction (PI) metal detector designed and built from scratch since November 2023 by a maker
with no prior analogue-electronics background. It is **not** a clone — several design choices are
deliberately unconventional.

In the language of the field, it's a **low-cost, monostatic time-domain electromagnetic (TEM)
spectrometer doing cued interrogation** — though it started life as nothing more ambitious than
"let's build a metal detector with no experience." It is one payload of a larger system: the coil is
towed on a trailer behind **Roverling**, an autonomous RTK-GPS ground robot, so every detection event
can be tagged with centimetre-level position and streamed back over LoRa. It therefore has to be
*quiet, stable and remotely controllable*, not merely sensitive.

What makes it unusual among PI detectors is that it doesn't optimise a single operating point.
It cycles through a user-defined grid of operating points and reports, for every frame, a
two-dimensional **decay-space matrix** — frequency/pulse-width on one axis, decay-amplitude (time) on
the other — that is designed from the ground up as an input to a classifier.

## How it works (in brief)

A high-current pulse energises the TX coil; on hard cutoff the collapsing field produces a flyback
and then a decaying eddy-current response. A nearby target perturbs that decay. The conditioned RX
signal is sampled at precise, calibrated delays.

- **Mode 1** — a single filtered (32-bit) sample at one held delay: the low-noise telemetry path, used for baselines and field tests.
- **Mode 2** — an interleaved sweep across a profile of *(frequency, pulse-width, sample-delay)* points, reported as one frame per sweep. The current locked profile (`cal_63_air_v1`) spans **7 pulse widths × 9 sample delays = a 63-cell matrix**. Pulse widths are spaced geometrically (9 → 100 µs, ×1.5 per step) so each band interrogates a distinct slice of target time-constant space; repetition rates are chosen to hold duty near 30%. (An eighth 6 µs band was dropped: it carried no target information not already present in the other bands and was notoriously noisy.)
- Sample delays are **amplitude-calibrated** — anchored to a top-dense ladder of voltages (4.9 → 0.5 V) on the region of the decay where this coil carries the most discrimination information — and snapped to the 8 ns PWM grid, deliberately avoiding the LC-ringing dead zones and the measured ~4.45–4.65 V noise keep-out zone.
- **Polarity convention:** ferrous targets read **positive** (stored magnetic energy reinforces the decay); non-ferrous read **negative** (opposing eddy currents weaken it). A third class turns out to be common in practice: **crossover targets** (cast iron, some stainless, real jewelry with steel fittings) read negative at short pulses and positive at long ones — the pulse-width axis resolves what a single operating point would misclassify.

## Highlights

- 63-cell decay-space matrix recovering **multi-time-constant discrimination from a PI platform** — something most commercial PI detectors don't attempt.
- **Validated on a 17-target labelled corpus** (July 2026): signature *shape* is invariant with target distance (5–15 cm, 30× amplitude range) and repeats across sessions and recalibrations to within a few percent — the property the classification layer is built on.
- Targets fall into **three shape families** — ferrous, non-ferrous, and crossover — and overlapping targets combine **linearly** (a spanner + copper pipe frame decomposes back into its parts at 0.99 correlation), so unmixing is on the table, not just classification.
- Phase-locked TX/sample timing on one RP2040 PWM slice — **~5 ns sample-trigger jitter (measured)**.
- LTC2508-32 dual-output front end (filtered 32-bit + raw 14-bit no-latency).
- A dedicated delay-calibration tool that measures the clip-release point per band and exports calibrated profiles.
- Three PyQt6 desktop tools: live Mode 1 GUI, the Mode 2 heatmap + ML-data bridge (`ClassViz`, including a self-describing session recorder for training data), and the delay calibrator.
- Built for autonomous use: RTK-GPS position tagging, LoRa telemetry, single dedicated low-noise supply.

## Repository layout

```
README.md                  This file — start here
DESIGN.md                  Full engineering reference (hardware, firmware, protocol, test log)
CHANGELOG.md               Project change log
CLAUDE.md                  Contributor / agent conventions (version bumps, changelog discipline)

docs/                      Per-tool cheat sheets + platform summary
  pimd_gui.md  pimd_classviz.md  pimd_delaycal.md  pimd_mcu.md  PIMD.md

mcu/                       MicroPython firmware for the RP2040-Zero
  pimd_mcu.py  main.py

src/                       PC-side tools (PyQt6)
  pimd_gui.py              Mode 1 filtered-telemetry GUI
  pimd_classviz.py         Mode 2 decay-space heatmap + ML logger
  pimd_delaycal.py         Delay-calibration sweep tool
  pimd111.ui  pimd111_ui.py
  requirements.txt
  data/                    Settings, captured CSVs and calibrated profiles (runtime-generated)

Electronics/PIMD604/       KiCad project — schematic rev 6.04 (as-built)

References/                Schematic export, scope captures, sample heatmaps
```

## Quick start

No build step for either the PC tools or the firmware.

### PC tools

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
cd src
python pimd_gui.py        # Mode 1 GUI (filtered telemetry)
python pimd_classviz.py   # Mode 2 decay-space visualiser + ML bridge
python pimd_delaycal.py   # delay-calibration sweep
```

The tools connect to the board on `/dev/ttyACMx` at 115200 baud.

### Firmware

```bash
# No build step — copy onto the board, then power-cycle it.
.venv/bin/mpremote connect /dev/ttyACM0 fs cp mcu/pimd_mcu.py :pimd_mcu.py + fs cp mcu/main.py :main.py
# (mpremote reset does not re-enumerate USB reliably — power-cycle the board.)
.venv/bin/mpremote connect /dev/ttyACM0 repl
```

### Bench-test over a serial terminal (115200)

```
V                              identify / firmware version
L                              list profiles
Q5   then  G                   Mode 2: stream the loaded operating profile (W5 records);  E to stop
*5000,40000,8400,256  then S   Mode 1: stream (* records, ~20/s);  E to stop
A32                            one 32-sample boxcar average (R record)
```

> Protocol note (firmware v4.23+): the `*` command takes **freq in Hz, pulse/delay in ns**; the `D`
> dynamic-profile command takes **µs**. See `docs/pimd_mcu.md` for the full contract.

## Hardware

- **Schematic:** the published KiCad project is **rev 6.04**, which represents the board **as-built**. The PCB itself was fabricated from rev **6.01**; 6.04 captures the corrections — there were a few PCB issues that needed rectifying after manufacture.
- **Front end / drive:** functional but a known rework target — a future revision will replace the TX switch and gate driver (planned: STP10NM60N + TC4420/TC4429) to retire the current FET being run past its rated SOA.
- **Thermal:** a thermistor is now fitted to the TX damping resistor. Thermal drift settles to effectively zero once the resistor reaches ~80 °C, which is the dominant warm-up transient.

![Schematic — PIMD rev 6.04](References/schematic-v604.jpg)

## Roadmap

This release is **Phase 2 — publish the work to date.** Active and planned work:

- **Phase 3 — machine learning.** Use the 63-cell decay-space matrix for filtering, classification and (the stretch goal) ground discrimination. First milestone reached (July 2026): a locked, delay-calibrated operating profile and a 17-target labelled signature corpus recorded at three distances, with distance-invariance, cross-session repeatability and mixture linearity all verified in air.
- **Faster response.** Investigate reducing cell count and per-cell averaging for quicker frames — the corpus so far says different targets go redundant in *different* cells, so nothing is cut yet.
- **Front-end revision** (TX switch + gate driver, as above), plus a scope measurement of TX coil current vs pulse width to settle whether the longest band is past the coil-current plateau.

See **DESIGN.md §14** for the full open-problems list.

## Documentation

- **[DESIGN.md](DESIGN.md)** — the complete engineering reference: measured operating envelope, coils, drive and receive chains, timing, serial protocol, power, invariants and curated test log. Self-contained; a new reader (human or agent) can pick up the project cold from it.
- **[docs/](docs/)** — concise cheat sheets for each tool and the firmware, plus the platform summary.
- **Build diary** — the full chronological story, with photos and dead-ends: <https://makies.com.au/pulse-induction-metal-detector/>
- **Video** — <https://www.youtube.com/@markmakies>

## Licence

This project uses two licences, matched to the kind of work:

- **Code** (`src/`, `mcu/`) — **GNU GPL v3.0-or-later**. See [`LICENSE`](LICENSE).
- **Hardware and documentation** (`Electronics/`, `docs/`, `DESIGN.md`, schematics, images) — **Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0)**. See [`LICENSE-docs`](LICENSE-docs).

Pulse Induction Metal Detector © 2022–2026 Mark Makies.

## Author

Built by **Mark Makies** (Australia).
Find more work at <https://makies.au/>.
