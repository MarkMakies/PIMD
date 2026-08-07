# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
# ###############################################################################
# PIMD GUI v4.16
# — Mode 1 display
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# Firmware commands used (wire protocol per DESIGN.md §9 — not altered here):
#   S / E                                   — start / stop Mode 1 streaming
#   *<freq_hz>,<pulse_ns>,<delay_ns>,<ds>   — configure the held Mode 1 pulse config
#   A<n>                                    — one boxcar-averaged raw sample
#   V                                       — identify; also carries the pack /
#                                             board-temp / lockout fields (fw v4.28+)
#
# Records parsed:
#   *<time_ms>,<value_uV>,<stddev_uV>,<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>
#   R<time_ms>,<mean_uV>,<std_uV>,<n>,<freq_hz>,<pulse_ns>,<delay_ns>,<min_uV>,<max_uV>
#   P<time_ms>,<pack_mV>,<board_temp_dC>    — unsolicited sensor telemetry, ~60 s
#   V<fw>,<board>,…,<pack_mV>,<board_temp_dC>,<lockout>
#                                           — fw / board read from every reply;
#                                             the trailing three need fw v4.28+
#   W…                                      — Mode 2 stream record, ignored here
#
# board_temp_dC is deci-degrees C (x10 integer) from the DS18B20 on GP6 as of fw
# v4.33, and TEMP_INVALID_DC (-32768) on that field means NO READING — sensor absent,
# unresponsive or CRC-failing. It is blanked, never plotted and never logged as a
# number; see _update_sensors().
#
# Session logs land in data/sessions/ as `gui_<ts>.csv`, alongside this project's
# other session dumps: a short '#' header, then one line per '*' record (the
# record verbatim, minus its '*'), with '# sensor:' comment lines interleaved as
# pack/temp telemetry arrives.
#
# History (full detail in CHANGELOG.md):
#   v4.16 board temperature is a real DS18B20 reading (fw v4.33) — sentinel-aware
#         gauge and session log, placeholder-thermistor tooltip retired
#   v4.15 MCU firmware version shown in the session block and written to the
#         session-log header (read from the 'V' reply already sent on connect)
#   v4.14 UI built in code (pimd111_ui.py retired); pack + board-temp gauges
#         replace the raw-voltage bar; session logs to data/sessions/; ENT/SPC
#         shortcuts dropped; pulse/delay ranges out to the profile maxima;
#         Current readout to 3 dp; alert row self-clears
#   v4.13 settings persistence (port/freq/pulse/delay/downsample/avg_n/toggles/geometry)
#   v4.12 A<n> serial-backlog fix; user Avg n field; no auto-connect; V/div options trimmed
#   v4.11 * command updated to MCU v4.23 protocol (Hz/ns)
#   v4.10 read_from_serial drains all lines, only last * packet updates UI
#   v4.09 quit_app uses self.close() so F12 triggers closeEvent
#   v4.08 direct-entry freq/pulse/delay fields; on-grid sliders; buffer-drain loop; closeEvent
#   v4.07 footer raw-status trim; horizontal grid lines back to gray
#   v4.06 chart-corruption fix (trim series by x-range); Boxcar toggle; Raw σ removed
#   v4.05 clear raw-mean/stddev series on Mode 1 start (phantom-trace fix)
#   v4.04 parse min_uV/max_uV appended to R record (mcu v4.15)
#   v4.03 Raw Avg / Raw sigma chart toggles
#   v4.02 startup defaults to Standard Operating Conditions; footer std-dev dedup
#   v4.01 editable port field (was hardcoded ttyACM0)
#   v4.00 renamed from pimd302.py; W records ignored; title updated

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import json
import os
import sys
import time
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QFormLayout, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QRadioButton,
    QSizePolicy, QSlider, QVBoxLayout, QWidget,
)
from PyQt6.QtSerialPort import QSerialPort
from PyQt6.QtCore import QIODevice, QRectF, QTimer, QPointF, Qt
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPainter, QPen, QShortcut
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

APP_VERSION = '4.16'

DEFAULT_PORT  = '/dev/ttyACM0'
_HERE         = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(_HERE, 'data', 'gui_settings.json')
SESSIONS_DIR  = os.path.join(_HERE, 'data', 'sessions')

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

# Pulse-width / sample-delay limits, in 8 ns slider counts. Set from the widest
# tracked profile (`cal_110_full_range_v4.json`: pulse 4.0–150.0 µs, delays
# 4.288–250.0 µs) so Mode 1 can reach every cell Mode 2 sweeps (v4.14). Whether a
# given pair is actually legal depends on frequency — the firmware rejects any
# config where pulse + delay + SAMPLE_PULSE_CORRECTION does not fit inside one
# period (pulse_duties_valid(), DESIGN §9) — so _check_period_fit() flags that
# separately rather than the sliders trying to encode it.
PULSE_MIN_US, PULSE_MAX_US = 4.0, 150.0
DELAY_MIN_US, DELAY_MAX_US = 4.0, 250.0
NS_PER_COUNT_INV = 125          # slider counts per µs (1 count = 8 ns)

SENSOR_POLL_MS = 10_000         # 'V' poll for pack/temp between the firmware's
                                # own 60 s unsolicited 'P' telemetry
ALERT_CLEAR_MS = 10_000         # transient alert row auto-clear (LOCKOUT exempt)

# Firmware-version label (v4.15). Set in three places — built, filled on 'V',
# reset on disconnect — so the base text lives here rather than being retyped.
FW_LABEL_TOOLTIP = 'MCU firmware version, from the V identify reply.'

# ---------------------------------------------------------------------------
# Pack state of charge
# ---------------------------------------------------------------------------
# Nominal Samsung ICR18650-26C open-circuit shape, per cell → SoC %. Same table
# as utilities/pack_discharge/packv.py; copied rather than imported, because
# nothing in src/ depends on utilities/ (DESIGN §15).
#
# Applied here to the LOADED pack voltage the firmware reports, with no
# correction, so it reads a few percent low while the coil is pulsing (~0.29 V
# at the terminals, DESIGN §12). It is a fuel-gauge indicator, not a calibrated
# runway number — that comes from packv.py's fit over a whole discharge.
N_CELLS = 6
SOC_NOMINAL = [(4.20, 100), (4.15, 95), (4.11, 90), (4.06, 85), (4.02, 80),
               (3.98, 75), (3.95, 70), (3.91, 65), (3.87, 60), (3.83, 55),
               (3.80, 50), (3.77, 45), (3.75, 40), (3.72, 35), (3.70, 30),
               (3.67, 25), (3.63, 20), (3.57, 15), (3.49, 10), (3.35, 5), (3.00, 0)]

# Pack zones, DESIGN §12 — the data-quality window, not the regulation floor.
# (upper bound mV, fill colour, short caption)
PACK_ZONES = (
    (21_000, '#f66151', 'LOCKOUT floor'),
    (21_500, '#ff8c00', 'below window'),
    (23_300, '#8ff0a4', 'clean window'),
    (24_000, '#f9f06b', 'transition'),
    (99_999, '#ff8c00', 'above ceiling'),
)
PACK_WINDOW_LO_MV = 21_500      # lower edge of the clean window — marked on the gauge

TEMP_GAUGE_MAX_C = 80.0         # board-temp gauge full scale
TEMP_INVALID_MAX_DC = -10_000   # board_temp_dC at or below this is the firmware's
                                # "no reading" sentinel (fw v4.33 sends -32768). Tested
                                # as a threshold rather than for equality so any future
                                # out-of-band code blanks the gauge too — and it cannot
                                # catch a real reading, the DS18B20 bottoming out at
                                # -55 °C, i.e. -550 dC.

KEY_LABEL_STYLE = 'background-color: rgb(61, 56, 70);\ncolor: rgb(237, 51, 59);'


def pack_soc_pct(pack_mV):
    """Loaded pack millivolts → SoC %, piecewise-linear on SOC_NOMINAL."""
    if pack_mV is None:
        return None
    vcell = pack_mV / 1000.0 / N_CELLS
    if vcell >= SOC_NOMINAL[0][0]:
        return 100.0
    if vcell <= SOC_NOMINAL[-1][0]:
        return 0.0
    for (v1, s1), (v2, s2) in zip(SOC_NOMINAL, SOC_NOMINAL[1:]):
        if v2 <= vcell <= v1:
            return s2 + (s1 - s2) * (vcell - v2) / (v1 - v2)
    return 0.0


def pack_zone(pack_mV):
    """Pack millivolts → (fill colour, short caption) per PACK_ZONES."""
    for upper, colour, caption in PACK_ZONES:
        if pack_mV <= upper:
            return colour, caption
    return PACK_ZONES[-1][1], PACK_ZONES[-1][2]


def _key_label(text):
    """Small dark keyboard-shortcut chip, as carried over from the .ui layout."""
    lbl = QLabel(text)
    font = QFont()
    font.setPointSize(9)
    font.setBold(True)
    lbl.setFont(font)
    lbl.setStyleSheet(KEY_LABEL_STYLE)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    return lbl


def _bold(text, points=10):
    lbl = QLabel(text)
    font = QFont()
    font.setPointSize(points)
    font.setBold(True)
    lbl.setFont(font)
    return lbl


class BatteryGauge(QWidget):
    """Battery-icon pack gauge — fill and text are state of charge, the caption
    is the measured pack voltage and which DESIGN §12 zone it sits in."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(170, 52)
        self.setMaximumHeight(52)
        self._pack_mV = None
        self._lockout = False
        self.setToolTip(
            'Pack voltage from the firmware (P/V telemetry, fw v4.28+).\n'
            'Fill and % are state of charge on the nominal ICR18650 curve,\n'
            'read off the loaded voltage, so it sits a few % low while pulsing.\n'
            'Colour is the DESIGN §12 data-quality window:\n'
            '  ≥ 24.0 V above the ceiling · 23.3–24.0 transition\n'
            '  21.5–23.3 clean window · below 21.5 out of window\n'
            '  ≤ 21.0 V firmware lockout floor (marked on the gauge).')

    def set_reading(self, pack_mV, lockout=False):
        self._pack_mV = pack_mV
        self._lockout = lockout
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cap_h = 15
        body = QRectF(1.5, 1.5, w - 9.5, h - cap_h - 4)
        nub = QRectF(body.right() + 1.5, body.top() + body.height() * 0.30,
                     5.0, body.height() * 0.40)

        outline = QColor('#5e5c64')
        p.setPen(QPen(outline, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(body, 3.0, 3.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(outline)
        p.drawRoundedRect(nub, 1.5, 1.5)

        inner = body.adjusted(3.0, 3.0, -3.0, -3.0)
        soc = pack_soc_pct(self._pack_mV)
        if soc is not None:
            colour, caption = pack_zone(self._pack_mV)
            if self._lockout:
                colour = PACK_ZONES[0][1]
            p.setBrush(QColor(colour))
            p.drawRect(QRectF(inner.left(), inner.top(),
                              inner.width() * max(0.0, min(100.0, soc)) / 100.0,
                              inner.height()))
            text = '{0:.0f} %'.format(soc)
            sub = '{0:.2f} V  ·  {1}'.format(self._pack_mV / 1000.0,
                                             'LOCKED OUT' if self._lockout else caption)
        else:
            text, sub = '—', 'no pack reading'

        # Lower edge of the clean window, so "stop capturing here" is visible
        # without doing the voltage-to-SoC conversion in your head.
        edge = pack_soc_pct(PACK_WINDOW_LO_MV)
        x = inner.left() + inner.width() * edge / 100.0
        p.setPen(QPen(QColor('#77767b'), 1.0, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(x, inner.top()), QPointF(x, inner.bottom()))

        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor('#241f31'))
        p.drawText(body, Qt.AlignmentFlag.AlignCenter, text)

        font.setPointSize(8)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor('#f66151') if self._lockout else self.palette().windowText().color())
        p.drawText(QRectF(0, h - cap_h, w, cap_h),
                   Qt.AlignmentFlag.AlignCenter, sub)


class BarGauge(QWidget):
    """Plain horizontal bar gauge with its reading printed inside — used for
    board temperature, whose firmware scale is a placeholder (see below)."""

    def __init__(self, vmax, fmt, colour='#a8c8e8', parent=None):
        super().__init__(parent)
        self.setMinimumSize(170, 24)
        self.setMaximumHeight(24)
        self._vmax = vmax
        self._fmt = fmt
        self._colour = colour
        self._value = None

    def set_value(self, value):
        self._value = value
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = QRectF(1.5, 1.5, self.width() - 3.0, self.height() - 3.0)
        p.setPen(QPen(QColor('#5e5c64'), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(body, 3.0, 3.0)

        inner = body.adjusted(2.5, 2.5, -2.5, -2.5)
        if self._value is None:
            text = '—'
        else:
            frac = max(0.0, min(1.0, self._value / self._vmax))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(self._colour))
            p.drawRect(QRectF(inner.left(), inner.top(),
                              inner.width() * frac, inner.height()))
            text = self._fmt.format(self._value)

        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor('#241f31') if self._value is not None
                 else self.palette().windowText().color())
        p.drawText(body, Qt.AlignmentFlag.AlignCenter, text)


class MainWindow(QMainWindow):
    # Color constants for button styling
    MY_GREEN = 'background-color: rgb(143, 240, 164);'
    MY_YELLOW = 'background-color: rgb(249, 240, 107);'
    MY_RED = 'background-color: rgb(246, 97, 81);'
    MY_BROWN = 'background-color: rgb(165, 42, 42);'

    def __init__(self):
        super().__init__()
        self.setWindowTitle('PIMD GUI v{0} by Mark Makies'.format(APP_VERSION))

        # Serial port and file handle
        self.serial = QSerialPort()
        self.file = None
        self.log_path = None

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

        # Pack / board-temp telemetry (firmware v4.28+): 'P' arrives unsolicited
        # every 60 s, and a 'V' poll fills the gaps and carries the lockout flag.
        self.pack_mV = None
        self.board_temp_dC = None
        self.pack_lockout = False

        # MCU identity, from the same 'V' reply (fields 0 and 1). Cleared on
        # disconnect — it is a property of the open connection, not of the app.
        self.fw_version = None
        self.board_id = None

        # Chart toggles for the raw boxcar-average path (off by default)
        self.show_raw_mean = False

        # Periodic poll for a raw-path averaged sample while running
        self.raw_poll_timer = QTimer()
        self.raw_poll_timer.timeout.connect(self.poll_raw_average)

        self.sensor_poll_timer = QTimer()
        self.sensor_poll_timer.timeout.connect(self.poll_sensors)

        # Alert row auto-clear. A firmware complaint is about the config that
        # was live when it was sent; left up, it outlives the config it refers
        # to and stops meaning anything. A latched lockout is exempt (sticky).
        self._alert_sticky = False
        self.alert_clear_timer = QTimer()
        self.alert_clear_timer.setSingleShot(True)
        self.alert_clear_timer.timeout.connect(lambda: self._set_alert(''))

        # Measurement parameters — defaults are the Standard Operating
        # Conditions (see CHANGELOG.md): 10.0 kHz / 20.0 us pulse / 10.0 us
        # delay / 256 decimation. apply_soc_defaults() (called from my_init)
        # pushes these onto the sliders/DS-factor button at startup.
        self.frequency = 10.0        # in kHz (displayed as x/10 slider value)
        self.pulse_width = 20.0      # in µs
        self.sample_delay = 10.0     # in µs
        self.down_sample = 256        # down-sample factor for decimation filter
        self.avg_n = 64

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
        self.series_raw_mean = None
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

        self._build_ui()

        # Setup UI connections and shortcuts
        self._setup_shortcuts()  # Set up keyboard shortcuts.
        self._setup_ui_connections()  # Connect UI widget signals to instance methods.

        # Connect serial ready signal
        self.serial.readyRead.connect(self.read_from_serial)

        # One-shot timer to allow UI to settle before initialization
        QTimer.singleShot(10, self.my_init)

    # ------------------------------------------------------------------
    # UI construction (was pimd111.ui / pimd111_ui.py until v4.14)
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 4, 6, 0)
        root.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addLayout(self._build_session_block())
        top.addWidget(self._build_slider_block())
        top.addWidget(self._build_gauge_block())
        top.addWidget(self._build_numeric_block())
        top.addStretch(1)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setContentsMargins(0, 2, 0, 0)
        body.setSpacing(4)
        body.addLayout(self._build_side_column())
        self.chart_view = QChartView()
        self.chart_view.setSizePolicy(QSizePolicy.Policy.Expanding,
                                      QSizePolicy.Policy.Expanding)
        self.chart_view.setFrameShape(QFrame.Shape.NoFrame)
        body.addWidget(self.chart_view, 1)
        root.addLayout(body, 1)

    def _build_session_block(self):
        """Port / Connect / Start / session-log block — top left."""
        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(3)

        grid.addWidget(QLabel('Port:'), 0, 0)
        self.le_port = QLineEdit(DEFAULT_PORT)
        self.le_port.setMaximumWidth(150)
        grid.addWidget(self.le_port, 0, 1)

        self.pb_connect = QPushButton('Not Connected')
        self.pb_connect.setStyleSheet(self.MY_YELLOW)
        self.pb_connect.setMinimumWidth(110)
        grid.addWidget(self.pb_connect, 0, 2)

        grid.addWidget(QLabel('Session:'), 1, 0)
        self.lbl_log = QLabel('—')
        font = QFont()
        font.setPointSize(8)
        self.lbl_log.setFont(font)
        self.lbl_log.setMinimumWidth(150)
        self.lbl_log.setToolTip('Session log file (data/sessions/).')
        grid.addWidget(self.lbl_log, 1, 1)

        self.pb_start = QPushButton('Stopped')
        self.pb_start.setStyleSheet(self.MY_YELLOW)
        self.pb_start.setMinimumWidth(110)
        self.pb_start.setEnabled(False)
        grid.addWidget(self.pb_start, 1, 2)

        # Firmware version of the connected board (v4.15) — field 0 of the 'V'
        # identify reply the GUI already sends on connect.
        grid.addWidget(QLabel('Firmware:'), 2, 0)
        self.lbl_fw = QLabel('—')
        self.lbl_fw.setFont(font)
        self.lbl_fw.setMinimumWidth(150)
        self.lbl_fw.setToolTip(FW_LABEL_TOOLTIP)
        grid.addWidget(self.lbl_fw, 2, 1)

        # Firmware complaints (rejected config, pack-voltage lockout) land here
        # rather than in the status bar, which the '*' stream rewrites ~20×/s.
        self.lbl_alert = QLabel('')
        self.lbl_alert.setFont(font)
        self.lbl_alert.setStyleSheet('color: rgb(224, 27, 36);')
        self.lbl_alert.setWordWrap(True)
        grid.addWidget(self.lbl_alert, 3, 0, 1, 3)
        grid.setRowStretch(3, 1)
        return grid

    def _build_slider_block(self):
        """Frequency / pulse width / sample delay sliders + DS factor."""
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(2)

        rows = (
            ('Frequency',    'pbFreqDown',   'pbFreqUp',   'lFreq',   'slFreq',
             ' Q ', ' W ', ' E ', ' R '),
            ('Pulse Width',  'pbPulseDown',  'pbPulseUp',  'lPulse',  'slPulse',
             ' A ', ' S ', ' D ', ' F '),
            ('Sample Delay', 'pbSampleDown', 'pbSampleUp', 'lSample', 'slSample',
             ' Z ', ' X ', ' C ', ' V '),
        )
        for r, (name, down, up, edit, slider, k1, k2, k3, k4) in enumerate(rows):
            grid.addWidget(_bold(name), r, 0)
            for col, (attr, text) in enumerate(((down, '-'), (up, '+')), start=1):
                btn = QPushButton(text)
                btn.setMaximumWidth(30)
                setattr(self, attr, btn)
                grid.addWidget(btn, r, col)
            le = QLineEdit()
            le.setMinimumWidth(75)
            le.setMaximumWidth(80)
            f = QFont()
            f.setPointSize(11)
            f.setBold(True)
            le.setFont(f)
            setattr(self, edit, le)
            grid.addWidget(le, r, 3)
            grid.addWidget(_key_label(k1), r, 4)
            grid.addWidget(_key_label(k2), r, 5)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setMinimumWidth(320)
            sl.setPageStep(0)
            sl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            setattr(self, slider, sl)
            grid.addWidget(sl, r, 6)
            grid.addWidget(_key_label(k3), r, 7)
            grid.addWidget(_key_label(k4), r, 8)

        self.slFreq.setMinimum(0)
        self.slFreq.setMaximum(len(CLEAN_FREQS_KHZ) - 1)
        self.slFreq.setSingleStep(1)
        self.slFreq.setValue(10)
        # v4.14: full profile range, in 8 ns counts (see PULSE_MIN_US et al).
        self.slPulse.setMinimum(round(PULSE_MIN_US * NS_PER_COUNT_INV))
        self.slPulse.setMaximum(round(PULSE_MAX_US * NS_PER_COUNT_INV))
        self.slPulse.setValue(2500)
        self.slSample.setMinimum(round(DELAY_MIN_US * NS_PER_COUNT_INV))
        self.slSample.setMaximum(round(DELAY_MAX_US * NS_PER_COUNT_INV))
        self.slSample.setValue(1250)

        grid.addWidget(_bold('DS Factor'), 3, 0)
        self.pbFactor = QPushButton('256')
        grid.addWidget(self.pbFactor, 3, 1, 1, 2)

        # Duty / period-fit readout — the firmware rejects any config whose
        # pulse + delay + correction does not fit inside one period.
        self.lbl_duty = QLabel('')
        f = QFont()
        f.setPointSize(9)
        self.lbl_duty.setFont(f)
        grid.addWidget(self.lbl_duty, 3, 3, 1, 6)
        return holder

    def _build_gauge_block(self):
        """Pack state-of-charge and board-temperature gauges (v4.14) — replaces
        the raw-voltage progress bar, which duplicated the Current readout."""
        holder = QWidget()
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(3)
        self.gauge_pack = BatteryGauge()
        col.addWidget(self.gauge_pack)
        self.gauge_temp = BarGauge(TEMP_GAUGE_MAX_C, '{0:.1f} °C')
        self.gauge_temp.setToolTip(
            'Board temperature from the firmware (P/V telemetry).\n'
            'DS18B20 1-Wire sensor on GP6, factory-calibrated to ±0.5 °C\n'
            '(fw v4.33+); reported to 0.1 °C and refreshed every 30 s.\n'
            'Shows — when the sensor is absent, unresponsive or CRC-failing.\n'
            'Firmware v4.28–v4.32 sent a bench-pot placeholder on this field.')
        col.addWidget(self.gauge_temp)
        col.addStretch(1)
        return holder

    def _build_numeric_block(self):
        """Current / Std Dev / Scale readouts."""
        holder = QWidget()
        form = QFormLayout(holder)
        form.setContentsMargins(0, 0, 20, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(5)

        big = QFont()
        big.setPointSize(14)
        big.setBold(True)
        mid = QFont()
        mid.setPointSize(12)
        mid.setBold(True)

        self.luV = QLabel('0.000 mV')
        self.luV.setFont(big)
        self.luV.setMinimumWidth(150)
        self.luV.setStyleSheet(self.MY_GREEN)
        self.luV.setAlignment(Qt.AlignmentFlag.AlignRight
                              | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(QLabel('Current'), self.luV)

        self.luVsd = QLabel('0 uV')
        self.luVsd.setFont(mid)
        self.luVsd.setMinimumWidth(120)
        self.luVsd.setAlignment(Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(QLabel('Std Dev'), self.luVsd)

        self.uVlabel = QLabel('V / div')
        self.uVlabel.setFont(big)
        self.uVlabel.setMinimumWidth(120)
        self.uVlabel.setStyleSheet('background-color: rgb(205, 171, 143);')
        self.uVlabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form.addRow(QLabel('Scale'), self.uVlabel)
        return holder

    def _build_side_column(self):
        """Chart-side controls: V/div, Sec/div, chart buttons, boxcar options."""
        col = QVBoxLayout()
        col.setContentsMargins(0, 6, 0, 6)
        col.setSpacing(0)

        hint_up = _key_label(' ⯅   ⯆ ')
        hint_up.setMaximumWidth(60)
        col.addWidget(hint_up)

        self.gbVertScale = QGroupBox('Volts / div')
        self.gbVertScale.setMaximumWidth(78)
        vbox = QVBoxLayout(self.gbVertScale)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        self.VoltageButtonGroup = QButtonGroup(self)
        # Ids are the vert_scales keys; the 10/20/50/100 µV steps were dropped
        # in v4.12 as too fine for normal use.
        for ident, text in ((-2, '500 mV'), (-3, '100 mV'), (-4, '50 mV'),
                            (-5, '20 mV'), (-6, '10 mV'), (-7, '5 mV'),
                            (-8, '2 mV'), (-9, '1 mV'), (-10, '500 uV'),
                            (-11, '200 uV')):
            rb = QRadioButton(text)
            self.VoltageButtonGroup.addButton(rb, ident)
            vbox.addWidget(rb)
        self.VoltageButtonGroup.button(-2).setChecked(True)
        col.addWidget(self.gbVertScale)

        hint_side = _key_label(' ⯇   ⯈ ')
        hint_side.setMaximumWidth(60)
        col.addWidget(hint_side)

        self.gbTimeScale = QGroupBox('Sec / div')
        self.gbTimeScale.setMaximumWidth(78)
        hbox = QVBoxLayout(self.gbTimeScale)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)
        self.TimeButtonGroup = QButtonGroup(self)
        for ident, text in ((-2, '30 s'), (-3, '20 s'), (-4, '10 s'),
                            (-5, '5 s'), (-6, '2 s'), (-7, '1 s')):
            rb = QRadioButton(text)
            self.TimeButtonGroup.addButton(rb, ident)
            hbox.addWidget(rb)
        self.TimeButtonGroup.button(-2).setChecked(True)
        col.addWidget(self.gbTimeScale)

        form_holder = QWidget()
        form = QFormLayout(form_holder)
        form.setContentsMargins(0, 5, 0, 0)
        form.setHorizontalSpacing(2)
        form.setVerticalSpacing(3)

        self.pbClear = QPushButton('Clear')
        self.pbClear.setMaximumWidth(55)
        form.addRow(_key_label(' DEL '), self.pbClear)
        self.pbReset = QPushButton('Reset')
        self.pbReset.setMaximumWidth(55)
        form.addRow(_key_label(' ESC '), self.pbReset)

        # Boxcar mode toggle — enables/disables A<n> polling and the orange
        # trace (v4.06).
        self.pb_boxcar_mode = QPushButton('Boxcar: OFF')
        self.pb_boxcar_mode.setCheckable(True)
        self.pb_boxcar_mode.setStyleSheet(self.MY_YELLOW)
        self.pb_boxcar_mode.toggled.connect(self._on_toggle_boxcar_mode)
        form.addRow(self.pb_boxcar_mode)

        # Avg n field — user sets A<n> sample count; orange if n would cause
        # the firmware to take > 80 % of the 250 ms poll timer (v4.12).
        self.le_avg_n = QLineEdit('64')
        self.le_avg_n.setMaximumWidth(50)
        self.le_avg_n.editingFinished.connect(self._on_avg_n_edited)
        form.addRow(QLabel('Avg n:'), self.le_avg_n)

        self.pb_show_raw_mean = QPushButton('Raw Avg: OFF')
        self.pb_show_raw_mean.setCheckable(True)
        self.pb_show_raw_mean.setStyleSheet(self.MY_YELLOW)
        self.pb_show_raw_mean.toggled.connect(self._on_toggle_raw_mean)
        form.addRow(self.pb_show_raw_mean)

        form.addRow(_key_label(' F12 '), QLabel('Quit'))
        col.addWidget(form_holder)
        col.addStretch(1)
        return col

    def _setup_shortcuts(self):
        # Set up keyboard shortcuts.
        # (v4.14: Return/Space — the old ENT/SPC chips — are gone; Connect and
        # Start are deliberate, mouse-only actions now.)

        scF11 = QShortcut(QKeySequence(Qt.Key.Key_F11), self)
        scF11.activated.connect(self.toggleFullScreen)

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
        sc_e.activated.connect(self.pbFreqUp.animateClick)
        sc_w = QShortcut(QKeySequence(Qt.Key.Key_W), self)
        sc_w.activated.connect(self.pbFreqDown.animateClick)
        sc_r = QShortcut(QKeySequence(Qt.Key.Key_R), self)
        sc_r.activated.connect(lambda: (self.slFreq.setValue(self.slFreq.value() + 1), self.change_parameters()))
        sc_q = QShortcut(QKeySequence(Qt.Key.Key_Q), self)
        sc_q.activated.connect(lambda: (self.slFreq.setValue(self.slFreq.value() - 1), self.change_parameters()))

        # Pulse width selector shortcuts
        sc_d = QShortcut(QKeySequence(Qt.Key.Key_D), self)
        sc_d.activated.connect(self.pbPulseUp.animateClick)
        sc_s = QShortcut(QKeySequence(Qt.Key.Key_S), self)
        sc_s.activated.connect(self.pbPulseDown.animateClick)
        sc_f = QShortcut(QKeySequence(Qt.Key.Key_F), self)
        sc_f.activated.connect(lambda: (self.slPulse.setValue(self.slPulse.value() + 10), self.change_parameters()))
        sc_a = QShortcut(QKeySequence(Qt.Key.Key_A), self)
        sc_a.activated.connect(lambda: (self.slPulse.setValue(self.slPulse.value() - 10), self.change_parameters()))

        # Sample delay selector shortcuts
        sc_c = QShortcut(QKeySequence(Qt.Key.Key_C), self)
        sc_c.activated.connect(self.pbSampleUp.animateClick)
        sc_x = QShortcut(QKeySequence(Qt.Key.Key_X), self)
        sc_x.activated.connect(self.pbSampleDown.animateClick)
        sc_v = QShortcut(QKeySequence(Qt.Key.Key_V), self)
        sc_v.activated.connect(lambda: (self.slSample.setValue(self.slSample.value() + 10), self.change_parameters()))
        sc_z = QShortcut(QKeySequence(Qt.Key.Key_Z), self)
        sc_z.activated.connect(lambda: (self.slSample.setValue(self.slSample.value() - 10), self.change_parameters()))

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
        self.pb_connect.clicked.connect(self.connect_port)
        self.pb_start.clicked.connect(self.start_stop)
        self.pbReset.clicked.connect(self.reset_chart)
        self.pbClear.clicked.connect(self.clear_chart)
        self.pbFactor.clicked.connect(self.set_factor)

        # Frequency slider and buttons
        self.pbFreqUp.clicked.connect(lambda: self.slFreq.setValue(self.slFreq.value() + 1))
        self.pbFreqUp.clicked.connect(self.change_parameters)
        self.pbFreqDown.clicked.connect(lambda: self.slFreq.setValue(self.slFreq.value() - 1))
        self.pbFreqDown.clicked.connect(self.change_parameters)
        self.slFreq.sliderReleased.connect(self.change_parameters)
        self.slFreq.valueChanged.connect(
            lambda value: self._set_freq_display(CLEAN_FREQS_KHZ[value] * 1000)
        )
        self.lFreq.editingFinished.connect(self._on_freq_edited)

        # Pulse width slider and buttons
        self.pbPulseUp.clicked.connect(lambda: self.slPulse.setValue(self.slPulse.value() + 1))
        self.pbPulseUp.clicked.connect(self.change_parameters)
        self.pbPulseDown.clicked.connect(lambda: self.slPulse.setValue(self.slPulse.value() - 1))
        self.pbPulseDown.clicked.connect(self.change_parameters)
        self.slPulse.sliderReleased.connect(self.change_parameters)
        self.slPulse.valueChanged.connect(
            lambda value: self._set_pulse_display(value * 0.008)
        )
        self.lPulse.editingFinished.connect(self._on_pulse_edited)

        # Sample delay slider and buttons
        self.pbSampleUp.clicked.connect(lambda: self.slSample.setValue(self.slSample.value() + 1))
        self.pbSampleUp.clicked.connect(self.change_parameters)
        self.pbSampleDown.clicked.connect(lambda: self.slSample.setValue(self.slSample.value() - 1))
        self.pbSampleDown.clicked.connect(self.change_parameters)
        self.slSample.sliderReleased.connect(self.change_parameters)
        self.slSample.valueChanged.connect(
            lambda value: self._set_delay_display(value * 0.008)
        )
        self.lSample.editingFinished.connect(self._on_delay_edited)

        # Button groups for vertical and horizontal scale changes
        self.VoltageButtonGroup.buttonToggled.connect(self.vert_scale)
        self.TimeButtonGroup.buttonToggled.connect(self.horiz_scale)

    # ------------------------------------------------------------------
    # QLineEdit display helpers — update text and 8 ns / clean-freq flag
    # ------------------------------------------------------------------

    def _set_freq_display(self, freq_hz):
        """Set lFreq text (Hz integer); highlight orange if not a clean 125 MHz divisor."""
        hz = int(round(freq_hz))
        self.lFreq.setText(str(hz))
        self.lFreq.setStyleSheet(
            '' if hz in CLEAN_FREQS_HZ else 'background-color: #ff8c00;'
        )
        self._check_avg_n_warning()
        self._check_period_fit()

    def _set_pulse_display(self, pulse_us):
        """Set lPulse text (µs, 3 dp); highlight orange if not a multiple of 8 ns."""
        self.lPulse.setText('{:.3f}'.format(pulse_us))
        self.lPulse.setStyleSheet(
            '' if round(pulse_us * 1000) % 8 == 0 else 'background-color: #ff8c00;'
        )
        self._check_period_fit()

    def _set_delay_display(self, delay_us):
        """Set lSample text (µs, 3 dp); highlight orange if total delay not on 8 ns grid."""
        self.lSample.setText('{:.3f}'.format(delay_us))
        total_ns = round((delay_us + SAMPLE_PULSE_CORRECTION_US) * 1000)
        self.lSample.setStyleSheet(
            '' if total_ns % 8 == 0 else 'background-color: #ff8c00;'
        )
        self._check_period_fit()

    # ------------------------------------------------------------------
    # editingFinished handlers — parse QLineEdit, update slider, apply
    # ------------------------------------------------------------------

    def _on_freq_edited(self):
        """Parse Hz from lFreq; clamp, snap slider to nearest clean freq, apply."""
        try:
            freq_hz = int(float(self.lFreq.text()))
            freq_hz = max(1000, min(65000, freq_hz))
        except ValueError:
            freq_hz = int(round(self.frequency * 1000))
        freq_khz = freq_hz / 1000
        slider_val = min(range(len(CLEAN_FREQS_KHZ)),
                         key=lambda i: abs(CLEAN_FREQS_KHZ[i] - freq_khz))
        self.slFreq.blockSignals(True)
        self.slFreq.setValue(slider_val)
        self.slFreq.blockSignals(False)
        self._set_freq_display(freq_hz)   # also calls _check_avg_n_warning
        self.change_parameters()

    def _on_pulse_edited(self):
        """Parse µs from lPulse; clamp, sync slider (no feedback), apply."""
        try:
            pulse_us = float(self.lPulse.text())
            pulse_us = max(PULSE_MIN_US, min(PULSE_MAX_US, pulse_us))
        except ValueError:
            pulse_us = self.pulse_width
        slider_val = max(self.slPulse.minimum(),
                         min(self.slPulse.maximum(), round(pulse_us * NS_PER_COUNT_INV)))
        self.slPulse.blockSignals(True)
        self.slPulse.setValue(slider_val)
        self.slPulse.blockSignals(False)
        self._set_pulse_display(pulse_us)
        self.change_parameters()

    def _on_delay_edited(self):
        """Parse µs from lSample; clamp, sync slider (no feedback), apply."""
        try:
            delay_us = float(self.lSample.text())
            delay_us = max(DELAY_MIN_US, min(DELAY_MAX_US, delay_us))
        except ValueError:
            delay_us = self.sample_delay
        slider_val = max(self.slSample.minimum(),
                         min(self.slSample.maximum(), round(delay_us * NS_PER_COUNT_INV)))
        self.slSample.blockSignals(True)
        self.slSample.setValue(slider_val)
        self.slSample.blockSignals(False)
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
        Effective raw rate ≈ freq/6 (BUSY 1-in-6 catch, DESIGN §7).
        A<n> time = 6*n/freq s; warn when > 0.2 s → n > freq/30."""
        if not hasattr(self, 'le_avg_n'):
            return
        try:
            freq_hz = int(float(self.lFreq.text()))
        except ValueError:
            freq_hz = int(round(self.frequency * 1000))
        n_safe = freq_hz / 30
        self.le_avg_n.setStyleSheet(
            'background-color: #ff8c00;' if self.avg_n > n_safe else ''
        )

    def _check_period_fit(self):
        """Duty readout + period-fit check (v4.14).

        The firmware computes both PWM duties from the same period and rejects
        the '*' config unless the sample edge still falls inside it — i.e.
        pulse + delay + SAMPLE_PULSE_CORRECTION < 1/freq (pulse_duties_valid(),
        DESIGN §9). With pulse/delay now reaching 150/250 µs that limit is
        reachable at the low-frequency bands, so say so before the board does.
        """
        if not hasattr(self, 'lbl_duty'):
            return
        try:
            freq_hz = int(float(self.lFreq.text()))
            pulse_us = float(self.lPulse.text())
            delay_us = float(self.lSample.text())
        except ValueError:
            return
        if freq_hz <= 0:
            return
        period_us = 1_000_000.0 / freq_hz
        span_us = pulse_us + delay_us + SAMPLE_PULSE_CORRECTION_US
        duty_pct = 100.0 * pulse_us / period_us
        if span_us >= period_us:
            self.lbl_duty.setStyleSheet('color: rgb(224, 27, 36);')
            self.lbl_duty.setText(
                'REJECTED: pulse+delay {0:.1f} µs > {1:.1f} µs period'.format(
                    span_us, period_us))
            self.lbl_duty.setToolTip(
                'The firmware will refuse this config: pulse width + sample delay '
                '+ {0} µs correction must fit inside one period. Lower the '
                'frequency, or shorten the pulse or delay.'.format(
                    SAMPLE_PULSE_CORRECTION_US))
        else:
            self.lbl_duty.setStyleSheet('')
            self.lbl_duty.setText(
                'drive duty {0:.1f} %  ·  pulse+delay {1:.1f} / {2:.1f} µs period'.format(
                    duty_pct, span_us, period_us))
            self.lbl_duty.setToolTip(
                'Drive duty sets coil dissipation (DESIGN §17.1). pulse+delay is '
                'measured against the period the firmware has to fit them in.')

    def set_factor(self):
        toggle_map = {'256': '1024', '1024': '256'}
        current_text = self.pbFactor.text()

        if current_text in toggle_map:
            new_text = toggle_map[current_text]
            self.pbFactor.setText(new_text)
            self.down_sample = int(new_text)
        self.change_parameters()

    def setup_file_logging(self):
        """Open a timestamped session log in data/sessions/ (v4.14 — was a bare
        data/P<ts>.csv next to the settings files, opened at startup whether or
        not anything ran). Called on Start, so an idle app leaves no empty file.
        """
        if self.file:
            self.file.close()
            self.file = None
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        ts = datetime.now()
        self.log_path = os.path.join(SESSIONS_DIR,
                                     'gui_' + ts.strftime('%Y%m%d_%H%M%S') + '.csv')
        self.file = open(self.log_path, 'a', buffering=1)   # line-buffered
        self.file.write('# pimd_gui v{0} — Mode 1 session\n'.format(APP_VERSION))
        self.file.write('# fw_version: {0}\n'.format(self.fw_version or 'unknown'))
        self.file.write('# session_start_iso: {0}\n'.format(ts.isoformat(timespec='seconds')))
        self.file.write('# columns: time_ms,value_uV,stddev_uV,freq_hz,pulse_ns,'
                        'delay_ns,downsample\n')
        self.lbl_log.setText(os.path.basename(self.log_path))
        self.lbl_log.setToolTip(self.log_path)

    def apply_soc_defaults(self):
        """
        Standard Operating Conditions (see CHANGELOG.md) — 10.0 kHz / 20.0 µs
        pulse / 10.0 µs delay / 256 decimation. Sets slider/button state and
        QLineEdit display; '*' command goes out when Start is pressed.

        The displays are set explicitly rather than left to the sliders'
        valueChanged: a slider already sitting on its default emits nothing, and
        before v4.14 that left the fields showing whatever text the .ui file
        carried until settings were loaded over them.
        """
        self.slFreq.setValue(10)     # index 10 → 10.0 kHz
        self.slPulse.setValue(2500)  # 2500 × 8 ns = 20.0 µs
        self.slSample.setValue(1250) # 1250 × 8 ns = 10.0 µs
        self._set_freq_display(10000)
        self._set_pulse_display(20.0)
        self._set_delay_display(10.0)
        self.pbFactor.setText('256')
        self.down_sample = 256

    def my_init(self):
        """
        Initialization routine run after the UI has loaded.
        """
        self.create_chart()
        self.apply_soc_defaults()
        # No auto-connect — the user presses Connect explicitly (v4.12).
        self.pb_boxcar_mode.setChecked(True)
        self.pb_show_raw_mean.setChecked(True)
        self._check_avg_n_warning()
        self._load_settings()
        self._check_period_fit()

    # ------------------------------------------------------------------
    # Serial connect / disconnect
    # ------------------------------------------------------------------
    def connect_port(self):
        # Open or close the serial port. Matches pimd_classviz / pimd_delaycal:
        # 'E' on connect to put the board in a known safe state, 'V' to pull the
        # firmware's identify line (and with it pack / temp / lockout), and Start
        # stays disabled until there is a port to start on (v4.14).
        if not self.serial.isOpen():
            if self.serial_open(True):
                self.pb_connect.setText('Connected')
                self.pb_connect.setStyleSheet(self.MY_GREEN)
                self.pb_start.setEnabled(True)
                self.send_command('E')
                self.send_command('V')
                self.sensor_poll_timer.start(SENSOR_POLL_MS)
                self._clear_alert(force=True)
                self.statusBar().showMessage('Connected — ready to start.', 5000)
            else:
                self.pb_connect.setText('Port Error')
                self.pb_connect.setStyleSheet(self.MY_RED)
                self.pb_start.setEnabled(False)
                self._set_alert('Could not open {0}: {1}'.format(
                    self.le_port.text().strip(), self.serial.errorString()))
        else:
            if self.pb_start.text() == 'Running':
                self.start_stop()
            self.sensor_poll_timer.stop()
            self.serial_open(False)
            self._clear_fw_identity()
            self.pb_connect.setText('Not Connected')
            self.pb_connect.setStyleSheet(self.MY_YELLOW)
            self.pb_start.setEnabled(False)
            self.statusBar().showMessage('Disconnected.', 5000)

    def start_stop(self):
        # Start or stop measurement.
        if not self.serial.isOpen():
            self._set_alert('Connect to the board before starting.')
            return
        if self.pb_start.text() != 'Running':
            self.pb_start.setText('Running')
            self.pb_start.setStyleSheet(self.MY_GREEN)

            self.setup_file_logging()  # Ensure a file is opened when starting
            self.send_command('S')
            self.change_parameters()
            if self.pb_boxcar_mode.isChecked():
                self.series_raw_mean.clear()
                self.raw_poll_timer.start(250)
        else:
            self.pb_start.setText('Stopped')
            self.pb_start.setStyleSheet(self.MY_YELLOW)
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

    def poll_sensors(self):
        # 'V' identify — cheap, legal in both modes, and its trailing fields are
        # the freshest pack / board-temp / lockout state the firmware holds
        # (it re-samples both at 1 Hz but only reports 'P' every 60 s).
        if self.serial.isOpen():
            self.serial.write(b'V\n')

    def v_div(self, direction):
        # Adjust vertical division scale via button group.
        ix = self.VoltageButtonGroup.checkedId()
        ix = ix + 1 if direction == 'up' else ix - 1
        # Clamp the value between -11 and -2
        ix = max(-11, min(-2, ix))
        self.VoltageButtonGroup.button(ix).setChecked(True)

    def h_div(self, direction):
        # Adjust horizontal division scale via button group.
        ix = self.TimeButtonGroup.checkedId()
        ix = ix + 1 if direction == 'up' else ix - 1
        # Clamp the value between -7 and -2
        ix = max(-7, min(-2, ix))
        self.TimeButtonGroup.button(ix).setChecked(True)

    def change_parameters(self):
        # Read from QLineEdit fields (authoritative) and send configuration command.
        try:
            freq_hz = int(float(self.lFreq.text()))
        except ValueError:
            freq_hz = int(round(self.frequency * 1000))
        try:
            pulse_us = float(self.lPulse.text())
        except ValueError:
            pulse_us = self.pulse_width
        try:
            delay_us = float(self.lSample.text())
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
        # A new config retires the firmware's complaint about the old one; if
        # this one is bad too, the board says so again within a round trip.
        self._clear_alert()
        self.send_command(command_str)

    def serial_open(self, flag):
        # Open (if flag is True) or close the serial port.
        # Returns True if successful.
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

    def read_from_serial(self):
        lines = []
        while self.serial.canReadLine():
            data = self.serial.readLine().data().decode('utf-8', errors='replace').rstrip()
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

            if p_voltage < 2.1 * 1_000_000:
                self.luV.setStyleSheet(self.MY_YELLOW)
            elif p_voltage > 3.5 * 1_000_000:
                self.luV.setStyleSheet(self.MY_RED)
            else:
                self.luV.setStyleSheet(self.MY_GREEN)

            self.luV.setText('{:9,.3f} mV '.format(p_voltage / 1000))
            self.luVsd.setText('{:12,d} uV '.format(p_stddev))

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

        elif line.startswith('P'):
            # Unsolicited pack / board-temp telemetry (firmware v4.28+):
            # P<time_ms>,<pack_mV>,<board_temp_dC>
            parts = line[1:].split(',')
            try:
                self._update_sensors(int(parts[1]), int(parts[2]))
            except (IndexError, ValueError) as e:
                print('Sensor packet parsing error:', e)

        elif line.startswith('V'):
            # Identify response. Fields 0 and 1 are the firmware version and the
            # board ID — present on every revision, so they are read ahead of the
            # field-count guard (v4.15). Fields 8..10 are pack_mV / board_temp_dC
            # / lockout (firmware v4.28+); older firmware sends 8 fields and is
            # left with the gauges blank.
            parts = line[1:].split(',')
            # Unlike the transient parse-error prints elsewhere here, a bad value
            # would sit in the label indefinitely, so require it to look like a
            # version before showing it.
            if parts and parts[0].replace('.', '').isdigit():
                self._update_fw_identity(parts[0],
                                         parts[1] if len(parts) > 1 else None)
            if len(parts) >= 11:
                try:
                    self._update_sensors(int(parts[8]), int(parts[9]),
                                         bool(int(parts[10])))
                except ValueError as e:
                    print('Identify parsing error:', e)

        elif line.startswith('W'):
            return  # Mode 2 stream record — silently ignore in Mode 1 GUI

        elif line.startswith('Command Input ERROR') or line.startswith('LOCKOUT'):
            # Firmware complaint — a rejected pulse config, or the v4.28
            # low-voltage failsafe latching. Both need saying out loud.
            lockout = 'lockout' in line or line.startswith('LOCKOUT')
            self._set_alert(line, sticky=lockout)
            if lockout:
                self.pack_lockout = True
                self.gauge_pack.set_reading(self.pack_mV, True)
                if self.pb_start.text() == 'Running':
                    self.start_stop()

    def _update_sensors(self, pack_mV, board_temp_dC, lockout=None):
        """Apply a pack / board-temp reading to the gauges and the session log.

        board_temp_dC may be the firmware's "no reading" sentinel (fw v4.33+, see
        TEMP_INVALID_MAX_DC). That is resolved to None once, here, so neither the gauge
        nor the log ever sees the raw sentinel: BarGauge already renders None as '—',
        and the log gets the word 'none' rather than a number that a later reader would
        have no way to tell from a temperature."""
        self.pack_mV = pack_mV
        valid_temp = board_temp_dC > TEMP_INVALID_MAX_DC
        self.board_temp_dC = board_temp_dC if valid_temp else None
        if lockout is not None:
            # 'V' says the latch has dropped — retire the sticky lockout alert.
            if self.pack_lockout and not lockout:
                self._clear_alert(force=True)
            self.pack_lockout = lockout
        self.gauge_pack.set_reading(pack_mV, self.pack_lockout)
        # Sub-zero readings are legal (the part goes to -55 °C) and BarGauge clamps the
        # bar fraction to [0, 1], so they show as an empty bar with the correct negative
        # number printed. Deliberate: the number is the reading, the bar is the glance.
        self.gauge_temp.set_value(board_temp_dC / 10.0 if valid_temp else None)
        if self.file:
            try:
                self.file.write('# sensor: {0}, pack_mV={1}, board_temp_dC={2}\n'.format(
                    datetime.now().isoformat(timespec='seconds'), pack_mV,
                    board_temp_dC if valid_temp else 'none'))
            except Exception as e:
                print('File write error (sensor line):', e)

    def _update_fw_identity(self, fw_version, board_id=None):
        """Show the MCU firmware version reported by the 'V' identify reply."""
        self.fw_version = fw_version
        self.board_id = board_id
        self.lbl_fw.setText('v' + fw_version)
        self.lbl_fw.setToolTip(FW_LABEL_TOOLTIP
                               + ('\nBoard ID: ' + board_id if board_id else ''))

    def _clear_fw_identity(self):
        """Forget the board's identity on disconnect, so a stale version cannot
        outlive the connection it came from."""
        self.fw_version = None
        self.board_id = None
        self.lbl_fw.setText('—')
        self.lbl_fw.setToolTip(FW_LABEL_TOOLTIP)

    def _set_alert(self, text, sticky=False):
        """Post (or clear) the alert row. Non-sticky text self-clears after
        ALERT_CLEAR_MS; sticky is for a latched lockout, which is a standing
        condition rather than a one-off complaint."""
        self.lbl_alert.setText(text)
        self.lbl_alert.setToolTip(text)
        self._alert_sticky = bool(text) and sticky
        self.alert_clear_timer.stop()
        if text and not sticky:
            self.alert_clear_timer.start(ALERT_CLEAR_MS)

    def _clear_alert(self, force=False):
        """Retire the current alert. A sticky (lockout) alert survives unless
        forced — only a reconnect or the firmware dropping the latch clears it."""
        if self._alert_sticky and not force:
            return
        self._set_alert('')

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

        self.chart_view.setChart(self.chart)
        self.chart_view.show()

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
            freq = (1 / (self.update_delay /1000)) * int(self.pbFactor.text()) / 1000
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

        self.statusBar().showMessage(
                f"Last command: {self.last_command:<20} | "
                f"Incoming packet: {self.last_packet:<60} | "
                f"{raw_status}"
                f"Rx freq: {freq:>4.1f} kHz | "
                f"SPS: {SPS:>4.1f} "
            )

    def vert_scale(self):
        # Called when the vertical scale button group changes.
        i = self.VoltageButtonGroup.checkedId()
        self.v_scale = self.vert_scales[i] * 10
        if self.v_scale == 5000:
            self.axis_z.setRange(0, 5)
            self.uVlabel.setText('V / div')
        elif self.v_scale <= 5:
            self.axis_z.setRange(-self.v_scale / 2 * 1000, self.v_scale / 2 * 1000)
            self.uVlabel.setText('uV / div')
        else:
            self.axis_z.setRange(-self.v_scale / 2, self.v_scale / 2)
            self.uVlabel.setText('mV / div')
        self.update_vert_scale = True

    def horiz_scale(self):
        # Called when the horizontal scale button group changes.
        i = self.TimeButtonGroup.checkedId()
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
        if not checked and self.series_raw_mean is not None:
            self.series_raw_mean.clear()

    def _on_toggle_boxcar_mode(self, checked):
        self.pb_boxcar_mode.setText('Boxcar: ON' if checked else 'Boxcar: OFF')
        self.pb_boxcar_mode.setStyleSheet(self.MY_GREEN if checked else self.MY_YELLOW)
        if self.series_raw_mean is None:
            return
        if checked:
            if self.pb_start.text() == 'Running':
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

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------
    def _load_settings(self):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            self.le_port.setText(s.get('port', DEFAULT_PORT))
            # Frequency — snap slider to nearest clean freq, then set exact text
            freq_hz  = int(s.get('freq_hz', 10000))
            freq_khz = freq_hz / 1000
            sl_freq  = min(range(len(CLEAN_FREQS_KHZ)),
                          key=lambda i: abs(CLEAN_FREQS_KHZ[i] - freq_khz))
            self.slFreq.setValue(sl_freq)
            self._set_freq_display(freq_hz)
            # Pulse width
            pulse_us = float(s.get('pulse_us', 20.0))
            sl_pulse = max(self.slPulse.minimum(),
                           min(self.slPulse.maximum(), round(pulse_us * NS_PER_COUNT_INV)))
            self.slPulse.setValue(sl_pulse)
            self._set_pulse_display(pulse_us)
            # Sample delay
            delay_us  = float(s.get('delay_us', 10.0))
            sl_sample = max(self.slSample.minimum(),
                            min(self.slSample.maximum(), round(delay_us * NS_PER_COUNT_INV)))
            self.slSample.setValue(sl_sample)
            self._set_delay_display(delay_us)
            # Downsample factor
            ds = int(s.get('down_sample', 256))
            self.down_sample = ds
            self.pbFactor.setText(str(ds))
            # Avg n
            avg_n = max(1, min(1000, int(s.get('avg_n', 64))))
            self.avg_n = avg_n
            self.le_avg_n.setText(str(avg_n))
            self._check_avg_n_warning()
            # Toggle buttons
            self.pb_boxcar_mode.setChecked(bool(s.get('boxcar_on', True)))
            self.pb_show_raw_mean.setChecked(bool(s.get('raw_avg_on', True)))
            # V/div and H/div button groups
            btn_v = self.VoltageButtonGroup.button(int(s.get('v_div_id', -2)))
            if btn_v:
                btn_v.setChecked(True)
            btn_h = self.TimeButtonGroup.button(int(s.get('h_div_id', -2)))
            if btn_h:
                btn_h.setChecked(True)
            # Window geometry
            w = int(s.get('window_w', 1200))
            h = int(s.get('window_h', 900))
            self.resize(w, h)
            x, y = s.get('window_x'), s.get('window_y')
            if x is not None and y is not None:
                self.move(int(x), int(y))
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            pass  # First run — keep apply_soc_defaults() values

    def _save_settings(self):
        try:
            freq_hz = int(float(self.lFreq.text()))
        except ValueError:
            freq_hz = int(round(self.frequency * 1000))
        try:
            pulse_us = float(self.lPulse.text())
        except ValueError:
            pulse_us = self.pulse_width
        try:
            delay_us = float(self.lSample.text())
        except ValueError:
            delay_us = self.sample_delay
        s = {
            'port':        self.le_port.text(),
            'freq_hz':     freq_hz,
            'pulse_us':    pulse_us,
            'delay_us':    delay_us,
            'down_sample': self.down_sample,
            'avg_n':       self.avg_n,
            'boxcar_on':   self.pb_boxcar_mode.isChecked(),
            'raw_avg_on':  self.pb_show_raw_mean.isChecked(),
            'v_div_id':    self.VoltageButtonGroup.checkedId(),
            'h_div_id':    self.TimeButtonGroup.checkedId(),
            'window_w':    self.width(),
            'window_h':    self.height(),
            'window_x':    self.x(),
            'window_y':    self.y(),
        }
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(s, f, indent=2)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._save_settings()
        self.raw_poll_timer.stop()
        self.sensor_poll_timer.stop()
        self.alert_clear_timer.stop()
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
