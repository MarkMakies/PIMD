#!/usr/bin/env python3
"""Is the 3.80/4.40 V threshold-column transient soak-driven or pack-voltage-driven?
TOOL_VERSION = v1

Reads every classviz session dump for the campaign and separates the two variables
that every session before 2026-07-30 had confounded in the same direction.

Read-only with respect to the repo: opens session dumps and the corpus, writes only
its own output (JSON on stdout, or --out).

# History (full detail in CHANGELOG.md):
#   v1 initial — 2x2 design, detrended-sigma metric, operating-point regression

Why this tool exists
--------------------
The 2026-07-30 CHANGELOG findings entry concluded the warm-up transient tracks soak
time, not pack state, from four within-session arguments.  Within one session the two
are perfectly confounded (rho 0.80-0.91 against either, identical magnitude), so no
within-session correlation could separate them.  Three sessions on 2026-07-30 broke
the confound in BOTH directions:

    cold rig + flat pack   15:01  (94 min idle, 22.85 V)
    warm rig + flat pack   17:10  (3.6 h streamed, down to 21.08 V)
    warm rig + fresh pack  20:52  (same run as 17:10 continued, pack swapped to 24.94 V)

The 17:10/20:52 pair is the controlled experiment: the `# soak:` counters show
streamed_s running continuously from one into the other (12963 s, idle_before_s=366),
so the rig is at the SAME thermal state six minutes apart and only the pack changed.

Method (established 2026-07-29, do not vary it without saying so)
----------------------------------------------------------------
Per-cell noise = detrended sigma over 50-frame windows (linear detrend inside each
window), averaged down each threshold column.  This reproduces the operator's
on-screen `settle` reading and matched their visual observations at every time point.

Two deliberate differences from classviz's live `settle`
(pimd_classviz._current_settle_mv), both stated because they matter:

1. classviz does NOT detrend -- same frames, same sigma, no detrend.  Every
   splithalf_floor in the corpora uses the undetrended form and stays comparable.
   Detrending here removes the slow thermal ramp that would otherwise be read as
   noise in a 7.2 s window, which is the whole point when the question is warm-up.
2. classviz reduces a ROLLING window every frame; this reduces disjoint windows.

Window hygiene, and why it is not a hardcoded time range
--------------------------------------------------------
A 50-frame window is only one measurement if those 50 frames arrived one nominal
period apart.  During the 2026-07-29 host stall (23:03-23:50) delivery collapsed
414 -> 35 frames/min, so a fixed-50-frame window there spans ~100 s and reads
accumulated thermal drift as noise -- that produced a phantom "noise relapse" at
23:28 in the first pass through this data.  classviz v1.64 refuses such windows
live; this is the offline equivalent, and it is a span test on the FIRMWARE clock
(WINDOW_SPAN_TOLERANCE x nominal), not a masked-out clock range, so it catches any
stall rather than the one already known about.

The firmware clock is the only clock used for anything time-based here.  PC arrival
timestamps are burst-batched: median interval 0.0035 s against a uniform 0.1440 s
firmware period, and the two share a mean, so a mean looks right while the median is
40x wrong.  pimd_features v11 exposes it as SessionData.fw_seconds.

Pack voltage as a function of wall-clock time
---------------------------------------------
Three provenance grades, never silently mixed -- each reading carries its grade:

  typed     a '# pack_v:' line with age_s <= AGE_FRESH_S.  True measurement time is
            (logged - age_s), not the log time.  This correction is inherited from
            utilities/pack_discharge/packv.py, where it was established.
  held      a '# pack_v:' line with a large age_s, or the pre-v1.66 two-field form.
            One typed value held across a stretch: an anchor at an unknown instant.
  note      handwritten DMM readings from References/V3/warm_bat_notes.md, the only
            record for the 07-29 and 08:28 sessions (neither carries pack_v lines).

Dropped outright: a header '# pack_v:' with age_s=unknown.  That is the spinbox value
restored from settings at launch -- nobody had looked at the meter -- and it is not a
reading at all.

LOADED readings only.  Loaded and unloaded differ by 0.4-0.5 V (24.76 -> 24.33 on Tue,
25.05 -> 24.55 on Wed) and mixing them would manufacture a 0.5 V step at every session
boundary.  Interpolation is linear between readings within a session and is NOT carried
across a rest: a rested pack rebounds (22.56 -> 22.85 over the midday break, no
charging), so a naive interpolation through a gap is wrong in the direction that
matters here.  Gaps are held flat and reported as extrapolation.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

TOOL_VERSION = 'v1'

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'src'))
import pimd_features as F                                    # noqa: E402

WINDOW_FRAMES = 50            # the established metric's window -- do not vary
WINDOW_SPAN_TOLERANCE = 3.0   # matches pimd_classviz.WINDOW_SPAN_TOLERANCE
AGE_FRESH_S = 30.0            # age_s at or below this is a fresh meter reading
STARTUP_EXCESS = 5.0          # a window this many x the session floor on EVERY column
                              # is a global startup event, not a column effect

# Handwritten DMM readings, References/V3/warm_bat_notes.md. UNDER LOAD only; the
# no-load 19:16/24.76 and 08:28/25.05 values are deliberately absent.
NOTE_READINGS = [
    # Tue 2026-07-29, pack B, rig partly warm at start
    ('2026-07-29T19:21', 24.33), ('2026-07-29T19:25', 24.30), ('2026-07-29T19:42', 24.07),
    ('2026-07-29T19:59', 23.96), ('2026-07-29T20:10', 23.87), ('2026-07-29T20:31', 23.69),
    ('2026-07-29T20:43', 23.59), ('2026-07-29T20:56', 23.49), ('2026-07-29T21:05', 23.42),
    ('2026-07-29T21:20', 23.33), ('2026-07-29T21:36', 23.19), ('2026-07-29T22:00', 23.02),
    ('2026-07-29T23:51', 22.48), ('2026-07-30T00:37', 22.26),
    # Wed 2026-07-30, pack A, rig cold at start
    ('2026-07-30T08:28', 24.55), ('2026-07-30T08:42', 24.19), ('2026-07-30T08:53', 24.08),
    ('2026-07-30T09:00', 24.00), ('2026-07-30T09:23', 23.79), ('2026-07-30T09:33', 23.69),
    ('2026-07-30T10:22', 23.28),
]

# Which physical pack each session ran on, from the operator's notes. Needed because
# terminal voltage is not comparable across packs (different internal resistance).
SESSION_PACK = {
    'session_20260729_191643': 'B',
    'session_20260730_082729': 'A',
    'session_20260730_112619': 'A',
    'session_20260730_112854': 'A',
    'session_20260730_123759': 'A',
    'session_20260730_124850': 'A',
    'session_20260730_150124': 'A',
    'session_20260730_171026': 'A',
    'session_20260730_205236': 'B',
}

# The 1h51m hole between the 22:00 and 23:51 Tue readings -- flagged, not smoothed over.
WORST_GAP = ('2026-07-29T22:00', '2026-07-29T23:51')


def parse_notes():
    return [(datetime.fromisoformat(t), v) for t, v in NOTE_READINGS]


def session_pack_track(sess):
    """The session's own '# pack_v:' readings as [(datetime, volts, grade)], with
    age_s applied so each entry sits at its true measurement time. Sorted, and
    de-duplicated on (time, volts) because age correction legitimately collapses a
    logged value and its re-log onto the same instant."""
    out = []
    for ts, volts, age_s in sess.pack_v:
        if age_s is None:
            # 'unknown' -- a settings restore, or the pre-v1.66 two-field form. The
            # header one is not a reading; a mid-stream one is a held value whose
            # instant we do not know, so it anchors at its log time.
            if ts == sess.t0 or abs((ts - sess.t0).total_seconds()) < 2.0:
                continue                      # header restore: drop outright
            out.append((ts, volts, 'held'))
            continue
        true_ts = ts - timedelta(seconds=age_s)
        out.append((true_ts, volts, 'typed' if age_s <= AGE_FRESH_S else 'held'))
    seen, uniq = set(), []
    for ts, v, g in sorted(out, key=lambda x: x[0]):
        key = (ts.replace(microsecond=0), round(v, 3))
        if key not in seen:
            seen.add(key)
            uniq.append((ts, v, g))
    return uniq


def build_voltage_model(sessions):
    """One pack-voltage track per pack, over wall-clock time, from every source.
    Returns {pack: [(datetime, volts, grade)]} sorted by time."""
    per_pack = defaultdict(list)
    for stem, sess in sessions.items():
        pack = SESSION_PACK.get(stem)
        for ts, v, g in session_pack_track(sess):
            per_pack[pack].append((ts, v, g))
    for ts, v in parse_notes():
        pack = 'B' if ts < datetime(2026, 7, 30, 6) else 'A'
        per_pack[pack].append((ts, v, 'note'))
    return {p: sorted(v, key=lambda x: x[0]) for p, v in per_pack.items()}


def voltage_at(track, when):
    """Linear interpolation between readings; held flat outside them. Returns
    (volts, grade) where grade degrades to 'interp'/'extrap' as appropriate."""
    if not track:
        return None, 'none'
    xs = [t.timestamp() for t, _, _ in track]
    vs = [v for _, v, _ in track]
    gs = [g for _, _, g in track]
    x = when.timestamp()
    if x <= xs[0]:
        return vs[0], 'extrap'
    if x >= xs[-1]:
        return vs[-1], 'extrap'
    i = int(np.searchsorted(xs, x))
    exact = [j for j in (i - 1, i) if abs(xs[j] - x) < 30]
    grade = gs[exact[0]] if exact else 'interp'
    return float(np.interp(x, xs, vs)), grade


def nominal_period_s(fw_seconds):
    """Median frame period on the firmware clock, over the same sample size classviz
    uses. This is what a 50-frame window OUGHT to span."""
    d = np.diff(fw_seconds[:F.NOMINAL_FRAME_RATE_HZ and 500])
    d = d[d > 0]
    if d.size < 20:
        d = np.diff(fw_seconds)
        d = d[d > 0]
    return float(np.median(d)) if d.size else None


def column_noise_series(sess, win=WINDOW_FRAMES):
    """Disjoint `win`-frame windows -> (centre_index, per-cell detrended sigma in uV,
    rejected_reason|None). A window whose firmware-clock span exceeds
    WINDOW_SPAN_TOLERANCE x nominal is REFUSED, not reduced: its frames are not one
    measurement. Same test as pimd_classviz._window_frames, applied offline."""
    fr = sess.frames_mV
    fw = sess.fw_seconds
    nominal = nominal_period_s(fw)
    expected = (win - 1) * nominal if nominal else None
    x = np.arange(win, dtype=float)
    A = np.vstack([x, np.ones(win)]).T
    pinv = np.linalg.pinv(A)
    out, rejected = [], 0
    for k in range(len(fr) // win):
        a, b = k * win, (k + 1) * win
        span = fw[b - 1] - fw[a]
        if span < 0 or (expected and span > expected * WINDOW_SPAN_TOLERANCE):
            rejected += 1
            continue
        blk = fr[a:b]
        resid = blk - A @ (pinv @ blk)
        out.append(((a + b) // 2, resid.std(0, ddof=1) * 1000.0))
    return out, rejected


def drop_startup(series, thresholds):
    """Strip the stream-start transient. The 08:28 dump reads 14-16 mV on ALL NINE
    columns in its first minutes -- a global event (profile load / first sweeps), not
    a column effect, and averaging it into the 3.80 V column would invent a warm-up
    that belongs to something else. Detected as 'every column above STARTUP_EXCESS x
    its own session floor', never as a hardcoded duration."""
    if not series:
        return series, 0
    cols = sorted(set(thresholds), reverse=True)
    colmeans = np.array([[sd[thresholds == t].mean() for t in cols] for _, sd in series])
    floor = np.percentile(colmeans, 10, axis=0)
    bad = (colmeans > floor * STARTUP_EXCESS).all(axis=1)
    n = 0
    for flag in bad:                      # only a LEADING run counts as startup
        if not flag:
            break
        n += 1
    return series[n:], n


def summarise(sess, series, thresholds, idx_lo, idx_hi):
    """Mean per-threshold-column noise over the windows whose centres fall in
    [idx_lo, idx_hi)."""
    sel = [sd for c, sd in series if idx_lo <= c < idx_hi]
    if not sel:
        return None
    sd = np.mean(sel, axis=0)
    return {'{0:.2f}'.format(t): round(float(sd[thresholds == t].mean()), 1)
            for t in sorted(set(thresholds), reverse=True)}, len(sel)


def effective_soak(sess, at_index=None):
    """(streamed_s - stalled_s) at the frame index, from the '# soak:' lines, plus
    idle_before_s. Effective soak is the subtraction because a stalled stream is not
    sweeping and the rig cools while it is stopped.

    Caveat the handover does not state and this found: streamed_s is banked within a
    classviz PROCESS, not across restarts. It read 0 at 17:10 having read 0 at 15:01,
    then 12963 at 20:52 -- so 17:10 and 20:52 are one process and one continuous soak,
    while 15:01 was a separate launch. That is exactly what makes the 17:10/20:52 pair
    a controlled experiment, so it is load-bearing rather than a footnote."""
    if not sess.soak:
        return None
    when = sess.t0 if at_index is None else sess.t0 + timedelta(
        seconds=float(sess.t_seconds[min(at_index, len(sess.t_seconds) - 1)]))
    best = None
    for ts, streamed, stalled, idle, event in sess.soak:
        if ts <= when or best is None:
            best = (streamed, stalled, idle, event)
    return {'streamed_s': best[0], 'stalled_s': best[1],
            'effective_s': best[0] - best[1], 'idle_before_s': best[2]}


def operating_point(sess, idx_lo, idx_hi):
    """Per-band grid mean in mV -- the operating point. A supply change moves this
    UNIFORMLY across bands; a thermal change moves it monotonically in pulse width
    (DESIGN 14.1, 17.10). That difference is what identifies the mechanism."""
    band = np.array([c['band_index'] for c in sess.colmap])
    pw = np.array([c['pulse_us'] for c in sess.colmap])
    m = sess.frames_mV[idx_lo:idx_hi].mean(0)
    return {'per_band': {str(round(float(pw[band == b][0]), 2)): round(float(m[band == b].mean()), 1)
                         for b in sorted(set(band))},
            'grid_mean': round(float(m.mean()), 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--sessions-dir', default=os.path.join(REPO, 'src', 'data', 'sessions'))
    ap.add_argument('--corpus', default=None,
                    help='corpus CSV for the detection-quality cross-check')
    ap.add_argument('--out', default=None)
    ap.add_argument('--slice-min', type=float, default=5.0,
                    help='length of each reported slice, minutes')
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.sessions_dir, 'session_*.csv')))
    if not paths:
        sys.exit('no session dumps under {0}'.format(args.sessions_dir))

    sessions, report = {}, {}
    for p in paths:
        stem = os.path.splitext(os.path.basename(p))[0]
        try:
            sess = F.parse_session_file(p)
        except Exception as e:
            print('[SKIP] {0}: {1}'.format(stem, e), file=sys.stderr)
            continue
        sessions[stem] = sess

    tracks = build_voltage_model(sessions)
    result = {'tool_version': TOOL_VERSION, 'features_version': F.TOOL_VERSION,
              'n_sessions': len(sessions), 'sessions': {},
              'pack_tracks': {p: [[t.isoformat(), v, g] for t, v, g in tr]
                              for p, tr in tracks.items()},
              'worst_interpolation_gap': {'from': WORST_GAP[0], 'to': WORST_GAP[1],
                                          'minutes': 111,
                                          'note': 'Tue 22:00->23:51, no reading between; '
                                                  'least defensible interpolation in the set'}}

    for stem, sess in sorted(sessions.items()):
        thresholds = np.array([c['threshold_v'] for c in sess.colmap])
        rate = F.measure_frame_rate_hz(sess.fw_seconds)
        series, rejected = column_noise_series(sess)
        series, n_startup = drop_startup(series, thresholds)
        n = len(sess.frames_mV)
        fps = int(round(args.slice_min * 60 * rate))
        pack = SESSION_PACK.get(stem)

        slices = {}
        for label, lo in (('first', 0), ('last', max(0, n - fps))):
            got = summarise(sess, series, thresholds, lo, lo + fps)
            if not got:
                continue
            cols, nwin = got
            when = sess.t0 + timedelta(seconds=float(sess.t_seconds[min(lo, n - 1)]))
            volts, grade = voltage_at(tracks.get(pack, []), when)
            slices[label] = {
                'at_iso': when.isoformat(timespec='seconds'), 'n_windows': nwin,
                'pack_v': None if volts is None else round(volts, 2), 'pack_v_grade': grade,
                'soak': effective_soak(sess, lo),
                'columns_uV': cols,
                'operating_point_mV': operating_point(sess, lo, lo + fps),
            }

        result['sessions'][stem] = {
            'pack': pack, 'frames': n, 'fw_minutes': round(float(sess.fw_seconds[-1]) / 60, 1),
            'frame_rate_hz': round(rate, 2), 'tool': sess.tool_version,
            'windows_rejected_stall': rejected, 'windows_dropped_startup': n_startup,
            'soak_at_open': effective_soak(sess, 0),
            'slices': slices,
        }

    if args.corpus:
        result['corpus'] = corpus_crosscheck(args.corpus, tracks)

    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        with open(args.out, 'w') as f:
            f.write(text + '\n')
        print('wrote {0}'.format(args.out), file=sys.stderr)
    else:
        print(text)


def corpus_crosscheck(path, tracks):
    """splithalf_floor / quality per capture, joined to pack voltage. Tests whether
    DETECTION QUALITY follows the same variable as the noise floor does.

    Caveats honoured rather than restated later: pack_v is populated on only a few
    captures (one held value across a stretch), the Ag_jewellery_01 captures were
    repaired 240 -> 60 mm on 2026-07-30, and hand-placement amplitude variance is
    ~+/-13 %, so a 20 % amplitude difference is not a soak or a voltage effect."""
    rows = list(csv.DictReader(open(path)))
    per_capture = {}
    for r in rows:
        cid = r['capture_id']
        if cid in per_capture:
            continue
        try:
            floor = float(r['splithalf_floor'])
        except (ValueError, KeyError):
            continue
        ts = None
        try:
            ts = datetime.fromisoformat(r['captured_at'])
        except (ValueError, KeyError):
            pass
        pack = 'B' if (ts and ts < datetime(2026, 7, 30, 6)) else 'A'
        volts, grade = voltage_at(tracks.get(pack, []), ts) if ts else (None, 'none')
        per_capture[cid] = {
            'target_id': r.get('target_id'), 'distance_mm': r.get('distance_mm'),
            'long_axis': r.get('long_axis'), 'repeat_idx': r.get('repeat_idx'),
            'captured_at': r.get('captured_at'), 'quality': r.get('quality'),
            'splithalf_floor': floor, 'amp': r.get('plateau_amp_mV'),
            'pack_v_logged': r.get('pack_v') or None,
            'pack_v_model': None if volts is None else round(volts, 2),
            'pack_v_grade': grade,
        }
    best = [v for v in per_capture.values()
            if v['target_id'] == 'Cu_pipe_01' and v['distance_mm'] == '120'
            and v['long_axis'] == 'y']
    vs = [(v['pack_v_model'], v['splithalf_floor']) for v in per_capture.values()
          if v['pack_v_model'] is not None]
    rho = None
    if len(vs) > 3:
        a = np.array(vs)
        rho = round(float(np.corrcoef(a[:, 0], a[:, 1])[0, 1]), 3)
    return {'n_captures': len(per_capture),
            'rho_floor_vs_pack_v': rho,
            'note': 'rho over ALL targets mixes placements and is a weak test; the '
                    'per-placement comparison below is the real one',
            'Cu_pipe_01_at_120_y': sorted(best, key=lambda v: v['captured_at'] or ''),
            'quality_counts': dict((k, sum(1 for v in per_capture.values()
                                           if v['quality'] == k))
                                  for k in sorted(set(v['quality'] for v in per_capture.values())))}


if __name__ == '__main__':
    main()
