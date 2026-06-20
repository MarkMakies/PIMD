###############################################################################
# PIMD Scope v4.02
# — Mode 2 streaming visualiser
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# Connects to the board, sends Q<n>/G to start Mode 2 streaming, and plots
# one subplot per (pulse, delay) channel in the selected profile.
#
# Protocol: receives W<profile_idx>,<time_ms>,<mean_ch0>,<mean_ch1>,...
# Board firmware: pimd_mcu.py v4.00+
#
# v4.02 title standardised to include author.
# v4.01 PROFILES_META converted to bands format; _update_titles updated for
#       multi-freq profiles; profile 4 CLASSIFY_EP added (5 bands × 9 cells)
# v4.00 initial version (replaces pimd_scope_cal.py poll-based approach)
###############################################################################

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import os
import sys
import time
from collections import deque

os.environ.setdefault('QT_API', 'pyqt6')

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSpinBox,
)
from PyQt6.QtSerialPort import QSerialPort  # noqa: E402
from PyQt6.QtCore import QIODevice  # noqa: E402

from matplotlib.figure import Figure  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402

HISTORY_POINTS = 240   # ~60 s at 4 Hz display refresh
DEFAULT_PROFILE = 3
DEFAULT_SPAN_MV = 50

# Local mirror of firmware's PROFILES table — update here when PROFILES changes.
# Each band entry: (freq_khz, pulse_us, delays_us)
PROFILES_META = {
    0: {'name': 'FAST_TRACK',  'bands': (
            (5.0,   40.0, (8.4,)),
        )},
    1: {'name': 'CLASSIFY',    'bands': (
            (10.0,  8.0, (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0)),
            (10.0, 20.0, (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0)),
            (10.0, 40.0, (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0)),
        )},
    2: {'name': 'SCOPE_CAL',   'bands': (
            (5.0,  10.0, (5.0, 6.7, 9.0, 12.1, 16.3, 22.0, 29.7, 40.0)),
        )},
    3: {'name': 'TRACK_25K',   'bands': (
            (25.0, 10.0, (7.6,)),
        )},
    4: {'name': 'CLASSIFY_EP', 'bands': (
            (10.6, 40.0, ( 8.56,  8.98,  9.37,  9.72, 10.08, 10.49, 10.96, 11.57, 12.53)),
            (17.6, 30.0, ( 8.12,  8.54,  8.92,  9.27,  9.63, 10.02, 10.50, 11.10, 12.03)),
            (29.2, 20.0, ( 7.62,  8.03,  8.40,  8.75,  9.11,  9.50,  9.96, 10.55, 11.46)),
            (43.0, 10.0, ( 6.80,  7.22,  7.58,  7.93,  8.28,  8.66,  9.11,  9.70, 10.57)),
            (57.0,  5.0, ( 6.03,  6.43,  6.78,  7.12,  7.46,  7.84,  8.28,  8.85,  9.71)),
        )},
}


class MainWindow(QMainWindow):
    MY_GREEN = 'background-color: rgb(143, 240, 164);'
    MY_YELLOW = 'background-color: rgb(249, 240, 107);'
    MY_RED = 'background-color: rgb(246, 97, 81);'

    def __init__(self):
        super().__init__()
        self.setWindowTitle('PIMD Scope v4.02 by Mark Makies')

        self.serial = QSerialPort()
        self.serial.readyRead.connect(self.read_from_serial)

        self.last_command = ''
        self.last_packet = ''
        self.start_time = None

        self.axes = []
        self.lines = []
        self.data = []

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        layout = QVBoxLayout(central)

        top_bar = QHBoxLayout()

        self.pb_connect = QPushButton('Not Connected')
        self.pb_connect.setStyleSheet(self.MY_YELLOW)
        self.pb_connect.clicked.connect(self.connect_port)
        top_bar.addWidget(self.pb_connect)

        self.pb_start = QPushButton('Stopped')
        self.pb_start.setStyleSheet(self.MY_YELLOW)
        self.pb_start.clicked.connect(self.start_stop)
        top_bar.addWidget(self.pb_start)

        self.header_label = QLabel('waiting for first W record...')
        top_bar.addWidget(self.header_label, stretch=1)

        top_bar.addWidget(QLabel('Profile:'))
        self.profile_spin = QSpinBox()
        self.profile_spin.setRange(0, 9)
        self.profile_spin.setValue(DEFAULT_PROFILE)
        self.profile_spin.setPrefix('P')
        self.profile_spin.valueChanged.connect(self._on_profile_changed)
        top_bar.addWidget(self.profile_spin)

        top_bar.addWidget(QLabel('Span:'))
        self.span_spin = QSpinBox()
        self.span_spin.setRange(1, 2000)
        self.span_spin.setValue(DEFAULT_SPAN_MV)
        self.span_spin.setPrefix('+/- ')
        self.span_spin.setSuffix(' mV')
        self.span_spin.valueChanged.connect(self.update_chart)
        top_bar.addWidget(self.span_spin)

        layout.addLayout(top_bar)

        self.figure = Figure(figsize=(8, 14), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)

        self.setCentralWidget(central)
        self.statusBar().showMessage('Not connected')

    # ------------------------------------------------------------------
    # Serial
    # ------------------------------------------------------------------
    def connect_port(self):
        if self.pb_connect.text() != 'Connected':
            if self.serial_open(True):
                self.pb_connect.setText('Connected')
                self.pb_connect.setStyleSheet(self.MY_GREEN)
                self.send_command('E')
                self.send_command('Q{0}'.format(self.profile_spin.value()))
            else:
                self.pb_connect.setText('Port Error')
                self.pb_connect.setStyleSheet(self.MY_RED)
        else:
            self.start_stop(force_stop=True)
            self.serial_open(False)
            self.pb_connect.setText('Not Connected')
            self.pb_connect.setStyleSheet(self.MY_YELLOW)

    def serial_open(self, flag):
        if flag:
            self.serial.setPortName('ttyACM0')
            self.serial.setBaudRate(115200)
            self.serial.setDataBits(QSerialPort.DataBits.Data8)
            self.serial.setParity(QSerialPort.Parity.NoParity)
            self.serial.setStopBits(QSerialPort.StopBits.OneStop)
            self.serial.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
            return self.serial.open(QIODevice.OpenModeFlag.ReadWrite)
        else:
            self.serial.close()
            return True

    def read_from_serial(self):
        while self.serial.canReadLine():
            raw = self.serial.readLine().data().decode('utf-8', errors='replace').rstrip()
            if raw:
                self.process_packet(raw)

    def send_command(self, text):
        self.serial.write((text + '\n').encode())
        self.last_command = text

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------
    def start_stop(self, force_stop=False):
        if force_stop or self.pb_start.text() == 'Running':
            self.send_command('E')
            self.pb_start.setText('Stopped')
            self.pb_start.setStyleSheet(self.MY_YELLOW)
        else:
            if not self.serial.isOpen():
                return
            self.start_time = time.time()
            for d in self.data:
                d.clear()
            self.send_command('G')
            self.pb_start.setText('Running')
            self.pb_start.setStyleSheet(self.MY_GREEN)

    def _on_profile_changed(self, value):
        """Switch profile: stop current stream, select new profile, restart if running."""
        was_running = self.pb_start.text() == 'Running'
        if was_running:
            self.send_command('E')
            self.pb_start.setText('Stopped')
            self.pb_start.setStyleSheet(self.MY_YELLOW)
        self.send_command('Q{0}'.format(value))
        if was_running:
            self.start_time = time.time()
            for d in self.data:
                d.clear()
            self.send_command('G')
            self.pb_start.setText('Running')
            self.pb_start.setStyleSheet(self.MY_GREEN)

    # ------------------------------------------------------------------
    # Packet handling
    # ------------------------------------------------------------------
    def process_packet(self, line):
        self.last_packet = line

        if len(line) > 1 and line[0] == 'W' and line[1].isdigit():
            parts = line.split(',')
            try:
                w_idx = int(parts[0][1:])
                n = len(parts) - 2         # number of channels = len - W<idx> - time_ms
                means = [int(parts[2 + i]) for i in range(n)]
            except (ValueError, IndexError) as e:
                self.statusBar().showMessage('W parse error: {0}'.format(e))
                return

            if n != len(self.lines):
                self._rebuild_axes(w_idx, n)
            elif self.axes:
                self._update_titles(w_idx)

            if self.start_time is None:
                self.start_time = time.time()
            t = time.time() - self.start_time

            for i, mean_uV in enumerate(means):
                self.data[i].append((t, mean_uV))
            self.update_chart()

        self._update_status()

    def _rebuild_axes(self, w_idx, n):
        self.figure.clear()
        if n == 0:
            self.canvas.draw_idle()
            return
        rows = max(1, n)
        axes_arr = self.figure.subplots(rows, 1, sharex=True, squeeze=False)
        self.axes = [row[0] for row in axes_arr]
        self.lines = []
        self.data = [deque(maxlen=HISTORY_POINTS) for _ in range(n)]
        for ax in self.axes:
            (line,) = ax.plot([], [], color='blue', linewidth=1)
            self.lines.append(line)
            ax.set_ylabel('uV')
            ax.label_outer()
        self.axes[-1].set_xlabel('time (s)')
        self._update_titles(w_idx)

    def _update_titles(self, w_idx):
        meta = PROFILES_META.get(w_idx, {})
        name = meta.get('name', '?')
        bands = meta.get('bands', ())

        freqs = [b[0] for b in bands]
        if len(set(freqs)) == 1:
            freq_str = '{0:.1f} kHz'.format(freqs[0]) if bands else '?'
        else:
            freq_str = 'multi-freq'
        self.header_label.setText(
            'Profile {0} ({1}) — {2}'.format(w_idx, name, freq_str))

        multi_band = len(bands) > 1
        titles = []
        for freq_khz, pulse_us, delays_us in bands:
            for delay_us in delays_us:
                if multi_band:
                    titles.append('{0:.0f}kHz/{1:.0f}us d={2:.2f}us'.format(
                        freq_khz, pulse_us, delay_us))
                else:
                    titles.append('d={0:.2f}us'.format(delay_us))

        fontsize = 7 if len(titles) > 12 else 9
        for ax, title in zip(self.axes, titles):
            ax.set_title(title, fontsize=fontsize)

    def update_chart(self):
        span_uv = self.span_spin.value() * 1000
        for i, line in enumerate(self.lines):
            pts = self.data[i]
            if pts:
                ts, vs = zip(*pts)
                line.set_data(ts, vs)
                mean_v = sum(vs) / len(vs)
                self.axes[i].set_ylim(mean_v - span_uv, mean_v + span_uv)
                self.axes[i].relim()
                self.axes[i].autoscale_view(scalex=True, scaley=False)
        self.canvas.draw_idle()

    def _update_status(self):
        self.statusBar().showMessage(
            'Last cmd: {0:<8} | Last packet: {1}'.format(
                self.last_command, self.last_packet))

    def closeEvent(self, event):
        if self.serial.isOpen():
            self.send_command('E')
            self.serial.waitForBytesWritten(100)
            self.serial.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.resize(900, 900)
    window.show()
    sys.exit(app.exec())
