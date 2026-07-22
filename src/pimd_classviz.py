# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
###############################################################################
# PIMD Signature Visualiser (ClassViz) v1.33
# — Mode 2 adaptive profile viewer
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# Connects to the board, sends Q4/G to start Mode 2 streaming with the default
# CLASSIFY_EP profile, and displays a heatmap of signed cell deviations from a
# captured air baseline. Includes a Training Session tab for guided, marked
# signature-corpus capture, and a top-bar saved-profile selector to load/send
# a band/pulse/delay profile to the board as a RAM-only "dynamic" profile
# (firmware D command) without reflashing — the heatmap/stats table resize to
# match whatever profile (static or dynamic) is active. Profile authoring/saving
# lives in pimd_delaycal.py; ClassViz only loads and runs.
#
# Protocol: receives W<profile_idx>,<time_ms>,<ch0>,...,<chN-1>
# Board firmware: pimd_mcu.py v4.23+
#
# History (full detail in CHANGELOG.md):
#   v1.33 continuous training capture (Training group; space-bar air/target toggle; supply battery/psu)
#   v1.32 structured target-metadata capture regime (registry-backed Analysis/Training capture)
#   v1.31 Analysis-tab signature captures hardened to session-pipeline rigor (settle gate, glitch exclusion)
#   v1.30 normalize Auto mode subtracts group mean, not first element (noisy-reference-cell fix)
#   v1.29 Analysis heatmap ColorBarItem legend doubling as an interactive range control
#   v1.28 "Std Dev (rolling N)" heatmap display mode + top-bar Rate readout
#   v1.27 Analysis tab layout regrouping (left column + 3-row right side), cosmetic
#   v1.26 Analysis tab settings persistence + in-GUI signature file editor
#   v1.25 Analysis tab: single averaged Band-Mean strip; chart-2 controls; relayout
#   v1.24 Analysis tab: per-group Auto/Manual normalize+scale; bordered charts; Y-lock fix
#   v1.23 new Analysis tab: real-time comparison charts + corpus overlay
#   v1.22 Training Start clears live columns; notes auto-derived from run list
#   v1.21 new Training Session tab: guided target-list capture, Space step-advance
#   v1.20 removed Profile Builder tab; top-bar Saved-profile "Load & Run"
#   v1.19 session-recording mark hotkeys (1/2/3/0/Space) via app-wide eventFilter
#   v1.18 _save_profile_file JSON padded to 3 d.p. (_pad_json_floats)
#   v1.17 3-decimal precision for all voltage/timing fields
#   v1.16 "Record Frames" reworked into self-describing session-dump recorder
#   v1.15 Stats Std column green/yellow/red thresholds; row-height +/- controls
#   v1.14 Stats/Profile tables sorted ascending by first delay
#   v1.13 remove single-cell isolation mode
#   v1.12 heatmap rows in descending delay order regardless of stream order
#   v1.11 settings persistence (port/capture/rolling/display/geometry/...)
#   v1.10 Mode 1 '*' command updated to MCU v4.23 protocol (Hz/ns)
#   v1.09 band labels + Stats delay to 3 d.p. (8 ns grid)
#   v1.08 Stats std-dev window sample-count based (was seconds)
#   v1.07 process_packet: 64-frame median glitch filter on display path
#   v1.06 Stats "Record Frames" toggle (raw W-frame CSV)
#   v1.05 fix _fmt(): no thousands-separator in saved CSV
#   v1.04 per-instance profile dims; Profile Builder tab; D-command dynamic profile
#   v1.03 Stats "Save table as CSV"
#   v1.02 Resume Sweep auto-sends G
#   v1.01 add Stats tab (per-cell value/mean/std) + single-cell isolation
#   v1.00 initial version: heatmap + baseline + labelled CSV logger + 3D surface
###############################################################################

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import csv
import io
import json
import math
import os
import sys
import time
from datetime import datetime, date, timedelta
from collections import deque

import numpy as np

os.environ.setdefault('QT_API', 'pyqt6')

from PyQt6.QtCore import QEvent, QIODevice, QTimer, Qt  # noqa: E402
from PyQt6.QtGui import QBrush, QColor, QFont  # noqa: E402
from PyQt6.QtSerialPort import QSerialPort  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
    QFileDialog, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QSplitter, QStackedWidget, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import pyqtgraph as pg  # noqa: E402

try:
    import pyqtgraph.opengl as gl
    _GL_AVAILABLE = True
except ImportError:
    _GL_AVAILABLE = False

import pimd_corpus_check  # noqa: E402 — Analysis tab signature-overlay loader
import pimd_features       # noqa: E402 — Analysis tab signature capture/save
import pimd_targets        # noqa: E402 — target registry, shared with pimd_features

APP_VERSION = '1.33'

REDRAW_MS   = 33    # ~30 Hz

DEFAULT_PROFILE_IDX   = 4   # static CLASSIFY_EP — sent automatically on connect
DYNAMIC_PROFILE_INDEX = 5   # must match firmware's NUM_PROFILES (pimd_mcu.py v4.07+)

CAPTURE_FRAMES_DEFAULT = 64
ROLLING_SECS_DEFAULT   = 3.0
DEFAULT_PORT = '/dev/ttyACM0'

PROFILES_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'profiles')
SESSIONS_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'sessions')
TRAINING_LISTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'training_lists')
CORPORA_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'corpora')
TARGETS_REGISTRY_PATH = pimd_targets.DEFAULT_REGISTRY_PATH   # single source of truth
SUPPLY_CHOICES = ['battery', 'psu']
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'data', 'classviz_settings.json')


def _default_profile():
    """Baseline CLASSIFY_EP profile — matches pimd_mcu.py PROFILES[4] exactly."""
    band_data = (
        (10601, 40.0, ( 8.56,  8.98,  9.37,  9.72, 10.08, 10.49, 10.96, 11.57, 12.53)),
        (17599, 30.0, ( 8.12,  8.54,  8.92,  9.27,  9.63, 10.02, 10.50, 11.10, 12.03)),
        (29201, 20.0, ( 7.62,  8.03,  8.40,  8.75,  9.11,  9.50,  9.96, 10.55, 11.46)),
        (43003, 10.0, ( 6.80,  7.22,  7.58,  7.93,  8.28,  8.66,  9.11,  9.70, 10.57)),
        (56992,  5.0, ( 6.03,  6.43,  6.78,  7.12,  7.46,  7.84,  8.28,  8.85,  9.71)),
    )
    threshold_v = [4.5 - 0.5 * j for j in range(9)]
    return {
        'name': 'CLASSIFY_EP',
        'averages': 32,
        'bands': [
            {'freq_hz': f, 'pulse_us': p, 'delays_us': list(d), 'threshold_v': threshold_v}
            for f, p, d in band_data
        ],
    }


def _list_profile_files():
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(PROFILES_DIR) if f.endswith('.json'))


def _load_profile_file(name):
    """Returns (profile_dict, raw_bytes) -- the raw bytes are needed for
    profile_sha8 (SHA-256 of the profile JSON bytes as loaded, DESIGN §10),
    which can only be computed from the literal file contents, not a
    re-serialized dict."""
    path = os.path.join(PROFILES_DIR, name + '.json')
    with open(path, 'rb') as f:
        raw = f.read()
    return json.loads(raw), raw


def _list_training_list_files():
    if not os.path.isdir(TRAINING_LISTS_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(TRAINING_LISTS_DIR) if f.endswith('.json'))


def _load_training_list_file(name):
    with open(os.path.join(TRAINING_LISTS_DIR, name + '.json')) as f:
        return json.load(f)


def _save_training_list_file(name, rows):
    """rows: list of {'target_id': str, 'distance_mm': float, 'placement':
    {'long_axis','face_normal','offset_x_mm','offset_y_mm','medium',
    'repeat_idx','notes'}}. A row missing 'target_id' (e.g. a pre-v1.32 list
    with the old 'target'/'distance_cm' keys) is loudly rejected on load --
    see _on_training_load_list() -- rather than migrated. Index is never
    persisted (always derived/renumbered on load); Time/Settledness are live
    per-run data, never part of the saved template."""
    os.makedirs(TRAINING_LISTS_DIR, exist_ok=True)
    data = {'name': name, 'rows': rows}
    with open(os.path.join(TRAINING_LISTS_DIR, name + '.json'), 'w') as f:
        json.dump(data, f, indent=2)


pg.setConfigOptions(background='w', foreground='k', antialias=True)

_R = int(Qt.AlignmentFlag.AlignRight) | int(Qt.AlignmentFlag.AlignVCenter)
_C = int(Qt.AlignmentFlag.AlignCenter)


def _fmt(uv):
    """µV → mV string with 3 d.p."""
    return '{0:.3f}'.format(uv / 1000.0)


def _csv_default_path():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    return os.path.join(data_dir, 'signatures_{0}.csv'.format(date.today().strftime('%Y%m%d')))


class MainWindow(QMainWindow):
    MY_GREEN  = 'background-color: rgb(143, 240, 164);'
    MY_YELLOW = 'background-color: rgb(249, 240, 107);'
    MY_RED    = 'background-color: rgb(246,  97,  81);'
    MY_BLUE   = 'background-color: rgb(153, 193, 241);'

    def __init__(self):
        super().__init__()
        self.setWindowTitle('PIMD ClassViz v{0} by Mark Makies'.format(APP_VERSION))

        # Serial
        self.serial = QSerialPort()
        self.serial.readyRead.connect(self.read_from_serial)
        self._last_cmd    = ''
        self._last_packet = ''
        self._fw_version_line: 'str | None' = None

        # Profile dimensions (n_bands, n_cells, labels, etc) — instance state so
        # the heatmap/stats table/single-cell selectors can resize at runtime
        # when a saved profile is loaded from the top-bar selector.
        self._set_profile_dims(_default_profile(), DEFAULT_PROFILE_IDX)

        # Data state — sweep
        self._latest_raw: 'np.ndarray | None' = None   # shape (n_channels,)
        self._baseline_mean: 'np.ndarray | None' = None  # shape (n_bands, n_cells)
        self._baseline_std:  'np.ndarray | None' = None  # shape (n_bands, n_cells)
        self._baseline_mode = 'static'   # 'static' | 'rolling' | 'nominal'
        self._baseline_age: 'float | None' = None
        self._capture_buf: list = []
        self._capturing   = False
        self._capture_n   = CAPTURE_FRAMES_DEFAULT
        self._rolling_buf: deque = deque(maxlen=10_000)
        self._rolling_T   = ROLLING_SECS_DEFAULT

        self._freeze       = False
        self._autoscale    = True
        self._manual_range = 200_000.0
        self._display_mode = 'delta'     # 'raw' | 'delta' | 'z'
        self._3d_visible   = False

        self._continuous_log     = False
        self._csv_header_written = False
        self._csv_rows           = 0
        self._frame_count        = 0

        # Throughput monitor — recomputed once/sec by _rate_timer (see below),
        # so the displayed Hz is an exact "frames received in the last second"
        # count, not a smoothed estimate.
        self._fps_hz                = 0.0
        self._fps_last_calc_wall    = time.time()
        self._fps_last_frame_count  = 0
        # Max number of complete lines drained in a single read_from_serial()
        # call since the last rate tick -- consistently >1 means the GUI is
        # falling behind the incoming serial stream and lines are backing up
        # in Qt's serial buffer between readyRead events.
        self._serial_max_batch      = 0

        self._recording           = False
        self._session_file        = None   # open file handle while a session is being recorded
        self._session_path        = None
        self._session_start_wall  = None   # time.time() at recording start (elapsed display)
        self._session_frame_count = 0

        self._ch_glitch_buf: 'np.ndarray | None' = None  # shape (64, n_channels), circular
        self._ch_glitch_pos  = 0

        # Data state — Training Session tab
        self._training_current_row: 'int | None' = None   # None when no training session active
        self._training_paused: bool = False
        self._training_row_start_wall: 'float | None' = None
        self._training_pause_started: 'float | None' = None

        # Data state — stats
        self._freeze_stats = False
        self._stats_row_height = 22

        # Data state — Analysis tab
        self._analysis_avg_n    = 1
        self._analysis_templates = {}   # (session,target,distance) -> {shape,color,label}

        self._analysis_strip_reset_ts = 0.0
        self._analysis_strip_norm_auto = True
        self._analysis_strip_manual_ref = 0.0
        self._analysis_strip_scale_auto = True
        self._analysis_strip_manual_halfrange = 5.0

        # Analysis tab — per-group Auto/Manual normalize+scale (heatmap/8-grid/9-grid)
        self._analysis_hm_norm_auto      = True
        self._analysis_hm_display_mode   = 'delta'   # used only when norm is Manual (decoupled)
        self._analysis_hm_scale_auto     = True
        self._analysis_hm_manual_range_uv = 200_000.0

        self._analysis_c2_norm_auto  = True
        self._analysis_c2_manual_ref = 0.0
        self._analysis_c2_scale_auto = True
        self._analysis_c2_manual_halfrange = 5.0

        self._analysis_g8_norm_auto  = True
        self._analysis_g8_manual_ref = 0.0
        self._analysis_g8_scale_auto = True
        self._analysis_g8_manual_halfrange = 5.0

        self._analysis_g9_norm_auto  = True
        self._analysis_g9_manual_ref = 0.0
        self._analysis_g9_scale_auto = True
        self._analysis_g9_manual_halfrange = 5.0

        # Analysis tab — signature file editing (New/Open-for-editing/Save/Delete)
        self._editable_sig_path       = None   # str|None -- the currently open-for-editing file
        self._editable_sig_session_id = None   # 'gui_YYYYMMDD_HHMMSS', assigned fresh on New/Open
        self._editable_sig_seq        = 0      # running per-file capture_id sequence, reset on New/Open
        self._editable_repeat_counts  = {}     # placement tuple -> count seen, for repeat_idx auto-increment

        # Target registry (pimd_targets.py) -- shared by the Analysis tab's
        # inline capture widgets and the Training tab's Placement dialog.
        self._targets        = {}    # dict[target_id -> pimd_targets.Target]
        self._target_issues   = []

        # Analysis tab — continuous training capture (v1.33). A second,
        # independent capture channel from _capturing/_capture_buf (which stay
        # hard-wired to the Heatmap tab's "Capture baseline"). One session
        # alternates AIR/TARGET phases; each committed air anchor is both
        # air_after for the previous target and air_before for the next.
        self._sig_capture_n    = pimd_features.MIN_CENTRAL_FRAMES
        self._analysis_training_active = False
        self._sig_train_phase  = 'air'       # 'air' | 'target'
        self._sig_train_status = 'settling'  # 'settling' | 'collecting' | 'ready'
        self._sig_train_buf    = None        # deque(maxlen=N) of (ts, raw_uV.copy()); rolls in 'ready'
        self._sig_train_last_style = None    # stylesheet churn guard for the status label
        self._sig_glitch_skipped = 0    # glitch frames excluded from the current window (v1.31)
        self._sig_air_before   = None   # {'t_seconds':(n,), 'frames_mV':(n,n_channels), 'n_frames':int}
        self._sig_air_after    = None   # same shape, optional
        self._sig_target       = None   # same shape
        self._sig_last_stats   = None   # cached dict from _compute_sig_stats(), for the live readout

        # Analysis tab — session recording (alternate path, reuses the
        # Training Session tab's own _session_start/_session_stop/_append_mark
        # machinery and self._recording/_training_paused flags verbatim).
        self._analysis_session_recording = False

        self._setup_colormaps()
        self._build_ui()
        QApplication.instance().installEventFilter(self)
        self._load_settings()

        self._redraw_timer = QTimer()
        self._redraw_timer.setInterval(REDRAW_MS)
        self._redraw_timer.timeout.connect(self._redraw)
        self._redraw_timer.start()

        self._rate_timer = QTimer()
        self._rate_timer.setInterval(1000)
        self._rate_timer.timeout.connect(self._update_rate)
        self._rate_timer.start()

    # ------------------------------------------------------------------
    # Profile dimensions
    # ------------------------------------------------------------------
    def _set_profile_dims(self, profile, profile_idx, profile_raw_bytes=None):
        """Pure data update — sets self._n_bands/_n_cells/_band_labels/etc from
        `profile` (dict: name, averages, bands=[{freq_hz,pulse_us,delays_us,
        threshold_v(optional)}, ...], all bands sharing the same delay count).
        Does not touch any UI widgets — see _apply_profile() for that.

        Also computes self._profile_sha8 (first 8 hex chars of SHA-256 of the
        profile JSON bytes as loaded, DESIGN §10) -- profile_raw_bytes is the
        literal bytes read from a saved profile file (_load_profile_file);
        when there is no file (the built-in _default_profile() fallback), a
        canonical sort_keys=True re-serialization is used as a documented,
        deliberate surrogate since there is nothing to hash literally."""
        bands = profile['bands']
        n_bands = len(bands)
        n_cells = len(bands[0]['delays_us'])
        self._profile           = profile
        self._active_profile_idx = profile_idx
        self._profile_raw_bytes = profile_raw_bytes if profile_raw_bytes is not None \
            else json.dumps(profile, sort_keys=True, separators=(',', ':')).encode('utf-8')
        self._profile_sha8 = pimd_features.profile_sha8_of_bytes(self._profile_raw_bytes)
        self._n_bands    = n_bands
        self._n_cells    = n_cells
        self._n_channels = n_bands * n_cells
        # Keep the (freq_hz, pulse_us, delays_us_tuple) shape used throughout
        # the rest of the file (was the module-level BANDS_META tuple).
        self._bands_meta = [(b['freq_hz'], b['pulse_us'], tuple(b['delays_us']))
                             for b in bands]
        self._band_labels = ['{0:,}Hz / {1:.3f}µs'.format(b['freq_hz'], b['pulse_us'])
                              for b in bands]
        # Sort display rows by first delay value descending so alternating
        # pulse-width profiles (high/low interleaved) still render in delay order.
        self._band_display_order = sorted(
            range(n_bands), key=lambda i: bands[i]['delays_us'][0], reverse=True)
        self._display_band_labels = [self._band_labels[i] for i in self._band_display_order]
        # Ascending delay order — used by the Stats table and Profile Builder table.
        self._band_stats_order  = list(reversed(self._band_display_order))
        self._stats_band_labels = [self._band_labels[i] for i in self._band_stats_order]
        self._has_threshold_v = all(
            'threshold_v' in b and len(b['threshold_v']) == n_cells for b in bands)
        if self._has_threshold_v:
            self._cell_labels = ['{0:.3f}V'.format(v) for v in bands[0]['threshold_v']]
            self._nominal_baseline_uv = np.array(
                [[v * 1_000_000 for v in b['threshold_v']] for b in bands], dtype=float)
        else:
            self._cell_labels = ['d{0}'.format(j) for j in range(n_cells)]
            self._nominal_baseline_uv = np.zeros((n_bands, n_cells))
        # Analysis tab: bands sorted pulse_us ascending. Raw protocol/profile
        # band order is NOT reliably pulse-ascending -- the live default
        # CLASSIFY_EP profile is actually pulse-*descending* (40->5us) -- so
        # every Analysis chart that plots "vs pulse width" must reindex by
        # this instead of assuming index order.
        self._pulse_sort_order = sorted(range(n_bands), key=lambda i: bands[i]['pulse_us'])
        self._pulse_us_sorted  = [bands[i]['pulse_us'] for i in self._pulse_sort_order]
        # Per-cell delay_us range across all bands, for the Analysis heatmap's
        # threshold-axis sub-label (threshold_v is constant per cell across
        # bands; delay_us is not, so it can only be shown as a range there).
        self._cell_delay_range_us = [
            (min(b['delays_us'][j] for b in bands), max(b['delays_us'][j] for b in bands))
            for j in range(n_cells)
        ]
        self._cell_delay_avg_us = [
            float(np.mean([b['delays_us'][j] for b in bands])) for j in range(n_cells)
        ]

    def _apply_profile(self, profile, profile_idx, profile_raw_bytes=None):
        """Switch the active profile at runtime: updates dimensions, clears any
        old-shape buffered data, and resizes the heatmap/3D surface/stats table/
        single-cell selectors to match. Called once for the default profile (via
        _set_profile_dims directly, before _build_ui) and again whenever a
        saved profile is loaded and run from the top-bar selector."""
        self._set_profile_dims(profile, profile_idx, profile_raw_bytes)

        # Old-shape data must not survive a dimension change.
        if self._recording:
            self.pb_record.setChecked(False)   # triggers _toggle_record_frames → auto-save
        self._rolling_buf.clear()
        self._baseline_mean = None
        self._baseline_std  = None
        self._baseline_age  = None
        self._latest_raw     = None
        self._frame_count    = 0
        self._ch_glitch_buf  = None
        self._ch_glitch_pos  = 0

        self._rebuild_heatmap_axes()
        self._rebuild_3d_surface()
        self._rebuild_stats_table()
        if hasattr(self, 'analysis_plot'):
            self._rebuild_analysis_heatmap_axes()
            self._rebuild_analysis_chart2_ticks()
            self._rebuild_analysis_grid8()
            self._rebuild_analysis_grid9()
            self._apply_g8_scale()
            self._apply_g9_scale()
            self._analysis_strip_reset_ts = 0.0
            self._reset_sig_capture_state()   # old raw arrays would mismatch the new n_channels
            self._refresh_analysis_overlays()
        self.header_label.setText('Profile {0} — {1} ({2} bands × {3} cells)'.format(
            profile_idx, profile.get('name', '?'), self._n_bands, self._n_cells))

    # ------------------------------------------------------------------
    # Colormaps
    # ------------------------------------------------------------------
    def _setup_colormaps(self):
        try:
            self.cm_div = pg.colormap.get('RdBu_r', source='matplotlib')
        except Exception:
            try:
                self.cm_div = pg.colormap.get('RdBu_r')
            except Exception:
                self.cm_div = pg.ColorMap(
                    pos=np.array([0.0, 0.5, 1.0]),
                    color=np.array([[0, 0, 220, 255], [255, 255, 255, 255],
                                    [220, 0, 0, 255]], dtype=np.uint8))
        try:
            self.cm_seq = pg.colormap.get('plasma', source='matplotlib')
        except Exception:
            try:
                self.cm_seq = pg.colormap.get('plasma')
            except Exception:
                self.cm_seq = pg.colormap.get('viridis')

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        layout  = QVBoxLayout(central)

        # Top bar — always visible on both tabs
        row1 = QHBoxLayout()
        row1.addWidget(QLabel('Port:'))
        self.le_port = QLineEdit(DEFAULT_PORT)
        self.le_port.setMaximumWidth(150)
        row1.addWidget(self.le_port)

        self.pb_connect = QPushButton('Not Connected')
        self.pb_connect.setStyleSheet(self.MY_YELLOW)
        self.pb_connect.clicked.connect(self.connect_port)
        row1.addWidget(self.pb_connect)

        self.pb_start = QPushButton('Stopped')
        self.pb_start.setStyleSheet(self.MY_YELLOW)
        self.pb_start.clicked.connect(self.start_stop)
        row1.addWidget(self.pb_start)

        # Saved-profile selector — replaces the old Profile Builder tab; picks a
        # profile JSON from data/profiles/ and sends it straight to the board.
        row1.addWidget(QLabel('Saved profile:'))
        self.cb_profile_file = QComboBox()
        self._refresh_profile_file_list()
        self.cb_profile_file.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        row1.addWidget(self.cb_profile_file)
        self.pb_load_run_profile = QPushButton('Load && Run')
        self.pb_load_run_profile.setStyleSheet(self.MY_YELLOW)
        self.pb_load_run_profile.clicked.connect(self._on_load_run_profile)
        row1.addWidget(self.pb_load_run_profile)

        self.header_label = QLabel('Profile {0} — {1} ({2} bands × {3} cells)'.format(
            self._active_profile_idx, self._profile.get('name', '?'),
            self._n_bands, self._n_cells))
        row1.addWidget(self.header_label, stretch=1)

        # Session-level supply (DESIGN §12 — battery/PSU noise floor differs
        # and can't be auto-detected). Not per-capture: shared by the
        # Analysis-tab quick-capture save path and the Training/Analysis
        # session mark-writing path.
        row1.addWidget(QLabel('Supply:'))
        self.cb_supply = QComboBox()
        self.cb_supply.addItems(SUPPLY_CHOICES)
        row1.addWidget(self.cb_supply)

        # Throughput readout — visible on every tab, updated once/sec by
        # _rate_timer/_update_rate. Answers "is data flowing at full speed".
        self.lbl_rate = QLabel('Rate: — (idle)')
        row1.addWidget(self.lbl_rate)
        layout.addLayout(row1)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_heatmap_tab(), 'Heatmap')
        self.tabs.addTab(self._build_stats_tab(),   'Stats')
        self.tabs.addTab(self._build_training_session_tab(), 'Training Session')
        self._analysis_tab_index = self.tabs.addTab(self._build_analysis_tab(), 'Analysis')
        layout.addWidget(self.tabs, stretch=1)

        self.setCentralWidget(central)
        self.statusBar().showMessage('Not connected')

        # Loaded here (after every tab -- and its target combo(s) -- is
        # built) so the initial population/degrade behavior applies before
        # _load_settings() restores any persisted target_id.
        self._load_targets_registry(show_dialog_on_error=True)

    # ------------------------------------------------------------------
    # Tab 0 — Heatmap
    # ------------------------------------------------------------------
    def _build_heatmap_tab(self):
        w      = QWidget()
        layout = QVBoxLayout(w)

        # Row 2 — display + baseline controls
        row2 = QHBoxLayout()
        row2.addWidget(QLabel('Display:'))
        self.cb_display = QComboBox()
        self.cb_display.addItems(['Δ deviation [default]', 'Z normalised', 'RAW abs µV',
                                   'Std Dev (rolling N, see Stats tab)'])
        self.cb_display.setCurrentIndex(0)
        self.cb_display.currentIndexChanged.connect(self._on_display_changed)
        row2.addWidget(self.cb_display)

        row2.addWidget(QLabel('Baseline:'))
        self.cb_baseline = QComboBox()
        self.cb_baseline.addItems(['Static capture', 'Rolling median', 'Nominal thresholds'])
        self.cb_baseline.currentIndexChanged.connect(self._on_baseline_mode_changed)
        row2.addWidget(self.cb_baseline)

        row2.addWidget(QLabel('N='))
        self.sp_capture_n = QSpinBox()
        self.sp_capture_n.setRange(1, 4096)
        self.sp_capture_n.setValue(CAPTURE_FRAMES_DEFAULT)
        row2.addWidget(self.sp_capture_n)

        self.pb_capture = QPushButton('Capture baseline')
        self.pb_capture.clicked.connect(self._start_capture)
        row2.addWidget(self.pb_capture)

        self.pb_clear = QPushButton('Clear baseline')
        self.pb_clear.clicked.connect(self.clear_baseline)
        row2.addWidget(self.pb_clear)

        self.pb_freeze = QPushButton('Freeze')
        self.pb_freeze.setCheckable(True)
        self.pb_freeze.toggled.connect(self._on_freeze_toggled)
        row2.addWidget(self.pb_freeze)
        layout.addLayout(row2)

        # Row 3 — scale + rolling T + baseline info
        row3 = QHBoxLayout()
        self.cb_autoscale = QCheckBox('Auto ±')
        self.cb_autoscale.setChecked(True)
        self.cb_autoscale.toggled.connect(self._on_autoscale_toggled)
        row3.addWidget(self.cb_autoscale)

        row3.addWidget(QLabel('Range (µV):'))
        self.sp_range = QDoubleSpinBox()
        self.sp_range.setRange(100, 5_000_000)
        self.sp_range.setSingleStep(10_000)
        self.sp_range.setDecimals(0)
        self.sp_range.setValue(self._manual_range)
        self.sp_range.setEnabled(False)
        self.sp_range.valueChanged.connect(self._on_range_changed)
        row3.addWidget(self.sp_range)

        row3.addWidget(QLabel('Rolling T (s):'))
        self.sp_rolling_t = QDoubleSpinBox()
        self.sp_rolling_t.setRange(0.5, 60.0)
        self.sp_rolling_t.setSingleStep(0.5)
        self.sp_rolling_t.setDecimals(1)
        self.sp_rolling_t.setValue(ROLLING_SECS_DEFAULT)
        self.sp_rolling_t.valueChanged.connect(self._on_rolling_t_changed)
        row3.addWidget(self.sp_rolling_t)

        self.lbl_baseline_info = QLabel('No baseline')
        row3.addWidget(self.lbl_baseline_info, stretch=1)

        self.lbl_scale = QLabel('Scale: —')
        row3.addWidget(self.lbl_scale)
        layout.addLayout(row3)

        # Main view stack (2D heatmap / 3D surface)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_heatmap_widget())   # index 0
        self.stack.addWidget(self._build_3d_widget())        # index 1
        layout.addWidget(self.stack, stretch=1)

        btn_toggle = QHBoxLayout()
        self.pb_toggle3d = QPushButton('Switch to 3D Surface')
        self.pb_toggle3d.clicked.connect(self._toggle_3d)
        btn_toggle.addWidget(self.pb_toggle3d)
        btn_toggle.addStretch(1)
        layout.addLayout(btn_toggle)

        # Zero-crossing summary
        self.lbl_crossings = QLabel('Crossings: —')
        layout.addWidget(self.lbl_crossings)

        # ML bridge — row A
        ml_a = QHBoxLayout()
        ml_a.addWidget(QLabel('Label:'))
        self.le_label = QLineEdit()
        self.le_label.setPlaceholderText('e.g. air / silver_coin / stainless_bolt')
        ml_a.addWidget(self.le_label, stretch=1)

        self.pb_snapshot = QPushButton('Record Snapshot')
        self.pb_snapshot.clicked.connect(self._record_snapshot)
        ml_a.addWidget(self.pb_snapshot)

        self.cb_continuous = QCheckBox('Log Continuously')
        self.cb_continuous.toggled.connect(self._on_continuous_toggled)
        ml_a.addWidget(self.cb_continuous)

        self.lbl_rows = QLabel('Rows: 0')
        ml_a.addWidget(self.lbl_rows)
        layout.addLayout(ml_a)

        # ML bridge — row B (CSV path)
        ml_b = QHBoxLayout()
        ml_b.addWidget(QLabel('CSV:'))
        self.le_csv = QLineEdit(_csv_default_path())
        ml_b.addWidget(self.le_csv, stretch=1)
        pb_browse = QPushButton('Browse…')
        pb_browse.clicked.connect(self._browse_csv)
        ml_b.addWidget(pb_browse)
        layout.addLayout(ml_b)

        return w

    def _build_heatmap_widget(self):
        self.gw = pg.GraphicsLayoutWidget()
        self.plot = self.gw.addPlot()
        self.plot.invertY(True)
        self.plot.setDefaultPadding(0)

        self.img = pg.ImageItem()
        self.img.setColorMap(self.cm_div)
        self.plot.addItem(self.img)

        self._rebuild_heatmap_axes()

        self.plot.scene().sigMouseMoved.connect(self._on_mouse_move)
        return self.gw

    def _rebuild_heatmap_axes(self):
        ax_b = self.plot.getAxis('bottom')
        ax_b.setTicks([[(j + 0.5, self._cell_labels[j]) for j in range(self._n_cells)]])
        ax_b.setLabel('Threshold' if self._has_threshold_v else 'Cell')

        ax_l = self.plot.getAxis('left')
        ax_l.setTicks([[(d + 0.5, self._display_band_labels[d]) for d in range(self._n_bands)]])
        ax_l.setLabel('Band')

        self.plot.setXRange(0, self._n_cells, padding=0)
        self.plot.setYRange(0, self._n_bands, padding=0)

    def _build_3d_widget(self):
        if not _GL_AVAILABLE:
            w   = QWidget()
            lbl = QLabel('3D view requires PyOpenGL — install python3-pyopengl')
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            QVBoxLayout(w).addWidget(lbl)
            return w

        self.gl_widget = gl.GLViewWidget()
        self.gl_widget.setCameraPosition(distance=15, elevation=30, azimuth=45)
        self._surface = gl.GLSurfacePlotItem(
            x=np.arange(self._n_cells, dtype=float),
            y=np.arange(self._n_bands, dtype=float),
            z=np.zeros((self._n_cells, self._n_bands)),
            smooth=False,
        )
        self.gl_widget.addItem(self._surface)
        return self.gl_widget

    def _rebuild_3d_surface(self):
        if not _GL_AVAILABLE or not hasattr(self, '_surface'):
            return
        self._surface.setData(
            x=np.arange(self._n_cells, dtype=float),
            y=np.arange(self._n_bands, dtype=float),
            z=np.zeros((self._n_cells, self._n_bands)))

    # ------------------------------------------------------------------
    # Tab 1 — Stats & Isolation
    # ------------------------------------------------------------------
    def _build_stats_tab(self):
        w      = QWidget()
        layout = QVBoxLayout(w)

        # Controls row
        ctrl = QHBoxLayout()
        self.pb_freeze_stats = QPushButton('Freeze')
        self.pb_freeze_stats.setCheckable(True)
        self.pb_freeze_stats.toggled.connect(self._on_freeze_stats_toggled)
        ctrl.addWidget(self.pb_freeze_stats)

        lbl_std_n = QLabel('Std dev N:')
        lbl_std_n.setToolTip('Rolling sample window, shared with the Heatmap tab\'s '
                              '"Std Dev" display mode and the Analysis tab heatmap.')
        ctrl.addWidget(lbl_std_n)
        self.sp_stats_window = QSpinBox()
        self.sp_stats_window.setRange(2, 2000)
        self.sp_stats_window.setSingleStep(10)
        self.sp_stats_window.setValue(50)
        self.sp_stats_window.setToolTip(lbl_std_n.toolTip())
        ctrl.addWidget(self.sp_stats_window)

        pb_save_stats = QPushButton('Save table CSV…')
        pb_save_stats.clicked.connect(self._save_stats_csv)
        ctrl.addWidget(pb_save_stats)

        self.pb_record = QPushButton('Record Session')
        self.pb_record.setCheckable(True)
        self.pb_record.setStyleSheet(self.MY_YELLOW)
        self.pb_record.toggled.connect(self._toggle_record_frames)
        ctrl.addWidget(self.pb_record)

        ctrl.addWidget(QLabel('Std:'))
        self.sp_std_lower = QDoubleSpinBox()
        self.sp_std_lower.setRange(0.0, 999.0)
        self.sp_std_lower.setDecimals(2)
        self.sp_std_lower.setSingleStep(0.05)
        self.sp_std_lower.setValue(0.50)
        self.sp_std_lower.setMaximumWidth(70)
        ctrl.addWidget(self.sp_std_lower)

        ctrl.addWidget(QLabel('–'))

        self.sp_std_upper = QDoubleSpinBox()
        self.sp_std_upper.setRange(0.0, 999.0)
        self.sp_std_upper.setDecimals(2)
        self.sp_std_upper.setSingleStep(0.05)
        self.sp_std_upper.setValue(1.00)
        self.sp_std_upper.setMaximumWidth(70)
        ctrl.addWidget(self.sp_std_upper)

        ctrl.addStretch(1)

        pb_rows_shrink = QPushButton('−')
        pb_rows_shrink.setMaximumWidth(28)
        pb_rows_shrink.clicked.connect(self._stats_rows_shrink)
        ctrl.addWidget(pb_rows_shrink)

        pb_rows_grow = QPushButton('+')
        pb_rows_grow.setMaximumWidth(28)
        pb_rows_grow.clicked.connect(self._stats_rows_grow)
        ctrl.addWidget(pb_rows_grow)

        ctrl.addWidget(QLabel('All values in mV'))
        layout.addLayout(ctrl)

        # Stats table: Band | Threshold | Delay µs | Latest mV | Mean mV | Std mV
        self.tbl_stats = QTableWidget(self._n_channels, 6)
        self.tbl_stats.setHorizontalHeaderLabels(
            ['Band', 'Threshold', 'Delay (µs)', 'Latest (mV)', 'Mean (mV)', 'Std (mV)'])
        self.tbl_stats.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_stats.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_stats.setAlternatingRowColors(True)
        self._rebuild_stats_table()

        layout.addWidget(self.tbl_stats, stretch=1)
        return w

    def _rebuild_stats_table(self):
        self.tbl_stats.setRowCount(self._n_channels)
        for d in range(self._n_bands):
            b = self._band_stats_order[d]
            freq_hz, pulse_us, delays = self._bands_meta[b]
            for c in range(self._n_cells):
                row = d * self._n_cells + c
                for col, text in enumerate([self._stats_band_labels[d],
                                            self._cell_labels[c],
                                            '{0:.3f}'.format(delays[c])]):
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(_C)
                    self.tbl_stats.setItem(row, col, item)
                for col in range(3, 6):
                    item = QTableWidgetItem('—')
                    item.setTextAlignment(_R)
                    self.tbl_stats.setItem(row, col, item)

    # ------------------------------------------------------------------
    # Saved-profile selector (top bar) — load a profile JSON from disk and
    # send it straight to the board as a dynamic (RAM-only) profile.
    # ------------------------------------------------------------------
    def _refresh_profile_file_list(self):
        self.cb_profile_file.clear()
        for name in _list_profile_files():
            self.cb_profile_file.addItem(name)

    def _build_d_command(self, profile):
        parts = ['D{0}'.format(profile['averages'])]
        for b in profile['bands']:
            fields = [str(b['freq_hz']), '{0:.3f}'.format(b['pulse_us'])]
            fields += ['{0:.3f}'.format(d) for d in b['delays_us']]
            parts.append(','.join(fields))
        return ';'.join(parts)

    def _on_load_run_profile(self):
        name = self.cb_profile_file.currentText()
        if not name:
            self.statusBar().showMessage('No saved profile selected')
            return
        try:
            profile, profile_raw_bytes = _load_profile_file(name)
        except Exception as e:
            self.statusBar().showMessage('Load failed: {0}'.format(e))
            return
        if not self.serial.isOpen():
            self.statusBar().showMessage('Not connected')
            return
        cmd = self._build_d_command(profile)
        self.send_command('E')
        self.send_command(cmd)
        self.send_command('Q{0}'.format(DYNAMIC_PROFILE_INDEX))
        self.send_command('G')
        self._apply_profile(profile, DYNAMIC_PROFILE_INDEX, profile_raw_bytes)
        self.pb_start.setText('Running')
        self.pb_start.setStyleSheet(self.MY_GREEN)
        self.statusBar().showMessage('Loaded and running profile: {0}'.format(
            profile.get('name', name)))

    # ------------------------------------------------------------------
    # Tab 2 — Training Session
    # ------------------------------------------------------------------
    def _build_training_session_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Control row
        ctrl = QHBoxLayout()
        self.pb_training_start = QPushButton('Start')
        self.pb_training_start.setStyleSheet(self.MY_GREEN)
        self.pb_training_start.clicked.connect(self._on_training_start)
        ctrl.addWidget(self.pb_training_start)

        self.pb_training_pause = QPushButton('Pause')
        self.pb_training_pause.setCheckable(True)
        self.pb_training_pause.setEnabled(False)
        self.pb_training_pause.toggled.connect(self._on_training_pause_toggled)
        ctrl.addWidget(self.pb_training_pause)

        self.pb_training_stop = QPushButton('Stop')
        self.pb_training_stop.setStyleSheet(self.MY_RED)
        self.pb_training_stop.setEnabled(False)
        self.pb_training_stop.clicked.connect(self._on_training_stop)
        ctrl.addWidget(self.pb_training_stop)

        ctrl.addStretch(1)

        ctrl.addWidget(QLabel('Settle window (frames):'))
        self.sp_training_settle = QSpinBox()
        self.sp_training_settle.setRange(2, 2000)
        self.sp_training_settle.setSingleStep(10)
        self.sp_training_settle.setValue(50)
        ctrl.addWidget(self.sp_training_settle)

        self.lbl_training_status = QLabel('Not recording')
        ctrl.addWidget(self.lbl_training_status)
        layout.addLayout(ctrl)

        hint = QLabel('Press Space to advance to the next target and mark it.')
        hint.setStyleSheet('color: gray;')
        layout.addWidget(hint)

        # Table: Index | Target ID | Distance (mm) | Time at Target (s) | Settledness (mV)
        self._training_row_placement = {}   # opaque token -> placement dict (survives Add/Remove Row)
        self._training_row_token_seq = 0
        self.tbl_training = QTableWidget(0, 5)
        self.tbl_training.setHorizontalHeaderLabels(
            ['Index', 'Target ID', 'Distance (mm)', 'Time at Target (s)', 'Settledness (mV)'])
        self.tbl_training.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_training.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.tbl_training.itemChanged.connect(self._on_training_table_changed)
        self._insert_default_training_row()
        layout.addWidget(self.tbl_training, stretch=1)

        # Add/Remove row + Placement… + validation
        row_btns = QHBoxLayout()
        self.pb_training_add_row = QPushButton('Add Row')
        self.pb_training_add_row.clicked.connect(self._on_training_add_row)
        row_btns.addWidget(self.pb_training_add_row)
        self.pb_training_remove_row = QPushButton('Remove Row')
        self.pb_training_remove_row.clicked.connect(self._on_training_remove_row)
        row_btns.addWidget(self.pb_training_remove_row)
        self.pb_training_placement = QPushButton('Placement…')
        self.pb_training_placement.setToolTip(
            'Edit the selected row\'s placement (long_axis/face_normal/offsets/medium/notes) -- '
            'same widget set as the Analysis tab.')
        self.pb_training_placement.clicked.connect(self._on_training_placement_clicked)
        row_btns.addWidget(self.pb_training_placement)
        row_btns.addStretch(1)
        layout.addLayout(row_btns)

        self.lbl_training_validation = QLabel('')
        layout.addWidget(self.lbl_training_validation)

        # Saved target-list template — mirrors the top-bar Saved-profile pattern
        row_list = QHBoxLayout()
        row_list.addWidget(QLabel('Saved list:'))
        self.cb_training_list = QComboBox()
        self._refresh_training_list_file_list()
        row_list.addWidget(self.cb_training_list, stretch=1)
        self.pb_training_load_list = QPushButton('Load List')
        self.pb_training_load_list.clicked.connect(self._on_training_load_list)
        row_list.addWidget(self.pb_training_load_list)
        self.pb_training_save_list = QPushButton('Save List…')
        self.pb_training_save_list.clicked.connect(self._on_training_save_list)
        row_list.addWidget(self.pb_training_save_list)
        layout.addLayout(row_list)

        self._validate_training_table()
        return w

    # -- row construction / editability -----------------------------------

    def _make_training_item(self, text, editable):
        item = QTableWidgetItem(text)
        item.setTextAlignment(_C)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _default_placement(self):
        return {'target_id': 'air', 'distance_mm': 0, 'long_axis': 'na', 'face_normal': 'na',
                'offset_x_mm': 0, 'offset_y_mm': 0, 'medium': 'air', 'repeat_idx': 1, 'notes': ''}

    def _populate_training_row(self, row, target_id, distance_mm, placement=None):
        self._training_row_token_seq += 1
        token = self._training_row_token_seq
        item0 = self._make_training_item('', editable=False)
        item0.setData(Qt.ItemDataRole.UserRole, token)
        self.tbl_training.setItem(row, 0, item0)
        self.tbl_training.setItem(row, 1, self._make_training_item(str(target_id), editable=True))
        try:
            dist_text = str(int(float(distance_mm)))
        except (TypeError, ValueError):
            dist_text = str(distance_mm)
        self.tbl_training.setItem(row, 2, self._make_training_item(dist_text, editable=True))
        self.tbl_training.setItem(row, 3, self._make_training_item('—', editable=False))
        self.tbl_training.setItem(row, 4, self._make_training_item('—', editable=False))
        self._training_row_placement[token] = dict(placement) if placement else self._default_placement()

    def _insert_default_training_row(self):
        self.tbl_training.blockSignals(True)
        r = self.tbl_training.rowCount()
        self.tbl_training.insertRow(r)
        self._populate_training_row(r, 'air', 0)
        self._renumber_training_rows()
        self.tbl_training.blockSignals(False)

    def _renumber_training_rows(self):
        for r in range(self.tbl_training.rowCount()):
            self.tbl_training.item(r, 0).setText(str(r + 1))

    # -- add/remove rows ----------------------------------------------------

    def _on_training_add_row(self):
        self.tbl_training.blockSignals(True)
        r = self.tbl_training.rowCount()
        self.tbl_training.insertRow(r)
        self._populate_training_row(r, '', 0)
        self._renumber_training_rows()
        self.tbl_training.blockSignals(False)
        self._validate_training_table()

    def _on_training_remove_row(self):
        r = self.tbl_training.currentRow()
        if r >= 0:
            token = self.tbl_training.item(r, 0).data(Qt.ItemDataRole.UserRole)
            self._training_row_placement.pop(token, None)
            self.tbl_training.blockSignals(True)
            self.tbl_training.removeRow(r)
            self._renumber_training_rows()
            self.tbl_training.blockSignals(False)
        self._validate_training_table()

    def _on_training_table_changed(self, item):
        self._validate_training_table()

    # -- Placement… dialog (shares _build_target_placement_widget_set with --
    # -- the Analysis tab's inline widgets -- one implementation) -----------

    def _on_training_placement_clicked(self):
        row = self.tbl_training.currentRow()
        if row < 0:
            self.statusBar().showMessage('Select a row first.')
            return
        token = self.tbl_training.item(row, 0).data(Qt.ItemDataRole.UserRole)
        current = self._training_row_placement.get(token, self._default_placement())
        current_target_id = self.tbl_training.item(row, 1).text().strip() or current.get('target_id')

        dlg = QDialog(self)
        dlg.setWindowTitle('Placement — row {0}'.format(row + 1))
        dlg_layout = QVBoxLayout(dlg)
        self._build_target_placement_widget_set(dlg_layout, 'training_dlg')
        self._populate_target_combo(self.training_dlg_target, selected_target_id=current_target_id)
        try:
            self.training_dlg_distance_mm.setValue(int(float(
                self.tbl_training.item(row, 2).text().strip() or current.get('distance_mm', 0) or 0)))
        except ValueError:
            self.training_dlg_distance_mm.setValue(int(current.get('distance_mm', 0) or 0))
        self.training_dlg_long_axis.setCurrentText(current.get('long_axis', 'na'))
        self.training_dlg_face_normal.setCurrentText(current.get('face_normal', 'na'))
        self.training_dlg_offset_x_mm.setValue(int(current.get('offset_x_mm', 0)))
        self.training_dlg_offset_y_mm.setValue(int(current.get('offset_y_mm', 0)))
        self.training_dlg_medium.setCurrentText(current.get('medium', 'air'))
        self.training_dlg_repeat_idx.setValue(int(current.get('repeat_idx', 1)))
        self.training_dlg_notes.setText(current.get('notes', ''))

        btn_row = QHBoxLayout()
        pb_ok = QPushButton('OK')
        pb_ok.clicked.connect(dlg.accept)
        pb_cancel = QPushButton('Cancel')
        pb_cancel.clicked.connect(dlg.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(pb_ok)
        btn_row.addWidget(pb_cancel)
        dlg_layout.addLayout(btn_row)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        placement = self._placement_from_widgets('training_dlg')
        self._training_row_placement[token] = placement
        self.tbl_training.blockSignals(True)
        self.tbl_training.item(row, 1).setText(placement['target_id'] or 'air')
        self.tbl_training.item(row, 2).setText(str(placement['distance_mm']))
        self.tbl_training.blockSignals(False)
        self._validate_training_table()

    # -- validation -----------------------------------------------------

    def _validate_training_table(self):
        rows = self.tbl_training.rowCount()
        has_air = False
        error = None
        if rows == 0:
            error = 'no target rows defined'
        else:
            for r in range(rows):
                target_id = self.tbl_training.item(r, 1).text().strip()
                dist_text = self.tbl_training.item(r, 2).text().strip()
                if not target_id:
                    error = 'row {0}: empty target'.format(r + 1)
                    break
                try:
                    float(dist_text)
                except ValueError:
                    error = 'row {0}: distance is not a number'.format(r + 1)
                    break
                if target_id.lower() == 'air':
                    has_air = True
                elif target_id not in self._targets:
                    error = "row {0}: target_id '{1}' not in the registry".format(r + 1, target_id)
                    break
            if error is None and not has_air:
                error = 'no row has Target ID = "air" (required by pimd_features.py)'

        valid = error is None
        if valid:
            self.lbl_training_validation.setText('✓ {0} targets'.format(rows))
            self.lbl_training_validation.setStyleSheet('color: green;')
        else:
            self.lbl_training_validation.setText('✗ {0}'.format(error))
            self.lbl_training_validation.setStyleSheet('color: red;')

        if self._training_current_row is None:   # never re-enable Start mid-session
            self.pb_training_start.setEnabled(valid)
        return valid

    # -- mark-text rule (mirrors the deleted _on_mark_hotkey branches) ------

    def _training_row_mark_text(self, row):
        target = self.tbl_training.item(row, 1).text().strip()
        if target.lower() == 'air':
            return 'air'   # no @ suffix — required exact match for pimd_features.py
        distance = self.tbl_training.item(row, 2).text().strip()
        return '{0} @{1}'.format(target, distance)

    def _training_row_mark_target_dict(self, row):
        """(target_id, placement dict) for _append_mark_target() -- distance_mm
        and target_id come from the row's live table cells (the source of
        truth for quick edits); the remaining placement fields come from
        _training_row_placement (set via the Placement… dialog)."""
        token = self.tbl_training.item(row, 0).data(Qt.ItemDataRole.UserRole)
        placement = dict(self._training_row_placement.get(token, self._default_placement()))
        target_id = self.tbl_training.item(row, 1).text().strip()
        dist_text = self.tbl_training.item(row, 2).text().strip()
        placement['target_id'] = target_id
        if target_id.lower() == 'air':
            placement['distance_mm'] = None
        else:
            try:
                placement['distance_mm'] = float(dist_text)
            except ValueError:
                placement['distance_mm'] = None
        return target_id, placement

    # -- Start / Pause / Stop / Space ---------------------------------------

    def _on_training_start(self):
        if not self._validate_training_table():
            self.statusBar().showMessage('Training list invalid — fix the table before starting.')
            return
        if not self.serial.isOpen() or self.pb_start.text() != 'Running':
            self.statusBar().showMessage(
                'Connect and start streaming before beginning a training session.')
            return
        if self._recording:
            self.statusBar().showMessage('A session is already recording — stop it first.')
            return

        self._clear_training_live_columns()

        # Reuses _session_start()'s file-open/header machinery verbatim, but
        # passes notes derived from the run list instead of popping up the
        # interactive notes prompt (there's nothing to ask the operator that
        # isn't already in the table). Syncs pb_record's checked state without
        # re-entering _toggle_record_frames -> _session_start() a second time.
        self._session_start(notes=self._build_training_notes())
        self.pb_record.blockSignals(True)
        self.pb_record.setChecked(True)
        self.pb_record.blockSignals(False)

        self._training_current_row = 0
        self._training_paused = False
        self._training_row_start_wall = time.time()
        self._append_mark(self._training_row_mark_text(0))
        target_id, placement = self._training_row_mark_target_dict(0)
        self._append_mark_target(target_id, placement)
        self.tbl_training.selectRow(0)
        self._set_training_active_ui(True)
        self._update_training_status_label()

    def _clear_training_live_columns(self):
        """Reset Time-at-Target and Settledness back to '—' for every row --
        otherwise a re-run of the same list would start showing the previous
        run's stale elapsed-time/settledness values on rows not yet reached."""
        for r in range(self.tbl_training.rowCount()):
            self.tbl_training.item(r, 3).setText('—')
            self.tbl_training.item(r, 4).setText('—')

    def _build_training_notes(self):
        """Session notes auto-derived from the run list, replacing the
        interactive notes prompt: nothing the operator would type isn't
        already captured by the table itself."""
        lines = ['Training Session run list:']
        for r in range(self.tbl_training.rowCount()):
            idx = self.tbl_training.item(r, 0).text()
            target = self.tbl_training.item(r, 1).text()
            distance = self.tbl_training.item(r, 2).text()
            lines.append('{0}. {1} @{2}mm'.format(idx, target, distance))
        return '\n'.join(lines)

    def _on_training_pause_toggled(self, checked):
        if checked:
            self._training_paused = True
            self._training_pause_started = time.time()
            self.pb_training_pause.setText('Resume')
            self.pb_training_pause.setStyleSheet(self.MY_YELLOW)
        else:
            self._training_paused = False
            if self._training_pause_started is not None:
                self._training_row_start_wall += (time.time() - self._training_pause_started)
            self._training_pause_started = None
            self.pb_training_pause.setText('Pause')
            self.pb_training_pause.setStyleSheet('')
        self._update_training_status_label()

    def _on_training_stop(self):
        if self._training_current_row is None:
            return
        self.pb_record.setChecked(False)   # -> _session_stop() -> centralized reset

    def _on_training_space(self):
        if self._training_current_row is None:
            return
        if self._training_paused:
            self.statusBar().showMessage('Paused — resume before marking next target')
            return

        last = self.tbl_training.rowCount() - 1
        if self._training_current_row >= last:
            n_targets = self.tbl_training.rowCount()
            path = self._session_path
            self.pb_record.setChecked(False)   # -> _session_stop() -> centralized reset
            self.statusBar().showMessage(
                'Training session complete: {0} targets recorded → {1}'.format(n_targets, path))
        else:
            self._training_current_row += 1
            self._training_row_start_wall = time.time()
            self._append_mark(self._training_row_mark_text(self._training_current_row))
            target_id, placement = self._training_row_mark_target_dict(self._training_current_row)
            self._append_mark_target(target_id, placement)
            self.tbl_training.selectRow(self._training_current_row)
            self._update_training_status_label()

    # -- UI enablement / reset -----------------------------------------

    def _set_training_active_ui(self, active):
        self.pb_training_start.setEnabled(not active and self._validate_training_table())
        self.pb_training_pause.setEnabled(active)
        self.pb_training_stop.setEnabled(active)
        self.pb_training_add_row.setEnabled(not active)
        self.pb_training_remove_row.setEnabled(not active)
        self.pb_training_placement.setEnabled(not active)
        self.pb_training_load_list.setEnabled(not active)
        self.pb_training_save_list.setEnabled(not active)
        self.tbl_training.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers if active
            else QAbstractItemView.EditTrigger.DoubleClicked)
        if not active:
            self.pb_training_pause.blockSignals(True)
            self.pb_training_pause.setChecked(False)
            self.pb_training_pause.setText('Pause')
            self.pb_training_pause.setStyleSheet('')
            self.pb_training_pause.blockSignals(False)

    def _update_training_status_label(self):
        if self._training_current_row is None:
            self.lbl_training_status.setText('Not recording')
        else:
            n = self.tbl_training.rowCount()
            state = ' (paused)' if self._training_paused else ''
            self.lbl_training_status.setText('Recording — target {0}/{1}{2}'.format(
                self._training_current_row + 1, n, state))

    def _reset_training_ui(self):
        """Called from _session_stop() whenever a Training Session was active
        when the underlying recording got closed out — from any of its
        trigger points, not just our own Stop button."""
        self._training_current_row = None
        self._training_paused = False
        self._training_pause_started = None
        self._training_row_start_wall = None
        self._set_training_active_ui(False)
        self._update_training_status_label()

    # -- live update (called from _redraw()) -----------------------------

    def _update_training_live(self):
        row = self._training_current_row
        n = self.sp_training_settle.value()
        recent = list(self._rolling_buf)[-n:]
        if len(recent) >= 2:
            mat = np.array([arr for _, arr in recent], dtype=float)
            stds = mat.std(0)
            settle_text = '{0:.3f}'.format(stds.mean() / 1000.0)
        else:
            settle_text = '—'
        self.tbl_training.item(row, 4).setText(settle_text)

        if not self._training_paused:
            elapsed = time.time() - self._training_row_start_wall
            self.tbl_training.item(row, 3).setText('{0:.1f}'.format(elapsed))

    # -- saved target-list template ---------------------------------------

    def _refresh_training_list_file_list(self):
        self.cb_training_list.clear()
        for name in _list_training_list_files():
            self.cb_training_list.addItem(name)

    def _on_training_load_list(self):
        name = self.cb_training_list.currentText()
        if not name:
            self.statusBar().showMessage('No saved target list selected')
            return
        try:
            data = _load_training_list_file(name)
        except Exception as e:
            self.statusBar().showMessage('Load failed: {0}'.format(e))
            return
        rows = data.get('rows', [])
        # Loud rejection, not a free-text -> target_id migration: a row
        # written by pre-v1.32 classviz (or hand-authored without target_id)
        # cannot be safely guessed against the registry (e.g. "steel
        # spanner" -> which target_id?). Re-author the list instead.
        missing = [i + 1 for i, r in enumerate(rows) if 'target_id' not in r]
        if missing:
            self.statusBar().showMessage(
                "'{0}' predates the target registry (row(s) {1} have no target_id) -- "
                're-author this list against the current registry; no automatic '
                'migration is attempted.'.format(name, ', '.join(str(i) for i in missing)))
            return
        self.tbl_training.blockSignals(True)
        self.tbl_training.setRowCount(0)
        self._training_row_placement = {}
        for r_data in rows:
            r = self.tbl_training.rowCount()
            self.tbl_training.insertRow(r)
            placement = dict(r_data.get('placement', {}))
            self._populate_training_row(r, r_data.get('target_id', ''), r_data.get('distance_mm', 0),
                                         placement=placement)
        if self.tbl_training.rowCount() == 0:
            self.tbl_training.insertRow(0)
            self._populate_training_row(0, 'air', 0)
        self._renumber_training_rows()
        self.tbl_training.blockSignals(False)
        self._validate_training_table()
        self.statusBar().showMessage('Loaded target list: {0} ({1} rows)'.format(
            name, self.tbl_training.rowCount()))

    def _on_training_save_list(self):
        name, ok = QInputDialog.getText(self, 'Save Target List', 'List name:')
        if not ok or not name.strip():
            return
        rows = []
        for r in range(self.tbl_training.rowCount()):
            target_id = self.tbl_training.item(r, 1).text().strip()
            dist_text = self.tbl_training.item(r, 2).text().strip()
            try:
                distance_mm = float(dist_text)
            except ValueError:
                self.statusBar().showMessage(
                    'Cannot save: row {0} has a non-numeric distance'.format(r + 1))
                return
            _target_id, placement = self._training_row_mark_target_dict(r)
            placement.pop('target_id', None)
            placement.pop('distance_mm', None)
            rows.append({'target_id': target_id, 'distance_mm': distance_mm, 'placement': placement})
        _save_training_list_file(name.strip(), rows)
        self._refresh_training_list_file_list()
        idx = self.cb_training_list.findText(name.strip())
        if idx >= 0:
            self.cb_training_list.setCurrentIndex(idx)
        self.statusBar().showMessage('Saved target list: {0}'.format(name.strip()))

    # ------------------------------------------------------------------
    # Tab 3 — Analysis
    # ------------------------------------------------------------------
    ANALYSIS_TAB_INDEX = 3

    def _style_compact(self, plot, title=None):
        """Small tick font + a little padding + optional small title --
        applied to every Analysis-tab plot so ~20 small panels can share
        one screen without their chrome eating the plot area."""
        font = QFont()
        font.setPointSize(7)
        plot.getAxis('bottom').setStyle(tickFont=font)
        plot.getAxis('left').setStyle(tickFont=font)
        plot.setDefaultPadding(0.02)
        if title:
            plot.setTitle(title, size='7pt')

    def _build_analysis_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Left column: Controls + Signatures + Heatmap, stacked, sharing one
        # width -- Signatures/Controls used to span the full tab width above
        # everything else; now they're grouped with the heatmap so the right
        # side (charts) can reach the top of the tab.
        left_col = QWidget()
        left_v = QVBoxLayout(left_col)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(4)

        top_box = QGroupBox('Controls')
        top_v = QVBoxLayout(top_box)
        top_v.setContentsMargins(4, 4, 4, 4)
        top_v.setSpacing(2)
        top_v.addLayout(self._build_analysis_ctrl_row_a())
        left_v.addWidget(top_box)
        left_v.addWidget(self._build_analysis_signatures_group())
        left_v.addWidget(self._build_analysis_training_group())
        left_v.addWidget(self._build_analysis_heatmap_group(), stretch=1)

        # Right column: row1 (strips | chart2 side by side) + 8-grid + 9-grid.
        row1_split = QSplitter(Qt.Orientation.Horizontal)
        row1_split.setHandleWidth(4)
        row1_split.addWidget(self._build_analysis_strips_group())
        row1_split.addWidget(self._build_analysis_chart2_group())
        row1_split.setSizes([700, 700])

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setHandleWidth(4)
        right_split.addWidget(row1_split)
        right_split.addWidget(self._build_analysis_grid8_group())
        right_split.addWidget(self._build_analysis_grid9_group())
        right_split.setSizes([220, 260, 260])

        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.setHandleWidth(4)
        main_split.addWidget(left_col)
        main_split.addWidget(right_split)
        main_split.setSizes([560, 1440])
        layout.addWidget(main_split, stretch=1)

        return w

    def _build_analysis_ctrl_row_a(self):
        ctrl_a = QHBoxLayout()
        ctrl_a.addWidget(QLabel('Avg N frames:'))
        self.sp_analysis_avg_n = QSpinBox()
        self.sp_analysis_avg_n.setRange(1, 200)
        self.sp_analysis_avg_n.setValue(self._analysis_avg_n)
        self.sp_analysis_avg_n.valueChanged.connect(self._on_analysis_avg_n_changed)
        ctrl_a.addWidget(self.sp_analysis_avg_n)

        self.pb_analysis_capture = QPushButton('Capture baseline')
        self.pb_analysis_capture.clicked.connect(self._start_capture)
        ctrl_a.addWidget(self.pb_analysis_capture)

        self.pb_analysis_clear = QPushButton('Clear baseline')
        self.pb_analysis_clear.clicked.connect(self.clear_baseline)
        ctrl_a.addWidget(self.pb_analysis_clear)

        self.lbl_analysis_baseline_info = QLabel('No baseline')
        ctrl_a.addWidget(self.lbl_analysis_baseline_info)
        ctrl_a.addStretch(1)
        return ctrl_a

    def _build_analysis_signatures_group(self):
        box = QGroupBox('Signatures')
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(2)
        self._build_sig_row1_files(v)
        v.addWidget(self.lw_analysis_templates)
        self._build_sig_row2_capture_inputs(v)
        self._build_sig_row3_readout_save(v)
        self._build_sig_row4_session(v)
        self._update_sig_mode_label()
        self._update_sig_session_status_label()
        return box

    def _build_sig_row1_files(self, v):
        row_a = QHBoxLayout()
        pb_load_sigs = QPushButton('Load signatures…')
        pb_load_sigs.clicked.connect(self._on_load_signatures_clicked)
        row_a.addWidget(pb_load_sigs)

        pb_new = QPushButton('New file…')
        pb_new.clicked.connect(self._on_sig_new_file_clicked)
        row_a.addWidget(pb_new)
        row_a.addStretch(1)
        v.addLayout(row_a)

        row_b = QHBoxLayout()
        pb_open = QPushButton('Open for editing…')
        pb_open.clicked.connect(self._on_sig_open_for_edit_clicked)
        row_b.addWidget(pb_open)

        pb_clear_sigs = QPushButton('Clear signatures')
        pb_clear_sigs.clicked.connect(self._on_clear_signatures_clicked)
        row_b.addWidget(pb_clear_sigs)

        self.lbl_sig_mode = QLabel('Mode: read-only')
        row_b.addWidget(self.lbl_sig_mode, stretch=1)
        v.addLayout(row_b)

        # Shrunk from the original wrapped left-to-right "tag" flow --
        # labels now carry amp/SNR/quality text, so a normal scrollable
        # top-to-bottom list stays compact and legible, freeing room below
        # for the capture/save/session controls.
        self.lw_analysis_templates = QListWidget()
        self.lw_analysis_templates.setFlow(QListWidget.Flow.TopToBottom)
        self.lw_analysis_templates.setMaximumHeight(46)
        self.lw_analysis_templates.itemChanged.connect(self._on_analysis_template_item_changed)
        self.lw_analysis_templates.currentItemChanged.connect(lambda *_: self._update_sig_capture_gating())

    # -- Shared target/placement widget set (Analysis tab inline + Training --
    # -- tab Placement dialog) -- one implementation, two call sites ---------

    def _build_target_placement_widget_set(self, layout, prefix):
        """Builds a target-registry combo + structured placement widgets into
        `layout`, storing them as self.{prefix}_target, {prefix}_distance_mm,
        {prefix}_long_axis, {prefix}_face_normal, {prefix}_offset_x_mm,
        {prefix}_offset_y_mm, {prefix}_medium, {prefix}_repeat_idx,
        {prefix}_notes. Pure construction -- caller wires signals and calls
        _populate_target_combo() to fill the target combo from the currently
        loaded registry. Instantiated inline (Analysis tab) and inside a
        QDialog (Training tab's per-row Placement editor) so field
        definitions never duplicate."""
        row_a = QHBoxLayout()
        row_a.addWidget(QLabel('Target:'))
        target_combo = QComboBox()
        target_combo.setMinimumWidth(220)
        setattr(self, '{0}_target'.format(prefix), target_combo)
        row_a.addWidget(target_combo, stretch=1)

        row_a.addWidget(QLabel('Distance (mm):'))
        distance_mm = QSpinBox()
        distance_mm.setRange(0, 5000)
        distance_mm.setValue(50)
        distance_mm.setToolTip('Coil face → nearest target surface, in mm.')
        setattr(self, '{0}_distance_mm'.format(prefix), distance_mm)
        row_a.addWidget(distance_mm)
        layout.addLayout(row_a)

        row_b = QHBoxLayout()
        row_b.addWidget(QLabel('Long axis:'))
        long_axis = QComboBox()
        long_axis.addItems(['na', 'x', 'y', 'z'])
        long_axis.setToolTip(
            "Direction the target registry's dim_a points. x = coil long axis "
            '(520mm direction), y = coil short axis (360mm), z = coil normal '
            '(vertical). na for compact/isotropic targets.')
        setattr(self, '{0}_long_axis'.format(prefix), long_axis)
        row_b.addWidget(long_axis)

        row_b.addWidget(QLabel('Face normal:'))
        face_normal = QComboBox()
        face_normal.addItems(['na', 'x', 'y', 'z'])
        face_normal.setToolTip(
            'Normal of the dim_a × dim_b face (plates/discs/sheets). Same x/y/z '
            'convention as Long axis. na where meaningless.')
        setattr(self, '{0}_face_normal'.format(prefix), face_normal)
        row_b.addWidget(face_normal)

        row_b.addWidget(QLabel('Medium:'))
        medium = QComboBox()
        medium.addItems(['air', 'soil', 'other'])
        setattr(self, '{0}_medium'.format(prefix), medium)
        row_b.addWidget(medium)
        layout.addLayout(row_b)

        row_c = QHBoxLayout()
        row_c.addWidget(QLabel('Offset X (mm):'))
        offset_x_mm = QSpinBox()
        offset_x_mm.setRange(-500, 500)
        offset_x_mm.setToolTip('Target centroid offset from coil centre, coil long axis. 0 = centred.')
        setattr(self, '{0}_offset_x_mm'.format(prefix), offset_x_mm)
        row_c.addWidget(offset_x_mm)

        row_c.addWidget(QLabel('Offset Y (mm):'))
        offset_y_mm = QSpinBox()
        offset_y_mm.setRange(-500, 500)
        offset_y_mm.setToolTip('Target centroid offset from coil centre, coil short axis. 0 = centred.')
        setattr(self, '{0}_offset_y_mm'.format(prefix), offset_y_mm)
        row_c.addWidget(offset_y_mm)

        repeat_tip = (
            'Provenance metadata only — distinguishes repeated captures of the '
            'same placement tuple (target, distance, axes, offsets, medium) so '
            'they don\'t collide as one signature in the corpus CSV. '
            'Auto-suggested as count+1 from the open file\'s existing captures; '
            'editable. Not used in any matching/classification math.')
        lbl_repeat = QLabel('Repeat #:')
        lbl_repeat.setToolTip(repeat_tip)
        row_c.addWidget(lbl_repeat)
        repeat_idx = QSpinBox()
        repeat_idx.setRange(1, 999)
        repeat_idx.setValue(1)
        repeat_idx.setToolTip(repeat_tip)
        setattr(self, '{0}_repeat_idx'.format(prefix), repeat_idx)
        row_c.addWidget(repeat_idx)
        layout.addLayout(row_c)

        row_d = QHBoxLayout()
        row_d.addWidget(QLabel('Notes:'))
        notes = QLineEdit()
        setattr(self, '{0}_notes'.format(prefix), notes)
        row_d.addWidget(notes, stretch=1)
        layout.addLayout(row_d)

    def _populate_target_combo(self, combo, selected_target_id=None):
        combo.blockSignals(True)
        combo.clear()
        combo.addItem('air — (no target)', 'air')
        for target_id in sorted(self._targets):
            t = self._targets[target_id]
            combo.addItem('{0} — {1}'.format(target_id, t.short_name), target_id)
        idx = combo.findData(selected_target_id) if selected_target_id else -1
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _placement_from_widgets(self, prefix):
        """Reads the current values of a _build_target_placement_widget_set()
        instance back into a plain dict, keyed the same as
        pimd_features.parse_mark_target_line()'s companion fields."""
        target_combo = getattr(self, '{0}_target'.format(prefix))
        return {
            'target_id': target_combo.currentData(),
            'distance_mm': getattr(self, '{0}_distance_mm'.format(prefix)).value(),
            'long_axis': getattr(self, '{0}_long_axis'.format(prefix)).currentText(),
            'face_normal': getattr(self, '{0}_face_normal'.format(prefix)).currentText(),
            'offset_x_mm': getattr(self, '{0}_offset_x_mm'.format(prefix)).value(),
            'offset_y_mm': getattr(self, '{0}_offset_y_mm'.format(prefix)).value(),
            'medium': getattr(self, '{0}_medium'.format(prefix)).currentText(),
            'repeat_idx': getattr(self, '{0}_repeat_idx'.format(prefix)).value(),
            'notes': getattr(self, '{0}_notes'.format(prefix)).text().strip(),
        }

    def _update_sig_repeat_idx_suggestion(self):
        """Auto-increments the Analysis tab's repeat_idx spinbox to the next
        unused value for the current placement tuple, per the brief's rule
        (still user-editable afterward -- this only sets a suggestion)."""
        if not hasattr(self, 'sig_target'):
            return
        placement = self._placement_from_widgets('sig')
        key = self._placement_tuple_key(placement)
        suggested = self._editable_repeat_counts.get(key, 0) + 1
        self.sig_repeat_idx.blockSignals(True)
        self.sig_repeat_idx.setValue(suggested)
        self.sig_repeat_idx.blockSignals(False)

    # -- Target registry loading / degrade behavior --------------------------

    def _load_targets_registry(self, show_dialog_on_error=True):
        """(Re)loads the target registry and repopulates every combo built by
        _build_target_placement_widget_set(). Degrade behavior:
          - missing/unreadable file -> air-only, status bar message.
          - loads with errors -> dialog (if show_dialog_on_error) + only the
            non-erroring targets loaded, 'air' always present.
          - loads with only warnings -> status bar summary, fully populated.
        Called once at UI-build time and again from the reload button."""
        try:
            targets, issues = pimd_targets.load_targets(TARGETS_REGISTRY_PATH)
        except OSError as e:
            self._targets, self._target_issues = {}, []
            self.statusBar().showMessage(
                "Target registry not found at {0} -- capture disabled except 'air' "
                '({1})'.format(TARGETS_REGISTRY_PATH, e))
            self._repopulate_target_combos()
            return

        self._targets, self._target_issues = targets, issues
        errors = [i for i in issues if i.severity == 'error']
        warnings = [i for i in issues if i.severity == 'warning']
        if errors and show_dialog_on_error:
            QMessageBox.critical(
                self, 'Target registry errors',
                "The target registry has {0} error(s) -- affected rows are unusable "
                "(only 'air' and valid rows are selectable):\n\n{1}".format(
                    len(errors), '\n'.join(str(i) for i in errors)))
        if errors:
            self.statusBar().showMessage(
                'Target registry: {0} usable target(s), {1} error(s), {2} warning(s) '
                '-- see dialog / run pimd_targets.py for detail'.format(
                    len(targets), len(errors), len(warnings)))
        elif warnings:
            self.statusBar().showMessage(
                'Target registry loaded: {0} target(s), {1} warning(s) (run '
                'pimd_targets.py for detail)'.format(len(targets), len(warnings)))
        else:
            self.statusBar().showMessage('Target registry loaded: {0} target(s)'.format(len(targets)))
        self._repopulate_target_combos()

    def _repopulate_target_combos(self):
        if hasattr(self, 'sig_target'):
            current = self.sig_target.currentData()
            self._populate_target_combo(self.sig_target, selected_target_id=current)
        if hasattr(self, '_update_sig_capture_gating'):
            self._update_sig_capture_gating()

    def _on_reload_targets_registry_clicked(self):
        self._load_targets_registry(show_dialog_on_error=True)

    def _build_sig_row2_capture_inputs(self, v):
        self._build_target_placement_widget_set(v, 'sig')
        self.sig_target.currentIndexChanged.connect(self._update_sig_capture_gating)
        for widget, signal_name in (
            (self.sig_target, 'currentIndexChanged'), (self.sig_distance_mm, 'valueChanged'),
            (self.sig_long_axis, 'currentIndexChanged'), (self.sig_face_normal, 'currentIndexChanged'),
            (self.sig_offset_x_mm, 'valueChanged'), (self.sig_offset_y_mm, 'valueChanged'),
            (self.sig_medium, 'currentIndexChanged'),
        ):
            getattr(widget, signal_name).connect(self._update_sig_repeat_idx_suggestion)

        row_reload = QHBoxLayout()
        self.pb_sig_reload_registry = QPushButton('Reload targets')
        self.pb_sig_reload_registry.clicked.connect(self._on_reload_targets_registry_clicked)
        row_reload.addWidget(self.pb_sig_reload_registry)
        row_reload.addStretch(1)
        v.addLayout(row_reload)

    def _build_analysis_training_group(self):
        """Training group (v1.33) — continuous space-bar-driven air/target
        toggle. Replaces the v1.31/1.32 three-button air-before/target/
        air-after quick-capture; the settle gate, glitch exclusion and stats
        math are unchanged, only the operator flow is new."""
        box = QGroupBox('Training')
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(2)

        row_a = QHBoxLayout()
        self.pb_sig_train_start = QPushButton('Start Training')
        self.pb_sig_train_start.setCheckable(True)
        self.pb_sig_train_start.toggled.connect(self._on_sig_train_start_toggled)
        row_a.addWidget(self.pb_sig_train_start)

        self.pb_sig_train_acquire = QPushButton('Acquire (Space)')
        self.pb_sig_train_acquire.clicked.connect(self._on_sig_train_acquire)
        self.pb_sig_train_acquire.setToolTip(
            'Commits the freshest N clean settled frames as the current '
            'phase\'s capture. Only acts when the indicator is blue (READY). '
            'The Space bar does the same while the Analysis tab is visible.')
        row_a.addWidget(self.pb_sig_train_acquire)

        self.lbl_sig_train_status = QLabel('Idle — press Start Training')
        row_a.addWidget(self.lbl_sig_train_status, stretch=1)
        v.addLayout(row_a)

        row_b = QHBoxLayout()
        row_b.addWidget(QLabel('Frames:'))
        self.sp_sig_capture_n = QSpinBox()
        self.sp_sig_capture_n.setRange(10, 2000)
        self.sp_sig_capture_n.setValue(self._sig_capture_n)
        self.sp_sig_capture_n.setToolTip(
            'Frames per capture window. Applied at the next phase change or '
            'settle-loss restart, not mid-window.')
        row_b.addWidget(self.sp_sig_capture_n)

        row_b.addWidget(QLabel('Settle ≤ (mV):'))
        self.sp_sig_settle_mv = QDoubleSpinBox()
        self.sp_sig_settle_mv.setRange(0.05, 50.0)
        self.sp_sig_settle_mv.setDecimals(3)
        self.sp_sig_settle_mv.setSingleStep(0.1)
        self.sp_sig_settle_mv.setValue(1.0)
        self.sp_sig_settle_mv.setToolTip(
            'Settledness gate: collection only runs while the mean per-channel '
            'rolling std dev (over the Stats tab\'s "Std dev N" window — same '
            'metric as the Training tab\'s Settledness) is at or below this, so '
            'target/air transitions and the firmware\'s ~10 s rolling-average '
            'ramp can\'t enter the window. Raise to 50 to disable.')
        row_b.addWidget(self.sp_sig_settle_mv)

        self.lbl_sig_train_phase = QLabel('')
        row_b.addWidget(self.lbl_sig_train_phase, stretch=1)
        v.addLayout(row_b)

        self._update_sig_capture_gating()
        return box

    def _build_sig_row3_readout_save(self, v):
        row_a = QHBoxLayout()
        self.lbl_sig_readout = QLabel('Amp: —  Mean|Δ|: —  Splithalf: —  SNR: —  Quality: —')
        self.lbl_sig_readout.setWordWrap(True)
        row_a.addWidget(self.lbl_sig_readout, stretch=1)
        v.addLayout(row_a)

        row_b = QHBoxLayout()
        self.pb_sig_save = QPushButton('Save Signature')
        self.pb_sig_save.clicked.connect(self._on_sig_save_clicked)
        row_b.addWidget(self.pb_sig_save)

        self.pb_sig_delete = QPushButton('Delete Selected')
        self.pb_sig_delete.clicked.connect(self._on_sig_delete_clicked)
        row_b.addWidget(self.pb_sig_delete)
        row_b.addStretch(1)
        v.addLayout(row_b)

    def _build_sig_row4_session(self, v):
        row_a = QHBoxLayout()
        lbl_session = QLabel('Session (alternate path — full recording for pimd_features.py):')
        lbl_session.setWordWrap(True)
        row_a.addWidget(lbl_session, stretch=1)
        v.addLayout(row_a)

        row_b = QHBoxLayout()
        self.pb_sig_session_start = QPushButton('Start')
        self.pb_sig_session_start.clicked.connect(self._on_sig_session_start)
        row_b.addWidget(self.pb_sig_session_start)

        self.pb_sig_session_pause = QPushButton('Pause')
        self.pb_sig_session_pause.setCheckable(True)
        self.pb_sig_session_pause.setEnabled(False)
        self.pb_sig_session_pause.toggled.connect(self._on_sig_session_pause_toggled)
        row_b.addWidget(self.pb_sig_session_pause)

        self.pb_sig_session_stop = QPushButton('Stop')
        self.pb_sig_session_stop.setEnabled(False)
        self.pb_sig_session_stop.clicked.connect(self._on_sig_session_stop)
        row_b.addWidget(self.pb_sig_session_stop)

        self.pb_sig_session_mark = QPushButton('Mark')
        self.pb_sig_session_mark.setEnabled(False)
        self.pb_sig_session_mark.clicked.connect(self._on_sig_session_mark)
        row_b.addWidget(self.pb_sig_session_mark)

        self.lbl_sig_session_status = QLabel('Not recording')
        row_b.addWidget(self.lbl_sig_session_status)
        row_b.addStretch(1)
        v.addLayout(row_b)

    # -- Chart 1: Analysis heatmap variant (renamed/reformatted axes) -------

    def _build_analysis_heatmap_group(self):
        box = QGroupBox('Heatmap — Pulse Width × Threshold')
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(2)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel('Normalize:'))
        self.cb_hm_norm = QComboBox()
        self.cb_hm_norm.addItems(['Auto (sync Heatmap tab)', 'Δ deviation', 'Z normalised', 'RAW abs',
                                   'Std Dev (rolling N)'])
        self.cb_hm_norm.currentIndexChanged.connect(self._on_hm_norm_changed)
        ctrl.addWidget(self.cb_hm_norm)

        ctrl.addWidget(QLabel('Scale:'))
        self.cb_hm_scale_auto = QCheckBox('Auto ±')
        self.cb_hm_scale_auto.setChecked(True)
        self.cb_hm_scale_auto.toggled.connect(self._on_hm_scale_auto_toggled)
        ctrl.addWidget(self.cb_hm_scale_auto)
        self.sp_hm_scale_manual = QDoubleSpinBox()
        self.sp_hm_scale_manual.setRange(100, 5_000_000)
        self.sp_hm_scale_manual.setSingleStep(10_000)
        self.sp_hm_scale_manual.setDecimals(0)
        self.sp_hm_scale_manual.setValue(self._analysis_hm_manual_range_uv)
        self.sp_hm_scale_manual.setEnabled(False)
        self.sp_hm_scale_manual.valueChanged.connect(self._on_hm_scale_manual_changed)
        ctrl.addWidget(self.sp_hm_scale_manual)
        ctrl.addWidget(QLabel('µV'))
        ctrl.addStretch(1)
        v.addLayout(ctrl)

        v.addWidget(self._build_analysis_heatmap_widget())
        return box

    def _build_analysis_heatmap_widget(self):
        self.analysis_gw = pg.GraphicsLayoutWidget()
        self.analysis_plot = self.analysis_gw.addPlot()
        self.analysis_plot.invertY(True)
        self._style_compact(self.analysis_plot)

        self.analysis_img = pg.ImageItem()
        self.analysis_img.setColorMap(self.cm_div)
        self.analysis_plot.addItem(self.analysis_img)

        # Colorbar/legend, docked below the heatmap's x-axis via insert_in --
        # doubles as an interactive range control: dragging its handles sets
        # the image's levels directly (see _update_analysis_heatmap's Manual-
        # scale branch, which leaves the bar in control instead of overriding
        # it every redraw tick). Also gives the mV/σ <-> colour legend asked
        # for, without a second widget.
        self.analysis_colorbar = pg.ColorBarItem(
            values=(-self._analysis_hm_manual_range_uv, self._analysis_hm_manual_range_uv),
            colorMap=self.cm_div, orientation='horizontal', label='value (µV, σ for Z mode)')
        cbar_font = QFont()
        cbar_font.setPointSize(7)
        self.analysis_colorbar.axis.setStyle(tickFont=cbar_font)
        self.analysis_colorbar.setImageItem(self.analysis_img, insert_in=self.analysis_plot)
        self.analysis_colorbar.sigLevelsChanged.connect(self._on_analysis_colorbar_levels_changed)
        # setImageItem() above calls img.setLevels() while the image still
        # has no data -- pyqtgraph defers that (ImageItem._defferedLevels)
        # and replays it at the end of the *next* setImage() call, which
        # would otherwise clobber the first real levels _update_analysis_
        # heatmap computes. A throwaway zero image flushes that replay now.
        self.analysis_img.setImage(np.zeros((self._n_bands, self._n_cells)))

        self._rebuild_analysis_heatmap_axes()
        return self.analysis_gw

    def _analysis_hm_mode(self):
        return self._display_mode if self._analysis_hm_norm_auto else self._analysis_hm_display_mode

    def _on_hm_norm_changed(self, idx):
        self._analysis_hm_norm_auto = (idx == 0)
        if idx > 0:
            self._analysis_hm_display_mode = ('delta', 'z', 'raw', 'stddev')[idx - 1]

    def _on_hm_scale_auto_toggled(self, checked):
        self._analysis_hm_scale_auto = checked
        self.sp_hm_scale_manual.setEnabled(not checked)

    def _on_hm_scale_manual_changed(self, val):
        self._analysis_hm_manual_range_uv = val
        if not self._analysis_hm_scale_auto:
            lo = 0.0 if self._analysis_hm_mode() in ('raw', 'stddev') else -val
            self.analysis_colorbar.setLevels((lo, val))

    def _on_analysis_colorbar_levels_changed(self, _bar):
        """Fires only on an actual drag of the colorbar's handles (setLevels()
        calls made by our own redraw code don't emit this) -- mirror the
        dragged range back into the manual-range spinbox/state so they stay
        consistent and the range survives a settings save. Ignored in Auto
        mode: the next redraw tick snaps the bar back to the auto-computed
        range anyway, so a drag there wouldn't stick."""
        if self._analysis_hm_scale_auto:
            return
        lo, hi = self.analysis_colorbar.levels()
        val = hi if self._analysis_hm_mode() in ('raw', 'stddev') else max(abs(lo), abs(hi))
        self._analysis_hm_manual_range_uv = val
        self.sp_hm_scale_manual.blockSignals(True)
        self.sp_hm_scale_manual.setValue(val)
        self.sp_hm_scale_manual.blockSignals(False)

    def _rebuild_analysis_heatmap_axes(self):
        """Same data/row-order as the Heatmap tab's chart -- only the label
        text/format differs (Pulse Width y-axis, integer µs, no frequency;
        Threshold x-axis stays volts/2dp with each column's delay_us range
        across all bands as a second label line, since delay_us -- unlike
        threshold_v -- isn't constant per column across bands)."""
        ax_b = self.analysis_plot.getAxis('bottom')
        labels = []
        for j in range(self._n_cells):
            lo, hi = self._cell_delay_range_us[j]
            if self._has_threshold_v:
                thr = self._profile['bands'][0]['threshold_v'][j]
                labels.append('{0:.2f}V\n({1:.2f}-{2:.2f})'.format(thr, lo, hi))
            else:
                labels.append('c{0}\n({1:.2f}-{2:.2f})'.format(j, lo, hi))
        ax_b.setTicks([[(j + 0.5, labels[j]) for j in range(self._n_cells)]])
        ax_b.setLabel('Threshold' if self._has_threshold_v else 'Cell', **{'font-size': '7pt'})

        ax_l = self.analysis_plot.getAxis('left')
        pw_labels = ['{0:.0f}µs'.format(self._bands_meta[self._band_display_order[d]][1])
                     for d in range(self._n_bands)]
        ax_l.setTicks([[(d + 0.5, pw_labels[d]) for d in range(self._n_bands)]])
        ax_l.setLabel('Pulse Width', **{'font-size': '7pt'})

        self.analysis_plot.setXRange(0, self._n_cells, padding=0)
        self.analysis_plot.setYRange(0, self._n_bands, padding=0)

    # -- Chart 2: normalized band-mean vs pulse width -----------------------

    def _build_analysis_chart2_group(self):
        box = QGroupBox('Pulse Width Mean (normalized)')
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(2)
        self._build_analysis_c2_ctrl_row(v)
        v.addWidget(self._build_analysis_chart2())
        return box

    def _build_analysis_c2_ctrl_row(self, v):
        row_a = QHBoxLayout()
        row_a.addWidget(QLabel('Normalize:'))
        self.cb_c2_norm_auto = QCheckBox('Auto (− group mean)')
        self.cb_c2_norm_auto.setChecked(True)
        self.cb_c2_norm_auto.toggled.connect(self._on_c2_norm_auto_toggled)
        row_a.addWidget(self.cb_c2_norm_auto)
        row_a.addWidget(QLabel('Manual ref (mV):'))
        self.sp_c2_norm_manual = QDoubleSpinBox()
        self.sp_c2_norm_manual.setRange(-100_000, 100_000)
        self.sp_c2_norm_manual.setDecimals(3)
        self.sp_c2_norm_manual.setValue(self._analysis_c2_manual_ref)
        self.sp_c2_norm_manual.setEnabled(False)
        self.sp_c2_norm_manual.valueChanged.connect(self._on_c2_norm_manual_changed)
        row_a.addWidget(self.sp_c2_norm_manual)
        row_a.addStretch(1)
        v.addLayout(row_a)

        row_b = QHBoxLayout()
        row_b.addWidget(QLabel('Scale:'))
        self.cb_c2_scale_auto = QCheckBox('Auto')
        self.cb_c2_scale_auto.setChecked(True)
        self.cb_c2_scale_auto.toggled.connect(self._on_c2_scale_auto_toggled)
        row_b.addWidget(self.cb_c2_scale_auto)
        row_b.addWidget(QLabel('± range:'))
        self.sp_c2_scale_manual = QDoubleSpinBox()
        self.sp_c2_scale_manual.setRange(0.01, 1000)
        self.sp_c2_scale_manual.setDecimals(3)
        self.sp_c2_scale_manual.setValue(self._analysis_c2_manual_halfrange)
        self.sp_c2_scale_manual.setEnabled(False)
        self.sp_c2_scale_manual.valueChanged.connect(self._on_c2_scale_manual_changed)
        row_b.addWidget(self.sp_c2_scale_manual)
        row_b.addStretch(1)
        v.addLayout(row_b)

    def _build_analysis_chart2(self):
        self.analysis_c2_glw = pg.GraphicsLayoutWidget()
        self.analysis_c2_plot = self.analysis_c2_glw.addPlot()
        self.analysis_c2_plot.setLogMode(x=True, y=False)
        self._style_compact(self.analysis_c2_plot)
        self.analysis_c2_plot.setLabel('bottom', 'pulse width (µs)', **{'font-size': '7pt'})
        self.analysis_c2_refline = self.analysis_c2_plot.addLine(
            y=0.0, pen=pg.mkPen((150, 150, 150), width=1))
        self.analysis_c2_curve = self.analysis_c2_plot.plot(
            [], [], pen=pg.mkPen('b', width=2), symbol='o', symbolSize=5)
        self.analysis_c2_template_curves = {}
        self._rebuild_analysis_chart2_ticks()
        return self.analysis_c2_glw

    def _on_c2_norm_auto_toggled(self, checked):
        self._analysis_c2_norm_auto = checked
        self.sp_c2_norm_manual.setEnabled(not checked)
        self._refresh_analysis_overlays()

    def _on_c2_norm_manual_changed(self, val):
        self._analysis_c2_manual_ref = val
        self._refresh_analysis_overlays()

    def _on_c2_scale_auto_toggled(self, checked):
        self._analysis_c2_scale_auto = checked
        self.sp_c2_scale_manual.setEnabled(not checked)
        self._apply_c2_scale()

    def _on_c2_scale_manual_changed(self, val):
        self._analysis_c2_manual_halfrange = val
        self._apply_c2_scale()

    def _apply_c2_scale(self):
        if self._analysis_c2_scale_auto:
            self.analysis_c2_plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            self.analysis_c2_plot.disableAutoRange(axis=pg.ViewBox.YAxis)
            half = self._analysis_c2_manual_halfrange
            self.analysis_c2_plot.setYRange(-half, half, padding=0)

    def _rebuild_analysis_chart2_ticks(self):
        ticks = [(math.log10(p), '{0:.3g}'.format(p)) for p in self._pulse_us_sorted]
        self.analysis_c2_plot.getAxis('bottom').setTicks([ticks, []])
        # Explicit range: an InfiniteLine (the y=1 refline) doesn't
        # contribute to auto-range, so before any curve data arrives the
        # view would otherwise default to an arbitrary, mostly-empty span.
        lo, hi = math.log10(min(self._pulse_us_sorted)), math.log10(max(self._pulse_us_sorted))
        self.analysis_c2_plot.setXRange(lo, hi, padding=0.1)

    # -- 8-grid: one panel per band -- that band's own per-cell profile -----

    def _build_analysis_grid8_group(self):
        box = QGroupBox('Per Pulse Width Cell Profiles (8-grid)')
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(2)
        v.addLayout(self._build_analysis_g8_ctrl_row())
        v.addWidget(self._build_analysis_grid8())
        return box

    def _build_analysis_g8_ctrl_row(self):
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel('Normalize:'))
        self.cb_g8_norm_auto = QCheckBox('Auto (− group mean)')
        self.cb_g8_norm_auto.setChecked(True)
        self.cb_g8_norm_auto.toggled.connect(self._on_g8_norm_auto_toggled)
        ctrl.addWidget(self.cb_g8_norm_auto)
        ctrl.addWidget(QLabel('Manual ref (mV):'))
        self.sp_g8_norm_manual = QDoubleSpinBox()
        self.sp_g8_norm_manual.setRange(-100_000, 100_000)
        self.sp_g8_norm_manual.setDecimals(3)
        self.sp_g8_norm_manual.setValue(self._analysis_g8_manual_ref)
        self.sp_g8_norm_manual.setEnabled(False)
        self.sp_g8_norm_manual.valueChanged.connect(self._on_g8_norm_manual_changed)
        ctrl.addWidget(self.sp_g8_norm_manual)

        ctrl.addWidget(QLabel('Scale:'))
        self.cb_g8_scale_auto = QCheckBox('Auto')
        self.cb_g8_scale_auto.setChecked(True)
        self.cb_g8_scale_auto.toggled.connect(self._on_g8_scale_auto_toggled)
        ctrl.addWidget(self.cb_g8_scale_auto)
        ctrl.addWidget(QLabel('± range:'))
        self.sp_g8_scale_manual = QDoubleSpinBox()
        self.sp_g8_scale_manual.setRange(0.01, 1000)
        self.sp_g8_scale_manual.setDecimals(3)
        self.sp_g8_scale_manual.setValue(self._analysis_g8_manual_halfrange)
        self.sp_g8_scale_manual.setEnabled(False)
        self.sp_g8_scale_manual.valueChanged.connect(self._on_g8_scale_manual_changed)
        ctrl.addWidget(self.sp_g8_scale_manual)
        ctrl.addStretch(1)
        return ctrl

    def _build_analysis_grid8(self):
        self.analysis_g8_glw = pg.GraphicsLayoutWidget()
        self._rebuild_analysis_grid8()
        return self.analysis_g8_glw

    def _rebuild_analysis_grid8(self):
        """Rebuilds panel count/order to match the current profile's n_bands
        (called from _apply_profile() on every profile change, same pattern
        as _rebuild_stats_table/_rebuild_heatmap_axes). Y axis is linked
        across all panels (locked to panel 0) since they share one scale."""
        self.analysis_g8_glw.clear()
        self.analysis_g8_plots = []
        self.analysis_g8_curves = []
        self.analysis_g8_template_curves = []
        for i, b in enumerate(self._pulse_sort_order):
            plot = self.analysis_g8_glw.addPlot(row=0, col=i)
            self._style_compact(plot, title='{0:.0f}µs'.format(self._bands_meta[b][1]))
            if i > 0:
                plot.hideAxis('left')
            plot.addLine(y=0.0, pen=pg.mkPen((150, 150, 150), width=1))
            curve = plot.plot([], [], pen=pg.mkPen('b', width=2), symbol='o', symbolSize=4)
            self.analysis_g8_plots.append(plot)
            self.analysis_g8_curves.append(curve)
            self.analysis_g8_template_curves.append({})
        self._rebuild_analysis_grid8_ticks()

    def _rebuild_analysis_grid8_ticks(self):
        """x-axis: each cell's delay_us averaged across all bands (1 d.p.) --
        not threshold_v, so grid8 shows a different identifying dimension
        than grid9's per-panel titles."""
        ticks = [(j + 0.5, '{0:.1f}'.format(self._cell_delay_avg_us[j])) for j in range(self._n_cells)]
        for plot in self.analysis_g8_plots:
            plot.getAxis('bottom').setTicks([ticks])
            plot.setXRange(0, self._n_cells, padding=0)

    def _on_g8_norm_auto_toggled(self, checked):
        self._analysis_g8_norm_auto = checked
        self.sp_g8_norm_manual.setEnabled(not checked)
        self._refresh_analysis_overlays()

    def _on_g8_norm_manual_changed(self, val):
        self._analysis_g8_manual_ref = val
        self._refresh_analysis_overlays()

    def _on_g8_scale_auto_toggled(self, checked):
        self._analysis_g8_scale_auto = checked
        self.sp_g8_scale_manual.setEnabled(not checked)
        self._apply_g8_scale()

    def _on_g8_scale_manual_changed(self, val):
        self._analysis_g8_manual_halfrange = val
        self._apply_g8_scale()

    def _apply_g8_scale(self):
        self._lock_group_yaxis(self.analysis_g8_plots, self._analysis_g8_scale_auto,
                                self._analysis_g8_manual_halfrange)

    # -- 9-grid: one panel per cell -- that cell's own per-band profile -----

    def _build_analysis_grid9_group(self):
        box = QGroupBox('Sample Delay Band Profiles (9-grid)')
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(2)
        v.addLayout(self._build_analysis_g9_ctrl_row())
        v.addWidget(self._build_analysis_grid9())
        return box

    def _build_analysis_g9_ctrl_row(self):
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel('Normalize:'))
        self.cb_g9_norm_auto = QCheckBox('Auto (− group mean)')
        self.cb_g9_norm_auto.setChecked(True)
        self.cb_g9_norm_auto.toggled.connect(self._on_g9_norm_auto_toggled)
        ctrl.addWidget(self.cb_g9_norm_auto)
        ctrl.addWidget(QLabel('Manual ref (mV):'))
        self.sp_g9_norm_manual = QDoubleSpinBox()
        self.sp_g9_norm_manual.setRange(-100_000, 100_000)
        self.sp_g9_norm_manual.setDecimals(3)
        self.sp_g9_norm_manual.setValue(self._analysis_g9_manual_ref)
        self.sp_g9_norm_manual.setEnabled(False)
        self.sp_g9_norm_manual.valueChanged.connect(self._on_g9_norm_manual_changed)
        ctrl.addWidget(self.sp_g9_norm_manual)

        ctrl.addWidget(QLabel('Scale:'))
        self.cb_g9_scale_auto = QCheckBox('Auto')
        self.cb_g9_scale_auto.setChecked(True)
        self.cb_g9_scale_auto.toggled.connect(self._on_g9_scale_auto_toggled)
        ctrl.addWidget(self.cb_g9_scale_auto)
        ctrl.addWidget(QLabel('± range:'))
        self.sp_g9_scale_manual = QDoubleSpinBox()
        self.sp_g9_scale_manual.setRange(0.01, 1000)
        self.sp_g9_scale_manual.setDecimals(3)
        self.sp_g9_scale_manual.setValue(self._analysis_g9_manual_halfrange)
        self.sp_g9_scale_manual.setEnabled(False)
        self.sp_g9_scale_manual.valueChanged.connect(self._on_g9_scale_manual_changed)
        ctrl.addWidget(self.sp_g9_scale_manual)
        ctrl.addStretch(1)
        return ctrl

    def _build_analysis_grid9(self):
        self.analysis_g9_glw = pg.GraphicsLayoutWidget()
        self._rebuild_analysis_grid9()
        return self.analysis_g9_glw

    def _rebuild_analysis_grid9(self):
        """Rebuilds panel count/order to match the current profile's n_cells
        (called from _apply_profile() on every profile change). Y axis is
        linked across all panels (locked to panel 0). Panel titles are each
        cell's delay_us range across all bands, same format as the heatmap's
        threshold sub-label -- not threshold_v (that's grid8's job now)."""
        self.analysis_g9_glw.clear()
        self.analysis_g9_plots = []
        self.analysis_g9_curves = []
        self.analysis_g9_template_curves = []
        for j in range(self._n_cells):
            lo, hi = self._cell_delay_range_us[j]
            title = '{0:.2f}-{1:.2f}µs'.format(lo, hi)
            plot = self.analysis_g9_glw.addPlot(row=0, col=j)
            plot.setLogMode(x=True, y=False)
            self._style_compact(plot, title=title)
            if j > 0:
                plot.hideAxis('left')
            plot.addLine(y=0.0, pen=pg.mkPen((150, 150, 150), width=1))
            curve = plot.plot([], [], pen=pg.mkPen('b', width=2), symbol='o', symbolSize=4)
            self.analysis_g9_plots.append(plot)
            self.analysis_g9_curves.append(curve)
            self.analysis_g9_template_curves.append({})
        self._rebuild_analysis_grid9_ticks()

    def _rebuild_analysis_grid9_ticks(self):
        ticks = [(math.log10(p), '{0:.3g}'.format(p)) for p in self._pulse_us_sorted]
        lo, hi = math.log10(min(self._pulse_us_sorted)), math.log10(max(self._pulse_us_sorted))
        for plot in self.analysis_g9_plots:
            plot.getAxis('bottom').setTicks([ticks, []])
            plot.setXRange(lo, hi, padding=0.1)

    def _on_g9_norm_auto_toggled(self, checked):
        self._analysis_g9_norm_auto = checked
        self.sp_g9_norm_manual.setEnabled(not checked)

    def _on_g9_norm_manual_changed(self, val):
        self._analysis_g9_manual_ref = val

    def _on_g9_scale_auto_toggled(self, checked):
        self._analysis_g9_scale_auto = checked
        self.sp_g9_scale_manual.setEnabled(not checked)
        self._apply_g9_scale()

    def _on_g9_scale_manual_changed(self, val):
        self._analysis_g9_manual_halfrange = val
        self._apply_g9_scale()

    def _apply_g9_scale(self):
        self._lock_group_yaxis(self.analysis_g9_plots, self._analysis_g9_scale_auto,
                                self._analysis_g9_manual_halfrange)

    @staticmethod
    def _lock_group_yaxis(plots, scale_auto, manual_halfrange):
        """'Y axis locked to the first chart in that series': panel 0 sets
        the range (auto-fit to its own data, or the manual ± range) and
        every sibling panel is explicitly set to that exact same range --
        NOT pyqtgraph's setYLink, which aligns ranges by on-screen pixel
        geometry rather than copying identical numeric bounds, and gave
        visibly different ranges for panels of the same size in testing."""
        if not plots:
            return
        master = plots[0]
        if scale_auto:
            master.enableAutoRange(axis=pg.ViewBox.YAxis)
            y_range = master.viewRange()[1]
        else:
            master.disableAutoRange(axis=pg.ViewBox.YAxis)
            y_range = (-manual_halfrange, manual_halfrange)
            master.setYRange(*y_range, padding=0)
        for plot in plots[1:]:
            plot.disableAutoRange(axis=pg.ViewBox.YAxis)
            plot.setYRange(*y_range, padding=0)

    # -- Strip: overall average delta vs time, one chart ---------------------

    def _build_analysis_strips_group(self):
        box = QGroupBox('Band Mean vs Time (average)')
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(2)
        self._build_analysis_strip_ctrl_row(v)

        self.analysis_strip_glw = pg.GraphicsLayoutWidget()
        self.analysis_strip_plot = self.analysis_strip_glw.addPlot()
        self._style_compact(self.analysis_strip_plot)
        self.analysis_strip_plot.setLabel('bottom', 'time (s)', **{'font-size': '7pt'})
        self.analysis_strip_refline = self.analysis_strip_plot.addLine(
            y=0.0, pen=pg.mkPen((150, 150, 150), width=1))
        self.analysis_strip_curve = self.analysis_strip_plot.plot([], [], pen=pg.mkPen('b', width=1))
        self.analysis_strip_template_lines = {}
        v.addWidget(self.analysis_strip_glw)
        return box

    def _build_analysis_strip_ctrl_row(self, v):
        row_a = QHBoxLayout()
        row_a.addWidget(QLabel('Normalize:'))
        self.cb_strip_norm_auto = QCheckBox('Auto (− group mean)')
        self.cb_strip_norm_auto.setChecked(True)
        self.cb_strip_norm_auto.toggled.connect(self._on_strip_norm_auto_toggled)
        row_a.addWidget(self.cb_strip_norm_auto)
        row_a.addWidget(QLabel('Manual ref (mV):'))
        self.sp_strip_norm_manual = QDoubleSpinBox()
        self.sp_strip_norm_manual.setRange(-100_000, 100_000)
        self.sp_strip_norm_manual.setDecimals(3)
        self.sp_strip_norm_manual.setValue(self._analysis_strip_manual_ref)
        self.sp_strip_norm_manual.setEnabled(False)
        self.sp_strip_norm_manual.valueChanged.connect(self._on_strip_norm_manual_changed)
        row_a.addWidget(self.sp_strip_norm_manual)
        row_a.addStretch(1)
        v.addLayout(row_a)

        row_b = QHBoxLayout()
        row_b.addWidget(QLabel('Scale:'))
        self.cb_strip_scale_auto = QCheckBox('Auto')
        self.cb_strip_scale_auto.setChecked(True)
        self.cb_strip_scale_auto.toggled.connect(self._on_strip_scale_auto_toggled)
        row_b.addWidget(self.cb_strip_scale_auto)
        row_b.addWidget(QLabel('± range:'))
        self.sp_strip_scale_manual = QDoubleSpinBox()
        self.sp_strip_scale_manual.setRange(0.01, 1000)
        self.sp_strip_scale_manual.setDecimals(3)
        self.sp_strip_scale_manual.setValue(self._analysis_strip_manual_halfrange)
        self.sp_strip_scale_manual.setEnabled(False)
        self.sp_strip_scale_manual.valueChanged.connect(self._on_strip_scale_manual_changed)
        row_b.addWidget(self.sp_strip_scale_manual)

        pb_reset = QPushButton('Reset time')
        pb_reset.clicked.connect(self._on_analysis_strip_reset)
        row_b.addWidget(pb_reset)
        row_b.addStretch(1)
        v.addLayout(row_b)

    def _on_analysis_strip_reset(self):
        self._analysis_strip_reset_ts = time.time()

    def _on_strip_norm_auto_toggled(self, checked):
        self._analysis_strip_norm_auto = checked
        self.sp_strip_norm_manual.setEnabled(not checked)

    def _on_strip_norm_manual_changed(self, val):
        self._analysis_strip_manual_ref = val

    def _on_strip_scale_auto_toggled(self, checked):
        self._analysis_strip_scale_auto = checked
        self.sp_strip_scale_manual.setEnabled(not checked)
        self._apply_strip_scale()

    def _on_strip_scale_manual_changed(self, val):
        self._analysis_strip_manual_halfrange = val
        self._apply_strip_scale()

    def _apply_strip_scale(self):
        if self._analysis_strip_scale_auto:
            self.analysis_strip_plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        else:
            self.analysis_strip_plot.disableAutoRange(axis=pg.ViewBox.YAxis)
            half = self._analysis_strip_manual_halfrange
            self.analysis_strip_plot.setYRange(-half, half, padding=0)

    # -- Shared live computation ---------------------------------------------

    def _compute_analysis_matrix(self):
        """(n_bands, n_cells) delta_mV matrix in raw profile-channel order
        (band_index*n_cells+cell_index -- NOT display order), averaged over
        the last 'Avg N frames' raw frames and baseline-corrected via the
        same shared baseline as the Heatmap tab. None if no data/baseline."""
        if not self._rolling_buf:
            return None
        n = max(1, self._analysis_avg_n)
        recent = list(self._rolling_buf)[-n:]
        raw = np.mean([arr for _, arr in recent], axis=0)
        mean, _ = self._get_current_baseline()
        if mean is None:
            return None
        raw_nxn = raw.reshape(self._n_bands, self._n_cells)
        return (raw_nxn - mean) / 1000.0

    @staticmethod
    def _normalize_group(values, auto, manual_ref):
        """Auto: subtract this curve's own mean. Manual: subtract one shared,
        user-entered reference value instead -- freezes the comparison scale
        rather than letting it shift every redraw as the live mean drifts.
        Mean rather than first-element: a single noisy reference point (e.g.
        one high-variance cell) used to get imposed at full strength on
        every other point in the group; the mean dilutes one outlier's
        contribution by ~1/group-size instead."""
        values = np.asarray(values, dtype=float)
        ref = values.mean() if auto else manual_ref
        return values - ref

    def _update_analysis_heatmap(self):
        """Chart 1's own matrix/levels, decoupled from the main Heatmap tab
        except when its Normalize combo is left on 'Auto' -- then it uses
        whatever display mode is selected there. Runs every redraw tick
        (cheap, same array sizes as the main heatmap) regardless of which
        tab is visible, so switching tabs shows current data instantly."""
        if self._latest_raw is None:
            return
        mode = self._analysis_hm_mode()
        mean, std = self._get_current_baseline()
        raw_nxn = self._latest_raw.reshape(self._n_bands, self._n_cells)[self._band_display_order]
        if mean is not None:
            mean = mean[self._band_display_order]
            if std is not None:
                std = std[self._band_display_order]
        matrix = self._compute_display_matrix(raw_nxn, mean, std, mode=mode)

        cmap = self.cm_seq if mode in ('raw', 'stddev') else self.cm_div
        self.analysis_img.setColorMap(cmap)
        self.analysis_colorbar.setColorMap(cmap)

        if self._analysis_hm_scale_auto:
            if mode in ('raw', 'stddev'):
                levels = (0.0, float(matrix.max()) * 1.05 + 1.0)
            else:
                lim = float(np.max(np.abs(matrix)))
                if lim < 1.0:
                    lim = 1.0
                levels = (-lim, lim)
            self.analysis_img.setImage(matrix.T, levels=levels)
            # ImageItem has no sigLevelsChanged in this pyqtgraph version, so
            # the bar won't pick up a programmatic level change on its own --
            # push it explicitly (update_items=False: don't bounce back into
            # the image we just set).
            self.analysis_colorbar.setLevels(levels, update_items=False)
        else:
            # Manual: the colorbar (dragged, or set via the range spinbox) is
            # the single source of truth for levels -- leave them alone here,
            # just repaint with whatever's already set, or a drag would get
            # overwritten on the very next tick.
            self.analysis_img.setImage(matrix.T, autoLevels=False)

    def _update_analysis_charts(self):
        matrix = self._compute_analysis_matrix()
        if hasattr(self, 'lbl_analysis_baseline_info'):
            self.lbl_analysis_baseline_info.setText(self.lbl_baseline_info.text())
        if matrix is None:
            return
        sorted_matrix = matrix[self._pulse_sort_order]   # rows now pulse_us ascending

        bandmeans = sorted_matrix.mean(axis=1)
        y2 = self._normalize_group(bandmeans, self._analysis_c2_norm_auto, self._analysis_c2_manual_ref)
        self.analysis_c2_curve.setData(self._pulse_us_sorted, y2)

        for i in range(self._n_bands):
            y = self._normalize_group(sorted_matrix[i, :], self._analysis_g8_norm_auto,
                                       self._analysis_g8_manual_ref)
            self.analysis_g8_curves[i].setData(np.arange(self._n_cells) + 0.5, y)

        for j in range(self._n_cells):
            y = self._normalize_group(sorted_matrix[:, j], self._analysis_g9_norm_auto,
                                       self._analysis_g9_manual_ref)
            self.analysis_g9_curves[j].setData(self._pulse_us_sorted, y)

        # "Y axis locked to the first chart" -- re-synced every tick since,
        # in Auto scale mode, panel 0's auto-fit range moves with live data.
        self._apply_g8_scale()
        self._apply_g9_scale()

    def _update_analysis_strips(self):
        """One chart: the whole matrix's average delta_mV (all bands, all
        cells) vs time -- derived from self._rolling_buf on the fly rather
        than a dedicated buffer; Reset just moves the cutoff timestamp
        forward."""
        mean, _ = self._get_current_baseline()
        if mean is None or not self._rolling_buf:
            return
        ts_all  = np.fromiter((ts for ts, _ in self._rolling_buf), dtype=float)
        mask = ts_all >= self._analysis_strip_reset_ts
        if not mask.any():
            self.analysis_strip_curve.setData([], [])
            return
        raw_all = np.array([arr for ts, arr in self._rolling_buf if ts >= self._analysis_strip_reset_ts],
                           dtype=float)
        t_sel = ts_all[mask]
        y = (raw_all.mean(axis=1) - mean.mean()) / 1000.0
        y = self._normalize_group(y, self._analysis_strip_norm_auto, self._analysis_strip_manual_ref)
        self.analysis_strip_curve.setData(t_sel - t_sel[0], y)

    # -- Controls handlers ----------------------------------------------------

    def _on_analysis_avg_n_changed(self, val):
        self._analysis_avg_n = val

    # -- Corpus signature overlay (excludes chart 1) -------------------------

    def _on_load_signatures_clicked(self):
        # DontUseNativeDialog: the native GTK/portal file dialog renders as a
        # completely blank window in this environment -- Qt's own dialog
        # widget works reliably instead.
        path, _ = QFileDialog.getOpenFileName(
            self, 'Load signature corpus', '', 'CSV files (*.csv)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return
        try:
            sigs = pimd_corpus_check.load_corpus(path)
        except (SystemExit, Exception) as e:
            self.statusBar().showMessage('Load failed: {0}'.format(e))
            return
        self._merge_template_list(sigs, source='loaded')
        self.statusBar().showMessage('Loaded {0} signature(s) from {1}'.format(len(sigs), path))

    def _merge_template_list(self, sigs, source):
        """Replace only the entries tagged `source` ('loaded' = read-only
        reference corpus, 'editable' = the active editable file), leaving
        entries from the other source untouched -- a loaded reference corpus
        and an active editable file coexist in one list, both overlay-able.
        Preserves checked state across a reload of the same source (so
        Save/Delete don't drop an overlay you had checked)."""
        prev_checked = {
            item.data(Qt.ItemDataRole.UserRole): item.checkState()
            for i in range(self.lw_analysis_templates.count())
            for item in [self.lw_analysis_templates.item(i)]
            if self._analysis_templates.get(item.data(Qt.ItemDataRole.UserRole), {}).get('source') == source
        }
        self.lw_analysis_templates.blockSignals(True)
        for i in reversed(range(self.lw_analysis_templates.count())):
            item = self.lw_analysis_templates.item(i)
            if self._analysis_templates.get(item.data(Qt.ItemDataRole.UserRole), {}).get('source') == source:
                self.lw_analysis_templates.takeItem(i)
        self._analysis_templates = {k: v for k, v in self._analysis_templates.items() if v['source'] != source}

        keys_sorted = sorted(sigs.keys(), key=lambda k: tuple(str(v) for v in k))
        prefix = '✎ ' if source == 'editable' else ''
        for i, key in enumerate(keys_sorted):
            sig = sigs[key]
            amp, splithalf, quality = sig['amp'], sig['splithalf'], sig['quality']
            snr = amp / splithalf if splithalf > 1e-9 else float('inf')
            if len(key) == 3:
                # 'loaded'/legacy source (pimd_corpus_check.load_corpus(),
                # still old target/distance_cm schema -- see its own
                # changelog entry for the v1.32-schema loud-rejection).
                session, display_target, display_place = key[0], key[1], '{0}cm'.format(key[2])
            else:
                # 'editable' source (this file's own _scan_editable_
                # signature_file(), v1.32+ schema) -- key is (session,
                # capture_id); display fields live in the value dict.
                session, capture_id = key
                display_target = sig.get('target_id') or capture_id
                display_place = '{0}mm'.format(sig['distance_mm']) if sig.get('distance_mm') else 'air'
            label = '{0}{1} @{2}  amp={3:.0f} SNR={4:.1f} [{5}]'.format(
                prefix, display_target, display_place, amp, snr, quality)
            color = pg.intColor(i, hues=max(len(sigs), 9))
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(prev_checked.get(key, Qt.CheckState.Unchecked))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setForeground(QBrush(color))
            item.setToolTip('{0} @{1} ({2})  amp={3:.3f}mV  splithalf={4:.3f}mV  SNR={5:.2f}  quality={6}'.format(
                display_target, display_place, session, amp, splithalf, snr, quality))
            self.lw_analysis_templates.addItem(item)
            self._analysis_templates[key] = {'shape': sig['shape'], 'color': color, 'label': label,
                                              'amp': amp, 'splithalf': splithalf, 'quality': quality,
                                              'source': source, 'session': session}
        self.lw_analysis_templates.blockSignals(False)
        self._refresh_analysis_overlays()

    def _on_clear_signatures_clicked(self):
        self.lw_analysis_templates.blockSignals(True)
        for i in range(self.lw_analysis_templates.count()):
            self.lw_analysis_templates.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.lw_analysis_templates.blockSignals(False)
        self._refresh_analysis_overlays()

    def _on_analysis_template_item_changed(self, _item):
        self._refresh_analysis_overlays()

    def _checked_template_keys(self):
        keys = []
        for i in range(self.lw_analysis_templates.count()):
            item = self.lw_analysis_templates.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                keys.append(item.data(Qt.ItemDataRole.UserRole))
        return keys

    def _refresh_analysis_overlays(self):
        """Rebuild every overlay curve/line from scratch against the current
        checked-template set. Templates are static (one capture, not live),
        so this only needs to run on load/(un)check/normalize-toggle -- not
        every redraw tick."""
        for curve in self.analysis_c2_template_curves.values():
            self.analysis_c2_plot.removeItem(curve)
        self.analysis_c2_template_curves = {}
        for i, plot in enumerate(self.analysis_g8_plots):
            for curve in self.analysis_g8_template_curves[i].values():
                plot.removeItem(curve)
            self.analysis_g8_template_curves[i] = {}
        for j, plot in enumerate(self.analysis_g9_plots):
            for curve in self.analysis_g9_template_curves[j].values():
                plot.removeItem(curve)
            self.analysis_g9_template_curves[j] = {}
        for line in self.analysis_strip_template_lines.values():
            self.analysis_strip_plot.removeItem(line)
        self.analysis_strip_template_lines = {}

        for key in self._checked_template_keys():
            tpl = self._analysis_templates.get(key)
            if tpl is None:
                continue
            shape = tpl['shape']
            if len(shape) != self._n_channels:
                self.statusBar().showMessage(
                    "Skipping overlay '{0}': {1} channels vs live profile's {2} -- "
                    "refusing to mix profile geometries (DESIGN §11)".format(
                        tpl['label'], len(shape), self._n_channels))
                continue
            pen = pg.mkPen(tpl['color'], width=2, style=Qt.PenStyle.DashLine)
            # Already pulse_us-ascending / threshold_v-descending, per the
            # corpus's own row-sort convention (pimd_corpus_check.load_long) --
            # matches sorted_matrix's row order directly, no reindex needed.
            tmatrix = shape.reshape(self._n_bands, self._n_cells)

            y2 = self._normalize_group(tmatrix.mean(axis=1), self._analysis_c2_norm_auto,
                                        self._analysis_c2_manual_ref)
            self.analysis_c2_template_curves[key] = self.analysis_c2_plot.plot(
                self._pulse_us_sorted, y2, pen=pen)

            for i, plot in enumerate(self.analysis_g8_plots):
                y = self._normalize_group(tmatrix[i, :], self._analysis_g8_norm_auto,
                                           self._analysis_g8_manual_ref)
                self.analysis_g8_template_curves[i][key] = plot.plot(
                    np.arange(self._n_cells) + 0.5, y, pen=pen)

            for j, plot in enumerate(self.analysis_g9_plots):
                y = self._normalize_group(tmatrix[:, j], self._analysis_g9_norm_auto,
                                           self._analysis_g9_manual_ref)
                self.analysis_g9_template_curves[j][key] = plot.plot(
                    self._pulse_us_sorted, y, pen=pen)

            # Strip overlay: the template's raw overall average (no time
            # axis on a static capture, so this is a plain reference line,
            # not passed through the strip's time-based normalize control).
            val = float(tmatrix.mean())
            line = pg.InfiniteLine(pos=val, angle=0, pen=pen)
            self.analysis_strip_plot.addItem(line)
            self.analysis_strip_template_lines[key] = line

    # -- Signature capture (air-before / target / air-after) ----------------

    # -- Training state machine (v1.33) ---------------------------------
    # One continuous session alternates AIR/TARGET capture phases; each
    # committed air anchor closes the previous target (air_after) and opens
    # the next (air_before). Status ladder within a phase: 'settling'
    # (yellow) -> 'collecting' (green) -> 'ready' (blue; the deque keeps
    # rolling so Acquire commits the freshest N clean frames). Settle loss
    # mid-window clears the buffer back to 'settling' -- a disturbance
    # contaminates the whole window (same philosophy as the v1.31 gate).

    def _on_sig_train_start_toggled(self, checked):
        if not checked:
            # Stop: keep any unsaved stats/readout so Save still works.
            self._reset_sig_capture_state(preserve_stats=True)
            return
        refuse = None
        if self._editable_sig_path is None:
            refuse = 'Training: open a signature file first (New file… / Open for editing…)'
        elif self._training_current_row is not None:
            refuse = 'Training: a guided Training Session is running — stop it first'
        if refuse is not None:
            self.pb_sig_train_start.blockSignals(True)
            self.pb_sig_train_start.setChecked(False)
            self.pb_sig_train_start.blockSignals(False)
            self.statusBar().showMessage(refuse)
            return
        self._sig_air_before = None
        self._sig_air_after  = None
        self._sig_target     = None
        self._sig_last_stats = None
        self._update_sig_readout()
        self._analysis_training_active = True
        self._sig_train_phase = 'air'
        self.pb_sig_train_start.setText('Stop Training')
        self._sig_train_restart_buffer()
        self._update_sig_capture_gating()

    def _on_sig_train_acquire(self):
        """Commits the freshest N clean settled frames as the current phase's
        capture. Bound to the Acquire button and (via eventFilter) Space."""
        if not self._analysis_training_active:
            return
        if self._sig_train_status != 'ready':
            self.statusBar().showMessage(
                'Training: not ready — wait for the blue READY state')
            return
        buf = self._sig_train_buf
        ts_arr  = np.array([ts for ts, _ in buf], dtype=float)
        raw_arr = np.array([r for _, r in buf], dtype=float)
        entry = {'t_seconds': ts_arr, 'frames_mV': raw_arr / 1000.0, 'n_frames': len(ts_arr)}
        if self._sig_glitch_skipped > 0.2 * buf.maxlen:
            self.statusBar().showMessage(
                '⚠ training acquire ({0}): {1} glitch frame(s) excluded while '
                'filling the {2}-frame window — check for interference'.format(
                    self._sig_train_phase, self._sig_glitch_skipped, buf.maxlen))
        if self._sig_train_phase == 'air':
            if self._sig_target is not None:
                # This air closes the pending target: compute + display a
                # stats *snapshot*, then immediately shift the slots so the
                # same anchor opens the next target. Save reads only
                # _sig_last_stats + placement widgets, so shifting here (not
                # at save time) is race-free even if the operator acquires
                # the next target before pressing Save.
                self._sig_air_after = entry
                had_unsaved = self._sig_last_stats is not None
                stats = self._compute_sig_stats()
                self._sig_last_stats = stats
                self._set_sig_readout_from_stats(stats)
                self._sig_air_before = entry
                self._sig_target     = None
                self._sig_air_after  = None
                if had_unsaved:
                    self.statusBar().showMessage(
                        'Training: previous unsaved capture replaced')
            else:
                self._sig_air_before = entry
            self._sig_train_phase = 'target'
        else:
            self._sig_target = entry
            self._sig_train_phase = 'air'
        self._sig_train_restart_buffer()
        self._update_sig_capture_gating()

    def _sig_train_restart_buffer(self):
        """New capture window: fresh deque (picks up a changed Frames value),
        zeroed glitch counter, back to the settling gate."""
        self._sig_capture_n = self.sp_sig_capture_n.value()
        self._sig_train_buf = deque(maxlen=self._sig_capture_n)
        self._sig_glitch_skipped = 0
        self._sig_train_status = 'settling'
        self._update_sig_train_indicator()

    def _current_settle_mv(self):
        """Mean per-channel rolling std in mV over the Stats tab's window --
        the v1.31 settle-gate metric, unchanged. None if <2 frames buffered
        (treated as not settled)."""
        n_win  = self.sp_stats_window.value()
        recent = list(self._rolling_buf)[-n_win:]
        if len(recent) < 2:
            return None
        mat = np.array([arr for _, arr in recent], dtype=float)
        return float(mat.std(0).mean()) / 1000.0

    def _sig_train_ingest(self, now, raw, glitch_mask):
        """Per-frame training logic, called from process_packet."""
        settle_mv = self._current_settle_mv()
        settled = settle_mv is not None and settle_mv <= self.sp_sig_settle_mv.value()
        if not settled:
            if self._sig_train_status != 'settling':
                # Settle lost mid-window: the whole window is contaminated.
                self._sig_train_buf.clear()
                self._sig_glitch_skipped = 0
                self._sig_train_status = 'settling'
            self._update_sig_train_indicator(settle_mv)
            return
        if glitch_mask.any():
            # mirrors pimd_features.drop_flagged: glitch frames never enter
            # a capture window
            self._sig_glitch_skipped += 1
        else:
            self._sig_train_buf.append((now, raw.copy()))
        full = len(self._sig_train_buf) >= self._sig_train_buf.maxlen
        self._sig_train_status = 'ready' if full else 'collecting'
        self._update_sig_train_indicator(settle_mv)

    def _update_sig_train_indicator(self, settle_mv=None):
        """Renders the colored status label + phase instruction. Stylesheet
        is only touched on state change; text may update every frame."""
        if not self._analysis_training_active:
            self.lbl_sig_train_status.setText('Idle — press Start Training')
            self.lbl_sig_train_phase.setText('')
            style = ''
        elif self._sig_train_status == 'settling':
            self.lbl_sig_train_status.setText(
                'SETTLING' + ('' if settle_mv is None else ' {0:.3f} mV'.format(settle_mv)))
            style = self.MY_YELLOW
        elif self._sig_train_status == 'collecting':
            self.lbl_sig_train_status.setText('COLLECTING {0}/{1}'.format(
                len(self._sig_train_buf), self._sig_train_buf.maxlen))
            style = self.MY_GREEN
        else:
            self.lbl_sig_train_status.setText(
                'READY — Space to acquire ({0})'.format(self._sig_train_phase))
            style = self.MY_BLUE
        if style != self._sig_train_last_style:
            self.lbl_sig_train_status.setStyleSheet(style)
            self._sig_train_last_style = style
        if self._analysis_training_active:
            if self._sig_train_phase == 'target':
                instr = 'Place target now — edit metadata while it settles'
            elif self._sig_target is not None:
                instr = 'Remove target now — next air acquire closes the signature'
            else:
                instr = 'Keep coil clear — leading air capture'
            self.lbl_sig_train_phase.setText(instr)

    def _reset_sig_capture_state(self, preserve_stats=False):
        """Ends any training session and clears the capture slots. With
        preserve_stats, the last computed signature (readout + Save) survives
        a Stop so an unsaved capture can still be saved."""
        self._analysis_training_active = False
        self._sig_train_phase    = 'air'
        self._sig_train_status   = 'settling'
        self._sig_train_buf      = None
        self._sig_glitch_skipped = 0
        self._sig_air_before = None
        self._sig_air_after  = None
        self._sig_target     = None
        pb = getattr(self, 'pb_sig_train_start', None)
        if pb is not None:
            pb.blockSignals(True)
            pb.setChecked(False)
            pb.blockSignals(False)
            pb.setText('Start Training')
            self._update_sig_train_indicator()
        if not preserve_stats:
            self._sig_last_stats = None
            self._update_sig_readout()
        self._update_sig_capture_gating()

    def _compute_sig_stats(self):
        """Reuses pimd_features.py's own plateau/baseline/quality math
        verbatim, just fed a live 1-2 anchor window instead of a recorded
        session's air segments. None if not enough captures yet; a dict with
        'error' if the air anchor(s) and target capture have mismatched
        channel counts (e.g. a profile change mid-sequence)."""
        if self._sig_target is None or self._sig_air_before is None:
            return None
        anchor_ts, anchor_vs = [], []
        for entry in (self._sig_air_before, self._sig_air_after):
            if entry is None:
                continue
            # Throwaway plateau -- only start_idx/end_idx/is_air feed
            # central_frames() here; the target/placement fields are
            # meaningless for this live 1-2 anchor window.
            plateau = pimd_features.Plateau(
                target_id='air', short_name='', distance_mm=None, long_axis='na', face_normal='na',
                offset_x_mm=0, offset_y_mm=0, medium='air', repeat_idx=1, notes='',
                is_air=True, start_idx=0, end_idx=entry['n_frames'])
            c0, c1 = pimd_features.central_frames(plateau)
            anchor_ts.append(float(np.median(entry['t_seconds'][c0:c1])))
            anchor_vs.append(np.median(entry['frames_mV'][c0:c1], axis=0))
        order = np.argsort(anchor_ts)
        anchor_ts = np.array(anchor_ts)[order]
        anchor_vs = np.array(anchor_vs)[order]

        tgt = self._sig_target
        if anchor_vs.shape[1] != tgt['frames_mV'].shape[1]:
            return {'error': "channel-count mismatch vs air anchor(s) -- refusing to mix profile "
                              "geometries (DESIGN §11)"}
        plateau_t = pimd_features.Plateau(
            target_id='target', short_name='', distance_mm=None, long_axis='na', face_normal='na',
            offset_x_mm=0, offset_y_mm=0, medium='air', repeat_idx=1, notes='',
            is_air=False, start_idx=0, end_idx=tgt['n_frames'])
        c0, c1 = pimd_features.central_frames(plateau_t)
        delta_mV, plateau_amp_mV, amp_mean_abs_mV, splithalf_floor, n_central, center_t = \
            pimd_features.compute_plateau_stats(tgt['frames_mV'], tgt['t_seconds'], c0, c1, anchor_ts, anchor_vs)
        quality = pimd_features.quality_flags(splithalf_floor, plateau_amp_mV, n_central)
        return dict(delta_mV=delta_mV, plateau_amp_mV=plateau_amp_mV, amp_mean_abs_mV=amp_mean_abs_mV,
                    splithalf_floor=splithalf_floor, quality=quality, n_central=n_central,
                    used_air_after=self._sig_air_after is not None,
                    out_of_range=(center_t < anchor_ts[0] or center_t > anchor_ts[-1]))

    def _update_sig_readout(self):
        self._sig_last_stats = self._compute_sig_stats()
        self._set_sig_readout_from_stats(self._sig_last_stats)

    def _set_sig_readout_from_stats(self, stats):
        """Renders the readout label from a stats dict (or None). Split from
        _update_sig_readout so the training air-acquire can display a stats
        snapshot after the slots have already been shifted (v1.33)."""
        if stats is None:
            self.lbl_sig_readout.setText('Amp: —  Mean|Δ|: —  Splithalf: —  SNR: —  Quality: —')
            self.lbl_sig_readout.setStyleSheet('')
        elif 'error' in stats:
            self.lbl_sig_readout.setText('Error: {0}'.format(stats['error']))
            self.lbl_sig_readout.setStyleSheet(self.MY_RED)
        else:
            splithalf = stats['splithalf_floor']
            snr = stats['plateau_amp_mV'] / splithalf if splithalf > 1e-9 else float('inf')
            note = '' if stats['used_air_after'] else '  (single air anchor — flat baseline)'
            self.lbl_sig_readout.setText(
                'Amp(L2): {0:.3f}mV  Mean|Δ|: {1:.3f}mV  Splithalf: {2:.3f}mV  SNR: {3:.1f}  '
                'Quality: {4}{5}'.format(stats['plateau_amp_mV'], stats['amp_mean_abs_mV'], splithalf,
                                          snr, stats['quality'], note))
            self.lbl_sig_readout.setStyleSheet('' if stats['quality'] == 'ok' else self.MY_YELLOW)

    def _update_sig_capture_gating(self):
        if not hasattr(self, 'pb_sig_train_acquire'):
            return   # mid-build: the Training group runs this again once complete
        has_file = self._editable_sig_path is not None
        self.sig_target.setEnabled(has_file)
        self.sig_distance_mm.setEnabled(has_file)
        self.sig_long_axis.setEnabled(has_file)
        self.sig_face_normal.setEnabled(has_file)
        self.sig_offset_x_mm.setEnabled(has_file)
        self.sig_offset_y_mm.setEnabled(has_file)
        self.sig_medium.setEnabled(has_file)
        self.sig_repeat_idx.setEnabled(has_file)
        self.sig_notes.setEnabled(has_file)
        self.sp_sig_capture_n.setEnabled(has_file)
        self.sp_sig_settle_mv.setEnabled(has_file)
        self.pb_sig_train_start.setEnabled(has_file)
        self.pb_sig_train_acquire.setEnabled(self._analysis_training_active)
        stats = self._sig_last_stats
        self.pb_sig_save.setEnabled(
            has_file and stats is not None and 'error' not in stats
            and self.sig_target.currentData() is not None)
        item = self.lw_analysis_templates.currentItem()
        tpl = self._analysis_templates.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        self.pb_sig_delete.setEnabled(bool(tpl) and tpl['source'] == 'editable')

    # -- Signature file operations (New / Open for editing / Save / Delete) --

    def _on_sig_new_file_clicked(self):
        os.makedirs(CORPORA_DIR, exist_ok=True)
        default = os.path.join(CORPORA_DIR, 'gui_signatures_{0}.csv'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S')))
        path, _ = QFileDialog.getSaveFileName(
            self, 'New signature file', default, 'CSV files (*.csv)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', newline='') as f:
            csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator='\n').writerow(
                pimd_features.CORPUS_HEADER_FIELDS)
        self._editable_sig_path = path
        self._editable_sig_session_id = 'gui_{0}'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
        self._editable_sig_seq = 0
        self._editable_repeat_counts = {}
        self._reset_sig_capture_state()
        self._merge_template_list({}, source='editable')
        self._update_sig_mode_label()
        self.statusBar().showMessage('New signature file: {0}'.format(path))

    def _on_sig_open_for_edit_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open signature file for editing', '', 'CSV files (*.csv)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return
        try:
            fmt = pimd_corpus_check.sniff_format(path)
        except SystemExit as e:
            self.statusBar().showMessage('Open failed: {0}'.format(e))
            return
        if fmt != 'long':
            self.statusBar().showMessage(
                'GUI editing only supports long-format corpus files -- use "Load signatures…" '
                'to browse this wide-format file read-only.')
            return
        sigs = self._scan_editable_signature_file(path)
        if sigs and QMessageBox.question(
                self, 'Open for editing',
                "'{0}' already has {1} signature(s). Add/Delete will modify this file directly. "
                "Continue?".format(os.path.basename(path), len(sigs)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        self._editable_sig_path = path
        self._editable_sig_session_id = 'gui_{0}'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
        self._reset_sig_capture_state()
        self._reload_editable_signature_list()
        self._update_sig_mode_label()
        self.statusBar().showMessage('Editing: {0} ({1} signature(s))'.format(path, len(sigs)))

    def _scan_editable_signature_file(self, path):
        """Groups a v1.32+ gui_signatures_*.csv's per-cell rows back into one
        entry per capture, keyed by (session, capture_id) -- the new schema's
        natural unique key (columns 0, 1), replacing the old
        (session, target, distance) key. Uses csv.reader (not a hand split)
        since notes/short_name can carry quoted commas."""
        fields = pimd_features.CORPUS_HEADER_FIELDS
        idx = {name: i for i, name in enumerate(fields)}
        groups, order = {}, []
        with open(path, newline='') as f:
            reader = csv.reader(line for line in f if not line.startswith('#'))
            header = next(reader, None)   # CORPUS_HEADER row
            for parts in reader:
                if not parts:
                    continue
                key = (parts[idx['session']], parts[idx['capture_id']])
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(parts)
        sigs = {}
        for key in order:
            rows = sorted(groups[key], key=lambda p: (float(p[idx['pulse_us']]), -float(p[idx['threshold_v']])))
            first = rows[0]
            sigs[key] = dict(
                shape=np.array([float(p[idx['delta_mV']]) for p in rows]),
                amp=float(first[idx['plateau_amp_mV']]), splithalf=float(first[idx['splithalf_floor']]),
                quality=first[idx['quality']],
                target_id=first[idx['target_id']], short_name=first[idx['short_name']],
                distance_mm=first[idx['distance_mm']], long_axis=first[idx['long_axis']],
                face_normal=first[idx['face_normal']], offset_x_mm=first[idx['offset_x_mm']],
                offset_y_mm=first[idx['offset_y_mm']], medium=first[idx['medium']],
                repeat_idx=first[idx['repeat_idx']],
            )
        return sigs

    @staticmethod
    def _placement_tuple_key(sig):
        """The brief's repeat-disambiguation tuple: (target_id, distance_mm,
        long_axis, face_normal, offset_x_mm, offset_y_mm, medium) --
        identifies "the same placement", which is what repeat_idx
        auto-increments against. Accepts either a _scan_editable_signature_
        file() value dict (string fields, from CSV) or a
        _placement_from_widgets() dict (int/str fields, from live widgets) --
        stringified so both sides compare equal."""
        return tuple(str(sig[k]) for k in ('target_id', 'distance_mm', 'long_axis',
                                            'face_normal', 'offset_x_mm', 'offset_y_mm', 'medium'))

    def _reload_editable_signature_list(self):
        if self._editable_sig_path is None:
            return
        sigs = self._scan_editable_signature_file(self._editable_sig_path)
        self._merge_template_list(sigs, source='editable')
        self._editable_repeat_counts = {}
        for sig in sigs.values():
            key = self._placement_tuple_key(sig)
            self._editable_repeat_counts[key] = self._editable_repeat_counts.get(key, 0) + 1
        self._editable_sig_seq = len(sigs)

    def _update_sig_mode_label(self):
        if self._editable_sig_path is None:
            self.lbl_sig_mode.setText('Mode: read-only')
            self.lbl_sig_mode.setStyleSheet('')
        else:
            self.lbl_sig_mode.setText('Mode: EDITING — {0}'.format(os.path.basename(self._editable_sig_path)))
            self.lbl_sig_mode.setStyleSheet(self.MY_YELLOW)

    def _build_colmap_for_corpus(self):
        colmap = []
        for b in self._profile['bands']:
            thr = b.get('threshold_v') if self._has_threshold_v else None
            for j in range(self._n_cells):
                colmap.append({'pulse_us': b['pulse_us'], 'threshold_v': thr[j] if thr else float('nan')})
        return colmap

    def _on_sig_save_clicked(self):
        stats = self._sig_last_stats
        if stats is None or 'error' in stats:
            self.statusBar().showMessage(
                stats['error'] if stats else 'Capture Air (before) and Capture Target first.')
            return
        if self._editable_sig_path is None:
            self.statusBar().showMessage('No editable signature file open.')
            return

        target_id = self.sig_target.currentData()
        if not target_id:
            self.statusBar().showMessage('Select a target before saving.')
            return
        if target_id != 'air' and target_id not in self._targets:
            self.statusBar().showMessage(
                "Target '{0}' is no longer in the registry (removed/renamed since it was "
                "selected) -- reload targets and pick again.".format(target_id))
            return
        short_name = self._targets[target_id].short_name if target_id in self._targets else ''

        existing = self._scan_editable_signature_file(self._editable_sig_path)
        if existing:
            existing_len = len(next(iter(existing.values()))['shape'])
            if existing_len != self._n_channels:
                self.statusBar().showMessage(
                    "Refusing to save: file has {0}-channel signatures, live profile has {1} channels "
                    "-- never mix profile geometries (DESIGN §11)".format(existing_len, self._n_channels))
                return

        placement = self._placement_from_widgets('sig')
        distance_mm = None if target_id == 'air' else placement['distance_mm']

        colmap = self._build_colmap_for_corpus()
        plateau = pimd_features.Plateau(
            target_id=target_id, short_name=short_name, distance_mm=distance_mm,
            long_axis=placement['long_axis'], face_normal=placement['face_normal'],
            offset_x_mm=placement['offset_x_mm'], offset_y_mm=placement['offset_y_mm'],
            medium=placement['medium'], repeat_idx=placement['repeat_idx'], notes=placement['notes'],
            is_air=(target_id == 'air'), start_idx=0, end_idx=0)

        self._editable_sig_seq += 1
        capture_id = '{0}_c{1:02d}'.format(self._editable_sig_session_id, self._editable_sig_seq)
        captured_at = datetime.now().isoformat()

        rows = pimd_features.build_rows(
            self._editable_sig_session_id, capture_id, captured_at, plateau, colmap,
            stats['delta_mV'], stats['plateau_amp_mV'], stats['splithalf_floor'],
            stats['quality'], stats['amp_mean_abs_mV'], self._profile.get('name'), self._profile_sha8,
            self._parsed_fw_version(), 'pimd_classviz.py v{0}'.format(APP_VERSION),
            self.cb_supply.currentText(), self._editable_sig_path)
        with open(self._editable_sig_path, 'a', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for row in rows:
                writer.writerow([row[k] for k in pimd_features.CORPUS_HEADER_FIELDS])
        self._reload_editable_signature_list()
        if self._analysis_training_active:
            # Keep the training session running: the slots were already
            # shifted at air-acquire, so recomputing correctly yields dashes
            # (and Save disabled) until the next signature completes.
            self._update_sig_readout()
            self._update_sig_capture_gating()
        else:
            self._reset_sig_capture_state()
        self.statusBar().showMessage(
            "Saved '{0}' ({1} rows) to {2}".format(capture_id, len(rows), self._editable_sig_path))

    def _on_sig_delete_clicked(self):
        item = self.lw_analysis_templates.currentItem()
        key = item.data(Qt.ItemDataRole.UserRole) if item else None
        tpl = self._analysis_templates.get(key) if key else None
        if tpl is None or tpl['source'] != 'editable' or self._editable_sig_path is None:
            self.statusBar().showMessage('Only signatures in the active editable file can be deleted.')
            return
        if QMessageBox.question(
                self, 'Delete signature', "Delete '{0}' from {1}? This cannot be undone.".format(
                    item.text(), self._editable_sig_path),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        with open(self._editable_sig_path) as f:
            lines = [l.rstrip('\n') for l in f]
        preamble   = [l for l in lines if l.startswith('#')]
        body       = [l for l in lines if l and not l.startswith('#')]
        header, data_lines = body[0], body[1:]
        # key is (session, capture_id) -- neither field can contain a comma
        # (both are generated strings), so a plain split is safe here even
        # though later fields (notes/short_name) may be csv-quoted.
        kept = [l for l in data_lines if tuple(l.split(',')[:2]) != key]
        with open(self._editable_sig_path, 'w') as f:
            for l in preamble:
                f.write(l + '\n')
            f.write(header + '\n')
            for l in kept:
                f.write(l + '\n')
        self._reload_editable_signature_list()
        self.statusBar().showMessage("Deleted '{0}' from {1}".format(item.text(), self._editable_sig_path))

    # -- Session recording (alternate path -- same file format as the ----
    # -- Training Session tab, reuses its machinery verbatim) -------------

    def _on_sig_session_start(self):
        if not self.serial.isOpen() or self.pb_start.text() != 'Running':
            self.statusBar().showMessage('Connect and start streaming before recording a session.')
            return
        if self._recording:
            self.statusBar().showMessage('A session is already recording — stop it first.')
            return
        self._session_start()   # notes=None -> interactive prompt, same as the plain Stats-tab flow
        self.pb_record.blockSignals(True)
        self.pb_record.setChecked(True)
        self.pb_record.blockSignals(False)
        self._analysis_session_recording = True
        self._set_sig_session_active_ui(True)
        self._update_sig_session_status_label()

    def _on_sig_session_pause_toggled(self, checked):
        # Shared with the Training Session tab's own pause -- process_packet's
        # frame-write gate checks this same flag regardless of which tab set it.
        self._training_paused = checked
        self.pb_sig_session_pause.setText('Resume' if checked else 'Pause')
        self.pb_sig_session_pause.setStyleSheet(self.MY_YELLOW if checked else '')
        self._update_sig_session_status_label()

    def _on_sig_session_stop(self):
        if not self._analysis_session_recording:
            return
        self.pb_record.setChecked(False)   # -> _session_stop() -> centralized reset

    def _on_sig_session_mark(self):
        if not self._recording:
            self.statusBar().showMessage('Start recording before marking.')
            return
        if self._training_paused:
            self.statusBar().showMessage('Paused — resume before marking.')
            return
        target_id = self.sig_target.currentData()
        if not target_id:
            self.statusBar().showMessage('Select a target before marking.')
            return
        if target_id != 'air' and target_id not in self._targets:
            self.statusBar().showMessage(
                "Target '{0}' is no longer in the registry -- reload targets and pick "
                'again.'.format(target_id))
            return
        placement = self._placement_from_widgets('sig')
        if target_id == 'air':
            placement['distance_mm'] = None
            text = 'air'
        else:
            text = '{0} @{1}'.format(target_id, pimd_features.format_distance(placement['distance_mm']))
        self._append_mark(text)
        self._append_mark_target(target_id, placement)
        self.statusBar().showMessage('Marked: {0}'.format(text))

    def _set_sig_session_active_ui(self, active):
        self.pb_sig_session_start.setEnabled(not active)
        self.pb_sig_session_pause.setEnabled(active)
        self.pb_sig_session_stop.setEnabled(active)
        self.pb_sig_session_mark.setEnabled(active)
        if not active:
            self.pb_sig_session_pause.blockSignals(True)
            self.pb_sig_session_pause.setChecked(False)
            self.pb_sig_session_pause.setText('Pause')
            self.pb_sig_session_pause.setStyleSheet('')
            self.pb_sig_session_pause.blockSignals(False)

    def _update_sig_session_status_label(self):
        if not self._analysis_session_recording:
            self.lbl_sig_session_status.setText('Not recording')
        else:
            self.lbl_sig_session_status.setText(
                'Recording{0}'.format(' (paused)' if self._training_paused else ''))

    # ------------------------------------------------------------------
    # Serial
    # ------------------------------------------------------------------
    def serial_open(self, flag):
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
            return self.serial.open(QIODevice.OpenModeFlag.ReadWrite)
        else:
            self.serial.close()
            return True

    def connect_port(self):
        if self.pb_connect.text() != 'Connected':
            if self.serial_open(True):
                self.pb_connect.setText('Connected')
                self.pb_connect.setStyleSheet(self.MY_GREEN)
                self.send_command('E')
                self.send_command('V')
                self.send_command('Q{0}'.format(DEFAULT_PROFILE_IDX))
                self._apply_profile(_default_profile(), DEFAULT_PROFILE_IDX)
                self.statusBar().showMessage('Connected — Q4 sent')
            else:
                self.pb_connect.setText('Port Error')
                self.pb_connect.setStyleSheet(self.MY_RED)
                self.statusBar().showMessage('Could not open port')
        else:
            self.start_stop(force_stop=True)
            self.serial_open(False)
            self.pb_connect.setText('Not Connected')
            self.pb_connect.setStyleSheet(self.MY_YELLOW)
            self.statusBar().showMessage('Disconnected')

    def read_from_serial(self):
        # Count lines drained in this single readyRead callback -- a batch of
        # more than a couple means GUI processing fell behind the incoming
        # stream between events and lines queued up in Qt's serial buffer.
        # _update_rate() surfaces the worst batch seen each second.
        n = 0
        while self.serial.canReadLine():
            raw = self.serial.readLine().data().decode('utf-8', errors='replace').rstrip()
            if raw:
                self.process_packet(raw)
            n += 1
        if n > self._serial_max_batch:
            self._serial_max_batch = n

    def send_command(self, text):
        self.serial.write((text + '\n').encode())
        self._last_cmd = text

    # ------------------------------------------------------------------
    # Start / stop
    # ------------------------------------------------------------------
    def start_stop(self, force_stop=False):
        if force_stop or self.pb_start.text() == 'Running':
            self.send_command('E')
            self.pb_start.setText('Stopped')
            self.pb_start.setStyleSheet(self.MY_YELLOW)
            if self._recording:
                self.pb_record.setChecked(False)   # auto-save recorded frames
        else:
            if not self.serial.isOpen():
                return
            self.send_command('G')
            self.pb_start.setText('Running')
            self.pb_start.setStyleSheet(self.MY_GREEN)

    # ------------------------------------------------------------------
    # Packet handling
    # ------------------------------------------------------------------
    def process_packet(self, line):
        self._last_packet = line

        # Normalise separator — firmware uses ',' but tolerate ', '
        line = line.replace(', ', ',')

        if not line:
            return

        if line[0] == 'V':
            self._fw_version_line = line
            return

        # Mode 2 sweep: W<idx>,<time_ms>,<ch0>,...,<chN-1> — idx must match the
        # profile we last selected (DEFAULT_PROFILE_IDX or DYNAMIC_PROFILE_INDEX).
        if len(line) < 2 or line[0] != 'W' or not line[1].isdigit():
            return

        parts = line.split(',')
        try:
            w_idx = int(parts[0][1:])
            if w_idx != self._active_profile_idx:
                return
            if len(parts) != 2 + self._n_channels:
                return
            fw_time_ms = int(parts[1])
            raw = np.array([int(parts[2 + i]) for i in range(self._n_channels)], dtype=float)
        except (ValueError, IndexError) as e:
            self.statusBar().showMessage('W parse error: {0}'.format(e))
            return

        now = time.time()

        # Glitch filter for display only: 64-frame circular median, 100 mV threshold.
        # Catches ADC bit-truncation artifacts (440–880 mV shifts) without suppressing
        # real signals (e.g. ±7 mV environmental pickup). _rolling_buf and _record_buf
        # receive unfiltered raw so frame recordings stay faithful.
        if self._ch_glitch_buf is None:
            self._ch_glitch_buf = np.zeros((64, self._n_channels))
        raw_mv = raw / 1000.0
        self._ch_glitch_buf[self._ch_glitch_pos] = raw_mv
        self._ch_glitch_pos = (self._ch_glitch_pos + 1) % 64
        med_mv = np.median(self._ch_glitch_buf, axis=0)
        glitch_mask = np.abs(raw_mv - med_mv) > 100.0
        raw_display = np.where(glitch_mask, med_mv * 1000.0, raw)
        self._latest_raw = raw_display

        self._frame_count += 1
        self._rolling_buf.append((now, raw))

        if self._recording and self._session_file and not self._training_paused:
            self._session_write_row(fw_time_ms, now, raw, glitch_mask)

        if self._capturing:
            self._capture_buf.append(raw.copy())
            n = len(self._capture_buf)
            self.pb_capture.setText('Capturing {0}/{1}…'.format(n, self._capture_n))
            if n >= self._capture_n:
                self._finalise_capture()

        # Analysis tab training capture -- independent of the baseline
        # capture above (self._capturing/_capture_buf stay Heatmap-tab-only).
        if self._analysis_training_active:
            self._sig_train_ingest(now, raw, glitch_mask)

        if self._continuous_log:
            raw_nxn = raw.reshape(self._n_bands, self._n_cells)
            mean, _ = self._get_current_baseline()
            delta = (raw_nxn - mean) if mean is not None else np.zeros((self._n_bands, self._n_cells))
            self._append_csv_row(self.le_label.text(), delta, raw_nxn, mean)

        self._update_status()

    # ------------------------------------------------------------------
    # Baseline
    # ------------------------------------------------------------------
    def _start_capture(self):
        self._capture_n   = self.sp_capture_n.value()
        self._capture_buf = []
        self._capturing   = True
        self.pb_capture.setText('Capturing 0/{0}…'.format(self._capture_n))
        self.pb_capture.setStyleSheet(self.MY_YELLOW)

    def _finalise_capture(self):
        arr = np.array(self._capture_buf, dtype=float)
        self._baseline_mean = arr.mean(0).reshape(self._n_bands, self._n_cells)
        self._baseline_std  = arr.std(0).reshape(self._n_bands, self._n_cells)
        self._baseline_age  = time.time()
        self._capturing     = False
        self._capture_buf   = []
        self.pb_capture.setText('Capture baseline')
        self.pb_capture.setStyleSheet('')

    def clear_baseline(self):
        self._baseline_mean = None
        self._baseline_std  = None
        self._baseline_age  = None

    def _get_current_baseline(self):
        """Return (mean_nxn, std_nxn) or (None, None)."""
        if self._baseline_mode == 'static':
            return self._baseline_mean, self._baseline_std

        if self._baseline_mode == 'nominal':
            return self._nominal_baseline_uv.copy(), np.zeros((self._n_bands, self._n_cells))

        cutoff = time.time() - self._rolling_T
        frames = [arr for ts, arr in self._rolling_buf if ts >= cutoff]
        if not frames:
            return None, None
        mat  = np.array(frames, dtype=float)
        mean = np.median(mat, axis=0).reshape(self._n_bands, self._n_cells)
        std  = mat.std(axis=0).reshape(self._n_bands, self._n_cells)
        return mean, std

    def _compute_rolling_stddev_nxn(self):
        """Per-cell std dev of the raw (unfiltered-by-baseline) signal over the
        last N samples -- a live noise/jitter monitor, independent of any
        baseline capture. N is the Stats tab's 'Std dev N' spinbox, reusing
        _update_stats_table's exact rolling-window computation so the heatmap
        and stats-table std dev always agree for the same N."""
        n = self.sp_stats_window.value()
        recent = list(self._rolling_buf)[-n:]
        if len(recent) < 2:
            return np.zeros((self._n_bands, self._n_cells))
        mat  = np.array([arr for _, arr in recent], dtype=float)
        stds = mat.std(0).reshape(self._n_bands, self._n_cells)
        return stds[self._band_display_order]

    # ------------------------------------------------------------------
    # Display computation (heatmap)
    # ------------------------------------------------------------------
    def _compute_display_matrix(self, raw_nxn, mean, std, mode=None):
        mode = mode or self._display_mode
        if mode == 'raw':
            return raw_nxn.copy()
        if mode == 'stddev':
            return self._compute_rolling_stddev_nxn()
        if mean is None:
            return np.zeros((self._n_bands, self._n_cells))
        delta = raw_nxn - mean
        if mode == 'delta':
            return delta
        safe_std = np.where(std is not None and std > 1.0, std, 1.0)
        return delta / safe_std

    def _update_heatmap(self, matrix):
        if self._autoscale:
            lim = float(np.max(np.abs(matrix)))
            if lim < 1.0:
                lim = 1.0
        else:
            lim = self._manual_range

        if self._display_mode in ('raw', 'stddev'):
            cmap   = self.cm_seq
            levels = (0.0, float(matrix.max()) * 1.05 + 1.0)
            if self._display_mode == 'raw':
                self.lbl_scale.setText('Scale: 0…{0:.3f} mV'.format(matrix.max() / 1000))
            else:
                self.lbl_scale.setText('Std Dev (N={0}): 0…{1:.3f} mV'.format(
                    self.sp_stats_window.value(), matrix.max() / 1000))
        else:
            cmap   = self.cm_div
            levels = (-lim, lim)
            unit = 'σ' if self._display_mode == 'z' else 'mV'
            val  = lim if self._display_mode == 'z' else lim / 1000
            self.lbl_scale.setText('Scale: ±{0:.3f} {1}'.format(val, unit))

        self.img.setColorMap(cmap)
        self.img.setImage(matrix.T, levels=levels)

    def _update_3d(self, matrix):
        # Note: the band axis is coarse — interpolation between bands is
        # cosmetic smoothing only, not real data.
        if not _GL_AVAILABLE or not hasattr(self, '_surface'):
            return
        lim = max(float(np.abs(matrix).max()), 1.0)
        normed = np.clip((matrix + lim) / (2.0 * lim), 0.0, 1.0)
        try:
            rgba = self.cm_div.map(normed.T.flatten(), mode='float')
            rgba = rgba.reshape(self._n_cells, self._n_bands, 4)
            self._surface.setData(z=matrix.T, colors=rgba)
        except Exception:
            self._surface.setData(z=matrix.T)

    # ------------------------------------------------------------------
    # Stats table update
    # ------------------------------------------------------------------
    def _update_stats_table(self):
        if self._freeze_stats or self._latest_raw is None:
            return

        raw    = self._latest_raw   # (n_channels,)
        n      = self.sp_stats_window.value()
        recent = list(self._rolling_buf)[-n:]

        if len(recent) >= 2:
            mat   = np.array([arr for _, arr in recent], dtype=float)
            means = mat.mean(0)
            stds  = mat.std(0)
        else:
            means = raw.copy()
            stds  = np.zeros(self._n_channels)

        for d in range(self._n_bands):
            b = self._band_stats_order[d]
            for c in range(self._n_cells):
                row      = d * self._n_cells + c
                proto_ch = b * self._n_cells + c
                self.tbl_stats.item(row, 3).setText(_fmt(raw[proto_ch]))
                self.tbl_stats.item(row, 4).setText(_fmt(means[proto_ch]))
                std_mv = stds[proto_ch] / 1000.0
                item5 = self.tbl_stats.item(row, 5)
                item5.setText('{0:.3f}'.format(std_mv))
                lo = self.sp_std_lower.value()
                hi = self.sp_std_upper.value()
                if std_mv < lo:
                    item5.setBackground(QBrush(QColor(143, 240, 164)))
                elif std_mv > hi:
                    item5.setBackground(QBrush(QColor(246, 97, 81)))
                else:
                    item5.setBackground(QBrush(QColor(249, 240, 107)))

    def _save_stats_csv(self):
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        default = os.path.join(data_dir,
            'stats_{0}.csv'.format(datetime.now().strftime('%Y%m%d_%H%M%S')))
        path, _ = QFileDialog.getSaveFileName(
            self, 'Save stats table', default, 'CSV files (*.csv)')
        if not path:
            return
        headers = ['Band', 'Threshold', 'Delay (us)',
                   'Latest (mV)', 'Mean (mV)', 'Std (mV)']
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(','.join(headers) + '\n')
            for row in range(self.tbl_stats.rowCount()):
                f.write(','.join(
                    self.tbl_stats.item(row, col).text()
                    for col in range(self.tbl_stats.columnCount())) + '\n')
        self.statusBar().showMessage('Stats table saved: {0}'.format(path))

    def _toggle_record_frames(self, checked):
        if checked:
            self._session_start()
        else:
            self._session_stop()

    def _session_start(self, notes=None):
        """Open a new self-describing session-dump CSV and write its header.
        notes: pre-supplied session notes (e.g. auto-derived from the Training
        Session run list) that skip the interactive prompt entirely. If None,
        prompts the operator via QInputDialog (the plain Stats-tab "Record
        Session" flow, which has no run list to derive notes from)."""
        if notes is None:
            notes, _ = QInputDialog.getMultiLineText(
                self, 'Session notes', 'Planned target order / notes for this session:')
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        ts   = datetime.now()
        path = os.path.join(SESSIONS_DIR, 'session_{0}.csv'.format(ts.strftime('%Y%m%d_%H%M%S')))
        f = open(path, 'w')
        self._session_write_header(f, ts, notes)
        self._session_file        = f
        self._session_path        = path
        self._session_start_wall  = time.time()
        self._session_frame_count = 0
        self._recording = True
        self.pb_record.setText('■ 0 frames')
        self.pb_record.setStyleSheet(self.MY_RED)

    def _parsed_fw_version(self):
        """Read-only reuse of the existing raw V-response capture (process_
        packet's 'if line[0]==\"V\"' branch) -- no new protocol behavior, just
        string extraction from data already received. Mirrors
        pimd_features._fw_version_from_v_response()."""
        if not self._fw_version_line:
            return 'unknown'
        parts = self._fw_version_line.split(',')
        return parts[0].lstrip('V').strip() if parts and parts[0] else 'unknown'

    def _session_write_header(self, f, ts, notes):
        """Write the '#'-prefixed comment header: everything an AI analyst needs
        to interpret the data rows without any external profile file or context."""
        fw_line = self._fw_version_line or 'unknown (no V response received)'
        f.write('# PIMD session dump\n')
        f.write('# session_start_iso: {0}\n'.format(ts.isoformat()))
        f.write('# tool: pimd_classviz.py v{0}\n'.format(APP_VERSION))
        f.write('# firmware_v_response (V<fw>,<board_id>,<num_profiles>,<active_idx>,'
                '<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>): {0}\n'.format(fw_line))
        f.write('# fw_version: {0}\n'.format(self._parsed_fw_version()))
        f.write('# supply: {0}\n'.format(self.cb_supply.currentText()))
        f.write('# active_profile_idx: {0}\n'.format(self._active_profile_idx))
        f.write('# n_bands: {0}  n_cells: {1}  n_channels: {2}\n'.format(
            self._n_bands, self._n_cells, self._n_channels))
        f.write('# profile_json: {0}\n'.format(json.dumps(self._profile, separators=(',', ':'))))
        # Authoritative profile_sha8 -- computed from the literal loaded bytes
        # (_set_profile_dims), not a re-serialization of the dict above (which
        # can use different key order/separators and would hash differently).
        # pimd_features.py v6 prefers this line over re-hashing profile_json.
        f.write('# profile_sha8: {0}\n'.format(self._profile_sha8))
        f.write('# colmap_fields: col_index,band_index,freq_hz,pulse_us,delay_us,threshold_v\n')
        for ch in range(self._n_channels):
            b, c = ch // self._n_cells, ch % self._n_cells
            freq_hz, pulse_us, delays = self._bands_meta[b]
            thr = (self._profile['bands'][b]['threshold_v'][c]
                   if self._has_threshold_v else '')
            f.write('# colmap: {0},{1},{2},{3},{4},{5}\n'.format(
                ch, b, freq_hz, pulse_us, delays[c], thr))
        if notes.strip():
            for line in notes.splitlines():
                f.write('# session_notes: {0}\n'.format(line))
        else:
            f.write('# session_notes: (none)\n')
        headers = ['pc_wallclock_iso', 'firmware_time_ms'] + \
                  ['ch{0}_uV'.format(i) for i in range(self._n_channels)] + ['flagged']
        f.write(','.join(headers) + '\n')
        f.flush()

    def _session_write_row(self, fw_time_ms, wall_ts, raw, glitch_mask):
        """Append one raw (pre-filter, pre-baseline) frame and flush immediately
        so a crash or serial dropout mid-session never loses more than one row."""
        row = [datetime.fromtimestamp(wall_ts).isoformat(), str(fw_time_ms)] + \
              [str(int(v)) for v in raw] + \
              ['1' if glitch_mask.any() else '0']
        self._session_file.write(','.join(row) + '\n')
        self._session_file.flush()
        self._session_frame_count += 1

    def _session_stop(self):
        self._recording = False
        self.pb_record.setText('Record Session')
        self.pb_record.setStyleSheet(self.MY_YELLOW)
        if self._session_file:
            self._session_file.close()
            self.statusBar().showMessage('Session saved: {0}  ({1} frames)'.format(
                self._session_path, self._session_frame_count))
        self._session_file       = None
        self._session_path       = None
        self._session_start_wall = None
        # Centralized reset: covers this method being triggered from any of its
        # callers (this tab's own toggle, _apply_profile force-stop on a profile
        # change, start_stop force-stop on disconnect) so the Training Session
        # tab's UI never gets stuck in a "started" state when the underlying
        # recording is closed out from under it.
        if self._training_current_row is not None:
            self._reset_training_ui()
        if self._analysis_session_recording:
            self._analysis_session_recording = False
            self._set_sig_session_active_ui(False)
            self._update_sig_session_status_label()

    # ------------------------------------------------------------------
    # Ground-truth marks (low-level writer, reused by the Training Session tab)
    # ------------------------------------------------------------------
    def _append_mark(self, text):
        """Append one '#'-prefixed ground-truth mark line to the currently-open
        session CSV and flush immediately. Cheap, synchronous write+flush on the
        already-open handle — same non-blocking pattern as _session_write_row().
        Safe to call from a keyboard event handler: PyQt runs a single-threaded
        event loop, so this only ever delays the *next* event by the cost of one
        small write+flush, never the ~7.3 Hz frame-logging path (a separate
        readyRead event, not re-entered by this call)."""
        ts = datetime.fromtimestamp(time.time()).isoformat()
        self._session_file.write('# mark: {0}, {1}\n'.format(ts, text))
        self._session_file.flush()

    def _append_mark_target(self, target_id, placement):
        """Append one '#'-prefixed structured companion line immediately after
        a '# mark:' line (same timestamp basis, called right after
        _append_mark() in the same call frame) -- purely additive, does not
        alter '# mark:' or any of its existing consumers (pimd_features.
        parse_mark_label()/segment_from_marks() keep working unchanged on
        pre-v1.32 sessions with no 'mark_target:' companion). `placement`:
        dict with distance_mm, long_axis, face_normal, offset_x_mm,
        offset_y_mm, medium, repeat_idx, notes. csv-quotes the field portion
        (notes may contain commas) with lineterminator='\\n' so no stray '\\r'
        lands in the session CSV -- pimd_features.parse_mark_target_line()
        parses this exact format."""
        ts = datetime.fromtimestamp(time.time()).isoformat()
        buf = io.StringIO()
        csv.writer(buf, lineterminator='\n').writerow([
            target_id, placement['distance_mm'] if placement['distance_mm'] is not None else '',
            placement['long_axis'], placement['face_normal'],
            placement['offset_x_mm'], placement['offset_y_mm'], placement['medium'],
            placement['repeat_idx'], placement['notes'],
        ])
        self._session_file.write('# mark_target: {0}, {1}'.format(ts, buf.getvalue()))
        self._session_file.flush()

    # ------------------------------------------------------------------
    # Redraw (30 Hz timer)
    # ------------------------------------------------------------------
    def _redraw(self):
        if self._recording:
            elapsed = time.time() - self._session_start_wall
            self.pb_record.setText('■ {0} frames, {1}'.format(
                self._session_frame_count, str(timedelta(seconds=int(elapsed)))))

        if self._latest_raw is None:
            return

        # Always update heatmap so it's current when user switches back to it
        if not self._freeze:
            mean, std = self._get_current_baseline()
            raw_nxn   = self._latest_raw.reshape(self._n_bands, self._n_cells)
            raw_nxn   = raw_nxn[self._band_display_order]
            if mean is not None:
                mean = mean[self._band_display_order]
                if std is not None:
                    std = std[self._band_display_order]
            matrix    = self._compute_display_matrix(raw_nxn, mean, std)
            self._update_heatmap(matrix)
            if self._3d_visible:
                self._update_3d(matrix)
            self._update_baseline_label(mean)
            delta_nxn = (raw_nxn - mean) if mean is not None else None
            self._update_crossings(delta_nxn)

        # Stats table — only compute when that tab is visible
        if self.tabs.currentIndex() == 1:
            self._update_stats_table()

        # Analysis tab's heatmap variant is always kept current (own scale/
        # normalize mode, decoupled from the main Heatmap tab), same "always
        # update" convention as the main heatmap, so switching tabs is instant.
        self._update_analysis_heatmap()

        # The rest of the Analysis tab's charts/strips — only compute when
        # that tab is visible.
        if self.tabs.currentIndex() == self.ANALYSIS_TAB_INDEX:
            self._update_analysis_charts()
            self._update_analysis_strips()

        # Training Session live cells — always live regardless of visible tab
        # (operator may be watching Heatmap while physically holding the probe).
        if self._training_current_row is not None:
            self._update_training_live()

    def _update_baseline_label(self, mean):
        mode = self._baseline_mode
        if mode == 'nominal':
            self.lbl_baseline_info.setText('Baseline: Nominal thresholds')
        elif mode == 'rolling':
            now   = time.time()
            count = sum(1 for ts, _ in self._rolling_buf if ts >= now - self._rolling_T)
            self.lbl_baseline_info.setText(
                'Baseline: Rolling {0:.1f}s ({1} frames)'.format(self._rolling_T, count))
        else:
            if self._capturing:
                self.lbl_baseline_info.setText('Baseline: Capturing…')
            elif mean is None:
                self.lbl_baseline_info.setText('Baseline: None — click Capture')
            else:
                age = (time.time() - self._baseline_age) if self._baseline_age else 0
                self.lbl_baseline_info.setText(
                    'Baseline: Static ({0}fr, {1:.0f}s ago)'.format(self._capture_n, age))

    def _update_crossings(self, delta_nxn):
        if delta_nxn is None:
            self.lbl_crossings.setText('Crossings: no baseline')
            return
        crossings = self._compute_crossings(delta_nxn)
        parts = []
        for b, cross in enumerate(crossings):
            pol = '+' if delta_nxn[b, 0] > 0 else '−'
            if cross is not None and self._has_threshold_v:
                tv = self._nominal_baseline_uv[self._band_display_order[b]] / 1_000_000
                j  = int(np.floor(cross))
                frac = cross - j
                thresh_v = tv[j] * (1 - frac) + tv[min(j + 1, len(tv) - 1)] * frac
                parts.append('B{0}:{1}↔{2:.3f}V'.format(b, pol, thresh_v))
            elif cross is not None:
                parts.append('B{0}:{1}↔cell{2:.3f}'.format(b, pol, cross))
            else:
                parts.append('B{0}:{1}'.format(b, pol))
        self.lbl_crossings.setText('Crossings:  ' + '   '.join(parts))

    # ------------------------------------------------------------------
    # Zero-crossing
    # ------------------------------------------------------------------
    def _compute_crossings(self, delta_nxn):
        crossings = []
        for b in range(self._n_bands):
            row   = delta_nxn[b]
            found = None
            for j in range(self._n_cells - 1):
                if row[j] * row[j + 1] < 0:
                    denom = abs(row[j]) + abs(row[j + 1])
                    frac  = abs(row[j]) / denom if denom > 0 else 0.5
                    found = j + frac
                    break
            crossings.append(found)
        return crossings

    def _on_freeze_stats_toggled(self, checked):
        self._freeze_stats = checked
        self.pb_freeze_stats.setStyleSheet(self.MY_YELLOW if checked else '')

    def _stats_rows_shrink(self):
        self._stats_row_height = max(12, self._stats_row_height - 4)
        self.tbl_stats.verticalHeader().setDefaultSectionSize(self._stats_row_height)

    def _stats_rows_grow(self):
        self._stats_row_height = min(48, self._stats_row_height + 4)
        self.tbl_stats.verticalHeader().setDefaultSectionSize(self._stats_row_height)

    # ------------------------------------------------------------------
    # ML bridge
    # ------------------------------------------------------------------
    def _record_snapshot(self):
        if self._latest_raw is None:
            self.statusBar().showMessage('No data to record')
            return
        raw_nxn = self._latest_raw.reshape(self._n_bands, self._n_cells)
        mean, _ = self._get_current_baseline()
        delta   = (raw_nxn - mean) if mean is not None else np.zeros((self._n_bands, self._n_cells))
        self._append_csv_row(self.le_label.text(), delta, raw_nxn, mean)
        self.statusBar().showMessage('Snapshot recorded — row {0}'.format(self._csv_rows))

    def _on_continuous_toggled(self, checked):
        self._continuous_log = checked

    def _write_csv_header(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        n = self._n_channels
        d_cols = ','.join('d{0:02d}'.format(i) for i in range(n))
        r_cols = ','.join('r{0:02d}'.format(i) for i in range(n))
        b_cols = ','.join('b{0:02d}'.format(i) for i in range(n))
        band_order = '  '.join('{0}={1}'.format(i, lbl)
                               for i, lbl in enumerate(self._band_labels))
        with open(path, 'w') as f:
            f.write('# PIMD ClassViz labelled-data log — profile {0} ({1}),'
                    ' generated by pimd_classviz.py v{2}\n'.format(
                        self._active_profile_idx, self._profile.get('name', '?'), APP_VERSION))
            f.write('# Columns: timestamp, label, baseline_mode,\n')
            f.write('#   d00..d{0:02d} = signed deviation uV (band-major: index=band*{1}+cell),\n'.format(
                n - 1, self._n_cells))
            f.write('#   r00..r{0:02d} = raw absolute uV,\n'.format(n - 1))
            f.write('#   b00..b{0:02d} = baseline mean uV used for delta\n'.format(n - 1))
            f.write('# Band order: {0}\n'.format(band_order))
            f.write('# Cell labels: {0}\n'.format(', '.join(self._cell_labels)))
            f.write('timestamp,label,baseline_mode,{0},{1},{2}\n'.format(d_cols, r_cols, b_cols))

    def _append_csv_row(self, label, delta_nxn, raw_nxn, baseline_nxn):
        path = self.le_csv.text()
        if not path:
            return
        if not self._csv_header_written:
            if not os.path.exists(path):
                self._write_csv_header(path)
            self._csv_header_written = True
        bl  = baseline_nxn if baseline_nxn is not None else np.zeros((self._n_bands, self._n_cells))
        ts  = datetime.now().isoformat(timespec='milliseconds')
        row = [ts, label, self._baseline_mode]
        row += delta_nxn.flatten().astype(int).tolist()
        row += raw_nxn.flatten().astype(int).tolist()
        row += bl.flatten().astype(int).tolist()
        with open(path, 'a') as f:
            f.write(','.join(str(v) for v in row) + '\n')
        self._csv_rows += 1
        self.lbl_rows.setText('Rows: {0}'.format(self._csv_rows))

    def _browse_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, 'Select CSV file', self.le_csv.text(), 'CSV files (*.csv)')
        if path:
            self.le_csv.setText(path)
            self._csv_header_written = False

    # ------------------------------------------------------------------
    # Toggle 2D / 3D
    # ------------------------------------------------------------------
    def _toggle_3d(self):
        if not _GL_AVAILABLE:
            self.statusBar().showMessage('3D view not available — install python3-pyopengl')
            return
        self._3d_visible = not self._3d_visible
        self.stack.setCurrentIndex(1 if self._3d_visible else 0)
        self.pb_toggle3d.setText(
            'Switch to 2D Heatmap' if self._3d_visible else 'Switch to 3D Surface')

    # ------------------------------------------------------------------
    # UI signal handlers
    # ------------------------------------------------------------------
    def _on_display_changed(self, idx):
        self._display_mode = ('delta', 'z', 'raw', 'stddev')[idx]

    def _on_baseline_mode_changed(self, idx):
        self._baseline_mode = ('static', 'rolling', 'nominal')[idx]

    def _on_freeze_toggled(self, checked):
        self._freeze = checked
        self.pb_freeze.setStyleSheet(self.MY_YELLOW if checked else '')

    def _on_autoscale_toggled(self, checked):
        self._autoscale = checked
        self.sp_range.setEnabled(not checked)

    def _on_range_changed(self, val):
        self._manual_range = val

    def _on_rolling_t_changed(self, val):
        self._rolling_T = val

    def _on_mouse_move(self, pos):
        if self.plot.sceneBoundingRect().contains(pos):
            vp = self.plot.vb.mapSceneToView(pos)
            cx, cy = int(vp.x()), int(vp.y())
            if 0 <= cx < self._n_cells and 0 <= cy < self._n_bands:
                delay_us = self._bands_meta[self._band_display_order[cy]][2][cx]
                self.statusBar().showMessage(
                    'Band {0} ({1}) | Cell {2} ({3}) | delay = {4:.3f} µs'.format(
                        cy, self._display_band_labels[cy], cx, self._cell_labels[cx], delay_us))
                return
        self._update_status()

    def _update_status(self):
        rec = ''
        if self._recording:
            elapsed = time.time() - self._session_start_wall
            rec = 'REC {0}f {1}  |  '.format(
                self._session_frame_count, str(timedelta(seconds=int(elapsed))))
        self.statusBar().showMessage(
            '{0}Frames: {1}  Cmd: {2:<6}  Last: {3}'.format(
                rec, self._frame_count, self._last_cmd, self._last_packet[:60]))

    def _update_rate(self):
        """Runs once/sec (see _rate_timer, __init__) — updates the top-bar
        throughput readout so it's visible regardless of which tab is active.
        Exact frames-in-the-last-second, not a smoothed average, so a stall
        shows up immediately as 0 Hz rather than decaying slowly into view."""
        now    = time.time()
        dt     = now - self._fps_last_calc_wall
        dcount = max(0, self._frame_count - self._fps_last_frame_count)
        self._fps_hz = dcount / dt if dt > 0 else 0.0
        self._fps_last_calc_wall   = now
        self._fps_last_frame_count = self._frame_count

        burst = self._serial_max_batch
        self._serial_max_batch = 0

        if not self.serial.isOpen() or self.pb_start.text() != 'Running':
            self.lbl_rate.setText('Rate: — (idle)')
            self.lbl_rate.setStyleSheet('')
            return

        cell_hz = self._fps_hz * self._n_channels
        txt = 'Rate: {0:.1f} Hz  ({1:,.0f} cells/s)'.format(self._fps_hz, cell_hz)
        if burst > 3:
            # A single readyRead drained more than 3 complete lines -- the
            # event loop briefly fell behind the ~100 Hz nominal stream.
            txt += '  ⚠ burst×{0}'.format(burst)
            self.lbl_rate.setStyleSheet(self.MY_YELLOW)
        else:
            self.lbl_rate.setStyleSheet('')
        self.lbl_rate.setText(txt)

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------
    def _load_settings(self):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            self.le_port.setText(s.get('port', DEFAULT_PORT))
            self.sp_capture_n.setValue(int(s.get('capture_n', CAPTURE_FRAMES_DEFAULT)))
            self.sp_rolling_t.setValue(float(s.get('rolling_t', ROLLING_SECS_DEFAULT)))
            self.cb_display.setCurrentIndex(int(s.get('display_idx', 0)))
            self.cb_baseline.setCurrentIndex(int(s.get('baseline_idx', 0)))
            self.sp_stats_window.setValue(int(s.get('stats_window', 50)))
            autoscale = bool(s.get('autoscale', True))
            self.cb_autoscale.setChecked(autoscale)
            if not autoscale:
                self.sp_range.setValue(float(s.get('range_uv', 200_000.0)))
            w = int(s.get('window_w', 1100))
            h = int(s.get('window_h', 900))
            self.resize(w, h)
            x, y = s.get('window_x'), s.get('window_y')
            if x is not None and y is not None:
                self.move(int(x), int(y))

            # Analysis tab -- avg-N, per-group Auto/Manual normalize+scale
            # (heatmap/chart2/8-grid/9-grid/strip), signature capture-N.
            # Deliberately NOT persisted: the active editable signature-file
            # path, in-progress captures -- resuming a stale "editing"
            # pointer at a file that may have changed or been deleted
            # between sessions is a foot-gun; every session starts read-only
            # with no active file.
            self.sp_analysis_avg_n.setValue(int(s.get('analysis_avg_n', 1)))

            self.cb_supply.setCurrentText(s.get('supply', SUPPLY_CHOICES[0]))

            # Last-used target_id + placement ARE persisted (v1.32+) -- the
            # original "don't persist target/distance" foot-gun above was
            # about *free text*: a stale/typo'd string looked plausible
            # forever. A registry-validated combo makes a dangling
            # target_id *detectable* (a dict lookup against the freshly
            # loaded registry, done in _load_targets_registry() before this
            # runs), so it's safe to restore -- silently falling back to
            # 'air' on a miss rather than restoring a meaningless
            # placement. repeat_idx is deliberately NOT persisted (it's
            # inherently per-save/derived).
            sig_target_id = s.get('sig_target_id')
            if sig_target_id and sig_target_id in self._targets or sig_target_id == 'air':
                self._populate_target_combo(self.sig_target, selected_target_id=sig_target_id)
                self.sig_distance_mm.setValue(int(s.get('sig_distance_mm', 50)))
                self.sig_long_axis.setCurrentText(s.get('sig_long_axis', 'na'))
                self.sig_face_normal.setCurrentText(s.get('sig_face_normal', 'na'))
                self.sig_offset_x_mm.setValue(int(s.get('sig_offset_x_mm', 0)))
                self.sig_offset_y_mm.setValue(int(s.get('sig_offset_y_mm', 0)))
                self.sig_medium.setCurrentText(s.get('sig_medium', 'air'))
                self.sig_notes.setText(s.get('sig_notes', ''))

            self.cb_hm_norm.setCurrentIndex(int(s.get('analysis_hm_norm_idx', 0)))
            self.cb_hm_scale_auto.setChecked(bool(s.get('analysis_hm_scale_auto', True)))
            self.sp_hm_scale_manual.setValue(float(s.get('analysis_hm_scale_manual', 200_000.0)))

            self.cb_c2_norm_auto.setChecked(bool(s.get('analysis_c2_norm_auto', True)))
            self.sp_c2_norm_manual.setValue(float(s.get('analysis_c2_norm_manual', 0.0)))
            self.cb_c2_scale_auto.setChecked(bool(s.get('analysis_c2_scale_auto', True)))
            self.sp_c2_scale_manual.setValue(float(s.get('analysis_c2_scale_manual', 5.0)))

            self.cb_g8_norm_auto.setChecked(bool(s.get('analysis_g8_norm_auto', True)))
            self.sp_g8_norm_manual.setValue(float(s.get('analysis_g8_norm_manual', 0.0)))
            self.cb_g8_scale_auto.setChecked(bool(s.get('analysis_g8_scale_auto', True)))
            self.sp_g8_scale_manual.setValue(float(s.get('analysis_g8_scale_manual', 5.0)))

            self.cb_g9_norm_auto.setChecked(bool(s.get('analysis_g9_norm_auto', True)))
            self.sp_g9_norm_manual.setValue(float(s.get('analysis_g9_norm_manual', 0.0)))
            self.cb_g9_scale_auto.setChecked(bool(s.get('analysis_g9_scale_auto', True)))
            self.sp_g9_scale_manual.setValue(float(s.get('analysis_g9_scale_manual', 5.0)))

            self.cb_strip_norm_auto.setChecked(bool(s.get('analysis_strip_norm_auto', True)))
            self.sp_strip_norm_manual.setValue(float(s.get('analysis_strip_norm_manual', 0.0)))
            self.cb_strip_scale_auto.setChecked(bool(s.get('analysis_strip_scale_auto', True)))
            self.sp_strip_scale_manual.setValue(float(s.get('analysis_strip_scale_manual', 5.0)))

            self.sp_sig_capture_n.setValue(int(s.get('sig_capture_n', pimd_features.MIN_CENTRAL_FRAMES)))
            self.sp_sig_settle_mv.setValue(float(s.get('sig_settle_mv', 1.0)))
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            self.resize(1100, 900)  # first run

    def _save_settings(self):
        s = {
            'port':         self.le_port.text(),
            'capture_n':    self.sp_capture_n.value(),
            'rolling_t':    self.sp_rolling_t.value(),
            'display_idx':  self.cb_display.currentIndex(),
            'baseline_idx': self.cb_baseline.currentIndex(),
            'stats_window': self.sp_stats_window.value(),
            'range_uv':     self.sp_range.value(),
            'autoscale':    self.cb_autoscale.isChecked(),
            'window_w':     self.width(),
            'window_h':     self.height(),
            'window_x':     self.x(),
            'window_y':     self.y(),

            'analysis_avg_n': self.sp_analysis_avg_n.value(),

            'analysis_hm_norm_idx':     self.cb_hm_norm.currentIndex(),
            'analysis_hm_scale_auto':   self.cb_hm_scale_auto.isChecked(),
            'analysis_hm_scale_manual': self.sp_hm_scale_manual.value(),

            'analysis_c2_norm_auto':    self.cb_c2_norm_auto.isChecked(),
            'analysis_c2_norm_manual':  self.sp_c2_norm_manual.value(),
            'analysis_c2_scale_auto':   self.cb_c2_scale_auto.isChecked(),
            'analysis_c2_scale_manual': self.sp_c2_scale_manual.value(),

            'analysis_g8_norm_auto':    self.cb_g8_norm_auto.isChecked(),
            'analysis_g8_norm_manual':  self.sp_g8_norm_manual.value(),
            'analysis_g8_scale_auto':   self.cb_g8_scale_auto.isChecked(),
            'analysis_g8_scale_manual': self.sp_g8_scale_manual.value(),

            'analysis_g9_norm_auto':    self.cb_g9_norm_auto.isChecked(),
            'analysis_g9_norm_manual':  self.sp_g9_norm_manual.value(),
            'analysis_g9_scale_auto':   self.cb_g9_scale_auto.isChecked(),
            'analysis_g9_scale_manual': self.sp_g9_scale_manual.value(),

            'analysis_strip_norm_auto':    self.cb_strip_norm_auto.isChecked(),
            'analysis_strip_norm_manual':  self.sp_strip_norm_manual.value(),
            'analysis_strip_scale_auto':   self.cb_strip_scale_auto.isChecked(),
            'analysis_strip_scale_manual': self.sp_strip_scale_manual.value(),

            'sig_capture_n': self.sp_sig_capture_n.value(),
            'sig_settle_mv': self.sp_sig_settle_mv.value(),

            'supply': self.cb_supply.currentText(),

            'sig_target_id':   self.sig_target.currentData(),
            'sig_distance_mm': self.sig_distance_mm.value(),
            'sig_long_axis':   self.sig_long_axis.currentText(),
            'sig_face_normal': self.sig_face_normal.currentText(),
            'sig_offset_x_mm': self.sig_offset_x_mm.value(),
            'sig_offset_y_mm': self.sig_offset_y_mm.value(),
            'sig_medium':      self.sig_medium.currentText(),
            'sig_notes':       self.sig_notes.text(),
        }
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(s, f, indent=2)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Global key handling — mark hotkeys
    # ------------------------------------------------------------------
    def eventFilter(self, obj, event):
        """App-wide filter (installed on the QApplication instance) so the
        Space-bar actions work regardless of focus, and are swallowed before
        widgets that already consume Space (e.g. QPushButton's
        Space-to-click). Suppressed whenever a text-entry widget has focus
        (including a QTableWidget cell mid-edit, which uses an embedded
        QLineEdit). Dispatch (v1.33): an active Analysis-tab training session
        gets Space as Acquire while that tab is visible; otherwise Space
        stays the Training Session tab's step-advance."""
        if event.type() == QEvent.Type.KeyPress:
            if isinstance(QApplication.focusWidget(), (QLineEdit, QSpinBox, QDoubleSpinBox)):
                return super().eventFilter(obj, event)
            if event.isAutoRepeat():
                return True   # swallow held-key repeats
            if event.key() == Qt.Key.Key_Space:
                if self._analysis_training_active and \
                        self.tabs.currentIndex() == self._analysis_tab_index:
                    self._on_sig_train_acquire()
                else:
                    self._on_training_space()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._save_settings()
        if self.serial.isOpen():
            self.send_command('E')
            self.serial.waitForBytesWritten(100)
            self.serial.close()
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication([])
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
