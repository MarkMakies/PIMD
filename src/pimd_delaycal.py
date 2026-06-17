###############################################################################
# PIMD Delay Calibration v1.01
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# For each configured (freq, pulse) pair, sweeps the sample delay from a start
# value in configurable steps, taking an A<n> raw boxcar average at each step,
# and records the (interpolated) delay at which the ADC reading crosses each
# target voltage threshold.  Results are shown in a live-updating table:
#   rows    = freq/pulse pairs  (e.g. "25kHz/10us")
#   columns = target voltages (V)
#   cells   = delay (µs) at threshold crossing, to 0.01 µs precision
#
# Firmware commands used:
#   E                                      — safe state (on connect / stop / done)
#   *<freq_kHz>,<pulse_us>,<delay_us>,256  — configure PWM (no streaming)
#   A<n>                                   — raw boxcar average; returns R record
#
# v1.00 initial version
# v1.01 freq and pulse width paired as tuples (freq/pulse input field, e.g. 25/10)
# v1.02 fix double-send bug: _on_r_record() no longer advances state when _check_thresholds()
#        already called _advance_pair(); saves current_delay before threshold check so
#        _prev_delay is always the actual measured delay, not the post-reset start_delay
###############################################################################

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import os
import sys
from datetime import datetime

os.environ.setdefault('QT_API', 'pyqt6')

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDoubleSpinBox, QSpinBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QFileDialog, QHeaderView,
)
from PyQt6.QtSerialPort import QSerialPort  # noqa: E402
from PyQt6.QtCore import QIODevice, Qt  # noqa: E402
from PyQt6.QtGui import QColor  # noqa: E402

APP_VERSION = '1.02'

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

        top.addSpacing(10)
        self.status_label = QLabel('Connect the board to begin.')
        top.addWidget(self.status_label, stretch=1)

        root.addLayout(top)

        # Content row: config left, results right
        content = QHBoxLayout()
        content.setSpacing(8)

        # Config panel
        cfg_box = QGroupBox('Configuration')
        cfg_box.setFixedWidth(280)
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

            # Crossed — linear interpolation between previous and current reading
            if (self._prev_uV is not None
                    and self._prev_uV > target_uV
                    and self._prev_uV != mean_uV):
                frac = (self._prev_uV - target_uV) / (self._prev_uV - mean_uV)
                interp = self._prev_delay + frac * (self._delay - self._prev_delay)
            else:
                interp = self._delay   # first step already at or below threshold

            self._fill_cell(self._pair_idx, self._thresh_idx,
                            f'{interp:.2f}', color=_COL_DONE)
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
        self.progress_label.setText('Calibration complete.')
        self.status_label.setText('Done — use Export CSV to save results.')
        self.statusBar().showMessage('Calibration complete.')

    def stop_calibration(self):
        self._state = 'idle'
        if self.serial.isOpen():
            self.send_command('E')
        self.pb_run.setEnabled(self.serial.isOpen())
        self.pb_stop.setEnabled(False)
        self.pb_export.setEnabled(self.table.rowCount() > 0)
        self.progress_label.setText('Stopped.')
        self.status_label.setText('Sweep stopped.')

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
        if self.serial.isOpen():
            self.send_command('E')
            self.serial.waitForBytesWritten(200)
            self.serial.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1050, 620)
    window.show()
    sys.exit(app.exec())
