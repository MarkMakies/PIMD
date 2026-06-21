###############################################################################
# PIMD Signature Visualiser (ClassViz) v1.14
# — Mode 2 adaptive profile viewer
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# Connects to the board, sends Q4/G to start Mode 2 streaming with the default
# CLASSIFY_EP profile, and displays a heatmap of signed cell deviations from a
# captured air baseline. Includes a labelled-data logger for ML training data
# capture, and a Profile Builder tab to edit/save/load band/pulse/delay profiles
# and send them to the board as a RAM-only "dynamic" profile (firmware D command)
# without reflashing — the heatmap/stats table/single-cell selectors resize to
# match whatever profile (static or dynamic) is active.
#
# Protocol: receives W<profile_idx>,<time_ms>,<ch0>,...,<chN-1>
# Board firmware: pimd_mcu.py v4.23+
#
# v1.14 Stats table and Profile Builder table rows now sorted ascending by first
#       delay value (lowest delay first).  _band_stats_order / _stats_band_labels
#       added to _set_profile_dims(); _rebuild_stats_table() and
#       _update_stats_table() use these in place of _band_display_order.
#       _populate_profile_editor() sorts bands by delays_us[0] ascending before
#       populating the table.  Heatmap display order unchanged (still descending).
# v1.13 Remove single-cell isolation: QGroupBox, _rebuild_single_cell_combos(),
#       _on_sc_band_changed(), _update_sc_info(), _run_single_cell(),
#       _resume_sweep(), _update_sc_button_states() all deleted.  _mode /
#       _sc_buf state and the Mode-1 '*' packet branch in process_packet()
#       removed.  start_stop() and _on_send_run_profile() simplified.
#       Tab renamed 'Stats' (was 'Stats && Isolation').  sc_ds removed from
#       settings persistence.
# v1.12 Heatmap row sort: bands displayed in descending delay order regardless of
#       profile stream order (alternating high/low pulse profiles stay ordered).
#       Band labels changed to '<freq Hz with ,>Hz / <pulse 1dp>µs' format.
#       _band_display_order maps display row → protocol band index; used in
#       _redraw(), stats table, and mouse tooltip. Serial commands and CSV logging
#       keep protocol (stream) order unchanged.
# v1.11 Settings persistence: port, capture N, rolling T, display mode, baseline
#       mode, stats std-dev window, single-cell downsample, manual range, autoscale
#       flag, and window geometry (size + position) saved to
#       data/classviz_settings.json on close and restored on startup.
#       _load_settings() called at end of __init__ after _build_ui(); first-run
#       default window size 1100×900 is now set there (removed from __main__).
# v1.10 * command (single-cell Mode 1) updated to match MCU v4.23 protocol:
#       freq in Hz (integer), pulse and delay in ns (integer).
#       Title standardised to include author.
# v1.09 _band_labels: pulse width and frequency now show 3 d.p. (was 0 d.p. / 1 d.p.).
#       Stats table Delay column: now 3 d.p. (was 2 d.p.).  Matches 8 ns grid precision.
# v1.08 Stats tab std-dev window: changed from seconds-based (QDoubleSpinBox, 0.5–60 s)
#       to sample-count-based (QSpinBox, 2–2000, default 50) to match pimd_delaycal.py.
#       Std column now shows 2 decimal places (was 1 d.p.).
# v1.07 process_packet: 64-frame circular median glitch filter on display path.
#       _latest_raw (→ heatmap, stats tab) uses median-substituted values when a
#       channel deviates >100 mV from its 64-frame median; _rolling_buf and
#       _record_buf keep the unfiltered raw values. Targets the 32-frame flat-step
#       ADC bit-truncation artifacts (440–880 mV shifts, fw v4.21 primary fix)
#       while leaving real signals (e.g. ±7 mV environmental pickup) fully visible.
#       64-frame window ensures ≥33 clean frames in buffer throughout any 32-frame
#       glitch, keeping the median stable.
# v1.06 Stats tab: add "Record Frames" toggle button — starts/stops recording of
#       raw W-record frames (fw_time_ms, wall_time_s, ch0…chN-1 in µV); auto-saves
#       to data/frames_YYYYMMDD_HHMMSS.csv on stop. Recording is also auto-stopped
#       when streaming stops or the profile changes.
# v1.05 fix _fmt(): remove thousands-separator from format string so saved CSV
#       files are machine-parseable (4373.6 not 4,373.6)
# v1.04 profile dimensions (N_BANDS/N_CELLS/BANDS_META/etc) moved from module
#       constants to instance state set by _apply_profile(); added Profile
#       Builder tab to edit/save/load profiles and send them to the board's new
#       D command (RAM-only dynamic profile, Q<DYNAMIC_PROFILE_INDEX>); default
#       Q4-on-connect behaviour unchanged
# v1.03 Stats tab: Save table as CSV button (saves whatever is currently displayed)
# v1.02 Resume Sweep now auto-sends G — sweep restarts immediately without extra click
# v1.01 add Stats tab (per-cell value/mean/std, mV) + single-cell isolation mode
# v1.00 initial version: heatmap + baseline + labelled CSV logger + 3D surface
###############################################################################

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import json
import os
import sys
import time
from datetime import datetime, date
from collections import deque

import numpy as np

os.environ.setdefault('QT_API', 'pyqt6')

from PyQt6.QtCore import QIODevice, QTimer, Qt  # noqa: E402
from PyQt6.QtSerialPort import QSerialPort  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QPushButton, QSpinBox, QStackedWidget, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import pyqtgraph as pg  # noqa: E402

try:
    import pyqtgraph.opengl as gl
    _GL_AVAILABLE = True
except ImportError:
    _GL_AVAILABLE = False

APP_VERSION = '1.14'

REDRAW_MS   = 33    # ~30 Hz

DEFAULT_PROFILE_IDX   = 4   # static CLASSIFY_EP — sent automatically on connect
DYNAMIC_PROFILE_INDEX = 5   # must match firmware's NUM_PROFILES (pimd_mcu.py v4.07+)

CAPTURE_FRAMES_DEFAULT = 64
ROLLING_SECS_DEFAULT   = 3.0
DEFAULT_PORT = '/dev/ttyACM0'

PROFILES_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'profiles')
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
    with open(os.path.join(PROFILES_DIR, name + '.json')) as f:
        return json.load(f)


def _save_profile_file(name, profile):
    os.makedirs(PROFILES_DIR, exist_ok=True)
    with open(os.path.join(PROFILES_DIR, name + '.json'), 'w') as f:
        json.dump(profile, f, indent=2)


pg.setConfigOptions(background='w', foreground='k', antialias=True)

_R = int(Qt.AlignmentFlag.AlignRight) | int(Qt.AlignmentFlag.AlignVCenter)
_C = int(Qt.AlignmentFlag.AlignCenter)


def _fmt(uv):
    """µV → mV string with 1 d.p."""
    return '{0:.1f}'.format(uv / 1000.0)


def _csv_default_path():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    return os.path.join(data_dir, 'signatures_{0}.csv'.format(date.today().strftime('%Y%m%d')))


class MainWindow(QMainWindow):
    MY_GREEN  = 'background-color: rgb(143, 240, 164);'
    MY_YELLOW = 'background-color: rgb(249, 240, 107);'
    MY_RED    = 'background-color: rgb(246,  97,  81);'

    def __init__(self):
        super().__init__()
        self.setWindowTitle('PIMD ClassViz v{0} by Mark Makies'.format(APP_VERSION))

        # Serial
        self.serial = QSerialPort()
        self.serial.readyRead.connect(self.read_from_serial)
        self._last_cmd    = ''
        self._last_packet = ''

        # Profile dimensions (n_bands, n_cells, labels, etc) — instance state so
        # the heatmap/stats table/single-cell selectors can resize at runtime
        # when a dynamic profile is sent from the Profile Builder tab.
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

        self._recording   = False
        self._record_buf: list = []   # list of (fw_time_ms, wall_time_s, raw_uv_array)

        self._ch_glitch_buf: 'np.ndarray | None' = None  # shape (64, n_channels), circular
        self._ch_glitch_pos  = 0

        # Data state — stats
        self._freeze_stats = False

        self._setup_colormaps()
        self._build_ui()
        self._load_settings()

        self._redraw_timer = QTimer()
        self._redraw_timer.setInterval(REDRAW_MS)
        self._redraw_timer.timeout.connect(self._redraw)
        self._redraw_timer.start()

    # ------------------------------------------------------------------
    # Profile dimensions
    # ------------------------------------------------------------------
    def _set_profile_dims(self, profile, profile_idx):
        """Pure data update — sets self._n_bands/_n_cells/_band_labels/etc from
        `profile` (dict: name, averages, bands=[{freq_hz,pulse_us,delays_us,
        threshold_v(optional)}, ...], all bands sharing the same delay count).
        Does not touch any UI widgets — see _apply_profile() for that."""
        bands = profile['bands']
        n_bands = len(bands)
        n_cells = len(bands[0]['delays_us'])
        self._profile           = profile
        self._active_profile_idx = profile_idx
        self._n_bands    = n_bands
        self._n_cells    = n_cells
        self._n_channels = n_bands * n_cells
        # Keep the (freq_hz, pulse_us, delays_us_tuple) shape used throughout
        # the rest of the file (was the module-level BANDS_META tuple).
        self._bands_meta = [(b['freq_hz'], b['pulse_us'], tuple(b['delays_us']))
                             for b in bands]
        self._band_labels = ['{0:,}Hz / {1:.1f}µs'.format(b['freq_hz'], b['pulse_us'])
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
            self._cell_labels = ['{0:.1f}V'.format(v) for v in bands[0]['threshold_v']]
            self._nominal_baseline_uv = np.array(
                [[v * 1_000_000 for v in b['threshold_v']] for b in bands], dtype=float)
        else:
            self._cell_labels = ['d{0}'.format(j) for j in range(n_cells)]
            self._nominal_baseline_uv = np.zeros((n_bands, n_cells))

    def _apply_profile(self, profile, profile_idx):
        """Switch the active profile at runtime: updates dimensions, clears any
        old-shape buffered data, and resizes the heatmap/3D surface/stats table/
        single-cell selectors to match. Called once for the default profile (via
        _set_profile_dims directly, before _build_ui) and again whenever a
        dynamic profile is sent from the Profile Builder tab."""
        self._set_profile_dims(profile, profile_idx)

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

        self.header_label = QLabel('Profile {0} — {1} ({2} bands × {3} cells)'.format(
            self._active_profile_idx, self._profile.get('name', '?'),
            self._n_bands, self._n_cells))
        row1.addWidget(self.header_label, stretch=1)
        layout.addLayout(row1)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_heatmap_tab(), 'Heatmap')
        self.tabs.addTab(self._build_stats_tab(),   'Stats')
        self.tabs.addTab(self._build_profile_tab(), 'Profile Builder')
        layout.addWidget(self.tabs, stretch=1)

        self.setCentralWidget(central)
        self.statusBar().showMessage('Not connected')

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
        self.cb_display.addItems(['Δ deviation [default]', 'Z normalised', 'RAW abs µV'])
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

        ctrl.addWidget(QLabel('Std dev N:'))
        self.sp_stats_window = QSpinBox()
        self.sp_stats_window.setRange(2, 2000)
        self.sp_stats_window.setSingleStep(10)
        self.sp_stats_window.setValue(50)
        ctrl.addWidget(self.sp_stats_window)

        pb_save_stats = QPushButton('Save table CSV…')
        pb_save_stats.clicked.connect(self._save_stats_csv)
        ctrl.addWidget(pb_save_stats)

        self.pb_record = QPushButton('Record Frames')
        self.pb_record.setCheckable(True)
        self.pb_record.setStyleSheet(self.MY_YELLOW)
        self.pb_record.toggled.connect(self._toggle_record_frames)
        ctrl.addWidget(self.pb_record)

        ctrl.addStretch(1)
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
    # Tab 2 — Profile Builder
    # ------------------------------------------------------------------
    def _build_profile_tab(self):
        w      = QWidget()
        layout = QVBoxLayout(w)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel('Saved profile:'))
        self.cb_profile_file = QComboBox()
        self._refresh_profile_file_list()
        row1.addWidget(self.cb_profile_file, stretch=1)
        pb_load = QPushButton('Load')
        pb_load.clicked.connect(self._on_load_profile_file)
        row1.addWidget(pb_load)
        pb_save = QPushButton('Save')
        pb_save.clicked.connect(self._on_save_profile_file)
        row1.addWidget(pb_save)
        pb_save_as = QPushButton('Save As…')
        pb_save_as.clicked.connect(self._on_save_profile_file_as)
        row1.addWidget(pb_save_as)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel('Name:'))
        self.le_profile_name = QLineEdit()
        row2.addWidget(self.le_profile_name, stretch=1)
        row2.addWidget(QLabel('Averages:'))
        self.sp_profile_avg = QSpinBox()
        self.sp_profile_avg.setRange(1, 256)
        self.sp_profile_avg.setValue(32)
        row2.addWidget(self.sp_profile_avg)
        layout.addLayout(row2)

        self.tbl_profile_bands = QTableWidget(0, 4)
        self.tbl_profile_bands.setHorizontalHeaderLabels(
            ['Freq (Hz)', 'Pulse (µs)', 'Delays (µs, comma-sep)',
             'Threshold V (optional, comma-sep)'])
        self.tbl_profile_bands.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tbl_profile_bands, stretch=1)

        row3 = QHBoxLayout()
        pb_add_band = QPushButton('Add Band')
        pb_add_band.clicked.connect(self._on_add_band_row)
        row3.addWidget(pb_add_band)
        pb_remove_band = QPushButton('Remove Band')
        pb_remove_band.clicked.connect(self._on_remove_band_row)
        row3.addWidget(pb_remove_band)
        row3.addStretch(1)
        layout.addLayout(row3)

        self.lbl_profile_validation = QLabel('')
        layout.addWidget(self.lbl_profile_validation)

        row_cmd = QHBoxLayout()
        row_cmd.addWidget(QLabel('Command:'))
        self.le_profile_command = QLineEdit()
        self.le_profile_command.setReadOnly(True)
        row_cmd.addWidget(self.le_profile_command, stretch=1)
        layout.addLayout(row_cmd)

        row4 = QHBoxLayout()
        self.pb_send_run = QPushButton('Send && Run')
        self.pb_send_run.setStyleSheet(self.MY_YELLOW)
        self.pb_send_run.clicked.connect(self._on_send_run_profile)
        row4.addWidget(self.pb_send_run)
        row4.addStretch(1)
        layout.addLayout(row4)

        # Any edit re-validates and refreshes the command preview.
        self.tbl_profile_bands.itemChanged.connect(self._on_profile_table_changed)
        self.le_profile_name.textChanged.connect(self._on_profile_table_changed)
        self.sp_profile_avg.valueChanged.connect(self._on_profile_table_changed)

        # Seed the editor with the currently active profile (CLASSIFY_EP baseline
        # on first launch).
        self._populate_profile_editor(self._profile)
        return w

    def _refresh_profile_file_list(self):
        self.cb_profile_file.clear()
        for name in _list_profile_files():
            self.cb_profile_file.addItem(name)

    def _populate_profile_editor(self, profile):
        self.le_profile_name.setText(profile.get('name', ''))
        self.sp_profile_avg.setValue(profile.get('averages', 32))
        bands = sorted(profile['bands'], key=lambda b: b['delays_us'][0])
        self.tbl_profile_bands.blockSignals(True)
        self.tbl_profile_bands.setRowCount(len(bands))
        for r, b in enumerate(bands):
            delays_str = ', '.join('{0:.2f}'.format(d) for d in b['delays_us'])
            thresh_str = (', '.join('{0:.2f}'.format(v) for v in b['threshold_v'])
                          if b.get('threshold_v') else '')
            for col, text in enumerate(
                    [str(b['freq_hz']), str(b['pulse_us']), delays_str, thresh_str]):
                self.tbl_profile_bands.setItem(r, col, QTableWidgetItem(text))
        self.tbl_profile_bands.blockSignals(False)
        self._validate_profile_editor()

    def _on_load_profile_file(self):
        name = self.cb_profile_file.currentText()
        if not name:
            return
        try:
            profile = _load_profile_file(name)
        except Exception as e:
            self.statusBar().showMessage('Load failed: {0}'.format(e))
            return
        self._populate_profile_editor(profile)
        self.statusBar().showMessage('Loaded profile: {0}'.format(name))

    def _on_save_profile_file(self):
        name = self.le_profile_name.text().strip()
        if not name:
            self.statusBar().showMessage('Enter a profile name before saving')
            return
        self._save_current_editor_as(name)

    def _on_save_profile_file_as(self):
        name, ok = QInputDialog.getText(self, 'Save Profile As', 'Profile name:')
        if not ok or not name.strip():
            return
        self.le_profile_name.setText(name.strip())
        self._save_current_editor_as(name.strip())

    def _save_current_editor_as(self, name):
        profile = self._validate_profile_editor()
        if profile is None:
            self.statusBar().showMessage('Cannot save: profile has validation errors')
            return
        profile['name'] = name
        _save_profile_file(name, profile)
        self._refresh_profile_file_list()
        idx = self.cb_profile_file.findText(name)
        if idx >= 0:
            self.cb_profile_file.setCurrentIndex(idx)
        self.statusBar().showMessage('Saved profile: {0}'.format(name))

    def _on_add_band_row(self):
        r = self.tbl_profile_bands.rowCount()
        self.tbl_profile_bands.insertRow(r)
        for col, text in enumerate(['10000', '10.0', '', '']):
            self.tbl_profile_bands.setItem(r, col, QTableWidgetItem(text))

    def _on_remove_band_row(self):
        r = self.tbl_profile_bands.currentRow()
        if r >= 0:
            self.tbl_profile_bands.removeRow(r)
        self._validate_profile_editor()

    def _on_profile_table_changed(self, *_args):
        self._validate_profile_editor()

    def _read_profile_from_editor(self):
        """Parse the band table into a profile dict. Returns (profile, error_str)."""
        rows = self.tbl_profile_bands.rowCount()
        if rows == 0:
            return None, 'no bands defined'
        bands = []
        n_delays = None
        for r in range(rows):
            freq_item   = self.tbl_profile_bands.item(r, 0)
            pulse_item  = self.tbl_profile_bands.item(r, 1)
            delays_item = self.tbl_profile_bands.item(r, 2)
            thresh_item = self.tbl_profile_bands.item(r, 3)
            try:
                freq_hz   = int(float(freq_item.text()))
                pulse_us  = float(pulse_item.text())
                delays_us = [float(x) for x in delays_item.text().split(',') if x.strip()]
            except (ValueError, AttributeError):
                return None, 'band {0}: invalid freq/pulse/delays'.format(r)
            if not delays_us:
                return None, 'band {0}: no delays'.format(r)
            if n_delays is None:
                n_delays = len(delays_us)
            elif len(delays_us) != n_delays:
                return None, ('band {0} has {1} delays, expected {2} '
                              '(rectangular only)').format(r, len(delays_us), n_delays)
            band = {'freq_hz': freq_hz, 'pulse_us': pulse_us, 'delays_us': delays_us}
            thresh_text = thresh_item.text().strip() if thresh_item else ''
            if thresh_text:
                try:
                    thresh_v = [float(x) for x in thresh_text.split(',') if x.strip()]
                except ValueError:
                    return None, 'band {0}: invalid threshold list'.format(r)
                if len(thresh_v) != n_delays:
                    return None, 'band {0}: threshold count must match delay count'.format(r)
                band['threshold_v'] = thresh_v
            bands.append(band)
        profile = {
            'name': self.le_profile_name.text().strip() or 'DYNAMIC',
            'averages': self.sp_profile_avg.value(),
            'bands': bands,
        }
        return profile, None

    def _validate_profile_editor(self):
        profile, error = self._read_profile_from_editor()
        if error:
            self.lbl_profile_validation.setText('✗ {0}'.format(error))
            self.lbl_profile_validation.setStyleSheet('color: red;')
            self.le_profile_command.setText('')
            self.pb_send_run.setEnabled(False)
            return None
        n_bands = len(profile['bands'])
        n_cells = len(profile['bands'][0]['delays_us'])
        self.lbl_profile_validation.setText('✓ {0} bands × {1} cells'.format(n_bands, n_cells))
        self.lbl_profile_validation.setStyleSheet('color: green;')
        self.le_profile_command.setText(self._build_d_command(profile))
        self.pb_send_run.setEnabled(True)
        return profile

    def _build_d_command(self, profile):
        parts = ['D{0}'.format(profile['averages'])]
        for b in profile['bands']:
            fields = [str(b['freq_hz']), str(b['pulse_us'])]
            fields += ['{0:.3f}'.format(d) for d in b['delays_us']]
            parts.append(','.join(fields))
        return ';'.join(parts)

    def _on_send_run_profile(self):
        profile = self._validate_profile_editor()
        if profile is None:
            return
        if not self.serial.isOpen():
            self.statusBar().showMessage('Not connected')
            return
        cmd = self._build_d_command(profile)
        self.send_command('E')
        self.send_command(cmd)
        self.send_command('Q{0}'.format(DYNAMIC_PROFILE_INDEX))
        self.send_command('G')
        self._apply_profile(profile, DYNAMIC_PROFILE_INDEX)
        self.pb_start.setText('Running')
        self.pb_start.setStyleSheet(self.MY_GREEN)
        self.statusBar().showMessage('Dynamic profile sent and running: {0}'.format(
            profile['name']))

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
        while self.serial.canReadLine():
            raw = self.serial.readLine().data().decode('utf-8', errors='replace').rstrip()
            if raw:
                self.process_packet(raw)

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

        if self._recording:
            self._record_buf.append((fw_time_ms, now, raw.copy()))

        if self._capturing:
            self._capture_buf.append(raw.copy())
            n = len(self._capture_buf)
            self.pb_capture.setText('Capturing {0}/{1}…'.format(n, self._capture_n))
            if n >= self._capture_n:
                self._finalise_capture()

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

    # ------------------------------------------------------------------
    # Display computation (heatmap)
    # ------------------------------------------------------------------
    def _compute_display_matrix(self, raw_nxn, mean, std):
        if self._display_mode == 'raw':
            return raw_nxn.copy()
        if mean is None:
            return np.zeros((self._n_bands, self._n_cells))
        delta = raw_nxn - mean
        if self._display_mode == 'delta':
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

        if self._display_mode == 'raw':
            self.img.setColorMap(self.cm_seq)
            self.img.setImage(matrix.T, levels=(0.0, float(matrix.max()) * 1.05 + 1.0))
            self.lbl_scale.setText('Scale: 0…{0:.0f} mV'.format(matrix.max() / 1000))
        else:
            self.img.setColorMap(self.cm_div)
            self.img.setImage(matrix.T, levels=(-lim, lim))
            unit = 'σ' if self._display_mode == 'z' else 'mV'
            val  = lim if self._display_mode == 'z' else lim / 1000
            self.lbl_scale.setText('Scale: ±{0:.2f} {1}'.format(val, unit))

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
                self.tbl_stats.item(row, 5).setText('{0:.2f}'.format(stds[proto_ch] / 1000.0))

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
            self._recording = True
            self._record_buf = []
            self.pb_record.setText('■ 0 frames')
            self.pb_record.setStyleSheet(self.MY_RED)
        else:
            self._recording = False
            self.pb_record.setText('Record Frames')
            self.pb_record.setStyleSheet(self.MY_YELLOW)
            self._save_frames_csv_auto()

    def _save_frames_csv_auto(self):
        if not self._record_buf:
            self.statusBar().showMessage('Record stopped — no frames to save.')
            return
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir,
            'frames_{0}.csv'.format(datetime.now().strftime('%Y%m%d_%H%M%S')))
        headers = ['fw_time_ms', 'wall_time_s'] + \
                  ['ch{0}_uV'.format(i) for i in range(self._n_channels)]
        with open(path, 'w') as f:
            f.write(','.join(headers) + '\n')
            for fw_t, wall_t, raw in self._record_buf:
                row = [str(fw_t), '{0:.4f}'.format(wall_t)] + \
                      [str(int(v)) for v in raw]
                f.write(','.join(row) + '\n')
        self.statusBar().showMessage(
            'Frames saved: {0}  ({1} rows)'.format(path, len(self._record_buf)))

    # ------------------------------------------------------------------
    # Redraw (30 Hz timer)
    # ------------------------------------------------------------------
    def _redraw(self):
        if self._recording:
            self.pb_record.setText('■ {0} frames'.format(len(self._record_buf)))

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
                parts.append('B{0}:{1}↔{2:.2f}V'.format(b, pol, thresh_v))
            elif cross is not None:
                parts.append('B{0}:{1}↔cell{2:.2f}'.format(b, pol, cross))
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
        self._display_mode = ('delta', 'z', 'raw')[idx]

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
                    'Band {0} ({1}) | Cell {2} ({3}) | delay = {4:.2f} µs'.format(
                        cy, self._display_band_labels[cy], cx, self._cell_labels[cx], delay_us))
                return
        self._update_status()

    def _update_status(self):
        self.statusBar().showMessage(
            'Frames: {0}  Cmd: {1:<6}  Last: {2}'.format(
                self._frame_count, self._last_cmd, self._last_packet[:60]))

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
        }
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, 'w') as f:
                json.dump(s, f, indent=2)
        except OSError:
            pass

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
