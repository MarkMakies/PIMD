
## What this project is

A working, field-tested pulse induction metal detector built by an experienced maker.
 **It is not a bring-up project — it already works.** The goal of any
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
  See README §13 for the full math. **The raw SPI path (SPI0/SDOB) is now live in
  `mcu/pimd_mcu.py` (Mode 2).** Metal detection response via Mode 2 confirmed 2026-06-16.
- Serial protocol — two non-concurrent modes (keep stable; the PC tools and the rover
  both speak it):
  - **Mode 1 — filtered/interrupt-driven:**
    - in: `S`/`s` start, `E`/`e` stop, `*<freq_kHz>,<pulse_us>,<delay_us>,<downsample>`
    - out: `*<time_ms>,<value_uV>,<stddev_uV>,<freq_kHz>,<pulse_us>,<delay_us>,<downsample>`
    - rate: pulse_freq / downsample (~20/s at 5 kHz / 256)
  - **Mode 2 — raw interleaved moving-average sweep:**
    - in: `Q<n>` select profile, `G`/`g` start streaming, `E`/`e` stop (shared)
    - out: `W<profile_idx>,<time_ms>,<mean_ch0>,<mean_ch1>,...`
    - rate: min(100 Hz, profile_freq / (z×y)); `S` rejected while Mode 2 running
  - **Both modes:** `V`/`v`/`?` identify, `L` list profiles, `A<x>` raw boxcar average
    (idle/Mode 1 only)
  - `E` is universal stop; modes are mutually exclusive (start of one requires `E` first)


## Control model — MCU stays a simple primitive + fixed profiles

The MCU must NOT grow a PC-driven scan engine. The orchestration model (README §13):
- Multi-point scans run from **fixed, compiled-in profiles** (a table selected by `Q<n>`),
  built on a single raw-acquisition primitive (interleaved one-period-per-cell loop with
  rolling average of depth x). `G` starts streaming; `E` stops. One command pair in →
  continuous W-record stream out. No PC-defined logic, no scheduler.
- **No flash writes** for profiles or anything else in the hot path (flash writes spike
  the noise floor ~10×). Profiles are compiled/RAM constants.
- Manual `*`/`S`/`E` commands stay for debug. Commands `Q<n>`/`G`/`L`/`V`/`?` are
  additive. Mode 2 `W` records are a new record type; the legacy `*` telemetry line stays
  valid. `P<n>` one-shot profile (v3.x) has been removed — use `Q<n>` + `G` instead.
- Keep a single read-line/write-line transport seam (USB-serial now → UART/LoRa later).
- Scan geometry is fixed per profile → ML classifiers are trained per-profile.

## Scan Profiles (compiled into firmware — `PROFILES` table in `mcu/pimd_mcu.py`)

| Idx | Name | Freq | Pulses (z) | Delays (y) | x | Cells | Confirmed |
|-----|------|------|-----------|-----------|---|-------|-----------|
| 0 | FAST_TRACK | 5 kHz | 40 µs | 8.4 µs | 8 | 1 | *not bench-tested this session* |
| 1 | CLASSIFY | 10 kHz | 8/20/40 µs | 8 log-spaced 5–40 µs | 32 | 24 | *not bench-tested this session* |
| 2 | SCOPE_CAL | 5 kHz | 10 µs | 8 log-spaced 5–40 µs | 1 | 8 | *not bench-tested this session* |
| 3 | TRACK_25K | 25 kHz | 10 µs | 7.6 µs | 16 | 1 | **verified 2026-06-16 (metal detection confirmed)** |

## Invariants — do not break

- Same-slice PWM phase-locking (above).
- The serial command/telemetry wire format (both modes).
- The µV scaling constant `5_000_000 // 2**31` (Mode 1 filtered path).
- Raw 14-bit µV conversion: `raw14 * 10_000_000 / 2**14` (Mode 2).
- The deliberate over-damping / early-sample design philosophy.
- The prime-ish pulse-rate choice (noise mitigation, not arbitrary).
- **No scan scheduler or PC-defined logic in firmware** beyond the fixed profile loop;
  **no flash writes** in normal operation.

## Coding conventions / environment

- MicroPython on RP2040 for `mcu/pimd_mcu.py`; pure-Python only, no CPython-only libs.
- PC tools are PyQt6: `src/pimd_gui.py` (Mode 1 GUI) and `src/pimd_scope.py` (Mode 2
  scope/visualiser). `src/pimd302.py` is the superseded v3.x GUI (kept for reference).
- Keep changes minimal and reversible; prefer a flagged main-loop fix over restructuring
  the ISR/acquisition model unless asked.
- When you cannot determine something from text (analogue behaviour, PCB layout, scope
  data), say so explicitly rather than guessing.
- Bump version number and add a header changelog line on every file edit.


**PC GUI — Mode 1 (PyQt6)**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt
cd src && python pimd_gui.py        # Mode 1 GUI, v4.00
```
- Connects to `/dev/ttyACM0` @ 115200 baud (hardcoded in `serial_open()`).
- Silently ignores `W` records if Mode 2 is running on the board.
- *Not bench-tested this session against v4.00 firmware.*

**PC Scope — Mode 2 (PyQt6)**
```bash
source .venv/bin/activate
cd src && python pimd_scope.py      # Mode 2 streaming visualiser, v4.00
```
- Connect → Start (sends `G`); profile spinbox sends `Q<n>` + restarts.
- Metal detection response confirmed 2026-06-16 with profile 3 (TRACK_25K).

**Package the GUI as a standalone executable**
```bash
cd src && pyinstaller --name=pimd_app --onefile --windowed pimd_gui.py
```
*(see `docs/build_notes.md` for the deploy-to-laptop copy step)*

**MCU firmware (RP2040, MicroPython)**
No build step — copy `mcu/pimd_mcu.py` and `mcu/main.py` onto the board's
filesystem via Thonny or `mpremote`:
```bash
source .venv/bin/activate
mpremote connect /dev/ttyACM0 fs cp mcu/pimd_mcu.py :pimd_mcu.py + fs cp mcu/main.py :main.py
```
Then **power-cycle the board** (mpremote reset does not re-enumerate USB reliably).
`main.py` is a one-line launcher: `import pimd_mcu`. The firmware's module-level code
runs the main loop on import.

Bench-test over a serial terminal at 115200 baud:
```
V           → version string
L           → list profiles
Q3          → select TRACK_25K
G           → start Mode 2 streaming (W records at ≤100 Hz)
E           → stop, safe state
*5,40,8.4,256  then S  → Mode 1 streaming (* records at ~20/s)
E           → stop
```

**Serial diagnostics**
```bash
python src/serial-speed-test.py   # raw packet-rate/interval probe on /dev/ttyACM0
```
