#!/usr/bin/env python3
"""
pimd_corpus_check.py — corpus-level acceptance checks for a PIMD signature corpus.

Version: 1.6

Reads the v1.32+ target-registry corpus schema (the CORPUS_HEADER schema that
pimd_classviz.py's Training capture and pimd_features.py's corpus builder both
write). The authoritative column list is pimd_features.CORPUS_HEADER_FIELDS;
real files live at src/data/corpora/gui_signatures_*.csv. Capture identity is
(session, capture_id); the *physical* identity used for cross-capture checks is
the placement tuple (target_id, distance_mm, long_axis, face_normal,
offset_x_mm, offset_y_mm, medium) -- mirrors pimd_classviz._placement_tuple_key.

Distances are read from the data (whatever distance_mm values were captured),
not hardcoded -- a target seen at >= 2 distances gets shape-invariance rows and
at >= 3 distances a falloff fit. All distance labels are in mm. An air capture
has no distance at all (blank distance_mm column): it appears in the split-half
SNR check labelled '@air' and is excluded from every distance-keyed check.

# History (full detail in CHANGELOG.md):
#   v1.6 FIX air captures (blank distance_mm) aborted the whole run
#   v1.5 migrate to the v1.32+ target_id/distance_mm schema; retire canary check; repeats via repeat_idx
#   v1.4 loud rejection of the v1.32+ schema (stopgap, superseded by v1.5)
#   v1.3 campaign-2: canary suffix-match, cross-session repeat, cos(10,15) gate, --baseline gating
#   v1.2 drop solder-specific 5/15cm falloff sub-check
#   v1.1 widen REPEAT_MARK_RE to accept numbered (rptN) suffixes
#   v1.0 initial six-check corpus acceptance suite (legacy target/distance_cm schema)

Usage:
    python pimd_corpus_check.py <corpus_csv> [--baseline <baseline_corpus_csv>]
"""

import argparse
import csv
import os
import sys

import numpy as np
import pandas as pd

import pimd_features
import pimd_target_check

# --- pass bands (tunable in one place) --------------------------------------
SHAPE_INVARIANCE_COS_MIN = 0.97
SPLITHALF_SNR_MIN = 10.0
REPEAT_COS_MIN = 0.995
REPEAT_RATIO_BAND = (0.95, 1.05)
FALLOFF_RATIO_BAND = (0.85, 1.15)
CROSS_CAMPAIGN_COS_MIN = 0.99

# The physical-placement identity a repeat_idx increments against (mirror of
# pimd_classviz._placement_tuple_key). PLACEMENT_FIELDS keys "the same
# placement" (used by the repeat check); TARGET_FIELDS is the same minus
# distance_mm and keys "the same physical target across distances" (used by the
# shape-invariance and falloff checks).
PLACEMENT_FIELDS = ('target_id', 'distance_mm', 'long_axis', 'face_normal',
                    'offset_x_mm', 'offset_y_mm', 'medium')
TARGET_FIELDS = tuple(f for f in PLACEMENT_FIELDS if f != 'distance_mm')

# target_id values that are not physical objects and are excluded from the
# object-centric checks (per-capture air anchors are captured separately and
# already do the drift correction that the old canary check used to audit).
NON_OBJECT_TARGET_IDS = frozenset({'', 'air'})

CHECK_ORDER = ["shape-invariance", "splithalf-snr", "repeat-consistency",
               "distance-falloff", "cross-campaign"]

CORPUS_FIELDS = pimd_features.CORPUS_HEADER_FIELDS
REQUIRED_FIELDS = set(CORPUS_FIELDS)


# -----------------------------------------------------------------------------
# Loading (v1.32+ CORPUS_HEADER schema only)
# -----------------------------------------------------------------------------

def _parse_distance_mm(raw):
    """Corpus distance_mm -> int mm, or None when the column is blank.

    An **air** capture legitimately has no distance: pimd_features writes
    format_distance(None) == '' for it (classviz forces distance_mm=None when
    target_id == 'air'). v1.5 parsed this column unconditionally, so a single
    air capture anywhere in the corpus aborted the whole run with an opaque
    "could not convert string to float: ''" before any check could run.
    None also covers a hand-edited row that simply left the field empty; every
    distance-keyed check skips those rather than guessing a value."""
    raw = raw.strip()
    return int(round(float(raw))) if raw else None


def _read_header(path):
    with open(path, newline='') as f:
        for line in f:
            if line.startswith('#'):
                continue
            return next(csv.reader([line]))
    return None


def load_corpus(path):
    """Reads a v1.32+ gui_signatures_*.csv into one signature dict per capture,
    keyed on (session, capture_id) -- the same regrouping/sort as
    pimd_classviz._scan_editable_signature_file (sort each capture's cell rows
    by pulse_us, then descending threshold_v). Rejects the legacy
    target/distance_cm schema with a clear message (support intentionally
    dropped in v1.5 -- there is no legacy corpus left to validate)."""
    header = _read_header(path)
    if header is None:
        raise SystemExit(f"{path}: empty file")
    cols = set(header)

    if 'target_id' not in cols or 'distance_mm' not in cols:
        if 'target' in cols or 'distance_cm' in cols:
            raise SystemExit(
                f"{path}: legacy target/distance_cm corpus schema -- "
                "pimd_corpus_check.py v1.5+ only reads the v1.32+ target-registry "
                "schema (target_id/distance_mm columns; see "
                "pimd_features.CORPUS_HEADER_FIELDS). Legacy-schema support was "
                "intentionally dropped; there is no legacy corpus left to validate.")
        raise SystemExit(
            f"{path}: unrecognized corpus CSV schema (header: {','.join(header)})")

    missing = REQUIRED_FIELDS - cols
    if missing:
        raise SystemExit(
            f"{path}: v1.32+ schema is missing required columns "
            f"{sorted(missing)} (expected pimd_features.CORPUS_HEADER_FIELDS).")

    idx = {name: i for i, name in enumerate(header)}
    groups, order = {}, []
    with open(path, newline='') as f:
        reader = csv.reader(line for line in f if not line.startswith('#'))
        next(reader, None)   # header row
        for parts in reader:
            if not parts:
                continue
            key = (parts[idx['session']], parts[idx['capture_id']])
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(parts)

    sigs = []
    for key in order:
        rows = sorted(groups[key],
                      key=lambda p: (float(p[idx['pulse_us']]), -float(p[idx['threshold_v']])))
        first = rows[0]

        def field(name, row=first):
            return row[idx[name]]

        sigs.append(dict(
            session=field('session'), capture_id=field('capture_id'),
            target_id=field('target_id'), short_name=field('short_name'),
            distance_mm=_parse_distance_mm(field('distance_mm')),
            long_axis=field('long_axis'), face_normal=field('face_normal'),
            offset_x_mm=field('offset_x_mm'), offset_y_mm=field('offset_y_mm'),
            medium=field('medium'), repeat_idx=int(float(field('repeat_idx'))),
            shape=np.array([float(p[idx['delta_mV']]) for p in rows], dtype=float),
            amp=float(field('plateau_amp_mV')),
            splithalf=float(field('splithalf_floor')),
            quality=field('quality'),
        ))

    n_cells = {len(s['shape']) for s in sigs}
    if len(n_cells) > 1:
        raise SystemExit(f"{path}: mixed cell counts across captures {sorted(n_cells)} "
                          "-- refusing to mix profile geometries (DESIGN §11)")
    return sigs


# -----------------------------------------------------------------------------
# Row / key helpers
# -----------------------------------------------------------------------------

def cosine(u, v):
    nu, nv = np.linalg.norm(u), np.linalg.norm(v)
    if nu == 0 or nv == 0:
        return np.nan
    return float(np.dot(u, v) / (nu * nv))


def mkrow(check, metric, value, band, status):
    return dict(check=check, metric=metric, value=value, pass_band=band, status=status)


def tag(corpus_label, session):
    return f'{corpus_label}:{session}'


def label_of(sig):
    return sig['short_name'] or sig['target_id']


def placement_key(sig):
    return tuple(str(sig[f]) for f in PLACEMENT_FIELDS)


def target_key(sig):
    return tuple(str(sig[f]) for f in TARGET_FIELDS)


def one_per_distance(sigs):
    """Groups object captures by physical target (TARGET_FIELDS) into
    {target_key -> {distance_mm -> sig}}, keeping one signature per distance --
    preferring the base placement (repeat_idx == 1) so repeats never
    double-count in the distance-keyed checks. Captures with no distance are
    excluded: air by target_id, plus (defensively) any object row whose
    distance_mm column was left blank -- a None key would otherwise blow up the
    `sorted(grp)` every caller does."""
    by_target = {}
    for s in sigs:
        if s['target_id'] in NON_OBJECT_TARGET_IDS or s['distance_mm'] is None:
            continue
        grp = by_target.setdefault(target_key(s), {})
        d = s['distance_mm']
        cur = grp.get(d)
        if cur is None or (s['repeat_idx'] == 1 and cur['repeat_idx'] != 1):
            grp[d] = s
    return by_target


# -----------------------------------------------------------------------------
# Check 1 — shape distance-invariance
# -----------------------------------------------------------------------------

def check_shape_invariance(sigs, corpus_label):
    rows = []
    gate_pass = gate_total = 0
    report_pass = report_total = 0

    for _, grp in sorted(one_per_distance(sigs).items()):
        dists = sorted(grp)
        if len(dists) < 2:
            continue
        near, far = dists[0], dists[-1]
        mid = dists[1] if len(dists) >= 3 else None
        lbl = label_of(grp[near])
        where = f'{lbl} [{tag(corpus_label, grp[near]["session"])}]'

        c_nf = cosine(grp[near]['shape'], grp[far]['shape'])
        c_mf = cosine(grp[mid]['shape'], grp[far]['shape']) if mid is not None else None

        if mid is not None:
            c_nm = cosine(grp[near]['shape'], grp[mid]['shape'])
            rows.append(mkrow('shape-invariance', f'cos({near}v{mid}mm) {where}',
                               f'{c_nm:.4f}', f'>= {SHAPE_INVARIANCE_COS_MIN}',
                               'PASS' if c_nm >= SHAPE_INVARIANCE_COS_MIN else 'FAIL'))
            # near-vs-far is report-only: an extended object can genuinely
            # change shape at the nearest distance (near-field) while agreeing
            # at mid/far -- that's physics, not a capture defect, so it's
            # AMBER'd rather than failed when the far-field pair still agrees.
            metric = f'cos({near}v{far}mm) {where}'
            if c_nf >= SHAPE_INVARIANCE_COS_MIN:
                status = 'PASS'
            elif c_mf is not None and c_mf >= SHAPE_INVARIANCE_COS_MIN:
                status = 'AMBER'
                metric += ' (near-field @near, extended target?)'
            else:
                status = 'FAIL'
            rows.append(mkrow('shape-invariance', metric, f'{c_nf:.4f}', 'report only', status))
            report_total += 1
            report_pass += (status == 'PASS')

            s_mf = 'PASS' if c_mf >= SHAPE_INVARIANCE_COS_MIN else 'FAIL'
            rows.append(mkrow('shape-invariance', f'cos({mid}v{far}mm) {where}',
                               f'{c_mf:.4f}', f'>= {SHAPE_INVARIANCE_COS_MIN}', s_mf))
            gate_total += 1
            gate_pass += (s_mf == 'PASS')
        else:
            # Only two distances -- no near-field/far-field separation is
            # possible, so the single pair is the gate directly.
            s_nf = 'PASS' if c_nf >= SHAPE_INVARIANCE_COS_MIN else 'FAIL'
            rows.append(mkrow('shape-invariance', f'cos({near}v{far}mm) {where}',
                               f'{c_nf:.4f}', f'>= {SHAPE_INVARIANCE_COS_MIN}', s_nf))
            gate_total += 1
            gate_pass += (s_nf == 'PASS')

    if gate_total:
        rows.append(mkrow('shape-invariance',
                           f'targets with far-field shape cos >= {SHAPE_INVARIANCE_COS_MIN} [{corpus_label}]',
                           f'{gate_pass}/{gate_total}', f'{gate_total}/{gate_total}',
                           'PASS' if gate_pass == gate_total else 'FAIL'))
    if report_total:
        rows.append(mkrow('shape-invariance',
                           f'targets with near-field shape cos >= {SHAPE_INVARIANCE_COS_MIN} [{corpus_label}]',
                           f'{report_pass}/{report_total}', 'report only', 'PASS'))
    if not gate_total and not report_total:
        rows.append(mkrow('shape-invariance',
                           f'targets captured at >= 2 distances [{corpus_label}]',
                           '0', 'n/a (informational)', 'SKIP'))
    return rows


# -----------------------------------------------------------------------------
# Check 2 — split-half SNR
# -----------------------------------------------------------------------------

def check_splithalf_snr(sigs, corpus_label):
    """Runs over *every* capture, air included -- an air capture has no
    distance but its split-half floor is still the most directly meaningful
    noise reading in the corpus, so it gets a row labelled '@air'. The sort key
    substitutes -1 for a missing distance (real distances are >= 0) so air
    sorts first within a label instead of raising on None < int."""
    rows = []

    def sort_key(s):
        d = s['distance_mm']
        return (label_of(s), -1 if d is None else d, s['session'])

    for s in sorted(sigs, key=sort_key):
        where = 'air' if s['distance_mm'] is None else f'{s["distance_mm"]}mm'
        metric = f'{label_of(s)} @{where} [{tag(corpus_label, s["session"])}]'
        if s['splithalf'] <= 0:
            rows.append(mkrow('splithalf-snr', metric, 'n/a (splithalf=0)',
                               f'>= {SPLITHALF_SNR_MIN}', 'SKIP'))
            continue
        snr = s['amp'] / s['splithalf']
        status = 'PASS' if snr >= SPLITHALF_SNR_MIN else 'FAIL'
        rows.append(mkrow('splithalf-snr', metric, f'{snr:.1f}',
                           f'>= {SPLITHALF_SNR_MIN}', status))
    return rows


# -----------------------------------------------------------------------------
# Check 3 — repeat consistency (via repeat_idx)
# -----------------------------------------------------------------------------

def check_repeat(sigs, corpus_label):
    """Repeat visits are now structured: within a placement (PLACEMENT_FIELDS),
    repeat_idx == 1 is the base and repeat_idx >= 2 are repeats of that same
    placement -- captured in the same session or a later one, it makes no
    difference here since the placement tuple is session-independent. Compares
    each repeat's shape cosine / amp ratio against the base."""
    rows = []
    by_placement = {}
    for s in sigs:
        if s['target_id'] in NON_OBJECT_TARGET_IDS:
            continue
        by_placement.setdefault(placement_key(s), []).append(s)

    found = False
    for _, caps in sorted(by_placement.items()):
        reps = [c for c in caps if c['repeat_idx'] >= 2]
        if not reps:
            continue
        found = True
        lbl, d = label_of(caps[0]), caps[0]['distance_mm']
        bases = [c for c in caps if c['repeat_idx'] == 1]
        if not bases:
            rows.append(mkrow('repeat-consistency',
                               f'base (repeat_idx==1) for "{lbl}" @{d}mm [{corpus_label}]',
                               'not found', 'n/a', 'SKIP'))
            continue
        base = min(bases, key=lambda c: c['capture_id'])
        for rep in sorted(reps, key=lambda c: c['repeat_idx']):
            c = cosine(rep['shape'], base['shape'])
            ratio = (rep['amp'] / base['amp']) if base['amp'] else np.nan
            status_c = 'PASS' if c > REPEAT_COS_MIN else 'FAIL'
            status_r = ('PASS' if REPEAT_RATIO_BAND[0] <= ratio <= REPEAT_RATIO_BAND[1]
                        else 'FAIL')
            where = (f'"{lbl}" @{d}mm rpt{rep["repeat_idx"]} vs base '
                     f'[{tag(corpus_label, rep["session"])}]')
            rows.append(mkrow('repeat-consistency', f'shape cos {where}',
                               f'{c:.4f}', f'> {REPEAT_COS_MIN}', status_c))
            rows.append(mkrow('repeat-consistency', f'amp ratio {where}',
                               f'{ratio:.3f}',
                               f'{REPEAT_RATIO_BAND[0]}-{REPEAT_RATIO_BAND[1]}', status_r))

    if not found:
        rows.append(mkrow('repeat-consistency',
                           f'repeat captures (repeat_idx >= 2) found [{corpus_label}]',
                           '0', 'n/a (informational)', 'SKIP'))
    return rows


# -----------------------------------------------------------------------------
# Check 4 — distance falloff
# -----------------------------------------------------------------------------

def fit_falloff(distances, amps):
    r = np.array(distances, dtype=float)
    a = np.array(amps, dtype=float)
    if np.any(a <= 0):
        return None
    slope, intercept = np.polyfit(np.log(r), np.log(a), 1)
    fit = np.exp(intercept) * r ** slope
    ratios = fit / a
    worst = float(ratios[np.argmax(np.abs(np.log(ratios)))])
    return -float(slope), worst


def check_falloff(sigs, corpus_label):
    rows = []
    any_target = False
    for _, grp in sorted(one_per_distance(sigs).items()):
        dists = sorted(grp)
        if len(dists) < 3:
            continue
        any_target = True
        where = f'{label_of(grp[dists[0]])} [{tag(corpus_label, grp[dists[0]]["session"])}]'
        fit = fit_falloff(dists, [grp[d]['amp'] for d in dists])
        if fit is None:
            rows.append(mkrow('distance-falloff', f'n (exponent) {where}',
                               'n/a (non-positive amp)', 'report only', 'SKIP'))
        else:
            n, worst = fit
            rows.append(mkrow('distance-falloff', f'n (exponent) {where}',
                               f'{n:.2f}', 'report only', 'PASS'))
            status = 'PASS' if FALLOFF_RATIO_BAND[0] <= worst <= FALLOFF_RATIO_BAND[1] else 'FAIL'
            rows.append(mkrow('distance-falloff', f'worst fit/measured ratio {where}',
                               f'{worst:.3f}',
                               f'{FALLOFF_RATIO_BAND[0]}-{FALLOFF_RATIO_BAND[1]}', status))
    if not any_target:
        rows.append(mkrow('distance-falloff',
                           f'targets captured at >= 3 distances [{corpus_label}]',
                           '0', 'n/a (informational)', 'SKIP'))
    return rows


# -----------------------------------------------------------------------------
# Check 5 — cross-campaign repeatability (only with --baseline)
# -----------------------------------------------------------------------------

def _cross_campaign_shapes(sigs):
    """One shape per (target_id, distance_mm), preferring the base placement --
    keyed by the *stable* target_id so it survives short_name edits between
    campaigns."""
    out = {}
    for _, grp in one_per_distance(sigs).items():
        for d, s in grp.items():
            key = (s['target_id'], d)
            cur = out.get(key)
            if cur is None or (s['repeat_idx'] == 1 and cur[1] != 1):
                out[key] = (s['shape'], s['repeat_idx'])
    return {k: v[0] for k, v in out.items()}


def check_cross_campaign(sigs_a, label_a, sigs_b, label_b, targets):
    """Compares the primary corpus (sigs_a) against a --baseline corpus
    (sigs_b, e.g. a prior campaign/rig), per (target_id, distance_mm) shape
    cosine. Informational, cross-rig only -- never a same-rig acceptance gate
    (see main()'s exit-code computation). `targets` (the registry, possibly
    empty) is only used to enrich labels with material_class."""
    rows = []
    a = _cross_campaign_shapes(sigs_a)
    b = _cross_campaign_shapes(sigs_b)
    common = sorted(set(a) & set(b))
    if not common:
        rows.append(mkrow('cross-campaign',
                           f'(target_id, distance) pairs common to {label_a} and {label_b} '
                           '(informational, cross-rig)', '0', 'n/a', 'SKIP'))
        return rows
    for (target_id, d) in common:
        c = cosine(a[(target_id, d)], b[(target_id, d)])
        status = 'PASS' if c >= CROSS_CAMPAIGN_COS_MIN else 'FAIL'
        mat = targets[target_id].material_class if target_id in targets else None
        lbl = f'"{target_id}"' + (f' ({mat})' if mat else '')
        rows.append(mkrow('cross-campaign',
                           f'shape cos {lbl} @{d}mm ({label_a} vs {label_b}) '
                           '(informational, cross-rig)',
                           f'{c:.4f}', f'>= {CROSS_CAMPAIGN_COS_MIN}', status))
    return rows


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def load_registry():
    """Best-effort registry load for label enrichment only -- a missing or
    broken registry must not stop an acceptance run, so failures degrade to an
    empty dict (labels then fall back to bare target_id)."""
    try:
        targets, _issues = pimd_target_check.load_targets()
        return targets
    except (OSError, ValueError):
        return {}


def build_arg_parser():
    p = argparse.ArgumentParser(
        description='Corpus-level acceptance checks for a PIMD signature corpus '
                    '(v1.32+ target-registry schema).')
    p.add_argument('corpus_csv', help='corpus CSV to check (v1.32+ CORPUS_HEADER schema)')
    p.add_argument('--baseline', metavar='CORPUS_CSV', default=None,
                    help="a second corpus (e.g. a prior campaign/rig's baseline) for "
                         'cross-campaign shape comparison. Informational only -- never '
                         'gates the exit code, and is never itself run through the full '
                         'acceptance suite (only compared against the primary corpus). '
                         'Omit for a same-rig acceptance run (default: cross-campaign '
                         'checks are skipped entirely).')
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = build_arg_parser().parse_args(argv)

    label = os.path.splitext(os.path.basename(args.corpus_csv))[0]
    sigs = load_corpus(args.corpus_csv)
    targets = load_registry()

    rows = []
    rows += check_shape_invariance(sigs, label)
    rows += check_splithalf_snr(sigs, label)
    rows += check_repeat(sigs, label)
    rows += check_falloff(sigs, label)

    if args.baseline:
        baseline_label = os.path.splitext(os.path.basename(args.baseline))[0]
        baseline_sigs = load_corpus(args.baseline)
        rows += check_cross_campaign(sigs, label, baseline_sigs, baseline_label, targets)
    else:
        rows.append(mkrow('cross-campaign',
                           'cross-campaign checks skipped (no --baseline corpus given)',
                           'n/a', 'n/a', 'SKIP'))

    df = pd.DataFrame(rows, columns=['check', 'metric', 'value', 'pass_band', 'status'])
    df = df.iloc[sorted(range(len(df)), key=lambda i: CHECK_ORDER.index(df.iloc[i]['check']))]
    df = df.rename(columns={'pass_band': 'pass band', 'status': 'PASS/FAIL'})

    with pd.option_context('display.max_rows', None, 'display.max_colwidth', 70,
                            'display.width', 160):
        print(df.to_string(index=False))

    n_fail = int((df['PASS/FAIL'] == 'FAIL').sum())
    n_amber = int((df['PASS/FAIL'] == 'AMBER').sum())
    n_skip = int((df['PASS/FAIL'] == 'SKIP').sum())
    n_pass = len(df) - n_fail - n_amber - n_skip
    print(f'\n{len(df)} checks: {n_pass} PASS, {n_amber} AMBER, {n_fail} FAIL, {n_skip} SKIP')

    # Cross-campaign is informational -- a different rig/campaign is a
    # reference point, not a same-rig acceptance gate -- so its FAILs never
    # contribute to the exit code (AMBER already doesn't, since it's not
    # 'FAIL' in the first place).
    n_fail_gating = int(((df['PASS/FAIL'] == 'FAIL') & (df['check'] != 'cross-campaign')).sum())
    return 1 if n_fail_gating else 0


if __name__ == '__main__':
    sys.exit(main())
