###############################################################################
# PIMD GUI v4.12
# — Mode 1 display
# Runs on Ubuntu desktop / laptop
#
# v4.12 (a) A<n> serial backlog fix: closeEvent and start_stop stop path now
#       call serial.clear(Direction.Output) before sending 'E', discarding any
#       queued A<n> commands accumulated in the write buffer. waitForBytesWritten
#       increased from 200 ms to 500 ms. Root cause: at slow rates (e.g. 6250 Hz /
#       DS 256) the firmware takes ~245 ms per A256, barely within the 250 ms poll
#       timer — any latency caused a growing backlog, delaying 'E' by 20–30 s.
#       (b) User-controlled Avg n field (default 64) added to the left sidebar
#       between the Boxcar and Raw Avg toggles. Orange highlight if n > freq/30,
#       meaning A<n> would exceed 80 % of the 250 ms poll timer. Warning also
#       re-evaluated on every frequency change.
#       (c) App no longer auto-connects on startup — consistent with pimd_classviz
#       and pimd_delaycal (user presses ENT / Connect explicitly).
#       (d) 10 uV, 20 uV, 50 uV and 100 uV V/div options removed from the left
#       sidebar to free space for the new Avg n field; minimum V/div is now 200 uV.
#       v_div arrow-key clamp updated accordingly (−11 instead of −15).
# v4.11 serial protocol updated to match MCU v4.23: * command now sends
#       freq in Hz (integer) and pulse/delay in ns (integer); * record parsing
#       updated accordingly. Title standardised to 'PIMD GUI v<N> by Mark Makies'.
# v4.10 read_from_serial: drain all buffered lines first, then dispatch — only
#       the last * packet per readyRead call gets the full chart/UI update; earlier
#       ones still write to file (skip_display=True path). Eliminates progressive
#       display lag when the event loop can't keep up with 39 SPS chart redraws.
#       process_packet: add skip_display=False parameter; early-return after file
#       write when skip_display is True. start_stop / closeEvent / setup_file_logging:
#       set self.file = None after close() — fixes "File write error, probably last
#       packet after stop" spam (closed file object is truthy; if self.file: passed
#       even after close, causing ValueError on write).
# v4.08 (a) lFreq/lPulse/lSample QLineEdit for direct precision entry: freq in
#       exact Hz (integer), pulse/delay to 3 dp in µs; orange highlight when
#       not on the 8 ns PWM grid or not a clean 125 MHz divisor. QLineEdit is
#       authoritative for the * command; sliders for coarse adjustment.
#       (b) Frequency slider re-ranged 0–17: each position is one of 18 clean
#       125 MHz divisors from 1–50 kHz (CLEAN_FREQS_KHZ list). Pulse/delay
#       sliders re-ranged in 8 ns counts (1 unit = 8 ns = 0.008 µs): slPulse
#       625–5000 (5–40 µs), slSample 625–3750 (5–30 µs). All slider positions
#       are inherently on-grid; +/- buttons step by one unit.
#       (c) Boxcar and Raw Avg buttons default ON.
#       (d) read_from_serial drains buffer in a while-canReadLine loop (was
#       single-line read → event-storm at high SPS → progressive UI freeze).
#       (e) closeEvent added: sends E, flushes serial, closes port and log file.
#       Removes fragile aboutToQuit lambda; F12 triggers closeEvent via self.close().
# v4.09 quit_app: QApplication.instance().exit() → self.close() so F12 actually
#       triggers closeEvent (QApplication.exit() bypasses closeEvent entirely).
#       (f) setup_file_logging closes previous file handle before opening new one.
# v4.07 remove range (min…max) from footer raw status string; fix horizontal
#       grid lines (axis_z) back to light gray (#cccccc, was blue).
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

# RP2040 PWM clock = 125 MHz → 8 ns per count.
# Clean frequencies: 125_000_000 % f == 0 (exact integer WRAP, no rounding).
SYS_CLK_HZ = 125_000_000
CLEAN_FREQS_HZ = frozenset(f for f in range(1000, 65001) if SYS_CLK_HZ % f == 0)

# Ordered subset used by the frequency slider (index 0–17, 1–50 kHz).
# All are exact 125 MHz divisors; spaced by ×1.25 or ×1.28 per step.
CLEAN_FREQS_KHZ = [1.0, 1.25, 1.6, 2.0, 2.5, 3.125, 4.0, 5.0,
                   6.25, 8.0, 10.0, 12.5, 15.625, 20.0, 25.0, 31.25, 40.0, 50.0]

# Must match firmware SAMPLE_PULSE_CORRECTION (µs). 0.904 µs = 904 ns = 113 × 8 ns exactly.
SAMPLE_PULSE_CORRECTION_US = 0.904

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
        self.setWindowTitle('PIMD GUI v4.12 by Mark Makies')

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

        # Remove 10/20/50/100 uV V/div options — too fine for normal use and
        # frees vertical space in the sidebar for the Avg n field (v4.12).
        for _name in ('rb2', 'rb9', 'rb5', 'rb10'):   # 100uV, 50uV, 20uV, 10uV
            btn = getattr(self.ui, _name)
            self.ui.VoltageButtonGroup.removeButton(btn)
            btn.setParent(None)

        # Boxcar mode toggle — enables/disables A<n> polling and the orange
        # trace (v4.06). "Raw Avg" toggle (show/hide trace within boxcar mode)
        # moved here from gridLayout_2.
        self.pb_boxcar_mode = QPushButton('Boxcar: OFF')
        self.pb_boxcar_mode.setCheckable(True)
        self.pb_boxcar_mode.setStyleSheet(self.MY_YELLOW)
        self.pb_boxcar_mode.toggled.connect(self._on_toggle_boxcar_mode)
        self.ui.formLayout_10.addRow(self.pb_boxcar_mode)

        # Avg n field — user sets A<n> sample count; orange if n would cause
        # the firmware to take > 80 % of the 250 ms poll timer (v4.12).
        self.avg_n = 64
        self.lbl_avg_n = QLabel('Avg n:')
        self.le_avg_n = QLineEdit('64')
        self.le_avg_n.setMaximumWidth(50)
        self.le_avg_n.editingFinished.connect(self._on_avg_n_edited)
        self.ui.formLayout_10.addRow(self.lbl_avg_n, self.le_avg_n)

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
        sc_r.activated.connect(lambda: (self.ui.slFreq.setValue(self.ui.slFreq.value() + 1), self.change_parameters()))
        sc_q = QShortcut(QKeySequence(Qt.Key.Key_Q), self)
        sc_q.activated.connect(lambda: (self.ui.slFreq.setValue(self.ui.slFreq.value() - 1), self.change_parameters()))

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
            lambda value: self._set_freq_display(CLEAN_FREQS_KHZ[value] * 1000)
        )
        self.ui.lFreq.editingFinished.connect(self._on_freq_edited)

        # Pulse width slider and buttons
        self.ui.pbPulseUp.clicked.connect(lambda: self.ui.slPulse.setValue(self.ui.slPulse.value() + 1))
        self.ui.pbPulseUp.clicked.connect(self.change_parameters)
        self.ui.pbPulseDown.clicked.connect(lambda: self.ui.slPulse.setValue(self.ui.slPulse.value() - 1))
        self.ui.pbPulseDown.clicked.connect(self.change_parameters)
        self.ui.slPulse.sliderReleased.connect(self.change_parameters)
        self.ui.slPulse.valueChanged.connect(
            lambda value: self._set_pulse_display(value * 0.008)
        )
        self.ui.lPulse.editingFinished.connect(self._on_pulse_edited)

        # Sample delay slider and buttons
        self.ui.pbSampleUp.clicked.connect(lambda: self.ui.slSample.setValue(self.ui.slSample.value() + 1))
        self.ui.pbSampleUp.clicked.connect(self.change_parameters)
        self.ui.pbSampleDown.clicked.connect(lambda: self.ui.slSample.setValue(self.ui.slSample.value() - 1))
        self.ui.pbSampleDown.clicked.connect(self.change_parameters)
        self.ui.slSample.sliderReleased.connect(self.change_parameters)
        self.ui.slSample.valueChanged.connect(
            lambda value: self._set_delay_display(value * 0.008)
        )
        self.ui.lSample.editingFinished.connect(self._on_delay_edited)

        # Button groups for vertical and horizontal scale changes
        self.ui.VoltageButtonGroup.buttonToggled.connect(self.vert_scale)
        self.ui.TimeButtonGroup.buttonToggled.connect(self.horiz_scale)

    # ------------------------------------------------------------------
    # QLineEdit display helpers — update text and 8 ns / clean-freq flag
    # ------------------------------------------------------------------

    def _set_freq_display(self, freq_hz):
        """Set lFreq text (Hz integer); highlight orange if not a clean 125 MHz divisor."""
        hz = int(round(freq_hz))
        self.ui.lFreq.setText(str(hz))
        self.ui.lFreq.setStyleSheet(
            '' if hz in CLEAN_FREQS_HZ else 'background-color: #ff8c00;'
        )
        self._check_avg_n_warning()

    def _set_pulse_display(self, pulse_us):
        """Set lPulse text (µs, 3 dp); highlight orange if not a multiple of 8 ns."""
        self.ui.lPulse.setText('{:.3f}'.format(pulse_us))
        self.ui.lPulse.setStyleSheet(
            '' if round(pulse_us * 1000) % 8 == 0 else 'background-color: #ff8c00;'
        )

    def _set_delay_display(self, delay_us):
        """Set lSample text (µs, 3 dp); highlight orange if total delay not on 8 ns grid."""
        self.ui.lSample.setText('{:.3f}'.format(delay_us))
        total_ns = round((delay_us + SAMPLE_PULSE_CORRECTION_US) * 1000)
        self.ui.lSample.setStyleSheet(
            '' if total_ns % 8 == 0 else 'background-color: #ff8c00;'
        )

    # ------------------------------------------------------------------
    # editingFinished handlers — parse QLineEdit, update slider, apply
    # ------------------------------------------------------------------

    def _on_freq_edited(self):
        """Parse Hz from lFreq; clamp, snap slider to nearest clean freq, apply."""
        try:
            freq_hz = int(float(self.ui.lFreq.text()))
            freq_hz = max(1000, min(65000, freq_hz))
        except ValueError:
            freq_hz = int(round(self.frequency * 1000))
        freq_khz = freq_hz / 1000
        slider_val = min(range(len(CLEAN_FREQS_KHZ)),
                         key=lambda i: abs(CLEAN_FREQS_KHZ[i] - freq_khz))
        self.ui.slFreq.blockSignals(True)
        self.ui.slFreq.setValue(slider_val)
        self.ui.slFreq.blockSignals(False)
        self._set_freq_display(freq_hz)   # also calls _check_avg_n_warning
        self.change_parameters()

    def _on_pulse_edited(self):
        """Parse µs from lPulse; clamp, sync slider (no feedback), apply."""
        try:
            pulse_us = float(self.ui.lPulse.text())
            pulse_us = max(5.0, min(100.0, pulse_us))
        except ValueError:
            pulse_us = self.pulse_width
        slider_val = max(self.ui.slPulse.minimum(),
                         min(self.ui.slPulse.maximum(), round(pulse_us * 125)))
        self.ui.slPulse.blockSignals(True)
        self.ui.slPulse.setValue(slider_val)
        self.ui.slPulse.blockSignals(False)
        self._set_pulse_display(pulse_us)
        self.change_parameters()

    def _on_delay_edited(self):
        """Parse µs from lSample; clamp, sync slider (no feedback), apply."""
        try:
            delay_us = float(self.ui.lSample.text())
            delay_us = max(5.0, min(100.0, delay_us))
        except ValueError:
            delay_us = self.sample_delay
        slider_val = max(self.ui.slSample.minimum(),
                         min(self.ui.slSample.maximum(), round(delay_us * 125)))
        self.ui.slSample.blockSignals(True)
        self.ui.slSample.setValue(slider_val)
        self.ui.slSample.blockSignals(False)
        self._set_delay_display(delay_us)
        self.change_parameters()

    def _on_avg_n_edited(self):
        """Parse and clamp the Avg n field; re-evaluate the safety warning."""
        try:
            n = max(1, min(1000, int(float(self.le_avg_n.text()))))
        except ValueError:
            n = 64
        self.avg_n = n
        self.le_avg_n.setText(str(n))
        self._check_avg_n_warning()

    def _check_avg_n_warning(self):
        """Orange if A<n> would occupy > 80 % of the 250 ms poll timer at current freq.
        Effective raw rate ≈ freq/6 (BUSY 1-in-6 catch, README §7).
        A<n> time = 6*n/freq s; warn when > 0.2 s → n > freq/30."""
        if not hasattr(self, 'le_avg_n'):
            return
        try:
            freq_hz = int(float(self.ui.lFreq.text()))
        except ValueError:
            freq_hz = int(round(self.frequency * 1000))
        n_safe = freq_hz / 30
        self.le_avg_n.setStyleSheet(
            'background-color: #ff8c00;' if self.avg_n > n_safe else ''
        )

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
        if self.file:
            self.file.close()
            self.file = None
        now = datetime.now()
        fname = 'data/' + now.strftime('P%d%m-%H%M%S.csv')
        self.ui.leFileName.setText(fname)  # Update UI field with filename
        self.file = open(fname, 'a')  # Open file in append mode

    def apply_soc_defaults(self):
        """
        Standard Operating Conditions (see CHANGELOG.md) \u2014 10.0 kHz / 20.0 \u00b5s
        pulse / 10.0 \u00b5s delay / 256 decimation. Sets slider/button state and
        QLineEdit display; '*' command goes out when Start is pressed.
        """
        self.ui.slFreq.setValue(10)     # index 10 \u2192 10.0 kHz
        self.ui.slPulse.setValue(2500)  # 2500 \u00d7 8 ns = 20.0 \u00b5s
        self.ui.slSample.setValue(1250) # 1250 \u00d7 8 ns = 10.0 \u00b5s
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
        # No auto-connect \u2014 user presses ENT / Connect explicitly (v4.12).
        self.pb_boxcar_mode.setChecked(True)
        self.pb_show_raw_mean.setChecked(True)
        self._check_avg_n_warning()

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
            self.raw_poll_timer.stop()
            self.serial.clear(QSerialPort.Direction.Output)
            self.send_command('E')
            if self.file:
                self.file.close()
                self.file = None

    def poll_raw_average(self):
        # Request a boxcar-averaged raw-path sample. Uses self.avg_n set by
        # the Avg n field (default 64). Firmware caps A<n> at 1000.
        if self.serial.isOpen():
            self.serial.write('A{0}\n'.format(self.avg_n).encode())

    def v_div(self, direction):
        # Adjust vertical division scale via button group.
        ix = self.ui.VoltageButtonGroup.checkedId()
        ix = ix + 1 if direction == 'up' else ix - 1
        # Clamp the value between -15 and -2
        ix = max(-11, min(-2, ix))
        self.ui.VoltageButtonGroup.button(ix).setChecked(True)

    def h_div(self, direction):
        # Adjust horizontal division scale via button group.
        ix = self.ui.TimeButtonGroup.checkedId()
        ix = ix + 1 if direction == 'up' else ix - 1
        # Clamp the value between -7 and -2
        ix = max(-7, min(-2, ix))
        self.ui.TimeButtonGroup.button(ix).setChecked(True)

    def change_parameters(self):
        # Read from QLineEdit fields (authoritative) and send configuration command.
        try:
            freq_hz = int(float(self.ui.lFreq.text()))
        except ValueError:
            freq_hz = int(round(self.frequency * 1000))
        try:
            pulse_us = float(self.ui.lPulse.text())
        except ValueError:
            pulse_us = self.pulse_width
        try:
            delay_us = float(self.ui.lSample.text())
        except ValueError:
            delay_us = self.sample_delay
        self.frequency = freq_hz / 1000          # kHz — kept for backwards compat
        self.pulse_width = pulse_us
        self.sample_delay = delay_us
        command_str = (
            '*'
            + str(freq_hz) + ','
            + str(round(pulse_us * 1000)) + ','
            + str(round(delay_us * 1000)) + ','
            + str(self.down_sample))
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
        lines = []
        while self.serial.canReadLine():
            data = self.serial.readLine().data().decode('utf-8').rstrip()
            if data:
                lines.append(data)
        if not lines:
            return
        # Only run the expensive chart/UI update for the last * packet in this
        # batch; earlier ones still get their file write via skip_display=True.
        last_star = max(
            (i for i, l in enumerate(lines) if l.startswith('*')),
            default=None
        )
        for i, line in enumerate(lines):
            self.process_packet(line, skip_display=(
                line.startswith('*') and i != last_star
            ))

    def process_packet(self, line, skip_display=False):
        REFERENCE_VOLTAGE = 5  # Volts
        self.last_packet = line  ## MM: store the current packet in an instance attribute

        if line.startswith('*'):
            line = line[1:]
            try:
                if self.file:
                    self.file.write(line + '\n')
            except Exception as e:
                print('File write error, probably last packet after stop:', e)

            if skip_display:
                return

            parts = line.split(',')
            try:
                p_timestamp = int(parts[0])
                p_voltage = int(parts[1])
                p_stddev = int(parts[2])
                p_frequency = int(parts[3])            # Hz (was kHz × 1000)
                p_pulse_width = int(parts[4]) / 1000.0  # ns → µs
                p_sample_delay = int(parts[5]) / 1000.0  # ns → µs
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
            # R<time_ms>,<value_uV>,<stddev_uV>,<x>,<freq_hz>,<pulse_ns>,<delay_ns>,<min_uV>,<max_uV>
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

    def closeEvent(self, event):
        self.raw_poll_timer.stop()
        if self.serial.isOpen():
            self.serial.clear(QSerialPort.Direction.Output)
            self.send_command('E')
            self.serial.waitForBytesWritten(500)
            self.serial.close()
        if self.file:
            self.file.close()
            self.file = None
        super().closeEvent(event)

    def quit_app(self):
        self.close()


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
