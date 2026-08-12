# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
# ###############################################################################
# PIMD Raw Logger v1.17
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# Deliberately dumb: loads a profile, streams it (Mode 2 dynamic profile,
# same as pimd_delaycal.py's THERMAL mode), and writes every line the
# firmware sends verbatim to a session log file -- no tables, no metrics
# derived from the cell data itself, so it can't develop the same class of
# display bug just fixed in pimd_delaycal.py (v1.43/v1.44) and gives a
# ground-truth raw record for later offline analysis. Structured "Acquire
# Target" / "Acquire Air" markers (from a target registry + distance field)
# BRACKET each segment in the log -- pressing one starts a capture of
# `Capture frames` streamed frames and the matching "acquire end" marker is
# written automatically when that count is reached (v1.16) -- so a later
# analysis pass reads the extent of each acquisition off the log instead of
# inferring it; a free-text Note field remains for anything else worth
# flagging. A settle indicator (rolling per-channel std dev, own metric,
# independent of pimd_classviz.py) tells the operator when the signal is
# steady enough to press Acquire, and a warm-up indicator (cumulative
# firmware-clock streaming time) tells them when the rig itself is ready to
# trust. A live grid shows the last streamed frame in the same band x delay
# layout the profile itself defines. Sessions can be stopped and resumed
# later via "Resume Session".
#
# Firmware commands used (same wire protocol as pimd_delaycal.py -- see
# DESIGN.md §9/§11, not altered here):
#   E                                      — safe state (on connect / stop / done)
#   D<avg>;<freq_hz>,<pulse_us>,<d0>,...;… — define dynamic profile (same as delaycal)
#   Q<n>                                   — select profile
#   G                                      — start Mode 2 streaming
#   V                                      — identify; sent ONCE on connect (v1.15) to
#                                            prime the sensor row before the first
#                                            unsolicited 'P' arrives. Deliberately not
#                                            polled periodically: this tool's whole point
#                                            is that the logged stream is what the
#                                            firmware sent unbidden, so nothing is
#                                            injected once streaming is running. Pack and
#                                            temperature then refresh from 'P' (~60 s),
#                                            and a lockout announces itself on the wire.
#
# Records parsed on screen (v1.15). Everything is still written to the log file
# verbatim regardless — parsing only feeds the sensor row, never the log:
#   P<time_ms>,<pack_mV>,<board_temp_dC>   — unsolicited sensor telemetry, ~60 s
#   V<fw>,<board>,…,<pack_mV>,<board_temp_dC>,<lockout>
#                                          — fw / board id; the trailing three need
#                                            firmware v4.28+
#   PACK: / LOCKOUT / Command Input ERROR  — firmware messages, surfaced in the alert row
#
# board_temp_dC is deci-degrees C (x10 integer) from the DS18B20 on GP6 as of firmware
# v4.33, and TEMP_INVALID_DC (-32768) on that field means NO READING — sensor absent,
# unresponsive or CRC-failing. It is blanked on screen, never shown as a number; see
# _update_sensors(). The pack SoC / zone maths is duplicated from pimd_gui.py rather
# than imported, keeping each app standalone in the same way _build_d_command() is.
#
# Log format: one line per event, "<iso-timestamp> <RAW|NOTE|MARK|META> <text>",
# interleaved in arrival order. RAW lines are copied byte-for-byte from the
# serial port (only trailing whitespace stripped); NOTE lines are operator
# annotations; MARK lines are structured "acquire target"/"acquire air"
# markers; META lines record session bookkeeping (profile loaded,
# start/stop/resume). Files land in data/sessions/, alongside this project's
# other session dumps.
#
# Note: the profile JSON's per-band `threshold_v` field is vestigial (the
# rig no longer aligns delays to voltage targets) and is deliberately never
# read here -- columns are identified purely by band index + position in
# `delays_us`.
#
# Grid convention (standardised so every raw-value grid in this repo reads
# the same way): rows are bands in profile order (increasing pulse width,
# shortest pulse at the top); columns are delays within a band in profile
# order (increasing delay/time, shortest at the left). So the top-left cell
# is the shortest pulse width read at the shortest delay, and the
# bottom-right cell is the longest pulse width read at the longest delay.
#
# History (full detail in CHANGELOG.md):
#   v1.17 pack row reads runtime-fraction SoC + live H:MM remaining from the
#         shared pimd_pack.py; the data-quality zone captions are retired
#   v1.16 FIX the last-frame grid could force the window wider than the screen
#         (QLabel size hint); grid moved to a non-wrapping scroll pane.
#         Settle window becomes Capture frames: an acquisition now takes a
#         fixed frame count and auto-stamps its own end marker
#   v1.15 sensor row on screen — pack volts / SoC / zone, board temperature, firmware
#         version and a firmware-alert line, at parity with pimd_gui.py; 'V' primed
#         once on connect, sensors cleared on disconnect
#   v1.14 settings persistence (port/target/distance/settle/warmup/geometry),
#         matching the other PC apps
#   v1.13 Place/Remove Target renamed to Acquire Target/Acquire Air (each
#         just stamps the start of its own segment, no place/remove
#         pairing); "Last line" panel replaced with a live band x delay grid
#         of the last frame's raw values, in the standard grid orientation
#   v1.12 v1.11's word-wrap fix didn't work -- W lines are comma-separated
#         with no spaces to break on, so QLabel's word-wrap has nothing to
#         act on; truncate the displayed text instead, which actually bounds
#         the window width
#   v1.11 wrap the Last line label so a long raw line can't stretch the
#         window; warm-up target spinbox floor lowered to 1s
#   v1.10 target/distance registry picker, Place/Remove markers, settle
#         indicator, warm-up indicator, Resume Session
#   v1.00 initial version
# ###############################################################################

# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false

import collections
import csv
import json
import os
import shlex
import sys
from datetime import datetime

os.environ.setdefault('QT_API', 'pyqt6')

from PyQt6.QtWidgets import (  # noqa: E402
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QFileDialog, QPlainTextEdit,
)
from PyQt6.QtSerialPort import QSerialPort  # noqa: E402
from PyQt6.QtCore import QIODevice  # noqa: E402
from PyQt6.QtGui import QFontDatabase  # noqa: E402

import pimd_pack  # noqa: E402 — pack SoC / time-remaining maths (no Qt in that module)

APP_VERSION = '1.17'

DYNAMIC_PROFILE_INDEX = 5   # matches pimd_mcu.py NUM_PROFILES / pimd_delaycal.py / pimd_classviz.py

DEFAULT_PORT = '/dev/ttyACM0'

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'profiles')
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'sessions')
TARGETS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'targets', 'targets_v4.csv')
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'data', 'rawlog_settings.json')

# Fields copied inline into MARK acquire-target lines, so the raw log alone
# identifies what was in the field without needing targets_v4.csv alongside it.
TARGET_MARK_FIELDS = (
    'short_name', 'shape_class', 'material_class', 'mass_g',
    'dim_a_mm', 'dim_b_mm', 'dim_c_mm',
)

GRID_COL_WIDTH = 8   # chars per raw-µV cell -- covers signed 7-digit values
SETTLE_WINDOW_FRAMES = 20   # rolling window the settle figure is measured over.
                            # Fixed, and deliberately NOT the Capture-frames
                            # value (v1.16): the two answer different questions
                            # -- settle is "is it steady enough to press
                            # Acquire yet", capture is "how much do I then
                            # take". Tying them meant a 2000-frame capture gave
                            # a settle figure that needed ~5 minutes to fill
                            # before it read anything at all.
GRID_MAX_ROWS = 12   # tallest the grid pane grows before it scrolls vertically.
                     # One row per band; the deepest tracked profile is 10
                     # (cal_110_full_range_v4), so 12 clears it with headroom
                     # without letting a hand-edited profile eat the window.

# --------------------------------------------------------------------------
# Pack / board-temperature display constants (v1.15, shared since v1.17).
#
# The pack maths was duplicated from pimd_gui.py under an "every PC app stands
# alone" rule. That was reversed in v1.17: it now comes from the shared
# pimd_pack.py, because four hand-synced copies of a calibration table is
# exactly the thing that drifts, and the note above telling you to retune both
# apps was the tell. The rule still stands for _build_d_command below, which is
# wire formatting rather than a calibration.
#
# This app still needs its own COLOURS: pimd_gui.py's are gauge fills behind
# dark text and use the pale end of the range, where here they colour the label
# text itself and the pales are illegible. That is why soc_colour() takes a
# for_text flag rather than this file keeping a second palette -- the
# breakpoints stay shared, only the shade differs.
#
# Gone with the shared move: the PACK_ZONES "data-quality window", whose
# captions told the operator to log only inside a narrow band of pack voltage.
# DESIGN 17.23, corrected 2026-08-12, measures that sensitivity at ~1 mV/V, so
# the window was advice against an effect that is not there.
# --------------------------------------------------------------------------

TEMP_INVALID_MAX_DC = -10_000   # board_temp_dC at or below this is the firmware's
                                # "no reading" sentinel (fw v4.33 sends -32768).
                                # Threshold, not equality -- see pimd_gui.py.


def _build_d_command(profile):
    """Same format as pimd_delaycal.py's _build_d_command / pimd_classviz.py --
    not imported from delaycal, kept independent by design (see header)."""
    parts = [f'D{profile["averages"]}']
    for b in profile['bands']:
        fields = [str(b['freq_hz']), str(b['pulse_us'])]
        fields += [f'{d:.3f}' for d in b['delays_us']]
        parts.append(','.join(fields))
    return ';'.join(parts)


def _now_iso():
    return datetime.now().isoformat(timespec='milliseconds')


def _load_targets(path=TARGETS_CSV):
    """Reads the target registry CSV, skipping '#'-prefixed comment lines."""
    targets = []
    if not os.path.exists(path):
        return targets
    with open(path, newline='') as f:
        lines = []
        for line in f:
            stripped = line.lstrip()
            if stripped.startswith('#') or stripped.startswith('"#'):
                continue   # comment lines, some quoted because they contain a comma
            lines.append(line)
    reader = csv.DictReader(lines)
    for row in reader:
        if not row.get('target_id'):
            continue
        targets.append(row)
    return targets


def _mark_field_string(target, distance_mm):
    parts = [f'target_id={target["target_id"]}']
    for key in TARGET_MARK_FIELDS:
        val = target.get(key, '')
        if key in ('short_name', 'shape_class', 'material_class') and (' ' in val or not val):
            parts.append(f'{key}="{val}"')
        else:
            parts.append(f'{key}={val}')
    parts.append(f'distance_mm={distance_mm:g}')
    return ' '.join(parts)


def _format_grid(profile, channels, col_width=GRID_COL_WIDTH):
    """Formats channel values as a band x delay grid, per the module's grid
    convention: rows = bands in profile order (increasing pulse width, top =
    shortest); columns = delays within a band in profile order (increasing
    delay, left = shortest). Comma-separated, fixed-width right-aligned so
    digits line up column to column across rows."""
    lines = []
    idx = 0
    for b in profile['bands']:
        n = len(b['delays_us'])
        row = channels[idx:idx + n]
        idx += n
        lines.append(', '.join(f'{v:{col_width}.0f}' for v in row))
    return '\n'.join(lines)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'PIMD Raw Logger v{APP_VERSION} by Mark Makies')

        self.serial = QSerialPort()
        self.serial.readyRead.connect(self.read_from_serial)

        self._profile = None
        self._profile_path = None
        self._log_file = None
        self._log_path = None
        self._line_count = 0
        self._awaiting_d_ready = False

        self._targets = _load_targets()
        self._acquiring = None   # None, or {'mode': 'target'|'air', 'frames', 'want', ...}
        self._acquiring_name = ''

        self._settle_buf = collections.deque(maxlen=SETTLE_WINDOW_FRAMES)
        self._streamed_s = 0.0
        self._last_w_ms = None

        # Sensor / identity state (v1.15). All None until the firmware says
        # otherwise, so the row reads '—' rather than a plausible-looking zero.
        self._pack_mV = None
        self._board_temp_dC = None      # None also means "sentinel seen", i.e. no reading
        self._pack_lockout = False
        # Fits the live discharge rate behind the row's time-remaining figure.
        # Fed note_pulse() from the W handler: sweeps arriving IS the coil
        # running, which is what makes the fitted rate a LOADED one. It also
        # watches for pack swaps, which happen between runs as packs charge.
        self._pack_tracker = pimd_pack.PackTracker()
        self._fw_version = None
        self._board_id = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        conn_row = QHBoxLayout()
        conn_row.addWidget(QLabel('Port:'))
        self.le_port = QLineEdit(DEFAULT_PORT)
        conn_row.addWidget(self.le_port)
        self.pb_connect = QPushButton('Connect')
        self.pb_connect.clicked.connect(self._on_connect_clicked)
        conn_row.addWidget(self.pb_connect)
        root.addLayout(conn_row)

        # Sensor row (v1.15) -- the rig's standing state, at parity with
        # pimd_gui.py's gauges. Rendered as text rather than painted gauges to
        # stay in keeping with this tool: it is deliberately dumb, and a number
        # you can read off and copy into a note beats a bar you have to eyeball.
        sensor_row = QHBoxLayout()
        self.lbl_pack = QLabel('Pack: —')
        self.lbl_pack.setToolTip(
            'Pack state of charge, voltage and time remaining, from the\n'
            "firmware's P/V telemetry (22k/2k7 divider on GP26, fw v4.29+).\n"
            'SoC is the fraction of usable pulsing runtime left, zeroed on the\n'
            '{0:.1f} V firmware floor. Time left uses the discharge rate fitted\n'
            'over the last {1:.0f} minutes of pulsing; a leading ~ means no rate\n'
            'has been fitted yet, so the figure is the stored curve ({2})\n'
            'rather than this pack. Refreshes every ~60 s while connected.'.format(
                pimd_pack.PACK_TRIP_MV / 1000.0,
                pimd_pack.PackTracker.WINDOW_S / 60.0,
                pimd_pack.PACK_CAL_EPOCH))
        sensor_row.addWidget(self.lbl_pack)
        sensor_row.addSpacing(16)
        self.lbl_temp = QLabel('Board: —')
        self.lbl_temp.setToolTip(
            'Board temperature from the firmware (P/V telemetry).\n'
            'DS18B20 1-Wire sensor on GP6, factory-calibrated to ±0.5 °C\n'
            '(fw v4.33+); reported to 0.1 °C and refreshed every 30 s.\n'
            'Shows — when the sensor is absent, unresponsive or CRC-failing.')
        sensor_row.addWidget(self.lbl_temp)
        sensor_row.addSpacing(16)
        self.lbl_fw = QLabel('FW: —')
        self.lbl_fw.setToolTip('MCU firmware version, from the V identify reply.')
        sensor_row.addWidget(self.lbl_fw)
        sensor_row.addSpacing(16)
        self.lbl_alert = QLabel('')
        self.lbl_alert.setStyleSheet('color: #f66151;')
        sensor_row.addWidget(self.lbl_alert, 1)
        root.addLayout(sensor_row)

        profile_row = QHBoxLayout()
        self.pb_load_profile = QPushButton('Load Profile')
        self.pb_load_profile.clicked.connect(self._on_load_profile_clicked)
        profile_row.addWidget(self.pb_load_profile)
        self.lbl_profile = QLabel('No profile loaded.')
        profile_row.addWidget(self.lbl_profile, 1)
        root.addLayout(profile_row)

        run_row = QHBoxLayout()
        self.pb_start = QPushButton('Start')
        self.pb_start.clicked.connect(self._on_start_clicked)
        self.pb_start.setEnabled(False)
        run_row.addWidget(self.pb_start)
        self.pb_resume = QPushButton('Resume Session')
        self.pb_resume.clicked.connect(self._on_resume_clicked)
        run_row.addWidget(self.pb_resume)
        self.pb_stop = QPushButton('Stop')
        self.pb_stop.clicked.connect(self._on_stop_clicked)
        self.pb_stop.setEnabled(False)
        run_row.addWidget(self.pb_stop)
        self.lbl_status = QLabel('Idle.')
        run_row.addWidget(self.lbl_status, 1)
        root.addLayout(run_row)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel('Target:'))
        self.cb_target = QComboBox()
        for t in self._targets:
            self.cb_target.addItem(f'{t["short_name"]} ({t["target_id"]})')
        target_row.addWidget(self.cb_target, 1)
        target_row.addWidget(QLabel('Distance from coil (mm):'))
        self.sb_distance_mm = QDoubleSpinBox()
        self.sb_distance_mm.setRange(0, 500)
        self.sb_distance_mm.setSingleStep(5)
        self.sb_distance_mm.setValue(20)
        target_row.addWidget(self.sb_distance_mm)
        self.pb_acquire_target = QPushButton('Acquire Target')
        self.pb_acquire_target.clicked.connect(self._on_acquire_target_clicked)
        self.pb_acquire_target.setEnabled(False)
        target_row.addWidget(self.pb_acquire_target)
        self.pb_acquire_air = QPushButton('Acquire Air')
        self.pb_acquire_air.clicked.connect(self._on_acquire_air_clicked)
        self.pb_acquire_air.setEnabled(False)
        target_row.addWidget(self.pb_acquire_air)
        root.addLayout(target_row)

        self.lbl_acquiring = QLabel('Not yet acquiring.')
        root.addWidget(self.lbl_acquiring)

        settle_row = QHBoxLayout()
        settle_row.addWidget(QLabel('Capture frames:'))
        self.sb_capture_frames = QSpinBox()
        self.sb_capture_frames.setRange(5, 2000)
        self.sb_capture_frames.setValue(20)
        self.sb_capture_frames.setToolTip(
            'How many streamed frames one acquisition takes.\n'
            'Pressing Acquire Target/Air starts the count; the end marker is\n'
            'written automatically when it completes.\n'
            'Independent of the settle figure beside it, which always reads over\n'
            f'the last {SETTLE_WINDOW_FRAMES} frames.')
        settle_row.addWidget(self.sb_capture_frames)
        settle_row.addWidget(QLabel('Settle <= (mV):'))
        self.sb_settle_mv = QDoubleSpinBox()
        self.sb_settle_mv.setRange(0.05, 50.0)
        self.sb_settle_mv.setSingleStep(0.05)
        self.sb_settle_mv.setValue(1.0)
        settle_row.addWidget(self.sb_settle_mv)
        self.lbl_settle = QLabel(f'Collecting 0/{SETTLE_WINDOW_FRAMES}')
        settle_row.addWidget(self.lbl_settle, 1)
        root.addLayout(settle_row)

        warmup_row = QHBoxLayout()
        warmup_row.addWidget(QLabel('Warm-up target (s):'))
        self.sb_warmup_s = QSpinBox()
        self.sb_warmup_s.setRange(1, 3600)
        self.sb_warmup_s.setValue(240)
        warmup_row.addWidget(self.sb_warmup_s)
        self.lbl_warmup = QLabel('WARMING 0/240 s')
        warmup_row.addWidget(self.lbl_warmup, 1)
        root.addLayout(warmup_row)

        note_row = QHBoxLayout()
        note_row.addWidget(QLabel('Note:'))
        self.le_note = QLineEdit()
        self.le_note.setPlaceholderText(
            'Anything else worth flagging -- Enter to log')
        self.le_note.returnPressed.connect(self._on_log_note_clicked)
        note_row.addWidget(self.le_note, 1)
        self.pb_log_note = QPushButton('Log Note')
        self.pb_log_note.clicked.connect(self._on_log_note_clicked)
        note_row.addWidget(self.pb_log_note)
        root.addLayout(note_row)

        # Grid pane (v1.16). The prose header is a word-wrapping QLabel; the
        # numbers live in a read-only, NON-WRAPPING QPlainTextEdit.
        #
        # Why not a QLabel for the numbers (which is what v1.13 used): a QLabel
        # reports its full text extent as its size hint, and a layout cannot
        # shrink below that -- so the window's minimum width grew with the
        # profile's delay count and could not be dragged back. One band of 72
        # delays is ~720 monospace chars, several times a 3440 px screen. That
        # is also why v1.11's word-wrap and v1.12's truncation were both dead
        # ends: wrapping needs break points a comma-separated numeric row does
        # not have, and truncation bounds the width by throwing away the data
        # you opened the pane to read. A QPlainTextEdit has a small minimum
        # width regardless of content and scrolls horizontally instead, so the
        # full row stays readable AND the window stays resizable. Selectable
        # text is a free bonus at the bench.
        self.lbl_grid_header = QLabel('No frame yet.')
        self.lbl_grid_header.setWordWrap(True)
        root.addWidget(self.lbl_grid_header)
        self.txt_grid = QPlainTextEdit()
        self.txt_grid.setReadOnly(True)
        self.txt_grid.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.txt_grid.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self._set_grid_rows(1)
        root.addWidget(self.txt_grid)
        self.lbl_log_path = QLabel('Log file: —')
        root.addWidget(self.lbl_log_path)

        self.txt_activity = QPlainTextEdit()
        self.txt_activity.setReadOnly(True)
        self.txt_activity.setMaximumBlockCount(2000)
        root.addWidget(self.txt_activity, 1)

        self.resize(1000, 640)
        self._load_settings()

    # ------------------------------------------------------------------
    # Activity log (on-screen only -- separate from the session log file)
    # ------------------------------------------------------------------
    def _log(self, msg: str):
        self.txt_activity.appendPlainText(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}')

    # ------------------------------------------------------------------
    # Serial connect / disconnect
    # ------------------------------------------------------------------
    def _on_connect_clicked(self):
        if self.serial.isOpen():
            self._on_stop_clicked()
            self.serial.close()
            self.pb_connect.setText('Connect')
            self.pb_start.setEnabled(False)
            self._clear_sensors()
            self._log('Disconnected.')
            return
        port = self.le_port.text().strip()
        if port.startswith('/dev/'):
            port = port[5:]   # QSerialPort wants the bare device name on Linux
        self.serial.setPortName(port)
        self.serial.setBaudRate(115200)
        self.serial.setDataBits(QSerialPort.DataBits.Data8)
        self.serial.setParity(QSerialPort.Parity.NoParity)
        self.serial.setStopBits(QSerialPort.StopBits.OneStop)
        self.serial.setFlowControl(QSerialPort.FlowControl.NoFlowControl)
        if self.serial.open(QIODevice.OpenModeFlag.ReadWrite):
            self.pb_connect.setText('Disconnect')
            self.pb_start.setEnabled(self._profile is not None)
            self._log(f'Connected on {self.le_port.text().strip()}.')
            # Prime the sensor row (v1.15). Without this the pack/temp fields sit
            # blank for up to a minute, until the first unsolicited 'P' lands.
            # Sent while the rig is idle, before any streaming, so it cannot
            # interleave with the acquisition stream.
            self.send_command('V')
        else:
            self._log(f'Failed to open {self.le_port.text().strip()}: '
                       f'{self.serial.errorString()}')

    def send_command(self, text):
        self.serial.write((text + '\n').encode())

    # ------------------------------------------------------------------
    # Profile loading
    # ------------------------------------------------------------------
    def _load_profile_file(self, path):
        """Parses/validates a profile JSON file. Returns the profile dict,
        raises (KeyError, ValueError, json.JSONDecodeError, OSError) on failure."""
        with open(path) as f:
            profile = json.load(f)
        bands = profile.get('bands', [])
        if not bands:
            raise ValueError('No bands in profile.')
        for b in bands:
            if 'freq_hz' not in b or 'pulse_us' not in b or 'delays_us' not in b:
                raise ValueError('Band missing freq_hz/pulse_us/delays_us.')
        if 'averages' not in profile:
            raise ValueError('Profile has no "averages" field.')
        return profile

    def _apply_loaded_profile(self, path, profile):
        self._profile = profile
        self._profile_path = path
        bands = profile['bands']
        n_bands = len(bands)
        n_cells = len(bands[0]['delays_us'])
        name = profile.get('name', os.path.basename(path))
        self.lbl_profile.setText(
            f'{name}  ({n_bands} band(s) x {n_cells} cell(s) = {n_bands * n_cells} channels, '
            f'averages={profile["averages"]})')
        self._log(f'Profile loaded: {os.path.basename(path)} -- '
                   f'{n_bands} band(s) x {n_cells} cell(s)')
        self.pb_start.setEnabled(self.serial.isOpen())

    def _on_load_profile_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Load Profile', PROFILES_DIR, 'JSON profiles (*.json)')
        if not path:
            return
        try:
            profile = self._load_profile_file(path)
        except (KeyError, ValueError, json.JSONDecodeError, OSError) as e:
            self._log(f'Profile load failed: {e}')
            self.lbl_profile.setText(f'Load failed: {e}')
            return
        self._apply_loaded_profile(path, profile)

    # ------------------------------------------------------------------
    # Target / air acquisition -- each button just stamps the start of its
    # own segment; there is no place/remove pairing to enforce.
    # ------------------------------------------------------------------
    def _reset_settle_buf(self):
        self._settle_buf.clear()
        self._update_settle_label()

    def _close_acquisition(self, reason):
        """Stamp `MARK acquire end` for the open acquisition, if any.

        Added v1.16, and it is the point of the change. Before this, an acquire
        marker recorded the state *from that point on* with nothing to close it,
        so the log said when a segment began and never when it ended. Analysis
        then had to guess the extent, and guessing wrong is not a small error:
        in rawlog_20260807_194234 a second Fe marker landed ~9 s after the
        spanner was already away, and segmenting on the markers as written mixed
        ~30 s of air into the target window and roughly halved its delta
        (+3.5 mV against +7.12 mV from the real plateau). A bracketed segment
        removes that whole class of mistake from the record rather than leaving
        each analysis pass to re-derive it.

        `frames` is what was actually captured and `complete` says whether the
        requested count was reached, so a run cut short by a stop, a disconnect
        or an impatient second press is still usable -- it is labelled, not
        silently short."""
        if not self._acquiring or not self._log_file:
            return
        a = self._acquiring
        got, want = a['frames'], a['want']
        fields = [f'mode={a["mode"]}']
        if a['mode'] == 'target':
            fields.append(f'target_id={a["target_id"]}')
        fields += [f'frames={got}', f'requested={want}',
                   f'complete={"yes" if got >= want else "no"}',
                   f'reason={reason}']
        self._write_log('MARK', 'acquire end ' + ' '.join(fields))
        self._acquiring = None
        return got, want

    def _begin_acquisition(self, mark_text, acquiring, screen_name):
        """Common path for both Acquire buttons: close any open segment, write
        the start marker, arm the frame counter, and reset the settle buffer so
        the figure on screen describes this capture rather than the run-up to it.

        The start marker is written HERE, after the close, rather than by the
        callers before it -- otherwise a second press emits the new segment's
        start before the previous segment's end, and the log stops being
        readable as brackets, which is the one property this is all for."""
        self._close_acquisition('superseded')
        self._write_log('MARK', mark_text)
        acquiring['frames'] = 0
        acquiring['want'] = self.sb_capture_frames.value()
        self._acquiring = acquiring
        self._acquiring_name = screen_name
        self.lbl_acquiring.setText(f'Capturing {screen_name}: 0/{acquiring["want"]} frames')
        self._log(f'Acquiring {screen_name} -- capturing {acquiring["want"]} frames')
        self._reset_settle_buf()

    def _on_acquire_target_clicked(self):
        if not self._log_file or not self._targets:
            return
        target = self._targets[self.cb_target.currentIndex()]
        distance_mm = self.sb_distance_mm.value()
        self._begin_acquisition(
            f'acquire target {_mark_field_string(target, distance_mm)}',
            {'mode': 'target', 'target_id': target['target_id'],
             'short_name': target['short_name'], 'distance_mm': distance_mm},
            f'{target["short_name"]} ({target["target_id"]}) @ {distance_mm:g} mm')

    def _on_acquire_air_clicked(self):
        if not self._log_file:
            return
        self._begin_acquisition('acquire air', {'mode': 'air'}, 'air (baseline)')

    def _count_acquisition_frame(self):
        """One streamed frame against the open acquisition; closes it at the
        requested count. Counting frames rather than seconds is deliberate --
        the sweep rate depends on the profile's cell count (6.9 Hz for the
        72-cell 150 µs sweep, 4.1 Hz for cal_110), so a frame budget means the
        same number of samples per cell whatever is loaded, which is what the
        offline averaging actually consumes."""
        if not self._acquiring:
            return
        self._acquiring['frames'] += 1
        got, want = self._acquiring['frames'], self._acquiring['want']
        name = self._acquiring_name
        if got < want:
            self.lbl_acquiring.setText(f'Capturing {name}: {got}/{want} frames')
            return
        self._close_acquisition('count-reached')
        self.lbl_acquiring.setText(f'Captured {name}: {got} frames -- done.')
        self._log(f'Capture complete: {name}, {got} frames')

    # ------------------------------------------------------------------
    # Start / stop / resume streaming
    # ------------------------------------------------------------------
    def _begin_streaming(self, status_prefix):
        self.pb_start.setEnabled(False)
        self.pb_resume.setEnabled(False)
        self.pb_load_profile.setEnabled(False)
        self.lbl_status.setText(f'{status_prefix} -- waiting for D OK...')
        self._awaiting_d_ready = True
        self.send_command('E')
        self.send_command(_build_d_command(self._profile))

    def _on_start_clicked(self):
        if not self.serial.isOpen() or self._profile is None:
            return
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        self._log_path = os.path.join(SESSIONS_DIR, f'rawlog_{ts}.txt')
        self._log_file = open(self._log_path, 'a', buffering=1)   # line-buffered
        self.lbl_log_path.setText(f'Log file: {self._log_path}')
        name = self._profile.get('name', os.path.basename(self._profile_path))
        self._write_log('META', f'profile={shlex.quote(self._profile_path)} name={name} '
                                 f'averages={self._profile["averages"]} '
                                 f'bands={len(self._profile["bands"])}')
        self._line_count = 0
        self._streamed_s = 0.0
        self._last_w_ms = None
        self._acquiring = None
        self.lbl_acquiring.setText('Not yet acquiring -- press Acquire Target or Acquire Air.')
        self._reset_settle_buf()
        self._update_warmup_label()
        self.pb_acquire_target.setEnabled(bool(self._targets))
        self.pb_acquire_air.setEnabled(True)
        self._begin_streaming('Starting')

    def _on_resume_clicked(self):
        if not self.serial.isOpen():
            self._log('Connect to the MCU before resuming a session.')
            return
        path, _ = QFileDialog.getOpenFileName(
            self, 'Resume Session', SESSIONS_DIR, 'Raw logs (rawlog_*.txt)')
        if not path:
            return
        try:
            info = _scan_session_file(path)
        except OSError as e:
            self._log(f'Resume failed: {e}')
            return
        if info['profile_path'] is None:
            self._log('Resume failed: no profile= record found in that log file.')
            return
        try:
            profile = self._load_profile_file(info['profile_path'])
        except (KeyError, ValueError, json.JSONDecodeError, OSError) as e:
            self._log(f'Resume failed: could not reload profile '
                       f'{info["profile_path"]}: {e} -- Load Profile manually, then retry.')
            return
        self._apply_loaded_profile(info['profile_path'], profile)

        self._log_path = path
        self._log_file = open(self._log_path, 'a', buffering=1)
        self.lbl_log_path.setText(f'Log file: {self._log_path}')
        self._line_count = 0
        self._streamed_s = info['streamed_s']
        self._last_w_ms = None
        self._reset_settle_buf()
        self._update_warmup_label()

        acquiring = info['open_acquisition']
        if acquiring is not None:
            # A resumed segment has no live frame counter (the frames it already
            # captured are in the old file, not this run), so it is re-armed for
            # a fresh full count from here. The earlier part stays bracketed in
            # the log by its own markers.
            acquiring['frames'] = 0
            acquiring['want'] = self.sb_capture_frames.value()
            self._acquiring_name = ('air (baseline)' if acquiring['mode'] == 'air'
                                    else acquiring.get('short_name',
                                                       acquiring.get('target_id', 'target')))
        self._acquiring = acquiring
        if acquiring is None:
            self.lbl_acquiring.setText('Not yet acquiring -- press Acquire Target or Acquire Air.')
        elif acquiring['mode'] == 'air':
            self.lbl_acquiring.setText('Acquiring: air (baseline). [resumed]')
        else:
            self.lbl_acquiring.setText(
                f'Acquiring: {acquiring.get("short_name", acquiring["target_id"])} '
                f'({acquiring["target_id"]}) [resumed]')
        self.pb_acquire_target.setEnabled(bool(self._targets))
        self.pb_acquire_air.setEnabled(True)

        self._write_log('META', f'resumed streamed_s={self._streamed_s:.1f}')
        self._log(f'Resuming {os.path.basename(path)} '
                   f'(streamed_s={self._streamed_s:.1f})')
        self._begin_streaming('Resuming')

    def _on_stop_clicked(self):
        if self.serial.isOpen():
            self.send_command('E')
        self._awaiting_d_ready = False
        if self._log_file:
            # Before the file goes away: a capture interrupted by Stop is
            # recorded as short rather than left dangling (v1.16).
            self._close_acquisition('stopped')
            self._write_log('META', 'stopped')
            self._log_file.close()
            self._log_file = None
        self.pb_start.setEnabled(self.serial.isOpen() and self._profile is not None)
        self.pb_resume.setEnabled(True)
        self.pb_stop.setEnabled(False)
        self.pb_load_profile.setEnabled(True)
        self.pb_acquire_target.setEnabled(False)
        self.pb_acquire_air.setEnabled(False)
        self.lbl_status.setText('Idle.')
        self._log('Stopped.')

    # ------------------------------------------------------------------
    # Serial read loop
    # ------------------------------------------------------------------
    def read_from_serial(self):
        while self.serial.canReadLine():
            raw = self.serial.readLine().data().decode('utf-8', errors='replace').rstrip()
            if not raw:
                continue
            self._write_log('RAW', raw)
            self._line_count += 1

            if raw.startswith('W'):
                self._pack_tracker.note_pulse()
                parsed = _parse_w_line(raw)
                if parsed is not None:
                    time_ms, channels = parsed
                    self._update_warmup(time_ms)
                    self._update_settle(channels)
                    self._update_grid_display(channels)
                    self._count_acquisition_frame()

            elif raw.startswith('P') and raw[1:2].isdigit():
                # Unsolicited pack / board-temp telemetry (firmware v4.28+):
                # P<time_ms>,<pack_mV>,<board_temp_dC>
                #
                # The isdigit() guard is load-bearing, and is the bug pimd_gui.py
                # v4.17 was cut to fix -- do not simplify it away. A bare
                # startswith('P') also matches every firmware MESSAGE beginning
                # with P: 'PACK: rail absent ...', 'PACK: present again ...' and
                # the 'Pulse Induction Metal Detector v...' boot banner. Those
                # split on commas into an IndexError once per pack power-cycle.
                # A record always has a digit after the tag (it is <time_ms>);
                # a message never does.
                parts = raw[1:].split(',')
                try:
                    self._update_sensors(int(parts[1]), int(parts[2]))
                except (IndexError, ValueError) as e:
                    self._log(f'Sensor packet parse error: {e} -- {raw}')

            elif raw.startswith('PACK:'):
                # Pack presence / failsafe-arming transitions (firmware v4.31-v4.32).
                # 'PACK: present again at N mV — lockout cleared ...' is the ONLY
                # line that retires a latch, so it is matched explicitly. Note it
                # contains the word "lockout" while meaning the opposite -- a
                # substring test for 'lockout' across all firmware messages would
                # latch on this one and invert the state.
                if 'lockout cleared' in raw:
                    self._pack_lockout = False
                    self._refresh_sensor_labels()
                self._set_alert(raw)

            elif raw.startswith('V'):
                # Identify reply. Fields 0/1 are firmware version and board ID and
                # are present on every revision; fields 8..10 are pack_mV /
                # board_temp_dC / lockout and need firmware v4.28+, so older
                # firmware simply leaves the sensor row blank.
                parts = raw[1:].split(',')
                # A bad value would sit in the label indefinitely rather than
                # scrolling past, so require it to look like a version first.
                if parts and parts[0].replace('.', '').isdigit():
                    self._update_fw_identity(parts[0],
                                             parts[1] if len(parts) > 1 else None)
                    if len(parts) >= 11:
                        try:
                            self._update_sensors(int(parts[8]), int(parts[9]),
                                                 bool(int(parts[10])))
                        except ValueError as e:
                            self._log(f'Identify parse error: {e} -- {raw}')

            elif raw.startswith('LOCKOUT') or raw.startswith('Command Input ERROR'):
                # A rejected config, or the v4.28 low-voltage failsafe latching.
                # Both need saying out loud. Only the two that actually name a
                # latched lockout set the flag -- a rejected pulse config is just
                # a complaint and must not colour the pack readout red.
                if raw.startswith('LOCKOUT') or 'lockout latched' in raw:
                    self._pack_lockout = True
                    self._refresh_sensor_labels()
                self._set_alert(raw)

            if self._awaiting_d_ready:
                if raw.startswith('D OK'):
                    self._awaiting_d_ready = False
                    self.send_command(f'Q{DYNAMIC_PROFILE_INDEX}')
                    self.send_command('G')
                    self.pb_stop.setEnabled(True)
                    self.lbl_status.setText('Streaming.')
                    self._log('Streaming started.')
                elif 'ERROR' in raw:
                    self._awaiting_d_ready = False
                    self.lbl_status.setText(f'D rejected: {raw}')
                    self._log(f'D command rejected: {raw}')
                    if self._log_file:
                        self._write_log('META', 'stopped (D rejected)')
                        self._log_file.close()
                        self._log_file = None
                    self.pb_start.setEnabled(True)
                    self.pb_resume.setEnabled(True)
                    self.pb_load_profile.setEnabled(True)

    # ------------------------------------------------------------------
    # Sensor row -- pack / board temperature / firmware identity (v1.15)
    # ------------------------------------------------------------------
    def _update_sensors(self, pack_mV, board_temp_dC, lockout=None):
        """Apply a pack / board-temp reading to the sensor row.

        board_temp_dC may be the firmware's "no reading" sentinel (see
        TEMP_INVALID_MAX_DC). It is resolved to None once, here, so the display
        never sees the raw sentinel and can never print -3276.8 °C as though it
        were a temperature. The log file is untouched either way -- it already
        holds the firmware's own line, sentinel and all, which is what a later
        offline pass should be reading."""
        self._pack_mV = pack_mV
        # Before the label refresh, so the caption is drawn from this reading's rate.
        self._pack_tracker.add(pack_mV)
        valid_temp = board_temp_dC > TEMP_INVALID_MAX_DC
        self._board_temp_dC = board_temp_dC if valid_temp else None
        if lockout is not None:
            self._pack_lockout = lockout
        self._refresh_sensor_labels()

    def _refresh_sensor_labels(self):
        if self._pack_mV is None:
            self.lbl_pack.setText('Pack: —')
            self.lbl_pack.setStyleSheet('')
        else:
            soc = pimd_pack.pack_soc_pct(self._pack_mV)
            colour = pimd_pack.soc_colour(0.0 if self._pack_lockout else soc,
                                          for_text=True)
            caption = pimd_pack.pack_caption(self._pack_mV, self._pack_lockout,
                                             self._pack_tracker)
            self.lbl_pack.setText(f'Pack: {soc:.0f}% · {caption}')
            self.lbl_pack.setStyleSheet(f'color: {colour}; font-weight: bold;')

        if self._board_temp_dC is None:
            self.lbl_temp.setText('Board: —')
        else:
            self.lbl_temp.setText(f'Board: {self._board_temp_dC / 10.0:.1f} °C')

    def _update_fw_identity(self, fw_version, board_id=None):
        self._fw_version = fw_version
        self._board_id = board_id
        self.lbl_fw.setText(f'FW: v{fw_version}')
        if board_id:
            self.lbl_fw.setToolTip(
                f'MCU firmware version, from the V identify reply.\nBoard ID: {board_id}')

    def _clear_sensors(self):
        """Forget everything the board told us, so a stale reading cannot outlive
        the connection it came from."""
        self._pack_mV = None
        self._board_temp_dC = None
        self._pack_lockout = False
        # A rate fitted on the pack that was here cannot describe whatever is
        # fitted next time -- packs get swapped between runs as they charge.
        self._pack_tracker.reset('disconnected')
        self._fw_version = None
        self._board_id = None
        self._refresh_sensor_labels()
        self.lbl_fw.setText('FW: —')
        self.lbl_fw.setToolTip('MCU firmware version, from the V identify reply.')
        self.lbl_alert.setText('')

    def _set_alert(self, text):
        """Post a firmware message to the alert row. Unlike pimd_gui.py these do
        not self-clear: this is a logging tool that gets left running unattended,
        and a PACK:/LOCKOUT event that scrolled away unseen is exactly the thing
        you need to know about when you come back to the bench. The activity
        pane below keeps the full timestamped history."""
        self.lbl_alert.setText(text)
        self.lbl_alert.setToolTip(text)
        self._log(text)

    # ------------------------------------------------------------------
    # Grid display -- last streamed frame, band x delay layout (see the
    # module header's "Grid convention" note)
    # ------------------------------------------------------------------
    def _set_grid_rows(self, n_rows):
        """Height the grid pane to its content, clamped to GRID_MAX_ROWS.

        Without this the QPlainTextEdit would claim a text-editor's default
        height and push the activity pane down; with it the pane is as tall as
        the profile needs (one line for a single-band sweep, ten for
        cal_110_full_range_v4) and scrolls vertically beyond the clamp."""
        rows = max(1, min(int(n_rows), GRID_MAX_ROWS))
        fm = self.txt_grid.fontMetrics()
        # frame + document margins + a horizontal scrollbar's worth of room,
        # so the last row is never hidden behind the scrollbar it triggers.
        chrome = (2 * self.txt_grid.frameWidth() + 8
                  + self.txt_grid.horizontalScrollBar().sizeHint().height())
        self.txt_grid.setFixedHeight(rows * fm.lineSpacing() + chrome)

    def _update_grid_display(self, channels):
        if self._profile is None:
            return
        n_bands = len(self._profile['bands'])
        header = (f'Last frame (raw line #{self._line_count}) -- {n_bands} band(s) top-to-bottom '
                  f'by increasing pulse width, delays left-to-right by increasing time, raw µV:')
        self.lbl_grid_header.setText(header)
        self._set_grid_rows(n_bands)
        # Preserve the horizontal scroll position across frames -- the pane
        # repaints several times a second, and resetting it would make a
        # scrolled-to column impossible to watch.
        hbar = self.txt_grid.horizontalScrollBar()
        pos = hbar.value()
        self.txt_grid.setPlainText(_format_grid(self._profile, channels))
        hbar.setValue(pos)

    # ------------------------------------------------------------------
    # Settle indicator (own metric: rolling per-channel std dev -> mV)
    # ------------------------------------------------------------------
    def _update_settle(self, channels):
        self._settle_buf.append(channels)
        self._update_settle_label()

    def _update_settle_label(self):
        n = len(self._settle_buf)
        window = SETTLE_WINDOW_FRAMES
        if n < window:
            self.lbl_settle.setText(f'Collecting {n}/{window}')
            self.lbl_settle.setStyleSheet('color: gray;')
            return
        n_ch = len(self._settle_buf[0])
        sums = [0.0] * n_ch
        sums_sq = [0.0] * n_ch
        for frame in self._settle_buf:
            for i in range(n_ch):
                v = frame[i] if i < len(frame) else 0.0
                sums[i] += v
                sums_sq[i] += v * v
        stds_uv = []
        for i in range(n_ch):
            mean = sums[i] / n
            var = max(0.0, sums_sq[i] / n - mean * mean)
            stds_uv.append(var ** 0.5)
        settle_mv = (sum(stds_uv) / n_ch) / 1000.0
        threshold_mv = self.sb_settle_mv.value()
        if settle_mv <= threshold_mv:
            self.lbl_settle.setText(f'READY σ={settle_mv:.2f} mV')
            self.lbl_settle.setStyleSheet('color: green; font-weight: bold;')
        else:
            self.lbl_settle.setText(f'SETTLING σ={settle_mv:.2f} mV')
            self.lbl_settle.setStyleSheet('color: darkorange; font-weight: bold;')

    # ------------------------------------------------------------------
    # Warm-up indicator (own metric: cumulative firmware-clock streaming time)
    # ------------------------------------------------------------------
    def _update_warmup(self, time_ms):
        if self._last_w_ms is not None and time_ms > self._last_w_ms:
            self._streamed_s += (time_ms - self._last_w_ms) / 1000.0
        self._last_w_ms = time_ms
        self._update_warmup_label()

    def _update_warmup_label(self):
        target_s = self.sb_warmup_s.value()
        if self._streamed_s >= target_s:
            self.lbl_warmup.setText(f'WARM ✓ ({self._streamed_s:.0f} s)')
            self.lbl_warmup.setStyleSheet('color: green; font-weight: bold;')
        else:
            self.lbl_warmup.setText(f'WARMING {self._streamed_s:.0f}/{target_s} s')
            self.lbl_warmup.setStyleSheet('color: darkorange; font-weight: bold;')

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _write_log(self, tag, text):
        if self._log_file:
            self._log_file.write(f'{_now_iso()} {tag} {text}\n')

    def _on_log_note_clicked(self):
        text = self.le_note.text().strip()
        if not text:
            return
        if not self._log_file:
            self.lbl_status.setText('Nothing running -- press Start before logging a note.')
            return
        self._write_log('NOTE', text)
        self._log(f'NOTE: {text}')
        self.le_note.clear()

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------
    def _load_settings(self):
        try:
            with open(SETTINGS_PATH) as f:
                s = json.load(f)
            self.le_port.setText(s.get('port', DEFAULT_PORT))
            target_idx = int(s.get('target_idx', 0))
            if 0 <= target_idx < self.cb_target.count():
                self.cb_target.setCurrentIndex(target_idx)
            self.sb_distance_mm.setValue(     s.get('distance_mm',    self.sb_distance_mm.value()))
            # 'settle_window' is the pre-v1.16 name for the same spinbox; read
            # it as a fallback so an existing settings file keeps its value.
            self.sb_capture_frames.setValue(int(s.get('capture_frames',
                                                s.get('settle_window',
                                                      self.sb_capture_frames.value()))))
            self.sb_settle_mv.setValue(       s.get('settle_mv',      self.sb_settle_mv.value()))
            self.sb_warmup_s.setValue(        s.get('warmup_s',       self.sb_warmup_s.value()))
            w = int(s.get('window_w', 1000))
            h = int(s.get('window_h', 640))
            self.resize(w, h)
            x, y = s.get('window_x'), s.get('window_y')
            if x is not None and y is not None:
                self.move(int(x), int(y))
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            pass  # first run -- keep the widget defaults set above

    def _save_settings(self):
        s = {
            'port':           self.le_port.text(),
            'target_idx':     self.cb_target.currentIndex(),
            'distance_mm':    self.sb_distance_mm.value(),
            'capture_frames': self.sb_capture_frames.value(),
            'settle_mv':      self.sb_settle_mv.value(),
            'warmup_s':       self.sb_warmup_s.value(),
            'window_w':       self.width(),
            'window_h':       self.height(),
            'window_x':       self.x(),
            'window_y':       self.y(),
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
        if self.serial.isOpen():
            self.send_command('E')
            self.serial.waitForBytesWritten(200)
        if self._log_file:
            self._close_acquisition('session-closed')
            self._write_log('META', 'session closed')
            self._log_file.close()
        if self.serial.isOpen():
            self.serial.close()
        super().closeEvent(event)


def _parse_w_line(raw):
    """Parses 'W<profile_idx>,<time_ms>,<mean_ch0>,<mean_ch1>,...'.
    Returns (time_ms, [channel_uv, ...]) or None on malformed input."""
    try:
        _, rest = raw.split(',', 1)
        time_ms_str, chans_str = rest.split(',', 1)
        time_ms = float(time_ms_str)
        channels = [float(x) for x in chans_str.split(',')]
        if not channels:
            return None
        return time_ms, channels
    except (ValueError, IndexError):
        return None


def _scan_session_file(path):
    """Scans a rawlog_*.txt session file to recover resume state: the profile
    path from the last META line, cumulative streamed seconds (summed
    positive time_ms deltas across RAW W... lines), and any acquisition still
    open at the end of the file.

    Segments are bracketed as of v1.16: `MARK acquire target|air` opens one and
    `MARK acquire end` closes it, so "still open" means the file ends mid-capture
    (a stop, a crash, or a session closed early). Logs written before v1.16 have
    no end markers, and for those the last acquire marker reads as open to the
    end of the file -- which is exactly what it meant at the time, so old
    sessions still resume correctly."""
    profile_path = None
    streamed_s = 0.0
    last_w_ms = None
    open_acquisition = None

    with open(path) as f:
        for line in f:
            try:
                _, tag, text = line.rstrip('\n').split(' ', 2)
            except ValueError:
                continue

            if tag == 'META' and 'profile=' in text:
                for tok in shlex.split(text):
                    if tok.startswith('profile='):
                        profile_path = tok[len('profile='):]

            elif tag == 'RAW' and text.startswith('W'):
                parsed = _parse_w_line(text)
                if parsed is not None:
                    time_ms, _channels = parsed
                    if last_w_ms is not None and time_ms > last_w_ms:
                        streamed_s += (time_ms - last_w_ms) / 1000.0
                    last_w_ms = time_ms

            elif tag == 'MARK':
                if text.startswith('acquire target '):
                    fields = {'mode': 'target'}
                    for tok in shlex.split(text[len('acquire target '):]):
                        if '=' in tok:
                            k, v = tok.split('=', 1)
                            fields[k] = v
                    open_acquisition = fields
                elif text.startswith('acquire end'):
                    # v1.16: segments are bracketed, so a completed capture is
                    # NOT still open. Without this a resume would re-arm a
                    # segment the operator had already finished and start
                    # appending fresh frames to it.
                    open_acquisition = None
                elif text.startswith('acquire air'):
                    open_acquisition = {'mode': 'air'}

    return {
        'profile_path': profile_path,
        'streamed_s': streamed_s,
        'open_acquisition': open_acquisition,
    }


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
