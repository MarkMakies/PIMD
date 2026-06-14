###############################################################################
# Pulse Induction Metal Detector, v3.01, coil v4
# Runs on Ubuntu desktop / laptop
#
# 204a  added std dev
# 204b adding rolling slope plot
# 204c display command at bottom as well
# 204d addidng slope and stddev to status bar
# 301 ready for field testing
# 302 few small fixes, less chart points, no std dev/slope on charts
#     to fix delays at 25kHz, max SPS about 40

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import sys
import time
import math
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtSerialPort import QSerialPort
from PyQt6.QtCore import QIODevice, QTimer, QPointF, Qt
from PyQt6.QtGui import QPen, QColor, QShortcut, QKeySequence
from PyQt6.QtCharts import QChart, QLineSeries, QValueAxis

from pimd111_ui import Ui_MainWindow  # This is your auto-generated UI file

# Constants for standard deviation calculation and display
NUMBER_STDDEV_POINTS = 100       # Number of recent voltage points used to compute stddev
STDDEV_MAX_SCALE = 1000          # Maximum stddev scale in microvolts (uV)
SLOPE_COUNT = 100               # Rolling average slope count (derivative)

class MainWindow(QMainWindow):
    # Color constants for button styling
    MY_GREEN = 'background-color: rgb(143, 240, 164);'
    MY_YELLOW = 'background-color: rgb(249, 240, 107);'
    MY_RED = 'background-color: rgb(246, 97, 81);'
    MY_BROWN = 'background-color: rgb(165, 42, 42);'

    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Pulse Induction Metal Detector v3.02 by Mark Makies')
        
        #self.showFullScreen()  ##MM Added to start in full-screen mode

        # Serial port and file handle
        self.serial = QSerialPort()
        self.file = None

        self.update_delays = []  # Stores last 10 inter-packet times
        self.last_packet_time = None  # Last received packet timestamp
        self.update_delay = 0  # Averaged delay between packets

        # New attribute to store the last command sent
        self.last_command = ""
        # New attribute to store the last incoming packet
        self.last_packet = ""

        # Raw-path boxcar-average ('R' record) - latest values for status bar
        self.raw_value_uV = None
        self.raw_stddev_uV = None
        self.raw_x = None

        # Periodic poll for a raw-path averaged sample while running
        self.raw_poll_timer = QTimer()
        self.raw_poll_timer.timeout.connect(self.poll_raw_average)

        # Measurement parameters (defaults)
        self.frequency = 25.0        # in kHz (displayed as x/10 slider value)
        self.pulse_width = 10.0      # in µs
        self.sample_delay = 7.4      # in µs
        self.down_sample = 1024       # down-sample factor for decimation filter

        # Chart scaling parameters
        self.v_scale = 5000
        self.vert_scales = { -2: 500, -3: 100, -4: 50, -5: 20, -6: 10,
                             -7: 5, -8: 2, -9: 1, -10: 0.5, -11: 0.2,
                             -12: 0.1, -13: 0.05, -14: 0.02, -15: 0.01 }
        self.h_scale = 180
        self.horiz_scales = { -2: 180, -3: 120, -4: 60, -5: 30, -6: 12, -7: 6 }

        # Chart objects
        self.chart = None
        self.series_v = None
        self.series_stddev = None  # New series for calculated stddev
        self.axis_x = None
        self.axis_y = None
        self.axis_t = None
        self.axis_z = None
        self.axis_stddev = None  # New axis for stddev
        self.series_stddev_slope = None #series for rolling average slope (derivative)

        # Vertical scale update flag and current Y range (for voltage)
        self.update_vert_scale = True
        self.cur_min = 0
        self.cur_max = 5000

        # Buffer to hold the last NUMBER_STDDEV_POINTS voltage values (in µV) for stddev calculation
        self.voltage_buffer = []
        ## buffer to hold raw voltage with timestamps for slope calculation over SLOPE_COUNT points
        self.voltage_ts_buffer = []

        # Setup UI connections and shortcuts
        self._setup_shortcuts()  # Set up keyboard shortcuts.
        self._setup_ui_connections()  # Connect UI widget signals to instance methods.

        # Connect serial ready signal
        self.serial.readyRead.connect(self.read_from_serial)

        # One-shot timer to allow UI to settle before initialization
        QTimer.singleShot(10, self.my_init)

    def _setup_shortcuts(self):
        # Set up keyboard shortcuts.

        scF11 = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        scF11.activated.connect(self.toggleFullScreen)

        # Connect
        sc_ent = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        sc_ent.activated.connect(self.connect_port)

        # Start/Stop
        sc_sp = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        #sc_sp.activated.connect(self.ui.pbStart.animateClick)
        sc_sp.activated.connect(self.start_stop)

        # Reset chart vertical scale
        sc_esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        sc_esc.activated.connect(self.reset_chart)

        # Clear chart data
        sc_del = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        sc_del.activated.connect(self.clear_chart)

        # Preselect functions
        sc_f1 = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        sc_f1.activated.connect(self.f1)
        sc_f2 = QShortcut(QKeySequence(Qt.Key.Key_F2), self)
        sc_f2.activated.connect(self.f2)
        sc_f3 = QShortcut(QKeySequence(Qt.Key.Key_F3), self)
        sc_f3.activated.connect(self.f3)
        sc_f4 = QShortcut(QKeySequence(Qt.Key.Key_F4), self)
        sc_f4.activated.connect(self.f4)
        sc_f12 = QShortcut(QKeySequence(Qt.Key.Key_F12), self)
        sc_f12.activated.connect(self.quit_app)

        # Frequency selector shortcuts
        sc_e = QShortcut(QKeySequence(Qt.Key.Key_E), self)
        sc_e.activated.connect(self.ui.pbFreqUp.animateClick)
        sc_w = QShortcut(QKeySequence(Qt.Key.Key_W), self)
        sc_w.activated.connect(self.ui.pbFreqDown.animateClick)
        sc_r = QShortcut(QKeySequence(Qt.Key.Key_R), self)
        sc_r.activated.connect(lambda: (self.ui.slFreq.setValue(self.ui.slFreq.value() + 10), self.change_parameters()))
        sc_q = QShortcut(QKeySequence(Qt.Key.Key_Q), self)
        sc_q.activated.connect(lambda: (self.ui.slFreq.setValue(self.ui.slFreq.value() - 10), self.change_parameters()))

        # Pulse width selector shortcuts
        sc_d = QShortcut(QKeySequence(Qt.Key.Key_D), self)
        sc_d.activated.connect(self.ui.pbPulseUp.animateClick)
        sc_s = QShortcut(QKeySequence(Qt.Key.Key_S), self)
        sc_s.activated.connect(self.ui.pbPulseDown.animateClick)
        sc_f = QShortcut(QKeySequence(Qt.Key.Key_F), self)
        sc_f.activated.connect(lambda: (self.ui.slPulse.setValue(self.ui.slPulse.value() + 10), self.change_parameters()))
        sc_a = QShortcut(QKeySequence(Qt.Key.Key_A), self)
        sc_a.activated.connect(lambda: (self.ui.slPulse.setValue(self.ui.slPulse.value() - 10), self.change_parameters()))

        # Sample delay selector shortcuts
        sc_c = QShortcut(QKeySequence(Qt.Key.Key_C), self)
        sc_c.activated.connect(self.ui.pbSampleUp.animateClick)
        sc_x = QShortcut(QKeySequence(Qt.Key.Key_X), self)
        sc_x.activated.connect(self.ui.pbSampleDown.animateClick)
        sc_v = QShortcut(QKeySequence(Qt.Key.Key_V), self)
        sc_v.activated.connect(lambda: (self.ui.slSample.setValue(self.ui.slSample.value() + 10), self.change_parameters()))
        sc_z = QShortcut(QKeySequence(Qt.Key.Key_Z), self)
        sc_z.activated.connect(lambda: (self.ui.slSample.setValue(self.ui.slSample.value() - 10), self.change_parameters()))

        # Up/Down for vertical scale adjustment
        sc_up = QShortcut(QKeySequence(Qt.Key.Key_Up), self)
        sc_up.activated.connect(lambda: self.v_div('up'))
        sc_down = QShortcut(QKeySequence(Qt.Key.Key_Down), self)
        sc_down.activated.connect(lambda: self.v_div('down'))
        # Left/Right for horizontal scale adjustment
        sc_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        sc_right.activated.connect(lambda: self.h_div('up'))
        sc_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        sc_left.activated.connect(lambda: self.h_div('down'))

    def toggleFullScreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _setup_ui_connections(self):
        # Connect UI widget signals to instance methods.
        # Buttons
        self.ui.pbConnect.clicked.connect(self.connect_port)
        self.ui.pbStart.clicked.connect(self.start_stop)
        self.ui.pbReset.clicked.connect(self.reset_chart)
        self.ui.pbClear.clicked.connect(self.clear_chart)
        self.ui.pbFactor.clicked.connect(self.set_factor)

        # Frequency slider and buttons
        self.ui.pbFreqUp.clicked.connect(lambda: self.ui.slFreq.setValue(self.ui.slFreq.value() + 1))
        self.ui.pbFreqUp.clicked.connect(self.change_parameters)
        self.ui.pbFreqDown.clicked.connect(lambda: self.ui.slFreq.setValue(self.ui.slFreq.value() - 1))
        self.ui.pbFreqDown.clicked.connect(self.change_parameters)
        self.ui.slFreq.sliderReleased.connect(self.change_parameters)
        self.ui.slFreq.valueChanged.connect(
            lambda value: self.ui.lFreq.setText('{:2.1f} kHz'.format(value / 10))
        )

        # Pulse width slider and buttons
        self.ui.pbPulseUp.clicked.connect(lambda: self.ui.slPulse.setValue(self.ui.slPulse.value() + 1))
        self.ui.pbPulseUp.clicked.connect(self.change_parameters)
        self.ui.pbPulseDown.clicked.connect(lambda: self.ui.slPulse.setValue(self.ui.slPulse.value() - 1))
        self.ui.pbPulseDown.clicked.connect(self.change_parameters)
        self.ui.slPulse.sliderReleased.connect(self.change_parameters)
        self.ui.slPulse.valueChanged.connect(
            lambda value: self.ui.lPulse.setText('{:2.1f} us'.format(value / 10))
        )

        # Sample delay slider and buttons
        self.ui.pbSampleUp.clicked.connect(lambda: self.ui.slSample.setValue(self.ui.slSample.value() + 1))
        self.ui.pbSampleUp.clicked.connect(self.change_parameters)
        self.ui.pbSampleDown.clicked.connect(lambda: self.ui.slSample.setValue(self.ui.slSample.value() - 1))
        self.ui.pbSampleDown.clicked.connect(self.change_parameters)
        self.ui.slSample.sliderReleased.connect(self.change_parameters)
        self.ui.slSample.valueChanged.connect(
            lambda value: self.ui.lSample.setText('{:2.1f} us'.format(value / 10))
        )

        # Button groups for vertical and horizontal scale changes
        self.ui.VoltageButtonGroup.buttonToggled.connect(self.vert_scale)
        self.ui.TimeButtonGroup.buttonToggled.connect(self.horiz_scale)

    def set_factor(self):
        toggle_map = {'256': '1024', '1024': '256'}
        current_text = self.ui.pbFactor.text()
        
        if current_text in toggle_map:
            new_text = toggle_map[current_text]
            self.ui.pbFactor.setText(new_text)
            self.down_sample = int(new_text)
        self.change_parameters()

    def setup_file_logging(self):
        """
        Creates a timestamped filename and opens it for logging.
        Can be called from multiple places.
        """
        now = datetime.now()
        fname = 'data/' + now.strftime('P%d%m-%H%M%S.csv')
        self.ui.leFileName.setText(fname)  # Update UI field with filename
        self.file = open(fname, 'a')  # Open file in append mode

    def my_init(self):
        """
        Initialization routine run after the UI has loaded.
        """
        # Set labels with arrow symbols
        self.ui.label_10.setText(' ' + '\u2bc5' + '   ' + '\u2bc6' + ' ')
        self.ui.label_13.setText(' ' + '\u2bc7' + '   ' + '\u2bc8' + ' ')

        self.setup_file_logging()  # Call function to handle file creation

        self.create_chart()
        self.connect_port()
        self.send_command('E')

    def connect_port(self):
        # Open or close the serial port based on the current state.
        if self.ui.pbConnect.text() != 'Connected':
            if self.serial_open(True):
                self.ui.pbConnect.setText('Connected')
                self.ui.pbConnect.setStyleSheet(self.MY_GREEN)
            else:
                self.ui.pbConnect.setText('Port Error')
                self.ui.pbConnect.setStyleSheet(self.MY_RED)
        else:
            self.serial_open(False)
            self.ui.pbConnect.setText('Not Connected')
            self.ui.pbConnect.setStyleSheet(self.MY_YELLOW)

    def start_stop(self):
        # Start or stop measurement.
        if self.ui.pbStart.text() != 'Running':
            self.ui.pbStart.setText('Running')
            self.ui.pbStart.setStyleSheet(self.MY_GREEN)

            self.setup_file_logging()  # Ensure a file is opened when starting
            self.send_command('S')
            self.change_parameters()
            self.raw_poll_timer.start(250)  # poll raw-path average (A32) at 4 Hz
        else:
            self.ui.pbStart.setText('Stopped')
            self.ui.pbStart.setStyleSheet(self.MY_YELLOW)
            self.send_command('E')
            self.raw_poll_timer.stop()
            if self.file:
                self.file.close()

    def poll_raw_average(self):
        # Request a boxcar-averaged raw-path sample (Task 2 'A<x>' primitive,
        # returns a new 'R...' record - does not affect the legacy '*' telemetry).
        if self.serial.isOpen():
            self.serial.write(b'A32\n')

    def v_div(self, direction):
        # Adjust vertical division scale via button group.
        ix = self.ui.VoltageButtonGroup.checkedId()
        ix = ix + 1 if direction == 'up' else ix - 1
        # Clamp the value between -15 and -2
        ix = max(-15, min(-2, ix))
        self.ui.VoltageButtonGroup.button(ix).setChecked(True)

    def h_div(self, direction):
        # Adjust horizontal division scale via button group.
        ix = self.ui.TimeButtonGroup.checkedId()
        ix = ix + 1 if direction == 'up' else ix - 1
        # Clamp the value between -7 and -2
        ix = max(-7, min(-2, ix))
        self.ui.TimeButtonGroup.button(ix).setChecked(True)

    def f1(self):
        # Preset configuration F1.
        self.ui.slFreq.setValue(250)
        self.ui.slPulse.setValue(100)
        self.ui.slSample.setValue(76)
        self.ui.pbFactor.setText('1024')
        self.down_sample = 1024
        self.change_parameters()

    def f2(self):
        # Preset configuration F2.
        self.ui.slFreq.setValue(96)
        self.ui.slPulse.setValue(200)
        self.ui.slSample.setValue(80)
        self.ui.pbFactor.setText('256')
        self.down_sample = 256
        self.change_parameters()

    def f3(self):
        # Preset configuration F3.
        self.ui.slFreq.setValue(61)
        self.ui.slPulse.setValue(300)
        self.ui.slSample.setValue(83)
        self.ui.pbFactor.setText('256')
        self.down_sample = 256
        self.change_parameters()

    def f4(self):
        # Preset configuration F4.
        self.ui.slFreq.setValue(49)
        self.ui.slPulse.setValue(400)
        self.ui.slSample.setValue(85)
        self.ui.pbFactor.setText('256')
        self.down_sample = 256
        self.change_parameters()

    def change_parameters(self):
        # Read the current slider values, update parameters, and send the configuration command via serial.
        self.frequency = self.ui.slFreq.value() / 10
        self.pulse_width = self.ui.slPulse.value() / 10
        self.sample_delay = self.ui.slSample.value() / 10
        command_str = (
            '*' 
            + str(self.frequency) + ', '
            + str(self.pulse_width) + ', '
            + str(self.sample_delay) + ', '
            + str(self.down_sample) )
        self.send_command(command_str)

    def serial_open(self, flag):
        # Open (if flag is True) or close the serial port.
        # Returns True if successful.
        if flag:
            self.serial.setPortName('ttyACM0')  # Adjust for your platform (e.g., 'COM4' on Windows)
            self.serial.setBaudRate(115200)
            self.serial.setDataBits(QSerialPort.DataBits.Data8)
            self.serial.setParity(QSerialPort.Parity.NoParity)
            self.serial.setStopBits(QSerialPort.StopBits.OneStop)
            self.serial.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
            if not self.serial.open(QIODevice.OpenModeFlag.ReadWrite):
                print('PORT ERROR')
                return False
            else:
                print('PORT OPEN')
                return True
        else:
            self.serial.close()
            print('PORT CLOSED')
            return True

    def read_from_serial(self):
        # Read an incoming line from the serial port and process it.
        data = self.serial.readLine().data().decode('utf-8').rstrip()
        if data:
            self.process_packet(data)

    def process_packet(self, line):
        REFERENCE_VOLTAGE = 5  # Volts
        self.last_packet = line  ## MM: store the current packet in an instance attribute
        
        if line.startswith('*'):
            line = line[1:]
            try:
                if self.file:
                    self.file.write(line + '\n')
            except Exception as e:
                print('File write error, probably last packet after stop:', e)

            parts = line.split(',')
            try:
                p_timestamp = int(parts[0])
                p_voltage = int(parts[1])
                p_stddev = int(parts[2])
                p_frequency = int(float(parts[3]) * 1000)
                p_pulse_width = float(parts[4])
                p_sample_delay = float(parts[5])
            except Exception as e:
                print('Packet parsing error:', e)
                return

            # Calculate inter-packet delay and update rolling average
            current_time = time.time() * 1000  # Convert to ms
            if self.last_packet_time is not None:
                delay = current_time - self.last_packet_time
                self.update_delays.append(delay)
                if len(self.update_delays) > 100:
                    self.update_delays.pop(0)
                self.update_delay = sum(self.update_delays) / len(self.update_delays)
            self.last_packet_time = current_time

            self.ui.dialV.setValue(int(p_voltage))
            if p_voltage < 2.1 * 1_000_000:
                self.ui.luV.setStyleSheet(self.MY_YELLOW)
            elif p_voltage > 3.5 * 1_000_000:
                self.ui.luV.setStyleSheet(self.MY_RED)
            else:
                self.ui.luV.setStyleSheet(self.MY_GREEN)

            self.ui.luV.setText('{:9,.0f} mV '.format(p_voltage / 1000))
            self.ui.luVsd.setText('{:12,d} uV '.format(p_stddev))
            
            self.update_uv_chart(p_timestamp, p_voltage)

            # Update the voltage buffer for stddev calculation
            self.voltage_buffer.append((p_timestamp/1000, p_voltage))
            if len(self.voltage_buffer) > NUMBER_STDDEV_POINTS:
                self.voltage_buffer.pop(0)
            
            # Update the raw voltage buffer for slope calculation
            self.voltage_ts_buffer.append((p_timestamp/1000, p_voltage))
            if len(self.voltage_ts_buffer) > SLOPE_COUNT:
                self.voltage_ts_buffer.pop(0)
            
            # Compute and update the calculated stddev series (and slope series)
            self.update_stddev_chart(p_timestamp)

        elif line.startswith('R'):
            # Raw-path boxcar-average record: R<time_ms>,<value_uV>,<stddev_uV>,<x>,<freq_kHz>,<pulse_us>,<delay_us>
            parts = line[1:].split(',')
            try:
                self.raw_value_uV = int(parts[1])
                self.raw_stddev_uV = int(parts[2])
                self.raw_x = int(parts[3])
            except Exception as e:
                print('Raw packet parsing error:', e)

    def create_chart(self):
        # Set up the chart and associated axes.
        self.chart = QChart()
        self.chart.legend().setVisible(False)

        # Voltage series (blue)
        self.series_v = QLineSeries()
        pen = QPen()
        pen.setWidth(1)
        pen.setColor(QColor('blue'))
        self.series_v.setPen(pen)
        self.chart.addSeries(self.series_v)

        # X axis (timestamp, not visible)
        self.axis_x = QValueAxis()
        self.axis_x.setTickCount(7)
        self.axis_x.setVisible(False)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignTop)
        self.series_v.attachAxis(self.axis_x)

        # Y axis (voltage, not visible)
        self.axis_y = QValueAxis()
        self.axis_y.setTickCount(6)
        self.axis_y.setVisible(False)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.series_v.attachAxis(self.axis_y)

        # T axis for relative time (visible)
        self.axis_t = QValueAxis()
        self.axis_t.setTickCount(7)
        self.axis_t.setRange(-180, 0)
        self.chart.addAxis(self.axis_t, Qt.AlignmentFlag.AlignBottom)

        # Z axis for relative voltage (visible)
        self.axis_z = QValueAxis()
        self.axis_z.setTickCount(11)
        self.axis_z.setRange(0, 5)
        self.chart.addAxis(self.axis_z, Qt.AlignmentFlag.AlignRight)
        self.axis_z.setGridLineColor(QColor("blue"))
        self.axis_z.setLabelsColor(QColor("blue"))

        # Create the stddev series (red)
        self.series_stddev = QLineSeries()
        pen_stddev = QPen(QColor('red'))
        pen_stddev.setWidth(1)
        self.series_stddev.setPen(pen_stddev)
        self.chart.addSeries(self.series_stddev)

        # Create a separate axis for stddev (displayed on the right)
        self.axis_stddev = QValueAxis()
        self.axis_stddev.setTickCount(11)
        self.axis_stddev.setRange(0, STDDEV_MAX_SCALE)  # Fixed range: 0 to 1000 µV
        self.chart.addAxis(self.axis_stddev, Qt.AlignmentFlag.AlignRight)
        self.series_stddev.attachAxis(self.axis_stddev)
        self.series_stddev.attachAxis(self.axis_x)
        #self.axis_stddev.setGridLineColor(QColor("red"))
        self.axis_stddev.setLabelsColor(QColor("red"))
        
        # Create the rolling average slope series (green) over SLOPE_COUNT points ## MM:
        self.series_stddev_slope = QLineSeries()
        pen_slope = QPen(QColor('green'))
        pen_slope.setWidth(1)
        self.series_stddev_slope.setPen(pen_slope)
        self.chart.addSeries(self.series_stddev_slope)
        self.series_stddev_slope.attachAxis(self.axis_stddev)
        self.series_stddev_slope.attachAxis(self.axis_x)

        self.ui.ChartView1.setChart(self.chart)
        self.ui.ChartView1.show()

    def update_uv_chart(self, timestamp, voltage):
        # Update the chart with a new data point.
        # timestamp: integer (ms), voltage: integer (µV)
        # Append new point (convert timestamp to seconds and voltage to mV)
        self.series_v.append(QPointF(timestamp / 1000, voltage / 1000))
        if self.series_v.count() > 5000:
            self.series_v.removePoints(0, 100)

        # Update X axis (time)
        last_timestamp = self.series_v.at(self.series_v.count() - 1).x()
        self.axis_x.setMax(last_timestamp)
        self.axis_x.setMin(self.axis_x.max() - self.h_scale)

        # Update Y axis (voltage) if needed
        last_voltage = self.series_v.at(self.series_v.count() - 1).y()
        margin = 0.1 * (self.cur_max - self.cur_min)
        if (last_voltage > self.cur_max - margin) or (last_voltage < self.cur_min + margin) or self.update_vert_scale:
            if self.v_scale == 5000:
                y_min, y_max = 0, 5000
            else:
                y_min = max(0, last_voltage - (self.v_scale / 2))
                y_max = y_min + self.v_scale
            self.axis_y.setRange(y_min, y_max)
            self.cur_min, self.cur_max = y_min, y_max
            self.update_vert_scale = False
        else:
            self.axis_y.setRange(self.cur_min, self.cur_max)

    def update_stddev_chart(self, timestamp):
        # Compute the standard deviation from the voltage_buffer (values in µV)
        if len(self.voltage_buffer) < 2:
            computed_stddev = 0
        else:
            values = [v for (t, v) in self.voltage_buffer]  # extract voltage values from tuples
            mean_val = sum(values) / len(values)
            variance = sum((x - mean_val) ** 2 for x in values) / len(values)
            computed_stddev = math.sqrt(variance)
        # Append the computed stddev (in µV) to the stddev series
        #MM self.series_stddev.append(QPointF(timestamp / 1000, computed_stddev))
        #if self.series_stddev.count() > 5000:
        #    self.series_stddev.removePoints(0, 1)
        # The stddev axis range remains fixed at 0 to STDDEV_MAX_SCALE

        # Compute rolling slope from raw voltage using SLOPE_COUNT points from voltage_ts_buffer
        slope = 0
        if len(self.voltage_ts_buffer) >= SLOPE_COUNT:
            first_time, first_voltage = self.voltage_ts_buffer[0]
            last_time, last_voltage = self.voltage_ts_buffer[-1]
            if last_time - first_time != 0:
                slope = (last_voltage - first_voltage) / (last_time - first_time)
            else:
                slope = 0
            #MM self.series_stddev_slope.append(QPointF(timestamp / 1000, abs(slope)))
            #if self.series_stddev_slope.count() > 5000:
            #    self.series_stddev_slope.removePoints(0, 1)
        # Update the status bar to include computed stddev and slope

        if self.update_delay > 0:
            freq = (1 / (self.update_delay /1000)) * int(self.ui.pbFactor.text()) / 1000
            SPS = 1 / (self.update_delay /1000)
        else:
            freq = 0
            SPS = 0

        if self.raw_value_uV is not None:
            raw_status = (f"Raw avg: {self.raw_value_uV:>9,d} uV, "
                           f"sd: {self.raw_stddev_uV:>6,d} uV (x{self.raw_x}) | ")
        else:
            raw_status = "Raw avg: -- | "

        self.ui.statusBar.showMessage(
                f"Last command: {self.last_command:<20} | "
                f"Incoming packet: {self.last_packet:<60} | "
                f"std dev: {computed_stddev:>6.0f} uV | "
                f"{raw_status}"
                f"Rx freq: {freq:>4.1f} kHz | "
                f"SPS: {SPS:>4.1f} "
            )

    def vert_scale(self):
        # Called when the vertical scale button group changes.
        i = self.ui.VoltageButtonGroup.checkedId()
        self.v_scale = self.vert_scales[i] * 10
        if self.v_scale == 5000:
            self.axis_z.setRange(0, 5)
            self.ui.uVlabel.setText('V / div')
        elif self.v_scale <= 5:
            self.axis_z.setRange(-self.v_scale / 2 * 1000, self.v_scale / 2 * 1000)
            self.ui.uVlabel.setText('uV / div')
        else:
            self.axis_z.setRange(-self.v_scale / 2, self.v_scale / 2)
            self.ui.uVlabel.setText('mV / div')
        self.update_vert_scale = True

    def horiz_scale(self):
        # Called when the horizontal scale button group changes.
        i = self.ui.TimeButtonGroup.checkedId()
        self.h_scale = self.horiz_scales[i]
        self.axis_t.setRange(-self.h_scale, 0)

    def reset_chart(self):
        # Reset the chart vertical scaling.
        self.update_vert_scale = True

    def clear_chart(self):
        # Clear the chart data.
        self.series_v.clear()
        self.series_stddev.clear()
        self.series_stddev_slope.clear()  ## MM: clear the slope series as well
        self.voltage_buffer.clear()
        self.voltage_ts_buffer.clear()

    def send_command(self, text):
        # Send a command string to the device over serial.
        full_text = text + '\n'
        self.serial.write(full_text.encode())
        # Update the last command sent
        self.last_command = text

    def exit_handler(self):
        # Handle application exit.
        print('Exiting...')
        if self.file:
            self.file.close()

    def quit_app(self):
        # Quit the application.
        QApplication.instance().exit()


if __name__ == '__main__':
    app = QApplication([])
    # Connect the exit handler
    app.aboutToQuit.connect(lambda: window.exit_handler() if (window := getattr(sys.modules[__name__], 'window', None)) else None)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
