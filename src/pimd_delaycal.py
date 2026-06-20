###############################################################################
# PIMD Delay Calibration v1.03
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# For each configured (freq, pulse) pair, sweeps the sample delay from a start
# value in configurable steps, taking an A<n> raw boxcar average at each step,
# and records the (interpolated) delay at which the ADC reading crosses each
# target voltage threshold.  Results are shown in a live-updating table:
#   rows    = freq/pulse pairs  (e.g. "25kHz/10us")
#   columns = target voltages (V)
#   cells   = delay (µs) at threshold crossing, snapped to 8 ns PWM grid (0.008 µs)
#
# Firmware commands used:
#   E                                      — safe state (on connect / stop / done)
#   *<freq_kHz>,<pulse_us>,<delay_us>,256  — configure PWM (no streaming)
#   A<n>                                   — raw boxcar average; returns R record
#   D<avg>;<freq_hz>,<pulse_us>,<d0>,...;… — define dynamic profile (thermal mode)
#   Q<n>                                   — select profile
#   G                                      — start Mode 2 streaming
#
# v1.05 Snap interpolated threshold-crossing delays to the 8 ns PWM clock grid
#       before storing in the table and exporting; display to 3 d.p. (0.008 µs
#       precision) instead of 2 d.p.  Off-grid delays cause ±1 LSB PWM jitter
#       (documented in pimd_gui.py v4.08 / pimd_mcu.py v4.22).
# v1.04 Thermal std dev: display to 2 decimal places (was integer mV).
# v1.03 Profile export: autosave calibrated delays as a classviz-compatible JSON
#       profile to data/profiles/ (timestamped, same format as pimd_classviz.py
#       _default_profile()).  Thermal monitoring mode: streams Mode 2 with the
#       exported profile for a configurable countdown, showing live latest-mean
#       and rolling-std-dev tables (rate-limited to 10 Hz).  Config panel widened
#       280→320 px; window resized 1050×620→1200×850.
# v1.02 fix double-send bug: _on_r_record() no longer advances state when _check_thresholds()
#        already called _advance_pair(); saves current_delay before threshold check so
#        _prev_delay is always the actual measured delay, not the post-reset start_delay
# v1.01 freq and pulse width paired as tuples (freq/pulse input field, e.g. 25/10)
# v1.00 initial version
###############################################################################

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import json
import os
import sys
import time
from collections import deque
from datetime import datetime
from statistics import stdev as _stdev

os.environ.setdefault('QT_API', 'pyqt6')

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDoubleSpinBox, QSpinBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QFileDialog, QHeaderView,
)
from PyQt6.QtSerialPort import QSerialPort  # noqa: E402
from PyQt6.QtCore import QIODevice, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QColor  # noqa: E402

APP_VERSION = '1.05'

DYNAMIC_PROFILE_INDEX = 5   # matches pimd_mcu.py NUM_PROFILES / pimd_classviz.py
PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'data', 'profiles')

def _snap_8ns(delay_us):
    """Round a delay to the nearest 8 ns RP2040 PWM clock boundary."""
    ns = round(delay_us * 1000)          # µs → ns, integer
    return (round(ns / 8) * 8) / 1000   # snap to 8 ns grid, back to µs


# Cell background colours
_COL_PENDING  = QColor(200, 220, 255)   # light blue: in progress
_COL_DONE     = QColor(143, 240, 164)   # green:      threshold found
_COL_NR       = QColor(210, 210, 210)   # grey:       not reached within max delay


class MainWindow(QMainWindow):
    MY_GREEN  = 'background-color: rgb(143, 240, 164);'
    MY_YELLOW = 'background-color: rgb(249, 240, 107);'
    MY_RED    = 'background-color: rgb(246, 97, 81);'

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'PIMD Delay Calibration v{APP_VERSION}')

        self.serial = QSerialPort()
        self.serial.readyRead.connect(self.read_from_serial)

        self.last_command = ''
        self.last_packet  = ''

        # Sweep state ─ reset at the start of every run
        self._state       = 'idle'   # 'idle' | 'sweeping' | 'done'
        self._fp_pairs    = []       # list of (freq_khz, pulse_us) tuples in run order
        self._thresholds  = []       # sorted-descending target voltages (µV ints)
        self._targets_v   = []       # same order as _thresholds, in V (for CSV header)
        self._pair_idx    = 0
        self._thresh_idx  = 0
        self._delay       = 0.0     # current delay being tested (µs)
        self._start_delay = 0.0     # snapshot of sp_start at run time
        self._step_size   = 0.1     # snapshot of sp_step  at run time
        self._step_count  = 0       # steps taken this pair (avoids float accumulation)
        self._prev_delay  = None    # delay of last R record (µs)
        self._prev_uV     = None    # mean_uV of last R record

        # Thermal / profile state
        self._thermal_state      = 'idle'       # 'idle' | 'running'
        self._thermal_remaining  = 0.0
        self._thermal_timer: 'QTimer | None' = None
        self._thermal_buf: deque = deque(maxlen=10_000)
        self._thermal_latest: 'list | None' = None  # µV ints, length n_channels
        self._thermal_n_bands    = 0
        self._thermal_n_cells    = 0
        self._thermal_n_channels = 0
        self._thermal_last_redraw = 0.0         # rate-limit redraws to ~10 Hz

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # Top bar
        top = QHBoxLayout()
        top.setSpacing(6)

        top.addWidget(QLabel('Port:'))
        self.le_port = QLineEdit('/dev/ttyACM0')
        self.le_port.setFixedWidth(140)
        top.addWidget(self.le_port)

        self.pb_connect = QPushButton('Not Connected')
        self.pb_connect.setStyleSheet(self.MY_YELLOW)
        self.pb_connect.setFixedWidth(120)
        self.pb_connect.clicked.connect(self.connect_port)
        top.addWidget(self.pb_connect)

        top.addSpacing(12)

        self.pb_run = QPushButton('Run')
        self.pb_run.setFixedWidth(80)
        self.pb_run.setEnabled(False)
        self.pb_run.clicked.connect(self.run_calibration)
        top.addWidget(self.pb_run)

        self.pb_stop = QPushButton('Stop')
        self.pb_stop.setFixedWidth(80)
        self.pb_stop.setEnabled(False)
        self.pb_stop.clicked.connect(self.stop_calibration)
        top.addWidget(self.pb_stop)

        self.pb_export = QPushButton('Export CSV')
        self.pb_export.setFixedWidth(100)
        self.pb_export.setEnabled(False)
        self.pb_export.clicked.connect(self.export_csv)
        top.addWidget(self.pb_export)

        self.pb_export_profile = QPushButton('Export Profile')
        self.pb_export_profile.setFixedWidth(110)
        self.pb_export_profile.setEnabled(False)
        self.pb_export_profile.clicked.connect(self.export_profile)
        top.addWidget(self.pb_export_profile)

        top.addSpacing(10)
        self.status_label = QLabel('Connect the board to begin.')
        top.addWidget(self.status_label, stretch=1)

        root.addLayout(top)

        # Content row: config left, results right
        content = QHBoxLayout()
        content.setSpacing(8)

        # Config panel
        cfg_box = QGroupBox('Configuration')
        cfg_box.setFixedWidth(320)
        form = QFormLayout(cfg_box)
        form.setSpacing(6)

        self.sp_start = QDoubleSpinBox()
        self.sp_start.setRange(0.10, 50.0)
        self.sp_start.setSingleStep(0.10)
        self.sp_start.setValue(5.0)
        self.sp_start.setSuffix(' us')
        self.sp_start.setDecimals(2)
        form.addRow('Start delay:', self.sp_start)

        self.sp_step = QDoubleSpinBox()
        self.sp_step.setRange(0.01, 5.0)
        self.sp_step.setSingleStep(0.01)
        self.sp_step.setValue(0.10)
        self.sp_step.setSuffix(' us')
        self.sp_step.setDecimals(2)
        form.addRow('Step size:', self.sp_step)

        self.sp_max = QDoubleSpinBox()
        self.sp_max.setRange(1.0, 200.0)
        self.sp_max.setSingleStep(0.5)
        self.sp_max.setValue(45.0)
        self.sp_max.setSuffix(' us')
        self.sp_max.setDecimals(1)
        form.addRow('Max delay:', self.sp_max)

        self.sp_avg = QSpinBox()
        self.sp_avg.setRange(10, 1000)
        self.sp_avg.setSingleStep(10)
        self.sp_avg.setValue(100)
        form.addRow('Averages N:', self.sp_avg)

        # freq/pulse pairs: "25/10, 20/20, 5/40"  →  (freq kHz)/(pulse µs)
        self.le_fp_pairs = QLineEdit('25/10, 20/20, 5/40')
        self.le_fp_pairs.setToolTip(
            'Comma-separated freq/pulse pairs (kHz/µs)\n'
            'e.g.  25/10, 20/20, 5/40')
        form.addRow('Freq/Pulse (kHz/us):', self.le_fp_pairs)

        self.le_targets = QLineEdit('4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5')
        form.addRow('Targets (V):', self.le_targets)

        content.addWidget(cfg_box)

        # Results area
        right = QVBoxLayout()
        right.setSpacing(4)

        self.progress_label = QLabel('Ready — configure parameters and press Run.')
        right.addWidget(self.progress_label)

        self.table = QTableWidget(0, 0)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        right.addWidget(self.table, stretch=1)

        # ── Thermal monitoring section ────────────────────────────────
        therm_grp = QGroupBox('Thermal Monitoring')
        therm_layout = QVBoxLayout(therm_grp)
        therm_layout.setSpacing(4)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        self.pb_thermal = QPushButton('THERMAL')
        self.pb_thermal.setFixedWidth(90)
        self.pb_thermal.setEnabled(False)
        self.pb_thermal.clicked.connect(self._start_thermal)
        ctrl.addWidget(self.pb_thermal)

        self.sp_thermal_secs = QSpinBox()
        self.sp_thermal_secs.setRange(10, 3600)
        self.sp_thermal_secs.setValue(240)
        self.sp_thermal_secs.setSuffix(' s')
        self.sp_thermal_secs.setFixedWidth(80)
        ctrl.addWidget(self.sp_thermal_secs)

        self.pb_thermal_stop = QPushButton('Stop')
        self.pb_thermal_stop.setFixedWidth(60)
        self.pb_thermal_stop.setEnabled(False)
        self.pb_thermal_stop.clicked.connect(self._stop_thermal)
        ctrl.addWidget(self.pb_thermal_stop)

        ctrl.addSpacing(16)
        ctrl.addWidget(QLabel('Std dev N:'))

        self.sp_thermal_n = QSpinBox()
        self.sp_thermal_n.setRange(2, 2000)
        self.sp_thermal_n.setValue(50)
        self.sp_thermal_n.setFixedWidth(70)
        ctrl.addWidget(self.sp_thermal_n)

        self.lbl_thermal_status = QLabel('')
        ctrl.addWidget(self.lbl_thermal_status, stretch=1)

        therm_layout.addLayout(ctrl)

        therm_layout.addWidget(QLabel('Latest mean (mV):'))

        self.tbl_thermal_mean = QTableWidget(0, 0)
        self.tbl_thermal_mean.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_thermal_mean.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.tbl_thermal_mean.setMaximumHeight(140)
        therm_layout.addWidget(self.tbl_thermal_mean)

        therm_layout.addWidget(QLabel('Std dev (mV):'))

        self.tbl_thermal_std = QTableWidget(0, 0)
        self.tbl_thermal_std.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_thermal_std.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.tbl_thermal_std.setMaximumHeight(140)
        therm_layout.addWidget(self.tbl_thermal_std)

        right.addWidget(therm_grp)
        # ─────────────────────────────────────────────────────────────

        content.addLayout(right, stretch=1)
        root.addLayout(content, stretch=1)

        self.setCentralWidget(central)
        self.statusBar().showMessage('Not connected')

    # ------------------------------------------------------------------
    # Serial
    # ------------------------------------------------------------------
    def connect_port(self):
        if self.pb_connect.text() != 'Connected':
            if self._serial_open(True):
                self.pb_connect.setText('Connected')
                self.pb_connect.setStyleSheet(self.MY_GREEN)
                self.send_command('E')
                self.pb_run.setEnabled(True)
                self.statusBar().showMessage('Connected — ready to run.')
            else:
                self.pb_connect.setText('Port Error')
                self.pb_connect.setStyleSheet(self.MY_RED)
                self.statusBar().showMessage('Serial port error.')
        else:
            self.stop_calibration()
            self._stop_thermal()
            self._serial_open(False)
            self.pb_connect.setText('Not Connected')
            self.pb_connect.setStyleSheet(self.MY_YELLOW)
            self.pb_run.setEnabled(False)
            self.statusBar().showMessage('Disconnected.')

    def _serial_open(self, flag):
        if flag:
            port = self.le_port.text().strip()
            if port.startswith('/dev/'):
                port = port[5:]          # QSerialPort wants bare device name on Linux
            self.serial.setPortName(port)
            self.serial.setBaudRate(115200)
            self.serial.setDataBits(QSerialPort.DataBits.Data8)
            self.serial.setParity(QSerialPort.Parity.NoParity)
            self.serial.setStopBits(QSerialPort.StopBits.OneStop)
            self.serial.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
            return self.serial.open(QIODevice.OpenModeFlag.ReadWrite)
        else:
            self.serial.close()
            return True

    def send_command(self, text):
        self.serial.write((text + '\n').encode())
        self.last_command = text

    def read_from_serial(self):
        while self.serial.canReadLine():
            raw = self.serial.readLine().data().decode('utf-8', errors='replace').rstrip()
            if not raw:
                continue
            self.last_packet = raw
            self._update_status_bar()

            if self._thermal_state == 'running' and raw.startswith('W'):
                self._on_thermal_w_record(raw)
                continue

            if raw.startswith('R'):
                self._on_r_record(raw)
            elif 'ERROR' in raw:
                self.status_label.setText(f'Firmware: {raw}')

    # ------------------------------------------------------------------
    # Calibration sweep
    # ------------------------------------------------------------------
    def _parse_config(self):
        """
        Parse config widgets.
        Returns (fp_pairs, thresholds_uV, targets_v).
        fp_pairs: list of (freq_khz, pulse_us) tuples, in entry order.
        """
        fp_pairs = []
        for token in self.le_fp_pairs.text().split(','):
            token = token.strip()
            if not token:
                continue
            parts = token.split('/')
            if len(parts) != 2:
                raise ValueError(
                    f'Bad freq/pulse pair "{token}" — use format freq/pulse, e.g. 25/10')
            try:
                freq_khz = float(parts[0].strip())
                pulse_us = float(parts[1].strip())
            except ValueError:
                raise ValueError(
                    f'Non-numeric freq/pulse pair "{token}"')
            if freq_khz <= 0 or pulse_us <= 0:
                raise ValueError(
                    f'Freq and pulse must be positive (got "{token}")')
            fp_pairs.append((freq_khz, pulse_us))
        if not fp_pairs:
            raise ValueError('Enter at least one freq/pulse pair.')

        try:
            targets_v = sorted(
                (float(v.strip()) for v in self.le_targets.text().split(',')
                 if v.strip()),
                reverse=True)
        except ValueError:
            raise ValueError('Invalid target voltages — enter comma-separated numbers.')
        if not targets_v:
            raise ValueError('Enter at least one target voltage.')

        thresholds_uV = [int(v * 1_000_000) for v in targets_v]
        return fp_pairs, thresholds_uV, targets_v

    def _row_label(self, freq_khz, pulse_us):
        freq_str  = f'{freq_khz:.0f}' if freq_khz == int(freq_khz) else f'{freq_khz:.1f}'
        pulse_str = f'{pulse_us:.0f}' if pulse_us  == int(pulse_us)  else f'{pulse_us:.1f}'
        return f'{freq_str}kHz/{pulse_str}us'

    def _rebuild_table(self, fp_pairs, targets_v):
        self.table.clear()
        self.table.setRowCount(len(fp_pairs))
        self.table.setColumnCount(len(targets_v))
        self.table.setVerticalHeaderLabels(
            [self._row_label(f, p) for f, p in fp_pairs])
        self.table.setHorizontalHeaderLabels([f'{v:.1f} V' for v in targets_v])
        for r in range(len(fp_pairs)):
            for c in range(len(targets_v)):
                item = QTableWidgetItem('')
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, item)

    def _mark_row_pending(self, row):
        """Highlight unmeasured cells in the current row as in-progress."""
        for c in range(self._thresh_idx, len(self._thresholds)):
            item = self.table.item(row, c)
            if item:
                item.setBackground(_COL_PENDING)

    def run_calibration(self):
        if not self.serial.isOpen():
            self.status_label.setText('Not connected.')
            return
        try:
            fp_pairs, thresholds_uV, targets_v = self._parse_config()
        except ValueError as e:
            self.status_label.setText(str(e))
            return

        self._fp_pairs    = fp_pairs
        self._thresholds  = thresholds_uV
        self._targets_v   = targets_v
        self._pair_idx    = 0
        self._thresh_idx  = 0
        self._start_delay = self.sp_start.value()
        self._step_size   = self.sp_step.value()
        self._step_count  = 0
        self._delay       = self._start_delay
        self._prev_delay  = None
        self._prev_uV     = None
        self._state       = 'sweeping'

        self._rebuild_table(fp_pairs, targets_v)
        self._mark_row_pending(0)

        self.pb_run.setEnabled(False)
        self.pb_stop.setEnabled(True)
        self.pb_export.setEnabled(False)
        self.pb_export_profile.setEnabled(False)
        self.pb_thermal.setEnabled(False)

        self.send_command('E')     # ensure firmware is in ready state
        self._send_next_step()

    def _send_next_step(self):
        """Send * config + A<n> for the current (freq, pulse, delay)."""
        if self._state != 'sweeping':
            return

        freq, pulse = self._fp_pairs[self._pair_idx]
        n = self.sp_avg.value()

        if self._delay > self.sp_max.value():
            self._mark_remaining_nr()
            self._advance_pair()
            return

        self.send_command(f'*{freq:.1f},{pulse:.1f},{self._delay:.2f},256')
        self.send_command(f'A{n}')

        total = len(self._fp_pairs) * len(self._thresholds)
        done  = self._pair_idx * len(self._thresholds) + self._thresh_idx
        self.progress_label.setText(
            f'{self._row_label(freq, pulse)} | Delay {self._delay:.2f} us | '
            f'{done}/{total} thresholds found')

    def _on_r_record(self, line):
        """Parse R record and advance sweep state machine."""
        if self._state != 'sweeping':
            return
        # Format: R<t>, <mean_uV>, <std_uV>, <count>, <freq_kHz>, <pulse_us>, <delay_us>
        parts = line[1:].split(',')
        try:
            mean_uV = int(parts[1])
            std_uV  = int(parts[2])
        except (ValueError, IndexError):
            return

        freq, pulse = self._fp_pairs[self._pair_idx]
        voltage_v = mean_uV / 1_000_000
        self.status_label.setText(
            f'{self._row_label(freq, pulse)} | Delay {self._delay:.2f} us | '
            f'Reading {voltage_v:.4f} V  (σ = {std_uV / 1000:.1f} mV)')

        current_pair_idx = self._pair_idx
        current_delay    = self._delay

        self._check_thresholds(mean_uV)

        # Only advance to the next step if _check_thresholds() did NOT call _advance_pair().
        # If it did, _advance_pair already reset all state and called _send_next_step().
        # Sending again here would corrupt the new pair's pipeline with a double-send.
        if self._state == 'sweeping' and self._pair_idx == current_pair_idx:
            self._prev_delay = current_delay
            self._prev_uV    = mean_uV
            self._step_count += 1
            self._delay = round(
                self._start_delay + self._step_count * self._step_size, 6)
            self._send_next_step()

    def _check_thresholds(self, mean_uV):
        """Detect all threshold crossings in this step; fill cells with interpolated delays."""
        while self._thresh_idx < len(self._thresholds):
            target_uV = self._thresholds[self._thresh_idx]
            if mean_uV > target_uV:
                break   # not yet crossed

            # Crossed — linear interpolation between previous and current reading,
            # then snap to the 8 ns PWM clock grid to avoid ±1 LSB jitter.
            if (self._prev_uV is not None
                    and self._prev_uV > target_uV
                    and self._prev_uV != mean_uV):
                frac = (self._prev_uV - target_uV) / (self._prev_uV - mean_uV)
                interp = self._prev_delay + frac * (self._delay - self._prev_delay)
            else:
                interp = self._delay   # first step already at or below threshold
            interp = _snap_8ns(interp)

            self._fill_cell(self._pair_idx, self._thresh_idx,
                            f'{interp:.3f}', color=_COL_DONE)
            self._thresh_idx += 1

        if self._thresh_idx >= len(self._thresholds):
            self._advance_pair()

    def _fill_cell(self, row, col, text, color=None):
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, col, item)
        else:
            item.setText(text)
        if color is not None:
            item.setBackground(color)

    def _mark_remaining_nr(self):
        """Mark all unfound thresholds for the current row as N/R."""
        for c in range(self._thresh_idx, len(self._thresholds)):
            self._fill_cell(self._pair_idx, c, 'N/R', color=_COL_NR)

    def _advance_pair(self):
        """Move to the next freq/pulse pair, or finish if all pairs done."""
        self._pair_idx   += 1
        self._thresh_idx  = 0
        self._step_count  = 0
        self._delay       = self._start_delay
        self._prev_delay  = None
        self._prev_uV     = None

        if self._pair_idx >= len(self._fp_pairs):
            self._finish()
        else:
            self._mark_row_pending(self._pair_idx)
            self._send_next_step()

    def _finish(self):
        self._state = 'done'
        self.send_command('E')
        self.pb_run.setEnabled(True)
        self.pb_stop.setEnabled(False)
        self.pb_export.setEnabled(True)
        self.pb_export_profile.setEnabled(True)
        self.pb_thermal.setEnabled(True)
        self.progress_label.setText('Calibration complete.')
        self.status_label.setText('Done — Export CSV / Export Profile / THERMAL.')
        self.statusBar().showMessage('Calibration complete.')

    def stop_calibration(self):
        self._state = 'idle'
        if self.serial.isOpen():
            self.send_command('E')
        self.pb_run.setEnabled(self.serial.isOpen())
        self.pb_stop.setEnabled(False)
        self.pb_export.setEnabled(self.table.rowCount() > 0)
        self.pb_export_profile.setEnabled(
            self.table.rowCount() > 0 and bool(self._fp_pairs))
        self.progress_label.setText('Stopped.')
        self.status_label.setText('Sweep stopped.')

    # ------------------------------------------------------------------
    # Profile export
    # ------------------------------------------------------------------
    def _build_profile(self):
        """Build a classviz-compatible profile dict from the calibration table."""
        max_delay = self.sp_max.value()
        bands = []
        for r, (freq_khz, pulse_us) in enumerate(self._fp_pairs):
            delays = []
            for c in range(len(self._targets_v)):
                item = self.table.item(r, c)
                text = item.text() if item else ''
                if text and text != 'N/R':
                    try:
                        delays.append(_snap_8ns(float(text)))
                    except ValueError:
                        delays.append(_snap_8ns(max_delay))
                else:
                    delays.append(_snap_8ns(max_delay))
            bands.append({
                'freq_hz':    int(round(freq_khz * 1000)),
                'pulse_us':   pulse_us,
                'delays_us':  delays,
                'threshold_v': list(self._targets_v),
            })
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        return {
            'name':     f'cal_{ts}',
            'averages': 32,
            'bands':    bands,
        }

    def export_profile(self):
        if not self._fp_pairs or not self._targets_v:
            self.statusBar().showMessage('No calibration data to export.')
            return
        profile = self._build_profile()
        os.makedirs(PROFILES_DIR, exist_ok=True)
        path = os.path.join(PROFILES_DIR, f"{profile['name']}.json")
        with open(path, 'w') as f:
            json.dump(profile, f, indent=2)
        self.statusBar().showMessage(f'Profile saved: {path}')
        self.status_label.setText(f'Profile → {os.path.basename(path)}')

    # ------------------------------------------------------------------
    # D command builder (same format as pimd_classviz.py)
    # ------------------------------------------------------------------
    def _build_d_command(self, profile):
        parts = [f'D{profile["averages"]}']
        for b in profile['bands']:
            fields = [str(b['freq_hz']), str(b['pulse_us'])]
            fields += [f'{d:.3f}' for d in b['delays_us']]
            parts.append(','.join(fields))
        return ';'.join(parts)

    # ------------------------------------------------------------------
    # Thermal monitoring
    # ------------------------------------------------------------------
    def _start_thermal(self):
        if not self.serial.isOpen():
            self.statusBar().showMessage('Not connected.')
            return
        if not self._fp_pairs or not self._targets_v:
            self.statusBar().showMessage('Run calibration first.')
            return

        profile = self._build_profile()
        n_bands = len(profile['bands'])
        n_cells = len(profile['bands'][0]['delays_us'])
        self._thermal_n_bands    = n_bands
        self._thermal_n_cells    = n_cells
        self._thermal_n_channels = n_bands * n_cells
        self._thermal_buf.clear()
        self._thermal_latest     = None
        self._thermal_remaining  = float(self.sp_thermal_secs.value())
        self._thermal_state      = 'running'

        # Define dynamic profile and start Mode 2 streaming
        self.send_command('E')
        self.send_command(self._build_d_command(profile))
        self.send_command(f'Q{DYNAMIC_PROFILE_INDEX}')
        self.send_command('G')

        self._rebuild_thermal_tables(profile)

        self._thermal_timer = QTimer(self)
        self._thermal_timer.setInterval(1000)
        self._thermal_timer.timeout.connect(self._thermal_tick)
        self._thermal_timer.start()

        self.pb_thermal.setEnabled(False)
        self.pb_thermal.setStyleSheet(self.MY_GREEN)
        self.pb_thermal_stop.setEnabled(True)
        self.pb_run.setEnabled(False)
        self.lbl_thermal_status.setText(
            f'Running — {int(self._thermal_remaining)} s remaining')
        self.statusBar().showMessage('Thermal monitoring started.')

    def _stop_thermal(self):
        if self._thermal_state != 'running':
            return
        self._thermal_state = 'idle'
        if self._thermal_timer:
            self._thermal_timer.stop()
            self._thermal_timer = None
        if self.serial.isOpen():
            self.send_command('E')
        self.pb_thermal.setEnabled(bool(self._fp_pairs))
        self.pb_thermal.setStyleSheet('')
        self.pb_thermal_stop.setEnabled(False)
        self.pb_run.setEnabled(self.serial.isOpen())
        self.lbl_thermal_status.setText('Stopped.')
        self.statusBar().showMessage('Thermal monitoring stopped.')

    def _thermal_tick(self):
        self._thermal_remaining -= 1.0
        if self._thermal_remaining <= 0:
            self.lbl_thermal_status.setText('Complete.')
            self._stop_thermal()
        else:
            self.lbl_thermal_status.setText(
                f'Running — {int(self._thermal_remaining)} s remaining')

    def _rebuild_thermal_tables(self, profile):
        """Size both thermal tables to match the profile dimensions."""
        row_labels = [
            self._row_label(b['freq_hz'] / 1000, b['pulse_us'])
            for b in profile['bands']
        ]
        col_labels = [f'{v:.1f} V' for v in self._targets_v]
        n_rows, n_cols = len(row_labels), len(col_labels)

        for tbl in (self.tbl_thermal_mean, self.tbl_thermal_std):
            tbl.setRowCount(n_rows)
            tbl.setColumnCount(n_cols)
            tbl.setVerticalHeaderLabels(row_labels)
            tbl.setHorizontalHeaderLabels(col_labels)
            for r in range(n_rows):
                for c in range(n_cols):
                    item = QTableWidgetItem('—')
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    tbl.setItem(r, c, item)

    def _on_thermal_w_record(self, line):
        """Parse W record from Mode 2 streaming and feed thermal display."""
        line = line.replace(', ', ',')
        parts = line.split(',')
        try:
            w_idx = int(parts[0][1:])
            if w_idx != DYNAMIC_PROFILE_INDEX:
                return
            if len(parts) != 2 + self._thermal_n_channels:
                return
            raw = [int(parts[2 + i]) for i in range(self._thermal_n_channels)]
        except (ValueError, IndexError):
            return

        self._thermal_latest = raw
        self._thermal_buf.append(raw)
        self._update_thermal_tables()

    def _update_thermal_tables(self):
        """Update mean and std-dev tables; rate-limited to ~10 Hz."""
        now = time.time()
        if now - self._thermal_last_redraw < 0.1:
            return
        self._thermal_last_redraw = now

        if self._thermal_latest is None:
            return

        latest = self._thermal_latest
        n = self.sp_thermal_n.value()
        recent = list(self._thermal_buf)[-n:]

        for b in range(self._thermal_n_bands):
            for c in range(self._thermal_n_cells):
                ch = b * self._thermal_n_cells + c

                item_m = self.tbl_thermal_mean.item(b, c)
                if item_m:
                    item_m.setText(str(int(latest[ch] / 1000)))

                item_s = self.tbl_thermal_std.item(b, c)
                if item_s:
                    if len(recent) >= 2:
                        vals = [frame[ch] for frame in recent]
                        item_s.setText(f'{_stdev(vals) / 1000:.2f}')
                    else:
                        item_s.setText('0.00')

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------
    def export_csv(self):
        os.makedirs('data', exist_ok=True)
        timestamp = datetime.now().strftime('%d%m-%H%M%S')
        default_path = os.path.join('data', f'delaycal_{timestamp}.csv')
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save calibration CSV', default_path, 'CSV files (*.csv)')
        if not path:
            return
        try:
            with open(path, 'w') as f:
                headers = ['freq_kHz/pulse_us'] + [f'{v:.1f}V' for v in self._targets_v]
                f.write(','.join(headers) + '\n')
                for r, (freq, pulse) in enumerate(self._fp_pairs):
                    row_vals = [self._row_label(freq, pulse)]
                    for c in range(len(self._targets_v)):
                        item = self.table.item(r, c)
                        row_vals.append(item.text() if item else '')
                    f.write(','.join(row_vals) + '\n')
            self.statusBar().showMessage(f'Exported: {path}')
        except OSError as e:
            self.statusBar().showMessage(f'Export error: {e}')

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _update_status_bar(self):
        self.statusBar().showMessage(
            f'Last cmd: {self.last_command:<35} | Last pkt: {self.last_packet}')

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._stop_thermal()
        if self.serial.isOpen():
            self.send_command('E')
            self.serial.waitForBytesWritten(200)
            self.serial.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 850)
    window.show()
    sys.exit(app.exec())
