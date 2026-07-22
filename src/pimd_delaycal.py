# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
# ###############################################################################
# PIMD Delay Calibration v1.25
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
#   *<freq_hz>,<pulse_ns>,<delay_ns>,256   — configure PWM (no streaming)
#   A<n>                                   — raw boxcar average; returns R record
#   D<avg>;<freq_hz>,<pulse_us>,<d0>,...;… — define dynamic profile (thermal mode)
#   Q<n>                                   — select profile
#   G                                      — start Mode 2 streaming
#
# History (full detail in CHANGELOG.md):
#   v1.25 APP_VERSION constant re-synced with header (was stuck at 1.19)
#   v1.24 Auto Nudge zigzag respects the signal-detect ceiling (down-only past it)
#   v1.23 sp_auto_max_iter range 1-20 -> 1-100
#   v1.22 Auto Nudge (parallel) locks a channel's delay once it passes threshold
#   v1.21 _auto_nudge_channel log lines prefixed with channel label
#   v1.20 voltage headers to 3 d.p.; Auto Nudge expanding-zigzag from calibrated delay
#   v1.19 Auto Nudge parallel/sequential toggle
#   v1.18 draggable QSplitter between left/right panes
#   v1.17 thermal tables sorted ascending by pulse_us
#   v1.16 row labels: freq in Hz with separator, pulse in µs 1 d.p.
#   v1.15 coarse+fine two-phase sweep per freq/pulse pair
#   v1.14 thermal tables dynamic minimumHeight (all rows visible)
#   v1.13 "Latest delay" label; splitter stretch (1,0); thermal min-height raise
#   v1.12 QSplitter above monitoring; splitter/geometry persistence; unified cell colouring
#   v1.11 post-nudge 1 s settling gate before std-dev accumulation
#   v1.10 wider left column/window; Live Monitoring & Auto Nudge box; settings persistence
#   v1.09 real-time cell colouring during Auto Nudge; Import Profile button
#   v1.08 scrolling activity log; Auto Nudge sequential per-channel
#   v1.07 Auto Nudge: iterative per-cell delay correction
#   v1.06 * command updated to MCU v4.23 protocol (Hz/ns)
#   v1.05 snap threshold-crossing delays to the 8 ns PWM grid; 3 d.p.
#   v1.04 thermal std dev to 2 d.p.
#   v1.03 profile export (classviz JSON) + thermal monitoring mode
#   v1.02 fix double-send bug in _on_r_record/_check_thresholds
#   v1.01 freq and pulse width paired as tuples (e.g. 25/10)
#   v1.00 initial version
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
    QApplication, QCheckBox, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QDoubleSpinBox, QSpinBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QGroupBox, QFormLayout,
    QFileDialog, QHeaderView, QPlainTextEdit, QSplitter,
)
from PyQt6.QtSerialPort import QSerialPort  # noqa: E402
from PyQt6.QtCore import QIODevice, Qt, QTimer  # noqa: E402
from PyQt6.QtGui import QColor  # noqa: E402

APP_VERSION = '1.25'

DYNAMIC_PROFILE_INDEX = 5   # matches pimd_mcu.py NUM_PROFILES / pimd_classviz.py
PROFILES_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'data', 'profiles')
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'data', 'delaycal_settings.json')

def _snap_8ns(delay_us):
    """Round a delay to the nearest 8 ns RP2040 PWM clock boundary."""
    ns = round(delay_us * 1000)          # µs → ns, integer
    return (round(ns / 8) * 8) / 1000   # snap to 8 ns grid, back to µs


# Cell background colours
_COL_PENDING      = QColor(200, 220, 255)   # light blue: in progress (calibration sweep)
_COL_DONE         = QColor(143, 240, 164)   # green:      threshold found / auto passed
_COL_NR           = QColor(210, 210, 210)   # grey:       not reached within max delay
_COL_AUTO_FLAGGED = QColor(246, 97, 81)     # red:        still bad after Auto max attempts
_COL_AUTO_QUEUED  = QColor(249, 240, 107)   # yellow:     bad channel queued for nudging
_COL_AUTO_WORKING = QColor(255, 175,  50)   # amber:      channel currently being soaked
_COL_AUTO_DRIFTED = QColor(186, 156, 214)   # lavender:   locked-good channel now reading above
                                             # threshold — frozen, not re-nudged


class MainWindow(QMainWindow):
    MY_GREEN  = 'background-color: rgb(143, 240, 164);'
    MY_YELLOW = 'background-color: rgb(249, 240, 107);'
    MY_RED    = 'background-color: rgb(246, 97, 81);'

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'PIMD Delay Calibration v{APP_VERSION} by Mark Makies')

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
        self._coarse_phase = False  # True during coarse hunt; False during fine sweep
        self._coarse_step  = 1.0   # µs — snapshot of sp_coarse_step at run time
        self._signal_uV    = 4_900_000  # µV — snapshot of sp_signal_v at run time

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
        self._thermal_display_order: list = []  # display_row → protocol_band (asc pulse_us)
        self._thermal_proto_to_display: dict = {}  # protocol_band → display_row

        # Auto Nudge state
        # Two modes (toggled by cb_sequential):
        #   Parallel  (default): all bad channels nudged together each iteration.
        #   Sequential          : one bad channel at a time, up to max_attempts each.
        self._auto_parallel = True          # False when Sequential checkbox is ticked
        self._auto_iter     = 0             # parallel mode iteration counter
        self._auto_state            = 'idle'    # 'idle' | 'soaking'
        self._auto_phase            = 'initial' # 'initial' | 'channel'
        self._auto_targets:  'list[int]' = []   # ordered bad-channel indices (set after initial eval)
        self._auto_target_idx        = 0        # index of current channel in _auto_targets
        self._auto_ch_attempts       = 0        # nudge attempts on current channel
        self._auto_cur_profile: 'dict | None' = None
        self._auto_cal_delays_flat: 'list[float]' = []  # calibrated delays µs, per channel
        self._auto_cur_delays_flat: 'list[float]' = []  # working delays µs, per channel
        self._auto_attempt_flat:    'list[int]'   = []  # nudge attempt count per channel (drives zigzag)
        self._auto_ceiling_flat:    'list[bool]'  = []  # True once mean_v hit sp_signal_v ceiling — down-only from here
        self._auto_down_mult_flat:  'list[int]'   = []  # next down-only nudge magnitude, once ceiling hit
        self._auto_locked_flat:     'list[bool]'  = []  # True once channel first passed (parallel mode only)
        self._auto_skip_flat:       'list[bool]'  = []  # True for N/R cells (excluded)
        self._auto_best_std_uV:     'list[float]' = []  # min std dev seen µV per channel
        self._auto_best_delays_flat:'list[float]' = []  # delay at best std per channel
        self._auto_soak_timer: 'QTimer | None' = None
        self._auto_running  = False         # True from _start_auto to _auto_finish/_stop_auto
        self._auto_settling = False         # True for 1 s after each G command; discards W records

        self._build_ui()
        self._load_settings()

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

        self.pb_import_profile = QPushButton('Import Profile')
        self.pb_import_profile.setFixedWidth(110)
        self.pb_import_profile.clicked.connect(self._import_profile)
        top.addWidget(self.pb_import_profile)

        top.addSpacing(10)
        self.status_label = QLabel('Connect the board to begin.')
        top.addWidget(self.status_label, stretch=1)

        root.addLayout(top)

        # Content row: config+log left, results right — horizontal splitter
        self.h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left column: config panel + activity log ──────────────────
        left_w = QWidget()
        left_col = QVBoxLayout(left_w)
        left_col.setSpacing(4)
        left_col.setContentsMargins(0, 0, 4, 0)

        cfg_box = QGroupBox('Configuration')
        cfg_box.setMinimumWidth(300)
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
        form.addRow('Fine step:', self.sp_step)

        self.sp_coarse_step = QDoubleSpinBox()
        self.sp_coarse_step.setRange(0.1, 50.0)
        self.sp_coarse_step.setSingleStep(0.1)
        self.sp_coarse_step.setValue(1.0)
        self.sp_coarse_step.setSuffix(' us')
        self.sp_coarse_step.setDecimals(1)
        self.sp_coarse_step.setToolTip(
            'Coarse hunt step per pair: sweeps from start delay in large steps\n'
            'until the signal drops below "Signal detect V", then backs up to\n'
            'the last clean coarse position and switches to the fine step.')
        form.addRow('Coarse step:', self.sp_coarse_step)

        self.sp_signal_v = QDoubleSpinBox()
        self.sp_signal_v.setRange(0.1, 5.0)
        self.sp_signal_v.setSingleStep(0.1)
        self.sp_signal_v.setValue(4.9)
        self.sp_signal_v.setSuffix(' V')
        self.sp_signal_v.setDecimals(1)
        self.sp_signal_v.setToolTip(
            'Voltage below which a real signal is considered present.\n'
            'Coarse hunt advances until a reading falls below this value.')
        form.addRow('Signal detect:', self.sp_signal_v)

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

        self.le_fp_pairs = QLineEdit('25/10, 20/20, 5/40')
        self.le_fp_pairs.setToolTip(
            'Comma-separated freq/pulse pairs (kHz/µs)\n'
            'e.g.  25/10, 20/20, 5/40')
        form.addRow('Freq/Pulse (kHz/us):', self.le_fp_pairs)

        self.le_targets = QLineEdit('4.5, 4.0, 3.5, 3.0, 2.5, 2.0, 1.5, 1.0, 0.5')
        form.addRow('Targets (V):', self.le_targets)

        left_col.addWidget(cfg_box)

        # Activity log
        log_box_grp = QGroupBox('Activity Log')
        log_layout = QVBoxLayout(log_box_grp)
        log_layout.setContentsMargins(4, 4, 4, 4)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(160)
        self.log_box.setPlaceholderText('Activity log…')
        log_layout.addWidget(self.log_box)

        left_col.addWidget(log_box_grp, stretch=1)
        # ─────────────────────────────────────────────────────────────

        # Results area
        right_w = QWidget()
        right = QVBoxLayout(right_w)
        right.setSpacing(4)
        right.setContentsMargins(4, 0, 0, 0)

        # Calibration table container (upper splitter pane)
        cal_container = QWidget()
        cal_layout = QVBoxLayout(cal_container)
        cal_layout.setContentsMargins(0, 0, 0, 0)
        cal_layout.setSpacing(4)

        self.progress_label = QLabel('Ready — configure parameters and press Run.')
        cal_layout.addWidget(self.progress_label)

        lbl_cal = QLabel('Latest delay (us):')
        lbl_cal.setStyleSheet('font-weight: bold;')
        cal_layout.addWidget(lbl_cal)

        self.table = QTableWidget(0, 0)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers)
        cal_layout.addWidget(self.table, stretch=1)

        # ── Live monitoring + Auto Nudge section ─────────────────────
        therm_grp = QGroupBox('Live Monitoring & Auto Nudge')
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
        self.sp_thermal_n.setToolTip(
            'Rolling window (frames) for std dev — shared by Thermal and Auto Nudge.\n'
            'Keep ≤ 200 with Auto: at ~100 Hz W-rate, N=200 ≈ 2 s; thermal drift\n'
            '(~50 µV/s) contributes ~100 µV — well below the 500 µV default threshold.')
        ctrl.addWidget(self.sp_thermal_n)

        self.lbl_thermal_status = QLabel('')
        ctrl.addWidget(self.lbl_thermal_status, stretch=1)

        therm_layout.addLayout(ctrl)

        lbl_mean = QLabel('Latest mean (mV):')
        lbl_mean.setStyleSheet('font-weight: bold;')
        therm_layout.addWidget(lbl_mean)

        self.tbl_thermal_mean = QTableWidget(0, 0)
        self.tbl_thermal_mean.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_thermal_mean.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.tbl_thermal_mean.setMinimumHeight(120)
        therm_layout.addWidget(self.tbl_thermal_mean, stretch=1)

        lbl_std = QLabel('Std dev (mV):')
        lbl_std.setStyleSheet('font-weight: bold;')
        therm_layout.addWidget(lbl_std)

        self.tbl_thermal_std = QTableWidget(0, 0)
        self.tbl_thermal_std.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_thermal_std.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        self.tbl_thermal_std.setMinimumHeight(120)
        therm_layout.addWidget(self.tbl_thermal_std, stretch=1)

        # ── Auto Nudge sub-section ────────────────────────────────────
        sep_lbl = QLabel('── Auto Nudge ──')
        sep_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        therm_layout.addWidget(sep_lbl)

        auto_row1 = QHBoxLayout()
        auto_row1.setSpacing(6)

        self.pb_auto = QPushButton('Auto')
        self.pb_auto.setFixedWidth(70)
        self.pb_auto.setEnabled(False)
        self.pb_auto.clicked.connect(self._start_auto)
        auto_row1.addWidget(self.pb_auto)

        self.pb_auto_stop = QPushButton('Stop Auto')
        self.pb_auto_stop.setFixedWidth(80)
        self.pb_auto_stop.setEnabled(False)
        self.pb_auto_stop.clicked.connect(self._stop_auto)
        auto_row1.addWidget(self.pb_auto_stop)

        auto_row1.addSpacing(8)
        auto_row1.addWidget(QLabel('Soak:'))
        self.sp_auto_soak_s = QSpinBox()
        self.sp_auto_soak_s.setRange(5, 600)
        self.sp_auto_soak_s.setValue(20)
        self.sp_auto_soak_s.setSuffix(' s')
        self.sp_auto_soak_s.setFixedWidth(70)
        auto_row1.addWidget(self.sp_auto_soak_s)

        auto_row1.addSpacing(8)
        self.lbl_max_att = QLabel('Max iterations:')
        auto_row1.addWidget(self.lbl_max_att)
        self.sp_auto_max_iter = QSpinBox()
        self.sp_auto_max_iter.setRange(1, 100)
        self.sp_auto_max_iter.setValue(5)
        self.sp_auto_max_iter.setFixedWidth(50)
        self.sp_auto_max_iter.setToolTip(
            'Parallel: max nudge iterations before flagging remaining bad channels.\n'
            'Sequential: max nudge attempts per channel before flagging it and moving on.')
        auto_row1.addWidget(self.sp_auto_max_iter)

        auto_row1.addSpacing(8)
        self.cb_sequential = QCheckBox('Sequential')
        self.cb_sequential.setToolTip(
            'Unchecked (default): Parallel — all bad channels nudged together each\n'
            'iteration; faster for production use.\n'
            'Checked: Sequential — one bad channel at a time; useful for debugging.')
        self.cb_sequential.toggled.connect(self._on_auto_mode_toggled)
        auto_row1.addWidget(self.cb_sequential)

        self.lbl_auto_status = QLabel('')
        auto_row1.addWidget(self.lbl_auto_status, stretch=1)

        therm_layout.addLayout(auto_row1)

        auto_row2 = QHBoxLayout()
        auto_row2.setSpacing(6)

        auto_row2.addWidget(QLabel('Threshold:'))
        self.sp_auto_threshold_mv = QDoubleSpinBox()
        self.sp_auto_threshold_mv.setRange(0.01, 100.0)
        self.sp_auto_threshold_mv.setValue(0.5)
        self.sp_auto_threshold_mv.setSuffix(' mV')
        self.sp_auto_threshold_mv.setDecimals(2)
        self.sp_auto_threshold_mv.setFixedWidth(90)
        auto_row2.addWidget(self.sp_auto_threshold_mv)

        auto_row2.addSpacing(8)
        auto_row2.addWidget(QLabel('Nudge:'))
        self.sp_auto_nudge_ns = QSpinBox()
        self.sp_auto_nudge_ns.setRange(8, 960)
        self.sp_auto_nudge_ns.setSingleStep(8)
        self.sp_auto_nudge_ns.setValue(80)
        self.sp_auto_nudge_ns.setSuffix(' ns')
        self.sp_auto_nudge_ns.setFixedWidth(80)
        self.sp_auto_nudge_ns.setToolTip(
            'Step magnitude (ns, multiple of 8 ns PWM grid).\n'
            'Applied as −N first toward earlier delays; flips to +N on cap hit.')
        auto_row2.addWidget(self.sp_auto_nudge_ns)

        auto_row2.addSpacing(8)
        auto_row2.addWidget(QLabel('Cap ±:'))
        self.sp_auto_cap_ns = QSpinBox()
        self.sp_auto_cap_ns.setRange(8, 9600)
        self.sp_auto_cap_ns.setSingleStep(8)
        self.sp_auto_cap_ns.setValue(960)
        self.sp_auto_cap_ns.setSuffix(' ns')
        self.sp_auto_cap_ns.setFixedWidth(90)
        self.sp_auto_cap_ns.setToolTip(
            'Max total deviation from calibrated delay in either direction.\n'
            'At ~115 mV/80 ns slope, 960 ns cap ≈ 1.4 V shift from target voltage.')
        auto_row2.addWidget(self.sp_auto_cap_ns)

        auto_row2.addStretch()
        therm_layout.addLayout(auto_row2)
        # ─────────────────────────────────────────────────────────────

        # Vertical splitter: cal table (top, 2×) | monitoring + nudge (bottom, 1×)
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.addWidget(cal_container)
        self.v_splitter.addWidget(therm_grp)
        self.v_splitter.setStretchFactor(0, 1)
        self.v_splitter.setStretchFactor(1, 0)
        right.addWidget(self.v_splitter, stretch=1)

        self.h_splitter.addWidget(left_w)
        self.h_splitter.addWidget(right_w)
        self.h_splitter.setStretchFactor(0, 0)
        self.h_splitter.setStretchFactor(1, 1)
        root.addWidget(self.h_splitter, stretch=1)

        self.setCentralWidget(central)
        self.statusBar().showMessage('Not connected')

    # ------------------------------------------------------------------
    # Activity log
    # ------------------------------------------------------------------
    def _log(self, msg: str):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_box.appendPlainText(f'[{ts}] {msg}')

    def _ch_label(self, ch: int) -> str:
        """Map flat channel index to 'ch{N} [band/target_V]' for log readability."""
        if (not self._fp_pairs or not self._targets_v
                or self._thermal_n_cells == 0):
            return f'ch{ch}'
        b = ch // self._thermal_n_cells
        c = ch  % self._thermal_n_cells
        band = (self._row_label(*self._fp_pairs[b])
                if b < len(self._fp_pairs) else f'b{b}')
        volt = (f'{self._targets_v[c]:.1f}V'
                if c < len(self._targets_v) else f'c{c}')
        return f'ch{ch} [{band}/{volt}]'

    def _auto_color_cell(self, ch: int, color: QColor):
        """Set the same background colour on all three tables for a flat channel index."""
        if self._thermal_n_cells == 0:
            return
        b = ch // self._thermal_n_cells
        c = ch  % self._thermal_n_cells
        cal_item = self.table.item(b, c)
        if cal_item:
            cal_item.setBackground(color)
        d = self._thermal_proto_to_display.get(b, b)
        for tbl in (self.tbl_thermal_mean, self.tbl_thermal_std):
            item = tbl.item(d, c)
            if item:
                item.setBackground(color)

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
            self._stop_auto()
            self._stop_thermal()
            self._serial_open(False)
            self.pb_connect.setText('Not Connected')
            self.pb_connect.setStyleSheet(self.MY_YELLOW)
            self.pb_run.setEnabled(False)
            self._log('Disconnected.')
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

            if (self._thermal_state == 'running' or self._auto_state == 'soaking') \
                    and raw.startswith('W'):
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
                raise ValueError(f'Non-numeric freq/pulse pair "{token}"')
            if freq_khz <= 0 or pulse_us <= 0:
                raise ValueError(f'Freq and pulse must be positive (got "{token}")')
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
        freq_hz = round(freq_khz * 1000)
        return f'{freq_hz:,}Hz / {pulse_us:.1f}us'

    def _rebuild_table(self, fp_pairs, targets_v):
        self.table.clear()
        self.table.setRowCount(len(fp_pairs))
        self.table.setColumnCount(len(targets_v))
        self.table.setVerticalHeaderLabels(
            [self._row_label(f, p) for f, p in fp_pairs])
        self.table.setHorizontalHeaderLabels([f'{v:.3f} V' for v in targets_v])
        for r in range(len(fp_pairs)):
            for c in range(len(targets_v)):
                item = QTableWidgetItem('')
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, item)

    def _mark_row_pending(self, row):
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
        self._start_delay  = self.sp_start.value()
        self._step_size    = self.sp_step.value()
        self._coarse_step  = self.sp_coarse_step.value()
        self._signal_uV    = int(round(self.sp_signal_v.value() * 1_000_000))
        self._step_count   = 0
        self._delay        = self._start_delay
        self._prev_delay   = None
        self._prev_uV      = None
        self._coarse_phase = (self._coarse_step > self._step_size)
        self._state        = 'sweeping'

        self._rebuild_table(fp_pairs, targets_v)
        self._mark_row_pending(0)

        self.pb_run.setEnabled(False)
        self.pb_stop.setEnabled(True)
        self.pb_export.setEnabled(False)
        self.pb_export_profile.setEnabled(False)
        self.pb_thermal.setEnabled(False)
        self.pb_auto.setEnabled(False)

        self._log(f'Starting calibration — {len(fp_pairs)} pair(s), '
                  f'{len(targets_v)} threshold(s)')
        self.send_command('E')
        self._send_next_step()

    def _send_next_step(self):
        if self._state != 'sweeping':
            return

        freq, pulse = self._fp_pairs[self._pair_idx]
        n = self.sp_avg.value()

        if self._delay > self.sp_max.value():
            self._mark_remaining_nr()
            self._advance_pair()
            return

        phase_tag = 'COARSE' if self._coarse_phase else '→'
        self._log(f'{phase_tag} {self._row_label(freq, pulse)}  delay {self._delay:.3f} µs')
        self.send_command(f'*{int(round(freq * 1000))},{int(round(pulse * 1000))},{int(round(self._delay * 1000))},256')
        self.send_command(f'A{n}')

        if self._coarse_phase:
            self.progress_label.setText(
                f'{self._row_label(freq, pulse)} | Coarse scan — delay {self._delay:.2f} µs')
        else:
            total = len(self._fp_pairs) * len(self._thresholds)
            done  = self._pair_idx * len(self._thresholds) + self._thresh_idx
            self.progress_label.setText(
                f'{self._row_label(freq, pulse)} | Delay {self._delay:.2f} us | '
                f'{done}/{total} thresholds found')

    def _on_r_record(self, line):
        if self._state != 'sweeping':
            return
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

        current_delay = self._delay

        # ── Coarse hunt ───────────────────────────────────────────────
        if self._coarse_phase:
            if mean_uV >= self._signal_uV:
                # No signal yet — advance by coarse step
                self._prev_delay = current_delay
                self._prev_uV    = mean_uV
                self._delay      = round(current_delay + self._coarse_step, 6)
            else:
                # Signal detected — back up to last clean coarse position
                # (or start_delay when signal appeared on the very first step)
                backup = (self._prev_delay
                          if self._prev_delay is not None
                          else self._start_delay)
                self._coarse_phase = False
                self._delay        = backup
                self._step_count   = round((backup - self._start_delay) / self._step_size)
                self._prev_delay   = None
                self._prev_uV      = None
                self._log(f'  Signal at {current_delay:.3f} µs — '
                          f'backing up to {backup:.3f} µs for fine sweep')
            self._send_next_step()
            return

        # ── Fine sweep (existing logic) ───────────────────────────────
        current_pair_idx = self._pair_idx

        self._check_thresholds(mean_uV)

        if self._state == 'sweeping' and self._pair_idx == current_pair_idx:
            self._prev_delay = current_delay
            self._prev_uV    = mean_uV
            self._step_count += 1
            self._delay = round(
                self._start_delay + self._step_count * self._step_size, 6)
            self._send_next_step()

    def _check_thresholds(self, mean_uV):
        while self._thresh_idx < len(self._thresholds):
            target_uV = self._thresholds[self._thresh_idx]
            if mean_uV > target_uV:
                break

            if (self._prev_uV is not None
                    and self._prev_uV > target_uV
                    and self._prev_uV != mean_uV):
                frac = (self._prev_uV - target_uV) / (self._prev_uV - mean_uV)
                interp = self._prev_delay + frac * (self._delay - self._prev_delay)
            else:
                interp = self._delay
            interp = _snap_8ns(interp)

            self._log(f'  ✓ {target_uV / 1_000_000:.1f} V at {interp:.3f} µs')
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
        count = len(self._thresholds) - self._thresh_idx
        if count:
            self._log(f'  — {count} threshold(s) not reached within max delay (N/R)')
        for c in range(self._thresh_idx, len(self._thresholds)):
            self._fill_cell(self._pair_idx, c, 'N/R', color=_COL_NR)

    def _advance_pair(self):
        self._pair_idx    += 1
        self._thresh_idx   = 0
        self._step_count   = 0
        self._delay        = self._start_delay
        self._prev_delay   = None
        self._prev_uV      = None
        self._coarse_phase = (self._coarse_step > self._step_size)

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
        self.pb_auto.setEnabled(True)
        self.progress_label.setText('Calibration complete.')
        self.status_label.setText('Done — Export CSV / Export Profile / THERMAL / Auto.')
        self._log('Calibration done.')
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
        self.pb_auto.setEnabled(
            self.serial.isOpen() and self.table.rowCount() > 0 and bool(self._fp_pairs))
        self.progress_label.setText('Stopped.')
        self.status_label.setText('Sweep stopped.')
        self._log('Calibration stopped.')

    # ------------------------------------------------------------------
    # Profile export
    # ------------------------------------------------------------------
    def _build_profile(self):
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

    def _import_profile(self):
        """Load a JSON profile into the calibration table, bypassing a sweep."""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Import Profile', PROFILES_DIR, 'JSON profiles (*.json)')
        if not path:
            return
        try:
            with open(path) as f:
                profile = json.load(f)
            bands = profile.get('bands', [])
            if not bands:
                raise ValueError('No bands in profile.')
            targets_v = bands[0].get('threshold_v')
            if not targets_v:
                raise ValueError('Profile has no threshold_v field.')

            fp_pairs      = [(b['freq_hz'] / 1000.0, b['pulse_us']) for b in bands]
            thresholds_uV = [int(v * 1_000_000) for v in targets_v]

            self._fp_pairs    = fp_pairs
            self._targets_v   = targets_v
            self._thresholds  = thresholds_uV
            self._state       = 'done'

            self._rebuild_table(fp_pairs, targets_v)
            for r, band in enumerate(bands):
                for c, delay in enumerate(band['delays_us']):
                    if c < len(targets_v):
                        self._fill_cell(r, c, f'{delay:.3f}', color=_COL_DONE)

            connected = self.serial.isOpen()
            self.pb_export.setEnabled(True)
            self.pb_export_profile.setEnabled(True)
            self.pb_thermal.setEnabled(connected)
            self.pb_auto.setEnabled(connected)

            name = profile.get('name', os.path.basename(path))
            self.progress_label.setText(
                f'Imported: {name}  ({len(fp_pairs)} band(s), '
                f'{len(targets_v)} threshold(s))')
            self.statusBar().showMessage(f'Profile imported: {os.path.basename(path)}')
            self._log(f'Profile imported: {os.path.basename(path)} '
                      f'— {len(fp_pairs)} band(s), {len(targets_v)} threshold(s)')
        except (KeyError, ValueError, json.JSONDecodeError, OSError) as e:
            self.statusBar().showMessage(f'Import error: {e}')
            self._log(f'Import failed: {e}')

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
        self.pb_auto.setEnabled(False)
        self.lbl_thermal_status.setText(
            f'Running — {int(self._thermal_remaining)} s remaining')
        self._log(f'THERMAL started ({int(self._thermal_remaining)} s)')
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
        self.pb_auto.setEnabled(bool(self._fp_pairs) and self.serial.isOpen())
        self.lbl_thermal_status.setText('Stopped.')
        self._log('THERMAL stopped.')
        self.statusBar().showMessage('Thermal monitoring stopped.')

    def _thermal_tick(self):
        self._thermal_remaining -= 1.0
        if self._thermal_remaining <= 0:
            self.lbl_thermal_status.setText('Complete.')
            self._log('THERMAL complete.')
            self._stop_thermal()
        else:
            self.lbl_thermal_status.setText(
                f'Running — {int(self._thermal_remaining)} s remaining')

    def _rebuild_thermal_tables(self, profile):
        bands = profile['bands']
        # Sort thermal table rows ascending by pulse_us; calibration table stays in
        # protocol (run) order.  _thermal_proto_to_display maps protocol_band → display_row
        # so _auto_color_cell and _update_thermal_tables can stay in sync.
        self._thermal_display_order = sorted(range(len(bands)), key=lambda i: bands[i]['pulse_us'])
        self._thermal_proto_to_display = {b: d for d, b in enumerate(self._thermal_display_order)}
        row_labels = [
            self._row_label(bands[b]['freq_hz'] / 1000, bands[b]['pulse_us'])
            for b in self._thermal_display_order
        ]
        col_labels = [f'{v:.3f} V' for v in self._targets_v]
        n_rows, n_cols = len(row_labels), len(col_labels)

        # Minimum height so all rows are always fully visible (no scrollbar).
        # 28 px header + 30 px per row + 4 px border, floor at 120 px.
        min_h = max(28 + n_rows * 30 + 4, 120)

        for tbl in (self.tbl_thermal_mean, self.tbl_thermal_std):
            tbl.setRowCount(n_rows)
            tbl.setColumnCount(n_cols)
            tbl.setVerticalHeaderLabels(row_labels)
            tbl.setHorizontalHeaderLabels(col_labels)
            tbl.setMinimumHeight(min_h)
            for r in range(n_rows):
                for c in range(n_cols):
                    item = QTableWidgetItem('—')
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    tbl.setItem(r, c, item)

    def _on_thermal_w_record(self, line):
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

        if self._auto_settling:
            return  # discard transition frames until signal settles
        self._thermal_latest = raw
        self._thermal_buf.append(raw)
        self._update_thermal_tables()

    def _update_thermal_tables(self):
        now = time.time()
        if now - self._thermal_last_redraw < 0.1:
            return
        self._thermal_last_redraw = now

        if self._thermal_latest is None:
            return

        latest = self._thermal_latest
        n = self.sp_thermal_n.value()
        recent = list(self._thermal_buf)[-n:]
        threshold_uV = self.sp_auto_threshold_mv.value() * 1000.0

        for d in range(self._thermal_n_bands):
            b  = self._thermal_display_order[d] if self._thermal_display_order else d
            for c in range(self._thermal_n_cells):
                ch = b * self._thermal_n_cells + c

                item_m = self.tbl_thermal_mean.item(d, c)
                if item_m:
                    item_m.setText(str(int(latest[ch] / 1000)))

                item_s = self.tbl_thermal_std.item(d, c)
                if item_s:
                    if len(recent) >= 2:
                        vals   = [frame[ch] for frame in recent]
                        std_uV = _stdev(vals)
                        item_s.setText(f'{std_uV / 1000:.2f}')
                    else:
                        item_s.setText('0.00')

                # Mirror calibration table status colour to both thermal tables
                if self._auto_running:
                    cal_item = self.table.item(b, c)
                    if cal_item:
                        bg = cal_item.background()
                        if item_m:
                            item_m.setBackground(bg)
                        if item_s:
                            item_s.setBackground(bg)

    # ------------------------------------------------------------------
    # Auto Nudge — sequential per-channel processing
    #
    # Phase "initial": one soak with the calibrated profile; all channels
    #   evaluated; bad-channel list built in order.
    # Phase "channel": each bad channel is tackled one at a time.
    #   Per channel: nudge → soak → evaluate that channel.
    #   If pass: advance to next channel.
    #   If fail and attempts < max: nudge again.
    #   If fail and attempts == max: flag channel (keep best-std delay), advance.
    # All channels stream together in every soak (Mode 2 requires multi-cell).
    # ------------------------------------------------------------------
    def _on_auto_mode_toggled(self, sequential: bool):
        self.lbl_max_att.setText('Max att/cell:' if sequential else 'Max iterations:')

    def _start_auto(self):
        if not self.serial.isOpen():
            self.statusBar().showMessage('Not connected.')
            return
        if not self._fp_pairs or not self._targets_v:
            self.statusBar().showMessage('Run calibration first.')
            return

        profile = self._build_profile()
        n_bands = len(profile['bands'])
        if n_bands == 0:
            self.statusBar().showMessage('No calibration bands.')
            return
        n_cells = len(profile['bands'][0]['delays_us'])
        n_ch    = n_bands * n_cells

        if n_ch < 2:
            self.statusBar().showMessage(
                'Auto Nudge requires ≥ 2 channels '
                '(need at least 2 target voltages or freq/pulse pairs).')
            return

        self._thermal_n_bands    = n_bands
        self._thermal_n_cells    = n_cells
        self._thermal_n_channels = n_ch
        self._thermal_buf.clear()
        self._thermal_latest     = None
        self._rebuild_thermal_tables(profile)

        self._auto_cal_delays_flat = [
            profile['bands'][b]['delays_us'][c]
            for b in range(n_bands) for c in range(n_cells)
        ]
        self._auto_cur_delays_flat  = list(self._auto_cal_delays_flat)
        self._auto_attempt_flat     = [0] * n_ch
        self._auto_ceiling_flat     = [False] * n_ch
        self._auto_down_mult_flat   = [0] * n_ch
        self._auto_locked_flat      = [False] * n_ch
        self._auto_best_std_uV      = [float('inf')] * n_ch
        self._auto_best_delays_flat = list(self._auto_cal_delays_flat)

        self._auto_skip_flat = []
        for b in range(n_bands):
            for c in range(n_cells):
                item = self.table.item(b, c)
                text = item.text() if item else ''
                self._auto_skip_flat.append(text in ('N/R', ''))

        self._auto_cur_profile  = profile
        self._auto_phase        = 'initial'
        self._auto_targets      = []
        self._auto_target_idx   = 0
        self._auto_ch_attempts  = 0

        self.pb_auto.setEnabled(False)
        self.pb_auto.setStyleSheet(self.MY_GREEN)
        self.pb_auto_stop.setEnabled(True)
        self.pb_run.setEnabled(False)
        self.pb_thermal.setEnabled(False)
        self.pb_thermal_stop.setEnabled(False)
        self.lbl_thermal_status.setText('Auto running…')

        self._auto_running  = True
        self._auto_parallel = not self.cb_sequential.isChecked()
        self._auto_iter     = 0
        n_active  = sum(1 for s in self._auto_skip_flat if not s)
        mode_str  = 'parallel' if self._auto_parallel else 'sequential'
        att_label = 'max iterations' if self._auto_parallel else 'max attempts/cell'
        self._log(f'Auto Nudge starting [{mode_str}] — {n_ch} channels ({n_active} active), '
                  f'threshold {self.sp_auto_threshold_mv.value():.2f} mV, '
                  f'{att_label} {self.sp_auto_max_iter.value()}')
        self._log('Initial soak to identify bad channels…')
        self._auto_run_soak()

    def _stop_auto(self):
        was_soaking = (self._auto_state == 'soaking')
        if self._auto_soak_timer:
            self._auto_soak_timer.stop()
            self._auto_soak_timer = None
        self._auto_state    = 'idle'
        self._auto_running  = False
        self._auto_settling = False
        if was_soaking and self.serial.isOpen():
            self.send_command('E')
        self.pb_auto.setEnabled(bool(self._fp_pairs) and self.serial.isOpen())
        self.pb_auto.setStyleSheet('')
        self.pb_auto_stop.setEnabled(False)
        self.pb_run.setEnabled(self.serial.isOpen())
        self.pb_thermal.setEnabled(bool(self._fp_pairs))
        self.lbl_thermal_status.setText('')
        if was_soaking:
            self._log('Auto Nudge stopped by user.')
            self.lbl_auto_status.setText('Stopped.')
            self.statusBar().showMessage('Auto Nudge stopped.')

    def _auto_run_soak(self):
        """Push current delays into profile, start Mode 2 stream, arm soak timer."""
        n_cells = self._thermal_n_cells
        for b, band in enumerate(self._auto_cur_profile['bands']):
            band['delays_us'] = [
                self._auto_cur_delays_flat[b * n_cells + c]
                for c in range(n_cells)
            ]

        self._thermal_buf.clear()
        self.send_command('E')
        self.send_command(self._build_d_command(self._auto_cur_profile))
        self.send_command(f'Q{DYNAMIC_PROFILE_INDEX}')
        self.send_command('G')
        self._auto_state    = 'soaking'
        self._auto_settling = True
        QTimer.singleShot(1000, self._auto_settle_done)

        soak_ms = self.sp_auto_soak_s.value() * 1000
        self._auto_soak_timer = QTimer(self)
        self._auto_soak_timer.setSingleShot(True)
        self._auto_soak_timer.timeout.connect(self._auto_soak_done)
        self._auto_soak_timer.start(soak_ms)

        soak_s = self.sp_auto_soak_s.value()
        if self._auto_parallel:
            max_iter = self.sp_auto_max_iter.value()
            n_bad    = len(self._auto_targets)
            if n_bad == 0:
                self.lbl_auto_status.setText(f'Parallel — initial soak {soak_s} s…')
            else:
                self.lbl_auto_status.setText(
                    f'Parallel — iter {self._auto_iter}/{max_iter}, '
                    f'{n_bad} ch — soaking {soak_s} s…')
        elif self._auto_phase == 'initial':
            self.lbl_auto_status.setText(f'Sequential — initial soak {soak_s} s…')
        else:
            ch        = self._auto_targets[self._auto_target_idx]
            n_targets = len(self._auto_targets)
            max_att   = self.sp_auto_max_iter.value()
            self.lbl_auto_status.setText(
                f'{self._ch_label(ch)} — '
                f'cell {self._auto_target_idx + 1}/{n_targets}, '
                f'attempt {self._auto_ch_attempts + 1}/{max_att} — '
                f'soaking {soak_s} s…')

    def _auto_soak_done(self):
        if self._auto_state != 'soaking':
            return
        self._auto_state = 'idle'
        self.send_command('E')
        QTimer.singleShot(200, self._auto_evaluate)

    def _auto_settle_done(self):
        """1-second settling gate expired: begin accepting W records into the buffer."""
        self._auto_settling = False
        self._thermal_buf.clear()   # discard any stray frames that arrived during gate

    def _auto_evaluate(self):
        """Dispatch to parallel evaluator or sequential initial/channel evaluator."""
        if self._auto_parallel:
            self._auto_evaluate_parallel()
        elif self._auto_phase == 'initial':
            self._auto_evaluate_initial()
        else:
            self._auto_evaluate_channel()

    def _auto_evaluate_parallel(self):
        """Parallel mode: evaluate active unlocked channels, nudge still-bad ones, loop.
        Channels that have already passed once are locked — their delay is never
        touched again; only their cell colour keeps tracking live pass/fail."""
        n            = self.sp_thermal_n.value()
        recent       = list(self._thermal_buf)[-n:]
        threshold_uV = self.sp_auto_threshold_mv.value() * 1000.0
        max_iter     = self.sp_auto_max_iter.value()

        still_bad = []
        for ch in range(self._thermal_n_channels):
            if self._auto_skip_flat[ch]:
                continue
            std_uV = (_stdev([frame[ch] for frame in recent])
                      if len(recent) >= 2 else float('inf'))

            if self._auto_locked_flat[ch]:
                self._auto_color_cell(
                    ch, _COL_DONE if std_uV <= threshold_uV else _COL_AUTO_DRIFTED)
                continue

            mean_v = (self._thermal_latest[ch] / 1_000_000
                      if self._thermal_latest else 0.0)
            self._auto_check_ceiling(ch, mean_v)

            if std_uV < self._auto_best_std_uV[ch]:
                self._auto_best_std_uV[ch]     = std_uV
                self._auto_best_delays_flat[ch] = self._auto_cur_delays_flat[ch]
            if std_uV > threshold_uV:
                still_bad.append(ch)
                self._auto_color_cell(ch, _COL_AUTO_QUEUED)
            else:
                self._auto_locked_flat[ch] = True
                self._auto_color_cell(ch, _COL_DONE)

        self._log(f'  Iter {self._auto_iter}: {len(still_bad)} channel(s) above threshold')
        self._auto_targets = still_bad

        if not still_bad:
            self._auto_finish(all_pass=True)
            return

        if self._auto_iter >= max_iter:
            for ch in still_bad:
                self._auto_color_cell(ch, _COL_AUTO_FLAGGED)
            self._auto_finish(all_pass=False)
            return

        # Nudge all still-bad channels simultaneously then soak again
        self._auto_iter += 1
        for ch in still_bad:
            self._auto_nudge_channel(ch)
        self._auto_run_soak()

    def _auto_evaluate_initial(self):
        """Evaluate all channels; build ordered bad list; start first channel."""
        if not self._fp_pairs:
            return
        threshold_uV = self.sp_auto_threshold_mv.value() * 1000.0
        n            = self.sp_thermal_n.value()
        recent       = list(self._thermal_buf)[-n:]
        n_ch         = self._thermal_n_channels

        bad = []
        for ch in range(n_ch):
            if self._auto_skip_flat[ch]:
                continue
            if len(recent) < 2:
                std_uV = float('inf')
            else:
                vals   = [frame[ch] for frame in recent]
                std_uV = _stdev(vals)
            if std_uV < self._auto_best_std_uV[ch]:
                self._auto_best_std_uV[ch]      = std_uV
                self._auto_best_delays_flat[ch] = self._auto_cur_delays_flat[ch]
            result = 'BAD' if std_uV > threshold_uV else 'ok'
            std_mv = std_uV / 1000.0
            mean_v = (self._thermal_latest[ch] / 1_000_000
                      if self._thermal_latest else 0.0)
            self._log(f'  {self._ch_label(ch)}: σ={std_mv:.2f} mV  '
                      f'mean={mean_v:.3f} V  [{result}]')
            if std_uV > threshold_uV:
                bad.append(ch)

        # Colour calibration table: good → green, bad → yellow (queued)
        bad_set = set(bad)
        for ch in range(n_ch):
            if self._auto_skip_flat[ch]:
                continue
            self._auto_color_cell(
                ch, _COL_AUTO_QUEUED if ch in bad_set else _COL_DONE)

        if not bad:
            self._log('All channels within threshold — nothing to nudge.')
            self._auto_finish(all_pass=True)
            return

        self._auto_targets    = bad
        self._auto_target_idx = 0
        self._auto_ch_attempts = 0
        self._log(f'Phase 2: {len(bad)} bad channel(s) → processing sequentially')
        self._auto_start_next_channel()

    def _auto_start_next_channel(self):
        """Nudge the current target channel and start its first soak."""
        if self._auto_target_idx >= len(self._auto_targets):
            self._auto_finish(all_pass=False)
            return
        self._auto_phase       = 'channel'
        self._auto_ch_attempts = 0
        ch  = self._auto_targets[self._auto_target_idx]
        idx = self._auto_target_idx
        n   = len(self._auto_targets)
        self._log(f'Working on {self._ch_label(ch)} '
                  f'({idx + 1} of {n} bad channels):')
        self._auto_color_cell(ch, _COL_AUTO_WORKING)
        self._auto_nudge_channel(ch)
        self._auto_run_soak()

    def _auto_evaluate_channel(self):
        """Evaluate only the current target channel; advance or retry."""
        if not self._auto_targets:
            self._auto_finish(all_pass=False)
            return
        ch           = self._auto_targets[self._auto_target_idx]
        threshold_uV = self.sp_auto_threshold_mv.value() * 1000.0
        max_att      = self.sp_auto_max_iter.value()
        n            = self.sp_thermal_n.value()
        recent       = list(self._thermal_buf)[-n:]

        if len(recent) < 2:
            std_uV = float('inf')
        else:
            vals   = [frame[ch] for frame in recent]
            std_uV = _stdev(vals)

        if std_uV < self._auto_best_std_uV[ch]:
            self._auto_best_std_uV[ch]      = std_uV
            self._auto_best_delays_flat[ch] = self._auto_cur_delays_flat[ch]

        std_mv  = std_uV / 1000.0
        cur_us  = self._auto_cur_delays_flat[ch]
        mean_v  = (self._thermal_latest[ch] / 1_000_000
                   if self._thermal_latest else 0.0)
        self._auto_check_ceiling(ch, mean_v)

        if std_uV <= threshold_uV:
            self._log(f'  attempt {self._auto_ch_attempts + 1}: '
                      f'σ={std_mv:.2f} mV @ {cur_us:.3f} µs  '
                      f'mean={mean_v:.3f} V  → PASSED')
            self._auto_color_cell(ch, _COL_DONE)
            self._auto_target_idx  += 1
            self._auto_ch_attempts  = 0
            self._auto_start_next_channel()
            return

        # Still bad
        self._log(f'  attempt {self._auto_ch_attempts + 1}/{max_att}: '
                  f'σ={std_mv:.2f} mV @ {cur_us:.3f} µs  '
                  f'mean={mean_v:.3f} V  → BAD')

        if self._auto_ch_attempts >= max_att - 1:
            best_us = self._auto_best_delays_flat[ch]
            best_mv = self._auto_best_std_uV[ch] / 1000.0
            self._log(f'  max attempts reached — flagging. '
                      f'Best: {best_us:.3f} µs (σ={best_mv:.2f} mV)')
            self._auto_color_cell(ch, _COL_AUTO_FLAGGED)
            self._auto_target_idx  += 1
            self._auto_ch_attempts  = 0
            self._auto_start_next_channel()
            return

        self._auto_ch_attempts += 1
        self._auto_nudge_channel(ch)
        self._auto_run_soak()

    def _auto_check_ceiling(self, ch: int, mean_v: float):
        """Once a channel's monitored voltage reaches the signal-detect ceiling
        (sp_signal_v, default 4.9 V — no real signal, see v1.15), lock its Auto
        Nudge search to down-only steps from that point on; nudging further up
        just walks deeper into no-signal territory."""
        if self._auto_ceiling_flat[ch] or mean_v < self.sp_signal_v.value():
            return
        self._auto_ceiling_flat[ch] = True
        k    = self._auto_attempt_flat[ch]
        mult = (k + 1) // 2
        self._auto_down_mult_flat[ch] = mult
        self._log(f'  {self._ch_label(ch)}: mean {mean_v:.3f} V ≥ signal-detect '
                  f'ceiling ({self.sp_signal_v.value():.1f} V) — further nudges will only move down.')

    def _auto_nudge_channel(self, ch: int):
        """Nudge one channel along an expanding ±nudge_ns zigzag from the calibrated
        delay.  Once _auto_check_ceiling() has flagged this channel, the zigzag is
        overridden to down-only steps of growing magnitude (see _auto_ceiling_flat)."""
        nudge_us = self.sp_auto_nudge_ns.value() / 1000.0
        cap_us   = self.sp_auto_cap_ns.value()   / 1000.0
        cal      = self._auto_cal_delays_flat[ch]

        self._auto_attempt_flat[ch] += 1
        k = self._auto_attempt_flat[ch]

        if self._auto_ceiling_flat[ch]:
            mult = self._auto_down_mult_flat[ch]
            sign = -1
            self._auto_down_mult_flat[ch] += 1
        else:
            mult = (k + 1) // 2
            sign = 1 if k % 2 else -1
        offset = mult * nudge_us

        if offset > cap_us:
            self._log(f'  {self._ch_label(ch)}: cap reached — no further nudge; '
                      f'best-std fallback applies')
            return

        proposed = _snap_8ns(cal + sign * offset)
        self._auto_cur_delays_flat[ch] = proposed
        self._log(f'  {self._ch_label(ch)} nudge #{k}: '
                  f'{sign * mult * self.sp_auto_nudge_ns.value():+d} ns from cal '
                  f'→ {proposed:.3f} µs (Δ {(proposed - cal) * 1000:+.0f} ns from cal)')

    def _auto_finish(self, all_pass: bool):
        """Update calibration table with best delays, report ΔV, export profile."""
        self._auto_state   = 'idle'
        self._auto_running = False
        if self.serial.isOpen():
            self.send_command('E')

        n_cells      = self._thermal_n_cells
        n_ch         = self._thermal_n_channels
        threshold_uV = self.sp_auto_threshold_mv.value() * 1000.0

        self._log('── Auto Nudge results ──')
        n_still_bad = 0
        for ch in range(n_ch):
            if self._auto_skip_flat[ch]:
                continue
            b          = ch // n_cells
            c          = ch  % n_cells
            best_delay = self._auto_best_delays_flat[ch]
            best_std   = self._auto_best_std_uV[ch]
            cal_delay  = self._auto_cal_delays_flat[ch]
            passed     = (best_std <= threshold_uV)

            item = self.table.item(b, c)
            if item:
                item.setText(f'{best_delay:.3f}')
            self._auto_color_cell(ch, _COL_DONE if passed else _COL_AUTO_FLAGGED)

            delta_ns  = round((best_delay - cal_delay) * 1000)
            status    = 'PASS' if passed else 'FLAGGED'
            log_line  = (f'  {self._ch_label(ch)}: {best_delay:.3f} µs '
                         f'(Δ{delta_ns:+d} ns)  '
                         f'σ={best_std / 1000:.2f} mV  [{status}]')
            if self._thermal_latest is not None and delta_ns != 0:
                target_uV = self._targets_v[c] * 1_000_000
                delta_mv  = (self._thermal_latest[ch] - target_uV) / 1000.0
                log_line += f'  ΔV={delta_mv:+.1f} mV'
            self._log(log_line)

            if not passed:
                n_still_bad += 1

        n_active = sum(1 for s in self._auto_skip_flat if not s)
        n_pass   = n_active - n_still_bad
        if n_still_bad == 0:
            summary = f'Auto complete — all {n_active} active cells passed.'
        else:
            summary = (f'Auto complete — {n_pass}/{n_active} passed, '
                       f'{n_still_bad} flagged red.')
        self._log(summary)

        # Compact adjusted-delays summary (only channels where delay changed)
        adjusted = [
            ch for ch in range(n_ch)
            if not self._auto_skip_flat[ch]
            and round((self._auto_best_delays_flat[ch]
                       - self._auto_cal_delays_flat[ch]) * 1000) != 0
        ]
        if adjusted:
            self._log('── Adjusted delays ──')
            for ch in adjusted:
                best_us  = self._auto_best_delays_flat[ch]
                cal_us   = self._auto_cal_delays_flat[ch]
                delta_ns = round((best_us - cal_us) * 1000)
                passed   = self._auto_best_std_uV[ch] <= threshold_uV
                self._log(
                    f'  {self._ch_label(ch):<32s}'
                    f'  {cal_us:.3f} → {best_us:.3f} µs'
                    f'  ({delta_ns:+d} ns)'
                    f'  [{("PASS" if passed else "FLAGGED")}]')
        else:
            self._log('No delays were adjusted.')

        self.lbl_auto_status.setText(summary)
        self.lbl_thermal_status.setText('')
        self.statusBar().showMessage(summary)
        self.progress_label.setText(
            f'{summary}  ·  {len(adjusted)} delay(s) adjusted')

        self.pb_auto.setEnabled(True)
        self.pb_auto.setStyleSheet('')
        self.pb_auto_stop.setEnabled(False)
        self.pb_run.setEnabled(self.serial.isOpen())
        self.pb_thermal.setEnabled(bool(self._fp_pairs))
        self.pb_export.setEnabled(True)
        self.pb_export_profile.setEnabled(True)

        self.export_profile()

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
                headers = ['freq_kHz/pulse_us'] + [f'{v:.3f}V' for v in self._targets_v]
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
    # Settings persistence
    # ------------------------------------------------------------------
    def _load_settings(self):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            self.le_port.setText(             s.get('port',              self.le_port.text()))
            self.sp_start.setValue(           s.get('start_delay',       self.sp_start.value()))
            self.sp_step.setValue(            s.get('step_size',         self.sp_step.value()))
            self.sp_coarse_step.setValue(     s.get('coarse_step',       self.sp_coarse_step.value()))
            self.sp_signal_v.setValue(        s.get('signal_v',          self.sp_signal_v.value()))
            self.sp_max.setValue(             s.get('max_delay',         self.sp_max.value()))
            self.sp_avg.setValue(             s.get('averages',          self.sp_avg.value()))
            self.le_fp_pairs.setText(         s.get('fp_pairs',          self.le_fp_pairs.text()))
            self.le_targets.setText(          s.get('targets',           self.le_targets.text()))
            self.sp_thermal_secs.setValue(    s.get('thermal_secs',      self.sp_thermal_secs.value()))
            self.sp_thermal_n.setValue(       s.get('thermal_n',         self.sp_thermal_n.value()))
            self.sp_auto_soak_s.setValue(     s.get('auto_soak_s',       self.sp_auto_soak_s.value()))
            self.sp_auto_max_iter.setValue(   s.get('auto_max_iter',     self.sp_auto_max_iter.value()))
            self.sp_auto_threshold_mv.setValue(s.get('auto_threshold_mv', self.sp_auto_threshold_mv.value()))
            self.sp_auto_nudge_ns.setValue(   s.get('auto_nudge_ns',     self.sp_auto_nudge_ns.value()))
            self.sp_auto_cap_ns.setValue(     s.get('auto_cap_ns',       self.sp_auto_cap_ns.value()))
            self.cb_sequential.setChecked(   bool(s.get('auto_sequential', False)))
            # Window geometry
            w = int(s.get('window_w', 1440))
            h = int(s.get('window_h', 1200))
            self.resize(w, h)
            x, y = s.get('window_x'), s.get('window_y')
            if x is not None and y is not None:
                self.move(int(x), int(y))
            # Splitter sizes (deferred so widget is laid out first)
            splitter_sizes = s.get('splitter')
            if splitter_sizes and len(splitter_sizes) == 2:
                QTimer.singleShot(0, lambda: self.v_splitter.setSizes(
                    [int(v) for v in splitter_sizes]))
            h_splitter_sizes = s.get('h_splitter')
            if h_splitter_sizes and len(h_splitter_sizes) == 2:
                QTimer.singleShot(0, lambda: self.h_splitter.setSizes(
                    [int(v) for v in h_splitter_sizes]))
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            self.resize(1440, 1200)  # first run — use default size

    def _save_settings(self):
        s = {
            'port':              self.le_port.text(),
            'start_delay':       self.sp_start.value(),
            'step_size':         self.sp_step.value(),
            'coarse_step':       self.sp_coarse_step.value(),
            'signal_v':          self.sp_signal_v.value(),
            'max_delay':         self.sp_max.value(),
            'averages':          self.sp_avg.value(),
            'fp_pairs':          self.le_fp_pairs.text(),
            'targets':           self.le_targets.text(),
            'thermal_secs':      self.sp_thermal_secs.value(),
            'thermal_n':         self.sp_thermal_n.value(),
            'auto_soak_s':       self.sp_auto_soak_s.value(),
            'auto_max_iter':     self.sp_auto_max_iter.value(),
            'auto_threshold_mv': self.sp_auto_threshold_mv.value(),
            'auto_nudge_ns':     self.sp_auto_nudge_ns.value(),
            'auto_cap_ns':       self.sp_auto_cap_ns.value(),
            'auto_sequential':   self.cb_sequential.isChecked(),
            'window_w':          self.width(),
            'window_h':          self.height(),
            'window_x':          self.x(),
            'window_y':          self.y(),
            'splitter':          self.v_splitter.sizes(),
            'h_splitter':        self.h_splitter.sizes(),
        }
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(s, f, indent=2)
        except OSError:
            pass

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
        self._save_settings()
        self._stop_auto()
        self._stop_thermal()
        if self.serial.isOpen():
            self.send_command('E')
            self.serial.waitForBytesWritten(200)
            self.serial.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()   # _load_settings() sets geometry; default 1440×1200 on first run
    window.show()
    sys.exit(app.exec())
