#!/usr/bin/env python3
"""Retro-label the mark-free session dumps by matching plateaus to corpus signatures.
TOOL_VERSION = v1

**NOT read-only with respect to the repo.** Unlike the other tools in `/utilities/`,
`--apply` REWRITES session dumps in place (after backing each one up). Default is a
dry run that reports and writes nothing.

# History (full detail in CHANGELOG.md):
#   v1 initial — change-point plateaus, cosine match against the corpus, guarded injection

Why this tool exists
--------------------
Session logging auto-starts (classviz v1.63) but the Mark button was only ever wired to
manual presses, so every dump written before classviz v1.68 carries **zero `# mark:`
lines**. That leaves ~380 000 frames of per-cell data with no ground truth, while the
labels sit in a corpus CSV that shares no key with the dumps — the corpus `session` id
and the dump filename are independent stamps of different events.

v1.68 fixes this going forward (`# capture:` lines carry exact frame windows). This tool
does what can still be done for the dumps already on disk: recover the labels by matching
each plateau's measured signature against the corpus.

Method
------
1. Plateaus: mean |frame-to-frame delta| in mV, smoothed with a centred 1 s box; frames
   above CHANGEPOINT_THRESHOLD_MV are transitions, maximal runs below it that last at
   least MIN_SEGMENT_S are plateaus. Same shape as pimd_features.detect_changepoints.
2. For each plateau, and each earlier plateau within REF_MAX_AGE_S used as an air
   reference, take the difference of medians and reorder it into corpus cell order
   (pulse ascending, threshold descending -- pimd_shape's vector convention).
3. Score that against every corpus capture that shares the dump's profile_sha8 and whose
   `captured_at` falls in a window around the plateau, by cosine on the unit shape.
   `captured_at` LAGS the frames (it is stamped at save time, tens of seconds later), so
   the window is asymmetric: mostly after the plateau, a little before.
4. Accept the best pairing only if cosine >= --cos-floor AND the delta clears --min-amp.
   Everything rejected is reported, never guessed at.

Why cosine and not time
-----------------------
Time alone cannot do it: `captured_at` lags by an unknown amount, several captures can
sit inside one plateau's neighbourhood, and 83 of 170 captures have no dump at all.
Shape is the discriminating key -- measured on the 07-30 data, the correct pairing scores
0.995-0.997 while the field of alternatives sits well below. Time is used only to bound
the candidate set, never to break a tie.

What the injected lines mean
----------------------------
They are RECONSTRUCTIONS, not operator ground truth, and are labelled as such: every
injected `mark_target:` carries `reconstructed cos=<score>` in its notes field, and a
`# session_notes:` line records the tool, the date and the cosine floor used. Nothing
downstream should ever treat these as equivalent to a mark the operator made.

Consequence worth knowing before --apply
----------------------------------------
Injecting marks changes what `pimd_features.py --out` produces from these dumps. Today it
emits NOTHING for them: with no marks it falls back to change-point detection, and every
non-air segment gets target_id=None and is skipped. With marks it will emit corpus rows --
which is largely the point, but those rows DUPLICATE captures already in the live corpus
under different ids. Do not merge them in without deciding to.
"""

import argparse
import collections
import csv
import datetime as dt
import io
import os
import shutil
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src'))
import pimd_features                                             # noqa: E402

TOOL_VERSION = 'relabel.py v1'

CHANGEPOINT_THRESHOLD_MV = 0.15   # pimd_features.CHANGEPOINT_THRESHOLD_MV_DEFAULT
CHANGEPOINT_WINDOW_S     = 1.0    # pimd_features.CHANGEPOINT_WINDOW_S_DEFAULT
MIN_SEGMENT_S            = 4.0    # pimd_features.MIN_SEGMENT_S_DEFAULT
COS_FLOOR_DEFAULT        = 0.95
MIN_AMP_MV               = 2.0    # a delta below this is air-vs-air, not a target
REF_MAX_AGE_S            = 600.0  # how far back an air reference may sit
LAG_BEFORE_S             = 120.0  # captured_at may precede the plateau start by this
LAG_AFTER_S              = 600.0  # ...or follow the plateau end by this (save-time lag)


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

def load_corpus(path):
    """[(captured_at, target_id, distance_mm, tilt_deg, profile_sha8, vec)] in the
    corpus cell order (pulse ascending, threshold descending)."""
    groups = collections.OrderedDict()
    with open(path, newline='') as f:
        for row in csv.DictReader(line for line in f if not line.startswith('#')):
            groups.setdefault(row['capture_id'], []).append(row)
    out = []
    for cid, rows in groups.items():
        rows = sorted(rows, key=lambda r: (float(r['pulse_us']), -float(r['threshold_v'])))
        first = rows[0]
        out.append(dict(
            capture_id=cid,
            captured_at=dt.datetime.fromisoformat(first['captured_at']),
            target_id=first['target_id'],
            distance_mm=first['distance_mm'],
            long_axis=first.get('long_axis', 'na'),
            tilt_deg=first.get('tilt_deg', ''),
            medium=first.get('medium', 'air'),
            repeat_idx=first.get('repeat_idx', '1'),
            profile_sha8=first.get('profile_sha8', ''),
            vec=np.array([float(r['delta_mV']) for r in rows], dtype=float)))
    return out


# ---------------------------------------------------------------------------
# Plateaus
# ---------------------------------------------------------------------------

def find_plateaus(frames_mV, frame_rate_hz):
    """[(start_idx, end_idx)] of maximal runs that are not transitions. Indices are
    into frames_mV, which parse_session_file fills in file order and does not filter --
    so they are also data-row indices in the file, which is what injection needs."""
    d = np.abs(np.diff(frames_mV, axis=0)).mean(axis=1)
    k = max(1, int(round(CHANGEPOINT_WINDOW_S * frame_rate_hz)))
    smooth = np.convolve(d, np.ones(k) / k, mode='same')
    trans = smooth > CHANGEPOINT_THRESHOLD_MV
    runs, i, n = [], 0, len(trans)
    min_frames = MIN_SEGMENT_S * frame_rate_hz
    while i < n:
        if trans[i]:
            i += 1
            continue
        j = i
        while j < n and not trans[j]:
            j += 1
        if (j - i) >= min_frames:
            runs.append((i, j))
        i = j
    return runs


def corpus_cell_order(colmap):
    """Channel indices that reorder a dump frame into corpus cell order."""
    return [i for i, _ in sorted(enumerate(colmap),
                                  key=lambda kv: (float(kv[1]['pulse_us']),
                                                  -float(kv[1]['threshold_v'])))]


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _plateau_centre(sess, run):
    return 0.5 * (float(sess.t_seconds[run[0]]) + float(sess.t_seconds[run[1] - 1]))


def _interp_baseline(sess, runs, med, j, k, centre):
    """Air baseline at `centre`: linear between plateaus j and k, or the nearer one
    alone when only one is available. Mirrors compute_plateau_stats()'s two-anchor
    interpolation, which is why it is worth the extra work -- a single anchor carries
    the full drift between it and the capture."""
    if j is None:
        return med[k]
    if k is None:
        return med[j]
    tj, tk = _plateau_centre(sess, runs[j]), _plateau_centre(sess, runs[k])
    if tk <= tj:
        return med[j]
    f = (centre - tj) / (tk - tj)
    return med[j] + f * (med[k] - med[j])


def match_plateaus(sess, corpus, cos_floor):
    """One record per plateau: the best (reference, corpus capture) pairing, or a
    rejection with the reason. Never returns a label below the floor."""
    rate = pimd_features.measure_frame_rate_hz(sess.fw_seconds)
    runs = find_plateaus(sess.frames_mV, rate)
    order = corpus_cell_order(sess.colmap)
    med = [np.median(sess.frames_mV[a:b], axis=0) for a, b in runs]
    wall = [(sess.t0 + dt.timedelta(seconds=float(sess.t_seconds[a])),
             sess.t0 + dt.timedelta(seconds=float(sess.t_seconds[b - 1]))) for a, b in runs]
    sha = sess.profile_sha8_explicit or ''
    results = []
    for i, ((a, b), m) in enumerate(zip(runs, med)):
        t_start, t_end = wall[i]
        pool = [c for c in corpus
                if (not sha or not c['profile_sha8'] or c['profile_sha8'] == sha)
                and t_start - dt.timedelta(seconds=LAG_BEFORE_S) <= c['captured_at']
                <= t_end + dt.timedelta(seconds=LAG_AFTER_S)]
        # Air baseline, built the way compute_plateau_stats() builds it: linearly
        # INTERPOLATED between a reference before and one after, evaluated at this
        # plateau's centre. A single earlier reference is not good enough -- at the
        # measured ~50 uV/s drift, a 400 s gap between plateaus is tens of mV of
        # baseline error, comparable to the signal itself, and it was costing ~0.05
        # of cosine against the corpus (which never sees that error, because it
        # brackets every capture with fresh air).
        centre = 0.5 * (float(sess.t_seconds[a]) + float(sess.t_seconds[b - 1]))
        near = [j for j in range(len(runs)) if j != i
                and abs(centre - 0.5 * (float(sess.t_seconds[runs[j][0]])
                                        + float(sess.t_seconds[runs[j][1] - 1]))) <= REF_MAX_AGE_S]
        befores = [j for j in near if j < i] or [None]
        afters = [j for j in near if j > i] or [None]
        best = None
        for j in befores:
            for k in afters:
                if j is None and k is None:
                    continue
                ref = _interp_baseline(sess, runs, med, j, k, centre)
                delta = (m - ref)[order]
                amp = float(np.linalg.norm(delta))
                if amp < MIN_AMP_MV:
                    continue
                for c in pool:
                    score = float(np.dot(unit(delta), unit(c['vec'])))
                    if best is None or score > best['cos']:
                        best = dict(cos=score, ref=(j, k), amp=amp, cap=c)
        rec = dict(idx=i, start=a, end=b, t_start=t_start, t_end=t_end,
                    dur_s=(b - a) / rate, n_candidates=len(pool), best=best)
        if best is None:
            rec['reject'] = ('no candidate' if not pool
                              else 'no reference plateau with a delta above %.1f mV' % MIN_AMP_MV)
        elif best['cos'] < cos_floor:
            rec['reject'] = 'best cosine %.3f below floor %.2f' % (best['cos'], cos_floor)
        results.append(rec)
    return results, rate


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------

def inject(path, results, cos_floor, dry_run=True):
    """Rewrite `path` with '# mark:' / '# mark_target:' lines before the data row that
    starts each accepted plateau.

    Streams the original line by line and only ever INSERTS, so every existing line --
    header, comment and data alike -- is passed through byte-identical. Verified by the
    caller rather than trusted."""
    accepted = {r['start']: r for r in results if not r.get('reject')}
    if not accepted:
        return 0, None
    stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = '{0}.bak-{1}-pre-relabel'.format(path, stamp)
    tmp = path + '.relabel-tmp'
    n_written = 0
    with open(path, newline='') as fin, open(tmp, 'w', newline='') as fout:
        data_idx = -1
        seen_header = False
        for line in fin:
            if line.startswith('#'):
                fout.write(line)
                continue
            if not seen_header:
                seen_header = True          # the column-header row
                fout.write(line)
                fout.write('# session_notes: (auto) marks below RECONSTRUCTED by {0} on {1}; '
                            'cosine floor {2:.2f}; not operator ground truth\n'.format(
                                TOOL_VERSION, dt.date.today().isoformat(), cos_floor))
                continue
            data_idx += 1
            rec = accepted.get(data_idx)
            if rec is not None:
                cap = rec['best']['cap']
                ts = rec['t_start'].isoformat()
                tid = cap['target_id']
                dist = '' if tid == 'air' else cap['distance_mm']
                text = 'air' if tid == 'air' else '{0} @{1}'.format(tid, dist)
                fout.write('# mark: {0}, {1}\n'.format(ts, text))
                sio = io.StringIO()
                csv.writer(sio, lineterminator='\n').writerow([
                    tid, dist, cap['long_axis'], 'na', 0, 0, cap['medium'],
                    cap['repeat_idx'],
                    'reconstructed cos={0:.3f} src={1}'.format(rec['best']['cos'], cap['capture_id']),
                    cap['tilt_deg']])
                fout.write('# mark_target: {0}, {1}'.format(ts, sio.getvalue()))
                n_written += 1
            fout.write(line)
    if dry_run:
        os.unlink(tmp)
        return n_written, None
    shutil.copy2(path, backup)
    os.replace(tmp, path)
    return n_written, backup


def verify_data_unchanged(original, rewritten):
    """Every non-'#' line must be byte-identical. Injection only inserts comments."""
    def data_lines(p):
        with open(p, newline='') as f:
            return [ln for ln in f if not ln.startswith('#')]
    a, b = data_lines(original), data_lines(rewritten)
    if len(a) != len(b):
        return False, 'line count {0} -> {1}'.format(len(a), len(b))
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return False, 'first difference at data line {0}'.format(i)
    return True, '{0} data lines identical'.format(len(a))


# ---------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('dumps', nargs='+', help='session dump CSV(s)')
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--cos-floor', type=float, default=COS_FLOOR_DEFAULT)
    ap.add_argument('--apply', action='store_true',
                    help='rewrite the dumps in place (default: dry run, writes nothing)')
    args = ap.parse_args(argv)

    corpus = load_corpus(args.corpus)
    print('corpus: {0} captures from {1}'.format(len(corpus), os.path.basename(args.corpus)))
    total_acc = total_rej = 0
    for path in args.dumps:
        print('\n=== {0} ==='.format(os.path.basename(path)))
        try:
            sess = pimd_features.parse_session_file(path)
        except ValueError as exc:
            # A header-only dump (stream opened, never delivered a frame) is a real
            # thing on disk -- session_20260731_091656.csv -- and parse_session_file
            # raises on it. Skip rather than abort the run: one dead file must not
            # cost the other ten.
            print('  unreadable — skipped ({0})'.format(exc))
            continue
        if not len(sess.frames_mV):
            print('  empty (header only) — skipped')
            continue
        if sess.marks or sess.captures:
            print('  already has {0} mark(s) / {1} capture line(s) — skipped, will not '
                  'double-label'.format(len(sess.marks), len(sess.captures)))
            continue
        results, rate = match_plateaus(sess, corpus, args.cos_floor)
        print('  {0} frames @ {1:.2f} Hz, {2} plateau(s)'.format(
            len(sess.frames_mV), rate, len(results)))
        for r in results:
            head = '  {0} {1:6.1f}s'.format(r['t_start'].strftime('%H:%M:%S'), r['dur_s'])
            if r.get('reject'):
                amp = '' if not r['best'] else '  |d|={0:.1f}mV'.format(r['best']['amp'])
                print('{0}  REJECT  {1} (candidates={2}){3}'.format(
                    head, r['reject'], r['n_candidates'], amp))
                total_rej += 1
            else:
                b = r['best']
                print('{0}  cos {1:+.3f}  {2:24s} @{3:>4}mm  |d|={4:6.1f}mV'.format(
                    head, b['cos'], b['cap']['target_id'], b['cap']['distance_mm'], b['amp']))
                total_acc += 1
        n, backup = inject(path, results, args.cos_floor, dry_run=not args.apply)
        if args.apply and backup:
            ok, msg = verify_data_unchanged(backup, path)
            print('  WROTE {0} mark pair(s); backup {1}'.format(n, os.path.basename(backup)))
            print('  verify: {0} — {1}'.format('OK' if ok else 'FAILED', msg))
            if not ok:
                print('  restoring from backup'); shutil.copy2(backup, path); return 1
        else:
            print('  dry run: would write {0} mark pair(s)'.format(n))
    print('\ntotal: {0} accepted, {1} rejected'.format(total_acc, total_rej))
    if not args.apply:
        print('(dry run — nothing written; re-run with --apply)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
