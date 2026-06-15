###############################################################################
# PIMD Scope-Cal Visualiser
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# Polls scan Profile 2 (SCOPE_CAL, fw v3.03+: 5 kHz, 10us pulse, 8 log-spaced
# sample delays, x=1) via the P2/M2 commands and plots all 8 delay-channel
# readings live, one auto-scaling subplot per delay, so the live data can be
# correlated against an oscilloscope trace of the TX pulse / sample trigger.
#
# v0.1 initial version
###############################################################################

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import os
import sys
import time
from collections import deque

os.environ.setdefault('QT_API', 'pyqt6')  # must be set before importing the matplotlib Qt backend below

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel,
)
from PyQt6.QtSerialPort import QSerialPort  # noqa: E402
from PyQt6.QtCore import QIODevice, QTimer  # noqa: E402

from matplotlib.figure import Figure  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402

NUM_CHANNELS = 8
POLL_INTERVAL_MS = 250
HISTORY_POINTS = 240  # ~60s of history at 250ms/poll


class MainWindow(QMainWindow):
    MY_GREEN = 'background-color: rgb(143, 240, 164);'
    MY_YELLOW = 'background-color: rgb(249, 240, 107);'
    MY_RED = 'background-color: rgb(246, 97, 81);'

    def __init__(self):
        super().__init__()
        self.setWindowTitle('PIMD Scope-Cal Visualiser v0.1')

        self.serial = QSerialPort()
        self.serial.readyRead.connect(self.read_from_serial)

        self.last_command = ''
        self.last_packet = ''

        self.delays_us = None
        self.pulse_us = None
        self.freq_khz = None
        self.start_time = None

        self.data = [deque(maxlen=HISTORY_POINTS) for _ in range(NUM_CHANNELS)]

        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_profile)

        self._build_ui()

        QTimer.singleShot(10, self.connect_port)

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

        self.header_label = QLabel('Profile 2 SCOPE_CAL: waiting for first reply...')
        top_bar.addWidget(self.header_label, stretch=1)

        layout.addLayout(top_bar)

        self.figure = Figure(figsize=(8, 14), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas)

        self.axes = self.figure.subplots(NUM_CHANNELS, 1, sharex=True)
        self.lines = []
        for ax in self.axes:
            (line,) = ax.plot([], [], color='blue', linewidth=1)
            self.lines.append(line)
            ax.set_ylabel('uV')
            ax.label_outer()  # hide x tick labels on all but the bottom subplot
        self.axes[-1].set_xlabel('time (s)')

        self.setCentralWidget(central)
        self.statusBar().showMessage('Not connected')

    # ------------------------------------------------------------------
    # Serial connection
    # ------------------------------------------------------------------
    def connect_port(self):
        if self.pb_connect.text() != 'Connected':
            if self.serial_open(True):
                self.pb_connect.setText('Connected')
                self.pb_connect.setStyleSheet(self.MY_GREEN)
                self.send_command('E')  # stop any running '*' telemetry
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
            data = self.serial.readLine().data().decode('utf-8', errors='replace').rstrip()
            if data:
                self.process_packet(data)

    def send_command(self, text):
        self.serial.write((text + '\n').encode())
        self.last_command = text

    # ------------------------------------------------------------------
    # Start/stop polling
    # ------------------------------------------------------------------
    def start_stop(self, force_stop=False):
        if force_stop or self.pb_start.text() == 'Running':
            self.pb_start.setText('Stopped')
            self.pb_start.setStyleSheet(self.MY_YELLOW)
            self.poll_timer.stop()
        else:
            if not self.serial.isOpen():
                return
            self.pb_start.setText('Running')
            self.pb_start.setStyleSheet(self.MY_GREEN)
            self.start_time = time.time()
            for d in self.data:
                d.clear()
            self.poll_timer.start(POLL_INTERVAL_MS)

    def poll_profile(self):
        self.send_command('P2')

    # ------------------------------------------------------------------
    # Packet handling
    # ------------------------------------------------------------------
    def process_packet(self, line):
        self.last_packet = line

        if line.startswith('M2,'):
            parts = line.split(',')
            try:
                freq_khz = float(parts[2])
                y = int(parts[4])
                pulse_us = float(parts[5])
                delays = [float(v) for v in parts[6:6 + y]]
                pairs = parts[6 + y:]
                means = [int(pairs[2 * i]) for i in range(y)]
            except (ValueError, IndexError) as e:
                self.statusBar().showMessage('M2 parse error: {0}'.format(e))
                return

            if self.delays_us is None:
                self.delays_us = delays
                self.pulse_us = pulse_us
                self.freq_khz = freq_khz
                self._apply_header()

            t = time.time() - self.start_time
            for i, mean_uV in enumerate(means):
                self.data[i].append((t, mean_uV))
            self.update_chart()

        self._update_status()

    def _apply_header(self):
        self.header_label.setText(
            'Profile 2 SCOPE_CAL: {0:.1f} kHz, pulse={1:.1f}us, delays={2}us'.format(
                self.freq_khz, self.pulse_us, self.delays_us))
        for ax, delay in zip(self.axes, self.delays_us):
            ax.set_title('delay={0:.1f}us'.format(delay), fontsize=9)

    def update_chart(self):
        for i, line in enumerate(self.lines):
            pts = self.data[i]
            if pts:
                ts, vs = zip(*pts)
                line.set_data(ts, vs)
                self.axes[i].relim()
                self.axes[i].autoscale_view()
        self.canvas.draw_idle()

    def _update_status(self):
        self.statusBar().showMessage(
            'Last command: {0:<6} | Last packet: {1}'.format(self.last_command, self.last_packet))

    def closeEvent(self, event):
        self.poll_timer.stop()
        if self.serial.isOpen():
            self.send_command('E')
            self.serial.waitForBytesWritten(100)
            self.serial.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.resize(900, 1000)
    window.show()
    sys.exit(app.exec())
