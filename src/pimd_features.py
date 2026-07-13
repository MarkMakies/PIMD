# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
###############################################################################
# PIMD Feature Extractor (pimd_features.py) v5
# — offline session-CSV -> training-corpus CSV converter
# Runs on Ubuntu desktop / laptop, standalone CLI script (no GUI, no Qt)
#
# Reads one or more self-describing session-dump CSVs produced by ClassViz's
# "Record Session" feature (pimd_classviz.py v1.16+), validates each against
# the locked cal_72_air_v2 operating profile (DESIGN §10 — never mix profile
# geometries, DESIGN §11), segments the frame stream into air/target plateaus
# (from '# mark:' ground-truth lines if present — pimd_classviz.py v1.19+ —
# else a rolling-window change-point fallback), corrects thermal drift
# (DESIGN §3/§17.5) with a piecewise-linear per-channel baseline anchored on
# air segments, and emits one row per (session, target, cell) matching the
# existing hand-built PIMD_target_corpus_signatures.csv schema, plus one
# appended column not in that legacy schema:
#   session,target,distance_cm,pulse_us,threshold_v,delta_mV,plateau_amp_mV,
#   splithalf_floor,quality,amp_mean_abs_mV
# plateau_amp_mV is ||delta_mV||_2 (L2 norm across the 72 cells -- the v1
# corpus's convention); amp_mean_abs_mV is mean(|delta_mV|) per cell, a
# distinct, smaller quantity kept under its own name (see
# compute_plateau_stats() for the exact definitions and why they differ).
# Optionally also emits a wide-format signatures CSV (--out-wide): one row
# per plateau, c00..c71 = that plateau's delta_mV vector, derived from the
# same per-plateau computation as the long rows (no re-parsing).
# Also writes one diagnostic PNG per input session (band-mean vs time, drift-
# corrected, with segment boundaries marked) for eyeballing before trusting a
# capture. Plain numpy + matplotlib only — no pandas, no csv module,
# consistent with the rest of the repo (plain comma-split, no quoting).
#
# v5 plateau_amp_mV restored to the v1 hand-built corpus's convention: L2
#    norm of the 72-cell drift-corrected delta_mV vector (was silently
#    emitting mean(|delta_mV|) per cell instead -- a different, ~9x smaller
#    quantity under the same column name). Measured defect: copper pipe 120g
#    @5cm read plateau_amp_mV=4.96 here vs. 113.7 (L2) in the v1 corpus for
#    the same nominal capture -- a ~23x apparent gap, only ~9x of which was
#    this convention bug (sqrt(72) x mean/rms shape factor); the remaining
#    ~2.3-3x is a separate, already-known, out-of-scope bench-geometry
#    difference between the v1 and v2 setups. This corrupted any cross-
#    campaign amplitude comparison and the canary-strength unit, both of
#    which are defined in v1's L2 units (1 unit == copper pipe 120g @10cm ==
#    45 mV L2). splithalf_floor changed to the same L2 convention (L2 norm of
#    the plateau's split-half-median difference vector, still halved) so
#    floor/amp stays a meaningful, convention-consistent fraction for the
#    noisy-quality gate. The old mean(|delta_mV|) quantity is still useful,
#    so it's kept -- appended as a new `amp_mean_abs_mV` column at the end of
#    both the long and wide row schemas (existing readers that select columns
#    by name are unaffected; nothing existing changed position or meaning
#    except plateau_amp_mV/splithalf_floor's numeric convention). Documented
#    in a comment block above compute_plateau_stats() and in wide_header_
#    lines()'s '# columns:' comment.
#      Checked pimd_corpus_check.py for absolute-mV thresholds assuming the
#    old mean-abs convention: none exist -- every amplitude-adjacent check is
#    ratio- or cosine-based (amp ratios, falloff fit/measured ratios, SNR =
#    amp/splithalf), so no threshold values needed changing. Verified against
#    session_20260707_134922.csv (regenerated corpus, before/after this fix):
#    all 29 pimd_corpus_check.py verdicts (PASS/FAIL/SKIP) are identical
#    before vs. after -- but flagging honestly, not all the underlying ratio
#    *values* are: SNR (amp/splithalf), the falloff n-exponent, and repeat
#    amp-ratios shifted somewhat (e.g. copper pipe @5cm SNR: 67.0 -> 34.5,
#    still comfortably >= the 10.0 gate) because L2 norm and mean-abs aren't
#    exactly proportional between two *different* vectors (amp's delta_mV vs
#    splithalf's half-difference vector, or the same target's vector at a
#    different distance) -- only cosine-similarity checks and same-vector
#    ratios are exactly convention-invariant; these SNR/falloff/repeat ratios
#    are only empirically stable-in-verdict, not mathematically guaranteed to
#    stay so for all future data. No pimd_corpus_check.py code change made --
#    this is a property of the statistics, not a bug in that tool.
# v4 segment_from_marks() now auto-suffixes repeat visits to the same
#    (target, distance_cm) within one session: '(rpt)' for the 2nd visit,
#    '(rpt3)'/'(rpt4)'/... beyond that. A guided Training Session run can
#    legitimately revisit the same target/distance more than once (e.g. a
#    saved list run twice for a repeatability check), but the output corpus
#    schema only carries (session, target, distance_cm) as a row's identity
#    -- without a disambiguator, a second visit silently merged into the
#    first under any groupby-style corpus tool, doubling the apparent cell
#    count (72 -> 144) rather than producing two distinct 72-cell captures.
#    Surfaced by pimd_corpus_check.py's "mixed cell counts ... refusing to
#    mix profile geometries (DESIGN §11)" guard on a real two-visit session
#    (session_20260707_125642.csv: 'copper pipe' visited twice, 'steel
#    spanner' once) -- that guard was correct to refuse, this was genuinely
#    corrupted data, not a false positive. '(rpt)' for the 2nd visit matches
#    the pre-existing hand-corpus convention pimd_corpus_check.py's repeat-
#    consistency check already looks for, so a simple double-visit needs no
#    other tool changes; pimd_corpus_check.py's REPEAT_MARK_RE widened
#    (`\(rpt\)` -> `\(rpt\d*\)`) so 3rd+ visits are also recognised. Verified:
#    re-running against that session now gives three distinct 72-row groups
#    (copper pipe / copper pipe (rpt) / steel spanner) instead of a mixed
#    [72, 144] crash, and pimd_corpus_check.py's repeat-consistency check now
#    correctly compares the repeat visit against its base capture at all 3
#    distances.
# v3 Fixed parse_session_file(): the single-pass parser flipped `header_done`
#    to True on the first non-'#' line (the CSV data-header row) and never
#    checked for '#' again afterward -- but '# mark: ...' lines are written
#    live as the operator advances targets mid-recording (pimd_classviz.py's
#    hotkey feature since v1.19, and its Training Session tab since v1.21),
#    so they land interspersed among data rows, not just before the first
#    one. Any mark after the first data row was silently parsed as a garbage
#    data row (`int(' air')` or `int(' copper pipe @5')` -> ValueError ->
#    the whole session [SKIP]ped, 0 rows written, no hard error). This bug
#    predates this file's v1 and was never caught because no real marked
#    session had been run through the tool until now (confirmed against
#    session_20260707_125642.csv: 13 marks, 9 non-air target plateaus x 72
#    channels = 648 rows, now written correctly with no regression on the
#    older no-marks sessions). New _parse_mark_content() helper shared by
#    both the pre-header-row and post-header-row '# mark:' parsing branches
#    so they can't drift apart.
# v2 Added --out-wide: one row per plateau (session,target,distance_cm,
#    plateau_amp_mV,splithalf_floor,quality,c00..c71) instead of one row per
#    cell. c00..c71 is delta_mV in the existing channel-index order with no
#    reordering -- checked cal_72_air_v2.json: the 8 bands are already
#    stored pulse_us-ascending, and each band's 9 cells are already stored
#    threshold_v-descending, so channel index (band_index*9+cell_index)
#    already satisfies "pulse ascending / threshold descending within band".
#    Wide rows are built from the exact delta_mV/plateau_amp_mV/
#    splithalf_floor/quality already computed for the long rows in
#    process_session -- never recomputed, so the two outputs can't drift
#    apart. New wide_header_lines()/open_wide_writer()/build_wide_row();
#    process_session() now returns (rows, wide_rows).
# v1 Initial implementation. No-marks fallback classifies the chronologically
#    first detected stable run as the air reference (assumes the standard
#    capture protocol: recording starts before the first target is placed) --
#    an earlier revision tried a session-wide median-of-segment-medians
#    instead, but that broke down on real captures with only a handful of
#    segments (confirmed against session_20260703_104324.csv, where the
#    visually-flat opening segment scored *further* from that median than
#    later target segments did). Change-point defaults (0.15 mV smoothed
#    threshold, 1 s window, 4 s min-segment) were hand-tuned against the
#    3 real un-marked sessions in data/sessions/ -- CHANGEPOINT_THRESHOLD_MV_
#    DEFAULT=0.5 (the initially spec'd value) found zero transitions at all
#    in session_20260703_111533.csv, collapsing the whole 272 s recording
#    into one run. All three sessions currently in data/sessions/ predate
#    the '# mark:' hotkeys (pimd_classviz.py v1.19) and rely entirely on this
#    fallback; future recordings should use the mark hotkeys to remove the
#    ambiguity.
###############################################################################

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SCRIPT_DIR       = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROFILE  = os.path.join(SCRIPT_DIR, 'data', 'profiles', 'cal_72_air_v2.json')
PROFILE_TOL      = 1e-6   # float compare tolerance for profile geometry validation

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

CORPUS_HEADER = ('session,target,distance_cm,pulse_us,threshold_v,delta_mV,plateau_amp_mV,'
                  'splithalf_floor,quality,amp_mean_abs_mV')


def warn(session_path, message):
    print('[WARN] {0}: {1}'.format(os.path.basename(session_path), message), file=sys.stderr)


def skip(session_path, message):
    print('[SKIP] {0}: {1}'.format(os.path.basename(session_path), message), file=sys.stderr)


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
    colmap: list            # list[dict] length n_channels: band_index, freq_hz, pulse_us, delay_us, threshold_v
    session_notes: str
    marks: list              # list[(datetime, str)]
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


def parse_session_file(path):
    marks = []
    colmap = []
    profile = None
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
                        profile = json.loads(content.split(':', 1)[1].strip())
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
                    elif content.startswith('mark:'):
                        marks.append(_parse_mark_content(content))
                    # else: unrecognised '#' line (active_profile_idx, firmware_v_response, ...) - ignored
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
                    if content.startswith('mark:'):
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

    return SessionData(
        path=path, session_start_iso=session_start_iso, tool_version=tool_version,
        n_bands=n_bands, n_cells=n_cells, n_channels=n_channels, profile=profile,
        colmap=colmap, session_notes='\n'.join(notes_lines), marks=marks,
        t0=t0, t_seconds=t_seconds, frames_mV=frames_mV, flagged=flagged_arr,
    )


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
# Profile validation (never mix profile geometries -- DESIGN §11-adjacent)
# ---------------------------------------------------------------------------

def load_reference_profile(path):
    with open(path) as f:
        return json.load(f)


def validate_profile(profile, reference, tol=PROFILE_TOL):
    if profile.get('name') != reference['name']:
        return False, "name '{0}' != '{1}'".format(profile.get('name'), reference['name'])
    if profile.get('averages') != reference['averages']:
        return False, 'averages {0} != {1}'.format(profile.get('averages'), reference['averages'])
    bands, ref_bands = profile.get('bands', []), reference['bands']
    if len(bands) != len(ref_bands):
        return False, '{0} bands != {1} bands'.format(len(bands), len(ref_bands))
    for i, (b, rb) in enumerate(zip(bands, ref_bands)):
        if int(b.get('freq_hz', -1)) != int(rb['freq_hz']):
            return False, 'band {0}: freq_hz {1} != {2}'.format(i, b.get('freq_hz'), rb['freq_hz'])
        if abs(float(b.get('pulse_us', -1)) - rb['pulse_us']) > tol:
            return False, 'band {0}: pulse_us {1} != {2}'.format(i, b.get('pulse_us'), rb['pulse_us'])
        delays, ref_delays = b.get('delays_us', []), rb['delays_us']
        if len(delays) != len(ref_delays) or any(abs(d - rd) > tol for d, rd in zip(delays, ref_delays)):
            return False, 'band {0}: delays_us mismatch'.format(i)
        thr, ref_thr = b.get('threshold_v', []), rb['threshold_v']
        if len(thr) != len(ref_thr) or any(abs(t - rt) > tol for t, rt in zip(thr, ref_thr)):
            return False, 'band {0}: threshold_v mismatch'.format(i)
    return True, ''


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

@dataclass
class Plateau:
    label: str
    distance_cm: object   # float or None
    is_air: bool
    start_idx: int
    end_idx: int           # [start_idx, end_idx) into the flagged-dropped frame arrays


def parse_mark_label(raw_text):
    text = raw_text.strip()
    if text.lower() == 'air':
        return 'air', None, True
    m = re.match(r'^(.*)@\s*(-?\d+(?:\.\d+)?)\s*$', text)
    if m:
        return m.group(1).strip(), float(m.group(2)), False
    return text, None, False


def segment_from_marks(sess, frame_rate_hz, settle_s):
    marks_sorted = sorted(sess.marks, key=lambda m: m[0])
    n = len(marks_sorted)
    settle_frames = int(round(settle_s * frame_rate_hz))
    plateaus = []
    visit_counts = {}   # (label.lower(), distance_cm) -> visits seen so far, this session
    for i, (mark_dt, raw_text) in enumerate(marks_sorted):
        label, distance_cm, is_air = parse_mark_label(raw_text)
        if not is_air and distance_cm is None:
            warn(sess.path, "mark '{0}' has no @distance suffix, treating as target with unknown distance".format(
                raw_text))
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
        # A guided Training Session run can legitimately revisit the same
        # target/distance more than once in one session (e.g. a saved list
        # visited twice for a repeatability check). Every non-air plateau
        # only carries (session, target, distance_cm) as its identity in the
        # output corpus -- without a disambiguator, a second visit would
        # silently merge into the first under groupby-style corpus tooling
        # (same key, doubled cell count). Suffix repeats '(rpt)', '(rpt3)',
        # '(rpt4)', ... -- '(rpt)' for the 2nd visit matches the pre-existing
        # hand-corpus convention (see pimd_corpus_check.py's repeat-
        # consistency check) so a simple double-visit needs no other tool
        # changes; later visits get a numbered variant.
        if not is_air:
            key = (label.lower(), distance_cm)
            visit_counts[key] = visit_counts.get(key, 0) + 1
            visit = visit_counts[key]
            if visit == 2:
                label = '{0} (rpt)'.format(label)
            elif visit > 2:
                label = '{0} (rpt{1})'.format(label, visit)
        plateaus.append(Plateau(label, distance_cm, is_air, start_idx, end_idx))
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
    segments get generic placeholder labels only -- there is no ground
    truth for *which* physical target a run corresponds to without marks,
    so guessing from session_notes text would risk silently mislabelling
    training data. If the session doesn't actually open in air (a target
    already in place at record-start), this heuristic will anchor on that
    target instead -- a real limitation without marks; use '# mark: ..., air'
    (pimd_classviz.py v1.19+) to remove the ambiguity entirely.
    """
    seg_medians = [np.median(frames_mV[s:e], axis=0) for s, e in runs]
    air_reference = seg_medians[0]
    plateaus = []
    target_n = 0
    for (s, e), med in zip(runs, seg_medians):
        is_air = np.mean(np.abs(med - air_reference)) < air_threshold_mv
        if is_air:
            plateaus.append(Plateau('air', None, True, s, e))
        else:
            target_n += 1
            plateaus.append(Plateau('segment_{0:02d}'.format(target_n), None, False, s, e))
    return plateaus


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


def build_rows(session_stem, plateau, colmap, delta_mV, plateau_amp_mV, splithalf_floor, quality,
               amp_mean_abs_mV, session_path):
    label = plateau.label
    if ',' in label:
        warn(session_path, "target label '{0}' contains a comma, replacing with ';'".format(label))
        label = label.replace(',', ';')
    rows = []
    for ch, c in enumerate(colmap):
        row = [
            session_stem, label, format_distance(plateau.distance_cm),
            format_value(c['pulse_us']), format_value(c['threshold_v']),
            format_value(delta_mV[ch]), format_value(plateau_amp_mV),
            format_value(splithalf_floor), quality, format_value(amp_mean_abs_mV),
        ]
        rows.append(','.join(row))
    return rows


def open_corpus_writer(out_path, append):
    exists = os.path.isfile(out_path)
    if exists and not append:
        raise SystemExit('{0} already exists; pass --append to add to it, or choose a different --out.'.format(
            out_path))
    f = open(out_path, 'a' if exists else 'w')
    if not exists:
        f.write(CORPUS_HEADER + '\n')
        f.flush()
    return f


def build_wide_row(session_stem, plateau, delta_mV, plateau_amp_mV, splithalf_floor, quality,
                    amp_mean_abs_mV):
    """One row per plateau: same metadata + scalars as build_rows(), plus the
    full delta_mV vector as c00..c71. Built from the exact values already
    computed for the long rows -- never recomputed -- so long and wide can't
    drift apart for the same plateau."""
    label = plateau.label.replace(',', ';')  # build_rows() already warns on this label
    cells = ','.join(format_value(v) for v in delta_mV)
    return ','.join([
        session_stem, label, format_distance(plateau.distance_cm),
        format_value(plateau_amp_mV), format_value(splithalf_floor), quality, cells,
        format_value(amp_mean_abs_mV),
    ])


def wide_header_lines(profile_name, n_channels):
    c_cols = ','.join('c{0:02d}'.format(i) for i in range(n_channels))
    return [
        '# profile: {0}'.format(profile_name),
        "# columns: session,target,distance_cm,plateau_amp_mV,splithalf_floor,quality,"
        "c00..c{0:02d} (band-major channel order: pulse_us ascending across bands, "
        "threshold_v descending within band -- same order as the session CSV colmap), "
        "amp_mean_abs_mV (mean|delta_mV| per cell -- distinct from plateau_amp_mV's L2 "
        "norm; see compute_plateau_stats() docstring)".format(n_channels - 1),
        'session,target,distance_cm,plateau_amp_mV,splithalf_floor,quality,' + c_cols + ',amp_mean_abs_mV',
    ]


def open_wide_writer(out_path, append, profile_name, n_channels):
    exists = os.path.isfile(out_path)
    if exists and not append:
        raise SystemExit('{0} already exists; pass --append to add to it, or choose a different --out-wide.'.format(
            out_path))
    f = open(out_path, 'a' if exists else 'w')
    if not exists:
        for line in wide_header_lines(profile_name, n_channels):
            f.write(line + '\n')
        f.flush()
    return f


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
        top.text(center_t, ylim[1], p.label, rotation=45, va='bottom', fontsize=7)

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

def process_session(path, args, reference_profile):
    """Returns a list of output CSV row strings. Never raises past this
    function -- every failure mode is caught at the narrowest reasonable
    scope and reported to stderr with [SKIP]/[WARN], so one bad session
    never aborts the batch."""
    try:
        sess = parse_session_file(path)
    except Exception as e:
        skip(path, 'failed to parse -- {0}'.format(e))
        return [], []

    ok, reason = validate_profile(sess.profile, reference_profile)
    if not ok:
        skip(path, 'profile geometry mismatch -- {0} (refusing to mix profile geometries)'.format(reason))
        return [], []

    sess = drop_flagged(sess)
    if len(sess.t_seconds) < 2:
        skip(path, 'fewer than 2 usable frames after dropping flagged rows')
        return [], []
    frame_rate_hz = measure_frame_rate_hz(sess.t_seconds)
    if abs(frame_rate_hz - NOMINAL_FRAME_RATE_HZ) > 0.15 * NOMINAL_FRAME_RATE_HZ:
        warn(path, 'measured frame rate {0:.2f} Hz deviates >15% from nominal {1:.2f} Hz'.format(
            frame_rate_hz, NOMINAL_FRAME_RATE_HZ))

    if sess.marks:
        plateaus = segment_from_marks(sess, frame_rate_hz, args.settle_s)
    else:
        runs = detect_changepoints(sess.frames_mV, frame_rate_hz, args.changepoint_window_s,
                                    args.changepoint_threshold_mv, args.min_segment_s)
        plateaus = classify_segments(runs, sess.frames_mV, args.air_threshold_mv)

    air_plateaus = [p for p in plateaus if p.is_air]
    if not air_plateaus:
        skip(path, 'no air segments found, cannot drift-correct')
        return [], []
    anchor_ts, anchor_vs = build_baseline_anchors(air_plateaus, sess.frames_mV, sess.t_seconds)
    if len(anchor_ts) == 1:
        warn(path, 'only one air anchor -- no drift correction possible, using a flat baseline')

    session_stem = os.path.splitext(os.path.basename(path))[0]
    rows, wide_rows = [], []
    for p in plateaus:
        if p.is_air:
            continue
        try:
            c_start, c_end = central_frames(p)
            delta_mV, plateau_amp_mV, amp_mean_abs_mV, splithalf_floor, n_central, center_t = compute_plateau_stats(
                sess.frames_mV, sess.t_seconds, c_start, c_end, anchor_ts, anchor_vs)
            if center_t < anchor_ts[0] or center_t > anchor_ts[-1]:
                warn(path, "plateau '{0}' center falls outside the air-anchor time range -- "
                           "baseline is flat-extrapolated there".format(p.label))
            quality = quality_flags(splithalf_floor, plateau_amp_mV, n_central)
            rows.extend(build_rows(session_stem, p, sess.colmap, delta_mV, plateau_amp_mV,
                                    splithalf_floor, quality, amp_mean_abs_mV, path))
            if args.out_wide:
                wide_rows.append(build_wide_row(session_stem, p, delta_mV, plateau_amp_mV,
                                                 splithalf_floor, quality, amp_mean_abs_mV))
        except Exception as e:
            warn(path, "plateau '{0}' failed -- {1}".format(p.label, e))

    if not args.no_plot:
        try:
            plot_dir = args.plot_dir or os.path.dirname(os.path.abspath(path))
            out_png = os.path.join(plot_dir, '{0}_diagnostic.png'.format(session_stem))
            plot_diagnostic(session_stem, out_png, sess, plateaus, anchor_ts, anchor_vs)
        except Exception as e:
            warn(path, 'diagnostic plot failed -- {0}'.format(e))

    return rows, wide_rows


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser():
    p = argparse.ArgumentParser(
        description='Convert PIMD ClassViz session-dump CSVs into training-corpus rows.')
    p.add_argument('sessions', nargs='+', help='One or more session_*.csv files.')
    p.add_argument('--out', required=True, help='Output/append long-format corpus CSV path.')
    p.add_argument('--out-wide', default=None,
                    help='Optional wide-format signatures CSV (one row per plateau, c00..c71 delta_mV columns).')
    p.add_argument('--append', action='store_true',
                    help='Append to --out/--out-wide if they already exist (default: refuse if they exist).')
    p.add_argument('--profile', default=DEFAULT_PROFILE,
                    help='Reference profile JSON to validate sessions against (default: cal_72_air_v2.json).')
    p.add_argument('--air-threshold-mv', type=float, dest='air_threshold_mv', default=AIR_THRESHOLD_MV_DEFAULT)
    p.add_argument('--settle-s', type=float, dest='settle_s', default=SETTLE_S_DEFAULT)
    p.add_argument('--changepoint-window-s', type=float, dest='changepoint_window_s',
                    default=CHANGEPOINT_WINDOW_S_DEFAULT)
    p.add_argument('--changepoint-threshold-mv', type=float, dest='changepoint_threshold_mv',
                    default=CHANGEPOINT_THRESHOLD_MV_DEFAULT)
    p.add_argument('--min-segment-s', type=float, dest='min_segment_s', default=MIN_SEGMENT_S_DEFAULT)
    p.add_argument('--plot-dir', default=None,
                    help='Directory for diagnostic PNGs (default: alongside each input CSV).')
    p.add_argument('--no-plot', action='store_true', help='Skip diagnostic PNG generation.')
    return p


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    reference_profile = load_reference_profile(args.profile)
    n_channels = sum(len(b['delays_us']) for b in reference_profile['bands'])
    f = open_corpus_writer(args.out, args.append)
    f_wide = open_wide_writer(args.out_wide, args.append, reference_profile['name'], n_channels) \
        if args.out_wide else None
    try:
        total, total_wide = 0, 0
        for path in args.sessions:
            rows, wide_rows = process_session(path, args, reference_profile)
            for r in rows:
                f.write(r + '\n')
            f.flush()
            total += len(rows)
            if f_wide:
                for r in wide_rows:
                    f_wide.write(r + '\n')
                f_wide.flush()
                total_wide += len(wide_rows)
        print('Wrote {0} rows from {1} session(s) to {2}'.format(total, len(args.sessions), args.out))
        if f_wide:
            print('Wrote {0} rows from {1} session(s) to {2}'.format(total_wide, len(args.sessions), args.out_wide))
    finally:
        f.close()
        if f_wide:
            f_wide.close()


if __name__ == '__main__':
    main()
