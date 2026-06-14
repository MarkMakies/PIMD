# CLAUDE.md — agent brief for the PIMD project

This file orients an AI coding agent (e.g. Claude Code) before it touches the repo.
Read it, then read `README.md` for full system detail. Review **against the stated
intent and the measured operating point below**, not against generic assumptions.

## What this project is

A working, field-tested pulse induction metal detector (hardware rev 6.01, firmware
v3.02, coil v4) built by an experienced maker. It is a payload for an autonomous
RTK-GPS rover. **It is not a bring-up project — it already works.** The goal of any
review or change is refinement: lower noise, less drift, more robust firmware. Do not
propose ground-up redesigns or "you should have used X instead" rewrites unless a
concrete defect justifies it.

## Measured operating envelope (treat as ground truth)

- TX pulse 40 µs, peak ≈ 7 A; sample delay 8.4 µs; pulse rate 5 kHz; decimation 256
  → 20 samples/s.
- Flyback measured: TX ≈ 251 V, RX ≈ 176 V. FET Q1 limits: < 10 A, < 300 µs, < 2 % duty.
- Filtered path noise ≈ ±450 µV; raw ≈ ±1400 µV; warmed-up σ < 100 µV; precision ≈ 10 µV.
- Sample-timing precision ≈ 15–20 ns.

If your analysis implies the detector "can't work" the way it's built, you are missing
context — the builder has scope captures proving otherwise. Flag the concern, don't
assert a contradiction.

## Hardware facts the firmware depends on (verified)

- MCU: Waveshare RP2040-Zero, MicroPython.
- **TX pulse and sample trigger MUST stay on the same PWM slice** (GPIO4 = PWM2A,
  GPIO5 = PWM2B, slice 2). This phase-locking is the core timing mechanism. **Never**
  refactor these onto different slices or replace with independent timers.
- ADC: LTC2508-32. SPI1 = filtered 32-bit (SDOA/SCKA/DRL, GPIO8/10/9). SPI0 = raw
  (SDOB/SCKB/BUSY, GPIO0/2/15). Decimation select SEL0 = GPIO12 (SEL1 currently
  unwired → only 256/1024 reachable).
- Filtered value → microvolts: `raw32 * 5_000_000 // 2**31`.
- **ADC acquisition architecture (decided):** for decay-curve / multi-delay capture and
  any moving-platform tracking, use the **fast no-latency raw output (SDOB, 14-bit)**,
  NOT the 32-bit filtered path. At the 5 kHz pulse rate the filtered path has ≈ 0.46 s
  group delay, ≈ 0.5 s settling after any sample-delay change, and only ≈ 2.4 Hz
  bandwidth — unusable for sweeping the sample point. Recover resolution by
  boxcar-averaging M raw samples at a held delay (noise ∝ 1/√M; M=16 ≈ 350 µV in
  ~3.2 ms, matching the filtered path's real-world 450 µV floor). Reserve the filtered
  32-bit path (SDOA) for a single held sweet-spot delay used as the low-noise baseline,
  where ~0.5 s latency is fine. The 32-bit precision is otherwise wasted: measured noise
  (~450 µV) is ~500× the converter's own 0.95 µV floor, i.e. the front end dominates.
  See README §13 for the full math. The raw SPI path is currently dead code in
  `pimd_mcu_302.py` and is the thing to bring to life.
- Serial protocol (keep stable; the PC GUI and the rover both speak it):
  - in: `S`/`s` run, `E`/`e` stop, `*<freq_kHz>,<pulse_us>,<delay_us>,<downsample>`
  - out: `*<time_ms>,<value_uV>,<stddev_uV>,<freq_kHz>,<pulse_us>,<delay_us>,<downsample>`

## Known confirmed issues you may fix

See `REVIEW.md` for the full list with line references. Highest value:
1. `print()` and a 4-byte SPI read inside the DRL interrupt handler (MicroPython ISR
   hazard).
2. No bound on `drive_duty`/`sample_duty` — can wrap past 65535 at high freq + wide
   pulse, silently corrupting timing.
3. The raw-ADC path is initialised but unused in this firmware version (dead code or
   missing logic — confirm intent before deleting).

## Control model — MCU stays a simple primitive + fixed profiles

The MCU must NOT grow a PC-driven scan engine. The orchestration model (README §13):
- Multi-point scans run from **fixed, compiled-in profiles** (a table selected by index),
  built on a single raw-acquisition primitive ("acquire x averages at the current
  delay"). One command in → one matrix streamed out. The only new firmware logic is a
  fixed loop over a compiled profile table — no PC-defined logic, no scheduler.
- **No flash writes** for profiles or anything else in the hot path (flash writes spike
  the noise floor ~10×). Profiles are compiled/RAM constants.
- Manual `*`/`S`/`E` commands stay for debug. New commands are additive: `P<n>` run
  profile, `L` list profiles, `V`/`?` identify. New scan output is a new record type;
  the legacy `*` telemetry line stays valid.
- Keep a single read-line/write-line transport seam (USB-serial now → UART/LoRa later).
- Scan geometry is fixed per profile → ML classifiers are trained per-profile.

## Invariants — do not break

- Same-slice PWM phase-locking (above).
- The serial command/telemetry wire format.
- The µV scaling constant `5_000_000 // 2**31`.
- The deliberate over-damping / early-sample design philosophy.
- The prime-ish pulse-rate choice (noise mitigation, not arbitrary).
- **No scan scheduler or PC-defined logic in firmware** beyond the fixed profile loop;
  **no flash writes** in normal operation.

## Coding conventions / environment

- MicroPython on RP2040 for `pimd_mcu_302.py`; pure-Python only, no CPython-only libs.
- PC GUI is PyQt6 (`pimd302.py` + generated `pimd111_ui.py`).
- Keep changes minimal and reversible; prefer a flagged main-loop fix over restructuring
  the ISR/acquisition model unless asked.
- When you cannot determine something from text (analogue behaviour, PCB layout, scope
  data), say so explicitly rather than guessing.

## Development commands

There is no test suite and no CI — this is a hardware project, verified by running it
against the real board/GUI.

**PC GUI (PyQt6)**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
cd src && python pimd302.py        # active GUI, v3.02
```
- Connects to `/dev/ttyACM0` @ 115200 baud (hardcoded in `serial_open()` in
  `pimd302.py`).
- `pimd111_ui.py` is generated from `pimd111.ui` via Qt Designer — regenerate with
  `pyuic6 -o pimd111_ui.py pimd111.ui`; never hand-edit the generated file.

**Lint**
```bash
flake8 src mcu          # config: .flake8 (max-line-length=120)
```

**Package the GUI as a standalone executable**
```bash
cd src && pyinstaller --name=pimd_app --onefile --windowed pimd302.py
# or: pyinstaller pimd_app.spec
```
(see `docs/build_notes.md` for the deploy-to-laptop copy step)

**MCU firmware (RP2040, MicroPython)**
No build step — copy `mcu/pimd_mcu_302.py` and `mcu/main.py` onto the board's
filesystem (e.g. via Thonny or `mpremote cp`). Bench-test over a serial terminal at
115200 baud using the protocol in README §7, e.g. `*5,40,8.4,256` then `S` to start,
`E` to stop.

**Serial diagnostics**
```bash
python src/serial-speed-test.py   # raw packet-rate/interval probe on /dev/ttyACM0
```

