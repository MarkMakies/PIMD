###############################################################################
# Pulse Induction Metal Detector GUI — Mode 1 display
# Runs on Ubuntu desktop / laptop
#
# v4.06 chart corruption fix: trim series_v/series_raw_mean by x-axis range
#       (not by point count) so no off-screen polyline segment crosses the
#       visible area when the warmup spike scrolls off the left edge. Add
#       "Boxcar" toggle button (enables/disables A<n> polling + orange trace)
#       and move "Raw Avg" button to the bottom-left F1/F2/F3/F4 area (those
#       presets removed). Remove Raw σ button, series_stddev, axis_stddev,
#       series_stddev_slope and all related state; keep raw_stddev_uV footer.
# v4.05 clear series_raw_mean and series_stddev on Mode 1 start (S command),
#       not just on DEL/Clear or toggle-off. Stale data from a previous session
#       left phantom traces — polyline from old off-screen points to new ones
#       — visible as multiple overlapping orange plots on the chart.
# v4.07 remove range (min…max) from footer raw status string; fix horizontal
#       grid lines (axis_z) back to light gray (#cccccc, was blue).
# v4.04 extend R record parsing: pimd_mcu.py v4.15 appends min_uV and max_uV
#       to the R record (format: R<t>,<mean>,<std>,<n>,<freq>,<pulse>,<delay>,
#       <min>,<max>). Parse parts[7]/parts[8] defensively.
# v4.03 add two chart toggles to visualise the raw boxcar-average path (A<n>):
#       "Raw Avg" overlays raw_value_uV (orange) on the existing voltage axis
#       next to the filtered-path blue trace; "Raw sigma" plots raw_stddev_uV
#       on the existing (previously unused) red stddev series/axis, which now
#       auto-expands its range as larger values are seen (was a fixed 0-1000uV
#       range, too narrow for the std dev values now being investigated, up to
#       70,000uV). Both default off; DEL/Clear resets them along with the rest
#       of the chart.
# v4.02 startup now defaults to Standard Operating Conditions (see CHANGELOG.md):
#       10.0 kHz / 20.0 us pulse / 10.0 us delay / 256 decimation. Removed the
#       footer's "std dev: ... uV" entry — it duplicated the top-right Std Dev
#       box (both show the firmware's filtered-path p_stddev); the now-unused
#       voltage_buffer/computed_stddev machinery behind it was removed too.
#       poll_raw_average() now sends A<n> with n = min(down_sample, 1000)
#       instead of a hardcoded A32, so the raw-path boxcar average's noise
#       floor is comparable to the filtered path's decimation factor instead
#       of differing by ~8-32x just from oversampling-count mismatch.
# v4.01 added editable port field (mirrors pimd_classviz.py) — was hardcoded to
#       'ttyACM0'; serial_open() now reads self.le_port.text(), stripping a leading
#       '/dev/' if present
# v4.00 renamed from pimd302.py; W (Mode 2 stream) records silently ignored;
#       window title updated

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import sys
import time
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton
from PyQt6.QtSerialPort import QSerialPort
from PyQt6.QtCore import QIODevice, QTimer, QPointF, Qt
from PyQt6.QtGui import QPen, QColor, QShortcut, QKeySequence
from PyQt6.QtCharts import QChart, QLineSeries, QValueAxis

from pimd111_ui import Ui_MainWindow  # This is your auto-generated UI file

DEFAULT_PORT = '/dev/ttyACM0'

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
        self.setWindowTitle('Pulse Induction Metal Detector v4.07 by Mark Makies')

        # Editable port field (mirrors pimd_classviz.py) — added below the existing
        # Connect/Start/filename rows in the same label+control grid layout.
        self.lbl_port = QLabel('Port:')
        self.le_port = QLineEdit(DEFAULT_PORT)
        self.le_port.setMaximumWidth(110)
        self.ui.gridLayout_2.addWidget(self.lbl_port, 3, 0, 1, 1)
        self.ui.gridLayout_2.addWidget(self.le_port, 3, 1, 1, 1)

        # Remove F1/F2/F3/F4 preset labels from the bottom-left area (v4.06).
        for _name in ('label_9', 'label_11', 'label_8', 'label_12',
                      'label_14', 'label_15', 'label_18', 'label_19'):
            getattr(self.ui, _name).setParent(None)

        # Boxcar mode toggle — enables/disables A<n> polling and the orange
        # trace (v4.06). "Raw Avg" toggle (show/hide trace within boxcar mode)
        # moved here from gridLayout_2.
        self.pb_boxcar_mode = QPushButton('Boxcar: OFF')
        self.pb_boxcar_mode.setCheckable(True)
        self.pb_boxcar_mode.setStyleSheet(self.MY_YELLOW)
        self.pb_boxcar_mode.toggled.connect(self._on_toggle_boxcar_mode)
        self.ui.formLayout_10.addRow(self.pb_boxcar_mode)

        self.pb_show_raw_mean = QPushButton('Raw Avg: OFF')
        self.pb_show_raw_mean.setCheckable(True)
        self.pb_show_raw_mean.setStyleSheet(self.MY_YELLOW)
        self.pb_show_raw_mean.toggled.connect(self._on_toggle_raw_mean)
        self.ui.formLayout_10.addRow(self.pb_show_raw_mean)

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

        # Chart toggles for the raw boxcar-average path (off by default)
        self.show_raw_mean = False

        # Periodic poll for a raw-path averaged sample while running
        self.raw_poll_timer = QTimer()
        self.raw_poll_timer.timeout.connect(self.poll_raw_average)

        # Measurement parameters — defaults are the Standard Operating
        # Conditions (see CHANGELOG.md): 10.0 kHz / 20.0 us pulse / 10.0 us
        # delay / 256 decimation. apply_soc_defaults() (called from my_init)
        # pushes these onto the sliders/DS-factor button at startup.
        self.frequency = 10.0        # in kHz (displayed as x/10 slider value)
        self.pulse_width = 20.0      # in µs
        self.sample_delay = 10.0     # in µs
        self.down_sample = 256        # down-sample factor for decimation filter

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
        self.axis_x = None
        self.axis_y = None
        self.axis_t = None
        self.axis_z = None

        # Vertical scale update flag and current Y range (for voltage)
        self.update_vert_scale = True
        self.cur_min = 0
        self.cur_max = 5000

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

    def apply_soc_defaults(self):
        """
        Standard Operating Conditions (see CHANGELOG.md) \u2014 10.0 kHz / 20.0 us
        pulse / 10.0 us delay / 256 decimation. Sets slider/button state only;
        the '*' command goes out the normal way when Start is pressed.
        """
        self.ui.slFreq.setValue(100)    # 10.0 kHz
        self.ui.slPulse.setValue(200)   # 20.0 us
        self.ui.slSample.setValue(100)  # 10.0 us
        self.ui.pbFactor.setText('256')
        self.down_sample = 256

    def my_init(self):
        """
        Initialization routine run after the UI has loaded.
        """
        # Set labels with arrow symbols
        self.ui.label_10.setText(' ' + '\u2bc5' + '   ' + '\u2bc6' + ' ')
        self.ui.label_13.setText(' ' + '\u2bc7' + '   ' + '\u2bc8' + ' ')

        self.setup_file_logging()  # Call function to handle file creation

        self.create_chart()
        self.apply_soc_defaults()
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
            if self.pb_boxcar_mode.isChecked():
                self.series_raw_mean.clear()
                self.raw_poll_timer.start(250)
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
        # n tracks the current DS Factor (was a hardcoded A32) so the raw
        # path's oversampling is comparable to the filtered path's decimation
        # factor instead of differing by ~8-32x just from sample-count
        # mismatch — that mismatch was the main reason the two std dev
        # readouts looked so far apart. Firmware caps A<n> at 1000.
        if self.serial.isOpen():
            n = min(self.down_sample, 1000)
            self.serial.write('A{0}\n'.format(n).encode())

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
            port = self.le_port.text()
            if port.startswith('/dev/'):
                port = port[5:]
            self.serial.setPortName(port)
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

            # Update the raw voltage buffer for slope calculation
            self.voltage_ts_buffer.append((p_timestamp/1000, p_voltage))
            if len(self.voltage_ts_buffer) > SLOPE_COUNT:
                self.voltage_ts_buffer.pop(0)
            
            # Compute and update the calculated stddev series (and slope series)
            self.update_stddev_chart(p_timestamp)

        elif line.startswith('R'):
            # Raw-path boxcar-average record:
            # R<time_ms>,<value_uV>,<stddev_uV>,<x>,<freq_kHz>,<pulse_us>,<delay_us>,<min_uV>,<max_uV>
            # min_uV/max_uV (firmware v4.15+) — sample extremes within the
            # boxcar window; diagnostic for outlier samples hiding inside the
            # mean/std (see CHANGELOG.md). Parsed defensively in case an older
            # firmware without these trailing fields is connected.
            parts = line[1:].split(',')
            try:
                r_timestamp = int(parts[0])
                self.raw_value_uV = int(parts[1])
                self.raw_stddev_uV = int(parts[2])
                self.raw_x = int(parts[3])
            except Exception as e:
                print('Raw packet parsing error:', e)
                return

            if self.show_raw_mean:
                self.series_raw_mean.append(QPointF(r_timestamp / 1000, self.raw_value_uV / 1000))
                x_min = self.axis_x.min()
                n = 0
                while n < self.series_raw_mean.count() and self.series_raw_mean.at(n).x() < x_min:
                    n += 1
                if n > 0:
                    self.series_raw_mean.removePoints(0, n)

        elif line.startswith('W'):
            return  # Mode 2 stream record — silently ignore in Mode 1 GUI

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

        # Raw boxcar-average mean series (orange) — toggled via "Raw Avg"
        # button (v4.03); shares the voltage axes with series_v.
        self.series_raw_mean = QLineSeries()
        pen_raw_mean = QPen(QColor('orange'))
        pen_raw_mean.setWidth(1)
        self.series_raw_mean.setPen(pen_raw_mean)
        self.chart.addSeries(self.series_raw_mean)

        _no_pen = QPen(QColor(0, 0, 0, 0))  # fully transparent — suppresses theme-overridden grid lines

        # X axis (timestamp, not visible)
        self.axis_x = QValueAxis()
        self.axis_x.setTickCount(7)
        self.axis_x.setVisible(False)
        self.chart.addAxis(self.axis_x, Qt.AlignmentFlag.AlignTop)
        self.series_v.attachAxis(self.axis_x)
        self.series_raw_mean.attachAxis(self.axis_x)
        self.axis_x.setGridLinePen(_no_pen)

        # Y axis (voltage, not visible)
        self.axis_y = QValueAxis()
        self.axis_y.setTickCount(6)
        self.axis_y.setVisible(False)
        self.chart.addAxis(self.axis_y, Qt.AlignmentFlag.AlignLeft)
        self.series_v.attachAxis(self.axis_y)
        self.series_raw_mean.attachAxis(self.axis_y)
        self.axis_y.setGridLinePen(_no_pen)

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
        self.axis_z.setGridLineColor(QColor("#cccccc"))  # preserves cosmetic (width=0) theme pen
        self.axis_z.setLabelsColor(QColor("blue"))

        self.ui.ChartView1.setChart(self.chart)
        self.ui.ChartView1.show()

    def update_uv_chart(self, timestamp, voltage):
        # Update the chart with a new data point.
        # timestamp: integer (ms), voltage: integer (µV)
        # Append new point (convert timestamp to seconds and voltage to mV)
        self.series_v.append(QPointF(timestamp / 1000, voltage / 1000))

        # Update X axis (time)
        last_timestamp = self.series_v.at(self.series_v.count() - 1).x()
        self.axis_x.setMax(last_timestamp)
        self.axis_x.setMin(self.axis_x.max() - self.h_scale)

        # Trim series to visible window — prevents off-screen points creating
        # diagonal polyline artifacts when the warmup spike scrolls off-screen
        x_min = self.axis_x.min()
        n = 0
        while n < self.series_v.count() and self.series_v.at(n).x() < x_min:
            n += 1
        if n > 0:
            self.series_v.removePoints(0, n)

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
        # Compute rolling slope from raw voltage using SLOPE_COUNT points from voltage_ts_buffer
        slope = 0
        if len(self.voltage_ts_buffer) >= SLOPE_COUNT:
            first_time, first_voltage = self.voltage_ts_buffer[0]
            last_time, last_voltage = self.voltage_ts_buffer[-1]
            if last_time - first_time != 0:
                slope = (last_voltage - first_voltage) / (last_time - first_time)
            else:
                slope = 0
        # Update the status bar to include computed stddev and slope

        if self.update_delay > 0:
            freq = (1 / (self.update_delay /1000)) * int(self.ui.pbFactor.text()) / 1000
            SPS = 1 / (self.update_delay /1000)
        else:
            freq = 0
            SPS = 0

        if self.raw_value_uV is not None:
            # "(N=...)" is the raw-path boxcar sample count (the A<n> argument
            # echoed back by firmware) — i.e. how many undecimated SDOB
            # samples this sd figure was averaged over. Was unlabelled "(x32)".
            # "range" is the min/max sample spread within that same boxcar
            # window (firmware v4.15+) — a wide spread with only a modest sd
            # points at a few outlier samples rather than uniform noise.
            raw_status = (f"Raw avg: {self.raw_value_uV:>9,d} uV, "
                           f"sd: {self.raw_stddev_uV:>6,d} uV (N={self.raw_x}) | ")
        else:
            raw_status = "Raw avg: -- | "

        self.ui.statusBar.showMessage(
                f"Last command: {self.last_command:<20} | "
                f"Incoming packet: {self.last_packet:<60} | "
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

    def _on_toggle_raw_mean(self, checked):
        # Show/hide the raw boxcar-average mean trace (orange), overlaid on
        # the same voltage axis as the filtered-path blue trace.
        self.show_raw_mean = checked
        self.pb_show_raw_mean.setText('Raw Avg: ON' if checked else 'Raw Avg: OFF')
        self.pb_show_raw_mean.setStyleSheet(self.MY_GREEN if checked else self.MY_YELLOW)
        if not checked:
            self.series_raw_mean.clear()

    def _on_toggle_boxcar_mode(self, checked):
        self.pb_boxcar_mode.setText('Boxcar: ON' if checked else 'Boxcar: OFF')
        self.pb_boxcar_mode.setStyleSheet(self.MY_GREEN if checked else self.MY_YELLOW)
        if checked:
            if self.ui.pbStart.text() == 'Running':
                self.series_raw_mean.clear()
                self.raw_poll_timer.start(250)
        else:
            self.raw_poll_timer.stop()
            self.series_raw_mean.clear()

    def clear_chart(self):
        # Clear the chart data.
        self.series_v.clear()
        self.series_raw_mean.clear()
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
