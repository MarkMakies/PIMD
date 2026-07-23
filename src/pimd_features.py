# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
###############################################################################
# PIMD Feature Extractor (pimd_features.py) v7
# — offline session-CSV / gui_signatures-CSV -> training-corpus CSV converter
# Runs on Ubuntu desktop / laptop, standalone CLI script (no GUI, no Qt)
#
# Reads one or more input files -- either self-describing session-dump CSVs
# produced by ClassViz's "Record Session" feature, or gui_signatures_*.csv
# files produced directly by the Analysis tab's quick-capture (the primary
# corpus source since pimd_classviz.py v1.32) -- joins each row's target_id
# against the target registry (pimd_target_check.py), enforces that a single
# corpus build never spans more than one profile geometry (DESIGN §10/§11),
# and emits one row per (capture, cell) -- see the module docstring below for
# the exact column list.
#
# History (full detail in CHANGELOG.md):
#   v7 doc-only: supply provenance vocabulary now battery|psu (free text; older corpora may hold 'usb')
#   v6 structured target-metadata capture regime (registry-backed target_id + placement + provenance)
#   v5 plateau_amp_mV/splithalf_floor restored to the v1 corpus's L2 convention
#   v4 segment_from_marks auto-suffixes repeat visits ((rpt)/(rpt3)...); superseded by repeat_idx in v6
#   v3 fix parse_session_file: '# mark:' lines interspersed among data rows now parsed
#   v2 add --out-wide (one row per plateau, c00..c71 delta_mV vector)
#   v1 initial implementation (no-marks fallback air-reference; change-point defaults)
###############################################################################

"""Output corpus schema (the ML contract for downstream tooling).

CORPUS_HEADER (raw, unjoined -- also what pimd_classviz.py writes directly to
gui_signatures_*.csv, one row per (capture, cell)):
  session          -- session/file stem the capture came from
  capture_id       -- '<session>_cNN', unique per capture press
  captured_at      -- ISO-8601 local time the capture completed
  target_id        -- registry key (pimd_target_check.py), or 'air'
  short_name       -- denormalised from the registry at write time (display only; join on target_id)
  distance_mm      -- int, coil face -> nearest target surface
  long_axis        -- x|y|z|na, direction the registry's dim_a points
  face_normal      -- x|y|z|na, normal of the dim_a x dim_b face
  offset_x_mm      -- int, target centroid offset from coil centre (coil long axis)
  offset_y_mm      -- int, target centroid offset from coil centre (coil short axis)
  medium           -- air|soil|other
  repeat_idx       -- int >= 1, disambiguates repeated captures of the same placement tuple
  notes            -- free text, per-capture
  pulse_us         -- band pulse width
  threshold_v      -- cell sample threshold
  delta_mV         -- baseline-corrected amplitude for this cell
  plateau_amp_mV   -- ||delta_mV||_2 across all cells in this capture
  splithalf_floor  -- noise-floor estimate, same L2 convention as plateau_amp_mV
  quality          -- 'ok', or '+'-joined flags ('noisy', 'short')
  amp_mean_abs_mV  -- mean(|delta_mV|) across all cells in this capture
  profile_name     -- loaded profile JSON's 'name' field
  profile_sha8     -- first 8 hex chars of SHA-256 of the profile JSON bytes as loaded
  fw_version       -- parsed from the board's V-identify reply
  tool_version     -- capturing tool's version string
  supply           -- battery|psu (free text; older corpora may contain 'usb')

JOINED_CORPUS_HEADER = CORPUS_HEADER plus, from a registry join on target_id
(blank for 'air'; pimd_features.py's own --out corpus build only):
  shape_class, dim_a_mm, dim_b_mm, dim_c_mm, wall_thickness_mm, closed_loop,
  mass_g, magnet_test, material_class, plating_material, substrate

Wide format (--out-wide, one row per capture instead of per cell):
  WIDE_METADATA_FIELDS + WIDE_SCALAR_FIELDS + c00..cNN (delta_mV vector, same
  channel order as CORPUS_HEADER's per-cell rows) + WIDE_TAIL_FIELDS, plus
  the same registry-joined columns appended for pimd_features.py's own build.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import pimd_target_check

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_VERSION = 'pimd_features.py v7'

AIR_THRESHOLD_MV_DEFAULT         = 0.25   # mean|delta| below this -> "air"
SETTLE_S_DEFAULT                 = 2.0    # marks path: trim after each mark for hand-transient settling
CHANGEPOINT_WINDOW_S_DEFAULT     = 1.0    # no-marks fallback: smoothing window
CHANGEPOINT_THRESHOLD_MV_DEFAULT = 0.15   # no-marks fallback: transition threshold on smoothed diff
MIN_SEGMENT_S_DEFAULT            = 4.0    # no-marks fallback: merge-short-into-neighbor floor

CENTRAL_FRACTION      = 0.60   # trim 20% off each end of a stable plateau before taking stats
MIN_CENTRAL_FRAMES    = 60     # below this -> quality flag "short"
NOISY_RATIO_THRESHOLD = 0.20   # splithalf_floor > this * plateau_amp_mV -> quality flag "noisy"
QUALITY_FLAG_SEP      = '+'    # NOT ',' -- every CSV in this repo is parsed with a plain split(',')
NOMINAL_FRAME_RATE_HZ = 7.3    # sanity-check only; actual rate is always measured from the data

MARK_TARGET_MATCH_TOL_S = 2.0   # max |dt| between a 'mark:' and its 'mark_target:' companion line

CORPUS_HEADER_FIELDS = [
    'session', 'capture_id', 'captured_at', 'target_id', 'short_name', 'distance_mm',
    'long_axis', 'face_normal', 'offset_x_mm', 'offset_y_mm', 'medium', 'repeat_idx', 'notes',
    'pulse_us', 'threshold_v', 'delta_mV', 'plateau_amp_mV', 'splithalf_floor', 'quality',
    'amp_mean_abs_mV', 'profile_name', 'profile_sha8', 'fw_version', 'tool_version', 'supply',
]
CORPUS_HEADER = ','.join(CORPUS_HEADER_FIELDS)

JOINED_EXTRA_FIELDS = ['shape_class', 'dim_a_mm', 'dim_b_mm', 'dim_c_mm', 'wall_thickness_mm',
                        'closed_loop', 'mass_g', 'magnet_test', 'material_class',
                        'plating_material', 'substrate']
JOINED_CORPUS_HEADER_FIELDS = CORPUS_HEADER_FIELDS + JOINED_EXTRA_FIELDS
JOINED_CORPUS_HEADER = ','.join(JOINED_CORPUS_HEADER_FIELDS)

WIDE_METADATA_FIELDS = ['session', 'capture_id', 'captured_at', 'target_id', 'short_name',
                         'distance_mm', 'long_axis', 'face_normal', 'offset_x_mm', 'offset_y_mm',
                         'medium', 'repeat_idx', 'notes']
WIDE_SCALAR_FIELDS = ['plateau_amp_mV', 'splithalf_floor', 'quality']
WIDE_TAIL_FIELDS = ['amp_mean_abs_mV', 'profile_name', 'profile_sha8', 'fw_version',
                     'tool_version', 'supply']


def warn(session_path, message):
    print('[WARN] {0}: {1}'.format(os.path.basename(session_path), message), file=sys.stderr)


def skip(session_path, message):
    print('[SKIP] {0}: {1}'.format(os.path.basename(session_path), message), file=sys.stderr)


def profile_sha8_of_bytes(raw_bytes):
    """First 8 hex chars of SHA-256 of `raw_bytes`. Per the target-metadata
    capture regime, this must be the profile JSON bytes as loaded/embedded --
    NOT a freshly re-json.dumps'd canonical form. Two content-identical but
    differently-formatted JSON files legitimately produce different sha8s;
    that's intentional (a provenance fingerprint of the literal artifact
    used, pinning geometry per DESIGN §10 -- not a semantic-equality check)."""
    return hashlib.sha256(raw_bytes).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Session CSV parsing
# ---------------------------------------------------------------------------

@dataclass
class SessionData:
    path: str
    session_start_iso: str
    tool_version: str
    n_bands: int
    n_cells: int
    n_channels: int
    profile: dict
    profile_raw_json: str    # exact embedded JSON substring, for the profile_sha8 fallback
    profile_sha8_explicit: object   # str or None -- authoritative when present (see module changelog v6.3)
    fw_version: str
    supply: str
    colmap: list            # list[dict] length n_channels: band_index, freq_hz, pulse_us, delay_us, threshold_v
    session_notes: str
    marks: list              # list[(datetime, str)]
    mark_targets: list        # list[(datetime, dict)] -- structured 'mark_target:' companions
    t0: datetime              # first frame's pc_wallclock timestamp (epoch for t_seconds / mark alignment)
    t_seconds: np.ndarray      # (n,)
    frames_mV: np.ndarray       # (n, n_channels)
    flagged: np.ndarray           # (n,) bool


def _parse_mark_content(content):
    """content is the '#'-stripped text of a 'mark: <iso-ts>, <label>' line
    (with the 'mark:' prefix still attached). Returns (datetime, label)."""
    rest = content.split(':', 1)[1].strip()
    ts_str, _, label = rest.partition(',')
    return datetime.fromisoformat(ts_str.strip()), label.strip()


_MARK_TARGET_KEYS = ['target_id', 'distance_mm', 'long_axis', 'face_normal', 'offset_x_mm',
                     'offset_y_mm', 'medium', 'repeat_idx', 'notes']


def parse_mark_target_line(content):
    """content is the '#'-stripped text of a 'mark_target: <iso-ts>, <csv
    fields>' line (with the 'mark_target:' prefix still attached). Returns
    (datetime, dict) with keys _MARK_TARGET_KEYS, or None if content isn't a
    mark_target line. The field portion is parsed with csv.reader (not a
    plain split) so a quoted comma inside `notes` survives -- classviz writes
    it with csv.writer, not hand-join."""
    if not content.startswith('mark_target:'):
        return None
    rest = content.split(':', 1)[1]
    ts_str, _, field_str = rest.strip().partition(',')
    reader = csv.reader(io.StringIO(field_str.strip()))
    raw_fields = next(reader, [])
    d = dict(zip(_MARK_TARGET_KEYS, (f.strip() for f in raw_fields)))
    d.setdefault('target_id', '')
    d['distance_mm'] = float(d['distance_mm']) if d.get('distance_mm') else None
    d['offset_x_mm'] = int(float(d['offset_x_mm'])) if d.get('offset_x_mm') else 0
    d['offset_y_mm'] = int(float(d['offset_y_mm'])) if d.get('offset_y_mm') else 0
    d['repeat_idx'] = int(float(d['repeat_idx'])) if d.get('repeat_idx') else 1
    d.setdefault('long_axis', 'na')
    d.setdefault('face_normal', 'na')
    d.setdefault('medium', 'air')
    d.setdefault('notes', '')
    return datetime.fromisoformat(ts_str.strip()), d


def _fw_version_from_v_response(raw):
    """raw is the literal V-identify reply string (e.g. 'V4.26,1,5,4,...').
    Mirrors pimd_classviz.py's _parsed_fw_version() -- same read-only
    extraction, no protocol involvement."""
    if not raw or raw.startswith('unknown'):
        return 'unknown'
    parts = raw.split(',')
    return parts[0].lstrip('V').strip() if parts else 'unknown'


def parse_session_file(path):
    marks = []
    mark_targets = []
    colmap = []
    profile = None
    profile_raw_json = ''
    profile_sha8_explicit = None
    firmware_v_response_raw = None
    fw_version_explicit = None
    supply = 'unknown'
    notes_lines = []
    n_bands = n_cells = n_channels = None
    session_start_iso = None
    tool_version = None
    header_done = False

    pc_ts_raw = []
    fw_ms = []
    rows = []
    flagged = []

    with open(path, 'r') as f:
        for line in f:
            line = line.rstrip('\n')
            if not header_done:
                if line.startswith('#'):
                    content = line[1:].strip()
                    if content.startswith('session_start_iso:'):
                        session_start_iso = content.split(':', 1)[1].strip()
                    elif content.startswith('tool:'):
                        tool_version = content.split(':', 1)[1].strip()
                    elif content.startswith('n_bands:'):
                        m = re.search(r'n_bands:\s*(\d+)\s+n_cells:\s*(\d+)\s+n_channels:\s*(\d+)', content)
                        if m:
                            n_bands, n_cells, n_channels = (int(x) for x in m.groups())
                    elif content.startswith('profile_json:'):
                        profile_raw_json = content.split(':', 1)[1].strip()
                        profile = json.loads(profile_raw_json)
                    elif content.startswith('profile_sha8:'):
                        profile_sha8_explicit = content.split(':', 1)[1].strip()
                    elif content.startswith('fw_version:'):
                        fw_version_explicit = content.split(':', 1)[1].strip()
                    elif content.startswith('firmware_v_response'):
                        _, _, raw = content.partition('): ')
                        firmware_v_response_raw = raw.strip()
                    elif content.startswith('supply:'):
                        supply = content.split(':', 1)[1].strip()
                    elif content.startswith('colmap_fields:'):
                        pass  # fixed known order (col_index,band_index,freq_hz,pulse_us,delay_us,threshold_v)
                    elif content.startswith('colmap:'):
                        parts = [p.strip() for p in content.split(':', 1)[1].strip().split(',')]
                        thr = parts[5] if len(parts) > 5 else ''
                        colmap.append({
                            'band_index': int(parts[1]),
                            'freq_hz': int(parts[2]),
                            'pulse_us': float(parts[3]),
                            'delay_us': float(parts[4]),
                            'threshold_v': float(thr) if thr else float('nan'),
                        })
                    elif content.startswith('session_notes:'):
                        notes_lines.append(content.split(':', 1)[1].strip())
                    elif content.startswith('mark_target:'):
                        parsed = parse_mark_target_line(content)
                        if parsed:
                            mark_targets.append(parsed)
                    elif content.startswith('mark:'):
                        marks.append(_parse_mark_content(content))
                    # else: unrecognised '#' line (active_profile_idx, ...) - ignored
                    continue
                else:
                    data_header_cols = line.split(',')
                    header_done = True
                    continue
            else:
                if not line:
                    continue
                if line.startswith('#'):
                    # Ground-truth marks are written live as the operator advances
                    # targets, so they land interspersed among data rows, not just
                    # before the first one -- must still be recognised here.
                    content = line[1:].strip()
                    if content.startswith('mark_target:'):
                        parsed = parse_mark_target_line(content)
                        if parsed:
                            mark_targets.append(parsed)
                    elif content.startswith('mark:'):
                        marks.append(_parse_mark_content(content))
                    # else: unrecognised '#' line mid-stream - ignored
                    continue
                parts = line.split(',')
                pc_ts_raw.append(parts[0])
                fw_ms.append(int(parts[1]))
                rows.append([int(v) for v in parts[2:2 + n_channels]])
                flagged.append(parts[2 + n_channels] == '1')

    if not rows:
        raise ValueError('no data rows found')
    if len(colmap) != n_channels:
        raise ValueError('colmap has {0} entries, expected n_channels={1}'.format(len(colmap), n_channels))
    if len(data_header_cols) != 2 + n_channels + 1:
        warn(path, 'CSV header column count ({0}) does not match n_channels={1}'.format(
            len(data_header_cols), n_channels))

    pc_ts = [datetime.fromisoformat(s) for s in pc_ts_raw]
    t0 = pc_ts[0]
    t_seconds = np.array([(t - t0).total_seconds() for t in pc_ts], dtype=np.float64)
    frames_mV = np.array(rows, dtype=np.float64) / 1000.0
    flagged_arr = np.array(flagged, dtype=bool)

    fw_version = fw_version_explicit or _fw_version_from_v_response(firmware_v_response_raw)

    return SessionData(
        path=path, session_start_iso=session_start_iso, tool_version=tool_version,
        n_bands=n_bands, n_cells=n_cells, n_channels=n_channels, profile=profile,
        profile_raw_json=profile_raw_json, profile_sha8_explicit=profile_sha8_explicit,
        fw_version=fw_version, supply=supply,
        colmap=colmap, session_notes='\n'.join(notes_lines), marks=marks,
        mark_targets=mark_targets,
        t0=t0, t_seconds=t_seconds, frames_mV=frames_mV, flagged=flagged_arr,
    )


def session_profile_sha8(sess):
    """The authoritative profile_sha8 for a parsed session dump: prefer the
    explicit '# profile_sha8:' line (classviz computed it from the literal
    loaded bytes -- see module changelog v6.3) and only fall back to hashing
    the embedded '# profile_json:' text for dumps that predate that line."""
    if sess.profile_sha8_explicit:
        return sess.profile_sha8_explicit
    return profile_sha8_of_bytes(sess.profile_raw_json.encode('utf-8'))


def drop_flagged(sess):
    mask = ~sess.flagged
    if mask.all():
        return sess
    sess.t_seconds = sess.t_seconds[mask]
    sess.frames_mV = sess.frames_mV[mask]
    sess.flagged = sess.flagged[mask]
    return sess


def measure_frame_rate_hz(t_seconds):
    dt = np.median(np.diff(t_seconds))
    return 1.0 / dt if dt > 0 else NOMINAL_FRAME_RATE_HZ


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

@dataclass
class Plateau:
    target_id: object     # str, or None if no structured metadata could be resolved (row is skipped)
    short_name: str
    distance_mm: object    # int/float or None (air)
    long_axis: str           # x|y|z|na
    face_normal: str          # x|y|z|na
    offset_x_mm: int
    offset_y_mm: int
    medium: str                # air|soil|other
    repeat_idx: int
    notes: str
    is_air: bool
    start_idx: int
    end_idx: int              # [start_idx, end_idx) into the flagged-dropped frame arrays


def parse_mark_label(raw_text):
    """Legacy '@distance' free-text parser -- kept as the fallback for
    old-style 'mark:' lines with no 'mark_target:' companion. Returns
    (label, distance_cm, is_air); label is NOT a target_id."""
    text = raw_text.strip()
    if text.lower() == 'air':
        return 'air', None, True
    m = re.match(r'^(.*)@\s*(-?\d+(?:\.\d+)?)\s*$', text)
    if m:
        return m.group(1).strip(), float(m.group(2)), False
    return text, None, False


def _match_mark_targets(marks_sorted, mark_targets, tol_s=MARK_TARGET_MATCH_TOL_S):
    """Nearest-timestamp match each mark to its 'mark_target:' companion
    (classviz writes them back-to-back, so they're microseconds apart, not
    exactly equal). Returns dict[mark_dt -> mark_target dict]. Each
    mark_target entry is consumed by at most one mark."""
    remaining = sorted(mark_targets, key=lambda mt: mt[0])
    matched = {}
    for mark_dt, _ in marks_sorted:
        best_i, best_delta = None, None
        for i, (mt_dt, _mt_dict) in enumerate(remaining):
            delta = abs((mt_dt - mark_dt).total_seconds())
            if best_delta is None or delta < best_delta:
                best_i, best_delta = i, delta
        if best_i is not None and best_delta <= tol_s:
            matched[mark_dt] = remaining.pop(best_i)[1]
    return matched


def segment_from_marks(sess, frame_rate_hz, settle_s, targets):
    marks_sorted = sorted(sess.marks, key=lambda m: m[0])
    matched_targets = _match_mark_targets(marks_sorted, sess.mark_targets)
    n = len(marks_sorted)
    settle_frames = int(round(settle_s * frame_rate_hz))
    plateaus = []
    for i, (mark_dt, raw_text) in enumerate(marks_sorted):
        mark_t = (mark_dt - sess.t0).total_seconds()
        start_idx = min(int(np.searchsorted(sess.t_seconds, mark_t)) + settle_frames, len(sess.t_seconds))
        if i + 1 < n:
            end_t = (marks_sorted[i + 1][0] - sess.t0).total_seconds()
            end_idx = int(np.searchsorted(sess.t_seconds, end_t))
        else:
            end_idx = len(sess.t_seconds)
        if start_idx >= end_idx:
            warn(sess.path, "plateau '{0}' has no frames left after settle trim, skipping".format(raw_text))
            continue

        mt = matched_targets.get(mark_dt)
        if mt is not None:
            target_id = mt['target_id'] or None
            is_air = (target_id == 'air')
            short_name = targets[target_id].short_name if target_id in targets else ''
            plateaus.append(Plateau(
                target_id=target_id, short_name=short_name, distance_mm=mt['distance_mm'],
                long_axis=mt['long_axis'], face_normal=mt['face_normal'],
                offset_x_mm=mt['offset_x_mm'], offset_y_mm=mt['offset_y_mm'], medium=mt['medium'],
                repeat_idx=mt['repeat_idx'], notes=mt['notes'], is_air=is_air,
                start_idx=start_idx, end_idx=end_idx))
            continue

        # Legacy fallback: no structured companion line for this mark. 'air'
        # still resolves cleanly ('air' is a valid pseudo target_id with no
        # registry row needed); a real free-text target label does not --
        # there is no label -> target_id migration (same "no migration code"
        # principle as the pre-v1.32 gui_signatures rejection), so it's
        # loudly warned and excluded from output.
        label, distance_cm, is_air = parse_mark_label(raw_text)
        if is_air:
            plateaus.append(Plateau(
                target_id='air', short_name='', distance_mm=None, long_axis='na', face_normal='na',
                offset_x_mm=0, offset_y_mm=0, medium='air', repeat_idx=1, notes='',
                is_air=True, start_idx=start_idx, end_idx=end_idx))
        else:
            warn(sess.path, "mark '{0}' predates structured target capture (no 'mark_target:' "
                             "companion) -- its rows cannot join the registry and will be "
                             "skipped; re-capture under pimd_classviz.py >= v1.32".format(raw_text))
            distance_mm = distance_cm * 10.0 if distance_cm is not None else None
            plateaus.append(Plateau(
                target_id=None, short_name=label, distance_mm=distance_mm, long_axis='na',
                face_normal='na', offset_x_mm=0, offset_y_mm=0, medium='air', repeat_idx=1,
                notes='', is_air=False, start_idx=start_idx, end_idx=end_idx))
    return plateaus


def detect_changepoints(frames_mV, frame_rate_hz, window_s, threshold_mv, min_seg_s):
    """Rolling-window mean-abs-diff change-point detection.

    diff[i] = mean_c(|X[i] - X[i-1]|) in mV is a single scalar per frame that
    spikes whenever a meaningful fraction of the 72 channels moves together
    (a hand introducing/removing a target ramps most channels over ~1-2s);
    sensor noise moves channels independently and mostly cancels in the mean.
    Smoothing with a centered moving average of ~1s suppresses single-frame
    noise without blurring real (multi-second) transitions. Frames where the
    smoothed signal exceeds threshold_mv are "transition" frames, excluded
    from every plateau; maximal runs of frames below threshold are candidate
    plateaus. Runs shorter than min_seg_s are merged into their nearer
    neighbor -- too short to be a genuine dwell, more likely a blip mid-
    transition.
    """
    n = frames_mV.shape[0]
    if n < 2:
        return [(0, n)]
    diff = np.mean(np.abs(np.diff(frames_mV, axis=0)), axis=1)  # (n-1,)
    window_frames = max(1, int(round(window_s * frame_rate_hz)))
    kernel = np.ones(window_frames) / window_frames
    smoothed = np.convolve(diff, kernel, mode='same')
    is_transition = smoothed > threshold_mv

    stable = np.empty(n, dtype=bool)
    stable[0] = True
    stable[1:] = ~is_transition

    runs = []
    start = None
    for i, s in enumerate(stable):
        if s and start is None:
            start = i
        elif not s and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, n))

    min_seg_frames = max(1, int(round(min_seg_s * frame_rate_hz)))
    return merge_short_segments(runs, min_seg_frames)


def merge_short_segments(runs, min_seg_frames):
    out = list(sorted(runs))
    changed = True
    while changed and len(out) > 1:
        changed = False
        for i, (s, e) in enumerate(out):
            if e - s < min_seg_frames:
                if i > 0:
                    ps, pe = out[i - 1]
                    out[i - 1] = (ps, e)
                    del out[i]
                else:
                    ns, ne = out[i + 1]
                    out[i] = (s, ne)
                    del out[i + 1]
                changed = True
                break
    return out


def classify_segments(runs, frames_mV, air_threshold_mv):
    """No-marks fallback: classify each candidate run as air/target.

    Assumes the standard capture protocol -- recording starts with the
    sensor resting in air, before the first target is introduced -- so the
    chronologically *first* candidate run is taken as the air reference.
    (An earlier revision tried a session-wide median-of-segment-medians as a
    baseline instead; that broke down on real captures with only a handful
    of segments, where the median has no reason to land near true air --
    confirmed empirically against session_20260703_104324.csv, where the
    visually-flat opening segment scored *further* from that median than
    later target segments did.) Every other run is compared against the
    first run's median; anything close enough is also "air" (the operator
    re-zeroing between targets), everything else is a target. Target
    segments carry target_id=None -- there is no ground truth for *which*
    physical target a run corresponds to without marks, so guessing from
    session_notes text would risk silently mislabelling training data (and,
    since v6, a placeholder like 'segment_01' was never a valid registry
    target_id anyway) -- these plateaus produce no output rows, only a
    warning. If the session doesn't actually open in air (a target already
    in place at record-start), this heuristic will anchor on that target
    instead -- a real limitation without marks; use the mark hotkeys
    (pimd_classviz.py v1.19+, target-registry-aware since v1.32) to remove
    the ambiguity entirely.
    """
    seg_medians = [np.median(frames_mV[s:e], axis=0) for s, e in runs]
    air_reference = seg_medians[0]
    plateaus = []
    target_n = 0
    for (s, e), med in zip(runs, seg_medians):
        is_air = np.mean(np.abs(med - air_reference)) < air_threshold_mv
        if is_air:
            plateaus.append(Plateau('air', '', None, 'na', 'na', 0, 0, 'air', 1, '', True, s, e))
        else:
            target_n += 1
            plateaus.append(Plateau(None, 'segment_{0:02d}'.format(target_n), None, 'na', 'na',
                                     0, 0, 'air', 1, '', False, s, e))
    return plateaus


def plateau_display_label(p):
    if p.is_air:
        return 'air'
    return p.target_id if p.target_id else '(unresolved: {0})'.format(p.short_name or '?')


# ---------------------------------------------------------------------------
# Baseline (thermal drift correction, DESIGN §3/§17.5) and per-plateau stats
# ---------------------------------------------------------------------------

def central_frames(plateau, central_fraction=CENTRAL_FRACTION):
    n = plateau.end_idx - plateau.start_idx
    trim = int(round(n * (1 - central_fraction) / 2))
    c_start, c_end = plateau.start_idx + trim, plateau.end_idx - trim
    if c_end <= c_start:
        return plateau.start_idx, plateau.end_idx
    return c_start, c_end


def build_baseline_anchors(air_plateaus, frames_mV, t_seconds):
    anchor_ts, anchor_vs = [], []
    for p in air_plateaus:
        c_start, c_end = central_frames(p)
        anchor_ts.append(np.median(t_seconds[c_start:c_end]))
        anchor_vs.append(np.median(frames_mV[c_start:c_end], axis=0))
    order = np.argsort(anchor_ts)
    return np.array(anchor_ts)[order], np.array(anchor_vs)[order]


def baseline_at(t, anchor_ts, anchor_vs):
    """Evaluate the piecewise-linear per-channel baseline at scalar or array
    time(s) t. np.interp clamps outside [anchor_ts[0], anchor_ts[-1]] to the
    nearest anchor value (flat extrapolation) -- drift correction is
    unavailable before the first air capture and after the last."""
    t = np.atleast_1d(t)
    out = np.stack([np.interp(t, anchor_ts, anchor_vs[:, c]) for c in range(anchor_vs.shape[1])], axis=-1)
    return out[0] if out.shape[0] == 1 and np.isscalar(t[0]) else out


def compute_plateau_stats(frames_mV, t_seconds, c_start, c_end, anchor_ts, anchor_vs):
    """Two distinct amplitude conventions are computed here, both over the
    72-cell drift-corrected delta_mV vector -- do not conflate them:

      plateau_amp_mV  = ||delta_mV||_2 (L2 / Euclidean norm across cells).
                         This is the v1 hand-built corpus's convention (and
                         the canary-strength unit's: 1 unit == copper pipe
                         120g @ 10cm == 45 mV L2) -- cross-campaign amplitude
                         comparisons and F9 falloff constants are stated in
                         this unit, so this column must stay L2.
      amp_mean_abs_mV = mean(|delta_mV|) per cell. A different, smaller
                         quantity (L2 norm is ~sqrt(n_cells) times mean|.|
                         for comparable per-cell magnitudes) -- kept under
                         its own honest name since it's still a useful,
                         differently-scaled amplitude summary.

    splithalf_floor uses the same L2 convention as plateau_amp_mV (over the
    half-difference vector, still halved) so floor/amp stays a meaningful,
    convention-consistent fraction for the noisy-quality gate below."""
    central = frames_mV[c_start:c_end]
    center_t = float(np.median(t_seconds[c_start:c_end]))
    median_frame = np.median(central, axis=0)
    baseline_vec = baseline_at(center_t, anchor_ts, anchor_vs)
    delta_mV = median_frame - baseline_vec
    plateau_amp_mV = float(np.linalg.norm(delta_mV))
    amp_mean_abs_mV = float(np.mean(np.abs(delta_mV)))

    half = len(central) // 2
    if half == 0:
        splithalf_floor = 0.0
    else:
        first_med = np.median(central[:half], axis=0)
        second_med = np.median(central[half:], axis=0)
        splithalf_floor = float(np.linalg.norm(first_med - second_med) / 2.0)

    return delta_mV, plateau_amp_mV, amp_mean_abs_mV, splithalf_floor, len(central), center_t


def quality_flags(splithalf_floor, plateau_amp_mV, n_central_frames):
    flags = []
    if plateau_amp_mV > 1e-9 and splithalf_floor > NOISY_RATIO_THRESHOLD * plateau_amp_mV:
        flags.append('noisy')
    if n_central_frames < MIN_CENTRAL_FRAMES:
        flags.append('short')
    return QUALITY_FLAG_SEP.join(flags) if flags else 'ok'


# ---------------------------------------------------------------------------
# Output rows
# ---------------------------------------------------------------------------

def format_value(x, ndp=3):
    return str(round(float(x), ndp))


def format_distance(x):
    if x is None:
        return ''
    xf = float(x)
    return str(int(xf)) if xf.is_integer() else format_value(xf)


def build_rows(session_stem, capture_id, captured_at, plateau, colmap, delta_mV, plateau_amp_mV,
               splithalf_floor, quality, amp_mean_abs_mV, profile_name, profile_sha8,
               fw_version, tool_version, supply, session_path):
    """One dict per cell, keyed by CORPUS_HEADER_FIELDS -- unjoined (no
    registry columns). This is the exact row shape pimd_classviz.py writes
    directly to gui_signatures_*.csv; pimd_features.py's own --out corpus
    build appends the registry-joined columns afterward (registry_join_
    fields()), so both callers share this one implementation."""
    if plateau.target_id is None:
        raise ValueError('build_rows() called on an unresolved plateau (target_id=None) -- '
                          'callers must skip these, see plateau_display_label()')
    rows = []
    for ch, c in enumerate(colmap):
        rows.append({
            'session': session_stem, 'capture_id': capture_id, 'captured_at': captured_at,
            'target_id': plateau.target_id, 'short_name': plateau.short_name,
            'distance_mm': format_distance(plateau.distance_mm),
            'long_axis': plateau.long_axis, 'face_normal': plateau.face_normal,
            'offset_x_mm': str(int(plateau.offset_x_mm)), 'offset_y_mm': str(int(plateau.offset_y_mm)),
            'medium': plateau.medium, 'repeat_idx': str(int(plateau.repeat_idx)), 'notes': plateau.notes,
            'pulse_us': format_value(c['pulse_us']), 'threshold_v': format_value(c['threshold_v']),
            'delta_mV': format_value(delta_mV[ch]), 'plateau_amp_mV': format_value(plateau_amp_mV),
            'splithalf_floor': format_value(splithalf_floor), 'quality': quality,
            'amp_mean_abs_mV': format_value(amp_mean_abs_mV),
            'profile_name': profile_name or '', 'profile_sha8': profile_sha8 or '',
            'fw_version': fw_version or 'unknown', 'tool_version': tool_version, 'supply': supply,
        })
    return rows


def build_wide_row(session_stem, capture_id, captured_at, plateau, delta_mV, plateau_amp_mV,
                    splithalf_floor, quality, amp_mean_abs_mV, profile_name, profile_sha8,
                    fw_version, tool_version, supply):
    """One dict per plateau (not per cell): same metadata as build_rows() plus
    the full delta_mV vector as c00..cNN. Built from the exact values already
    computed for the long rows -- never recomputed -- so long and wide can't
    drift apart for the same plateau."""
    row = {
        'session': session_stem, 'capture_id': capture_id, 'captured_at': captured_at,
        'target_id': plateau.target_id, 'short_name': plateau.short_name,
        'distance_mm': format_distance(plateau.distance_mm),
        'long_axis': plateau.long_axis, 'face_normal': plateau.face_normal,
        'offset_x_mm': str(int(plateau.offset_x_mm)), 'offset_y_mm': str(int(plateau.offset_y_mm)),
        'medium': plateau.medium, 'repeat_idx': str(int(plateau.repeat_idx)), 'notes': plateau.notes,
        'plateau_amp_mV': format_value(plateau_amp_mV), 'splithalf_floor': format_value(splithalf_floor),
        'quality': quality, 'amp_mean_abs_mV': format_value(amp_mean_abs_mV),
        'profile_name': profile_name or '', 'profile_sha8': profile_sha8 or '',
        'fw_version': fw_version or 'unknown', 'tool_version': tool_version, 'supply': supply,
    }
    for i, v in enumerate(delta_mV):
        row['c{0:02d}'.format(i)] = format_value(v)
    return row


def registry_join_fields(target_id, targets):
    """Returns dict[JOINED_EXTRA_FIELDS] for target_id: blank for 'air',
    looked-up registry values for a known id. Raises KeyError(target_id) for
    an id not present in `targets` -- callers translate that into a hard,
    file-naming SystemExit (unknown target_id is a hard error, not a
    degraded row)."""
    if target_id == 'air':
        return {k: '' for k in JOINED_EXTRA_FIELDS}
    if target_id not in targets:
        raise KeyError(target_id)
    t = targets[target_id]
    return {
        'shape_class': t.shape_class,
        'dim_a_mm': format_value(t.dim_a_mm), 'dim_b_mm': format_value(t.dim_b_mm),
        'dim_c_mm': format_value(t.dim_c_mm),
        'wall_thickness_mm': format_value(t.wall_thickness_mm) if t.wall_thickness_mm is not None else '',
        'closed_loop': t.closed_loop, 'mass_g': format_value(t.mass_g),
        'magnet_test': t.magnet_test, 'material_class': t.material_class,
        'plating_material': t.plating_material or '', 'substrate': t.substrate or '',
    }


def open_corpus_writer(out_path, append, fields):
    exists = os.path.isfile(out_path)
    if exists and not append:
        raise SystemExit('{0} already exists; pass --append to add to it, or choose a different --out.'.format(
            out_path))
    f = open(out_path, 'a' if exists else 'w', newline='')
    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    if not exists:
        writer.writerow(fields)
        f.flush()
    return f, writer


def open_wide_writer(out_path, append, fields):
    exists = os.path.isfile(out_path)
    if exists and not append:
        raise SystemExit('{0} already exists; pass --append to add to it, or choose a different --out-wide.'.format(
            out_path))
    f = open(out_path, 'a' if exists else 'w', newline='')
    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    if not exists:
        writer.writerow(fields)
        f.flush()
    return f, writer


# ---------------------------------------------------------------------------
# Diagnostic plot
# ---------------------------------------------------------------------------

def plot_diagnostic(session_stem, out_png, sess, plateaus, anchor_ts, anchor_vs):
    n_bands, n_cells = sess.n_bands, sess.n_cells
    drift_corrected = sess.frames_mV - baseline_at(sess.t_seconds, anchor_ts, anchor_vs)
    band_mean = drift_corrected.reshape(-1, n_bands, n_cells).mean(axis=2)  # (n, n_bands)
    pulse_us = [b['pulse_us'] for b in sess.profile['bands']]

    fig, axes = plt.subplots(n_bands, 1, figsize=(14, 2.2 * n_bands), sharex=True)
    if n_bands == 1:
        axes = [axes]

    for b, ax in enumerate(axes):
        ax.plot(sess.t_seconds, band_mean[:, b], linewidth=0.8, color='tab:blue')
        ax.set_ylabel('{0:.3g}us band\n(mV)'.format(pulse_us[b]))
        ax.axhline(0.0, color='0.7', linewidth=0.5)
        for p in plateaus:
            color = 'tab:green' if p.is_air else 'tab:orange'
            ax.axvspan(sess.t_seconds[p.start_idx], sess.t_seconds[min(p.end_idx, len(sess.t_seconds) - 1)],
                       alpha=0.12, color=color)
            ax.axvline(sess.t_seconds[p.start_idx], color=color, linewidth=0.5, alpha=0.5)

    top = axes[0]
    ylim = top.get_ylim()
    for p in plateaus:
        c_start, c_end = min(p.start_idx, len(sess.t_seconds) - 1), min(p.end_idx, len(sess.t_seconds) - 1)
        center_t = sess.t_seconds[(c_start + c_end) // 2]
        top.text(center_t, ylim[1], plateau_display_label(p), rotation=45, va='bottom', fontsize=7)

    axes[-1].set_xlabel('time (s)')
    title = '{0} -- diagnostic'.format(session_stem)
    notes = sess.session_notes.strip()
    if notes and notes != '(none)':
        title += '\nnotes: {0}'.format(notes[:160] + ('...' if len(notes) > 160 else ''))
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Per-session orchestration
# ---------------------------------------------------------------------------

def process_session(path, args, targets):
    """Returns (rows: list[dict] in JOINED_CORPUS_HEADER_FIELDS shape,
    wide_rows: list[dict], group: (profile_name, profile_sha8) or None).
    Never raises past this function for parse/segmentation failures -- every
    such failure is caught at the narrowest reasonable scope and reported to
    stderr with [SKIP]/[WARN], so one bad session never aborts the batch. An
    unknown target_id IS allowed to raise SystemExit (via registry_join_
    fields()) -- that's a hard corpus-build error per the brief, not a
    per-session skip."""
    try:
        sess = parse_session_file(path)
    except Exception as e:
        skip(path, 'failed to parse -- {0}'.format(e))
        return [], [], None

    group = (sess.profile.get('name'), session_profile_sha8(sess))

    sess = drop_flagged(sess)
    if len(sess.t_seconds) < 2:
        skip(path, 'fewer than 2 usable frames after dropping flagged rows')
        return [], [], group
    frame_rate_hz = measure_frame_rate_hz(sess.t_seconds)
    if abs(frame_rate_hz - NOMINAL_FRAME_RATE_HZ) > 0.15 * NOMINAL_FRAME_RATE_HZ:
        warn(path, 'measured frame rate {0:.2f} Hz deviates >15% from nominal {1:.2f} Hz'.format(
            frame_rate_hz, NOMINAL_FRAME_RATE_HZ))

    if sess.marks:
        plateaus = segment_from_marks(sess, frame_rate_hz, args.settle_s, targets)
    else:
        runs = detect_changepoints(sess.frames_mV, frame_rate_hz, args.changepoint_window_s,
                                    args.changepoint_threshold_mv, args.min_segment_s)
        plateaus = classify_segments(runs, sess.frames_mV, args.air_threshold_mv)

    air_plateaus = [p for p in plateaus if p.is_air]
    if not air_plateaus:
        skip(path, 'no air segments found, cannot drift-correct')
        return [], [], group
    anchor_ts, anchor_vs = build_baseline_anchors(air_plateaus, sess.frames_mV, sess.t_seconds)
    if len(anchor_ts) == 1:
        warn(path, 'only one air anchor -- no drift correction possible, using a flat baseline')

    session_stem = os.path.splitext(os.path.basename(path))[0]
    profile_name, profile_sha8 = group
    rows, wide_rows = [], []
    seq = 0
    for p in plateaus:
        if p.is_air:
            continue
        if p.target_id is None:
            continue   # already warned in segment_from_marks()/classify_segments()
        try:
            c_start, c_end = central_frames(p)
            delta_mV, plateau_amp_mV, amp_mean_abs_mV, splithalf_floor, n_central, center_t = compute_plateau_stats(
                sess.frames_mV, sess.t_seconds, c_start, c_end, anchor_ts, anchor_vs)
            if center_t < anchor_ts[0] or center_t > anchor_ts[-1]:
                warn(path, "plateau '{0}' center falls outside the air-anchor time range -- "
                           "baseline is flat-extrapolated there".format(plateau_display_label(p)))
            quality = quality_flags(splithalf_floor, plateau_amp_mV, n_central)

            seq += 1
            capture_id = '{0}_c{1:02d}'.format(session_stem, seq)
            captured_at = (sess.t0 + timedelta(seconds=center_t)).isoformat()

            joined = registry_join_fields(p.target_id, targets)

            cell_rows = build_rows(session_stem, capture_id, captured_at, p, sess.colmap, delta_mV,
                                    plateau_amp_mV, splithalf_floor, quality, amp_mean_abs_mV,
                                    profile_name, profile_sha8, sess.fw_version, TOOL_VERSION,
                                    sess.supply, path)
            for row in cell_rows:
                row.update(joined)
            rows.extend(cell_rows)

            if args.out_wide:
                wide_row = build_wide_row(session_stem, capture_id, captured_at, p, delta_mV,
                                           plateau_amp_mV, splithalf_floor, quality, amp_mean_abs_mV,
                                           profile_name, profile_sha8, sess.fw_version, TOOL_VERSION,
                                           sess.supply)
                wide_row.update(joined)
                wide_rows.append(wide_row)
        except KeyError as e:
            raise SystemExit("{0}: unknown target_id '{1}' -- not in the registry and not "
                              "'air'".format(path, e.args[0]))
        except Exception as e:
            warn(path, "plateau '{0}' failed -- {1}".format(plateau_display_label(p), e))

    if not args.no_plot:
        try:
            plot_dir = args.plot_dir or os.path.dirname(os.path.abspath(path))
            out_png = os.path.join(plot_dir, '{0}_diagnostic.png'.format(session_stem))
            plot_diagnostic(session_stem, out_png, sess, plateaus, anchor_ts, anchor_vs)
        except Exception as e:
            warn(path, 'diagnostic plot failed -- {0}'.format(e))

    return rows, wide_rows, group


# ---------------------------------------------------------------------------
# gui_signatures_*.csv direct ingest (primary corpus source since classviz v1.32)
# ---------------------------------------------------------------------------

def sniff_input_kind(path):
    """Returns 'session_dump', 'gui_signatures', or 'legacy_gui_signatures'."""
    with open(path, newline='') as f:
        for line in f:
            if line.startswith('# PIMD session dump'):
                return 'session_dump'
            if line.startswith('#'):
                continue
            cols = next(csv.reader([line]))
            if 'target_id' in cols and 'distance_mm' in cols:
                return 'gui_signatures'
            if 'target' in cols and 'distance_cm' in cols:
                return 'legacy_gui_signatures'
            raise SystemExit('{0}: unrecognized input file (not a session dump or a '
                              'gui_signatures corpus CSV -- header: {1})'.format(path, line.strip()))
    raise SystemExit('{0}: empty file'.format(path))


def load_gui_signatures_csv(path):
    """Parses a v1.32+ gui_signatures_*.csv (CORPUS_HEADER schema) directly
    into one dict per row -- this file is already at full per-cell corpus-row
    granularity, no plateau/segmentation math needed."""
    with open(path, newline='') as f:
        lines = [line for line in f if not line.startswith('#')]
    return list(csv.DictReader(lines))


def process_gui_signatures_file(path, targets):
    """Returns (rows: list[dict] in JOINED_CORPUS_HEADER_FIELDS shape,
    groups: set[(profile_name, profile_sha8)] seen in this file)."""
    raw_rows = load_gui_signatures_csv(path)
    if not raw_rows:
        warn(path, 'no rows found')
        return [], set()
    out_rows = []
    groups = set()
    for r in raw_rows:
        target_id = r.get('target_id', '')
        try:
            joined = registry_join_fields(target_id, targets)
        except KeyError:
            raise SystemExit("{0}: unknown target_id '{1}' -- not in the registry and not "
                              "'air'".format(path, target_id))
        row = dict(r)
        row.update(joined)
        out_rows.append(row)
        groups.add((r.get('profile_name', ''), r.get('profile_sha8', '')))
    if len(groups) > 1:
        warn(path, 'file itself spans multiple profile geometries: {0}'.format(sorted(groups)))
    return out_rows, groups


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser():
    p = argparse.ArgumentParser(
        description='Convert PIMD ClassViz session-dump or gui_signatures CSVs into a '
                    'registry-joined training-corpus CSV.')
    p.add_argument('sessions', nargs='+',
                    help='One or more session_*.csv (session-dump) or gui_signatures_*.csv files.')
    p.add_argument('--out', required=True, help='Output/append long-format corpus CSV path.')
    p.add_argument('--out-wide', default=None,
                    help='Optional wide-format signatures CSV (one row per capture, c00..cNN '
                         'delta_mV columns). Only populated from session-dump inputs.')
    p.add_argument('--append', action='store_true',
                    help='Append to --out/--out-wide if they already exist (default: refuse if they exist).')
    p.add_argument('--registry', default=pimd_target_check.DEFAULT_REGISTRY_PATH,
                    help='Target registry CSV (default: {0}).'.format(pimd_target_check.DEFAULT_REGISTRY_PATH))
    p.add_argument('--air-threshold-mv', type=float, dest='air_threshold_mv', default=AIR_THRESHOLD_MV_DEFAULT)
    p.add_argument('--settle-s', type=float, dest='settle_s', default=SETTLE_S_DEFAULT)
    p.add_argument('--changepoint-window-s', type=float, dest='changepoint_window_s',
                    default=CHANGEPOINT_WINDOW_S_DEFAULT)
    p.add_argument('--changepoint-threshold-mv', type=float, dest='changepoint_threshold_mv',
                    default=CHANGEPOINT_THRESHOLD_MV_DEFAULT)
    p.add_argument('--min-segment-s', type=float, dest='min_segment_s', default=MIN_SEGMENT_S_DEFAULT)
    p.add_argument('--plot-dir', default=None,
                    help='Directory for diagnostic PNGs (default: alongside each input CSV; '
                         'session-dump inputs only).')
    p.add_argument('--no-plot', action='store_true', help='Skip diagnostic PNG generation.')
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)

    try:
        targets, reg_issues = pimd_target_check.load_targets(args.registry)
    except OSError as e:
        raise SystemExit('Could not read target registry {0}: {1}'.format(args.registry, e))
    reg_errors = [i for i in reg_issues if i.severity == 'error']
    if reg_errors:
        for i in reg_errors:
            print('[REGISTRY ERROR] {0}'.format(i), file=sys.stderr)
        raise SystemExit('Target registry {0} has {1} error(s) -- fix it before building a '
                          'corpus (see: python pimd_target_check.py --registry {0}).'.format(
                              args.registry, len(reg_errors)))
    for i in reg_issues:
        if i.severity == 'warning':
            warn(args.registry, str(i))

    file_groups = {}   # (profile_name, profile_sha8) -> [paths]
    all_rows = []
    all_wide_rows = []

    for path in args.sessions:
        kind = sniff_input_kind(path)
        if kind == 'legacy_gui_signatures':
            raise SystemExit("{0}: pre-v1.32 schema (target/distance_cm columns) -- no "
                              "migration path; re-capture under pimd_classviz.py >= "
                              "v1.32.".format(path))
        elif kind == 'gui_signatures':
            rows, groups = process_gui_signatures_file(path, targets)
            for g in groups:
                file_groups.setdefault(g, []).append(path)
            all_rows.extend(rows)
        else:
            rows, wide_rows, group = process_session(path, args, targets)
            if group is not None:
                file_groups.setdefault(group, []).append(path)
            all_rows.extend(rows)
            all_wide_rows.extend(wide_rows)

    if len(file_groups) > 1:
        lines = ['Refusing to build a corpus spanning multiple profile geometries (DESIGN §11):']
        for g, paths in sorted(file_groups.items(), key=lambda kv: kv[0]):
            lines.append('  {0}: {1}'.format(g, ', '.join(os.path.basename(p) for p in paths)))
        lines.append("Re-run with only one geometry group's files at a time.")
        raise SystemExit('\n'.join(lines))

    f, writer = open_corpus_writer(args.out, args.append, JOINED_CORPUS_HEADER_FIELDS)
    try:
        for row in all_rows:
            writer.writerow([row.get(k, '') for k in JOINED_CORPUS_HEADER_FIELDS])
        f.flush()
        print('Wrote {0} rows from {1} input file(s) to {2}'.format(
            len(all_rows), len(args.sessions), args.out))
    finally:
        f.close()

    if args.out_wide:
        # Column count varies with profile geometry -- derive it from the
        # first wide row actually produced, rather than assuming a fixed 72.
        n_channels = 0
        if all_wide_rows:
            n_channels = sum(1 for k in all_wide_rows[0] if re.match(r'^c\d+$', k))
        wide_fields = (WIDE_METADATA_FIELDS + WIDE_SCALAR_FIELDS +
                       ['c{0:02d}'.format(i) for i in range(n_channels)] +
                       WIDE_TAIL_FIELDS + JOINED_EXTRA_FIELDS)
        f_wide, writer_wide = open_wide_writer(args.out_wide, args.append, wide_fields)
        try:
            for row in all_wide_rows:
                writer_wide.writerow([row.get(k, '') for k in wide_fields])
            f_wide.flush()
            print('Wrote {0} rows from {1} input file(s) to {2}'.format(
                len(all_wide_rows), len(args.sessions), args.out_wide))
            if any(sniff_input_kind(p) == 'gui_signatures' for p in args.sessions):
                warn(args.out_wide, 'gui_signatures-sourced captures are not represented in '
                                     'the wide output (only session-dump inputs are)')
        finally:
            f_wide.close()


if __name__ == '__main__':
    main()
