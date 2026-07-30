# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
###############################################################################
# PIMD Signature Visualiser (ClassViz) v1.63
# — Mode 2 adaptive profile viewer
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# Connects to the board, sends Q4/G to start Mode 2 streaming with the default
# CLASSIFY_EP profile, and displays a heatmap of signed cell deviations from a
# captured air baseline. Signature-corpus capture lives on the Analysis tab
# (its Training group runs the automated auto-detect air/target/air cycle and
# writes the corpus CSV), alongside a top-bar saved-profile selector to load/send
# a band/pulse/delay profile to the board as a RAM-only "dynamic" profile
# (firmware D command) without reflashing — the heatmap/stats table resize to
# match whatever profile (static or dynamic) is active. Profile authoring/saving
# lives in pimd_delaycal.py; ClassViz only loads and runs.
#
# Protocol: receives W<profile_idx>,<time_ms>,<ch0>,...,<chN-1>
# Board firmware: pimd_mcu.py v4.23+
#
# History (full detail in CHANGELOG.md):
#   v1.66 session dump: pack_v carries age_s; new '# soak:' run/idle history lines
#   v1.65 FIX corpus append wrote the tool's columns, not the file's (ragged CSV)
#   v1.64 window span guard; stream-stall detection; pack voltage; chart pause
#   v1.63 session logging auto-starts with the stream; Session Start adopts a running log
#   v1.62 FIX repeat_idx stuck at r1 (re-suggest after reload; normalise the placement key)
#   v1.61 signature list rows carry long axis + repeat; colour is per target
#   v1.60 remove the face_normal / offset X / offset Y capture inputs (schema unchanged)
#   v1.57 show the central-frame count that survives the trim; Frames default 60 -> 100
#   v1.56 Training A/B labels name the gate holding each phase up (σ/Δ vs threshold)
#   v1.55 lift the v1.41 manual latch: Space-forced placements auto-detect removal too
#   v1.54 FIX removal auto-detect: transient + fresh target ref; Air age = cycle budget
#   v1.53 auto-connect + run the last profile at launch; gauge row spacing; np.bool_ warning
#   v1.52 FIX Detect gauge read a stale air reference; Air age gauge; readout under the label
#   v1.51 Analysis Trigger Levels gauges (Settle/Detect/Amp/SNR) with draggable thresholds
#   v1.50 below-gate frames leave no trail at all; the trail is green by construction
#   v1.49 FIX custom band pair lost on restart (clamped by the startup profile's narrower spin range)
#   v1.48 Family Plane: no gridlines on a rank axis; the zero rails follow the spacing curve
#   v1.47 Family Plane per-axis Scale combo (expand-ends / rank spacing; no log, it is backwards here)
#   v1.46 scratch saves plot immediately (own template source) and draw as triangles
#   v1.45 FIX heatmap colorbar handles now mark Min/Max; live shape cursor/trail green above SNR gate
#   v1.44 Analysis heatmap manual scale is an explicit Min/Max; signature dialogs remember their directory
#   v1.43 Shape Space renamed Family Plane Analysis; material tags, per-axis custom bands, ladder click
#   v1.42 new Shape Space tab (feature-space scatter + docks) + scratch captures
#   v1.41 FIX Space-forced target placement skipped the removal wait (auto-detect latch)
#   v1.40 FIX capture_id reuse after a delete silently merged later saves into an existing capture
#   v1.39 remove the Training Session tab (all capture now via the Analysis tab Training group)
#   v1.38 Analysis: shrinkable heatmap split, auto-check new sigs, black live traces, quality colouring
#   v1.37 FIX Load signatures / Open for editing rejected the app's own v1.32+ files (schema dispatch)
#   v1.36 persist Saved-profile / Saved-list selectors, Stats Std thresholds, Training settle window
#   v1.35 training status labels name air/target; place/remove countdown flashes (red <5 s) + beeps
#   v1.34 training auto-detect cycle (auto place/remove, 30 s countdowns, Save/Ignore, rolling air reuse)
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
import zlib
from datetime import datetime, date, timedelta
from collections import Counter, deque

import numpy as np

os.environ.setdefault('QT_API', 'pyqt6')

from PyQt6.QtCore import QEvent, QIODevice, QTimer, Qt  # noqa: E402
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QPixmap  # noqa: E402
from PyQt6.QtSerialPort import QSerialPort  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QSplitter, QStackedWidget, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import pyqtgraph as pg  # noqa: E402
from pyqtgraph.dockarea import Dock, DockArea  # noqa: E402 — Shape Space tab layout

try:
    import pyqtgraph.opengl as gl
    _GL_AVAILABLE = True
except ImportError:
    _GL_AVAILABLE = False

import pimd_corpus_check  # noqa: E402 — Analysis tab signature-overlay loader
import pimd_features       # noqa: E402 — Analysis tab signature capture/save
import pimd_shape          # noqa: E402 — Shape Space tab feature maths (no Qt in that module)
import pimd_target_check        # noqa: E402 — target registry, shared with pimd_features

APP_VERSION = '1.66'

REDRAW_MS   = 33    # ~30 Hz

# Gap between the auto-start connect and the profile send, so the board has
# answered the E/V/Q4 handshake before the D/Q/G burst arrives -- the same beat
# an operator leaves between clicking Connect and Load & Run.
AUTOSTART_PROFILE_MS = 600

# Assumed seconds per W-frame when no measured rate is available yet (the
# _fps_hz readout needs a second of streaming first). ~3.3 Hz is the 63-cell
# sweep -- the same figure behind "a 50-frame window is 15 s at the sweep rate".
SWEEP_PERIOD_FALLBACK_S = 0.3

# Smallest Training "Frames" value whose central 60% still clears
# MIN_CENTRAL_FRAMES, so a full window is not stamped 'short' by
# quality_flags(). pimd_features trims 20% off each end of every plateau
# (CENTRAL_FRACTION) before taking stats, so only 60 of 100 frames feed them.
# This used to default to MIN_CENTRAL_FRAMES itself -- 60 frames, trimmed to 36
# central, which is BELOW the 60 the flag tests against, so a default-Frames
# capture was stamped 'short' every time (v1.57). Same expression the Family
# Plane scratch capture has sized its window with since v1.46.
SIG_CAPTURE_N_DEFAULT = int(math.ceil(
    pimd_features.MIN_CENTRAL_FRAMES / pimd_features.CENTRAL_FRACTION))   # 100

# -- Analysis heatmap colorbar-as-range-slider (v1.45) ----------------------
# ColorBarItem's internal coordinate space is a fixed 0..256 across the bar,
# independent of the levels on its axis.
CBAR_SPAN = 256.0
# The bar's axis shows a *domain* wider than the Min/Max window, so the handles
# have room to travel outwards as well as in. The domain is the union of the
# window and the data actually on screen -- but never so wide that the window
# shrinks below this fraction of the bar, or a tight window on a wide-ranging
# field (Δ mode reaches ~500000 µV) becomes an unreadable sliver.
CBAR_MIN_WINDOW_FRAC = 0.5
# ...and never so narrow that the handles end up pinned on the bar's two ends
# with nowhere to be dragged outwards to, which is what happens whenever the
# window already contains all the data.
CBAR_MAX_WINDOW_FRAC = 0.9

DEFAULT_PROFILE_IDX   = 4   # static CLASSIFY_EP — sent automatically on connect
DYNAMIC_PROFILE_INDEX = 5   # must match firmware's NUM_PROFILES (pimd_mcu.py v4.07+)

CAPTURE_FRAMES_DEFAULT = 64
ROLLING_SECS_DEFAULT   = 3.0
DEFAULT_PORT = '/dev/ttyACM0'

PROFILES_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'profiles')
SESSIONS_DIR       = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'sessions')
CORPORA_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'corpora')
# Shape Space scratch captures -- deliberately NOT data/corpora/: those ids are
# unregistered, and pimd_features' corpus build hard-errors on an unknown
# target_id. That guard is intentional; a scratch object gets promoted by
# registering it in targets_v1.csv and recapturing it properly.
SCRATCH_DIR        = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'scratch')
TARGETS_REGISTRY_PATH = pimd_target_check.DEFAULT_REGISTRY_PATH   # single source of truth
SUPPLY_CHOICES = ['battery', 'psu']
SCRATCH_ID_PREFIX = 'scratch_'
SCRATCH_MEDIA = ['air', 'soil', 'sand', 'water', 'other']

# -- Family Plane Analysis tab ---------------------------------------------
# Tab name (v1.43; was "Shape Space"). Held as a constant because it prefixes
# every status-bar line this tab emits.
SHAPE_TAB_TITLE = 'Family Plane Analysis'
# (key, menu label). 'custom' reads the control bar's band-range spin pair
# for that axis (X and Y have their own pair, so custom-vs-custom is a real
# plane and not the identity diagonal); everything else is a fixed pimd_shape
# feature. Used for both axis combos and, with SHAPE_COLOUR_EXTRA appended,
# the Colour-by combo.
SHAPE_AXES = [
    ('early',    'early mean'),
    ('mid',      'mid mean'),
    ('late',     'late mean'),
    ('custom',   'custom band range'),
    ('crossing', 'crossing µs (log)'),
    ('decay',    'decay persistence'),
    ('log_amp',  'log₁₀ amplitude'),
]
SHAPE_COLOUR_EXTRA = [('family', 'family'), ('distance', 'distance'), ('none', 'none')]
# Per-axis spacing curves (v1.47). The family-plane axes are band-range means of
# a UNIT shape, so they are hard-bounded at +/- 1/sqrt(k * n_delays) -- +/-0.1925
# for 3 of 7 bands -- and the corpus reaches 83% of that ceiling. Both families
# therefore pile up against opposite walls with the family decision boundary as
# an empty band between them: on the 2026-07-23 corpus the middle 48% of the Y
# axis holds nothing while each cluster is squeezed into 8-31%.
#
# There is deliberately NO log option. Log expands near zero and compresses at
# the extremes, which is backwards here -- measured, it drives the dead middle
# from 48% to 85%. These curves expand near the ENDS instead (measured on the
# same corpus: cube 15% dead, atanh 14%, rank 2%).
SHAPE_SCALES = [
    ('linear', 'Linear'),
    ('cube',   'Expand ends (cube)'),
    ('atanh',  'Expand ends (atanh)'),
    ('rank',   'Rank'),
]
# atanh(0.999) -- the normaliser that keeps the 'atanh' curve inside [-1, 1].
SHAPE_ATANH_K = math.atanh(0.999)
# Axes whose values are pulse widths in µs -- plotted as log10 with the
# profile's own pulse ladder as ticks (see _shape_axis_ticks). pyqtgraph's
# PlotItem.setLogMode only transforms PlotDataItems, not the bare
# ScatterPlotItems this tab draws, so the log transform is done on the values.
SHAPE_LOG_US_AXES = ('crossing',)
# Axes that are signed band-range means of the unit shape, so 0 is the
# meaningful "no signal" origin. While the air reference is rolling the live
# dot is pinned there rather than drawn at its computed position: the residual
# is ~0 in magnitude but its unit shape still has a definite direction (the
# reference's half-window drift lag), which parks the dot at a consistent
# off-centre spot -- measured, right inside the non-ferrous cluster. On the
# other axes 0 is not the origin of anything, so the dot is hidden instead.
SHAPE_CENTRED_AXES = ('early', 'mid', 'late', 'custom')

SHAPE_FAMILY_COLOURS = {
    'non_ferrous':      '#1f77b4',
    'crossover':        '#9467bd',
    'ferrous':          '#d62728',
    pimd_shape.LOW_SNR: '#999999',
}

# material_class / plating_material -> short tag drawn beside a point. Chemical
# symbols where one exists, so the plane reads as chemistry rather than as
# registry strings; alloys get a 3-letter contraction. Keys are exactly the
# registry's material_class vocabulary (pimd_target_check.DENSITY_G_PER_CM3)
# plus the plating materials that appear only in plating_material/substrate.
# An unlisted material falls back to Title-cased first 3 letters — a new
# registry material shows up as a readable guess, not as '?'.
SHAPE_MATERIAL_ABBREV = {
    'aluminium':    'Al',
    'brass':        'Brs',
    'cast_iron':    'CI',
    'chrome':       'Cr',
    'copper':       'Cu',
    'cu_alloy':     'CuA',
    'ferrite':      'Frt',
    'gold':         'Au',
    'lead':         'Pb',
    'ndfeb':        'NdFe',
    'nickel':       'Ni',
    'silver':       'Ag',
    'solder_sn_pb': 'SnPb',
    'stainless':    'SS',
    'steel':        'Fe',
    'tin':          'Sn',
    'zinc':         'Zn',
}
# Above this many drawn captures the per-point material tags are suppressed:
# past ~200 the text is denser than the points it annotates and the plane
# becomes unreadable. The checkbox still reads checked -- the tags come back
# on their own once the drawn set shrinks (a gate change, a different file).
SHAPE_LABEL_MAX = 200
SHAPE_GATE_DEFAULT  = pimd_shape.DEFAULT_SNR_GATE
SHAPE_TRAIL_DEFAULT = 30
SHAPE_TRAIL_MAX     = 500   # deque cap; the spinbox slices the last N of it
# Air-reference age beyond which the gauge reads amber. Far shorter than a
# static baseline's 600 s would suggest: at the DESIGN §3 drift rate a 60 s-old
# locked reference has already accumulated ~1 mV/cell, the same order as a weak
# target, so a lock older than this is worth re-arming before trusting.
SHAPE_AIR_AMBER_S   = 60.0
# Air-buffer frames. Deliberately much shorter than the Analysis tab's
# capture-window default (120): that window is for a stationary corpus capture
# bracketed by air on BOTH sides, where length buys noise. A rolling reference
# is single-ended, so its median sits half a window in the PAST and that lag is
# baked straight into every measurement as drift. Measured against a spanner @
# 60 mm on a drifting air simulation, family read correctly out to a 15 s hold
# at 20-40 frames and was already wrong at 5 s by 80-120 frames.
SHAPE_AIR_N_DEFAULT      = 40
# Live/settle window, frames. Much shorter than the Stats tab's 50: the settle
# metric only reads "settled" once the whole window sits inside one state, so a
# 50-frame window means a target does not register for a whole window — by which
# time drift has already spoiled the reading. The split-half noise floor over 15
# frames is still ~0.5 mV against a 39 mV target at 60 mm.
#   Sweep rate, measured (v1.64): 6.9 Hz under cal_63_air_bat_v3, so 50 frames is
#   ≈7.2 s and 15 frames ≈2.2 s. Earlier comments here quoted ~3.3 Hz / 15 s for
#   the 50-frame window; that was never re-measured after the profile changed and
#   is off by ~2×. Nothing derives timing from those numbers — they were prose —
#   but they are what made the frame-count window look time-bounded when it is not
#   (see _window_frames).
SHAPE_WIN_N_DEFAULT      = 15
# Span guard on every frame-count window (v1.64). A window of N frames is only a
# window of time if frames keep arriving; when the host stalls, N frames can span
# minutes and the per-channel σ over them reads accumulated DRIFT as noise. On
# 2026-07-29 23:03-23:50 a host stall (fw v4.27 now counts these MCU-side) made a
# 50-frame window span ~100 s instead of 7.2 s and inflated `settle` ~6×, which
# read on-screen as a noise relapse that did not happen. Any window spanning more
# than this multiple of its expected duration is refused rather than reduced, so a
# stall fails safe to "not settled" instead of to a plausible-looking number.
WINDOW_SPAN_TOLERANCE = 3.0
# Frames used to estimate the nominal frame period for that guard, from the
# FIRMWARE clock (_fw_ms_buf -- arrival time is burst-batched and cannot measure a
# frame period; see that attribute). The MEDIAN is the right estimator and the
# reason is the stall itself: through the whole 47-minute event 87% of firmware
# intervals were still a healthy 0.144 s (the MCU emitted short bursts of
# consecutive frames) and only 13% were the long gaps, so the median holds at
# nominal while the window span blows out. A mean, or the live 1 s rate, would
# rise or collapse with the stream and the guard would never trip.
WINDOW_NOMINAL_SAMPLE_N = 500
WINDOW_NOMINAL_MIN_N    = 20    # below this, no nominal is established and the
                                # guard stays off (stream start must not read stalled)
# A gap in FIRMWARE time this long counts as a stall worth recording (v1.64).
# 2 s is ~14 nominal frames at the measured 6.9 Hz -- well clear of ordinary
# scheduling jitter (p99 of healthy intervals on 2026-07-29 was 0.180 s) while
# still catching every one of the 222 gaps in that session's stall window.
FRAME_GAP_WARN_S = 2.0
# Nag interval for a fresh pack-voltage reading while recording (v1.64), seconds.
PACK_V_REMIND_S = 20 * 60
# How often a '# soak:' line is written while streaming (v1.66), seconds.
SOAK_EMIT_S = 60
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


pg.setConfigOptions(background='w', foreground='k', antialias=True)

# Highlight colours, as bare rgb() strings so both the widget stylesheets
# (MainWindow.MY_GREEN/YELLOW/RED, built from these) and the per-field <span>
# backgrounds in the signature readout draw from one definition.
_HL_GREEN  = 'rgb(143, 240, 164)'
_HL_YELLOW = 'rgb(249, 240, 107)'
_HL_RED    = 'rgb(246,  97,  81)'
_HL_BLUE   = 'rgb(153, 193, 241)'

_R = int(Qt.AlignmentFlag.AlignRight) | int(Qt.AlignmentFlag.AlignVCenter)
_C = int(Qt.AlignmentFlag.AlignCenter)


# Value <-> bar-axis transforms for a gauge's draggable threshold marker.
# Every gauge but the amplitude one plots the setting directly; that one plots
# log₁₀ of it, so a dragged position has to come back through _pow10_axis
# before it reaches the spinbox. Named functions rather than lambdas so a
# traceback through a marker drag says which transform it was in.
def _identity(x):
    return x


def _log10_axis(x):
    return math.log10(max(x, 1e-3))


def _pow10_axis(x):
    return 10.0 ** x


def _hl_qcolor(css_rgb):
    """QColor from one of the _HL_* 'rgb(r, g, b)' strings above. Those are
    CSS -- fine for stylesheets and <span> backgrounds, but pyqtgraph's
    mkBrush/mkColor rejects them. Parsed here rather than duplicated as hex
    literals so the colours still have exactly one definition."""
    body = css_rgb[css_rgb.index('(') + 1:css_rgb.index(')')]
    return QColor(*(int(v) for v in body.split(',')))


def _hl_ink(css_rgb):
    """Same hue, darkened for use as a STROKE. The _HL_* colours are
    backgrounds -- _HL_YELLOW is a pale rgb(249,240,107) that reads well as a
    fill behind dark text but is close to invisible as a 2 px line on
    pyqtgraph's white canvas. Derived rather than hard-coded so the fill and
    the stroke stay the same colour."""
    return _hl_qcolor(css_rgb).darker(160)


def _fmt(uv):
    """µV → mV string with 3 d.p."""
    return '{0:.3f}'.format(uv / 1000.0)


def _csv_default_path():
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    return os.path.join(data_dir, 'signatures_{0}.csv'.format(date.today().strftime('%Y%m%d')))


class ScratchDialog(QDialog):
    """Save Scratch… — the small form behind a quick capture of an
    unregistered object. Deliberately not the Analysis tab's structured
    placement widget set: a scratch object has no registry row, so `long_axis`
    has no dim_a to point along and is written 'na' rather than invented.
    (face_normal and the offsets stopped being inputs anywhere at v1.60, so
    they are no longer part of the distinction.)"""

    def __init__(self, parent, air2_available, default_distance_mm=50):
        super().__init__(parent)
        self.setWindowTitle('Save scratch capture')
        form = QFormLayout(self)

        self.le_label = QLineEdit()
        self.le_label.setPlaceholderText('e.g. rusty hinge')
        form.addRow('Label (required):', self.le_label)

        self.le_note = QLineEdit()
        form.addRow('Note:', self.le_note)

        self.cb_no_distance = QCheckBox('unknown / not measured')
        self.sp_distance = QSpinBox()
        self.sp_distance.setRange(0, 2000)
        self.sp_distance.setValue(int(default_distance_mm))
        self.sp_distance.setSuffix(' mm')
        self.cb_no_distance.toggled.connect(lambda on: self.sp_distance.setEnabled(not on))
        dist_row = QHBoxLayout()
        dist_row.addWidget(self.sp_distance)
        dist_row.addWidget(self.cb_no_distance)
        form.addRow('Distance:', dist_row)

        self.cb_medium = QComboBox()
        self.cb_medium.addItems(SCRATCH_MEDIA)
        form.addRow('Medium:', self.cb_medium)

        self.cb_anchor = QComboBox()
        self.cb_anchor.addItem('static baseline (flat, quick)', 'flat')
        self.cb_anchor.addItem('last training capture (air/target/air)', 'air2')
        if not air2_available:
            # Disabled rather than hidden: the option is real, it just needs a
            # completed Analysis-tab cycle, and saying so is more useful than
            # silently offering one choice.
            model_item = self.cb_anchor.model().item(1)
            if model_item is not None:
                model_item.setEnabled(False)
            self.cb_anchor.setToolTip(
                'Two-anchor (drift-corrected) capture needs a completed, unsaved '
                'Training cycle on the Analysis tab.')
        form.addRow('Air anchor:', self.cb_anchor)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                    QDialogButtonBox.StandardButton.Cancel)
        self._save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self._save_button.setEnabled(False)
        self.le_label.textChanged.connect(
            lambda text: self._save_button.setEnabled(bool(text.strip())))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return {
            'label': self.le_label.text().strip(),
            'note': self.le_note.text().strip(),
            'distance_mm': None if self.cb_no_distance.isChecked() else self.sp_distance.value(),
            'medium': self.cb_medium.currentText(),
            'anchor': self.cb_anchor.currentData(),
        }


class MainWindow(QMainWindow):
    MY_GREEN  = 'background-color: {0};'.format(_HL_GREEN)
    MY_YELLOW = 'background-color: {0};'.format(_HL_YELLOW)
    MY_RED    = 'background-color: {0};'.format(_HL_RED)
    MY_BLUE   = 'background-color: {0};'.format(_HL_BLUE)

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
        # Firmware frame clock for the same frames, appended in lockstep with
        # _rolling_buf and with the same maxlen so index -k aligns in both
        # (v1.64). Kept as a parallel deque rather than widening _rolling_buf's
        # tuple, which many consumers unpack as (ts, arr).
        #
        # It exists because _rolling_buf's timestamp is PC ARRIVAL time, and
        # arrival is burst-batched: read_from_serial() drains several lines per
        # readyRead and stamps them microseconds apart. Measured over all 114k
        # frames of the 2026-07-29 dump, arrival intervals are bimodal -- median
        # 0.0035 s with 57% of them under 10 ms, against p90 0.444 s -- while the
        # firmware clock is uniform at median 0.1440 s with NONE under 10 ms. Both
        # necessarily share the same mean (0.1683 s: same elapsed, same count),
        # which is the trap: an arrival-time mean looks right while its median is
        # 40x too small, and the median is what survives a stall. So arrival time
        # cannot measure how much TIME a window of frames covers, and the
        # firmware's own clock can. This is what the span guard measures against.
        # The degree of batching varies -- one 10k-frame stretch of that session
        # ran only 23% batched -- so this is not a fixed factor to correct for.
        self._fw_ms_buf: deque = deque(maxlen=10_000)
        self._rolling_T   = ROLLING_SECS_DEFAULT
        # v1.64 window-span guard state (see _window_frames). span/reason are
        # written on every window reduction and read only for display; the
        # nominal cache is keyed on _frame_count so it recomputes once a frame.
        self._window_span_s        = None
        self._window_block_reason  = None
        self._nominal_frame_cache  = (-1, None)
        # v1.64 stream-gap detection (see _note_frame_gap). Latched for the run:
        # the Rate readout is instantaneous and clears itself, which is no use
        # for an unattended session.
        self._last_fw_time_ms = None
        self._stall_count     = 0
        self._stall_worst_s   = 0.0
        self._stall_last_wall = None
        # v1.64 pack voltage. None means not measured (see _pack_v_value); the
        # persisted value is restored in _load_settings.
        self._pack_v           = None
        self._pack_v_last_wall = None
        self._pack_v_edited_wall = None    # v1.66: when the field was last TYPED
        # v1.66 soak history. The rig's thermal state depends on how long it has
        # actually been sweeping, not on wall-clock elapsed -- a stopped stream
        # cools it, and nothing recorded that. streamed_s accumulates ACROSS
        # stop/start rather than being (now - session_start).
        self._stall_total_s        = 0.0
        self._stream_run_start_wall = None   # wall time this streaming run began
        self._streamed_total_s     = 0.0     # completed runs, this session
        self._last_stream_stop_iso = None    # persisted; drives idle_before_s
        self._soak_last_emit_wall  = None
        # v1.64 per-chart draw pause (see _make_chart_pause_checkbox). Deliberately
        # NOT persisted: a chart that comes back frozen after a restart reads as a
        # bug, and the reason to pause is a condition of the run, not a preference.
        self._analysis_c2_paused = False
        self._analysis_g8_paused = False
        self._analysis_g9_paused = False

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

        # Pauses session *recording* (frame rows stop being written, marks are
        # refused) without closing the file. Driven by the Analysis tab's
        # Session Pause button; read by process_packet.
        self._session_paused: bool = False

        # Auto-logging (v1.63). A session dump opens by itself whenever the
        # stream starts, so a bench run can't silently go unrecorded -- the
        # 2026-07-29 session lost its whole profiling window and the 47-minute
        # pack settle before it that way, and raw stream is not recoverable
        # after the fact.
        #   _session_autolog            -- operator preference, persisted.
        #   _session_autolog_suppressed -- latched by an explicit Stop so "stop"
        #                                  means stop; cleared at the next
        #                                  stream start.
        #   _session_autostarted        -- the open file was auto-opened, so
        #                                  Session Start adopts it (adds notes)
        #                                  instead of refusing.
        #   _session_stop_is_forced     -- set by the programmatic force-stops
        #                                  (_apply_profile, start_stop) so
        #                                  _toggle_record_frames can tell them
        #                                  apart from an operator click.
        self._session_autolog            = True
        self._session_autolog_suppressed = False
        self._session_autostarted        = False
        self._session_stop_is_forced     = False

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
        # Manual scale is an explicit (min, max) pair, not a ± half-range
        # (v1.44). Std Dev is the case that forced it: a rolling σ field lives
        # in a narrow band well above zero, so a range anchored at 0 spends
        # most of the colour ramp on values that never occur.
        self._analysis_hm_manual_min_uv  = -200_000.0
        self._analysis_hm_manual_max_uv  = 200_000.0
        # Colorbar-as-range-slider state (v1.45). The bar's axis spans a domain
        # wider than the Min/Max window so the two handles have somewhere to sit
        # *and* somewhere to travel; frozen mid-drag so the value under the
        # cursor doesn't move while the window is being dragged.
        self._analysis_cbar_domain     = None  # (lo, hi) currently on the bar's axis
        self._analysis_cbar_data_range = None  # (lo, hi) of the matrix last drawn
        self._analysis_cbar_dragging   = False
        self._analysis_cbar_syncing    = False  # guards our own setRegion() calls

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
        # Directory the signature file dialogs open in, persisted across
        # sessions (v1.44). Corpora and scratch files live in several places
        # (src/data/corpora/, src/data/scratch/, ad-hoc directories for
        # another rig's captures), so re-navigating from the CWD on every
        # load was a per-session tax. Only the DIRECTORY is remembered -- a
        # remembered file path would be a stale pointer, which is the foot-gun
        # _load_settings' comment calls out for the editable-file path.
        self._last_sig_dir = CORPORA_DIR

        # Target registry (pimd_target_check.py) -- backs the Analysis tab's inline
        # capture widgets.
        self._targets        = {}    # dict[target_id -> pimd_target_check.Target]
        self._target_issues   = []

        # Analysis tab — automated auto-detect training cycle (v1.34). A
        # second, independent capture channel from _capturing/_capture_buf
        # (which stay hard-wired to the Heatmap tab's "Capture baseline"). One
        # Space press locks the leading air; target placement/removal are
        # auto-detected; the trailing air rolls straight into the next cycle's
        # leading air (same rolling deque).
        self._sig_capture_n    = SIG_CAPTURE_N_DEFAULT
        self._analysis_training_active = False
        # phase: 'air_lead' | 'await_target' | 'target' | 'await_remove' | 'air_trail'
        self._sig_train_phase  = 'air_lead'
        self._sig_train_status = 'settling'  # 'settling' | 'collecting' | 'ready' (collecting phases)
        self._sig_train_buf    = None        # deque(maxlen=N) of (ts, raw_uV.copy()); rolls in 'ready'
        self._sig_train_last_style = None    # stylesheet churn guard for the status label
        self._sig_glitch_skipped = 0    # glitch frames excluded from the current window (v1.31)
        self._sig_air_ref      = None   # np mV vector: median of the locked leading air (auto-detect ref)
        self._sig_air_ref_ts   = None   # wall time it was locked -- DESIGN §17.10 makes reference
                                        # AGE the ceiling on any frozen-reference measurement
        self._sig_await_deadline = None # wall-clock; 30 s guard for await_target/await_remove
        self._sig_removal_armed = False # a settle-loss has been seen during await_remove, so
                                        # the object has physically moved -- drift cannot set this
        self._sig_target_manual = False # placement was forced by Space, so auto-detect can't
                                        # see this target -- removal must be manual too (v1.41)
        self._sig_decide_pending = False  # a computed signature is awaiting Save/Ignore
        self._sig_decide_flash_on = False # flash phase for the Save/Ignore buttons
        self._sig_await_flash_on = False  # flash phase for the place/remove countdown (B)
        self._sig_air_before   = None   # {'t_seconds':(n,), 'frames_mV':(n,n_channels), 'n_frames':int}
        self._sig_air_after    = None   # same shape, optional
        self._sig_target       = None   # same shape
        self._sig_last_stats   = None   # cached dict from _compute_sig_stats(), for the live readout
        # (session, capture_id) keys saved during this app session (v1.38) --
        # they land *checked* in the signature list so a fresh capture is on
        # the charts immediately, without hunting for it. Only ever consulted
        # for a key's first appearance, so unticking one sticks. In-memory
        # only; cleared whenever a different editable file is started/opened.
        self._sig_autocheck_keys = set()

        self._SIG_AWAIT_SECONDS = 30.0  # place/remove-target guard countdown

        # Re-entry guard for the Trigger Levels gauges: a marker drag sets its
        # bound spinbox, whose valueChanged re-renders the column, which would
        # otherwise reposition the very line being dragged.
        self._gauge_marker_drag = False

        # Analysis tab — session recording (alternate path to the Stats tab's
        # Record Session button; drives the same _session_start/_session_stop/
        # _append_mark machinery and the _recording/_session_paused flags).
        self._analysis_session_recording = False

        # Shape Space tab — feature-space view of the SAME signature store the
        # Analysis tab loads into (self._analysis_templates); no second loader,
        # no second copy of the captures. Per-capture features are cached
        # because they only change when the store or the profile changes;
        # anything that depends on the control bar (the custom band range) is
        # derived at draw time from the cached unit shape instead.
        self._shape_feat_cache   = {}     # template key -> feature dict
        self._shape_selected_key = None   # clicked scatter point
        # role -> monotone spacing callable, or None for a plain linear axis.
        # Rebuilt from the drawn captures on every static redraw (v1.47).
        self._shape_scale_map    = None
        # role -> the custom band (lo, hi) the operator actually asked for, as
        # opposed to what the spinboxes are currently able to show (v1.49).
        # The spins are ranged to the LIVE profile, so a pair chosen under a
        # 7-band profile cannot even be represented while the app is still on
        # the 5-band startup profile -- setValue() would clamp it away and the
        # choice would be lost. None until settings load or an operator edit.
        self._shape_band_pref    = {'x': None, 'y': None}
        self._shape_live         = None   # feature dict for the current frame, or None
        # Live feature dicts, appended once per W frame in process_packet so
        # the trail is already populated when the tab is first shown. Only
        # gated frames go in -- below the gate the shape is normalised noise
        # and a trail would make it look like a real trajectory.
        self._shape_trail        = deque(maxlen=SHAPE_TRAIL_MAX)
        self._shape_geom_warned  = False  # one §11 geometry message per store load

        # Shape Space air reference — its OWN, deliberately not the shared
        # _get_current_baseline(). A one-shot static air capture cannot serve
        # this tab: thermal drift (DESIGN §3 ≈ −50 µV/s, §14.1 heavy bands
        # −20…−31 mV) accumulates into the delta as a large *coherent* term,
        # and the SNR gate cannot catch that by construction — splithalf is a
        # short-timescale scatter statistic, so drift inflates amp while
        # leaving splithalf flat. Simulated at the documented rate against a
        # fresh static baseline, coil in air, the frame reads SNR 8.6 after
        # 30 s and 67 after 4½ minutes: the dot goes confidently coloured and
        # wanders on nothing at all. Referencing recent air instead cancels
        # the drift, which is the same reason the Analysis tab's Training
        # cycle brackets every target with air (DESIGN §17.5).
        #
        # Two modes, and Space is the only thing that moves between them:
        #   'air'      every frame feeds the rolling buffer and the reference
        #              is its running median, so the live delta is ~0 by
        #              construction and the cursor sits at the origin.
        #   'measure'  the last 'frames' of air were snapshotted as a fixed
        #              reference; the cursor moves against it.
        # Nothing here auto-detects a target arriving or leaving — an earlier
        # revision did, and it is gone by direction.
        self._shape_air_mode   = 'air'
        self._shape_air_buf    = None    # deque(maxlen=Air frames) of mV frames
        self._shape_air_ref    = None    # np vector, mV
        self._shape_air_ref_ts = None    # wall time the reference was snapshotted

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

        # Auto-start (v1.53): reproduce the operator's own opening move --
        # Connect, then Load & Run whatever profile the dropdown remembers.
        # singleShot(0) rather than a direct call so the window is up and the
        # event loop running before any serial I/O; degrades to a status-bar
        # message and a normal idle app if there is no port or no profile.
        QTimer.singleShot(0, self._autostart)

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
        # Cells sorted threshold_v DESCENDING -- with _pulse_sort_order below,
        # this is what puts a live frame into pimd_shape's vector convention
        # (band-major, pulse ascending, thresholds high->low), the same order
        # the corpus rows are sorted into on save. Live and stored shapes are
        # only comparable because both go through these two reindexes.
        if self._has_threshold_v:
            thr = bands[0]['threshold_v']
            self._cell_sort_order = [int(j) for j in
                                      np.argsort([-float(v) for v in thr], kind='stable')]
            self._threshold_v_sorted = [float(thr[j]) for j in self._cell_sort_order]
        else:
            self._cell_sort_order = list(range(n_cells))
            self._threshold_v_sorted = [float('nan')] * n_cells
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
        was_recording = self._recording
        if self._recording:
            self._session_stop_is_forced = True   # not an operator Stop; don't suppress auto-log
            self.pb_record.setChecked(False)      # triggers _toggle_record_frames → auto-save
        self._rolling_buf.clear()
        self._fw_ms_buf.clear()      # v1.64: must stay index-aligned with the above
        self._baseline_mean = None
        self._baseline_std  = None
        self._baseline_age  = None
        self._latest_raw     = None
        self._frame_count    = 0
        self._ch_glitch_buf  = None
        self._ch_glitch_pos  = 0

        # Shape Space state is invalidated BEFORE anything redraws: the cached
        # features and the live trail were computed under the old geometry,
        # and _refresh_analysis_overlays() below reaches the Shape Space
        # panels, which would otherwise repopulate from the stale cache.
        if hasattr(self, 'shape_scatter'):
            self._shape_invalidate_features()
            self._shape_trail.clear()
            self._shape_live = None
            self._shape_selected_key = None
            self._shape_air_restart()   # old-geometry air reference is unusable

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
            self._refresh_analysis_overlays()  # tail-calls _shape_redraw_static()
        self.header_label.setText('Profile {0} — {1} ({2} bands × {3} cells)'.format(
            profile_idx, profile.get('name', '?'), self._n_bands, self._n_cells))

        # v1.63: the dump we just force-closed was headed with the *old*
        # profile_json/sha8, so continuing into it was never an option -- open
        # a fresh, correctly-headed one rather than leave the rest of the run
        # unlogged. Only if a recording was actually interrupted; a profile
        # change while idle stays idle. Last in the method so the new header is
        # written against the fully-applied profile.
        if was_recording:
            self._maybe_autostart_session('profile change')

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
        # Analysis-tab quick-capture save path and the session mark-writing
        # path.
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
        self._analysis_tab_index = self.tabs.addTab(self._build_analysis_tab(), 'Analysis')
        self._shape_tab_index = self.tabs.addTab(self._build_shape_tab(), SHAPE_TAB_TITLE)
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
        # This path sends its own 'G' rather than going through start_stop(), so
        # it has to arm auto-logging itself -- and it matters most here: it is
        # the v1.53 launch auto-start, i.e. the whole warm-up and settle window
        # before anyone presses anything. No double-open risk: if _apply_profile
        # above already reopened a dump, _maybe_autostart_session no-ops.
        self._session_autolog_suppressed = False
        self._maybe_autostart_session('profile load + run')
        self.statusBar().showMessage('Loaded and running profile: {0}'.format(
            profile.get('name', name)))

    # ------------------------------------------------------------------
    # Tab 2 — Analysis
    # ------------------------------------------------------------------
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

        # Left column: Controls + Signatures + Training above, Heatmap below,
        # sharing one width -- Signatures/Controls used to span the full tab
        # width above everything else; now they're grouped with the heatmap so
        # the right side (charts) can reach the top of the tab.
        #
        # The two halves are split (v1.38) rather than stacked with a fixed
        # heatmap stretch: the heatmap used to own a fixed share of the column
        # height regardless of how many signatures were loaded, so the
        # signature list stayed ~2 rows tall and was unusable for picking
        # overlays out of a 10+ capture corpus. The handle now trades heatmap
        # height for signature-list height, and the heatmap can be dragged
        # away entirely on a capture-only day.
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
        left_v.addWidget(self._build_analysis_signatures_group(), stretch=1)
        left_v.addWidget(self._build_analysis_training_group())

        left_split = QSplitter(Qt.Orientation.Vertical)
        left_split.setHandleWidth(4)
        left_split.addWidget(left_col)
        left_split.addWidget(self._build_analysis_heatmap_group())
        left_split.setStretchFactor(0, 1)
        left_split.setStretchFactor(1, 1)
        left_split.setSizes([620, 380])
        left_split.setCollapsible(0, False)   # capture controls must stay reachable
        left_split.setCollapsible(1, True)    # the heatmap may be dragged fully away
        self.analysis_left_split = left_split

        # Right column: row1 (trigger gauges | strips | chart2 side by side)
        # + 8-grid + 9-grid. The gauges sit leftmost and take no share of a
        # resize -- they are four fixed-height rows, so extra width is wasted
        # on them and wanted by the charts.
        row1_split = QSplitter(Qt.Orientation.Horizontal)
        row1_split.setHandleWidth(4)
        row1_split.addWidget(self._build_analysis_gauges_group())
        row1_split.addWidget(self._build_analysis_strips_group())
        row1_split.addWidget(self._build_analysis_chart2_group())
        row1_split.setSizes([300, 600, 600])
        row1_split.setStretchFactor(0, 0)
        row1_split.setCollapsible(0, True)
        self.analysis_row1_split = row1_split

        right_split = QSplitter(Qt.Orientation.Vertical)
        right_split.setHandleWidth(4)
        right_split.addWidget(row1_split)
        right_split.addWidget(self._build_analysis_grid8_group())
        right_split.addWidget(self._build_analysis_grid9_group())
        # Row 1 opens at 320 rather than the old 220: five 46 px gauge rows,
        # the 8 px gaps between them and the group title need ~290, and
        # anything less opens them squashed to their 26 px minimum. The handle
        # still trades it back for grid height, and analysis_row1_split_sizes
        # persists whatever you choose.
        right_split.setSizes([320, 210, 210])

        main_split = QSplitter(Qt.Orientation.Horizontal)
        main_split.setHandleWidth(4)
        main_split.addWidget(left_split)
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
        v.addWidget(self.lw_analysis_templates, stretch=1)
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

        # Changed from the original wrapped left-to-right "tag" flow --
        # labels now carry amp/SNR/quality text, so a normal scrollable
        # top-to-bottom list is more legible. It takes all the height the
        # left splitter gives it (v1.38): the old 46px *maximum* pinned it to
        # ~2 visible rows, which made a 10+ capture corpus unpickable; 46px is
        # now the floor instead, and the surplus comes out of the heatmap.
        self.lw_analysis_templates = QListWidget()
        self.lw_analysis_templates.setFlow(QListWidget.Flow.TopToBottom)
        self.lw_analysis_templates.setMinimumHeight(46)
        self.lw_analysis_templates.itemChanged.connect(self._on_analysis_template_item_changed)
        self.lw_analysis_templates.currentItemChanged.connect(lambda *_: self._update_sig_capture_gating())

    # -- Target/placement widget set (Analysis tab inline capture inputs) ----

    def _build_target_placement_widget_set(self, layout, prefix, emphasise_target=False):
        """Builds a target-registry combo + structured placement widgets into
        `layout`, storing them as self.{prefix}_target, {prefix}_distance_mm,
        {prefix}_long_axis, {prefix}_medium, {prefix}_repeat_idx. Pure
        construction -- caller wires signals and calls
        _populate_target_combo() to fill the target combo from the currently
        loaded registry. Kept as a separate builder (rather than inlined into
        its one caller) because the field set is the corpus schema's placement
        tuple -- it deserves one definition even with a single instantiation
        site. The second call site, the Training Session tab's per-row
        Placement dialog, went with that tab in v1.39.

        emphasise_target: bold/enlarge the Target label + combo (v1.38), where
        that one combo decides what every Save writes into the corpus and
        picking the wrong one silently mislabels a capture -- it shouldn't
        look like just another dropdown."""
        row_a = QHBoxLayout()
        lbl_target = QLabel('Target:')
        target_combo = QComboBox()
        target_combo.setMinimumWidth(220)
        if emphasise_target:
            emph_font = QFont()
            emph_font.setPointSize(12)
            emph_font.setBold(True)
            lbl_target.setFont(emph_font)
            target_combo.setFont(emph_font)
            target_combo.setMinimumWidth(300)
            target_combo.setMinimumHeight(30)
        row_a.addWidget(lbl_target)
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

        row_b.addWidget(QLabel('Medium:'))
        medium = QComboBox()
        medium.addItems(['air', 'soil', 'other'])
        setattr(self, '{0}_medium'.format(prefix), medium)
        row_b.addWidget(medium)

        # Repeat # shared row B with the offsets' row until v1.60 removed
        # those; on its own it did not earn a row of its own.
        repeat_tip = (
            'Provenance metadata only — distinguishes repeated captures of the '
            'same placement tuple (target, distance, long axis, medium) so '
            'they don\'t collide as one signature in the corpus CSV. '
            'Auto-suggested as count+1 from the open file\'s existing captures; '
            'editable. Not used in any matching/classification math.')
        lbl_repeat = QLabel('Repeat #:')
        lbl_repeat.setToolTip(repeat_tip)
        row_b.addWidget(lbl_repeat)
        repeat_idx = QSpinBox()
        repeat_idx.setRange(1, 999)
        repeat_idx.setValue(1)
        repeat_idx.setToolTip(repeat_tip)
        setattr(self, '{0}_repeat_idx'.format(prefix), repeat_idx)
        row_b.addWidget(repeat_idx)
        row_b.addStretch(1)
        layout.addLayout(row_b)

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
            # Not inputs since v1.60 -- they were never set, and face_normal
            # being a *persisted* combo meant a value chosen once silently
            # attached itself to every later capture (all 12 captures of a
            # tube in the v3 corpus carry face_normal=z, which is meaningless
            # for that shape). Still keys of this dict, so the CSV column, the
            # session dump's mark_target: line and the placement tuple are all
            # unchanged -- pimd_corpus_check.PLACEMENT_FIELDS still expects
            # them, and older corpora carry real values.
            'face_normal': 'na',
            'offset_x_mm': 0,
            'offset_y_mm': 0,
            'medium': getattr(self, '{0}_medium'.format(prefix)).currentText(),
            'repeat_idx': getattr(self, '{0}_repeat_idx'.format(prefix)).value(),
            # The Notes entry box was dropped in v1.38 (dead weight in the
            # capture flow -- nothing was being typed into it). The key and
            # the corpus 'notes' column stay, always empty, so build_rows()
            # and the session dump's mark_target: line are unchanged.
            'notes': '',
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
        Called once at UI-build time. The Analysis tab's "Reload targets"
        button was dropped in v1.38 -- the registry is a slow-moving reference
        file, so a mid-session reload was never worth a permanent control;
        restart ClassViz to pick up registry edits."""
        try:
            targets, issues = pimd_target_check.load_targets(TARGETS_REGISTRY_PATH)
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
                '-- see dialog / run pimd_target_check.py for detail'.format(
                    len(targets), len(errors), len(warnings)))
        elif warnings:
            self.statusBar().showMessage(
                'Target registry loaded: {0} target(s), {1} warning(s) (run '
                'pimd_target_check.py for detail)'.format(len(targets), len(warnings)))
        else:
            self.statusBar().showMessage('Target registry loaded: {0} target(s)'.format(len(targets)))
        self._repopulate_target_combos()

    def _repopulate_target_combos(self):
        if hasattr(self, 'sig_target'):
            current = self.sig_target.currentData()
            self._populate_target_combo(self.sig_target, selected_target_id=current)
        if hasattr(self, '_update_sig_capture_gating'):
            self._update_sig_capture_gating()

    def _build_sig_row2_capture_inputs(self, v):
        self._build_target_placement_widget_set(v, 'sig', emphasise_target=True)
        self.sig_target.currentIndexChanged.connect(self._update_sig_capture_gating)
        for widget, signal_name in (
            (self.sig_target, 'currentIndexChanged'), (self.sig_distance_mm, 'valueChanged'),
            (self.sig_long_axis, 'currentIndexChanged'),
            (self.sig_medium, 'currentIndexChanged'),
        ):
            getattr(widget, signal_name).connect(self._update_sig_repeat_idx_suggestion)

    def _build_analysis_training_group(self):
        """Training group (v1.34) — automated auto-detect capture cycle. One
        Space press per cycle locks the leading air; target placement and
        removal are auto-detected (settle + Detect threshold), with 30 s guard
        countdowns and a Save/Ignore decision. The settle gate, glitch
        exclusion and stats math (pimd_features) are unchanged from v1.33."""
        box = QGroupBox('Training')
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(2)

        # -- Row 1: Start/Stop, Frames, Settle, Detect, Space-override --------
        row1 = QHBoxLayout()
        self.pb_sig_train_start = QPushButton('Start Training')
        self.pb_sig_train_start.setCheckable(True)
        self.pb_sig_train_start.toggled.connect(self._on_sig_train_start_toggled)
        row1.addWidget(self.pb_sig_train_start)

        row1.addWidget(QLabel('Frames:'))
        self.sp_sig_capture_n = QSpinBox()
        self.sp_sig_capture_n.setRange(10, 2000)
        self.sp_sig_capture_n.setValue(self._sig_capture_n)
        self.sp_sig_capture_n.valueChanged.connect(self._update_sig_capture_n_warning)
        self._sig_capture_n_last_style = None
        self._update_sig_capture_n_warning(self.sp_sig_capture_n.value())
        row1.addWidget(self.sp_sig_capture_n)

        row1.addWidget(QLabel('Settle ≤ (mV):'))
        self.sp_sig_settle_mv = QDoubleSpinBox()
        self.sp_sig_settle_mv.setRange(0.05, 50.0)
        self.sp_sig_settle_mv.setDecimals(3)
        self.sp_sig_settle_mv.setSingleStep(0.1)
        self.sp_sig_settle_mv.setValue(1.0)
        self.sp_sig_settle_mv.setToolTip(
            'Settledness gate: collection only runs while the mean per-channel '
            'rolling std dev (over the Stats tab\'s "Std dev N" window) is at '
            'or below this, so '
            'target/air transitions and the firmware\'s ~10 s rolling-average '
            'ramp can\'t enter the window. Raise to 50 to disable.')
        row1.addWidget(self.sp_sig_settle_mv)

        row1.addWidget(QLabel('Detect ≥ (mV):'))
        self.sp_sig_detect_mv = QDoubleSpinBox()
        self.sp_sig_detect_mv.setRange(0.05, 50.0)
        self.sp_sig_detect_mv.setDecimals(3)
        self.sp_sig_detect_mv.setSingleStep(0.1)
        self.sp_sig_detect_mv.setValue(0.5)
        self.sp_sig_detect_mv.setToolTip(
            'Target auto-detect threshold. After the signal re-settles, a '
            'target is "present" when the mean per-channel |Δ| from the locked '
            'leading-air baseline exceeds this, and "removed" when it drops '
            'back below it. Raise for large/close targets, lower for small/'
            'distant ones.')
        row1.addWidget(self.sp_sig_detect_mv)

        self.cb_sig_train_override = QCheckBox('Space override')
        self.cb_sig_train_override.setChecked(True)
        self.cb_sig_train_override.setToolTip(
            'When checked, Space also force-advances the current phase (commit '
            'whatever is collected / skip the auto-detect wait) as a manual '
            'fallback. When unchecked, Space only locks the leading air and the '
            'rest of the cycle is purely auto-detected.')
        row1.addWidget(self.cb_sig_train_override)
        row1.addStretch(1)
        v.addLayout(row1)

        # -- Row 2: A = status (colored), B = instruction --------------------
        row2 = QHBoxLayout()
        self.lbl_sig_train_status = QLabel('Idle — press Start Training')
        self.lbl_sig_train_status.setToolTip(
            'Status (A): yellow = settling/waiting, blue = collecting (frames '
            'left), green = acquired (rolling).')
        row2.addWidget(self.lbl_sig_train_status, stretch=1)
        self.lbl_sig_train_instr = QLabel('')
        self.lbl_sig_train_instr.setToolTip('Instruction (B): what to do next.')
        row2.addWidget(self.lbl_sig_train_instr, stretch=1)
        v.addLayout(row2)

        # -- Row 3: Save / Ignore decision (flash when a signature is ready) --
        row3 = QHBoxLayout()
        self.pb_sig_train_save = QPushButton('Save Sig')
        self.pb_sig_train_save.clicked.connect(self._on_sig_train_save)
        row3.addWidget(self.pb_sig_train_save)
        self.pb_sig_train_ignore = QPushButton('Ignore Sig')
        self.pb_sig_train_ignore.clicked.connect(self._on_sig_train_ignore)
        row3.addWidget(self.pb_sig_train_ignore)
        row3.addStretch(1)
        v.addLayout(row3)

        self._sig_decide_flash_timer = QTimer(self)
        self._sig_decide_flash_timer.setInterval(450)
        self._sig_decide_flash_timer.timeout.connect(self._sig_decide_flash_tick)

        self._sig_await_flash_timer = QTimer(self)
        self._sig_await_flash_timer.setInterval(450)
        self._sig_await_flash_timer.timeout.connect(self._sig_await_flash_tick)

        self._update_sig_capture_gating()
        return box

    def _update_sig_capture_n_warning(self, n):
        """Frames below SIG_CAPTURE_N_DEFAULT cannot produce a capture that
        clears MIN_CENTRAL_FRAMES, so every save at that setting is stamped
        'short' by quality_flags(). Say so at the setting, not afterwards in
        the corpus. Amber, not blocked -- a deliberately short capture is still
        allowed, just marked. Style churn is guarded because this fires on
        every keystroke in the spinbox."""
        central = self._central_frame_count(n)
        short = central < pimd_features.MIN_CENTRAL_FRAMES
        tip = ('Frames per capture window. Applied at the next phase change or '
               'settle-loss restart, not mid-window.\n\n'
               'pimd_features trims {0:.0%} off each end before taking stats '
               '(CENTRAL_FRACTION), so {1} frames give {2} central — the count '
               'quality_flags() tests against MIN_CENTRAL_FRAMES ({3}).').format(
                   (1 - pimd_features.CENTRAL_FRACTION) / 2, n, central,
                   pimd_features.MIN_CENTRAL_FRAMES)
        if short:
            tip += ('\n\n⚠ Below {0} frames every capture is stamped '
                    "'short'.".format(SIG_CAPTURE_N_DEFAULT))
        self.sp_sig_capture_n.setToolTip(tip)
        style = self.MY_YELLOW if short else ''
        if style != self._sig_capture_n_last_style:
            self.sp_sig_capture_n.setStyleSheet(style)
            self._sig_capture_n_last_style = style

    def _build_sig_row3_readout_save(self, v):
        # Green-when thresholds for the readout colouring below (v1.38).
        # Defaults come from pimd_features' own constants so the colours start
        # out agreeing with the quality column it writes; editable because the
        # right amplitude floor is rig- and target-dependent.
        row_q = QHBoxLayout()
        row_q.addWidget(QLabel('Green when:'))

        row_q.addWidget(QLabel('Amp(L2) ≥'))
        self.sp_sig_q_amp_mv = QDoubleSpinBox()
        self.sp_sig_q_amp_mv.setRange(0.0, 1000.0)
        self.sp_sig_q_amp_mv.setDecimals(2)
        self.sp_sig_q_amp_mv.setSingleStep(0.25)
        self.sp_sig_q_amp_mv.setValue(
            pimd_features.AIR_THRESHOLD_MV_DEFAULT * math.sqrt(self._n_channels))
        self.sp_sig_q_amp_mv.setToolTip(
            'Amp(L2) at/above this reads green, at/above half of it amber, below red.\n'
            'Default = pimd_features.AIR_THRESHOLD_MV_DEFAULT × √n_channels, i.e. the '
            'L2 equivalent of the "above this, not air" mean|Δ| threshold (L2 ≈ √n × '
            'mean|·| for comparable per-cell magnitudes).')
        row_q.addWidget(self.sp_sig_q_amp_mv)
        row_q.addWidget(QLabel('mV'))

        row_q.addWidget(QLabel('Mean|Δ| ≥'))
        self.sp_sig_q_mean_mv = QDoubleSpinBox()
        self.sp_sig_q_mean_mv.setRange(0.0, 1000.0)
        self.sp_sig_q_mean_mv.setDecimals(3)
        self.sp_sig_q_mean_mv.setSingleStep(0.05)
        self.sp_sig_q_mean_mv.setValue(pimd_features.AIR_THRESHOLD_MV_DEFAULT)
        self.sp_sig_q_mean_mv.setToolTip(
            'Mean|Δ| at/above this reads green, at/above half of it amber, below red.\n'
            'Default = pimd_features.AIR_THRESHOLD_MV_DEFAULT, which is literally '
            '"mean|delta| below this -> air".')
        row_q.addWidget(self.sp_sig_q_mean_mv)
        row_q.addWidget(QLabel('mV'))

        row_q.addWidget(QLabel('Splithalf ≤'))
        self.sp_sig_q_split_ratio = QDoubleSpinBox()
        self.sp_sig_q_split_ratio.setRange(0.01, 2.0)
        self.sp_sig_q_split_ratio.setDecimals(2)
        self.sp_sig_q_split_ratio.setSingleStep(0.05)
        self.sp_sig_q_split_ratio.setValue(pimd_features.NOISY_RATIO_THRESHOLD)
        self.sp_sig_q_split_ratio.setToolTip(
            'Splithalf/SNR read green while splithalf ≤ this × Amp, amber to 1.5× that, '
            'else red.\nDefault = pimd_features.NOISY_RATIO_THRESHOLD, the exact rule '
            "quality_flags() uses to stamp 'noisy' (0.20 == SNR 5).")
        row_q.addWidget(self.sp_sig_q_split_ratio)
        row_q.addWidget(QLabel('× Amp'))
        row_q.addStretch(1)
        v.addLayout(row_q)

        for sp in (self.sp_sig_q_amp_mv, self.sp_sig_q_mean_mv, self.sp_sig_q_split_ratio):
            sp.valueChanged.connect(
                lambda *_: self._set_sig_readout_from_stats(self._sig_last_stats))
        # sp_sig_q_amp_mv is also the Amp gauge's marker, so the line has to
        # follow a typed value the same frame.
        self.sp_sig_q_amp_mv.valueChanged.connect(self._update_analysis_gauges)

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

        self.cb_session_autolog = QCheckBox('Auto-log')
        self.cb_session_autolog.setChecked(self._session_autolog)
        self.cb_session_autolog.setToolTip(
            'When checked, a session dump opens by itself as soon as the stream '
            'starts (and again after a profile change, which needs a new header), '
            'so nothing goes unrecorded. Start Training opens one too as a '
            'backstop. Auto-started sessions get a generated notes line; press '
            'Start to add your own to a session already running. An explicit Stop '
            'suppresses auto-logging until the next stream start.')
        self.cb_session_autolog.toggled.connect(self._on_session_autolog_toggled)
        row_b.addWidget(self.cb_session_autolog)

        self.lbl_sig_session_status = QLabel('Not recording')
        row_b.addWidget(self.lbl_sig_session_status)
        row_b.addStretch(1)
        v.addLayout(row_b)

        # -- Pack voltage (v1.64) ------------------------------------------
        # A 6S pack falls ~2.5 V across a long run and NONE of it was recorded:
        # '# supply: battery' was the only supply fact in the dump. Settling the
        # 2026-07-29/30 warm-up-vs-battery question needed pack voltage against
        # the frame timeline, and that only existed as handwriting on paper.
        row_c = QHBoxLayout()
        row_c.addWidget(QLabel('Pack V:'))
        self.sp_pack_v = QDoubleSpinBox()
        self.sp_pack_v.setRange(0.0, 60.0)
        self.sp_pack_v.setDecimals(2)
        self.sp_pack_v.setSingleStep(0.01)
        self.sp_pack_v.setSpecialValueText('—')      # 0.00 means "not measured"
        self.sp_pack_v.setValue(self._pack_v or 0.0)
        self.sp_pack_v.setToolTip(
            'Measured pack terminal voltage, under load. 0.00 (—) means not '
            'measured and is written as blank rather than as a reading.\n\n'
            'Stamped into every signature capture (pack_v column) and into the '
            'session header. Press "Log V" to timestamp it mid-stream so a long '
            'run carries a voltage TRACK, not one value: analysis interpolates '
            'between entries.')
        self.sp_pack_v.valueChanged.connect(self._on_pack_v_changed)
        row_c.addWidget(self.sp_pack_v)

        self.pb_pack_v_log = QPushButton('Log V')
        self.pb_pack_v_log.setToolTip(
            'Append the current pack voltage to the open session dump as a '
            'timestamped "# pack_v:" line.')
        self.pb_pack_v_log.clicked.connect(self._on_pack_v_log)
        row_c.addWidget(self.pb_pack_v_log)

        self.lbl_pack_v_age = QLabel('')
        row_c.addWidget(self.lbl_pack_v_age)
        row_c.addStretch(1)
        v.addLayout(row_c)

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
        self.cb_hm_scale_auto = QCheckBox('Auto')
        self.cb_hm_scale_auto.setChecked(True)
        self.cb_hm_scale_auto.toggled.connect(self._on_hm_scale_auto_toggled)
        # clicked (not toggled) fires only on a real click, so seeding the
        # limits from what is currently on screen can't fire during
        # _load_settings and overwrite the restored ones.
        self.cb_hm_scale_auto.clicked.connect(self._on_hm_scale_auto_clicked)
        ctrl.addWidget(self.cb_hm_scale_auto)
        self.sp_hm_scale_min = QDoubleSpinBox()
        self.sp_hm_scale_max = QDoubleSpinBox()
        for caption, sp, val in (
                ('Min', self.sp_hm_scale_min, self._analysis_hm_manual_min_uv),
                ('Max', self.sp_hm_scale_max, self._analysis_hm_manual_max_uv)):
            ctrl.addWidget(QLabel(caption))
            # Signed range on BOTH: a diverging mode wants min < 0, Std Dev
            # and RAW want both limits positive, and which is which is the
            # operator's call, not a rule worth enforcing here.
            sp.setRange(-5_000_000, 5_000_000)
            sp.setDecimals(0)
            # Adaptive stepping: one fixed step cannot serve a Δ range of
            # ~500000 µV and a Std Dev range of ~500 µV at the same time.
            sp.setStepType(QAbstractSpinBox.StepType.AdaptiveDecimalStepType)
            sp.setMaximumWidth(96)
            sp.setValue(val)
            sp.setEnabled(False)
            sp.valueChanged.connect(self._on_hm_scale_limits_changed)
            ctrl.addWidget(sp)
        self.sp_hm_scale_min.setToolTip(
            'Colour-scale limits in µV, used when Auto is off. Also what the colorbar\'s '
            'own drag handles write into.\nStd Dev and RAW are unipolar, so a floor of 0 '
            'wastes half the ramp — set Min just under the quiet-cell level and Max just '
            'over the noisy one to see the structure between them.')
        self.sp_hm_scale_max.setToolTip(self.sp_hm_scale_min.toolTip())
        ctrl.addWidget(QLabel('µV'))
        ctrl.addStretch(1)
        v.addLayout(ctrl)

        v.addWidget(self._build_analysis_heatmap_widget())
        return box

    def _build_analysis_heatmap_widget(self):
        self.analysis_gw = pg.GraphicsLayoutWidget()
        # Low floor (v1.38) so the left splitter can squeeze the heatmap right
        # down in favour of the signature list -- the widget's natural minimum
        # would otherwise pin the handle well short of collapsed.
        self.analysis_gw.setMinimumHeight(80)
        self.analysis_plot = self.analysis_gw.addPlot()
        self.analysis_plot.invertY(True)
        self._style_compact(self.analysis_plot)

        self.analysis_img = pg.ImageItem()
        self.analysis_img.setColorMap(self.cm_div)
        self.analysis_plot.addItem(self.analysis_img)

        # Colorbar/legend, docked below the heatmap's x-axis via insert_in --
        # doubles as an interactive range control and as the mV/σ <-> colour
        # legend, without a second widget.
        #
        # interactive=False (v1.45): ColorBarItem's own handles are *relative*
        # adjusters, not level markers -- _regionChanged() snaps them back to
        # 25%/75% of the bar after every drag, so they can never show where
        # Min/Max sit. We drive our own LinearRegionItem instead, positioned by
        # value against a domain wider than the window (see
        # _update_analysis_cbar_range).
        self.analysis_colorbar = pg.ColorBarItem(
            values=(self._analysis_hm_manual_min_uv, self._analysis_hm_manual_max_uv),
            colorMap=self.cm_div, orientation='horizontal', label='value (µV, σ for Z mode)',
            interactive=False)
        cbar_font = QFont()
        cbar_font.setPointSize(7)
        self.analysis_colorbar.axis.setStyle(tickFont=cbar_font)
        self.analysis_colorbar.setImageItem(self.analysis_img, insert_in=self.analysis_plot)

        # The bar's internal x range is a fixed 0..256 whatever the levels are
        # (ColorBarItem.__init__), so CBAR_SPAN is the coordinate system the
        # handles live in and value<->position goes through the domain.
        self.analysis_cbar_region = pg.LinearRegionItem(
            (0.0, CBAR_SPAN), 'vertical', swapMode='block',
            pen=pg.mkPen('#202020', width=2), brush=pg.mkBrush(None),
            hoverPen=pg.mkPen('#ffffff', width=3), hoverBrush=pg.mkBrush(None),
            bounds=(0.0, CBAR_SPAN))
        self.analysis_cbar_region.setZValue(1000)
        for line in self.analysis_cbar_region.lines:
            line.addMarker('<|>', size=7)
        self.analysis_cbar_region.setToolTip(
            'Drag to set the Min/Max colour-scale limits. The pale tails outside the '
            'handles are values the scale saturates on.')
        self.analysis_colorbar.addItem(self.analysis_cbar_region)
        self.analysis_cbar_region.sigRegionChanged.connect(self._on_analysis_cbar_region_changing)
        self.analysis_cbar_region.sigRegionChangeFinished.connect(
            self._on_analysis_cbar_region_done)
        self.analysis_cbar_region.setVisible(not self._analysis_hm_scale_auto)
        self._analysis_cbar_cmap = self.cm_div
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
        self.sp_hm_scale_min.setEnabled(not checked)
        self.sp_hm_scale_max.setEnabled(not checked)
        # In Auto the bar spans exactly the auto-computed range, so handles
        # would sit uselessly on its two ends -- and dragging them wouldn't
        # stick anyway, the next tick recomputes the range.
        if hasattr(self, 'analysis_cbar_region'):
            self.analysis_cbar_region.setVisible(not checked)

    def _on_hm_scale_auto_clicked(self, checked):
        """Leaving Auto seeds Min/Max from the range currently on screen, so
        manual mode starts from what the operator is already looking at and is
        tightened from there -- rather than snapping to a stale pair saved
        under some other display mode."""
        if checked:
            return
        lo, hi = self.analysis_colorbar.levels()
        if lo is None or hi is None or not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
            return
        for sp, val in ((self.sp_hm_scale_min, lo), (self.sp_hm_scale_max, hi)):
            sp.blockSignals(True)
            sp.setValue(float(val))
            sp.blockSignals(False)
        self._analysis_hm_manual_min_uv = float(lo)
        self._analysis_hm_manual_max_uv = float(hi)

    def _on_hm_scale_limits_changed(self, _val):
        """Keep min < max without fighting the user mid-edit: nudge the other
        spinbox rather than snapping back the one being typed into. The levels
        themselves are applied by the next redraw tick, which reads these two
        as the source of truth in manual mode."""
        sp_min, sp_max = self.sp_hm_scale_min, self.sp_hm_scale_max
        if sp_min.value() >= sp_max.value():
            other = sp_max if self.sender() is sp_min else sp_min
            step = max(1.0, abs(sp_min.value()) * 0.01)
            other.blockSignals(True)
            other.setValue(sp_min.value() + step if other is sp_max
                           else sp_max.value() - step)
            other.blockSignals(False)
        self._analysis_hm_manual_min_uv = sp_min.value()
        self._analysis_hm_manual_max_uv = sp_max.value()
        # Redraw the bar now rather than waiting for the next tick: with no
        # stream running _update_analysis_heatmap() returns early, and typing a
        # limit that moved nothing on screen is exactly the confusing case.
        self._update_analysis_cbar(self._analysis_hm_manual_min_uv,
                                    self._analysis_hm_manual_max_uv)

    # -- Colorbar as an absolute range slider (v1.45) -------------------------
    # ColorBarItem's own handles are relative adjusters that snap back to
    # 25%/75% after every drag, so they can never show where Min/Max sit. Ours
    # are positioned by value: the bar's axis spans a *domain* wider than the
    # window, the handles sit at Min and Max within it, and the pale tails
    # outside them are the values the scale saturates on.

    @staticmethod
    def _cbar_pos(value, dom_lo, dom_hi):
        """Value -> position in the bar's fixed 0..CBAR_SPAN coordinate space."""
        if dom_hi <= dom_lo:
            return 0.0
        return float(np.clip((value - dom_lo) / (dom_hi - dom_lo), 0.0, 1.0) * CBAR_SPAN)

    @staticmethod
    def _cbar_value(pos, dom_lo, dom_hi):
        return float(dom_lo + (pos / CBAR_SPAN) * (dom_hi - dom_lo))

    def _analysis_cbar_domain_for(self, lo, hi):
        """The range the bar's axis spans: the window widened to take in the
        data actually on screen, so a handle has somewhere to travel outwards
        to -- then held between CBAR_MIN/MAX_WINDOW_FRAC, which re-centres the
        window on the bar. The union is quantised and the clamped forms derive
        from (lo, hi) alone: reading an unrounded data max straight off the
        live matrix walks the axis and the handles a pixel every frame.

        Sticky: an existing domain that still holds the window at a workable
        size is kept as-is. Refitting on every tick would re-centre the window
        after every drag, springing the handles back to 25%/75% -- which is the
        ColorBarItem behaviour this replaced."""
        span = hi - lo
        cur = self._analysis_cbar_domain
        if cur is not None and cur[1] > cur[0] and cur[0] <= lo and hi <= cur[1]:
            frac = span / (cur[1] - cur[0])
            if CBAR_MIN_WINDOW_FRAC <= frac <= CBAR_MAX_WINDOW_FRAC:
                return cur
        d_lo, d_hi = self._analysis_cbar_data_range or (lo, hi)
        dom_lo, dom_hi = min(lo, d_lo), max(hi, d_hi)
        dom_span = dom_hi - dom_lo
        if np.isfinite(dom_span) and dom_span > 0:
            step = 10.0 ** math.floor(math.log10(dom_span / 4.0))
            dom_lo = math.floor(dom_lo / step) * step
            dom_hi = math.ceil(dom_hi / step) * step
            dom_span = dom_hi - dom_lo
        widest, tightest = span / CBAR_MIN_WINDOW_FRAC, span / CBAR_MAX_WINDOW_FRAC
        if not (tightest <= dom_span <= widest):
            pad = (min(max(dom_span, tightest), widest) - span) / 2.0
            dom_lo, dom_hi = lo - pad, hi + pad
        if not (dom_hi > dom_lo):
            dom_lo, dom_hi = lo - 1.0, hi + 1.0
        return dom_lo, dom_hi

    def _set_analysis_cbar_gradient(self, lo, hi, dom_lo, dom_hi):
        """Paint the bar's strip clipped the same way the image is: flat below
        Min, the ramp across the window, flat above Max. Written straight onto
        the bar pixmap rather than via ColorBarItem.setColorMap(), which would
        push both the strip's clipped map and the bar's (domain) levels into
        the heatmap image."""
        cmap = self._analysis_cbar_cmap
        lut = cmap.getLookupTable(nPts=256, alpha=True)
        vals = np.linspace(dom_lo, dom_hi, 256)
        t = np.clip((vals - lo) / (hi - lo), 0.0, 1.0) if hi > lo else np.zeros(256)
        strip = np.expand_dims(lut[(t * 255.0).astype(int)], axis=0)
        qimg = pg.functions.ndarray_to_qimage(np.ascontiguousarray(strip),
                                               QImage.Format.Format_RGBA8888)
        self.analysis_colorbar.bar.setPixmap(QPixmap.fromImage(qimg))

    def _update_analysis_cbar(self, lo, hi):
        """Re-point the whole bar at colour-scale window (lo, hi): axis domain,
        clipped gradient, handle positions."""
        if not hasattr(self, 'analysis_cbar_region'):
            return
        auto = self._analysis_hm_scale_auto
        self.analysis_cbar_region.setVisible(not auto)
        if auto:
            dom = (lo, hi)                       # no tails to show, no handles
        elif self._analysis_cbar_dragging and self._analysis_cbar_domain is not None:
            dom = self._analysis_cbar_domain     # frozen: don't move the ruler mid-drag
        else:
            dom = self._analysis_cbar_domain_for(lo, hi)
        self._analysis_cbar_domain = dom
        # update_items=False -- the axis is showing the domain, which must not
        # be pushed into the image as its levels.
        self.analysis_colorbar.setLevels(dom, update_items=False)
        self._set_analysis_cbar_gradient(lo, hi, dom[0], dom[1])
        if not auto and not self._analysis_cbar_dragging:
            self._analysis_cbar_syncing = True
            self.analysis_cbar_region.setRegion(
                (self._cbar_pos(lo, dom[0], dom[1]), self._cbar_pos(hi, dom[0], dom[1])))
            self._analysis_cbar_syncing = False

    def _on_analysis_cbar_region_changing(self):
        """Live during a handle drag: mirror the dragged positions into the
        Min/Max spinboxes (rounded to what those spinboxes can actually show,
        so the two never disagree). The image's levels follow on the next
        redraw tick, which reads the spinboxes."""
        if self._analysis_cbar_syncing or self._analysis_hm_scale_auto:
            return
        dom = self._analysis_cbar_domain
        if dom is None:
            return
        self._analysis_cbar_dragging = True
        p_lo, p_hi = self.analysis_cbar_region.getRegion()
        lo = float(round(self._cbar_value(p_lo, dom[0], dom[1])))
        hi = float(round(self._cbar_value(p_hi, dom[0], dom[1])))
        if hi <= lo:
            return
        self._analysis_hm_manual_min_uv = lo
        self._analysis_hm_manual_max_uv = hi
        for sp, val in ((self.sp_hm_scale_min, lo), (self.sp_hm_scale_max, hi)):
            sp.blockSignals(True)
            sp.setValue(val)
            sp.blockSignals(False)
        self._set_analysis_cbar_gradient(lo, hi, dom[0], dom[1])

    def _on_analysis_cbar_region_done(self):
        self._analysis_cbar_dragging = False

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

    def _make_chart_pause_checkbox(self, attr):
        """A 'Pause' checkbox for one live chart group (v1.64).

        These three charts redraw every frame and between them push 1 + n_bands +
        n_cells setData calls per tick (17 at 63 cells) plus two scale re-syncs.
        Drawing competes with draining the serial port on the same single-threaded
        Qt event loop, and when the reader loses that race frames queue up (the
        Rate readout's 'burst×N') and, at the limit, the MCU blocks in its emit
        print() and stops sweeping — which is not merely lost data, it changes the
        rig's thermal load (see _note_frame_gap). Pausing a chart is the direct
        way to buy the ingest path time on a long unattended run.

        Paused means "don't draw", never "don't record": the frame path,
        _rolling_buf, the session dump and every gate are untouched. Resuming
        picks up from live data with no backfill, which is the honest behaviour
        for a live view."""
        cb = QCheckBox('Pause')
        cb.setToolTip(
            'Stop redrawing this chart to free event-loop time for draining the '
            'serial stream. Recording, gating and the session dump are unaffected; '
            'the chart resumes from live data. Pausing all three also skips the '
            'shared matrix computation behind them.')
        cb.toggled.connect(lambda checked, a=attr: setattr(self, a, checked))
        return cb

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
        self.cb_c2_pause = self._make_chart_pause_checkbox('_analysis_c2_paused')
        row_b.addWidget(self.cb_c2_pause)
        v.addLayout(row_b)

    def _build_analysis_chart2(self):
        self.analysis_c2_glw = pg.GraphicsLayoutWidget()
        self.analysis_c2_plot = self.analysis_c2_glw.addPlot()
        self.analysis_c2_plot.setLogMode(x=True, y=False)
        self._style_compact(self.analysis_c2_plot)
        self.analysis_c2_plot.setLabel('bottom', 'pulse width (µs)', **{'font-size': '7pt'})
        self.analysis_c2_refline = self.analysis_c2_plot.addLine(
            y=0.0, pen=pg.mkPen((150, 150, 150), width=1))
        # Live "current" trace is black (v1.38) -- it used to be blue, which
        # collided with whatever blue pg.intColor() handed a template overlay,
        # making "live vs corpus" ambiguous at a glance. Black is never an
        # intColor hue, and the overlays stay dashed on top of it.
        self.analysis_c2_curve = self.analysis_c2_plot.plot(
            [], [], pen=pg.mkPen('k', width=2), symbol='o', symbolSize=5)
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
        self.cb_g8_pause = self._make_chart_pause_checkbox('_analysis_g8_paused')
        ctrl.addWidget(self.cb_g8_pause)
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
            curve = plot.plot([], [], pen=pg.mkPen('k', width=2), symbol='o', symbolSize=4)
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
        self.cb_g9_pause = self._make_chart_pause_checkbox('_analysis_g9_paused')
        ctrl.addWidget(self.cb_g9_pause)
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
            curve = plot.plot([], [], pen=pg.mkPen('k', width=2), symbol='o', symbolSize=4)
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

    # -- Trigger levels: the Training gates, plotted and settable ------------

    def _build_analysis_gauges_group(self):
        """Settle / Detect / Amp / SNR, so the two Training auto-detect
        thresholds can be seen against the live signal and dragged to a level
        that clears the noise, instead of being guessed at and then debugged by
        running a cycle.

        Settle and Detect carry draggable markers bound to the spinboxes in the
        Training group. Amp and SNR are context -- their markers move the
        quality/gate settings those two are judged against. Air age is
        read-only (binding None): its limit is derived from the Detect setting
        and the measured drift rate, so there is nothing to drag."""
        box = QGroupBox('Trigger Levels')
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(2)
        self.analysis_gauges = {}
        v.addWidget(self._build_gauge_column([
            ('settle',   'Settle ≤',  'mV σ',      ('sp_sig_settle_mv', _identity, _identity)),
            ('detect',   'Detect ≥',  'mV wander', ('sp_sig_detect_mv', _identity, _identity)),
            ('amp',      'Amp (log)', 'mV',        ('sp_sig_q_amp_mv', _log10_axis, _pow10_axis)),
            ('snr',      'SNR',       '',          ('sp_shape_gate', _identity, _identity)),
            ('air_age',  'Air age',   's',         None),
        ], self.analysis_gauges, value_w=58))
        # Typing into the spinbox must move the marker now, not on the next
        # frame. Guarded inside _update_analysis_gauges against the drag that
        # set the spinbox in the first place. sp_sig_q_amp_mv already drives a
        # readout refresh (_build_sig_row3_readout_save) and sp_shape_gate an
        # axis redraw, so those two are picked up in their existing handlers.
        self.sp_sig_settle_mv.valueChanged.connect(self._update_analysis_gauges)
        self.sp_sig_detect_mv.valueChanged.connect(self._update_analysis_gauges)
        return box

    @staticmethod
    def _gauge_hi(value, threshold, floor=0.2):
        """Top of a threshold-anchored bar axis. Anchored on the THRESHOLD,
        not on the reading the way the Family Plane's settle gauge is
        (max(value*2, 1.0)): a value-scaled axis slides the marker around under
        the cursor, and here the marker is the control you are trying to grab.
        It still grows to fit an over-range reading rather than pinning it."""
        hi = max(2.0 * threshold, floor)
        if value is not None and np.isfinite(value):
            hi = max(hi, 1.25 * value)
        return hi

    def _analysis_gauge_features(self):
        """Live feature dict measured against the TRAINING cycle's locked
        leading air (_sig_air_ref), over the Stats window the settle/detect
        gates use -- so Amp/SNR here describe the same comparison the cycle is
        making. None until a cycle locks an air reference; the caller then
        falls back to _shape_live, which is measured against the Family Plane's
        own reference and reads ~0 while that one is still rolling."""
        if self._sig_air_ref is None:
            return None
        vec, splithalf = self._shape_live_window(
            ref=self._sig_air_ref, n_win=self.sp_stats_window.value())
        if vec is None or splithalf is None:
            return None
        try:
            return self._shape_feature_dict(
                vec, list(self._pulse_us_sorted), self._n_cells,
                pimd_shape.amp_l2(vec), splithalf)
        except ValueError:
            return None

    def _sig_dev_mode(self):
        """Which comparison the Detect gauge should be showing: 'air' and
        'target' are the two phases where the state machine is actually
        testing a fresh reference against Detect, and the gauge shows the very
        number being tested. Everywhere else nothing is gated, so it shows air
        wander instead of a reference quietly ageing (§17.10, v1.52)."""
        if not self._analysis_training_active:
            return 'wander'
        return {'await_target': 'air', 'await_remove': 'target'}.get(
            self._sig_train_phase, 'wander')

    def _sig_cycle_budget_s(self):
        """The longest a healthy cycle can legitimately take from the air lock
        to the finished signature, and so the Air-age marker's limit (v1.54).

        After the lock the cycle owes: await_target (guard), the target window,
        await_remove (guard), the trailing-air window. Two collecting windows
        and two guards -- air_lead is already spent by the time the lock
        happens. At 120 frames and ~3.3 Hz that is ~132 s.

        The limit used to be the drift budget, Detect / 0.05 mV/s (the
        §17.2/§17.10 measured rate) -- 10 s at Detect 0.5, which went red
        long before a 120-frame target
        window could finish and so said nothing. That number described whether
        a magnitude test against the frozen reference could still work; with
        removal now testing against the target snapshot instead (v1.54),
        nothing gates on the air reference's age any more, and the useful
        question became "is this cycle dragging".

        Sweep period comes from the measured rate when there is one -- a
        63-cell profile sweeps slower than a 45-cell one, so a hardcoded period
        would be wrong on half the profiles."""
        period = 1.0 / self._fps_hz if self._fps_hz > 0.2 else SWEEP_PERIOD_FALLBACK_S
        return 2.0 * self.sp_sig_capture_n.value() * period + 2.0 * self._SIG_AWAIT_SECONDS

    def _update_analysis_gauges(self):
        """Settle and Detect are the exact quantities _sig_train_ingest()
        gates on -- same helpers, same windows -- so the bar crossing the
        marker and the cycle advancing are one event, not two things that
        ought to agree. Amp/SNR are context and gate nothing here."""
        if not hasattr(self, 'analysis_gauges') or self._gauge_marker_drag:
            return

        settle_thr = self.sp_sig_settle_mv.value()
        settle_mv  = self._current_settle_mv()
        # v1.64: show what the window actually was, not just the reduction over
        # it. 50 frames is 7.2 s when the stream is healthy and can be minutes
        # when it is not, and the number alone cannot tell those apart.
        settle_blocked = settle_mv is None and self._window_block_reason == 'stalled'
        self._set_gauge(
            self.analysis_gauges, 'settle', settle_mv,
            0.0, self._gauge_hi(settle_mv, settle_thr), settle_thr,
            self._window_status_text(settle_mv), good_above=False,
            # the readout is a phrase, not a number -- don't suffix it with 'mV σ'
            unit='' if settle_blocked else None)

        # Which reference is honest right now. In the two gated phases show the
        # very number the state machine is testing; otherwise show how far the
        # air moves on its own, which is the floor Detect has to clear and does
        # not accumulate the way a frozen reference does. The unit text names
        # which one is on screen -- reading 'vs air' when nothing is locked was
        # the whole v1.51 confusion.
        detect_thr = self.sp_sig_detect_mv.value()
        mode       = self._sig_dev_mode()
        dev_mv, unit = {
            'air':    (self._current_dev_from_air,    'mV vs air'),
            'target': (self._current_dev_from_target, 'mV vs target'),
        }.get(mode, (self._current_air_wander_mv, 'mV wander'))
        dev_mv = dev_mv()
        # The verdict flips with the mode, because "good" does. Gated (either
        # reference): dev at or above Detect is the transition being waited for
        # -- target arrived, or target departed. Wander: the air moving LESS
        # than Detect is what you want, because that is the trigger level
        # clearing the noise floor, which is the whole reason to look.
        self._set_gauge(
            self.analysis_gauges, 'detect', dev_mv,
            0.0, self._gauge_hi(dev_mv, detect_thr), detect_thr,
            '' if dev_mv is None else '{0:.3f}'.format(dev_mv),
            good_above=mode != 'wander', unit=unit)

        # Age of the locked air reference against the cycle budget -- "is this
        # cycle dragging", not the old drift budget (see _sig_cycle_budget_s()
        # for why that limit stopped being the right question at v1.54).
        age = (None if self._sig_air_ref_ts is None
               else time.time() - self._sig_air_ref_ts)
        age_limit = self._sig_cycle_budget_s()
        self._set_gauge(
            self.analysis_gauges, 'air_age', age,
            0.0, self._gauge_hi(age, age_limit, floor=30.0), age_limit,
            '' if age is None else '{0:.0f}'.format(age), good_above=False)

        feat    = self._analysis_gauge_features() or self._shape_live
        amp_thr = math.log10(max(self.sp_sig_q_amp_mv.value(), 1e-3))
        # sp_shape_gate lives on the Family Plane tab, which is built after
        # this one -- and _redraw() can fire in between.
        gate = self._shape_gate() if hasattr(self, 'sp_shape_gate') else SHAPE_GATE_DEFAULT
        if feat is None:
            self._set_gauge(self.analysis_gauges, 'amp', None, -2, 3, amp_thr, '')
            self._set_gauge(self.analysis_gauges, 'snr', None, 0, max(20.0, gate * 2), gate, '')
        else:
            self._set_gauge(self.analysis_gauges, 'amp', feat['log_amp'], -2, 3, amp_thr,
                            '{0:.2f}'.format(feat['amp']))
            self._set_gauge(
                self.analysis_gauges, 'snr', feat['snr'], 0, max(20.0, gate * 2), gate,
                '∞' if not np.isfinite(feat['snr']) else '{0:.1f}'.format(feat['snr']))

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
        self.analysis_strip_curve = self.analysis_strip_plot.plot([], [], pen=pg.mkPen('k', width=1))
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
        # Not setColorMap() on the bar: that pushes the bar's own levels (which
        # are the slider's *domain*, not the image's) back into the image. The
        # bar's strip is painted by _set_analysis_cbar_gradient from this map.
        self._analysis_cbar_cmap = cmap
        self._analysis_cbar_data_range = (float(matrix.min()), float(matrix.max()))

        if self._analysis_hm_scale_auto:
            if mode in ('raw', 'stddev'):
                levels = (0.0, float(matrix.max()) * 1.05 + 1.0)
            else:
                lim = float(np.max(np.abs(matrix)))
                if lim < 1.0:
                    lim = 1.0
                levels = (-lim, lim)
        else:
            # Manual: the Min/Max spinboxes are the single source of truth
            # (v1.44). Re-applying them every tick is safe with the slider
            # handles because a drag writes the dragged values straight back
            # into the spinboxes -- so what is re-applied here is what was just
            # dragged, not a stale pair that would fight the drag.
            levels = (self._analysis_hm_manual_min_uv, self._analysis_hm_manual_max_uv)
        self.analysis_img.setImage(matrix.T, levels=levels)
        # ImageItem has no sigLevelsChanged in this pyqtgraph version, so the
        # bar won't pick up a programmatic level change on its own.
        self._update_analysis_cbar(levels[0], levels[1])

    def _update_analysis_charts(self):
        if hasattr(self, 'lbl_analysis_baseline_info'):
            self.lbl_analysis_baseline_info.setText(self.lbl_baseline_info.text())
        # v1.64: with all three paused there is nothing to draw, so don't pay for
        # the shared matrix either -- that is the largest single saving here and
        # the reason the check comes before _compute_analysis_matrix() rather
        # than per-chart below. The baseline-info label still updates: it is text,
        # it costs nothing, and it is not one of the paused charts.
        if (self._analysis_c2_paused and self._analysis_g8_paused
                and self._analysis_g9_paused):
            return
        matrix = self._compute_analysis_matrix()
        if matrix is None:
            return
        sorted_matrix = matrix[self._pulse_sort_order]   # rows now pulse_us ascending

        if not self._analysis_c2_paused:
            bandmeans = sorted_matrix.mean(axis=1)
            y2 = self._normalize_group(bandmeans, self._analysis_c2_norm_auto,
                                        self._analysis_c2_manual_ref)
            self.analysis_c2_curve.setData(self._pulse_us_sorted, y2)

        if not self._analysis_g8_paused:
            for i in range(self._n_bands):
                y = self._normalize_group(sorted_matrix[i, :], self._analysis_g8_norm_auto,
                                           self._analysis_g8_manual_ref)
                self.analysis_g8_curves[i].setData(np.arange(self._n_cells) + 0.5, y)

        if not self._analysis_g9_paused:
            for j in range(self._n_cells):
                y = self._normalize_group(sorted_matrix[:, j], self._analysis_g9_norm_auto,
                                           self._analysis_g9_manual_ref)
                self.analysis_g9_curves[j].setData(self._pulse_us_sorted, y)

        # "Y axis locked to the first chart" -- re-synced every tick since,
        # in Auto scale mode, panel 0's auto-fit range moves with live data.
        # Skipped with its grid: re-syncing a scale nothing is drawing into is
        # exactly the work being paused.
        if not self._analysis_g8_paused:
            self._apply_g8_scale()
        if not self._analysis_g9_paused:
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

    def _sig_file_is_new_schema(self, path):
        """True if the file's header carries the v1.32+ corpus schema this app
        reads and writes (target_id/distance_mm/delta_mV columns), i.e. is
        _scan_editable_signature_file()-readable. pimd_corpus_check.py is still
        on the legacy target/distance_cm schema and hard-rejects the new one,
        so both load paths dispatch on this. Reads only the first non-comment
        line."""
        try:
            with open(path, newline='') as f:
                header = next((ln for ln in f if not ln.startswith('#')), '')
        except OSError:
            return False
        cols = header.rstrip('\n').split(',')
        return 'target_id' in cols and 'distance_mm' in cols and 'delta_mV' in cols

    def _corpus_fields_for_path(self, path):
        """The column list to WRITE when appending a capture to `path` (v1.65).

        An existing file's own header wins over `CORPUS_HEADER_FIELDS`. Both
        append paths write one value per field and only emit a header row when
        the file is new, so as soon as the tool's field list grew (features v9
        added `pack_v`) appending to a file written before it produced rows with
        one more value than the header declares -- a ragged CSV, silently, on the
        first Save into any corpus captured earlier. That is every corpus on disk
        today, including the v3 one in active use.

        Writing the file's own columns is the right resolution rather than
        migrating the file or refusing to append: `pack_v` is an OPTIONAL column
        by design (pimd_corpus_check.OPTIONAL_FIELDS), so a file without it
        simply does not record it -- exactly as a capture with no voltage entered
        does not. A column the file declares but the row has no value for is
        written blank, so a joined or foreign header cannot KeyError here.
        """
        try:
            with open(path, newline='') as f:
                header = next((ln for ln in f if not ln.startswith('#')), '')
        except OSError:
            return list(pimd_features.CORPUS_HEADER_FIELDS)
        cols = [c for c in header.rstrip('\n').split(',') if c]
        return cols if cols else list(pimd_features.CORPUS_HEADER_FIELDS)

    def _sig_dialog_dir(self):
        """Start directory for the signature file dialogs -- the last one used,
        falling back to src/data/corpora/ if it has since been moved away."""
        if self._last_sig_dir and os.path.isdir(self._last_sig_dir):
            return self._last_sig_dir
        return CORPORA_DIR if os.path.isdir(CORPORA_DIR) else ''

    def _remember_sig_dir(self, path):
        if path:
            self._last_sig_dir = os.path.dirname(os.path.abspath(path))

    def _on_load_signatures_clicked(self):
        # DontUseNativeDialog: the native GTK/portal file dialog renders as a
        # completely blank window in this environment -- Qt's own dialog
        # widget works reliably instead.
        path, _ = QFileDialog.getOpenFileName(
            self, 'Load signature corpus', self._sig_dialog_dir(), 'CSV files (*.csv)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return
        self._remember_sig_dir(path)
        try:
            # v1.32+ files (what this app writes) go through our own reader;
            # pimd_corpus_check.load_corpus only handles the legacy schema and
            # would SystemExit on the new one (v1.37 fix).
            if self._sig_file_is_new_schema(path):
                sigs = self._scan_editable_signature_file(path)
            else:
                sigs = pimd_corpus_check.load_corpus(path)
        except (SystemExit, Exception) as e:
            self.statusBar().showMessage('Load failed: {0}'.format(e))
            return
        self._merge_template_list(sigs, source='loaded')
        self.statusBar().showMessage('Loaded {0} signature(s) from {1}'.format(len(sigs), path))

    # Per-source list prefix. Three sources share one store, so the list has to
    # say which file a row came from without a second column.
    _TEMPLATE_SOURCE_PREFIX = {'editable': '✎ ', 'scratch': '△ '}

    # Distinct hues the per-target colouring draws from. With a handful of
    # targets in a corpus a collision is unlikely; two sharing a hue is
    # cosmetic and the label still separates them, which is a better trade
    # than a scheme that reshuffles colours to stay unique.
    TEMPLATE_HUES = 36

    @staticmethod
    def _template_color(target_id, ordinal, n_for_target):
        """Hue from the target, value stepped across that target's captures
        (v1.61). Every capture of a target reads as one family in the list,
        while its individual captures stay separable -- which matters because
        this colour is also the pen for the chart overlay curves and the Family
        Plane markers, where a flat per-target colour would make two overlaid
        orientations of the same target indistinguishable.

        The hue comes from zlib.crc32, NOT the builtin hash(): str hashing is
        salted per process (PYTHONHASHSEED), so hash() would hand a target a
        different colour on every launch -- a subtler version of the per-row
        instability this replaces, and one that passes every in-process test.

        Value rather than saturation carries most of the shade: these are
        list-item foreground colours on a light background, where darker stays
        readable and lighter does not. A small hue jitter runs alongside it,
        because value alone cannot separate many captures of one target -- at
        17 captures the steps are ~5 units apart and adjacent overlay curves
        would be indistinguishable. Two dimensions help; they do not make 17
        shades of one hue genuinely distinct, and the label is what identifies
        a row. Deliberately kept narrow so the family still reads as one."""
        idx = zlib.crc32((target_id or '?').encode('utf-8')) % MainWindow.TEMPLATE_HUES
        h, s, _v, a = pg.intColor(idx, hues=MainWindow.TEMPLATE_HUES).getHsv()
        if n_for_target > 1:
            frac = ordinal / (n_for_target - 1)          # 0.0 .. 1.0
            v = int(round(230 - 90 * frac))
            h = int(round(h + 20 * (frac - 0.5))) % 360   # +/- 10 degrees
        else:
            v = 185
        out = QColor()
        out.setHsv(h, s, max(0, min(255, v)), a)
        return out

    def _merge_template_list(self, sigs, source):
        """Replace only the entries tagged `source` ('loaded' = read-only
        reference corpus, 'editable' = the active editable file, 'scratch' =
        today's Family Plane scratch file), leaving entries from the other
        sources untouched -- all three coexist in one list, all overlay-able.
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
        prefix = self._TEMPLATE_SOURCE_PREFIX.get(source, '')

        # Two passes (v1.61): the colour's shade needs each capture's ordinal
        # WITHIN its target, which isn't known until every key is resolved.
        # Pass 1 only hoists the existing key-shape branch, unchanged.
        resolved = []
        for key in keys_sorted:
            sig = sigs[key]
            if len(key) == 3:
                # 'loaded'/legacy source (pimd_corpus_check.load_corpus(),
                # still old target/distance_cm schema -- see its own
                # changelog entry for the v1.32-schema loud-rejection).
                session, display_target, display_place = key[0], key[1], '{0}cm'.format(key[2])
                target_id, distance_mm = key[1], str(int(float(key[2])) * 10)
            else:
                # 'editable' source (this file's own _scan_editable_
                # signature_file(), v1.32+ schema) -- key is (session,
                # capture_id); display fields live in the value dict.
                session, capture_id = key
                display_target = sig.get('target_id') or capture_id
                display_place = '{0}mm'.format(sig['distance_mm']) if sig.get('distance_mm') else 'air'
                target_id, distance_mm = sig.get('target_id', ''), sig.get('distance_mm', '')
            resolved.append((key, sig, session, display_target, display_place,
                              target_id, distance_mm))

        # Group sizes are per source batch, exactly as the old row index was.
        # The HUE doesn't depend on them -- it comes from the target_id -- so a
        # target keeps its colour whichever source it arrives from.
        target_counts = Counter(r[5] for r in resolved)
        target_seen = {}

        for key, sig, session, display_target, display_place, target_id, distance_mm in resolved:
            amp, splithalf, quality = sig['amp'], sig['splithalf'], sig['quality']
            snr = amp / splithalf if splithalf > 1e-9 else float('inf')
            ordinal = target_seen.get(target_id, 0)
            target_seen[target_id] = ordinal + 1

            # Orientation + repeat, so the six captures that share
            # 'Cu_pipe_01 @120mm' are tellable apart. Legacy corpora predate
            # the schema and carry neither -- omitted silently rather than
            # padded, and a long_axis of 'na' says nothing worth a column.
            place = display_place
            axis = str(sig.get('long_axis') or '').strip()
            if axis and axis != 'na':
                place += '  {0}'.format(axis)
            repeat = str(sig.get('repeat_idx') or '').strip()
            if repeat:
                place += '  r{0}'.format(repeat)
            label = '{0}{1} @{2}   amp={3:.0f} SNR={4:.1f} [{5}]'.format(
                prefix, display_target, place, amp, snr, quality)
            color = self._template_color(target_id, ordinal, target_counts[target_id])
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # Signatures captured in this app session default to *checked* so
            # they're on the charts the moment they're saved (v1.38); anything
            # else (a loaded reference corpus, a reopened file) defaults to
            # unchecked so a 30-capture corpus doesn't flood every plot. The
            # default only ever applies to a key's first appearance -- once an
            # item exists, prev_checked preserves whatever it was set to, so
            # unticking a fresh capture sticks across Save/Delete reloads.
            default = (Qt.CheckState.Checked if key in self._sig_autocheck_keys
                       else Qt.CheckState.Unchecked)
            item.setCheckState(prev_checked.get(key, default))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setForeground(QBrush(color))
            item.setToolTip('{0} @{1} ({2})  amp={3:.3f}mV  splithalf={4:.3f}mV  SNR={5:.2f}  quality={6}'.format(
                display_target, place, session, amp, splithalf, snr, quality))
            self.lw_analysis_templates.addItem(item)
            # target_id/distance_mm/geometry are carried through (v1.42) rather
            # than only being formatted into `label`: the Shape Space tab plots
            # from this same store and needs them as data, not display text.
            # pulses_us/n_delays fall back to the live profile for any source
            # that doesn't report its own geometry.
            self._analysis_templates[key] = {'shape': sig['shape'], 'color': color, 'label': label,
                                              'amp': amp, 'splithalf': splithalf, 'quality': quality,
                                              'source': source, 'session': session,
                                              'target_id': target_id, 'distance_mm': distance_mm,
                                              'short_name': sig.get('short_name', ''),
                                              'pulses_us': sig.get('pulses_us') or list(self._pulse_us_sorted),
                                              'n_delays': sig.get('n_delays') or self._n_cells,
                                              'profile_name': sig.get('profile_name', '')}
        self.lw_analysis_templates.blockSignals(False)
        self._shape_invalidate_features()
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

        # Shape Space draws from the same store and the same checked set, so
        # it refreshes on exactly the same events (load, (un)check, clear,
        # profile change) rather than needing its own set of hooks.
        self._shape_redraw_static()

    # -- Signature capture (air-before / target / air-after) ----------------

    # -- Training state machine (v1.34) ---------------------------------
    # Automated auto-detect cycle. Phases:
    #   air_lead     -- rolling the leading air; Space (green) locks the last
    #                   N frames and starts the cycle.
    #   await_target -- air locked; wait (30 s) for a target to be placed and
    #                   the signal to re-settle above the Detect threshold.
    #   target       -- collect N target frames.
    #   await_remove -- target acquired; wait (30 s) for removal (re-settle
    #                   back below Detect).
    #   air_trail    -- collect N trailing air frames -> compute the signature
    #                   -> Save/Ignore; the buffer keeps rolling as the next
    #                   cycle's leading air.
    # Colour ladder in the collecting phases: 'settling' (yellow) ->
    # 'collecting' (blue, frames-left countdown) -> 'ready' (green, rolling).
    # Settle loss mid-window clears the buffer -- a disturbance contaminates
    # the whole window (v1.31 gate philosophy). All snapshot/stats math is
    # unchanged from v1.33; only the transition triggers and UI are new.

    _SIG_COLLECTING_PHASES = ('air_lead', 'target', 'air_trail')

    def _on_sig_train_start_toggled(self, checked):
        if not checked:
            # Stop: keep any unsaved stats/readout so Save still works.
            self._reset_sig_capture_state(preserve_stats=True)
            return
        refuse = None
        if self._editable_sig_path is None:
            refuse = 'Training: open a signature file first (New file… / Open for editing…)'
        if refuse is not None:
            self.pb_sig_train_start.blockSignals(True)
            self.pb_sig_train_start.setChecked(False)
            self.pb_sig_train_start.blockSignals(False)
            self.statusBar().showMessage(refuse)
            return
        # v1.63 backstop. Stream start is the primary trigger and will normally
        # have opened a dump already, in which case this no-ops; it only bites
        # if logging was never armed or the stream predates the preference.
        # Deliberately after the refuse-guard -- a training start that was
        # rejected shouldn't leave a session file behind.
        self._maybe_autostart_session('training start')
        self._sig_air_before = None
        self._sig_air_after  = None
        self._sig_target     = None
        self._sig_last_stats = None
        self._sig_air_ref    = None
        self._sig_air_ref_ts = None
        self._sig_await_deadline = None
        self._sig_target_manual = False
        self._sig_removal_armed = False
        self._clear_sig_decide()
        self._update_sig_readout()
        self._analysis_training_active = True
        self._sig_train_phase = 'air_lead'
        self.pb_sig_train_start.setText('Stop Training')
        self._sig_train_restart_buffer()
        self._update_sig_capture_gating()

    def _sig_train_snapshot(self):
        """The current rolling buffer as a capture entry (same dict shape the
        v1.33 acquire produced)."""
        buf = self._sig_train_buf
        ts_arr  = np.array([ts for ts, _ in buf], dtype=float)
        raw_arr = np.array([r for _, r in buf], dtype=float)
        if self._sig_glitch_skipped > 0.2 * buf.maxlen:
            self.statusBar().showMessage(
                '⚠ training ({0}): {1} glitch frame(s) excluded while filling '
                'the {2}-frame window — check for interference'.format(
                    self._sig_train_phase, self._sig_glitch_skipped, buf.maxlen))
        return {'t_seconds': ts_arr, 'frames_mV': raw_arr / 1000.0, 'n_frames': len(ts_arr)}

    def _on_sig_train_space(self):
        """Space handler. Locks the leading air (air_lead -> await_target), and
        — when 'Space override' is checked — force-advances any other phase as
        a manual fallback for slow/failed auto-detect."""
        if not self._analysis_training_active:
            return
        if self._sig_decide_pending:
            self.statusBar().showMessage('Training: decide Save / Ignore first')
            return
        phase = self._sig_train_phase
        override = self.cb_sig_train_override.isChecked()
        if phase == 'air_lead':
            if self._sig_train_status != 'ready':
                if not override:
                    self.statusBar().showMessage(
                        'Training: leading air not ready yet (wait for green)')
                    return
            self._sig_lock_leading_air()
        elif not override and not self._sig_target_manual:
            # a manual placement latches manual for the rest of the cycle:
            # auto-detect is off for the removal, so unticking the checkbox
            # mid-cycle must not strand the operator in a 30 s timeout
            self.statusBar().showMessage(
                'Training: auto-detecting — enable "Space override" to advance manually')
            return
        elif phase == 'await_target':
            self._sig_enter_target(manual=True)
        elif phase == 'target':
            self._sig_finish_target()
        elif phase == 'await_remove':
            self._sig_enter_air_trail()
        elif phase == 'air_trail':
            self._sig_finish_air_trail()
        self._update_sig_capture_gating()

    def _sig_can_commit(self):
        """True if the rolling buffer holds enough frames to snapshot (guards
        a Space-override force-advance of a barely-started window)."""
        if self._sig_train_buf is None or len(self._sig_train_buf) < 2:
            self.statusBar().showMessage('Training: not enough frames collected yet')
            return False
        return True

    def _sig_lock_leading_air(self):
        """Snapshot the last N rolling frames as the leading air and arm the
        target-placement wait."""
        if not self._sig_can_commit():
            return
        entry = self._sig_train_snapshot()
        self._sig_air_before = entry
        # air reference for the Detect threshold: median of the locked frames
        self._sig_air_ref = np.median(entry['frames_mV'], axis=0)
        self._sig_air_ref_ts = time.time()
        self._sig_target    = None
        self._sig_air_after = None
        self._sig_train_phase = 'await_target'
        self._sig_await_deadline = time.time() + self._SIG_AWAIT_SECONDS
        self._start_await_flash()
        self._update_sig_train_indicator()

    def _start_await_flash(self):
        """Beep once and start the B-instruction flash for a place/remove
        countdown (imminent-action cue)."""
        QApplication.beep()
        self._sig_await_flash_on = True
        self._sig_await_flash_timer.start()

    def _stop_await_flash(self):
        self._sig_await_flash_on = False
        timer = getattr(self, '_sig_await_flash_timer', None)
        if timer is not None:
            timer.stop()
        if hasattr(self, 'lbl_sig_train_instr'):
            self.lbl_sig_train_instr.setStyleSheet('')

    def _sig_await_flash_tick(self):
        self._sig_await_flash_on = not self._sig_await_flash_on
        self._update_sig_train_indicator()

    def _await_flash_style(self, remaining):
        if not self._sig_await_flash_on:
            return ''
        return self.MY_RED if remaining <= 5 else self.MY_YELLOW

    def _sig_enter_target(self, manual=False):
        """manual=True means Space forced the placement rather than auto-detect
        firing -- often because this target's |Δ| from air stays under Detect,
        sometimes just impatience.

        v1.41 used this to block removal auto-detect entirely: the removal test
        was then the placement comparison inverted, so it read 'removed' on the
        first settled frame of await_remove and skipped the removal wait (v1.40
        field failure). v1.54 replaced that test -- removal now needs a settle
        transient AND a departure from the target snapshot, neither of which
        holds on arrival -- so v1.55 lifted the block and auto-detect is tried
        for manual placements too. The flag still keeps Space permitted through
        the rest of the cycle without the override checkbox, which is the
        fallback when a target is too weak for either direction to fire."""
        self._stop_await_flash()
        self._sig_target_manual = manual
        self._sig_train_phase = 'target'
        self._sig_await_deadline = None
        self._sig_train_restart_buffer()

    def _sig_finish_target(self):
        if not self._sig_can_commit():
            return
        self._sig_target = self._sig_train_snapshot()
        # This removal needs its own transient -- arm from scratch (v1.54).
        self._sig_removal_armed = False
        self._sig_train_phase = 'await_remove'
        self._sig_await_deadline = time.time() + self._SIG_AWAIT_SECONDS
        self._start_await_flash()
        self._update_sig_train_indicator()

    def _sig_enter_air_trail(self):
        self._stop_await_flash()
        self._sig_train_phase = 'air_trail'
        self._sig_await_deadline = None
        self._sig_train_restart_buffer()

    def _sig_finish_air_trail(self):
        """Trailing air completes the signature; the buffer keeps rolling as
        the next cycle's leading air while the operator decides Save/Ignore."""
        if not self._sig_can_commit():
            return
        self._sig_air_after = self._sig_train_snapshot()
        stats = self._compute_sig_stats()
        self._sig_last_stats = stats
        self._set_sig_readout_from_stats(stats)
        # stats now hold everything Save needs (it reads _sig_last_stats +
        # placement widgets, never the raw slots) -- drop the slots so the
        # readout/Save gating go inert once the decision is made.
        self._sig_air_before = None
        self._sig_target     = None
        self._sig_air_after  = None
        # The air reference dies with the cycle (v1.52). It used to survive
        # into the next cycle's air_lead and keep ageing -- harmless to the
        # gate, which only consults it in await_target/await_remove and always
        # after a fresh lock, but the v1.51 Detect gauge read it every frame
        # and so displayed minutes of accumulated drift as a live deviation.
        self._sig_air_ref    = None
        self._sig_air_ref_ts = None
        # roll straight into the next leading air (same deque, no reset);
        # the next cycle re-arms auto-detect from scratch
        self._sig_target_manual = False
        self._sig_removal_armed = False
        self._sig_train_phase = 'air_lead'
        self._sig_start_sig_decide()
        self._update_sig_train_indicator()

    def _sig_train_abort(self, reason):
        """Discard the in-progress signature on a countdown timeout; the
        session stays live and returns to rolling leading air. The buffer is
        restarted so a stale window (e.g. target frames after a remove
        timeout) can't be mistaken for fresh air."""
        self._sig_air_before = None
        self._sig_target     = None
        self._sig_air_after  = None
        self._sig_air_ref    = None
        self._sig_air_ref_ts = None
        self._sig_await_deadline = None
        self._sig_target_manual = False
        self._sig_removal_armed = False
        self._stop_await_flash()
        self._sig_train_phase = 'air_lead'
        self._sig_train_restart_buffer()
        self.statusBar().showMessage('Training: ' + reason)
        self.lbl_sig_train_instr.setText(reason)
        self.lbl_sig_train_instr.setStyleSheet(self.MY_RED)
        self._update_sig_capture_gating()

    def _sig_train_restart_buffer(self):
        """New capture window: fresh deque (picks up a changed Frames value),
        zeroed glitch counter, back to the settling gate."""
        self._sig_capture_n = self.sp_sig_capture_n.value()
        self._sig_train_buf = deque(maxlen=self._sig_capture_n)
        self._sig_glitch_skipped = 0
        self._sig_train_status = 'settling'
        self._update_sig_train_indicator()

    @staticmethod
    def _central_frame_count(n_frames):
        """How many of `n_frames` survive pimd_features' central trim -- the
        count that actually feeds the stats, and the one quality_flags() tests
        against MIN_CENTRAL_FRAMES.

        Routed through central_frames() with the same throwaway Plateau that
        _compute_sig_stats() builds, rather than re-deriving the arithmetic, so
        the trim has one definition and cannot drift from what the corpus
        builder does to the very same window."""
        if n_frames <= 0:
            return 0
        plateau = pimd_features.Plateau(
            target_id='', short_name='', distance_mm=None, long_axis='na', face_normal='na',
            offset_x_mm=0, offset_y_mm=0, medium='air', repeat_idx=1, notes='',
            is_air=False, start_idx=0, end_idx=int(n_frames))
        c0, c1 = pimd_features.central_frames(plateau)
        return c1 - c0

    def _window_status_text(self, value_mv):
        """Gauge value text for a window reduction: the number plus the window's
        real duration, or the reason it is blank. Reads the state
        _window_frames() just wrote, so it must be called after the reduction."""
        if value_mv is None:
            if self._window_block_reason == 'stalled':
                span = self._window_span_s
                return ('STALLED {0:.0f} s'.format(span) if span else 'STALLED')
            return ''      # 'filling' is the ordinary startup case: plain '—'
        span = self._window_span_s
        if span is None:
            return '{0:.3f}'.format(value_mv)
        return '{0:.3f}  [{1:.1f} s]'.format(value_mv, span)

    def _nominal_frame_s(self):
        """Median FIRMWARE inter-frame interval over the recent buffer, or None
        until WINDOW_NOMINAL_MIN_N frames exist. Cached per frame --
        _window_frames() is called several times per frame (settle gate, both
        gauges, Shape Space) and this is the only part of it that touches more
        than n_win frames.

        The firmware clock, not arrival time -- see _fw_ms_buf for why arrival
        time cannot measure a frame period at all.

        Median, not mean, for the reason at WINDOW_NOMINAL_SAMPLE_N: it survives
        the very stalls the guard exists to catch. Through the whole 2026-07-29
        event the MCU still emitted bursts of consecutive frames one nominal
        period apart, so the median holds at nominal while the window's total
        span blows out -- which is exactly the signal wanted."""
        if self._nominal_frame_cache[0] == self._frame_count:
            return self._nominal_frame_cache[1]
        fw = list(self._fw_ms_buf)[-WINDOW_NOMINAL_SAMPLE_N:]
        val = None
        if len(fw) >= WINDOW_NOMINAL_MIN_N:
            d = np.diff(np.asarray(fw, dtype=float)) / 1000.0
            d = d[d > 0]
            if d.size:
                val = float(np.median(d))
        self._nominal_frame_cache = (self._frame_count, val)
        return val

    def _window_frames(self, n_win, exact=False):
        """The last `n_win` buffered frames, or None when the window cannot be
        trusted (v1.64). Every frame-count window in this file goes through
        here, so "how many frames" and "over how long" cannot drift apart again.

        Returns a list of (ts, arr) tuples -- unchanged in shape, so callers
        reduce exactly what they always did. None means don't reduce: either too
        few frames, or the window covers more than WINDOW_SPAN_TOLERANCE × the
        time it should, i.e. the stream stalled and the frames either side of the
        gap are not one measurement. `exact` requires the full n_win (the wander
        metric needs two genuinely adjacent windows, not two halves of whatever
        arrived).

        Span is measured on the FIRMWARE clock via the index-aligned _fw_ms_buf.
        Side effect by design: records that span and the refusal reason so the UI
        can say WHY a reading is blank. A blank nobody can explain is what let
        the 23:03 stall run for 47 minutes."""
        recent = list(self._rolling_buf)[-n_win:]
        self._window_span_s = None
        if len(recent) < 2 or (exact and len(recent) < n_win):
            self._window_block_reason = 'filling'
            return None

        fw = list(self._fw_ms_buf)[-len(recent):]
        nominal = self._nominal_frame_s()
        if len(fw) == len(recent):
            span = (fw[-1] - fw[0]) / 1000.0
            # A firmware clock that steps backwards (board reset mid-run) makes
            # the span meaningless rather than large: refuse on the same footing.
            if span < 0:
                self._window_block_reason = 'stalled'
                return None
            self._window_span_s = span
            if nominal:
                expected = (len(recent) - 1) * nominal
                if span > expected * WINDOW_SPAN_TOLERANCE:
                    self._window_block_reason = 'stalled'
                    return None
        self._window_block_reason = None
        return recent

    def _current_settle_mv(self, n_win=None):
        """Mean per-channel rolling std in mV over a window of frames -- the
        v1.31 settle-gate metric, unchanged. None if the window is unusable
        (treated as not settled) -- see _window_frames for the two ways.

        `n_win` defaults to the Stats tab's window; the Shape Space tab passes
        its own, much shorter one (a 50-frame window covers a whole sweep
        window, so a target appearing does not read settled for that long --
        fine for a corpus capture, far too slow for a live view).

        The REDUCTION is untouched at v1.64: same frames, same σ, no
        detrending. The 0.4 mV gate and every splithalf_floor/quality value in
        the corpora stay comparable; only demonstrably untrustworthy windows
        now return None instead of a number."""
        n_win  = n_win or self.sp_stats_window.value()
        recent = self._window_frames(n_win)
        if recent is None:
            return None
        mat = np.array([arr for _, arr in recent], dtype=float)
        return float(mat.std(0).mean()) / 1000.0

    def _current_dev_from_air(self):
        """Mean per-channel |Δ| in mV between the current settle-window median
        and the locked leading-air reference. None if no reference or too few
        frames / a channel-count mismatch (profile changed mid-cycle)."""
        if self._sig_air_ref is None:
            return None
        recent = self._window_frames(self.sp_stats_window.value())
        if recent is None:
            return None
        mat = np.array([arr for _, arr in recent], dtype=float) / 1000.0
        if mat.shape[1] != self._sig_air_ref.shape[0]:
            return None
        return float(np.abs(np.median(mat, axis=0) - self._sig_air_ref).mean())

    def _current_dev_from_target(self):
        """Mean per-channel |Δ| in mV between the current settle window and the
        TARGET snapshot -- how far the signal has moved away from what was just
        captured. None if there is no target snapshot or too few frames.

        This is the removal test's reference (v1.54), and the point of it is
        that it is seconds old rather than minutes: `_sig_target` is taken in
        _sig_finish_target(), immediately before await_remove begins. The old
        test asked whether the signal had come back to within Detect of the
        LEADING AIR, a reference by then a whole target window older -- and
        DESIGN §17.10 measured that as unable to work: at ~50 µV/s, 150 s of
        drift reads 5.2 mV where a spanner @60 mm reads 2.8 mV, so removing the
        object makes |Δ| from stale air go UP, not down."""
        if self._sig_target is None:
            return None
        ref = np.median(self._sig_target['frames_mV'], axis=0)
        recent = self._window_frames(self.sp_stats_window.value())
        if recent is None:
            return None
        mat = np.array([arr for _, arr in recent], dtype=float) / 1000.0
        if mat.shape[1] != ref.shape[0]:
            return None
        return float(np.abs(np.median(mat, axis=0) - ref).mean())

    def _current_air_wander_mv(self):
        """Mean per-channel |Δ| between the current settle window and the one
        immediately before it -- how far the air moves on its own over one
        window (≈7.2 s at 50 frames / 6.9 Hz measured, v1.64). None until two
        full windows are buffered.

        Same reduction and units as _current_dev_from_air(), so it is directly
        comparable to the Detect threshold: this is the floor Detect has to
        clear. It is what the Detect gauge shows when no cycle is gating on a
        locked reference -- unlike a frozen reference, it does not accumulate,
        so it reads the drift RATE rather than the drift total (v1.52).

        v1.64 routes it through _window_frames() like the other three. It had
        been written out on the argument that duplicated lines were cheaper than
        touching the gating hot path -- but the span guard has to hold on ALL
        four or a stall still gets read as noise through whichever one was
        skipped, and this metric spans TWO windows so it is the most exposed of
        them. `exact=True` keeps the original requirement that both halves be
        full, or "one window ago" is not one window ago."""
        n = self.sp_stats_window.value()
        if n < 2:
            return None
        recent = self._window_frames(2 * n, exact=True)
        if recent is None:
            return None
        mat  = np.array([arr for _, arr in recent], dtype=float) / 1000.0
        half = len(mat) // 2
        return float(np.abs(np.median(mat[half:], axis=0)
                             - np.median(mat[:half], axis=0)).mean())

    def _sig_train_ingest(self, now, raw, glitch_mask):
        """Per-frame training logic, called from process_packet."""
        settle_mv = self._current_settle_mv()
        settled = settle_mv is not None and settle_mv <= self.sp_sig_settle_mv.value()
        phase = self._sig_train_phase

        if phase in ('await_target', 'await_remove'):
            # Guard countdown + auto-detect. Both transitions now fire on the
            # same shape of test -- settled, and |Δ| from a FRESH reference
            # above Detect -- but each against its own reference: placement is
            # a departure from the locked air, removal a departure from the
            # target snapshot taken moments earlier (v1.54). The
            # placement/removal transient (unsettled) is skipped naturally.
            if self._sig_await_deadline is not None and now >= self._sig_await_deadline:
                self._sig_train_abort('timed out — signature discarded')
                return

            # Removal is a physical event: lifting the object unsettles the
            # signal before it re-settles somewhere else. Latch that transient
            # and require it, because drift never produces one -- it is what
            # separates "target lifted" from "reference aged" (§17.10), and it
            # is why a magnitude test alone could not be trusted here.
            if phase == 'await_remove' and not settled:
                self._sig_removal_armed = True

            dev = None      # stays None while unsettled -- the label shows σ then
            if settled:
                if phase == 'await_target':
                    dev = self._current_dev_from_air()
                    if dev is not None and dev > self.sp_sig_detect_mv.value():
                        self._sig_enter_target()
                        return
                # Runs for a Space-forced placement too (v1.55 lifted the v1.41
                # latch): the target snapshot exists however the phase was
                # entered, and neither half of this test can be satisfied on
                # arrival, so the v1.40 instant-skip cannot recur. A target too
                # weak to clear Detect going on will not clear it coming off
                # either -- that cycle simply falls through to Space, which
                # stays permitted for a manual placement.
                elif self._sig_removal_armed:
                    dev = self._current_dev_from_target()
                    if dev is not None and dev > self.sp_sig_detect_mv.value():
                        self._sig_enter_air_trail()
                        return
            self._update_sig_train_indicator(settle_mv, dev)
            return

        # Collecting phases (air_lead / target / air_trail).
        if not settled:
            if self._sig_train_status != 'settling':
                self._sig_train_buf.clear()
                self._sig_glitch_skipped = 0
                self._sig_train_status = 'settling'
            self._update_sig_train_indicator(settle_mv)
            return
        if glitch_mask.any():
            self._sig_glitch_skipped += 1
        else:
            self._sig_train_buf.append((now, raw.copy()))
        full = len(self._sig_train_buf) >= self._sig_train_buf.maxlen
        self._sig_train_status = 'ready' if full else 'collecting'
        if full and phase == 'target':
            self._sig_finish_target()           # enough target frames -> await removal
            return
        if full and phase == 'air_trail':
            self._sig_finish_air_trail()         # enough trailing air -> signature + decide
            return
        self._update_sig_train_indicator(settle_mv)

    def _update_sig_train_indicator(self, settle_mv=None, dev=None):
        """Renders A (colored status) and B (instruction). Stylesheet is only
        touched on state change; text may update every frame.

        A carries the live measurement against the gate that is currently
        holding the cycle up, so a stalled phase says *why* it is stalled: σ
        against Settle while unsettled, |Δ| against Detect once settled. The
        two await phases used to render one fixed string each ('WAITING for
        target…'), which left the operator watching a countdown with no idea
        whether the rig was still settling, or settled and just short of
        Detect. B stays the instruction, plus the countdown or the frame count
        for whichever window is filling (v1.56)."""
        if not self._analysis_training_active:
            self.lbl_sig_train_status.setText('Idle — press Start Training')
            self.lbl_sig_train_status.setStyleSheet('')
            self._sig_train_last_style = ''
            self.lbl_sig_train_instr.setText('')
            self.lbl_sig_train_instr.setStyleSheet('')
            return

        phase = self._sig_train_phase
        # subject for the collecting-phase labels (air_lead/target/air_trail)
        subj = 'target' if phase == 'target' else 'air'
        settle_thr = self.sp_sig_settle_mv.value()
        detect_thr = self.sp_sig_detect_mv.value()

        def vs_settle():
            """'σ0.412 > 0.400' -- the gate that is holding the phase up.

            Falls back to measuring it: the phase-transition call sites don't
            carry a settle value, and a label reading 'σ —' on every state
            change is exactly the uninformative thing v1.56 is fixing. Only the
            rare non-ingest callers pay for the extra reduction."""
            s = settle_mv if settle_mv is not None else self._current_settle_mv()
            if s is None:
                # v1.64: "filling" is only one of the two reasons now, and the
                # other one is an operator action item -- the stream stopped.
                # Re-reading the reason here is safe because the fallback above
                # has just re-run the reduction when settle_mv was None.
                if self._window_block_reason == 'stalled':
                    return 'σ — STREAM STALLED'
                return 'σ — (filling)'
            return 'σ{0:.3f} > {1:.3f}'.format(s, settle_thr)

        def vs_detect():
            if dev is None:
                return 'Δ — '
            return 'Δ{0:.3f} < {1:.3f}'.format(dev, detect_thr)

        # -- A: status colour + text --
        if phase == 'await_target':
            # Settled-but-short-of-Detect and still-settling are different
            # problems with different fixes (move it closer / stop touching the
            # bench), and the countdown alone cannot tell them apart.
            # MOVING/WAITING here, mirroring MOVING/MOVED in await_remove --
            # and never a bare 'SETTLING', which the collecting phases use with
            # a subject ('SETTLING air') and would read as the same state.
            if dev is None:
                a_text = 'MOVING — ' + vs_settle()
            else:
                a_text = 'WAITING target — ' + vs_detect()
            style = self.MY_YELLOW
        elif phase == 'await_remove':
            if not self._sig_removal_armed:
                # No transient yet: nothing has physically moved (v1.54).
                a_text, style = 'HOLDING target — lift it to release', self.MY_GREEN
            elif dev is None:
                a_text, style = 'MOVING — ' + vs_settle(), self.MY_YELLOW
            else:
                a_text, style = 'MOVED — ' + vs_detect(), self.MY_YELLOW
        elif self._sig_train_status == 'settling':
            a_text = 'SETTLING {0} — {1}'.format(subj, vs_settle())
            style = self.MY_YELLOW
        else:
            # '(N central)' is what survives pimd_features' 20/20 trim of the
            # window as it stands RIGHT NOW -- not the projected final count.
            # That makes it the answer to "what do I get if I Space out of here",
            # which is how a capture ends up stamped 'short'. Yellow while that
            # count is under MIN_CENTRAL_FRAMES extends the existing ladder
            # rather than fighting it (yellow already means not ready), so the
            # phase reads yellow -> blue -> green as frames bank up. An ACQUIRED
            # row still yellow means the Frames setting itself is too low.
            buf = self._sig_train_buf
            central = self._central_frame_count(len(buf))
            short = central < pimd_features.MIN_CENTRAL_FRAMES
            if self._sig_train_status == 'collecting':
                a_text = 'COLLECTING {0} — {1}/{2} ({3} central)'.format(
                    subj, len(buf), buf.maxlen, central)
                style = self.MY_YELLOW if short else self.MY_BLUE
            else:   # ready
                a_text = 'ACQUIRED {0} — {1}/{1} ({2} central)'.format(
                    subj, buf.maxlen, central)
                style = self.MY_YELLOW if short else self.MY_GREEN
        self.lbl_sig_train_status.setText(a_text)
        if style != self._sig_train_last_style:
            self.lbl_sig_train_status.setStyleSheet(style)
            self._sig_train_last_style = style

        # -- B: instruction (decision overlays air_lead; the place/remove
        # countdowns flash yellow, then red in the final 5 s) --
        b_style = ''

        def filling(label):
            """'<label> — 47/120 frames', or a settle note when the count is
            not the reason it is slow. Deliberately not 'window cleared': the
            status is the same on a first fill, where nothing was cleared."""
            buf = self._sig_train_buf
            if buf is None:
                return label
            if self._sig_train_status == 'settling':
                return '{0} — waiting for settle'.format(label)
            return '{0} — {1}/{2} frames'.format(label, len(buf), buf.maxlen)

        if self._sig_decide_pending:
            b_text = 'Save signature?'
        elif phase == 'await_target':
            rem = self._sig_await_remaining()
            b_text = 'Place target now — need Δ≥{0:.2f} mV — {1}s'.format(detect_thr, rem)
            b_style = self._await_flash_style(rem)
        elif phase == 'target':
            b_text = filling('Profiling target')
        elif phase == 'await_remove':
            rem = self._sig_await_remaining()
            # Auto-detect is attempted either way since v1.55, but a manual
            # placement is the case most likely to need the Space fallback, so
            # that label names both rather than promising auto-detect alone.
            b_text = ('Remove target — auto, or Space — {0}s' if self._sig_target_manual
                      else 'Remove target now — {0}s').format(rem)
            b_style = self._await_flash_style(rem)
        elif phase == 'air_trail':
            b_text = filling('Final air')
        elif self._sig_train_status == 'ready':   # air_lead ready
            b_text = 'Press Space'
        else:
            b_text = filling('Acquiring leading air')
        self.lbl_sig_train_instr.setText(b_text)
        self.lbl_sig_train_instr.setStyleSheet(b_style)

    def _sig_await_remaining(self):
        if self._sig_await_deadline is None:
            return int(self._SIG_AWAIT_SECONDS)
        return max(0, int(round(self._sig_await_deadline - time.time())))

    # -- Save / Ignore decision -----------------------------------------
    def _sig_start_sig_decide(self):
        self._sig_decide_pending = True
        self._sig_decide_flash_on = True
        self._sig_decide_flash_timer.start()
        self._update_sig_capture_gating()

    def _clear_sig_decide(self):
        self._sig_decide_pending = False
        self._sig_decide_flash_on = False
        timer = getattr(self, '_sig_decide_flash_timer', None)
        if timer is not None:
            timer.stop()
        for pb in (getattr(self, 'pb_sig_train_save', None),
                   getattr(self, 'pb_sig_train_ignore', None)):
            if pb is not None:
                pb.setStyleSheet('')

    def _sig_decide_flash_tick(self):
        self._sig_decide_flash_on = not self._sig_decide_flash_on
        self.pb_sig_train_save.setStyleSheet(self.MY_GREEN if self._sig_decide_flash_on else '')
        self.pb_sig_train_ignore.setStyleSheet(self.MY_YELLOW if self._sig_decide_flash_on else '')

    def _on_sig_train_save(self):
        # _on_sig_save_clicked's training-branch tail clears the decision and
        # resets the readout/gating (works for a direct pb_sig_save click too).
        if not self._sig_decide_pending:
            return
        self._on_sig_save_clicked()   # reads _sig_last_stats + placement widgets

    def _on_sig_train_ignore(self):
        if not self._sig_decide_pending:
            return
        self._clear_sig_decide()
        self._sig_last_stats = None
        self._update_sig_readout()
        self.statusBar().showMessage('Training: signature ignored')
        if self._analysis_training_active:
            self._update_sig_train_indicator()
        self._update_sig_capture_gating()

    def _reset_sig_capture_state(self, preserve_stats=False):
        """Ends any training session and clears the capture slots. With
        preserve_stats, the last computed signature (readout + Save) survives
        a Stop so an unsaved capture can still be saved."""
        self._analysis_training_active = False
        self._sig_train_phase    = 'air_lead'
        self._sig_train_status   = 'settling'
        self._sig_train_buf      = None
        self._sig_glitch_skipped = 0
        self._sig_air_ref        = None
        self._sig_air_ref_ts     = None
        self._sig_await_deadline = None
        self._sig_target_manual  = False
        self._sig_removal_armed  = False
        self._sig_air_before = None
        self._sig_air_after  = None
        self._sig_target     = None
        self._clear_sig_decide()   # always stop the flash; _sig_last_stats kept below if preserving
        self._stop_await_flash()
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

    @staticmethod
    def _hl_span(text, colour):
        return '<span style="background-color:{0};">&nbsp;{1}&nbsp;</span>'.format(colour, text)

    def _set_sig_readout_from_stats(self, stats):
        """Renders the readout label from a stats dict (or None). Split from
        _update_sig_readout so the training air-acquire can display a stats
        snapshot after the slots have already been shifted (v1.33).

        v1.38: each parameter carries its own green/amber/red background
        instead of the whole label going yellow on quality != 'ok'. "Is this a
        good capture?" was previously mental arithmetic against constants that
        live in pimd_features; the bands now come from the Green-when
        spinboxes, defaulted from those same constants.

        NOTE (deliberate, flagged): the amplitude bands read "more signal is
        better", so an intentional *air* capture -- where a large Amp/Mean|Δ|
        is the bad outcome -- will still colour green. Inverting the sense for
        target_id == 'air' is a separate decision, not made here."""
        if stats is None:
            self.lbl_sig_readout.setText('Amp: —  Mean|Δ|: —  Splithalf: —  SNR: —  Quality: —')
            self.lbl_sig_readout.setStyleSheet('')
        elif 'error' in stats:
            self.lbl_sig_readout.setText('Error: {0}'.format(stats['error']))
            self.lbl_sig_readout.setStyleSheet(self.MY_RED)
        else:
            amp = stats['plateau_amp_mV']
            mean_abs = stats['amp_mean_abs_mV']
            splithalf = stats['splithalf_floor']
            snr = amp / splithalf if splithalf > 1e-9 else float('inf')

            def amplitude_colour(value, threshold):
                if value >= threshold:
                    return _HL_GREEN
                return _HL_YELLOW if value >= threshold / 2.0 else _HL_RED

            amp_col = amplitude_colour(amp, self.sp_sig_q_amp_mv.value())
            mean_col = amplitude_colour(mean_abs, self.sp_sig_q_mean_mv.value())

            # Splithalf and SNR are the same quantity read two ways, so they
            # share one verdict rather than disagreeing on screen.
            ratio = self.sp_sig_q_split_ratio.value()
            if splithalf <= ratio * amp:
                noise_col = _HL_GREEN
            elif splithalf <= 1.5 * ratio * amp:
                noise_col = _HL_YELLOW
            else:
                noise_col = _HL_RED

            quality = stats['quality']
            quality_col = _HL_GREEN if quality == 'ok' else _HL_YELLOW

            note = '' if stats['used_air_after'] else '  (single air anchor — flat baseline)'
            self.lbl_sig_readout.setText(
                'Amp(L2): {0}  Mean|Δ|: {1}  Splithalf: {2}  SNR: {3}  Quality: {4}{5}'.format(
                    self._hl_span('{0:.3f}mV'.format(amp), amp_col),
                    self._hl_span('{0:.3f}mV'.format(mean_abs), mean_col),
                    self._hl_span('{0:.3f}mV'.format(splithalf), noise_col),
                    self._hl_span('{0:.1f}'.format(snr), noise_col),
                    self._hl_span(quality, quality_col),
                    note))
            # Spans carry the colour now -- a label-wide stylesheet would
            # paint the gaps between them too.
            self.lbl_sig_readout.setStyleSheet('')

    def _update_sig_capture_gating(self):
        if not hasattr(self, 'pb_sig_train_ignore'):
            return   # mid-build: the Training group runs this again once complete
        has_file = self._editable_sig_path is not None
        self.sig_target.setEnabled(has_file)
        self.sig_distance_mm.setEnabled(has_file)
        self.sig_long_axis.setEnabled(has_file)
        self.sig_medium.setEnabled(has_file)
        self.sig_repeat_idx.setEnabled(has_file)
        self.sp_sig_capture_n.setEnabled(has_file)
        self.sp_sig_settle_mv.setEnabled(has_file)
        self.sp_sig_detect_mv.setEnabled(has_file)
        self.cb_sig_train_override.setEnabled(has_file)
        self.pb_sig_train_start.setEnabled(has_file)
        self.pb_sig_train_save.setEnabled(self._sig_decide_pending)
        self.pb_sig_train_ignore.setEnabled(self._sig_decide_pending)
        stats = self._sig_last_stats
        self.pb_sig_save.setEnabled(
            has_file and stats is not None and 'error' not in stats
            and self.sig_target.currentData() is not None)
        item = self.lw_analysis_templates.currentItem()
        tpl = self._analysis_templates.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        self.pb_sig_delete.setEnabled(bool(tpl) and tpl['source'] == 'editable')

    # -- Signature file operations (New / Open for editing / Save / Delete) --

    def _on_sig_new_file_clicked(self):
        # A NEW corpus file still defaults into src/data/corpora/ rather than
        # the last-used directory: that is where the capture pipeline expects
        # corpora to be, and the last-used directory may well have been
        # somewhere a read-only corpus was browsed from.
        os.makedirs(CORPORA_DIR, exist_ok=True)
        default = os.path.join(CORPORA_DIR, 'gui_signatures_{0}.csv'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S')))
        path, _ = QFileDialog.getSaveFileName(
            self, 'New signature file', default, 'CSV files (*.csv)',
            options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return
        self._remember_sig_dir(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', newline='') as f:
            csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator='\n').writerow(
                pimd_features.CORPUS_HEADER_FIELDS)
        self._editable_sig_path = path
        self._editable_sig_session_id = 'gui_{0}'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
        self._editable_sig_seq = 0
        self._editable_repeat_counts = {}
        self._sig_autocheck_keys.clear()
        self._reset_sig_capture_state()
        self._merge_template_list({}, source='editable')
        self._update_sig_mode_label()
        self.statusBar().showMessage('New signature file: {0}'.format(path))

    def _on_sig_open_for_edit_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open signature file for editing', self._sig_dialog_dir(),
            'CSV files (*.csv)', options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return
        self._remember_sig_dir(path)
        # Editing appends v1.32+ rows via Save, so the file must already be that
        # schema (target_id/distance_mm/delta_mV). The old pimd_corpus_check
        # sniff gate rejected exactly these files (v1.37 fix).
        if not self._sig_file_is_new_schema(path):
            self.statusBar().showMessage(
                'Open for editing needs a v1.32+ signature file (target_id/distance_mm '
                'columns). Use "New file…" to start one, or "Load signatures…" to browse a '
                'legacy corpus read-only.')
            return
        try:
            sigs = self._scan_editable_signature_file(path)
        except Exception as e:
            self.statusBar().showMessage('Open failed: {0}'.format(e))
            return
        if sigs and QMessageBox.question(
                self, 'Open for editing',
                "'{0}' already has {1} signature(s). Add/Delete will modify this file directly. "
                "Continue?".format(os.path.basename(path), len(sigs)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        self._editable_sig_path = path
        self._editable_sig_session_id = 'gui_{0}'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
        # Forget this session's auto-check marks: the file's existing captures
        # should come back exactly as they are on disk (unticked), including
        # any saved earlier in this session and then deliberately unticked.
        self._sig_autocheck_keys.clear()
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
            # The capture's OWN geometry, read off its rows rather than assumed
            # from the live profile -- the Shape Space tab needs it to compute
            # band-wise features, and to tell a genuinely different profile
            # geometry from a merely different cell count (DESIGN §11).
            pulses_us = sorted({float(p[idx['pulse_us']]) for p in rows})
            n_bands   = len(pulses_us)
            sigs[key] = dict(
                shape=np.array([float(p[idx['delta_mV']]) for p in rows]),
                pulses_us=pulses_us,
                n_delays=(len(rows) // n_bands) if n_bands else 0,
                amp=float(first[idx['plateau_amp_mV']]), splithalf=float(first[idx['splithalf_floor']]),
                quality=first[idx['quality']],
                target_id=first[idx['target_id']], short_name=first[idx['short_name']],
                distance_mm=first[idx['distance_mm']], long_axis=first[idx['long_axis']],
                face_normal=first[idx['face_normal']], offset_x_mm=first[idx['offset_x_mm']],
                offset_y_mm=first[idx['offset_y_mm']], medium=first[idx['medium']],
                repeat_idx=first[idx['repeat_idx']],
                profile_name=first[idx['profile_name']],
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
        stringified so both sides compare equal.

        Field list and per-field normalisation both come from
        pimd_corpus_check rather than being restated here, so the app and the
        checker cannot drift on what "the same placement" is. The
        normalisation matters since v1.60: rows captured before it carry
        face_normal='z' and the widgets now yield 'na', so without it a
        placement fails to match its own history and repeat_idx restarts at 1
        (v1.62)."""
        return tuple(pimd_corpus_check.placement_value(f, sig[f])
                      for f in pimd_corpus_check.PLACEMENT_FIELDS)

    def _reload_editable_signature_list(self):
        if self._editable_sig_path is None:
            return
        sigs = self._scan_editable_signature_file(self._editable_sig_path)
        self._merge_template_list(sigs, source='editable')
        self._editable_repeat_counts = {}
        for sig in sigs.values():
            key = self._placement_tuple_key(sig)
            self._editable_repeat_counts[key] = self._editable_repeat_counts.get(key, 0) + 1
        # Resume numbering above the highest _cNN already in the file, NOT at
        # len(sigs) -- a deleted capture leaves a gap, and counting would then
        # hand the next save an id that already exists. Duplicate ids don't
        # error: the append succeeds, _scan_editable_signature_file() folds the
        # rows into the existing capture, len() stays put, and every further
        # save silently merges into the same id (v1.39 field failure).
        self._editable_sig_seq = max(
            [self._capture_id_seq(cid) for _, cid in sigs] or [0])
        # Re-suggest now the counts have moved (v1.62). Without this the
        # spinbox only ever updated on a placement-WIDGET change, so two
        # captures of one placement with nothing touched in between both saved
        # as r1 -- which is exactly what the 15:39 session on 2026-07-28 did.
        # Hooked here rather than at each caller: save, delete and file-open
        # all land on this one seam.
        self._update_sig_repeat_idx_suggestion()

    @staticmethod
    def _capture_id_seq(capture_id):
        """Trailing _cNN sequence number of a capture_id, 0 if unparseable."""
        tail = capture_id.rsplit('_c', 1)[-1]
        return int(tail) if tail.isdigit() else 0

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
                "selected) -- restart ClassViz to pick up registry edits, then pick "
                "again.".format(target_id))
            return
        short_name = self._targets[target_id].short_name if target_id in self._targets else ''

        existing = self._scan_editable_signature_file(self._editable_sig_path)
        for sig in existing.values():
            # every capture, not just the first -- a short/long shape means
            # either a mixed profile geometry or an id collision that folded
            # two captures together, and both must block the save
            existing_len = len(sig['shape'])
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

        # Last line of defence against a reused capture_id (see
        # _reload_editable_signature_list): a collision would append the rows
        # into an existing capture, where the scan folds them together and the
        # save vanishes from the list. Skip past anything already in the file.
        self._editable_sig_seq += 1
        capture_id = '{0}_c{1:02d}'.format(self._editable_sig_session_id, self._editable_sig_seq)
        while (self._editable_sig_session_id, capture_id) in existing:
            self._editable_sig_seq += 1
            capture_id = '{0}_c{1:02d}'.format(self._editable_sig_session_id, self._editable_sig_seq)
        captured_at = datetime.now().isoformat()

        rows = pimd_features.build_rows(
            self._editable_sig_session_id, capture_id, captured_at, plateau, colmap,
            stats['delta_mV'], stats['plateau_amp_mV'], stats['splithalf_floor'],
            stats['quality'], stats['amp_mean_abs_mV'], self._profile.get('name'), self._profile_sha8,
            self._parsed_fw_version(), 'pimd_classviz.py v{0}'.format(APP_VERSION),
            self.cb_supply.currentText(), self._editable_sig_path,
            pack_v=self._pack_v_value())
        # v1.65: the FILE's columns, not the tool's -- appending 26-field rows
        # under a 25-column header is what growing CORPUS_HEADER_FIELDS would
        # otherwise have done to every corpus captured before features v9.
        fields = self._corpus_fields_for_path(self._editable_sig_path)
        with open(self._editable_sig_path, 'a', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for row in rows:
                writer.writerow([row.get(k, '') for k in fields])
        # Mark it for auto-check *before* the reload rebuilds the list, so the
        # new row lands ticked and _merge_template_list's closing
        # _refresh_analysis_overlays() draws its overlay straight away. This
        # covers the automated Training cycle too (which saves through here),
        # by design -- everything captured this session is on the charts, and
        # "Clear signatures" is the way back out.
        self._sig_autocheck_keys.add((self._editable_sig_session_id, capture_id))
        self._reload_editable_signature_list()
        if self._analysis_training_active:
            # Keep the session running: the raw slots were cleared when the
            # signature was computed, so the readout goes to dashes and the
            # decision (flash + Save/Ignore) is retired until the next cycle.
            self._clear_sig_decide()
            self._sig_last_stats = None
            self._update_sig_readout()
            self._update_sig_train_indicator()
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

    # -- Session recording (alternate path to the Stats tab's Record ------
    # -- Session button -- same file format, same machinery) --------------

    def _on_sig_session_start(self):
        if not self.serial.isOpen() or self.pb_start.text() != 'Running':
            self.statusBar().showMessage('Connect and start streaming before recording a session.')
            return
        if self._recording:
            # v1.63: an auto-started session has only a generated notes line, so
            # Start *adopts* it -- prompt, append the operator's notes mid-file
            # and leave the recording running. Restarting would cost the frames
            # already logged, which is the opposite of what auto-logging is for.
            if self._session_autostarted:
                notes, ok = QInputDialog.getMultiLineText(
                    self, 'Session notes',
                    'Notes for this (auto-started) session:')
                if ok and notes.strip():
                    self._append_session_notes(notes)
                    self.statusBar().showMessage('Notes added to {0}'.format(self._session_path))
                return
            self.statusBar().showMessage('A session is already recording — stop it first.')
            return
        self._begin_session()   # notes=None -> interactive prompt, same as the plain Stats-tab flow

    def _begin_session(self, notes=None, auto=False):
        """Open a session dump and bring the Analysis tab's Session controls and
        the Stats tab's Record button into the recording state. Shared by the
        Session Start button and the v1.63 auto-start path so the two can't
        drift out of step; the pb_record sync is blockSignals'd because
        _session_start() has already done the work _toggle_record_frames would."""
        self._session_start(notes, auto=auto)
        self.pb_record.blockSignals(True)
        self.pb_record.setChecked(True)
        self.pb_record.blockSignals(False)
        self._analysis_session_recording = True
        self._set_sig_session_active_ui(True)
        self._update_sig_session_status_label()

    def _on_session_autolog_toggled(self, checked):
        self._session_autolog = checked
        if checked:
            # Re-arming by hand clears any suppression a previous Stop latched,
            # otherwise ticking the box would look like it did nothing.
            self._session_autolog_suppressed = False
            self._maybe_autostart_session('auto-log enabled')
        self._update_sig_session_status_label()

    def _maybe_autostart_session(self, trigger):
        """Open a session dump unattended, if one isn't already open and the
        operator hasn't opted out. Silent no-op in every refusing case -- this
        runs from stream start, training start and profile changes, none of
        which should nag. `trigger` names the caller in the notes line so the
        dump says why it exists."""
        if not self._session_autolog or self._session_autolog_suppressed:
            return
        if self._recording:
            return
        if not self.serial.isOpen() or self.pb_start.text() != 'Running':
            return
        profile_name = (self._profile or {}).get('name', 'unknown')
        self._begin_session(
            notes='(auto) {0}; {1} / {2}; supply {3}'.format(
                trigger, profile_name, self._profile_sha8, self.cb_supply.currentText()),
            auto=True)
        self.statusBar().showMessage('Auto-logging session: {0}'.format(self._session_path))

    def _on_sig_session_pause_toggled(self, checked):
        # process_packet's frame-write gate and the mark handler both read this
        # flag; _session_stop() clears it so a session stopped while paused
        # can't leave the next one silently recording nothing.
        self._session_paused = checked
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
        if self._session_paused:
            self.statusBar().showMessage('Paused — resume before marking.')
            return
        target_id = self.sig_target.currentData()
        if not target_id:
            self.statusBar().showMessage('Select a target before marking.')
            return
        if target_id != 'air' and target_id not in self._targets:
            self.statusBar().showMessage(
                "Target '{0}' is no longer in the registry -- restart ClassViz to pick "
                'up registry edits, then pick again.'.format(target_id))
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
            # Naming the suppression is the point: after an explicit Stop the
            # box is still ticked but nothing will auto-start until the stream
            # is restarted, and a silent "Not recording" would hide that.
            if self._session_autolog and self._session_autolog_suppressed:
                self.lbl_sig_session_status.setText('Not recording (auto-log off until restream)')
            elif self._session_autolog:
                self.lbl_sig_session_status.setText('Not recording (auto-log armed)')
            else:
                self.lbl_sig_session_status.setText('Not recording')
        else:
            self.lbl_sig_session_status.setText('Recording{0}{1}'.format(
                ' (auto)' if self._session_autostarted else '',
                ' (paused)' if self._session_paused else ''))

    # ------------------------------------------------------------------
    # Tab 3 — Family Plane Analysis (internally still `shape`; the tab was
    # called "Shape Space" up to v1.42)
    # ------------------------------------------------------------------
    # Human exploration of signature geometry: every loaded signature is a
    # point in a selectable 2-D feature space, with the current frame moving
    # through it as a live dot. The feature maths lives in pimd_shape.py (no
    # Qt there, so a classifier can import the same functions); everything
    # here is plumbing and drawing.
    #
    # Two rules the panels exist to enforce, both about not lying:
    #   - below the SNR gate the unit shape is normalised NOISE. It still has
    #     a family verdict and it still moves around the plane convincingly.
    #     So below the gate the live dot draws yellow (green at or above it)
    #     and leaves NO trail at all, loaded captures draw hollow in LOW_SNR
    #     grey, and gated-only is the default for every derived panel.
    #   - family() is a SIGN test and decay_persistence() is a magnitude test.
    #     A ferrite reads ferrous by sign and non-ferrous by decay. Both
    #     readouts are shown; neither is allowed to overrule the other.

    def _build_shape_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.addWidget(self._build_shape_ctrl_bar())

        # DockArea rather than nested QSplitters (what the Analysis tab uses):
        # five panels that each want the whole screen at different moments, so
        # they need to be floatable and re-orderable, not just resizable.
        self.shape_dock_area = DockArea()
        self.shape_docks = {}
        for name, size, builder in (
                ('Scatter',         (600, 500), self._build_shape_scatter_dock),
                ('Gauges',          (400, 230), self._build_shape_gauges_dock),
                ('Tile Inspector',  (400, 200), self._build_shape_tiles_dock),
                ('Band Curves',     (400, 200), self._build_shape_curves_dock),
                ('Crossing Ladder', (1000, 320), self._build_shape_ladder_dock)):
            dock = Dock(name, size=size)
            dock.addWidget(builder())
            self.shape_docks[name] = dock
        self._shape_apply_default_layout()
        layout.addWidget(self.shape_dock_area, stretch=1)

        self._shape_redraw_static()
        self._update_shape_gating()
        return w

    def _shape_apply_default_layout(self):
        """Scatter large on the left; right column top-to-bottom Gauges, Tile
        Inspector, Band Curves; Crossing Ladder along the bottom, full width.
        Also the 'Reset layout' target, so it has to work on docks that are
        currently floating or already placed -- moveDock() handles both."""
        # addDock() re-homes a dock that is already placed (it apoptoses the
        # old container) and pulls a floated one back out of its temp window,
        # so replaying the sequence is a complete re-layout -- no teardown
        # needed, and this works identically on first build and on Reset.
        area = self.shape_dock_area
        d = self.shape_docks
        area.addDock(d['Scatter'], 'left')
        area.addDock(d['Gauges'], 'right', d['Scatter'])
        area.addDock(d['Tile Inspector'], 'bottom', d['Gauges'])
        area.addDock(d['Band Curves'], 'bottom', d['Tile Inspector'])
        area.addDock(d['Crossing Ladder'], 'bottom')

    def _on_shape_reset_layout(self):
        self._shape_apply_default_layout()
        self.statusBar().showMessage('Family Plane Analysis: layout reset to default')

    def _shape_dock_state(self):
        """DockArea.saveState() as JSON-serialisable data, or None. Wrapped
        because a failure here must not cost the user every other setting in
        the file -- _save_settings runs from closeEvent()."""
        try:
            return self.shape_dock_area.saveState()
        except Exception:
            return None

    # -- Control bar --------------------------------------------------------

    def _build_shape_ctrl_bar(self):
        box = QGroupBox(SHAPE_TAB_TITLE)
        outer = QVBoxLayout(box)
        outer.setContentsMargins(6, 4, 6, 4)
        outer.setSpacing(3)
        row = QHBoxLayout()
        row.setSpacing(4)
        outer.addLayout(row)

        self.cb_shape_x = QComboBox()
        self.cb_shape_y = QComboBox()
        self.cb_shape_scale_x = QComboBox()
        self.cb_shape_scale_y = QComboBox()
        for caption, cb_axis, cb_scale in (
                ('X:', self.cb_shape_x, self.cb_shape_scale_x),
                ('Y:', self.cb_shape_y, self.cb_shape_scale_y)):
            row.addWidget(QLabel(caption))
            row.addWidget(cb_axis)
            for key, label in SHAPE_SCALES:
                cb_scale.addItem(label, key)
            cb_scale.setMaximumWidth(120)
            cb_scale.setToolTip(
                'Spacing along this axis only — every scale maps the drawn set\'s '
                'min/max onto themselves, so a point keeps its value and the ticks '
                'still read real feature units.\n'
                '"Expand ends" stretches the two extremes and compresses the middle: '
                'the family-plane axes are bounded, so both families press against '
                'opposite walls with the family decision boundary empty between them. '
                'Cube is gentle, atanh is stronger.\n'
                '"Rank" spaces the drawn points evenly — the most spread, but position '
                'stops meaning anything physical and moves as the drawn set changes.\n'
                'A log scale is deliberately absent: it expands near zero and '
                'compresses the extremes, which is the wrong way round here.')
            row.addWidget(QLabel('Scale:'))
            row.addWidget(cb_scale)
        row.addWidget(QLabel('Colour:'))
        self.cb_shape_colour = QComboBox()
        row.addWidget(self.cb_shape_colour)
        for key, label in SHAPE_AXES:
            self.cb_shape_x.addItem(label, key)
            self.cb_shape_y.addItem(label, key)
            self.cb_shape_colour.addItem(label, key)
        for key, label in SHAPE_COLOUR_EXTRA:
            self.cb_shape_colour.addItem(label, key)
        self.cb_shape_x.setCurrentIndex(0)          # early mean
        self.cb_shape_y.setCurrentIndex(2)          # late mean -- the family plane
        self.cb_shape_colour.setCurrentIndex(len(SHAPE_AXES))   # family
        for cb in (self.cb_shape_x, self.cb_shape_y, self.cb_shape_colour,
                   self.cb_shape_scale_x, self.cb_shape_scale_y):
            cb.currentIndexChanged.connect(self._on_shape_axis_changed)

        # One band-range pair PER AXIS (v1.43). With a single shared pair,
        # picking "custom band range" on both axes plotted a feature against
        # itself -- every point on the y=x diagonal, which looks like a
        # finding and is an artefact. Colour-by "custom band range" reads the
        # X pair; it has no third pair of its own.
        self.sp_shape_band_lo = QSpinBox()
        self.sp_shape_band_hi = QSpinBox()
        self.sp_shape_band_y_lo = QSpinBox()
        self.sp_shape_band_y_hi = QSpinBox()
        hi_max = max(0, self._n_bands - 1)
        for caption, (sp_lo, sp_hi) in (
                ('Custom bands X:', (self.sp_shape_band_lo, self.sp_shape_band_hi)),
                ('Y:',              (self.sp_shape_band_y_lo, self.sp_shape_band_y_hi))):
            row.addWidget(QLabel(caption))
            for sp in (sp_lo, sp_hi):
                sp.setRange(0, hi_max)
                sp.setMaximumWidth(48)
                sp.valueChanged.connect(self._on_shape_custom_range_changed)
                row.addWidget(sp)
            sp_hi.setValue(hi_max)
            sp_lo.setToolTip(
                'Inclusive band index range (0 = shortest pulse) behind the "custom band '
                'range" entry on this axis.\nThe X pair is also what colour-by "custom '
                'band range" reads.')

        row.addWidget(QLabel('SNR gate:'))
        self.sp_shape_gate = QDoubleSpinBox()
        self.sp_shape_gate.setRange(0.0, 1000.0)
        self.sp_shape_gate.setDecimals(1)
        self.sp_shape_gate.setSingleStep(0.5)
        self.sp_shape_gate.setValue(SHAPE_GATE_DEFAULT)
        self.sp_shape_gate.setMaximumWidth(70)
        self.sp_shape_gate.setToolTip(
            'Amp(L2)/splithalf below which a shape is not interpreted: stored captures '
            'draw hollow, the live cursor draws yellow instead of green, and it leaves '
            'no trail.\nDefault 5.0 = '
            '1/pimd_features.NOISY_RATIO_THRESHOLD, the same line that stamps a capture '
            "'noisy'.")
        self.sp_shape_gate.valueChanged.connect(self._on_shape_axis_changed)
        row.addWidget(self.sp_shape_gate)

        row.addWidget(QLabel('Trail:'))
        self.sp_shape_trail = QSpinBox()
        self.sp_shape_trail.setRange(0, SHAPE_TRAIL_MAX)
        self.sp_shape_trail.setValue(SHAPE_TRAIL_DEFAULT)
        self.sp_shape_trail.setMaximumWidth(60)
        self.sp_shape_trail.setToolTip(
            'Live-dot trail length, in frames. Only frames at or above the SNR gate '
            'leave a mark, but every frame ages the window along — so holding '
            'below-gate fades the trail out rather than freezing the last good pass.')
        row.addWidget(self.sp_shape_trail)

        self.cb_shape_labels = QCheckBox('Material tags')
        self.cb_shape_labels.setChecked(True)
        self.cb_shape_labels.setToolTip(
            'Draw the target\'s material beside each scatter point, and append it to each '
            'Crossing Ladder row: Al, Fe, SS, Cu, Brs…, with "base/plating" for a plated '
            'target (Fe/Zn).\nMaterial comes from the target registry, so a capture whose '
            'target_id is not in it (scratch objects, another rig\'s corpus) reads "?".\n'
            'Suppressed automatically above {0} drawn points.'.format(SHAPE_LABEL_MAX))
        self.cb_shape_labels.toggled.connect(self._on_shape_axis_changed)
        row.addWidget(self.cb_shape_labels)

        row.addStretch(1)

        # Same handler as the Analysis tab's button -- one loader, one store.
        pb_load = QPushButton('Load signatures…')
        pb_load.clicked.connect(self._on_load_signatures_clicked)
        row.addWidget(pb_load)

        self.pb_shape_air = QPushButton('Re-arm Air')
        self.pb_shape_air.setToolTip(
            'Drop the current air reference and start tracking fresh air.\n'
            'This tab keeps its OWN air reference — it does not touch the shared static '
            'baseline the Heatmap and Analysis tabs use.')
        self.pb_shape_air.clicked.connect(self._on_shape_rearm_air)
        row.addWidget(self.pb_shape_air)

        self.pb_shape_scratch = QPushButton('Save Scratch…')
        self.pb_shape_scratch.setToolTip(
            'Grab the object currently under the coil as an unregistered "scratch" '
            'capture, written to src/data/scratch/ — never to a corpus.\nIt is plotted '
            'immediately, as a triangle, and joins the Analysis tab\'s signature list '
            'under a △ prefix.')
        self.pb_shape_scratch.clicked.connect(self._on_shape_save_scratch)
        row.addWidget(self.pb_shape_scratch)

        pb_reset = QPushButton('Reset layout')
        pb_reset.clicked.connect(self._on_shape_reset_layout)
        row.addWidget(pb_reset)

        # -- Row 2: air tracking ------------------------------------------
        # Own spinboxes with their own persisted values, deliberately NOT
        # shared with the Analysis tab's Training group: exploration wants a
        # looser settle gate than corpus capture, and coupling them would mean
        # loosening the gate to wave things around silently loosened the
        # corpus too.
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        outer.addLayout(row2)
        row2.addWidget(QLabel('Air:'))

        row2.addWidget(QLabel('window'))
        self.sp_shape_win_n = QSpinBox()
        self.sp_shape_win_n.setRange(4, 500)
        self.sp_shape_win_n.setValue(SHAPE_WIN_N_DEFAULT)
        self.sp_shape_win_n.setToolTip(
            'Frames behind every live number on this tab: the shape itself, its split-half '
            'noise floor, the settle metric and the |Δ|-from-air test.\n'
            'Shorter responds faster and accumulates less drift; longer is quieter. This is '
            'NOT the Stats tab\'s "Std dev N" — 50 frames there is ~15 s, so a target would '
            'not read as settled for 15 s.')
        row2.addWidget(self.sp_shape_win_n)

        row2.addWidget(QLabel('frames'))
        self.sp_shape_air_n = QSpinBox()
        self.sp_shape_air_n.setRange(2, 2000)
        self.sp_shape_air_n.setValue(SHAPE_AIR_N_DEFAULT)
        self.sp_shape_air_n.setToolTip(
            'Frames in the rolling air buffer. Longer = a quieter reference but a '
            'slower response to drift, and longer before the air reads ready.')
        row2.addWidget(self.sp_shape_air_n)

        self.lbl_shape_air = QLabel('')
        self.lbl_shape_air.setToolTip(
            'Air state. Yellow = filling the air buffer, green = a full "frames" collected, '
            'blue = measuring against the snapshot. Space is the only thing that switches.')
        row2.addWidget(self.lbl_shape_air)
        row2.addStretch(1)
        self._shape_air_last_style = None
        return box

    def _on_shape_axis_changed(self, *_):
        self._shape_redraw_static()
        # sp_shape_gate routes through here, and it is the SNR gauge's marker
        # on the Analysis tab too.
        self._update_analysis_gauges()

    def _shape_band_spins(self, role):
        """The (lo, hi) spin pair for an axis role. Only 'y' has its own pair
        -- 'x' and the colour-by both read the X pair (see the control bar)."""
        if role == 'y':
            return self.sp_shape_band_y_lo, self.sp_shape_band_y_hi
        return self.sp_shape_band_lo, self.sp_shape_band_hi

    def _shape_band_saved(self, role, idx):
        """The custom band index to persist: the remembered preference where
        there is one, else whatever the spinbox holds."""
        pref = (self._shape_band_pref or {}).get(role)
        return pref[idx] if pref else self._shape_band_spins(role)[idx].value()

    def _on_shape_custom_range_changed(self, *_):
        """Keep lo <= hi without fighting the user mid-edit: nudge the other
        spinbox rather than snapping back the one being typed into. Only the
        pair the edited spinbox belongs to is touched."""
        sender = self.sender()
        for role in ('x', 'y'):
            sp_lo, sp_hi = self._shape_band_spins(role)
            if sender not in (sp_lo, sp_hi):
                continue
            lo, hi = sp_lo.value(), sp_hi.value()
            if lo > hi:
                other = sp_hi if sender is sp_lo else sp_lo
                other.blockSignals(True)
                other.setValue(lo if other is sp_hi else hi)
                other.blockSignals(False)
            # An operator edit is the new preference for THIS pair only -- the
            # other pair may be sitting clamped under a narrow profile, and
            # rewriting it from the spinbox would discard its wider choice.
            self._shape_band_pref[role] = (sp_lo.value(), sp_hi.value())
        self._shape_redraw_static()

    def _shape_custom_range(self, role='x'):
        sp_lo, sp_hi = self._shape_band_spins(role)
        lo, hi = sp_lo.value(), sp_hi.value()
        hi = min(hi, self._n_bands - 1)
        return min(lo, hi), hi

    def _shape_gate(self):
        return self.sp_shape_gate.value()

    # -- Docks --------------------------------------------------------------

    def _build_shape_scatter_dock(self):
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        # Standing banner, not a transient status-bar line: while foreign
        # geometries are on the plane the fact has to stay on screen, because
        # the numbers look perfectly ordinary.
        self.lbl_shape_foreign = QLabel('')
        self.lbl_shape_foreign.setWordWrap(True)
        self.lbl_shape_foreign.setStyleSheet(self.MY_YELLOW)
        self.lbl_shape_foreign.setVisible(False)
        v.addWidget(self.lbl_shape_foreign)

        self.shape_scatter_gw = pg.GraphicsLayoutWidget()
        self.shape_scatter_plot = self.shape_scatter_gw.addPlot()
        self._style_compact(self.shape_scatter_plot)
        self.shape_scatter_plot.showGrid(x=True, y=True, alpha=0.25)
        # The two zero rails. Held as attributes (v1.48) because a spacing
        # curve moves where the feature value 0 lands, and 0 is the one
        # reference on this plane worth drawing: it is the family decision
        # boundary. Angle 0 is the horizontal rail, so it tracks the Y axis.
        self.shape_zero_h = pg.InfiniteLine(pos=0, angle=0,
                                            pen=pg.mkPen('#bbbbbb', width=1))
        self.shape_zero_v = pg.InfiniteLine(pos=0, angle=90,
                                            pen=pg.mkPen('#bbbbbb', width=1))
        self.shape_scatter_plot.addItem(self.shape_zero_h)
        self.shape_scatter_plot.addItem(self.shape_zero_v)

        # Draw order matters: captures underneath, then the selection ring,
        # then the trail, then the live dot on top of everything.
        self.shape_scatter = pg.ScatterPlotItem(
            pxMode=True, hoverable=True, hoverSize=15,
            tip=lambda x, y, data: data['tip'] if isinstance(data, dict) else '')
        self.shape_scatter.sigClicked.connect(self._on_shape_point_clicked)
        self.shape_scatter_plot.addItem(self.shape_scatter)

        # Bigger than the live dot (18) so the selection reads as a ring
        # *around* a capture rather than competing with the live marker.
        self.shape_sel_marker = pg.ScatterPlotItem(
            pxMode=True, size=26, symbol='o', brush=None,
            pen=pg.mkPen('#000000', width=2))
        self.shape_scatter_plot.addItem(self.shape_sel_marker)

        self.shape_trail_item = pg.ScatterPlotItem(pxMode=True, symbol='o', pen=None)
        self.shape_scatter_plot.addItem(self.shape_trail_item)

        self.shape_live_item = pg.ScatterPlotItem(pxMode=True, symbol='o')
        self.shape_scatter_plot.addItem(self.shape_live_item)

        # Material tags. Pooled and reused rather than created per redraw:
        # addItem/removeItem on a few hundred TextItems every control change
        # is the expensive part, setText/setPos is not.
        self._shape_label_items = []
        self._shape_label_font = QFont()
        self._shape_label_font.setPointSize(7)

        self.lbl_shape_hint = pg.TextItem(anchor=(0.5, 0.5), color='#888888')
        self.shape_scatter_plot.addItem(self.lbl_shape_hint)
        v.addWidget(self.shape_scatter_gw, stretch=1)
        return box

    def _build_shape_curves_dock(self):
        self.shape_curves_gw = pg.GraphicsLayoutWidget()
        self.shape_curves_plot = self.shape_curves_gw.addPlot()
        self._style_compact(self.shape_curves_plot, title='Band mean vs pulse width (self-normalised)')
        self.shape_curves_plot.showGrid(x=True, y=True, alpha=0.25)
        self.shape_curves_plot.addItem(
            pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen('#888888', width=1)))
        self.shape_curves_plot.setYRange(-1.1, 1.1)
        # Static curves (selection + checked signatures) are rebuilt wholesale,
        # but only on load/selection/control changes. The live curve is a
        # single persistent item updated in place: rebuilding 66 checked
        # curves every redraw tick measured 65 ms against a 33 ms budget.
        self._shape_curve_items = []
        self.shape_curves_cross = pg.ScatterPlotItem(
            pxMode=True, size=12, symbol='x', pen=pg.mkPen('#000000', width=2), brush=None)
        self.shape_curves_plot.addItem(self.shape_curves_cross)
        # Yellow, like every other live indicator on this tab.
        self.shape_curves_live = self.shape_curves_plot.plot(
            [], [], pen=pg.mkPen(_hl_ink(_HL_YELLOW), width=3))
        self.shape_curves_live_cross = pg.ScatterPlotItem(
            pxMode=True, size=14, symbol='x',
            pen=pg.mkPen(_hl_ink(_HL_YELLOW), width=3), brush=None)
        self.shape_curves_plot.addItem(self.shape_curves_live_cross)
        return self.shape_curves_gw

    def _build_shape_ladder_dock(self):
        self.shape_ladder_gw = pg.GraphicsLayoutWidget()
        self.shape_ladder_plot = self.shape_ladder_gw.addPlot()
        self._style_compact(self.shape_ladder_plot, title='Crossing width by target (gated captures)')
        self.shape_ladder_plot.showGrid(x=True, alpha=0.25)

        # Sentinel rails: shaded, labelled, non-interactive. They are where
        # CROSS_ALREADY_POS / CROSS_NEVER land, so a target that never crosses
        # is visible as a fact rather than missing from the plot.
        self.shape_ladder_rails = []
        for colour in ('#d62728', '#1f77b4'):
            # setAlpha, not an 8-digit hex string: Qt reads '#xxxxxxxx' as
            # #AARRGGBB, so appending an alpha pair to an #RRGGBB silently
            # yields a completely different colour.
            fill = QColor(colour)
            fill.setAlpha(34)
            region = pg.LinearRegionItem(values=(0, 0), movable=False, brush=pg.mkBrush(fill),
                                          pen=pg.mkPen(None))
            region.setZValue(-10)
            self.shape_ladder_plot.addItem(region)
            self.shape_ladder_rails.append(region)
        self.shape_ladder_rail_labels = []
        for text, colour in (('positive by\nband 0', '#d62728'), ('never\ncrosses', '#1f77b4')):
            item = pg.TextItem(text, anchor=(0.5, 0.0), color=colour)
            item.setZValue(20)      # above the shaded rail it labels
            self.shape_ladder_plot.addItem(item)
            self.shape_ladder_rail_labels.append(item)

        self.shape_ladder_points = pg.ScatterPlotItem(
            pxMode=True, hoverable=True, hoverSize=14,
            tip=lambda x, y, data: data['tip'] if isinstance(data, dict) else '')
        # Same handler as the scatter (v1.43): the ladder is where an outlier
        # capture is spotted, so it has to be where that capture can be opened
        # in the Tile Inspector as well.
        self.shape_ladder_points.sigClicked.connect(self._on_shape_point_clicked)
        self.shape_ladder_plot.addItem(self.shape_ladder_points)
        # Selection ring, the scatter's in the ladder's coordinates.
        self.shape_ladder_sel = pg.ScatterPlotItem(
            pxMode=True, size=22, symbol='o', brush=None,
            pen=pg.mkPen('#000000', width=2))
        self.shape_ladder_sel.setZValue(12)
        self.shape_ladder_plot.addItem(self.shape_ladder_sel)
        # target_id -> ladder row, filled by _update_shape_ladder(); the row
        # order is by median crossing width, so nothing else can derive it.
        self._shape_ladder_rows = {}
        # Live frame gets its own row at the top of the ladder, in the same
        # visual language as the capture dots, plus a full-height line so its
        # crossing can be read straight down against every target's dots. A
        # bare vertical line on its own was too easy to mistake for grid.
        self.shape_ladder_live = pg.InfiniteLine(
            pos=0, angle=90, pen=pg.mkPen('#000000', width=2, style=Qt.PenStyle.DashLine))
        self.shape_ladder_live.setVisible(False)
        self.shape_ladder_plot.addItem(self.shape_ladder_live)
        self.shape_ladder_live_pt = pg.ScatterPlotItem(
            pxMode=True, hoverable=True, hoverSize=20,
            tip=lambda x, y, data: data['tip'] if isinstance(data, dict) else '')
        self.shape_ladder_live_pt.setZValue(15)
        self.shape_ladder_plot.addItem(self.shape_ladder_live_pt)
        self.shape_ladder_sep = pg.InfiniteLine(
            pos=0, angle=0, pen=pg.mkPen('#999999', width=1, style=Qt.PenStyle.DotLine))
        self.shape_ladder_sep.setVisible(False)
        self.shape_ladder_plot.addItem(self.shape_ladder_sep)
        self._shape_ladder_live_row = 0
        return self.shape_ladder_gw

    def _build_shape_tiles_dock(self):
        self.shape_tiles_gw = pg.GraphicsLayoutWidget()
        self.shape_tiles_plot = self.shape_tiles_gw.addPlot()
        self.shape_tiles_plot.invertY(True)     # band 0 (shortest pulse) at the top
        self._style_compact(self.shape_tiles_plot, title='Tile Inspector — no selection')
        self.shape_tiles_img = pg.ImageItem()
        self.shape_tiles_img.setColorMap(self.cm_div)   # red = positive/ferrous, blue = negative
        self.shape_tiles_plot.addItem(self.shape_tiles_img)
        return self.shape_tiles_gw

    # -- Gauge column (shared: Family Plane dock + Analysis trigger levels) ---

    def _build_gauge_column(self, specs, store, value_w=88):
        """A column of horizontal bars with numeric readouts. Each is its own
        mini plot rather than one shared axis -- the quantities have nothing in
        common numerically, and each needs its own threshold line.

        A spec is (key, row label, unit, binding). `binding` is None for a
        read-only gate line; otherwise (spinbox_attr, to_axis, from_axis),
        which makes the line draggable and writes the released position back to
        `self.<spinbox_attr>` through `from_axis`. The spinbox is named rather
        than passed because the Analysis column is built before the Family
        Plane tab exists, so `sp_shape_gate` cannot be resolved at build time.
        `to_axis`/`from_axis` are the value<->axis pair (identity everywhere
        except the log₁₀ amplitude bar).

        Each row is a two-line left block (name over readout) and then bar, all
        the way to the right edge. The readout used to sit in its own column to
        the RIGHT of the bar, which cost ~110 px of every row: the bar is the
        part being read, and at a 300 px column width it was down to ~130 px
        with its tick labels running into each other.

        `value_w` is the space the numeric readout reserves, and so the floor
        under the left block's width. 88 fits the Family Plane's 'air mode'
        word readout; a numbers-only column can go narrower."""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(4, 2, 4, 2)
        # Rows are two lines of text against a boxed plot; at the old 1 px they
        # ran together into one block and the eye had to find the boundaries.
        v.setSpacing(8)
        blocks = []
        for key, name, unit, binding in specs:
            row = QHBoxLayout()
            row.setSpacing(4)

            block = QWidget()
            block_v = QVBoxLayout(block)
            block_v.setContentsMargins(0, 0, 0, 0)
            block_v.setSpacing(0)
            lbl = QLabel(name)
            block_v.addWidget(lbl)
            readout = QHBoxLayout()
            readout.setSpacing(3)
            blocks.append(block)
            row.addWidget(block)

            # Height budget: the scale axis takes a fixed ~16 px and the
            # GraphicsLayout's default margins another ~18, so a 24 px strip
            # left the viewbox 4.5 px tall and the bar rendered as a hairline.
            # Zero the margins and give each row up to 46 px -> ~28 px of
            # viewbox. Min/max rather than setFixedHeight: four fixed 46 px
            # rows put a 191 px floor under the whole dock, which the dock
            # splitter then could not honour a saved layout against.
            gw = pg.GraphicsLayoutWidget()
            gw.setMinimumHeight(26)
            gw.setMaximumHeight(46)
            gw.ci.layout.setContentsMargins(0, 0, 0, 0)
            gw.ci.layout.setSpacing(0)
            plot = gw.addPlot()
            plot.hideAxis('left')
            plot.setMouseEnabled(x=False, y=False)
            plot.hideButtons()
            plot.setYRange(-0.5, 0.5, padding=0)
            font = QFont()
            font.setPointSize(7)
            ax = plot.getAxis('bottom')
            ax.setStyle(tickFont=font, tickLength=2)
            ax.setHeight(16)
            bar = pg.BarGraphItem(x0=[0], y=[0], height=0.8, width=[0], brush='#4caf50')
            plot.addItem(bar)
            gate_line = pg.InfiniteLine(pos=0, angle=90, movable=binding is not None,
                                        pen=pg.mkPen('#000000', width=1,
                                                      style=Qt.PenStyle.DashLine))
            if binding is not None:
                # A draggable gate is a control, not an annotation: widen the
                # grab area and light it on hover so it reads as one.
                gate_line.setHoverPen(pg.mkPen('#1565c0', width=2))
                gate_line.setCursor(Qt.CursorShape.SizeHorCursor)
                gate_line.sigPositionChangeFinished.connect(
                    lambda _line, s=store, k=key: self._on_gauge_marker_dragged(s, k))
            plot.addItem(gate_line)
            row.addWidget(gw, stretch=1)

            value = QLabel('—')
            value.setMinimumWidth(value_w)
            readout.addWidget(value)
            unit_lbl = QLabel(unit)
            readout.addWidget(unit_lbl)
            readout.addStretch(1)
            block_v.addLayout(readout)
            v.addLayout(row)
            store[key] = {'plot': plot, 'bar': bar, 'gate': gate_line, 'value': value,
                           'unit': unit_lbl, 'unit_text': unit, 'binding': binding}
        # One width for every left block, so all the bars start at the same x
        # (they already end at the same x -- nothing follows them now). A
        # per-row minimum can't do this: the widest name or readout would
        # shorten its own bar and the column would read as five unrelated
        # charts rather than one stack. Measured after the loop so the widest
        # readout string a row can hold is included, not just its label.
        if blocks:
            block_w = max(value_w, *(b.sizeHint().width() for b in blocks))
            for b in blocks:
                b.setFixedWidth(block_w)
        v.addStretch(1)
        return w

    def _on_gauge_marker_dragged(self, store, key):
        """A dragged gate line writes its new position back to the bound
        spinbox -- that spinbox is the real setting; the line is just a handle
        on it. The value is clamped to the spinbox's own range and rounded to
        its decimals, then the line is snapped to where the spinbox actually
        landed rather than left where the mouse was released."""
        g = store[key]
        spin_attr, to_axis, from_axis = g['binding']
        sp = getattr(self, spin_attr, None)
        if sp is None:
            return
        try:
            val = from_axis(float(g['gate'].value()))
        except (ValueError, OverflowError):
            return
        if not math.isfinite(val):
            return
        val = round(min(max(val, sp.minimum()), sp.maximum()), sp.decimals())
        # The spinbox's own valueChanged re-renders this column; the flag stops
        # that repositioning the line out from under the drag that caused it.
        self._gauge_marker_drag = True
        try:
            sp.setValue(val)
        finally:
            self._gauge_marker_drag = False
        g['gate'].setPos(to_axis(sp.value()))
        self._update_analysis_gauges()

    def _build_shape_gauges_dock(self):
        """The Family Plane's four gauges. Read-only gate lines (binding None)
        -- this tab reports against its thresholds, it does not set them. The
        amplitude BAR is log₁₀ but its readout is plain mV, so the label — not
        the unit column — carries the "(log)" note."""
        self.shape_gauges = {}
        return self._build_gauge_column([
            ('amp',      'Amp ‖Δ‖₂ (log)', '',     None),
            ('snr',      'SNR',            '',     None),
            ('settle',   'Settled',        'mV σ', None),
            ('baseline', 'Air age',        's',    None),
        ], self.shape_gauges)

    # -- Features -----------------------------------------------------------

    def _shape_invalidate_features(self):
        self._shape_feat_cache = {}
        self._shape_geom_warned = False

    def _shape_feature_dict(self, vec, pulses_us, n_delays, amp, splithalf):
        """The per-capture feature bundle every panel reads. `u` (the unit
        shape) is kept so the custom-band-range axis can be recomputed at draw
        time when the spinboxes move, without invalidating the whole cache."""
        n_bands = len(pulses_us)
        u = pimd_shape.unit_shape(vec)
        early, mid, late = pimd_shape.default_band_ranges(n_bands)
        snr = pimd_shape.snr(amp, splithalf)
        return {
            'vec': vec, 'u': u, 'pulses_us': pulses_us,
            'n_bands': n_bands, 'n_delays': n_delays,
            'early': pimd_shape.band_range_mean(u, early[0], early[1], n_bands, n_delays),
            'mid':   pimd_shape.band_range_mean(u, mid[0], mid[1], n_bands, n_delays),
            'late':  pimd_shape.band_range_mean(u, late[0], late[1], n_bands, n_delays),
            'crossing': pimd_shape.crossing_us(vec, pulses_us, n_delays),
            'decay':    pimd_shape.decay_persistence(vec, n_bands, n_delays),
            'log_amp':  math.log10(amp) if amp > 0 else float('nan'),
            'amp': amp, 'splithalf': splithalf, 'snr': snr,
            'family': pimd_shape.family(vec, n_bands, n_delays),
            # Defaults so a live-frame dict is structurally the same as a
            # capture's. Both are correct for the live frame by definition:
            # it is always on the live profile and is never a saved scratch.
            # The live frame has no registry entry, hence no material -- and
            # must not borrow the Analysis tab's selected target_id: what is
            # actually under the coil is exactly what this tab is asking.
            'foreign': False, 'is_scratch': False,
            'material_tag': '?', 'material_text': 'live frame (no registry entry)',
        }

    @staticmethod
    def _shape_material_abbrev(material):
        """Short tag for one registry material string. Unknown materials fall
        back to their first 3 letters Title-cased rather than to '?': a
        registry that gains a material should read as that material, not as
        missing data."""
        material = (material or '').strip().lower()
        if not material:
            return ''
        return SHAPE_MATERIAL_ABBREV.get(material) or material[:3].title()

    def _shape_material_tag(self, target_id):
        """(short tag, long text) for a capture's material, from the target
        registry. A plated target reads 'base/plating' (Fe/Zn) -- which layer
        the eddy currents actually see is the question this tab exists to
        explore, so the tag must not collapse it to one material.

        Anything the registry does not know reads '?' rather than a guess:
        scratch objects are unregistered by design, and a corpus captured on
        another rig can carry target_ids this registry has never seen."""
        target = self._targets.get(target_id)
        if target is None:
            if target_id == 'air':
                return 'air', 'air (no target)'
            return '?', 'material unknown — {0} is not in the target registry'.format(
                target_id or 'this capture')
        base = self._shape_material_abbrev(target.material_class)
        plating = self._shape_material_abbrev(target.plating_material)
        if plating and plating != base:
            return ('{0}/{1}'.format(base, plating),
                    '{0} plated {1}'.format(target.material_class, target.plating_material))
        return base or '?', target.material_class or 'unspecified'

    def _shape_capture_features(self):
        """Feature dicts for every loaded capture, keyed the same as
        self._analysis_templates. Cached; the cache is dropped whenever the
        store or the profile changes.

        Captures from a DIFFERENT profile geometry are included, not skipped
        (v1.42) -- but flagged `foreign` and drawn distinctly. The reasoning,
        since this is the one place in the app that does mix geometries:

        The overlay path in _refresh_analysis_overlays() must refuse, because
        it plots raw cell-by-cell curves where cell index N is a different
        (pulse, threshold) pair under a different profile -- superimposing
        those is meaningless. These features are not that: every pimd_shape
        function takes its geometry explicitly and normalises through it, so a
        crossing width is µs either way and a family verdict is a sign either
        way. They are comparable in KIND.

        They are NOT calibrated against each other -- a crossing is
        interpolated on that profile's own pulse ladder, and decay persistence
        reads that profile's own threshold columns -- so every foreign point
        is marked in the scatter, the ladder and the tile, and the Scatter dock
        carries a standing banner naming the count. This is a human
        exploration view, not a dataset: DESIGN §10's "frames from different
        profile geometries must never be mixed in one dataset" governs corpus
        builds, and nothing here writes one. Scratch saves still refuse a
        geometry mismatch outright.

        Genuinely unusable captures (a shape that isn't a rectangular
        n_bands x n_delays, or too few bands/delays for the features to be
        defined) are still dropped."""
        unusable = 0
        for key, tpl in self._analysis_templates.items():
            if key in self._shape_feat_cache:
                continue
            pulses_us = list(tpl.get('pulses_us') or self._pulse_us_sorted)
            n_delays  = int(tpl.get('n_delays') or self._n_cells)
            vec = np.asarray(tpl['shape'], dtype=float)
            try:
                feat = self._shape_feature_dict(
                    vec, pulses_us, n_delays, tpl['amp'], tpl['splithalf'])
            except ValueError:
                unusable += 1
                self._shape_feat_cache[key] = None
                continue
            target_id = tpl.get('target_id') or ''
            foreign = (len(pulses_us) != self._n_bands or n_delays != self._n_cells
                       or (tpl.get('profile_name') or self._profile.get('name'))
                       != self._profile.get('name'))
            mat_tag, mat_text = self._shape_material_tag(target_id)
            feat.update({
                'key': key, 'label': tpl['label'], 'target_id': target_id,
                'short_name': tpl.get('short_name', ''),
                'distance_mm': tpl.get('distance_mm', ''),
                'quality': tpl.get('quality', ''), 'session': tpl.get('session', ''),
                'is_scratch': target_id.startswith(SCRATCH_ID_PREFIX),
                'profile_name': tpl.get('profile_name', ''),
                'geom': '{0}×{1}'.format(len(pulses_us), n_delays),
                'foreign': foreign,
                'material_tag': mat_tag, 'material_text': mat_text,
            })
            self._shape_feat_cache[key] = feat
        if unusable and not self._shape_geom_warned:
            self._shape_geom_warned = True
            self.statusBar().showMessage(
                'Family Plane Analysis: dropped {0} capture(s) whose cell count is not '
                'a rectangular band × delay geometry'.format(unusable))
        return {k: v for k, v in self._shape_feat_cache.items()
                if v is not None and k in self._analysis_templates}

    # -- Air reference ------------------------------------------------------
    # Two modes, toggled by Space and by nothing else. See the block comment
    # on _shape_air_mode in __init__.
    #
    # A previous revision auto-froze the reference when mean |Δ| crossed a
    # Detect threshold and auto-released when it fell back, with a settle gate
    # in front of both. All of that is gone by direction. One measured fact is
    # worth keeping as to why it was never going to be reliable anyway: an
    # absolute |Δ| against a frozen reference cannot detect removal under
    # drift, because after a long hold the accumulated drift exceeds the
    # target's own |Δ| — a spanner @60 mm reads |Δ| 2.8 mV while 150 s of
    # drift reads 5.2 mV, so taking the object away makes |Δ| go *up*.

    def _shape_air_held(self):
        return self._shape_air_mode == 'measure'

    def _shape_air_restart(self):
        """Back to air mode with a fresh, empty buffer.

        The buffer is cleared rather than kept: the counter restarting at 0
        and the indicator going back to yellow is what makes the mode change
        unambiguous at a glance, and anything collected during a measurement
        had a target in front of the coil."""
        self._shape_air_mode   = 'air'
        self._shape_air_buf    = deque(maxlen=max(2, self.sp_shape_air_n.value()))
        self._shape_air_ref    = None
        self._shape_air_ref_ts = None
        self._shape_trail.clear()

    def _shape_air_ingest(self, now, raw, glitch_mask):
        """Per-W-frame air tracking, called from process_packet before the
        live features are computed (they read the reference this maintains).

        In 'measure' this does nothing at all -- the reference is frozen and
        only Space moves the mode."""
        if self._shape_air_buf is None or self._shape_air_buf.maxlen != max(
                2, self.sp_shape_air_n.value()):
            # Picks up a changed Air-frames value; deque(maxlen) is immutable.
            old = list(self._shape_air_buf or [])
            self._shape_air_buf = deque(old, maxlen=max(2, self.sp_shape_air_n.value()))

        if self._shape_air_held():
            return

        # Glitch frames stay excluded. That is the existing 64-frame
        # ADC-artifact median filter (440-880 mV bit-truncation events), not
        # one of the removed thresholds -- one of those in the reference would
        # corrupt every subsequent measurement.
        if not glitch_mask.any():
            self._shape_air_buf.append(raw / 1000.0)
        if len(self._shape_air_buf) >= 2:
            self._shape_air_ref = np.median(np.array(self._shape_air_buf, dtype=float), axis=0)
            self._shape_air_ref_ts = now

    def _on_shape_air_space(self):
        """Space on the Shape Space tab -- the only thing that changes mode.

        air -> measure: snapshot the last 'frames' of air as a fixed
        reference and start showing cursor movement against it.
        measure -> air: back to rolling air, buffer cleared."""
        if self._shape_air_held():
            self._shape_air_restart()
            self.statusBar().showMessage('Family Plane Analysis: back to air capture')
            return
        n = len(self._shape_air_buf or ())
        if n < 2:
            self.statusBar().showMessage(
                'Family Plane Analysis: need at least 2 air frames to take a reference '
                '(have {0})'.format(n))
            return
        # The reference is already the buffer's running median; measure mode
        # simply stops it being refreshed. Timestamp it here so the Air-age
        # gauge counts from the snapshot rather than from the last update.
        self._shape_air_mode   = 'measure'
        self._shape_air_ref_ts = time.time()
        self._shape_trail.clear()
        cap = self._shape_air_buf.maxlen
        self.statusBar().showMessage(
            'Family Plane Analysis: air reference taken on {0} frame(s){1} — Space returns to '
            'air'.format(n, '' if n >= cap else ' (thin: {0} of {1})'.format(n, cap)))

    def _shape_air_status(self):
        """(text, stylesheet) for the air status label. Three states on the
        Training group's colour ladder: yellow while the air buffer fills,
        green once it holds a full 'frames', blue while measuring."""
        buf = self._shape_air_buf
        n, cap = (len(buf), buf.maxlen) if buf is not None else (0, 0)
        if self._shape_air_held():
            return ('MEASURING — Space for air', self.MY_BLUE)
        if n < cap:
            return ('AIR {0}/{1}'.format(n, cap), self.MY_YELLOW)
        return ('AIR {0}/{1} — Space to measure'.format(n, cap), self.MY_GREEN)

    # -- Live frame ---------------------------------------------------------

    def _shape_live_window(self, ref=None, n_win=None):
        """(vec, splithalf) for the current frame, in mV -- BOTH derived from
        the same window, mirroring pimd_features.compute_plateau_stats():
        `vec` is the window's per-cell median minus the Shape Space AIR
        REFERENCE (not the shared static baseline — see the _shape_air_mode
        comment in __init__ for why a one-shot baseline cannot work here), and
        `splithalf` is the L2 of the two half-medians' difference, halved.
        (None, None) if there is no reference or too few frames.

        While the reference is rolling it is the median of very nearly these
        same frames, so `vec` is ~0 by construction and the dot sits at the
        centre. That is the intended idle state, not a degenerate one.

        The single window is the whole point, and it is worth spelling out
        because getting it wrong is silent. Amplitude and noise must be
        averaged over the SAME number of frames or their ratio is not an SNR.
        An earlier version took `vec` from _compute_analysis_matrix() (a mean
        over the Analysis tab's Avg-N frames, default 1) while the noise came
        from a 50-frame split-half: that inflates the ratio by roughly
        sqrt(N_window / N_avg), and bench-level air noise then cleared the 5.0
        gate on its own -- the live dot would have gone confidently coloured
        on nothing at all, which is exactly what the gate exists to prevent.

        `vec` is returned in pimd_shape's convention (band-major, pulse
        ascending, thresholds high->low), so live and stored shapes are
        directly comparable.

        `ref`/`n_win` default to this tab's own air reference and window. The
        Analysis tab's trigger-level gauges pass the Training cycle's locked
        leading air and the Stats window instead, so the amplitude they show is
        measured against the same reference the auto-detect gates use."""
        n_win  = n_win or self.sp_shape_win_n.value()
        recent = list(self._rolling_buf)[-n_win:]
        if len(recent) < 4:
            return None, None
        if ref is None:
            ref = self._shape_air_ref
        if ref is None:
            return None, None
        mat = np.array([arr for _, arr in recent], dtype=float) / 1000.0
        if mat.shape[1] != ref.size:
            return None, None
        delta = np.median(mat, axis=0) - ref
        vec = delta.reshape(self._n_bands, self._n_cells)[
            self._pulse_sort_order][:, self._cell_sort_order].reshape(-1)
        # The reference cancels in the half-difference, so the noise floor is
        # taken on the raw frames.
        half = len(mat) // 2
        splithalf = float(np.linalg.norm(
            np.median(mat[:half], axis=0) - np.median(mat[half:], axis=0)) / 2.0)
        return vec, splithalf

    def _shape_ingest_frame(self):
        """Per-W-frame live feature update, called from process_packet. Cheap
        (one reshape + a handful of reductions over n_channels values at the
        ~3 Hz sweep rate), and done regardless of which tab is visible so the
        trail is already populated when Shape Space is first shown.

        Only frames taken in 'measure' mode join the trail: in 'air' the
        reference is the running median of very nearly these same frames, so
        the cursor is pinned at the origin and a trail would say nothing."""
        vec, splithalf = self._shape_live_window()
        if vec is None or splithalf is None:
            self._shape_live = None
            return
        try:
            feat = self._shape_feature_dict(
                vec, list(self._pulse_us_sorted), self._n_cells,
                pimd_shape.amp_l2(vec), splithalf)
        except ValueError:
            self._shape_live = None
            return
        held = self._shape_air_held()
        feat['air_mode'] = self._shape_air_mode
        # Snapshot for the gauges and the hover tip. The drawing code does NOT
        # read it -- _shape_live_colour() re-tests snr against the gate as it
        # stands at redraw, so moving the gate recolours the trail already
        # captured rather than only the frames ingested after the change.
        feat['gated'] = feat['snr'] >= self._shape_gate()
        self._shape_live = feat
        if held:
            self._shape_trail.append(feat)
        else:
            self._shape_trail.clear()

    # -- Axis / colour dispatch ---------------------------------------------

    def _shape_axis_value(self, feat, key, role='x'):
        """Feature value for an axis/colour key. 'custom' is derived here (not
        cached) so the band-range spinboxes take effect immediately, and it
        reads `role`'s own spin pair -- pass 'y' for the Y axis."""
        if key == 'custom':
            lo, hi = self._shape_custom_range(role)
            return pimd_shape.band_range_mean(
                feat['u'], lo, hi, feat['n_bands'], feat['n_delays'])
        if key == 'distance':
            try:
                return float(feat['distance_mm'])
            except (TypeError, ValueError):
                return float('nan')
        return feat.get(key, float('nan'))

    def _shape_plot_value(self, feat, key, role='x'):
        """Axis value in PLOT coordinates -- log10 for the pulse-width axes,
        whose ticks are relabelled back to µs by _shape_axis_ticks(), then the
        axis's own spacing curve. Every consumer (capture spots, live cursor,
        trail, selection ring) goes through here, which is why the Scale combo
        needs no other wiring."""
        val = self._shape_axis_value(feat, key, role)
        if key in SHAPE_LOG_US_AXES:
            val = math.log10(val) if val and val > 0 else float('nan')
        return self._shape_scale_apply(val, role)

    # -- Axis spacing curves (v1.47) ----------------------------------------
    # See SHAPE_SCALES for why these exist and why none of them is a log.
    #
    # One invariant makes the rest tractable: every curve maps the drawn
    # captures' [lo, hi] onto ITSELF, and only the interior spacing changes.
    # So auto-range behaviour is untouched, a tick can always be labelled with
    # its true feature value, and switching scales never moves the view.

    def _shape_scale_key(self, role):
        cb = self.cb_shape_scale_y if role == 'y' else self.cb_shape_scale_x
        return cb.currentData() or 'linear'

    def _shape_scale_apply(self, val, role):
        """Map one plot value through `role`'s spacing curve. Identity unless
        _shape_build_scale_maps() found a usable domain."""
        fn = (self._shape_scale_map or {}).get(role)
        if fn is None or val is None or not np.isfinite(val):
            return val
        return fn(val)

    def _shape_build_scale_maps(self):
        """Rebuild both axes' spacing curves from the captures currently drawn.

        Called before _rebuild_shape_axes() (the ticks read the same domain),
        and derived from the CAPTURES only -- never from the live frame. The
        live cursor moves every frame; folding it into the domain would rescale
        the whole plane under itself several times a second."""
        self._shape_scale_map = {'x': None, 'y': None}
        self._shape_scale_domain = {'x': None, 'y': None}
        feats = self._shape_capture_features()
        for role, cb in (('x', self.cb_shape_x), ('y', self.cb_shape_y)):
            key = cb.currentData()
            scale = self._shape_scale_key(role)
            if scale == 'linear' or key in SHAPE_LOG_US_AXES:
                # The crossing axis owns its ticks (the profile's pulse ladder
                # plus the ≤pos / never sentinel rails); a second transform
                # would leave those labels pointing at the wrong rails.
                continue
            vals = np.array(
                [v for v in (self._shape_axis_value(f, key, role) for f in feats.values())
                 if v is not None and np.isfinite(v)], dtype=float)
            if vals.size < 2:
                continue
            lo, hi = float(vals.min()), float(vals.max())
            if not (hi > lo):
                continue
            self._shape_scale_map[role] = self._shape_scale_fn(scale, lo, hi, vals)
            self._shape_scale_domain[role] = (lo, hi)

    def _shape_zero_pos(self, role):
        """Where the feature value 0 lands on `role`'s axis.

        Left at a literal 0 when the axis has no curve, and also when 0 is
        outside the drawn range -- the curves clamp, so transforming an
        off-domain zero would pin the rail to the edge of the plot and draw a
        boundary line where there is no boundary. Off-view is the honest place
        for it, which is where a literal 0 already puts it."""
        dom = (self._shape_scale_domain or {}).get(role)
        if dom is None or not (dom[0] <= 0.0 <= dom[1]):
            return 0.0
        return self._shape_scale_apply(0.0, role)

    @staticmethod
    def _nice_step(raw):
        """Round a raw tick spacing up the 1-2-5 ladder."""
        if not np.isfinite(raw) or raw <= 0:
            return 1.0
        mag = 10.0 ** math.floor(math.log10(raw))
        for m in (1.0, 2.0, 5.0):
            if raw <= m * mag:
                return m * mag
        return 10.0 * mag

    def _shape_scale_ticks(self, role):
        """Ticks at round FEATURE values, positioned through the spacing curve
        -- so a tick labelled -0.150 sits wherever -0.150 actually landed and
        the axis stays readable as a measurement. None on a linear axis, where
        pyqtgraph's own ticks (and its SI prefix) are left alone."""
        fn = (self._shape_scale_map or {}).get(role)
        dom = (self._shape_scale_domain or {}).get(role)
        if fn is None or dom is None:
            return None
        lo, hi = dom
        step = self._nice_step((hi - lo) / 8.0)
        # Enough decimals to resolve one step, whatever the axis's units --
        # band-range means are ~0.1 and distances are tens of mm.
        decimals = max(0, min(6, int(math.ceil(-math.log10(step))) + 1))
        cand, v = [], math.ceil(lo / step) * step
        while v <= hi + step * 1e-6:
            # Snap the accumulated float back onto the step, or the tick that
            # should read 0.000 lands at -2.8e-17 and prints as '-0.000'.
            snapped = 0.0 if abs(v) < step * 1e-6 else v
            cand.append((fn(snapped), snapped))
            v += step

        # Thin out collisions (v1.48). Round feature values are evenly spaced in
        # VALUE, not in position -- and a curve that compresses the middle puts
        # several of them on the same few pixels, so under rank -0.050 / 0.000 /
        # 0.050 printed on top of each other. Greedy by priority, not left to
        # right: 0 goes in first so it survives, since it is the family
        # decision boundary and carries a drawn rail.
        #
        # Measured in PIXELS where the viewbox can say how wide it is: what
        # collides is label text, so a fixed fraction of the domain is either
        # wasteful on a wide dock or still overlapping on a narrow one. The
        # fraction is the fallback for the first pass, before layout.
        vb = self.shape_scatter_plot.getViewBox()
        pix = float(vb.width() if role == 'x' else vb.height())
        need_px = 52.0 if role == 'x' else 20.0     # a '-0.150' at 7pt, plus air
        min_sep = (hi - lo) * (need_px / pix if pix > 4 * need_px else 0.045)
        kept = []
        for pos, val in sorted(cand, key=lambda pv: abs(pv[1])):
            if all(abs(pos - p) >= min_sep for p, _ in kept):
                kept.append((pos, val))
        ticks = [(p, '{0:.{1}f}'.format(val, decimals))
                 for p, val in sorted(kept, key=lambda pv: pv[0])]
        return [ticks] if len(ticks) >= 2 else None

    @classmethod
    def _shape_scale_fn(cls, scale, lo, hi, vals):
        """(scale, domain, drawn values) -> a monotone callable on that domain.

        `rank` interpolates into the drawn set's ECDF rather than taking a
        literal rank, so the live cursor and the selection ring -- neither of
        which is IN the drawn set -- still land somewhere consistent."""
        span = hi - lo
        srt = np.sort(vals)

        def norm(v):
            return 2.0 * (v - lo) / span - 1.0

        def denorm(t):
            return lo + (t + 1.0) * span / 2.0

        if scale == 'rank':
            n = float(len(srt) - 1) or 1.0
            def fn(v):
                # Clamped at both ends: a live value outside the drawn range
                # has no rank, and pinning it to the edge is the honest answer.
                return denorm(2.0 * min(max(
                    float(np.searchsorted(srt, v, side='left')), 0.0), n) / n - 1.0)
        elif scale == 'atanh':
            def fn(v):
                t = min(max(norm(v), -0.999), 0.999)
                return denorm(math.atanh(t) / SHAPE_ATANH_K)
        else:                                    # 'cube'
            def fn(v):
                t = min(max(norm(v), -1.0), 1.0)
                return denorm(t ** 3)
        return fn

    def _shape_axis_ticks(self, key):
        """Tick spec for a plot axis, or None to leave pyqtgraph's automatic
        ticks alone. The crossing axis gets the profile's own pulse ladder
        plus a label on each sentinel rail, so 'never crosses' reads as a
        stated outcome instead of an unexplained cluster at 200."""
        if key not in SHAPE_LOG_US_AXES:
            return None
        ticks = [(math.log10(pimd_shape.CROSS_ALREADY_POS), '≤{0:.0f}\n(pos)'.format(
            self._pulse_us_sorted[0]))]
        ticks += [(math.log10(p), '{0:.0f}'.format(p)) for p in self._pulse_us_sorted]
        ticks.append((math.log10(pimd_shape.CROSS_NEVER), 'never'))
        return [ticks]

    def _shape_axis_label(self, key, role='x'):
        """Menu label for an axis key. 'custom' names the band range it is
        currently reading -- with a pair per axis, an unqualified 'custom band
        range' on both axes says nothing about what is being compared."""
        for k, label in SHAPE_AXES + SHAPE_COLOUR_EXTRA:
            if k == key:
                if k == 'custom':
                    lo, hi = self._shape_custom_range(role)
                    return 'custom bands {0}–{1}'.format(lo, hi)
                return label
        return key

    def _rebuild_shape_axes(self):
        """Reapply axis labels/ticks and resize the custom-band spinboxes to
        the live profile. Called on build and on every profile change."""
        if not hasattr(self, 'sp_shape_band_lo'):
            return
        hi_max = max(0, self._n_bands - 1)
        for role in ('x', 'y'):
            sp_lo, sp_hi = self._shape_band_spins(role)
            for sp in (sp_lo, sp_hi):
                sp.blockSignals(True)
                sp.setRange(0, hi_max)
                sp.blockSignals(False)
            pref = self._shape_band_pref.get(role)
            if pref is None:
                if sp_hi.value() == 0:
                    sp_hi.blockSignals(True)
                    sp_hi.setValue(hi_max)
                    sp_hi.blockSignals(False)
                continue
            # Re-apply the remembered pair against the range this profile can
            # actually represent (v1.49). The spins are only as wide as the
            # LIVE profile, so a Y pair of 4..6 restored while the app was
            # still on the 5-band startup profile came back as 4..4 -- clamped
            # by setValue() and never recovered when the 7-band profile
            # arrived and widened the range. Clamping here is display-only:
            # `pref` is left alone, so switching back to a wide profile
            # restores the full pair.
            lo = min(max(pref[0], 0), hi_max)
            hi = min(max(pref[1], lo), hi_max)
            for sp, val in ((sp_lo, lo), (sp_hi, hi)):
                sp.blockSignals(True)
                sp.setValue(val)
                sp.blockSignals(False)

        x_key = self.cb_shape_x.currentData()
        y_key = self.cb_shape_y.currentData()
        for axis_name, key, role in (('bottom', x_key, 'x'), ('left', y_key, 'y')):
            axis = self.shape_scatter_plot.getAxis(axis_name)
            scaled = self._shape_scale_ticks(role)
            ticks = scaled if scaled is not None else self._shape_axis_ticks(key)
            axis.setTicks(ticks)
            label = self._shape_axis_label(key, role)
            if scaled is not None:
                # The non-linear spacing has to be said, or the plane reads as
                # a measurement it is not.
                label += ' [{0}]'.format(self._shape_scale_key(role))
            # On AUTOMATIC ticks pyqtgraph's auto SI prefix is left on (its
            # default, and what every other plot in this file uses): band-range
            # means are ~0.1, so the axis renders them x1000 and says so in the
            # label.
            #
            # On EXPLICIT ticks it has to go off. Our tick strings already
            # carry full values, so a latched '(x0.001)' on the label is a flat
            # contradiction -- it reads -0.150 as -0.000150. Turning it off
            # does NOT clear the scale already latched into autoSIPrefixScale
            # (updateAutoSIPrefix re-latches it from the range on every
            # setRange, whatever the flag says), but that scale only ever
            # reaches tickStrings(), which explicit ticks bypass entirely. The
            # flag alone is what removes the suffix from the label.
            axis.enableAutoSIPrefix(ticks is None)
            axis.setLabel(label, **{'font-size': '7pt'})

        # A spacing curve needs a domain, which only the drawn captures give.
        for role, cb in (('x', self.cb_shape_scale_x), ('y', self.cb_shape_scale_y)):
            key = x_key if role == 'x' else y_key
            cb.setEnabled(key not in SHAPE_LOG_US_AXES)

        # Gridlines are dropped on a RANK axis (v1.48). Under the other scales
        # a gridline still marks a real feature value at its real position; a
        # rank axis is ordinal, so a grid over it draws a metric that is not
        # there. Per axis, since the scales are: rank on Y alone keeps the
        # vertical gridlines. The two zero rails stay either way -- they are
        # the family decision boundary, and are the only reference asked for.
        self.shape_scatter_plot.showGrid(
            x=self._shape_scale_key('x') != 'rank',
            y=self._shape_scale_key('y') != 'rank', alpha=0.25)
        # ...and they have to be MOVED, not left at plot 0: a curve maps the
        # feature value 0 to wherever it falls between the drawn min and max.
        self.shape_zero_v.setPos(self._shape_zero_pos('x'))
        self.shape_zero_h.setPos(self._shape_zero_pos('y'))

        # Band Curves and the Crossing Ladder both live on the log-µs axis.
        for plot in (self.shape_curves_plot, self.shape_ladder_plot):
            ax = plot.getAxis('bottom')
            ax.setTicks(self._shape_axis_ticks('crossing'))
            ax.setLabel('Pulse width (µs)', **{'font-size': '7pt'})

    # -- Drawing ------------------------------------------------------------

    def _shape_colour_for(self, feat, colour_key, gated, lo=None, hi=None):
        if not gated:
            return QColor(SHAPE_FAMILY_COLOURS[pimd_shape.LOW_SNR])
        if colour_key == 'none':
            return QColor('#1f77b4')
        if colour_key == 'family':
            return QColor(SHAPE_FAMILY_COLOURS.get(feat['family'], '#666666'))
        val = self._shape_axis_value(feat, colour_key)
        if not np.isfinite(val) or lo is None or hi is None or hi <= lo:
            return QColor('#666666')
        return self.cm_seq.map((val - lo) / (hi - lo), mode='qcolor')

    def _shape_redraw_static(self):
        """Everything that only changes when the store, the selection or a
        control-bar setting changes -- axes, capture points, the ladder, the
        tile. Cheap enough to just run on those events rather than per frame."""
        if not hasattr(self, 'shape_scatter'):
            return
        # Before the axes: the spacing curves define where the ticks land.
        self._shape_build_scale_maps()
        self._rebuild_shape_axes()
        self._update_shape_scatter_captures()
        self._update_shape_ladder()
        # Again, after the ladder: the scatter's pass through it ringed the
        # ladder row from the PREVIOUS layout, and rows are re-ordered by
        # median crossing width on every rebuild.
        self._update_shape_selection_marker()
        self._update_shape_tile()
        self._update_shape_curves()

    def _update_shape_scatter_captures(self):
        feats = self._shape_capture_features()
        x_key = self.cb_shape_x.currentData()
        y_key = self.cb_shape_y.currentData()
        colour_key = self.cb_shape_colour.currentData()
        gate = self._shape_gate()

        # Continuous colour-by needs the range over the drawn set first.
        lo = hi = None
        if colour_key not in ('family', 'none'):
            vals = [self._shape_axis_value(f, colour_key) for f in feats.values()]
            vals = [v for v in vals if np.isfinite(v)]
            if vals:
                lo, hi = min(vals), max(vals)

        # One material tag per (target, distance), not per capture: repeats of
        # the same target at the same distance land on top of each other, so
        # per-capture tags would draw the same string 3-5 times in the same
        # few pixels. Distance is in the key because the same target at a
        # different distance IS a visually separate cluster and needs its own.
        spots, labels, labelled = [], [], set()
        for key, feat in feats.items():
            x = self._shape_plot_value(feat, x_key, 'x')
            y = self._shape_plot_value(feat, y_key, 'y')
            if not (np.isfinite(x) and np.isfinite(y)):
                continue
            gated = feat['snr'] >= gate
            colour = self._shape_colour_for(feat, colour_key, gated, lo, hi)
            spots.append({
                'pos': (x, y),
                'size': 11 if feat['is_scratch'] else 9,
                # Symbol = (other profile?, scratch object?) -- see _SHAPE_SYMBOLS.
                'symbol': self._shape_marker_symbol(feat),
                # Filled = gated, hollow = below gate (the app's existing
                # convention for "this number is trustworthy").
                'brush': pg.mkBrush(colour) if gated else None,
                'pen': self._shape_marker_pen(colour, feat['foreign']),
                'data': {'key': key, 'tip': self._shape_tip(feat)},
            })
            tag_key = (feat['target_id'], feat['distance_mm'])
            if feat['material_tag'] and tag_key not in labelled:
                labelled.add(tag_key)
                labels.append((x, y, feat['material_tag'], colour))
        self.shape_scatter.setData(spots)
        self._update_shape_point_labels(labels)
        self._update_shape_foreign_banner(feats)

        empty = not spots
        self.lbl_shape_hint.setVisible(empty)
        if empty:
            self.lbl_shape_hint.setText(
                'No signatures loaded — use "Load signatures…" above\n'
                '(shares the Analysis tab\'s loaded set)')
            self.shape_scatter_plot.setXRange(-1, 1)
            self.shape_scatter_plot.setYRange(-1, 1)
            self.lbl_shape_hint.setPos(0, 0)
        else:
            # Re-enable auto-range: the empty-state setXRange/setYRange above
            # latches the view off auto, and the feature axes have wildly
            # different natural scales (early mean spans ~0.2, crossing µs
            # spans ~1.4 decades) -- an axis change with a latched view puts
            # every point off screen.
            self.shape_scatter_plot.enableAutoRange()
        self._update_shape_selection_marker()

    def _update_shape_point_labels(self, labels):
        """Material tags on the plane. `labels` is one (x, y, text, colour) per
        drawn (target, distance) group, taking the group's first point's
        position and colour — so a tag can never be a different colour from
        the marker it sits beside.

        Colour follows the marker rather than being a neutral grey: under
        colour-by family that makes the tag itself part of the verdict — a red
        'Al' is a non-ferrous material reading ferrous, which is the whole
        point of putting the material on the plane."""
        entries = ([(x, y, text, colour) for x, y, text, colour in labels if text]
                   if self.cb_shape_labels.isChecked() else [])
        if len(entries) > SHAPE_LABEL_MAX:
            entries = []
        while len(self._shape_label_items) < len(entries):
            item = pg.TextItem(anchor=(-0.25, 0.5))   # just right of the marker
            item.setFont(self._shape_label_font)
            item.setZValue(4)                          # under the live dot/trail
            self.shape_scatter_plot.addItem(item)
            self._shape_label_items.append(item)
        # Surplus items are hidden, not destroyed -- the pool is bounded by
        # SHAPE_LABEL_MAX and the next load probably needs them back.
        for i, item in enumerate(self._shape_label_items):
            if i >= len(entries):
                item.setVisible(False)
                continue
            x, y, text, colour = entries[i]
            item.setText(text, color=colour)
            item.setPos(x, y)
            item.setVisible(True)

    # Marker shape carries the two "this is not an ordinary corpus capture"
    # facts, because colour is spoken for (family / colour-by) and fill is
    # spoken for (gated). A dashed outline alone was tried first and reads
    # fine on a hollow marker but is nearly invisible on a filled 9 px one,
    # so shape does the work and the dash is kept as reinforcement.
    #   (foreign, scratch) -> symbol
    _SHAPE_SYMBOLS = {
        (False, False): 'o',      # circle   — live profile, registered target
        (False, True):  't1',     # triangle — live profile, scratch object
        (True,  False): 's',      # square   — other profile, registered target
        (True,  True):  'd',      # diamond  — other profile, scratch object
    }

    @classmethod
    def _shape_marker_symbol(cls, feat):
        return cls._SHAPE_SYMBOLS[(bool(feat['foreign']), bool(feat['is_scratch']))]

    @staticmethod
    def _shape_marker_pen(colour, foreign):
        """Outline for a capture marker; dashed for a foreign geometry, to
        reinforce the symbol (and to stay legible on hollow, below-gate
        markers where the fill can't help)."""
        return (pg.mkPen(colour, width=2, style=Qt.PenStyle.DashLine) if foreign
                else pg.mkPen(colour, width=2))

    def _update_shape_foreign_banner(self, feats):
        """Names the foreign geometries actually on screen. Counts and profile
        names, not a generic warning: 'these 12 came from cal_72_air_v3 (8×9)'
        is actionable, 'some data may differ' is not."""
        if not hasattr(self, 'lbl_shape_foreign'):
            return
        groups = {}
        for feat in feats.values():
            if not feat['foreign']:
                continue
            key = (feat['profile_name'] or 'unnamed profile', feat['geom'])
            groups[key] = groups.get(key, 0) + 1
        self.lbl_shape_foreign.setVisible(bool(groups))
        if not groups:
            return
        parts = ['{0} from {1} ({2})'.format(n, name, geom)
                 for (name, geom), n in sorted(groups.items())]
        self.lbl_shape_foreign.setText(
            '⚠ Mixed profile geometries — {0}, drawn as squares (diamonds if scratch) '
            'with dashed outlines. Live profile is {1} ({2}×{3}), drawn as circles '
            '(triangles if scratch). Features are comparable in kind but NOT calibrated '
            'across ladders: a crossing width is interpolated on its own profile\'s '
            'pulse ladder, and decay persistence reads its own threshold '
            'columns.'.format(' · '.join(parts), self._profile.get('name', '?'),
                              self._n_bands, self._n_cells))

    @staticmethod
    def _shape_tip(feat):
        cross = feat['crossing']
        if cross == pimd_shape.CROSS_NEVER:
            cross_txt = 'never'
        elif cross == pimd_shape.CROSS_ALREADY_POS:
            cross_txt = 'already positive'
        else:
            cross_txt = '{0:.1f} µs'.format(cross)
        tip = ('{0} @{1}\nmaterial: {2}\nfamily: {3}   crossing: {4}\ndecay: {5:.2f}\n'
               'amp: {6:.2f} mV   SNR: {7:.1f}\nquality: {8}'.format(
                   feat['target_id'] or '?',
                   '{0} mm'.format(feat['distance_mm']) if feat['distance_mm'] else 'air',
                   feat['material_text'],
                   feat['family'], cross_txt, feat['decay'], feat['amp'], feat['snr'],
                   feat['quality'] or '?'))
        if feat['foreign']:
            tip += '\n⚠ other profile: {0} ({1}) — not calibrated against the live one'.format(
                feat['profile_name'] or 'unnamed', feat['geom'])
        return tip

    def _update_shape_selection_marker(self):
        """The selection ring, on BOTH the scatter and the ladder -- a click in
        either has to be visible in the other, otherwise selecting from the
        ladder looks like it did nothing to the plane."""
        if not hasattr(self, 'shape_ladder_sel'):
            return          # mid-build: the ladder dock is created last
        feats = self._shape_capture_features()
        feat = feats.get(self._shape_selected_key)
        if feat is None:
            self.shape_sel_marker.setData([])
            self.shape_ladder_sel.setData([])
            return
        x = self._shape_plot_value(feat, self.cb_shape_x.currentData(), 'x')
        y = self._shape_plot_value(feat, self.cb_shape_y.currentData(), 'y')
        if np.isfinite(x) and np.isfinite(y):
            self.shape_sel_marker.setData([{'pos': (x, y)}])
        else:
            self.shape_sel_marker.setData([])

        # The ladder only carries gated captures, so a below-gate selection
        # legitimately has no row to ring.
        row = self._shape_ladder_rows.get(feat['target_id'] or '?')
        cross = feat['crossing']
        if row is None or feat['snr'] < self._shape_gate():
            self.shape_ladder_sel.setData([])
        else:
            self.shape_ladder_sel.setData([{'pos': (math.log10(cross), row)}])

    def _on_shape_point_clicked(self, _item, points, _ev=None):
        """Click handler for both the scatter and the ladder -- either one
        selects the capture, and every selection-driven panel (ring, Tile
        Inspector, Band Curves) follows from the one key."""
        if not len(points):
            return
        data = points[0].data()
        if not isinstance(data, dict) or 'key' not in data:
            return
        self._shape_selected_key = data['key']
        self._update_shape_selection_marker()
        self._update_shape_tile()
        self._update_shape_curves()

    def _update_shape_live_scatter(self):
        """Live cursor + trail.

        The cursor carries no family colour -- that verdict belongs to the
        loaded captures it is being compared against, and a cursor that took a
        family colour as it moved would read as the instrument asserting
        something it has not been asked to assert. It does carry the one
        verdict it can make about itself: yellow below the SNR gate, green at
        or above it (v1.45).

        The TRAIL is above-gate only (v1.50) -- a below-gate frame leaves no
        mark at all, so the trail is green by construction and draws just the
        part of a sweep that was worth reading. Below-gate frames still go into
        the buffer and still age the trail along, so sitting off-target fades
        the whole thing out within `Trail` frames rather than freezing the last
        good pass on screen.

        Both the cursor colour and the trail's membership are decided against
        the *current* gate rather than the `gated` flag stamped at ingest, so
        moving the SNR gate spinbox repaints and re-selects the trail already
        on screen instead of only affecting later frames."""
        feat = self._shape_live
        x_key = self.cb_shape_x.currentData()
        y_key = self.cb_shape_y.currentData()
        if feat is None:
            self.shape_live_item.setData([])
            self.shape_trail_item.setData([])
            return
        held = self._shape_air_held()
        if not held:
            # Air mode: the reference is the running median of very nearly
            # these frames, so the delta is ~0 -- pin to the origin where that
            # is the meaningful "no signal" point, and hide it where it isn't
            # (see SHAPE_CENTRED_AXES). Its computed position is not zero: the
            # residual's unit shape still has a definite direction from the
            # reference's half-window drift lag, which parked it inside the
            # non-ferrous cluster.
            if x_key not in SHAPE_CENTRED_AXES or y_key not in SHAPE_CENTRED_AXES:
                self.shape_live_item.setData([])
                self.shape_trail_item.setData([])
                return
            # Through the spacing curves, not a literal (0, 0): those map 0 to
            # itself only when the drawn range happens to be symmetric.
            x = self._shape_scale_apply(0.0, 'x')
            y = self._shape_scale_apply(0.0, 'y')
        else:
            x = self._shape_plot_value(feat, x_key, 'x')
            y = self._shape_plot_value(feat, y_key, 'y')
        if not (np.isfinite(x) and np.isfinite(y)):
            self.shape_live_item.setData([])
            self.shape_trail_item.setData([])
            return

        gate = self._shape_gate()
        self.shape_live_item.setData([{
            'pos': (x, y), 'size': 16, 'symbol': 'o',
            'brush': pg.mkBrush(self._shape_live_colour(feat, gate)),
            'pen': pg.mkPen('#000000', width=2)}])

        n_trail = self.sp_shape_trail.value()
        if not held or n_trail <= 0:
            self.shape_trail_item.setData([])
            return
        trail = list(self._shape_trail)[-n_trail:]
        green = _hl_qcolor(_HL_GREEN)
        spots = []
        for i, tf in enumerate(trail):
            # Below the gate the unit shape is normalised noise that still
            # wanders the plane convincingly, so it leaves no trail (v1.50).
            if not self._shape_above_gate(tf, gate):
                continue
            tx = self._shape_plot_value(tf, x_key, 'x')
            ty = self._shape_plot_value(tf, y_key, 'y')
            if not (np.isfinite(tx) and np.isfinite(ty)):
                continue
            # Age is the position in the WHOLE window, not among the drawn
            # points: a surviving mark has to keep fading as below-gate frames
            # push it back, or an old pass would sit at full brightness for as
            # long as nothing else got above the gate.
            frac = (i + 1) / len(trail)          # oldest faintest
            colour = QColor(green)
            colour.setAlpha(int(30 + 170 * frac))
            spots.append({'pos': (tx, ty), 'size': 4 + 5 * frac,
                          'brush': pg.mkBrush(colour), 'pen': None})
        self.shape_trail_item.setData(spots)

    @staticmethod
    def _shape_above_gate(feat, gate):
        """Is this frame's own shape above noise? Read against the gate passed
        in, not feat['gated'], so a gate change re-decides the trail already on
        screen."""
        snr = feat.get('snr')
        # snr is +inf when splithalf collapses to zero -- that is above any
        # gate. NaN compares False, which is the right answer for it.
        return snr is not None and snr >= gate

    @classmethod
    def _shape_live_colour(cls, feat, gate):
        """Live CURSOR colour: green at or above the SNR gate, yellow below it.
        Not a family verdict -- just whether this frame's own shape is above
        noise, which is the only thing the live cursor is entitled to say. The
        trail no longer needs this (v1.50): it draws above-gate frames only, so
        it is green throughout."""
        return _hl_qcolor(_HL_GREEN if cls._shape_above_gate(feat, gate) else _HL_YELLOW)

    @staticmethod
    def _shape_band_curve(feat):
        """(xs, ys) for one band-mean profile: log10 pulse widths against band
        means normalised to their own max |value|, so shapes compare without
        amplitude drowning the picture. None if the shape is all zero."""
        means = pimd_shape.band_means(feat['vec'], feat['n_bands'], feat['n_delays'])
        peak = float(np.max(np.abs(means)))
        if peak <= 0:
            return None
        return [math.log10(p) for p in feat['pulses_us']], means / peak

    def _update_shape_curves(self):
        """Static half of the Band Curves dock: the selected capture (bold) and
        the checked signatures. Rebuilt on load/selection/control changes only
        -- see _update_shape_curves_live() for the per-tick half."""
        if not hasattr(self, 'shape_curves_plot'):
            return
        for item in self._shape_curve_items:
            self.shape_curves_plot.removeItem(item)
        self._shape_curve_items = []

        feats = self._shape_capture_features()
        # Selection first (drawn bold), then whatever is checked in the shared
        # signature list -- the same "what am I comparing" control the
        # Analysis tab's overlays use.
        keys = []
        if self._shape_selected_key in feats:
            keys.append(self._shape_selected_key)
        for key in self._checked_template_keys():
            if key in feats and key not in keys:
                keys.append(key)

        cross_spots = []
        for i, key in enumerate(keys):
            feat = feats[key]
            curve_xy = self._shape_band_curve(feat)
            if curve_xy is None:
                continue
            colour = QColor(SHAPE_FAMILY_COLOURS.get(feat['family'], '#666666'))
            width = 3 if i == 0 and key == self._shape_selected_key else 1
            # Dashed here too, and for a sharper reason than elsewhere: a
            # foreign curve's points sit on ITS pulse ladder, so its vertices
            # need not line up with the live profile's x ticks at all.
            pen = pg.mkPen(colour, width=width,
                           style=Qt.PenStyle.DashLine if feat['foreign'] else Qt.PenStyle.SolidLine)
            self._shape_curve_items.append(self.shape_curves_plot.plot(*curve_xy, pen=pen))
            cross = feat['crossing']
            if cross not in (pimd_shape.CROSS_NEVER, pimd_shape.CROSS_ALREADY_POS):
                cross_spots.append({'pos': (math.log10(cross), 0.0)})
        self.shape_curves_cross.setData(cross_spots)

    def _update_shape_curves_live(self):
        """Live half of the Band Curves dock -- one persistent curve item
        updated in place, so a tick costs the same whether 1 or 66 signatures
        are checked. Drawn only in 'measure': in air mode the band profile is
        the normalised shape of a ~0 delta, i.e. noise."""
        if not hasattr(self, 'shape_curves_live'):
            return
        live = self._shape_live
        curve_xy = self._shape_band_curve(live) if (
            live is not None and self._shape_air_held()) else None
        if curve_xy is None:
            self.shape_curves_live.setData([], [])
            self.shape_curves_live_cross.setData([])
            return
        self.shape_curves_live.setData(*curve_xy)
        cross = live['crossing']
        self.shape_curves_live_cross.setData(
            [{'pos': (math.log10(cross), 0.0)}]
            if cross not in (pimd_shape.CROSS_NEVER, pimd_shape.CROSS_ALREADY_POS) else [])

    def _update_shape_ladder(self):
        """One row per target, sorted by median crossing width; one dot per
        gated capture. Below-gate captures are left out entirely -- an
        ungated crossing width is a coin toss, and putting it on the ladder
        would imply an ordering that isn't there.

        Row labels carry the material tag (v1.43): the ladder's whole claim is
        that crossing width orders targets by conductivity/permeability, and
        that claim is only readable if the material is on the row. One tag per
        row rather than per dot -- a row IS one target, so per-dot tags would
        be the same string repeated."""
        if not hasattr(self, 'shape_ladder_plot'):
            return
        feats = self._shape_capture_features()
        gate = self._shape_gate()
        by_target = {}
        for feat in feats.values():
            if feat['snr'] < gate:
                continue
            by_target.setdefault(feat['target_id'] or '?', []).append(feat)

        x_lo = math.log10(pimd_shape.CROSS_ALREADY_POS)
        x_hi = math.log10(pimd_shape.CROSS_NEVER)
        order = sorted(by_target, key=lambda t: float(
            np.median([f['crossing'] for f in by_target[t]])))
        tag_rows = self.cb_shape_labels.isChecked()
        spots, ticks = [], []
        self._shape_ladder_rows = {}
        for row, target in enumerate(order):
            self._shape_ladder_rows[target] = row
            tag = by_target[target][0]['material_tag']
            ticks.append((row, '{0}  [{1}]'.format(target, tag) if tag_rows and tag
                          else target))
            for feat in by_target[target]:
                colour = QColor(SHAPE_FAMILY_COLOURS.get(feat['family'], '#666666'))
                spots.append({
                    'pos': (math.log10(feat['crossing']), row),
                    'size': 10, 'symbol': self._shape_marker_symbol(feat),
                    'brush': pg.mkBrush(colour),
                    'pen': self._shape_marker_pen(QColor('#333333'), feat['foreign']),
                    # 'key' is what makes a ladder dot clickable into the Tile
                    # Inspector -- same payload shape as a scatter spot.
                    'data': {'key': feat['key'], 'tip': self._shape_tip(feat)},
                })
        # Reserve the top row for the live frame and label it, so there is
        # somewhere for the live dot to sit even before any target is
        # presented -- an empty row reads as "nothing live", which is honest;
        # a missing row reads as a bug.
        n_rows = max(1, len(order))
        self._shape_ladder_live_row = n_rows
        ticks.append((n_rows, '▶ LIVE'))
        self.shape_ladder_points.setData(spots)
        self.shape_ladder_plot.getAxis('left').setTicks([ticks])
        self.shape_ladder_plot.setYRange(-0.7, n_rows + 0.5, padding=0)
        self.shape_ladder_plot.setXRange(x_lo - 0.04, x_hi + 0.04, padding=0)
        self.shape_ladder_sep.setPos(n_rows - 0.5)
        self.shape_ladder_sep.setVisible(True)

        # Rails sit just outside the real pulse ladder, on the sentinel values.
        first, last = math.log10(self._pulse_us_sorted[0]), math.log10(self._pulse_us_sorted[-1])
        self.shape_ladder_rails[0].setRegion((x_lo - 0.04, (x_lo + first) / 2.0))
        self.shape_ladder_rails[1].setRegion(((last + x_hi) / 2.0, x_hi + 0.04))
        self.shape_ladder_rail_labels[0].setText(
            'positive by\n{0:.0f} µs'.format(self._pulse_us_sorted[0]))
        # Anchored just under the top of the target rows -- row 0 is the
        # bottom row, and n_rows is now the LIVE row, so n_rows - 0.6 is clear
        # of both the capture dots and the live marker.
        label_y = n_rows - 0.6
        self.shape_ladder_rail_labels[0].setPos((x_lo - 0.04 + (x_lo + first) / 2.0) / 2.0, label_y)
        self.shape_ladder_rail_labels[1].setPos(((last + x_hi) / 2.0 + x_hi + 0.04) / 2.0, label_y)

        self._update_shape_ladder_live()

    def _update_shape_ladder_live(self):
        """Live frame on the ladder: a marker on the reserved LIVE row plus a
        matching full-height line down through the target rows. Cheap enough
        to run every redraw tick (two setData calls), which is why it is split
        out of _update_shape_ladder()'s static rebuild.

        Yellow, like every other live indicator, and shown only in 'measure':
        in air mode the crossing width of a ~0 delta is meaningless, and
        putting it on an ordered ladder would imply a rank that isn't there."""
        if not hasattr(self, 'shape_ladder_live_pt'):
            return
        live = self._shape_live
        show_live = live is not None and self._shape_air_held()
        self.shape_ladder_live.setVisible(bool(show_live))
        if not show_live:
            self.shape_ladder_live_pt.setData([])
            return
        x = math.log10(live['crossing'])
        colour = _hl_ink(_HL_YELLOW)
        self.shape_ladder_live.setPos(x)
        self.shape_ladder_live.setPen(pg.mkPen(colour, width=2, style=Qt.PenStyle.DashLine))
        cross = live['crossing']
        if cross == pimd_shape.CROSS_NEVER:
            cross_txt = 'never crosses'
        elif cross == pimd_shape.CROSS_ALREADY_POS:
            cross_txt = 'already positive at {0:.0f} µs'.format(self._pulse_us_sorted[0])
        else:
            cross_txt = '{0:.1f} µs'.format(cross)
        self.shape_ladder_live_pt.setData([{
            'pos': (x, self._shape_ladder_live_row),
            'size': 16, 'symbol': 'd',
            # Bright fill behind a black outline, matching the scatter cursor;
            # the darker ink is only for the unfilled dashed line.
            'brush': pg.mkBrush(_hl_qcolor(_HL_YELLOW)), 'pen': pg.mkPen('#000000', width=2),
            'data': {'tip': 'LIVE frame\nfamily: {0}\ncrossing: {1}\ndecay: {2:.2f}\n'
                             'amp: {3:.2f} mV   SNR: {4:.1f}'.format(
                                 live['family'], cross_txt, live['decay'],
                                 live['amp'], live['snr'])},
        }])

    def _update_shape_tile(self):
        """The selected capture's raw cell matrix, self-normalised on a
        diverging map (red positive/ferrous, blue negative)."""
        if not hasattr(self, 'shape_tiles_img'):
            return
        feats = self._shape_capture_features()
        feat = feats.get(self._shape_selected_key)
        if feat is None:
            self.shape_tiles_img.clear()
            self.shape_tiles_plot.setTitle(
                'Tile Inspector — click a point on the plane or the ladder', size='7pt')
            return
        matrix = np.asarray(feat['vec'], dtype=float).reshape(feat['n_bands'], feat['n_delays'])
        lim = float(np.max(np.abs(matrix)))
        if lim <= 0:
            lim = 1.0
        self.shape_tiles_img.setImage(matrix.T, levels=(-lim, lim))
        # A foreign tile's own axes are drawn below, so the title has to say
        # whose ladder they are -- the picture is otherwise indistinguishable
        # from a live-profile capture.
        title = '{0} ({1}) @{2} — amp {3:.2f} mV, SNR {4:.1f}, {5} [{6}]'.format(
            feat['target_id'] or '?', feat['material_text'],
            '{0} mm'.format(feat['distance_mm']) if feat['distance_mm'] else 'air',
            feat['amp'], feat['snr'], feat['quality'] or '?', feat['session'])
        if feat['foreign']:
            title += '  ⚠ {0} ({1}), not the live profile'.format(
                feat['profile_name'] or 'other profile', feat['geom'])
        self.shape_tiles_plot.setTitle(title, size='7pt')

        ax_l = self.shape_tiles_plot.getAxis('left')
        ax_l.setTicks([[(i + 0.5, '{0:.0f}µs'.format(p))
                        for i, p in enumerate(feat['pulses_us'])]])
        ax_l.setLabel('Pulse width', **{'font-size': '7pt'})
        ax_b = self.shape_tiles_plot.getAxis('bottom')
        # Threshold labels come from the LIVE profile, so they are only
        # truthful for a capture on that same ladder.
        if feat['foreign']:
            ax_b.setTicks(None)
            ax_b.setLabel('Threshold column (own ladder)', **{'font-size': '7pt'})
        elif len(self._threshold_v_sorted) == feat['n_delays']:
            ax_b.setTicks([[(j + 0.5, '{0:.2f}V'.format(v))
                            for j, v in enumerate(self._threshold_v_sorted)]])
            ax_b.setLabel('Threshold', **{'font-size': '7pt'})
        else:
            ax_b.setTicks(None)
        self.shape_tiles_plot.setXRange(0, feat['n_delays'], padding=0)
        self.shape_tiles_plot.setYRange(0, feat['n_bands'], padding=0)

    def _set_gauge(self, store, key, value, lo, hi, threshold, text, good_above=True,
                   unit=None):
        """`unit` overrides the row's fixed unit suffix -- pass '' when the
        readout is a word rather than a number, so 'air mode' does not render
        as 'air mode s'."""
        g = store[key]
        g['unit'].setText(g['unit_text'] if unit is None else unit)
        g['plot'].setXRange(lo, hi, padding=0)
        # bool(), not the bare np.isfinite() result: that is an np.bool_, and
        # PyQt's setVisible() takes it as an index rather than a bool --
        # thousands of DeprecationWarnings per session at the redraw rate.
        has_value = value is not None and bool(np.isfinite(value))
        # A read-only gate is an annotation on a reading, so it goes away with
        # the reading. A draggable one is the control you set the threshold
        # with, so it stays -- Detect has no value at all until a cycle locks
        # an air reference, which is exactly when you want to pre-position it.
        g['gate'].setVisible(threshold is not None and (has_value or g['binding'] is not None))
        if threshold is not None and not g['gate'].moving:
            g['gate'].setBounds((lo, hi))
            g['gate'].setPos(min(max(threshold, lo), hi))
        if not has_value:
            g['bar'].setOpts(x0=[lo], width=[0])
            # v1.64: `text or '—'` rather than a bare '—', so a caller that knows
            # WHY there is no value can say so. Every pre-v1.64 caller passes ''
            # in this case, so their rendering is unchanged.
            g['value'].setText(text or '—')
            return
        clamped = min(max(value, lo), hi)
        if threshold is None:
            # Informational gauge: no pass/fail, so no gate line and a neutral
            # bar rather than a green/red verdict nobody asked for.
            brush = QColor('#9e9e9e')
        else:
            ok = (value >= threshold) if good_above else (value <= threshold)
            brush = _hl_qcolor(_HL_GREEN if ok else _HL_RED)
        g['bar'].setOpts(x0=[lo], width=[clamped - lo], brush=brush)
        g['value'].setText(text)

    def _shape_set_gauge(self, key, value, lo, hi, threshold, text, good_above=True,
                         unit=None):
        self._set_gauge(self.shape_gauges, key, value, lo, hi, threshold, text,
                        good_above=good_above, unit=unit)

    def _update_shape_gauges(self):
        """Amplitude / SNR / settledness / air age. Every input is an existing
        per-frame statistic (_current_settle_mv, the air reference timestamp,
        the Analysis tab's Green-when Amp threshold) -- nothing is recomputed
        here on its own terms. The settle and air thresholds are this tab's
        own, matching the gate the air state machine actually applies."""
        if not hasattr(self, 'shape_gauges'):
            return
        feat = self._shape_live
        gate = self._shape_gate()

        amp_threshold = self.sp_sig_q_amp_mv.value()
        if feat is None:
            self._shape_set_gauge('amp', None, -2, 3, math.log10(max(amp_threshold, 1e-3)), '')
            self._shape_set_gauge('snr', None, 0, max(20.0, gate * 2), gate, '')
        else:
            log_amp = feat['log_amp']
            self._shape_set_gauge(
                'amp', log_amp, -2, 3, math.log10(max(amp_threshold, 1e-3)),
                '{0:.2f} mV'.format(feat['amp']))
            self._shape_set_gauge(
                'snr', feat['snr'], 0, max(20.0, gate * 2), gate,
                '∞' if not np.isfinite(feat['snr']) else '{0:.1f}'.format(feat['snr']))

        settle_mv = self._current_settle_mv(self.sp_shape_win_n.value())
        # Informational only -- there is no settle threshold on this tab any
        # more, so no gate line and no pass/fail colour. Still worth showing:
        # "is the rig quiet right now" is useful context for a reading.
        self._shape_set_gauge(
            'settle', settle_mv, 0, max((settle_mv or 0.0) * 2, 1.0), None,
            '' if settle_mv is None else '{0:.3f}'.format(settle_mv))

        # Age of the SNAPSHOT. In air mode the reference is refreshed every
        # frame, so an age would be meaningless -- the bar goes empty and the
        # readout says which mode it is in.
        if self._shape_air_held() and self._shape_air_ref_ts is not None:
            age = time.time() - self._shape_air_ref_ts
            text = '{0:.0f}'.format(age)
        else:
            age, text = None, 'air mode'
        self._shape_set_gauge(
            'baseline', age, 0, SHAPE_AIR_AMBER_S * 1.5, SHAPE_AIR_AMBER_S,
            text, good_above=False, unit=None if age is not None else '')
        if age is None:
            self.shape_gauges['baseline']['value'].setText(text)

    def _update_shape_live(self):
        """Per-redraw refresh of everything the live frame drives. The static
        panels (capture points, ladder rows, tile) are NOT rebuilt here --
        they only change on load/selection/control changes."""
        self._update_shape_air_status()
        self._update_shape_live_scatter()
        self._update_shape_curves_live()
        self._update_shape_ladder_live()
        self._update_shape_gauges()
        self._update_shape_gating()

    def _update_shape_air_status(self):
        """Air status label. Stylesheet is only touched on a state change --
        the same churn guard the Training group's indicator uses."""
        if not hasattr(self, 'lbl_shape_air'):
            return
        text, style = self._shape_air_status()
        self.lbl_shape_air.setText(text)
        if style != self._shape_air_last_style:
            self.lbl_shape_air.setStyleSheet(style)
            self._shape_air_last_style = style

    def _update_shape_gating(self):
        if not hasattr(self, 'pb_shape_scratch'):
            return
        self.pb_shape_scratch.setEnabled(self._shape_scratch_blocker() is None)

    def _shape_scratch_blocker(self):
        """None when a scratch capture can be taken, else the reason why not
        (used both to gate the button and to explain it in the status bar).

        Deliberately only two conditions: measure mode, and enough frames
        since the snapshot. No hidden SNR or settledness threshold greys the
        button out -- you save what you can see, and a thin or noisy capture
        is stamped honestly by pimd_features.quality_flags() instead."""
        if not self._shape_air_held() or self._shape_air_ref is None:
            return 'in air mode — press Space to take a reference first'
        if self._shape_live is None:
            return 'no live frame yet'
        since = self._shape_air_ref_ts or 0.0
        if sum(1 for ts, _ in self._rolling_buf if ts >= since) < 2:
            return 'not enough frames since the air reference — hold a moment longer'
        return None

    def _on_shape_rearm_air(self):
        """Drop the air reference and start tracking fresh air.

        Deliberately does NOT call _start_capture(): this tab keeps its own
        reference (see _shape_air_mode in __init__), and having a Shape Space
        button mutate the baseline the Heatmap and Analysis tabs share would
        be a side effect nobody asked for. The task brief specified the shared
        capture here; the bench showed that baseline is the wrong reference
        for this tab, so this departs from the brief on purpose."""
        self._shape_air_restart()
        self.statusBar().showMessage(
            'Family Plane Analysis: air re-armed — collecting {0} settled frames'.format(
                self.sp_shape_air_n.value()))

    # -- Scratch captures ---------------------------------------------------
    # Quick grabs of unregistered objects, for exploring rather than for the
    # corpus. They are written to data/scratch/, NEVER data/corpora/: a
    # corpus build hard-errors on an unregistered target_id, and that guard is
    # deliberate. A scratch object gets promoted by registering it in
    # targets_v1.csv and recapturing it properly.
    #
    # A save also merges the file back into the shared template store under its
    # own 'scratch' source (v1.46), so the point is on the plane immediately --
    # as a triangle, per _SHAPE_SYMBOLS. Its own source, not 'loaded' or
    # 'editable': _merge_template_list replaces a source wholesale, so reusing
    # either would silently drop the reference corpus a scratch is being
    # compared against, which is the entire point of taking one.

    @staticmethod
    def _shape_slugify(label):
        """Free-text label -> the trailing part of a scratch target_id.
        pimd_target_check.TARGET_ID_RE is the authority on what a valid id
        looks like ([A-Za-z0-9_]+), so everything else collapses to '_'."""
        slug = ''.join(ch if (ch.isascii() and ch.isalnum()) else '_' for ch in label)
        return slug.strip('_')

    def _shape_scratch_path(self):
        return os.path.join(SCRATCH_DIR, 'gui_scratch_{0}.csv'.format(
            date.today().strftime('%Y%m%d')))

    def _shape_scratch_stats(self, anchor_mode):
        """Signature stats for a scratch capture, through the same
        pimd_features routines the Analysis tab's save path uses.

          'flat'  -- target window = the last N live frames; the single air
                     anchor is this tab's HELD air reference, timestamped at
                     the moment it was fixed. pimd_features.baseline_at()
                     clamps outside the anchor range, so one anchor means a
                     flat (not drift-corrected) baseline -- the documented
                     single-anchor case, and what makes a scratch grab quick.
                     Requires a held reference: against rolling air the delta
                     is ~0 by construction, so there would be nothing to save.
          'air2'  -- the Analysis tab's Training cycle already computed a
                     two-anchor, drift-corrected signature; reuse it verbatim
                     rather than duplicating that state machine here.

        Returns a stats dict shaped exactly like _compute_sig_stats()'s."""
        if anchor_mode == 'air2':
            stats = self._sig_last_stats
            if stats is None or 'error' in stats:
                return {'error': 'no completed training capture to save'}
            return dict(stats)

        if not self._shape_air_held() or self._shape_air_ref is None:
            return {'error': 'air reference is still rolling — press Space to lock it '
                              'against the target'}
        # Frames since the reference was frozen, capped at the count that
        # survives central_frames()' 60 % trim without earning a 'short' flag.
        # Two things this gets right that a plain "last N frames" did not:
        # the window can never reach back past the freeze and pick up air (it
        # was reading 'noisy' because it straddled the placement transient),
        # and a patient capture now clears MIN_CENTRAL_FRAMES honestly instead
        # of always being stamped 'short'.
        n = SIG_CAPTURE_N_DEFAULT
        since = self._shape_air_ref_ts or 0.0
        recent = [(ts, arr) for ts, arr in self._rolling_buf if ts >= since][-n:]
        if len(recent) < 2:
            return {'error': 'not enough frames since the air was locked — hold the '
                              'target a moment longer'}
        frames_mV = np.array([arr for _, arr in recent], dtype=float) / 1000.0
        t_seconds = np.array([ts for ts, _ in recent], dtype=float)
        if frames_mV.shape[1] != self._shape_air_ref.size:
            return {'error': 'air/frame channel-count mismatch — refusing to mix '
                              'profile geometries (DESIGN §11)'}

        anchor_ts = np.array([float(self._shape_air_ref_ts or t_seconds[0])])
        anchor_vs = np.array([self._shape_air_ref.reshape(-1)])
        plateau = pimd_features.Plateau(
            target_id='scratch', short_name='', distance_mm=None, long_axis='na',
            face_normal='na', offset_x_mm=0, offset_y_mm=0, medium='air', repeat_idx=1,
            notes='', is_air=False, start_idx=0, end_idx=len(recent))
        c0, c1 = pimd_features.central_frames(plateau)
        delta_mV, plateau_amp_mV, amp_mean_abs_mV, splithalf_floor, n_central, center_t = \
            pimd_features.compute_plateau_stats(frames_mV, t_seconds, c0, c1, anchor_ts, anchor_vs)
        return dict(
            delta_mV=delta_mV, plateau_amp_mV=plateau_amp_mV,
            amp_mean_abs_mV=amp_mean_abs_mV, splithalf_floor=splithalf_floor,
            quality=pimd_features.quality_flags(splithalf_floor, plateau_amp_mV, n_central),
            n_central=n_central, used_air_after=False,
            out_of_range=(center_t < anchor_ts[0] or center_t > anchor_ts[-1]))

    def _on_shape_save_scratch(self):
        blocker = self._shape_scratch_blocker()
        if blocker is not None:
            self.statusBar().showMessage('Save Scratch: {0}'.format(blocker))
            return
        training_stats = self._sig_last_stats
        air2_available = (training_stats is not None and 'error' not in training_stats
                          and training_stats.get('used_air_after'))
        dlg = ScratchDialog(self, air2_available=air2_available,
                            default_distance_mm=self.sig_distance_mm.value())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        fields = dlg.values()

        slug = self._shape_slugify(fields['label'])
        if not slug:
            self.statusBar().showMessage(
                'Save Scratch: label has no usable characters — ids must match '
                '[A-Za-z0-9_]+')
            return
        target_id = SCRATCH_ID_PREFIX + slug
        if not pimd_target_check.TARGET_ID_RE.match(target_id):
            self.statusBar().showMessage(
                "Save Scratch: '{0}' is not a valid target_id".format(target_id))
            return

        stats = self._shape_scratch_stats(fields['anchor'])
        if 'error' in stats:
            self.statusBar().showMessage('Save Scratch: {0}'.format(stats['error']))
            return

        path = self._shape_scratch_path()
        os.makedirs(SCRATCH_DIR, exist_ok=True)
        is_new = not os.path.exists(path)
        existing = {}
        if not is_new:
            # Same geometry guard as the corpus save path: appending a
            # different-width signature to an existing file would produce a
            # mixed-geometry file that no downstream tool can read (DESIGN §11).
            try:
                existing = self._scan_editable_signature_file(path)
            except Exception as e:
                self.statusBar().showMessage(
                    'Save Scratch: cannot read {0} ({1})'.format(path, e))
                return
            for sig in existing.values():
                if len(sig['shape']) != self._n_channels:
                    self.statusBar().showMessage(
                        'Save Scratch: {0} holds {1}-channel signatures, live profile has '
                        '{2} — never mix profile geometries (DESIGN §11)'.format(
                            os.path.basename(path), len(sig['shape']), self._n_channels))
                    return

        # The schema has no anchor column (scratch files are deliberately the
        # same shape as gui_signatures_*.csv), so the anchor mode is recorded
        # in the free-text notes -- a flat single-anchor capture is NOT
        # drift-corrected and that has to be visible later.
        notes = fields['note']
        notes = '{0} [anchor={1}]'.format(notes, fields['anchor']).strip()

        # One session per scratch FILE (i.e. per day), with a running capture
        # sequence resumed above the highest _cNN already in it. A
        # timestamp-derived session plus a fixed _c01 would collide for two
        # saves inside the same second: _scan_editable_signature_file() folds
        # same-key rows into one capture, so the second save would vanish into
        # the first -- exactly the v1.40 corpus-path failure.
        session_id = 'scratch_{0}'.format(date.today().strftime('%Y%m%d'))
        seq = max([self._capture_id_seq(cid) for _, cid in existing] or [0])
        seq += 1
        capture_id = '{0}_c{1:02d}'.format(session_id, seq)
        while (session_id, capture_id) in existing:
            seq += 1
            capture_id = '{0}_c{1:02d}'.format(session_id, seq)

        plateau = pimd_features.Plateau(
            target_id=target_id, short_name=fields['label'],
            distance_mm=fields['distance_mm'], long_axis='na', face_normal='na',
            offset_x_mm=0, offset_y_mm=0, medium=fields['medium'], repeat_idx=1,
            notes=notes, is_air=False, start_idx=0, end_idx=0)
        rows = pimd_features.build_rows(
            session_id, capture_id, datetime.now().isoformat(),
            plateau, self._build_colmap_for_corpus(),
            stats['delta_mV'], stats['plateau_amp_mV'], stats['splithalf_floor'],
            stats['quality'], stats['amp_mean_abs_mV'], self._profile.get('name'),
            self._profile_sha8, self._parsed_fw_version(),
            'pimd_classviz.py v{0}'.format(APP_VERSION), self.cb_supply.currentText(), path,
            pack_v=self._pack_v_value())
        try:
            # v1.65: same schema-follows-the-file rule as the corpus save path.
            # A new file gets the current header; an existing one keeps its own.
            fields = (list(pimd_features.CORPUS_HEADER_FIELDS) if is_new
                      else self._corpus_fields_for_path(path))
            with open(path, 'a', newline='') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
                if is_new:
                    writer.writerow(fields)
                for row in rows:
                    writer.writerow([row.get(k, '') for k in fields])
        except OSError as e:
            self.statusBar().showMessage('Save Scratch failed: {0}'.format(e))
            return
        # Straight onto the plane (v1.46). A scratch grab went to disk and
        # nowhere else, so the whole reason for taking one -- see where this
        # object lands against the loaded corpus -- needed a Load signatures…
        # round trip to answer.
        self._sig_autocheck_keys.add((session_id, capture_id))
        drawn = self._reload_scratch_signature_list(path)
        self.statusBar().showMessage(
            "Saved scratch '{0}' as {1} ({2} rows, anchor={3}) to {4}{5}".format(
                target_id, capture_id, len(rows), fields['anchor'], path,
                ' — plotted' if drawn else ''))

    def _reload_scratch_signature_list(self, path):
        """Re-read the scratch file into the shared template store under its
        own 'scratch' source, so it coexists with a loaded reference corpus and
        an active editable file rather than replacing either. Whole file, not
        just the row just written: _merge_template_list replaces a source
        wholesale, and re-reading is also the only check that what went to disk
        reads back as a signature. Returns True if it landed."""
        try:
            sigs = self._scan_editable_signature_file(path)
        except Exception as e:
            self.statusBar().showMessage(
                'Saved to {0}, but it could not be re-read to plot it ({1})'.format(
                    os.path.basename(path), e))
            return False
        self._merge_template_list(sigs, source='scratch')
        return True

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

    def _autostart(self):
        """Connect and run the remembered profile at launch, so opening the app
        lands on a streaming board rather than on two clicks of ceremony.

        Nothing here is forced: no port, a port that won't open, or no
        remembered profile each leave the app sitting exactly as it did before
        v1.53, with the reason in the status bar."""
        if self.serial.isOpen():
            return
        if not self.le_port.text().strip():
            self.statusBar().showMessage('Auto-start: no port remembered — connect manually')
            return
        self.connect_port()
        if not self.serial.isOpen():
            return      # connect_port() already reported it and reddened the button
        if not self.cb_profile_file.currentText():
            self.statusBar().showMessage('Auto-start: connected; no saved profile to run')
            return
        # The profile send waits out the connect handshake (E/V/Q4) rather than
        # racing it -- same beat an operator leaves between the two clicks.
        QTimer.singleShot(AUTOSTART_PROFILE_MS, self._autostart_run_profile)

    def _autostart_run_profile(self):
        """Second half of _autostart(), after the connect handshake. Re-checks
        the port: the operator can disconnect inside the delay."""
        if not self.serial.isOpen():
            return
        self._on_load_run_profile()

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
            # v1.66: final soak line BEFORE the dump is closed below, then bank
            # this run's streamed time. Order matters -- pb_record.setChecked
            # closes the file.
            self._append_soak('stream-stop')
            if self._stream_run_start_wall is not None:
                self._streamed_total_s += time.time() - self._stream_run_start_wall
                self._stream_run_start_wall = None
            self._last_stream_stop_iso = datetime.fromtimestamp(time.time()).isoformat()
            if self._recording:
                self._session_stop_is_forced = True   # stopping the stream, not opting out of logging
                self.pb_record.setChecked(False)      # auto-save recorded frames
        else:
            if not self.serial.isOpen():
                return
            self.send_command('G')
            self.pb_start.setText('Running')
            self.pb_start.setStyleSheet(self.MY_GREEN)
            # v1.63 primary auto-log trigger. A fresh stream is also the point
            # at which a previous explicit Stop stops applying -- that latch is
            # scoped to one streaming run, so "stop logging this run" doesn't
            # quietly become "stop logging all day".
            self._session_autolog_suppressed = False
            # v1.64: the stall latch is scoped to one streaming run, like the
            # suppression flag above -- a stall from an earlier run must not sit
            # on the Rate readout accusing this one.
            self._last_fw_time_ms = None
            self._stall_count     = 0
            self._stall_worst_s   = 0.0
            self._stall_total_s   = 0.0
            self._stall_last_wall = None
            # v1.66: mark the run start BEFORE the dump opens, so the header's
            # soak line already carries this run's idle_before_s.
            self._stream_run_start_wall = time.time()
            self._maybe_autostart_session('stream start')
            self._append_soak('stream-start')

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
        raw_mv = raw / 1000.0
        if self._ch_glitch_buf is None:
            # Seeded with the FIRST frame, not zeros. Zero-filled, the median
            # sits near 0 until 33 real frames have arrived, so every one of
            # those frames is |raw − 0| > 100 mV, i.e. flagged as a glitch:
            # the heatmap showed ~0 for its first ~10 s after connect or after
            # a profile change, and Shape Space's air buffer (which excludes
            # glitch frames) filled at a crawl over the same period.
            self._ch_glitch_buf = np.tile(raw_mv, (64, 1))
        self._ch_glitch_buf[self._ch_glitch_pos] = raw_mv
        self._ch_glitch_pos = (self._ch_glitch_pos + 1) % 64
        med_mv = np.median(self._ch_glitch_buf, axis=0)
        glitch_mask = np.abs(raw_mv - med_mv) > 100.0
        raw_display = np.where(glitch_mask, med_mv * 1000.0, raw)
        self._latest_raw = raw_display

        self._frame_count += 1
        self._rolling_buf.append((now, raw))
        self._fw_ms_buf.append(fw_time_ms)
        # v1.64: gap detection on the FIRMWARE clock, before the row is written,
        # so the '# stall:' line lands immediately above the frame that closed
        # the gap. See _note_frame_gap for why firmware time is the right clock.
        self._note_frame_gap(fw_time_ms, now)

        if self._recording and self._session_file and not self._session_paused:
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

        # Shape Space air tracking + live features. Done per frame regardless
        # of the visible tab (the air reference has to be current the moment
        # that tab is shown, not start warming up then); drawing is still
        # gated on visibility in _redraw(). Air first — the live features read
        # the reference it maintains.
        if hasattr(self, 'shape_scatter'):
            self._shape_air_ingest(now, raw, glitch_mask)
            self._shape_ingest_frame()

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
            # v1.63: the programmatic force-stops (_apply_profile on a dimension
            # change, start_stop on stream stop/disconnect) reach here through
            # the same pb_record.setChecked(False) an operator click does, so
            # they flag themselves first. Only a real click suppresses
            # auto-logging -- otherwise changing profile would silently turn
            # recording off for the rest of the run.
            forced = self._session_stop_is_forced
            self._session_stop_is_forced = False
            self._session_stop()
            if not forced and self._session_autolog:
                self._session_autolog_suppressed = True
                self.statusBar().showMessage(
                    'Session stopped — auto-logging suppressed until the stream is restarted.')
                self._update_sig_session_status_label()

    def _session_start(self, notes=None, auto=False):
        """Open a new self-describing session-dump CSV and write its header.
        notes: pre-supplied session notes, skipping the interactive prompt. If
        None (the Stats tab's "Record Session" button and the Analysis tab's
        Session Start), prompts the operator via QInputDialog.
        auto: opened unattended by _maybe_autostart_session (v1.63), which
        always supplies notes -- the QInputDialog is modal and would stall the
        stream behind a dialog nobody asked for."""
        if notes is None:
            notes, _ = QInputDialog.getMultiLineText(
                self, 'Session notes', 'Planned target order / notes for this session:')
        self._session_autostarted = auto
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        ts   = datetime.now()
        # Second-resolution names collide when a dump closes and reopens inside
        # the same second, and 'w' would silently truncate the one just closed.
        # Harmless while recording was two deliberate button presses; v1.63's
        # auto-restart after a profile change does exactly that back-to-back,
        # so suffix rather than overwrite. Consumers glob session_*.csv and read
        # the timestamp from the header, not the filename.
        stem = 'session_{0}'.format(ts.strftime('%Y%m%d_%H%M%S'))
        path = os.path.join(SESSIONS_DIR, stem + '.csv')
        seq  = 1
        while os.path.exists(path):
            seq += 1
            path = os.path.join(SESSIONS_DIR, '{0}_{1}.csv'.format(stem, seq))
        f = open(path, 'w')
        self._session_write_header(f, ts, notes)
        self._session_file        = f
        self._session_path        = path
        self._session_start_wall  = time.time()
        self._session_frame_count = 0
        # v1.64: the header line IS a reading when a voltage is entered, so the
        # nag clock starts from it rather than from zero. With the field blank it
        # stays None and the label says so immediately.
        self._pack_v_last_wall    = (time.time() if self._pack_v_value() is not None
                                     else None)
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
        # v1.63: lets the analysis side tell an unattended dump from one the
        # operator deliberately started (and so how much to trust the notes).
        f.write('# session_autostart: {0}\n'.format(
            'true' if self._session_autostarted else 'false'))
        f.write('# firmware_v_response (V<fw>,<board_id>,<num_profiles>,<active_idx>,'
                '<freq_hz>,<pulse_ns>,<delay_ns>,<downsample>): {0}\n'.format(fw_line))
        f.write('# fw_version: {0}\n'.format(self._parsed_fw_version()))
        f.write('# supply: {0}\n'.format(self.cb_supply.currentText()))
        # v1.64. The header value is the reading at session start; '# pack_v:'
        # lines appended mid-stream carry the rest of the discharge, which is
        # what a multi-hour run actually needs (2.5 V of fall on 2026-07-29).
        pack_v = self._pack_v_value()
        f.write('# pack_v: {0}\n'.format(
            '{0}, {1:.2f}, {2}'.format(ts.isoformat(), pack_v, self._pack_v_age_field())
            if pack_v is not None else '(not measured)'))
        # v1.66: soak context at the moment this dump opens, so a dump started
        # mid-run (a profile change opens a fresh one) is still self-describing
        # about how long the rig had already been going.
        f.write('# soak: {0}, {1}, event=session-open\n'.format(
            ts.isoformat(), self._soak_fields()))
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
        # callers (the Stats tab's own toggle, _apply_profile force-stop on a
        # profile change, start_stop force-stop on disconnect) so the Analysis
        # tab's Session controls never get stuck in a "started" state when the
        # underlying recording is closed out from under them.
        self._session_paused = False
        self._session_autostarted = False
        if self._analysis_session_recording:
            self._analysis_session_recording = False
            self._set_sig_session_active_ui(False)
        # Unconditional since v1.63: the idle label now also reports whether
        # auto-logging is armed or suppressed, which is true regardless of
        # which tab started the recording that just closed.
        self._update_sig_session_status_label()

    # ------------------------------------------------------------------
    # Ground-truth marks (low-level writer, used by the Analysis tab's Session)
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

    def _pack_v_value(self):
        """Current pack voltage, or None when the field reads its 0.00 '—'
        special value. None is written as a blank column / omitted line rather
        than as 0.00, which would look like a measurement of a flat pack."""
        v = self.sp_pack_v.value() if hasattr(self, 'sp_pack_v') else 0.0
        return v if v > 0.0 else None

    def _on_pack_v_changed(self, value):
        self._pack_v = value if value > 0.0 else None
        # v1.66: when the number was last TYPED, which is not the same as when it
        # was last logged. A reading's usefulness depends on how long ago someone
        # actually looked at the meter, so that is what gets written out.
        self._pack_v_edited_wall = time.time()

    def _pack_v_age_s(self):
        """Seconds since the pack-voltage field was last edited, or None when
        that is unknown (v1.66).

        Unknown covers the value restored from settings at launch: _load_settings
        calls setValue(), which fires valueChanged like any edit, but a number
        carried over from the last session is emphatically NOT a reading anyone
        just took -- the field comes up pre-filled, so treating the restore as an
        edit would stamp every launch with a confident age_s=0 it has not earned.
        _load_settings clears the timestamp again for exactly that reason."""
        if self._pack_v_edited_wall is None:
            return None
        return time.time() - self._pack_v_edited_wall

    def _pack_v_age_field(self):
        """The 'age_s=...' fragment for a written pack_v line -- an integer
        second count, or the literal 'unknown'. Never omitted: a reader must be
        able to tell 'nobody knows how old this is' from 'this is fresh', and an
        absent field would read as the latter."""
        age = self._pack_v_age_s()
        return 'age_s=unknown' if age is None else 'age_s={0:.0f}'.format(age)

    def _on_pack_v_log(self):
        """Timestamp the current pack voltage into the open dump."""
        volts = self._pack_v_value()
        if volts is None:
            self.statusBar().showMessage('Enter a pack voltage before logging it.')
            return
        if not (self._recording and self._session_file):
            self.statusBar().showMessage('No session recording — pack voltage not logged.')
            return
        if self._session_paused:
            self.statusBar().showMessage('Paused — resume before logging pack voltage.')
            return
        self._append_pack_v(volts)
        self._pack_v_last_wall = time.time()
        self._update_pack_v_age()
        self.statusBar().showMessage('Logged pack voltage: {0:.2f} V'.format(volts))

    def _append_pack_v(self, volts):
        """One '# pack_v: <iso>, <volts>, age_s=<n|unknown>' line, mid-stream.
        Same cheap write+flush on the open handle as _append_mark, and the same
        argument for why that is safe on the event loop.

        v1.66 added the age field. pimd_features v10 parses it and still accepts
        the v1.64 two-field form, which is what every dump captured before today
        uses -- including the 2026-07-29/30 pair the warm-up findings rest on."""
        ts = datetime.fromtimestamp(time.time()).isoformat()
        self._session_file.write('# pack_v: {0}, {1:.2f}, {2}\n'.format(
            ts, volts, self._pack_v_age_field()))
        self._session_file.flush()

    def _update_pack_v_age(self):
        """Age of the last logged reading, and the nag when it goes stale.

        Status bar only, never a dialog: v1.63 established that a modal would
        stall the stream behind a prompt nobody asked for. Sized against the
        gap this exists to prevent -- the 2026-07-29 session has 1h51m between
        two readings, which is exactly where interpolating pack voltage onto the
        frame timeline is least defensible."""
        if not hasattr(self, 'lbl_pack_v_age'):
            return
        if not self._recording:
            self.lbl_pack_v_age.setText('')
            self.lbl_pack_v_age.setStyleSheet('')
            return
        if self._pack_v_last_wall is None:
            self.lbl_pack_v_age.setText('no reading logged')
            self.lbl_pack_v_age.setStyleSheet(self.MY_YELLOW)
            return
        age_s = time.time() - self._pack_v_last_wall
        self.lbl_pack_v_age.setText('last V {0:.0f} min ago'.format(age_s / 60.0))
        if age_s >= PACK_V_REMIND_S:
            self.lbl_pack_v_age.setStyleSheet(self.MY_YELLOW)
            self.statusBar().showMessage(
                'Pack voltage due — last reading {0:.0f} min ago'.format(age_s / 60.0))
        else:
            self.lbl_pack_v_age.setStyleSheet('')

    def _streamed_s(self):
        """Cumulative seconds the stream has actually been running this session
        (v1.66), completed runs plus the one in progress."""
        total = self._streamed_total_s
        if self._stream_run_start_wall is not None:
            total += time.time() - self._stream_run_start_wall
        return total

    def _idle_before_s(self):
        """Seconds between the previously OBSERVED stream stop and this run's
        start, or None when not known.

        Read this as classviz-observed idle, NOT as guaranteed rig idle. If the
        app was closed and reopened, the board was unplugged, or the rig was left
        powered with the stream merely stopped, this number describes what this
        tool saw and not the hardware's thermal history. It is also unknown after
        a kill (settings are written on close), and blank on a first ever run.
        A strong hint, not a measurement -- and it must not be read as one, since
        the entire point of logging it is to stop inferring thermal state from a
        proxy without saying so."""
        if self._last_stream_stop_iso is None or self._stream_run_start_wall is None:
            return None
        try:
            stopped = datetime.fromisoformat(self._last_stream_stop_iso).timestamp()
        except (ValueError, TypeError):
            return None
        gap = self._stream_run_start_wall - stopped
        return gap if gap >= 0 else None

    def _soak_fields(self):
        """The body of a '# soak:' line (v1.66).

        stalled_s is carried alongside streamed_s deliberately: while the stream
        is stalled the MCU is not sweeping (fw v4.27, _note_frame_gap), so
        streamed_s OVERSTATES soak -- by ~45 min on the 2026-07-29 session.
        Effective soak is streamed_s - stalled_s, and both are given rather than
        one pre-subtracted number so the subtraction stays visible and reversible."""
        idle = self._idle_before_s()
        return 'streamed_s={0:.0f}, stalled_s={1:.0f}, idle_before_s={2}'.format(
            self._streamed_s(), self._stall_total_s,
            'unknown' if idle is None else '{0:.0f}'.format(idle))

    def _append_soak(self, event):
        """One '# soak:' line into the open dump. Same write+flush pattern and
        the same cheapness argument as _append_mark. Silent no-op when nothing is
        recording, so callers on the start/stop paths need no guard of their own."""
        # `.closed` as well as the pair: this helper is called from start_stop's
        # two branches, where the dump is opened and closed a line or two away,
        # so it is the one append site where an inconsistent (_recording=True,
        # handle already closed) state is a plausible ordering slip rather than
        # an impossible one. Cheaper to tolerate here than to debug later.
        if not (self._recording and self._session_file) or self._session_paused:
            return
        if getattr(self._session_file, 'closed', False):
            return
        ts = datetime.fromtimestamp(time.time()).isoformat()
        self._session_file.write('# soak: {0}, {1}, event={2}\n'.format(
            ts, self._soak_fields(), event))
        self._session_file.flush()
        self._soak_last_emit_wall = time.time()

    def _note_frame_gap(self, fw_time_ms, wall_ts):
        """Detect a break in the stream and record it (v1.64).

        The clock is the FIRMWARE's own elapsed-ms field, not PC wall time,
        because the question is whether the MCU stopped emitting. A gap in
        firmware time means frames the MCU counted never arrived -- and since
        the Mode 2 emit is a blocking print() to USB CDC, the MCU was very
        likely stalled inside it with the PWM free-running on one band's config
        (fw v4.27 counts these MCU-side via 'B'). That is not just missing data:
        the rig's thermal load changes while it happens. Measured 2026-07-29
        23:03-23:50 -- 47 minutes, ~90% of frames lost, the operating point
        moved +10 mV (9 µs) to +78 mV (100 µs), and it went unnoticed because
        nothing recorded it and the operator was away.

        Both a durable record (a '# stall:' line in the open dump, so an
        after-the-fact analysis can mask the window instead of inferring it) and
        a latched UI warning, since the existing Rate readout clears itself on
        the next good second and cannot survive an unattended run."""
        prev = self._last_fw_time_ms
        self._last_fw_time_ms = fw_time_ms
        if prev is None or fw_time_ms < prev:
            return          # first frame, or the firmware clock restarted
        gap_s = (fw_time_ms - prev) / 1000.0
        if gap_s < FRAME_GAP_WARN_S:
            return
        self._stall_count += 1
        self._stall_worst_s = max(self._stall_worst_s, gap_s)
        # v1.66: the SUM matters, not just the worst. While the stream is stalled
        # the rig is not sweeping, so wall time streaming overstates soak -- by
        # ~45 min on the 2026-07-29 session alone. '# soak:' reports this so
        # effective soak = streamed_s - stalled_s.
        self._stall_total_s += gap_s
        self._stall_last_wall = wall_ts
        if self._recording and self._session_file and not self._session_paused:
            # Same cheap synchronous write+flush as _append_mark, and the same
            # argument for why it is safe on the frame path.
            self._session_file.write('# stall: {0}, {1:.3f} s gap in firmware time\n'.format(
                datetime.fromtimestamp(wall_ts).isoformat(), gap_s))
            self._session_file.flush()

    def _append_session_notes(self, text):
        """Append operator notes to a session already recording (v1.63), one
        '# session_notes:' line per line of text -- the same key the header
        uses, so pimd_features collects header and late notes into one
        session_notes string (features v8 reads the mid-stream ones). Same
        write+flush pattern and the same cheapness argument as _append_mark."""
        for line in text.splitlines():
            self._session_file.write('# session_notes: {0}\n'.format(line))
        self._session_file.flush()

    def _append_mark_target(self, target_id, placement):
        """Append one '#'-prefixed structured companion line immediately after
        a '# mark:' line (same timestamp basis, called right after
        _append_mark() in the same call frame) -- purely additive, does not
        alter '# mark:' or any of its existing consumers (pimd_features.
        parse_mark_label()/segment_from_marks() keep working unchanged on
        pre-v1.32 sessions with no 'mark_target:' companion). `placement`:
        dict with distance_mm, long_axis, face_normal, offset_x_mm,
        offset_y_mm, medium, repeat_idx, notes (always '' since v1.38 dropped
        the entry box -- the field itself stays). csv-quotes the field portion
        with lineterminator='\\n' so no stray '\\r' lands in the session CSV --
        pimd_features.parse_mark_target_line() parses this exact format."""
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
        # that tab is visible. Keyed off _analysis_tab_index (what addTab()
        # actually returned) rather than a hardcoded constant: v1.39 removed a
        # tab above this one, and a stale literal here would have silently
        # stopped matching and frozen the charts.
        if self.tabs.currentIndex() == self._analysis_tab_index:
            self._update_analysis_charts()
            self._update_analysis_strips()
            self._update_analysis_gauges()

        # Shape Space: only the live-frame-driven panels refresh per tick, and
        # only while the tab is showing. The capture points / ladder rows /
        # tile change on load, selection and control-bar edits instead, so
        # they are redrawn from those events (_shape_redraw_static).
        if self.tabs.currentIndex() == self._shape_tab_index:
            self._update_shape_live()

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

        # v1.64: piggy-backed on this existing 1 Hz timer rather than adding a
        # second one — the pack-voltage age only needs minute resolution.
        self._update_pack_v_age()
        # v1.66: and the periodic soak line, on the same tick for the same reason.
        # ~300 lines over a five-hour session against 114k data rows, and it means
        # any stretch of frames has a nearby soak reference without interpolating.
        if self._recording and self._stream_run_start_wall is not None:
            last = self._soak_last_emit_wall
            if last is None or (time.time() - last) >= SOAK_EMIT_S:
                self._append_soak('periodic')

        if not self.serial.isOpen() or self.pb_start.text() != 'Running':
            self.lbl_rate.setText('Rate: — (idle)')
            self.lbl_rate.setStyleSheet('')
            return

        cell_hz = self._fps_hz * self._n_channels
        txt = 'Rate: {0:.1f} Hz  ({1:,.0f} cells/s)'.format(self._fps_hz, cell_hz)
        # v1.64: a LATCHED stall count, because the instantaneous readout above
        # is exactly what failed to raise the alarm on 2026-07-29 -- it recovered
        # the moment the stream did, leaving nothing on screen to notice.
        if self._stall_count:
            txt += '  ⛔ {0} stall{1}, worst {2:.0f} s'.format(
                self._stall_count, '' if self._stall_count == 1 else 's',
                self._stall_worst_s)
        if burst > 3:
            # A single readyRead drained more than 3 complete lines -- the
            # event loop briefly fell behind the ~100 Hz nominal stream.
            txt += '  ⚠ burst×{0}'.format(burst)
            self.lbl_rate.setStyleSheet(self.MY_YELLOW)
        elif self._stall_count:
            self.lbl_rate.setStyleSheet(self.MY_RED)
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
            # v1.64. Restored as a convenience only -- the last session's closing
            # voltage is the best guess for this session's opening one, and it is
            # visibly editable. 0.0 restores the '—' not-measured state.
            self.sp_pack_v.setValue(float(s.get('pack_v') or 0.0))
            # v1.66: setValue above fired valueChanged and so looks like an edit.
            # Undo that -- a voltage carried over from the last session is not a
            # reading anyone just took, and pack_v lines must say age_s=unknown
            # for it rather than claiming a confident age_s=0 every launch.
            self._pack_v_edited_wall = None
            # Drives idle_before_s on the next stream start. Only as good as the
            # last clean exit: settings are written on close, so a kill loses it
            # and idle_before_s reads unknown (see _idle_before_s).
            self._last_stream_stop_iso = s.get('last_stream_stop_iso') or None

            # Defaults on (v1.63): the failure this guards against -- a bench
            # run that turns out not to have been recorded -- is unrecoverable,
            # and the cost of the opposite mistake is ~13 MB/hour of gitignored
            # CSV. setChecked drives _on_session_autolog_toggled, which is safe
            # here: nothing is streaming yet, so _maybe_autostart_session no-ops.
            self._session_autolog = bool(s.get('session_autolog', True))
            self.cb_session_autolog.setChecked(self._session_autolog)

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
                # sig_face_normal / sig_offset_x_mm / sig_offset_y_mm are no
                # longer read (v1.60). Leaving them unread rather than
                # migrating the file is the point: a stale persisted
                # face_normal is exactly what was leaking into captures.
                self.sig_medium.setCurrentText(s.get('sig_medium', 'air'))

            self.cb_hm_norm.setCurrentIndex(int(s.get('analysis_hm_norm_idx', 0)))
            self.cb_hm_scale_auto.setChecked(bool(s.get('analysis_hm_scale_auto', True)))
            # v1.44 split the ± half-range into explicit limits; a settings
            # file written by v1.43 or earlier carries only the half-range, so
            # fall back to the symmetric pair it used to mean.
            half = float(s.get('analysis_hm_scale_manual', 200_000.0))
            self.sp_hm_scale_min.setValue(float(s.get('analysis_hm_scale_min', -half)))
            self.sp_hm_scale_max.setValue(float(s.get('analysis_hm_scale_max', half)))

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

            self.sp_sig_capture_n.setValue(int(s.get('sig_capture_n', SIG_CAPTURE_N_DEFAULT)))
            self.sp_sig_settle_mv.setValue(float(s.get('sig_settle_mv', 1.0)))
            self.sp_sig_detect_mv.setValue(float(s.get('sig_detect_mv', 0.5)))
            self.cb_sig_train_override.setChecked(bool(s.get('sig_train_override', True)))

            # Readout green/amber/red bands -- each spinbox keeps whatever
            # default _build_sig_row3_readout_save() derived from
            # pimd_features when the key is absent.
            self.sp_sig_q_amp_mv.setValue(
                float(s.get('sig_q_amp_mv', self.sp_sig_q_amp_mv.value())))
            self.sp_sig_q_mean_mv.setValue(
                float(s.get('sig_q_mean_mv', self.sp_sig_q_mean_mv.value())))
            self.sp_sig_q_split_ratio.setValue(
                float(s.get('sig_q_split_ratio', self.sp_sig_q_split_ratio.value())))

            # Analysis left-column split (signature list vs heatmap). Length
            # check guards a settings file written by a build with a different
            # child count.
            left_sizes = s.get('analysis_left_split_sizes')
            if isinstance(left_sizes, list) and len(left_sizes) == self.analysis_left_split.count():
                self.analysis_left_split.setSizes([int(x) for x in left_sizes])

            # Analysis row-1 split (trigger gauges | band-mean strip | chart 2).
            row1_sizes = s.get('analysis_row1_split_sizes')
            if isinstance(row1_sizes, list) and len(row1_sizes) == self.analysis_row1_split.count():
                self.analysis_row1_split.setSizes([int(x) for x in row1_sizes])

            # Stats-tab Std colour thresholds.
            self.sp_std_lower.setValue(float(s.get('std_lower', 0.50)))
            self.sp_std_upper.setValue(float(s.get('std_upper', 1.00)))

            # Shape Space — axis/colour selections, gate, trail, custom band
            # range. findData guards an axis key retired by a later version.
            for combo, saved in ((self.cb_shape_x, s.get('shape_x')),
                                  (self.cb_shape_y, s.get('shape_y')),
                                  (self.cb_shape_colour, s.get('shape_colour')),
                                  (self.cb_shape_scale_x, s.get('shape_scale_x')),
                                  (self.cb_shape_scale_y, s.get('shape_scale_y'))):
                idx = combo.findData(saved) if saved else -1
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            self.sp_shape_gate.setValue(float(s.get('shape_gate', SHAPE_GATE_DEFAULT)))
            self.sp_shape_trail.setValue(int(s.get('shape_trail', SHAPE_TRAIL_DEFAULT)))
            x_lo = int(s.get('shape_band_lo', 0))
            x_hi = int(s.get('shape_band_hi', max(0, self._n_bands - 1)))
            # The Y pair (v1.43) defaults to the X pair's saved values, so a
            # settings file from v1.42 restores the plane it was drawing.
            y_lo = int(s.get('shape_band_y_lo', x_lo))
            y_hi = int(s.get('shape_band_y_hi', x_hi))
            for sp, val in ((self.sp_shape_band_lo, x_lo), (self.sp_shape_band_hi, x_hi),
                             (self.sp_shape_band_y_lo, y_lo), (self.sp_shape_band_y_hi, y_hi)):
                sp.setValue(val)
            # AFTER the setValue calls, which fire the range handler and would
            # otherwise overwrite this with whatever the spins could hold. The
            # app is still on the 5-band startup profile here, so a saved 6 is
            # clamped to 4 on screen -- _rebuild_shape_axes() restores it from
            # these remembered values once the real profile lands (v1.49).
            self._shape_band_pref = {'x': (x_lo, x_hi), 'y': (y_lo, y_hi)}
            self.cb_shape_labels.setChecked(bool(s.get('shape_labels', True)))
            self.sp_shape_win_n.setValue(int(s.get('shape_win_n', SHAPE_WIN_N_DEFAULT)))
            self.sp_shape_air_n.setValue(int(s.get('shape_air_n', SHAPE_AIR_N_DEFAULT)))

            # Dock layout. Restored inside its own try: a state written by a
            # build with different dock names must degrade to the default
            # layout, not take the app down on startup.
            dock_state = s.get('shape_dock_state')
            if dock_state:
                try:
                    self.shape_dock_area.restoreState(dock_state)
                except Exception:
                    self._shape_apply_default_layout()
                    self.statusBar().showMessage(
                        'Family Plane Analysis: saved dock layout could not be restored '
                        '— using the default')

            # Last signature-dialog directory. Validated at use time by
            # _sig_dialog_dir(), not here -- a directory that exists at
            # startup can still be gone (or on an unmounted disk) by the time
            # the dialog opens.
            self._last_sig_dir = s.get('last_signature_dir') or CORPORA_DIR

            # Saved-profile dropdown (already populated from disk in _build_ui,
            # so findText guards a since-deleted file; only the dropdown
            # selection is restored -- no auto Load & Run).
            profile_name = s.get('profile_file')
            if profile_name:
                idx = self.cb_profile_file.findText(profile_name)
                if idx >= 0:
                    self.cb_profile_file.setCurrentIndex(idx)
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
            'analysis_hm_scale_min':    self.sp_hm_scale_min.value(),
            'analysis_hm_scale_max':    self.sp_hm_scale_max.value(),

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
            'sig_detect_mv': self.sp_sig_detect_mv.value(),
            'sig_train_override': self.cb_sig_train_override.isChecked(),

            'profile_file':    self.cb_profile_file.currentText(),
            'last_signature_dir': self._last_sig_dir,
            'std_lower':       self.sp_std_lower.value(),
            'std_upper':       self.sp_std_upper.value(),

            'supply': self.cb_supply.currentText(),
            'pack_v': self.sp_pack_v.value(),
            'last_stream_stop_iso': self._last_stream_stop_iso,
            'session_autolog': self.cb_session_autolog.isChecked(),

            'sig_target_id':   self.sig_target.currentData(),
            'sig_distance_mm': self.sig_distance_mm.value(),
            'sig_long_axis':   self.sig_long_axis.currentText(),
            'sig_medium':      self.sig_medium.currentText(),

            'sig_q_amp_mv':       self.sp_sig_q_amp_mv.value(),
            'sig_q_mean_mv':      self.sp_sig_q_mean_mv.value(),
            'sig_q_split_ratio':  self.sp_sig_q_split_ratio.value(),

            'analysis_left_split_sizes': self.analysis_left_split.sizes(),
            'analysis_row1_split_sizes': self.analysis_row1_split.sizes(),

            'shape_x':       self.cb_shape_x.currentData(),
            'shape_y':       self.cb_shape_y.currentData(),
            'shape_colour':  self.cb_shape_colour.currentData(),
            'shape_scale_x': self.cb_shape_scale_x.currentData(),
            'shape_scale_y': self.cb_shape_scale_y.currentData(),
            'shape_gate':    self.sp_shape_gate.value(),
            'shape_trail':   self.sp_shape_trail.value(),
            # The PREFERENCE, not the spinbox, when one is held (v1.49):
            # quitting while on a narrow profile must not write that profile's
            # clamped pair over the wider one the operator actually chose.
            'shape_band_lo': self._shape_band_saved('x', 0),
            'shape_band_hi': self._shape_band_saved('x', 1),
            'shape_band_y_lo': self._shape_band_saved('y', 0),
            'shape_band_y_hi': self._shape_band_saved('y', 1),
            'shape_labels':  self.cb_shape_labels.isChecked(),
            'shape_win_n':     self.sp_shape_win_n.value(),
            'shape_air_n':     self.sp_shape_air_n.value(),
            'shape_dock_state': self._shape_dock_state(),
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
        Space-bar action works regardless of focus, and is swallowed before
        widgets that already consume Space (e.g. QPushButton's
        Space-to-click). Suppressed whenever a text-entry widget has focus.
        Space drives an active Analysis-tab training cycle (lock leading air /
        override-advance) while that tab is visible; otherwise it is left alone
        and reaches whatever widget has focus, as normal. Since v1.39 that is
        the only Space binding -- the Training Session tab's step-advance went
        with the tab.

        v1.42: Space also locks/releases the Shape Space air reference, but
        ONLY while that tab is the visible one. The two bindings are keyed on
        different tab indices and can never both match, so the Training
        group's Space handling is untouched."""
        if event.type() == QEvent.Type.KeyPress:
            if isinstance(QApplication.focusWidget(), (QLineEdit, QSpinBox, QDoubleSpinBox)):
                return super().eventFilter(obj, event)
            if event.isAutoRepeat():
                return True   # swallow held-key repeats
            if event.key() == Qt.Key.Key_Space and self._analysis_training_active \
                    and self.tabs.currentIndex() == self._analysis_tab_index:
                self._on_sig_train_space()
                return True
            if event.key() == Qt.Key.Key_Space \
                    and self.tabs.currentIndex() == self._shape_tab_index:
                self._on_shape_air_space()
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
