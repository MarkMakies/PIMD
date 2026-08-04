# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
# ###############################################################################
# PIMD Raw Logger v1.13
# Runs on Ubuntu desktop / laptop, standalone PyQt6 app (no .ui file)
#
# Deliberately dumb: loads a profile, streams it (Mode 2 dynamic profile,
# same as pimd_delaycal.py's THERMAL mode), and writes every line the
# firmware sends verbatim to a session log file -- no tables, no metrics
# derived from the cell data itself, so it can't develop the same class of
# display bug just fixed in pimd_delaycal.py (v1.43/v1.44) and gives a
# ground-truth raw record for later offline analysis. Structured "Acquire
# Target" / "Acquire Air" markers (from a target registry + distance field)
# stamp the start of each segment in the log so a later analysis pass can
# segment the raw stream by exactly which lines fall inside which
# acquisition; a free-text Note field remains for anything else worth
# flagging. A settle indicator (rolling per-channel std dev, own metric,
# independent of pimd_classviz.py) tells the operator when a segment has
# enough stable data to move on, and a warm-up indicator (cumulative
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

APP_VERSION = '1.13'

DYNAMIC_PROFILE_INDEX = 5   # matches pimd_mcu.py NUM_PROFILES / pimd_delaycal.py / pimd_classviz.py

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'profiles')
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'sessions')
TARGETS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'targets', 'targets_v4.csv')

# Fields copied inline into MARK acquire-target lines, so the raw log alone
# identifies what was in the field without needing targets_v4.csv alongside it.
TARGET_MARK_FIELDS = (
    'short_name', 'shape_class', 'material_class', 'mass_g',
    'dim_a_mm', 'dim_b_mm', 'dim_c_mm',
)

GRID_COL_WIDTH = 8   # chars per raw-µV cell -- covers signed 7-digit values


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
        self._acquiring = None   # None, or {'mode': 'target', ...} / {'mode': 'air'}

        self._settle_buf = collections.deque(maxlen=20)
        self._streamed_s = 0.0
        self._last_w_ms = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        conn_row = QHBoxLayout()
        conn_row.addWidget(QLabel('Port:'))
        self.le_port = QLineEdit('/dev/ttyACM0')
        conn_row.addWidget(self.le_port)
        self.pb_connect = QPushButton('Connect')
        self.pb_connect.clicked.connect(self._on_connect_clicked)
        conn_row.addWidget(self.pb_connect)
        root.addLayout(conn_row)

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
        settle_row.addWidget(QLabel('Settle window (frames):'))
        self.sb_settle_window = QSpinBox()
        self.sb_settle_window.setRange(5, 200)
        self.sb_settle_window.setValue(20)
        self.sb_settle_window.valueChanged.connect(self._on_settle_window_changed)
        settle_row.addWidget(self.sb_settle_window)
        settle_row.addWidget(QLabel('Settle <= (mV):'))
        self.sb_settle_mv = QDoubleSpinBox()
        self.sb_settle_mv.setRange(0.05, 50.0)
        self.sb_settle_mv.setSingleStep(0.05)
        self.sb_settle_mv.setValue(1.0)
        settle_row.addWidget(self.sb_settle_mv)
        self.lbl_settle = QLabel('Collecting 0/20')
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

        self.lbl_grid = QLabel('No frame yet.')
        self.lbl_grid.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        root.addWidget(self.lbl_grid)
        self.lbl_log_path = QLabel('Log file: —')
        root.addWidget(self.lbl_log_path)

        self.txt_activity = QPlainTextEdit()
        self.txt_activity.setReadOnly(True)
        self.txt_activity.setMaximumBlockCount(2000)
        root.addWidget(self.txt_activity, 1)

        self.resize(1000, 640)

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

    def _on_acquire_target_clicked(self):
        if not self._log_file or not self._targets:
            return
        target = self._targets[self.cb_target.currentIndex()]
        distance_mm = self.sb_distance_mm.value()
        self._write_log('MARK', f'acquire target {_mark_field_string(target, distance_mm)}')
        self._acquiring = {'mode': 'target', 'target_id': target['target_id'],
                            'short_name': target['short_name'], 'distance_mm': distance_mm}
        self.lbl_acquiring.setText(
            f'Acquiring: {target["short_name"]} ({target["target_id"]}) @ {distance_mm:g} mm')
        self._log(f'Acquiring target: {target["short_name"]} @ {distance_mm:g} mm')
        self._reset_settle_buf()

    def _on_acquire_air_clicked(self):
        if not self._log_file:
            return
        self._write_log('MARK', 'acquire air')
        self._acquiring = {'mode': 'air'}
        self.lbl_acquiring.setText('Acquiring: air (baseline).')
        self._log('Acquiring air (baseline).')
        self._reset_settle_buf()

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
                parsed = _parse_w_line(raw)
                if parsed is not None:
                    time_ms, channels = parsed
                    self._update_warmup(time_ms)
                    self._update_settle(channels)
                    self._update_grid_display(channels)

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
    # Grid display -- last streamed frame, band x delay layout (see the
    # module header's "Grid convention" note)
    # ------------------------------------------------------------------
    def _update_grid_display(self, channels):
        if self._profile is None:
            return
        n_bands = len(self._profile['bands'])
        header = (f'Last frame (raw line #{self._line_count}) -- {n_bands} band(s) top-to-bottom '
                  f'by increasing pulse width, delays left-to-right by increasing time, raw µV:')
        self.lbl_grid.setText(f'{header}\n{_format_grid(self._profile, channels)}')

    # ------------------------------------------------------------------
    # Settle indicator (own metric: rolling per-channel std dev -> mV)
    # ------------------------------------------------------------------
    def _on_settle_window_changed(self, n):
        self._settle_buf = collections.deque(self._settle_buf, maxlen=n)
        self._update_settle_label()

    def _update_settle(self, channels):
        self._settle_buf.append(channels)
        self._update_settle_label()

    def _update_settle_label(self):
        n = len(self._settle_buf)
        window = self.sb_settle_window.value()
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
    # Cleanup
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if self.serial.isOpen():
            self.send_command('E')
            self.serial.waitForBytesWritten(200)
        if self._log_file:
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
    positive time_ms deltas across RAW W... lines), and the most recent
    MARK acquire (target or air) -- there's no place/remove pairing to
    track, each acquire marker simply is the current state from that point."""
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
