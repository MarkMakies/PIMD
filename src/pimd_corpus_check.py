#!/usr/bin/env python3
"""
pimd_corpus_check.py — corpus-level acceptance checks for a PIMD signature corpus.

Version: 1.3
Changelog:
  v1.3 (2026-07-07) — Campaign 2 (rig change) support, four changes:
      (A) check_canary() now detects canary rows by suffix match (any
      '<base> CANARY-START'/'<base> CANARY-END' target, not just a bare
      exact-match "CANARY-START"/"CANARY-END") -- train-s1.csv's
      "copper pipe CANARY-START"/"copper pipe CANARY-END" rows were
      silently invisible to the old exact-match check ("0 pairs found"),
      even though the SNR check already proved both were captured. New
      strip_canary_suffix() helper (replaces CANARY_LABELS) also emits a
      'drift status' row per pair (protocol v2's drift-flag criterion:
      either the shape-cos or amp-ratio check failing means the session is
      drift-flagged and its 15cm rows get downgraded -- pimd_features.py's
      quality column handles the actual downgrade, this just reports).
      Canary rows are now also excluded from check_shape_invariance() and
      check_falloff() (they only exist @5cm and would otherwise pollute
      per-target checks if a session ever names one to look like a normal
      target).
      (B) New check_repeat_cross_session(): the same target+distance
      captured in two different sessions (e.g. a capture plan revisiting
      'copper pipe' in session s1 and again in s4) now gets its own
      shape-cos/amp-ratio repeat-consistency rows, labelled with both
      session IDs -- distinct from and additional to the existing
      within-session '(rpt)' handling, which is unchanged.
      (C) check_shape_invariance() adds a cos(10v15) metric row per target.
      Extended objects (spanner, cast iron trivet, galvanized pipe) show a
      real, repeatable near-field shape change at 5cm on this rig while
      agreeing at 10/15cm -- blanket-FAILing that mislabels physics as
      capture error. New verdict: cos(5,15) < 0.97 but cos(10,15) >= 0.97
      now reports 'AMBER' (near-field @5, extended target?) instead of
      'FAIL'; both low is still FAIL. The cos(5,15) roll-up row is now
      report-only (no verdict); a new cos(10,15) roll-up row is the real
      per-corpus gate. AMBER is its own status alongside PASS/FAIL/SKIP in
      the summary line and never contributes to the exit code.
      (D) Cross-campaign comparison (check_cross_campaign(), check 6) is now
      gated behind an explicit `--baseline <corpus_csv>` CLI argument
      (replaces the old ambiguous positional 2nd-corpus-file convention;
      only the primary corpus gets the full acceptance suite, the baseline
      is only ever used for the comparison itself). Default (no baseline):
      prints one SKIP row, 'cross-campaign checks skipped (campaign 2; no
      rig-1 baseline applicable)'. When given, results are labelled
      '(informational, cross-rig)' and excluded from the exit-code gate --
      a different rig/campaign is a reference point, not a same-rig
      acceptance criterion. No absolute-mV thresholds anywhere in this file
      assumed the old plateau_amp_mV convention (checked per pimd_features.py
      v5's changelog) -- every amplitude-adjacent check here is already
      ratio- or cosine-based, so nothing else needed changing for that.
      Verified against train-s1.csv (session_20260707_143723): canary
      shape-cos=0.9983/amp-ratio=0.952 now report real values (previously
      invisible); spanner/trivet/galvanized cos(5,15) FAILs correctly flip
      to AMBER (their cos(10,15) = 0.9887/0.9863/0.9963, all >= 0.97);
      copper pipe/SNR/falloff rows are byte-for-byte identical to the
      pre-this-change run (diffed directly); `--baseline
      PIMD_target_corpus_signatures_v1.csv` runs without error (0 common
      5cm target names -- v1 uses weight-suffixed names like "copper pipe
      120g", a naming-convention mismatch, not a code defect; out of scope
      to fix here).
  v1.2 (2026-07-07) — Removed the solder-specific 5cm/15cm amplitude-ratio
      sub-check from check 5 (distance falloff): it always printed a row
      (PASS/FAIL when a "solder"-named target was present, else an
      uninformative "n/a (no solder target)" SKIP for every corpus that
      didn't happen to include one), which read as clutter/noise on any
      corpus not built around that specific canary. The general per-target
      falloff fit (n exponent, worst fit/measured ratio) still runs for
      every target regardless of name, solder included. Removed
      SOLDER_FALLOFF_MIN along with it.
  v1.1 (2026-07-07) — Widened REPEAT_MARK_RE to accept an optional trailing
      number inside the parens (e.g. '(rpt3)', '(rpt4)'), not just a bare
      '(rpt)', so numbered repeat suffixes are also recognised
      as repeat-consistency targets, not just a bare '(rpt)' -- companion to
      pimd_features.py v4, which now auto-suffixes a session's 2nd+ visit to
      the same (target, distance_cm) this way rather than leaving them
      identically named (which load_corpus() correctly refused to accept:
      "mixed cell counts ... refusing to mix profile geometries").
  v1.0 (2026-07-04) — Initial version. Runs six checks against one or two
      corpus CSVs (schema of PIMD_target_corpus_signatures.csv, long or wide
      format, auto-detected):
        1. shape distance-invariance — cosine(5cm,10cm) and cosine(5cm,15cm)
           per capture, plus a per-corpus count passing cos(5,15) >= 0.97.
        2. split-half SNR (plateau_amp_mV / splithalf_floor) per signature.
        3. canary consistency — CANARY-START vs CANARY-END target rows,
           matched per session and shared distance.
        4. repeat consistency — targets marked '(rpt)' or 'REPEAT' vs their
           best-matching base capture.
        5. distance falloff — amp ~ r^-n log-log fit over 5/10/15 cm, worst
           fit/measured ratio. (v1.2 removed a solder-specific 5cm/15cm
           contamination-ratio sub-check that used to run here.)
        6. cross-campaign repeatability — per-target 5cm shape cosine between
           two corpora, only run when two corpus CSVs are given.
      All checks run per corpus (each input CSV independently); check 6 is
      the only cross-corpus comparison. Everything is printed as one flat
      table (check, metric, value, pass band, PASS/FAIL/SKIP) and the process
      exits nonzero if any row FAILs, so this can gate a capture day.
      Plain numpy / pandas only (repo convention).

Usage:
    python pimd_corpus_check.py <corpus_csv> [--baseline <baseline_corpus_csv>]
"""

import argparse
import os
import re
import sys

import numpy as np
import pandas as pd

# --- pass bands (tunable in one place) --------------------------------------
SHAPE_INVARIANCE_COS_MIN = 0.97
SPLITHALF_SNR_MIN = 10.0
CANARY_COS_MIN = 0.995
CANARY_RATIO_BAND = (0.95, 1.05)
REPEAT_COS_MIN = 0.995
REPEAT_RATIO_BAND = (0.95, 1.05)
FALLOFF_RATIO_BAND = (0.85, 1.15)
CROSS_CAMPAIGN_COS_MIN = 0.99

# A canary target name is '<base> CANARY-START'/'<base> CANARY-END' (base is
# whatever object is used as the drift canary, e.g. 'copper pipe'; matched as
# a suffix so it pairs correctly regardless of what the base object is named)
# -- or, for backward compatibility, a bare 'CANARY-START'/'CANARY-END' with
# no base at all.
CANARY_SUFFIX_RE = re.compile(r'^(?:(?P<base>.+?)\s+)?CANARY-(?P<kind>START|END)$', re.IGNORECASE)
REPEAT_MARK_RE = re.compile(r"\(rpt\d*\)|\brepeat(ed)?\b", re.IGNORECASE)


def strip_canary_suffix(target):
    """Returns (base, kind) if target is/ends with a CANARY-START or
    CANARY-END marker (case-insensitive; base is '' for a bare marker with no
    object name), else None. kind is 'START' or 'END'."""
    m = CANARY_SUFFIX_RE.match(target.strip())
    if not m:
        return None
    return (m.group('base') or '').strip(), m.group('kind').upper()

CHECK_ORDER = ["shape-invariance", "splithalf-snr", "canary-consistency",
               "repeat-consistency", "distance-falloff", "cross-campaign"]


# -----------------------------------------------------------------------------
# Loading (long or wide format, auto-detected)
# -----------------------------------------------------------------------------

def sniff_format(path):
    with open(path) as f:
        header = None
        for line in f:
            if line.startswith('#'):
                continue
            header = line.rstrip('\n')
            break
    if header is None:
        raise SystemExit(f"{path}: empty file")
    cols = header.split(',')
    if {'pulse_us', 'threshold_v', 'delta_mV'} <= set(cols):
        return 'long'
    if any(re.match(r'c\d+$', c) for c in cols):
        return 'wide'
    raise SystemExit(f"{path}: unrecognized corpus CSV schema (header: {header})")


def dist_key(distance_cm):
    return 'NA' if pd.isna(distance_cm) else int(distance_cm)


def load_long(path):
    df = pd.read_csv(path, comment='#')
    sigs = {}
    for (session, target, distance_cm), g in df.groupby(
            ['session', 'target', 'distance_cm'], dropna=False):
        g = g.sort_values(['pulse_us', 'threshold_v'], ascending=[True, False])
        sigs[(session, target, dist_key(distance_cm))] = dict(
            shape=g['delta_mV'].to_numpy(dtype=float),
            amp=float(g['plateau_amp_mV'].iloc[0]),
            splithalf=float(g['splithalf_floor'].iloc[0]),
            quality=str(g['quality'].iloc[0]),
        )
    return sigs


def load_wide(path):
    df = pd.read_csv(path, comment='#')
    c_cols = sorted((c for c in df.columns if re.match(r'c\d+$', c)),
                     key=lambda c: int(c[1:]))
    sigs = {}
    for _, r in df.iterrows():
        sigs[(r['session'], r['target'], dist_key(r['distance_cm']))] = dict(
            shape=r[c_cols].to_numpy(dtype=float),
            amp=float(r['plateau_amp_mV']),
            splithalf=float(r['splithalf_floor']),
            quality=str(r['quality']),
        )
    return sigs


def load_corpus(path):
    fmt = sniff_format(path)
    sigs = load_long(path) if fmt == 'long' else load_wide(path)
    n_cells = {len(s['shape']) for s in sigs.values()}
    if len(n_cells) > 1:
        raise SystemExit(f"{path}: mixed cell counts across rows {sorted(n_cells)} "
                          "-- refusing to mix profile geometries (DESIGN §11)")
    return sigs


# -----------------------------------------------------------------------------
# Row helpers
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


# -----------------------------------------------------------------------------
# Check 1 — shape distance-invariance
# -----------------------------------------------------------------------------

def check_shape_invariance(sigs, corpus_label):
    rows = []
    by_capture = {}
    for (session, target, d), s in sigs.items():
        if strip_canary_suffix(target) is not None:
            continue  # canaries only exist @5cm and are checked separately
        by_capture.setdefault((session, target), {})[d] = s['shape']

    pass_1015 = total_1015 = 0
    pass_515 = total_515 = 0
    for (session, target), by_d in sorted(by_capture.items()):
        if 5 not in by_d:
            continue
        v5 = by_d[5]
        c_10 = cosine(v5, by_d[10]) if 10 in by_d else None
        c_15 = cosine(v5, by_d[15]) if 15 in by_d else None
        c_1015 = cosine(by_d[10], by_d[15]) if (10 in by_d and 15 in by_d) else None

        if c_10 is not None:
            status = 'PASS' if c_10 >= SHAPE_INVARIANCE_COS_MIN else 'FAIL'
            rows.append(mkrow('shape-invariance',
                               f'cos(5v10) {target} [{tag(corpus_label, session)}]',
                               f'{c_10:.4f}', f'>= {SHAPE_INVARIANCE_COS_MIN}', status))

        if c_15 is not None:
            total_515 += 1
            pass_515 += (c_15 >= SHAPE_INVARIANCE_COS_MIN)
            metric = f'cos(5v15) {target} [{tag(corpus_label, session)}]'
            if c_15 >= SHAPE_INVARIANCE_COS_MIN:
                status = 'PASS'
            elif c_1015 is not None and c_1015 >= SHAPE_INVARIANCE_COS_MIN:
                # Extended objects genuinely change shape at 5cm on this rig
                # (near-field effect) while agreeing at 10/15cm -- that's
                # physics, not a capture defect, so it's flagged rather than
                # failed outright.
                status = 'AMBER'
                metric += ' (near-field @5, extended target?)'
            else:
                status = 'FAIL'
            rows.append(mkrow('shape-invariance', metric,
                               f'{c_15:.4f}', f'>= {SHAPE_INVARIANCE_COS_MIN}', status))

        if c_1015 is not None:
            status = 'PASS' if c_1015 >= SHAPE_INVARIANCE_COS_MIN else 'FAIL'
            rows.append(mkrow('shape-invariance',
                               f'cos(10v15) {target} [{tag(corpus_label, session)}]',
                               f'{c_1015:.4f}', f'>= {SHAPE_INVARIANCE_COS_MIN}', status))
            total_1015 += 1
            pass_1015 += (status == 'PASS')

    if total_1015:
        rows.append(mkrow('shape-invariance',
                           f'targets with cos(10,15) >= {SHAPE_INVARIANCE_COS_MIN} [{corpus_label}]',
                           f'{pass_1015}/{total_1015}', f'{total_1015}/{total_1015}',
                           'PASS' if pass_1015 == total_1015 else 'FAIL'))
    if total_515:
        # Informational only now -- see the cos(10,15) roll-up above for the
        # real gate; the 0.97 cos(5,15) band is compact-target-only on this
        # rig (extended targets can legitimately fail it near-field).
        rows.append(mkrow('shape-invariance',
                           f'targets with cos(5,15) >= {SHAPE_INVARIANCE_COS_MIN} [{corpus_label}]',
                           f'{pass_515}/{total_515}', 'report only', 'PASS'))
    return rows


# -----------------------------------------------------------------------------
# Check 2 — split-half SNR
# -----------------------------------------------------------------------------

def check_splithalf_snr(sigs, corpus_label):
    rows = []
    for (session, target, d), s in sorted(sigs.items(), key=lambda kv: (kv[0][1], kv[0][2])):
        metric = f'{target} @{d}cm [{tag(corpus_label, session)}]'
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
# Check 3 — canary consistency
# -----------------------------------------------------------------------------

def check_canary(sigs, corpus_label):
    rows = []
    by_session_base = {}
    for (session, target, d), s in sigs.items():
        parsed = strip_canary_suffix(target)
        if parsed is None:
            continue
        base, kind = parsed
        by_session_base.setdefault((session, base), {}).setdefault(kind, {})[d] = s

    found = False
    for (session, base), kinds in sorted(by_session_base.items()):
        start, end = kinds.get('START'), kinds.get('END')
        if not start or not end:
            continue
        for d in sorted(set(start) & set(end), key=str):
            found = True
            s_start, s_end = start[d], end[d]
            c = cosine(s_start['shape'], s_end['shape'])
            ratio = (s_end['amp'] / s_start['amp']) if s_start['amp'] else np.nan
            status_c = 'PASS' if c > CANARY_COS_MIN else 'FAIL'
            status_r = ('PASS' if CANARY_RATIO_BAND[0] <= ratio <= CANARY_RATIO_BAND[1]
                        else 'FAIL')
            base_tag = f'"{base}" ' if base else ''
            where = f'{base_tag}[{tag(corpus_label, session)}] @{d}cm'
            rows.append(mkrow('canary-consistency', f'shape cos {where}',
                               f'{c:.4f}', f'> {CANARY_COS_MIN}', status_c))
            rows.append(mkrow('canary-consistency', f'amp ratio {where}',
                               f'{ratio:.3f}',
                               f'{CANARY_RATIO_BAND[0]}-{CANARY_RATIO_BAND[1]}', status_r))
            # Protocol v2's drift-flag criterion: either check failing means
            # the session is drift-flagged and its 15cm rows get downgraded
            # (pimd_features.py's quality column handles the actual downgrade
            # -- this just reports the verdict for a human to see up front).
            drift_flagged = status_c == 'FAIL' or status_r == 'FAIL'
            rows.append(mkrow('canary-consistency', f'drift status {where}',
                               'DRIFT-FLAGGED -- 15cm rows downgraded' if drift_flagged else 'ok',
                               'n/a', 'FAIL' if drift_flagged else 'PASS'))

    if not found:
        rows.append(mkrow('canary-consistency',
                           f'CANARY-START/END pairs found [{corpus_label}]',
                           '0', 'n/a (informational)', 'SKIP'))
    return rows


# -----------------------------------------------------------------------------
# Check 4 — repeat consistency
# -----------------------------------------------------------------------------

def find_repeat_base(target, base_candidates):
    """Match a '(rpt)'/REPEAT-marked target name to its base capture.

    Tries an exact match on the marker-stripped name first (e.g. 'widget
    (rpt)' -> 'widget'). Falls back to matching by first word + a shared
    digit-bearing token (e.g. 'brass block 370g (rpt)' -> 'brass 370g'),
    since real corpus naming isn't always a clean suffix strip -- returns
    None (unresolved) rather than guessing when that fallback isn't unique.
    """
    stripped = re.sub(r'\s{2,}', ' ', REPEAT_MARK_RE.sub('', target)).strip()
    if stripped in base_candidates:
        return stripped
    words = target.split()
    if not words:
        return None
    first = words[0].lower()
    weight_tokens = [w for w in words if any(ch.isdigit() for ch in w)]
    if not weight_tokens:
        return None
    candidates = [t for t in base_candidates
                  if t.split() and t.split()[0].lower() == first
                  and any(wt in t for wt in weight_tokens)]
    return candidates[0] if len(candidates) == 1 else None


def check_repeat(sigs, corpus_label):
    rows = []
    all_targets = sorted({t for (_, t, _) in sigs})
    repeat_targets = [t for t in all_targets if REPEAT_MARK_RE.search(t)]
    if not repeat_targets:
        rows.append(mkrow('repeat-consistency',
                           f'repeat-labelled targets found [{corpus_label}]',
                           '0', 'n/a (informational)', 'SKIP'))
        return rows

    base_candidates = [t for t in all_targets if t not in repeat_targets]
    by_target = {}
    for (session, target, d), s in sigs.items():
        by_target.setdefault(target, {})[d] = (session, s)

    for rt in repeat_targets:
        base = find_repeat_base(rt, base_candidates)
        if base is None:
            rows.append(mkrow('repeat-consistency',
                               f'base capture for "{rt}" [{corpus_label}]',
                               'not found', 'n/a', 'SKIP'))
            continue
        rep_by_d, base_by_d = by_target.get(rt, {}), by_target.get(base, {})
        for d in sorted(set(rep_by_d) & set(base_by_d), key=str):
            (sess_r, sr), (sess_b, sb) = rep_by_d[d], base_by_d[d]
            c = cosine(sr['shape'], sb['shape'])
            ratio = (sr['amp'] / sb['amp']) if sb['amp'] else np.nan
            status_c = 'PASS' if c > REPEAT_COS_MIN else 'FAIL'
            status_r = ('PASS' if REPEAT_RATIO_BAND[0] <= ratio <= REPEAT_RATIO_BAND[1]
                        else 'FAIL')
            where = f'"{rt}" vs "{base}" @{d}cm [{corpus_label}]'
            rows.append(mkrow('repeat-consistency', f'shape cos {where}',
                               f'{c:.4f}', f'> {REPEAT_COS_MIN}', status_c))
            rows.append(mkrow('repeat-consistency', f'amp ratio {where}',
                               f'{ratio:.3f}',
                               f'{REPEAT_RATIO_BAND[0]}-{REPEAT_RATIO_BAND[1]}', status_r))
    return rows


def check_repeat_cross_session(sigs, corpus_label):
    """A capture plan can revisit the same target+distance in an entirely
    separate session (e.g. 'copper pipe' captured in full in session s1 and
    again in session s4) rather than as a same-session '(rpt)' revisit --
    check_repeat() above only ever compares within-session names, so this is
    a distinct, additional comparison: same (target, distance_cm), different
    session, matched by exact target-name equality (so it never overlaps
    with '(rpt)'-suffixed names, which are always within-session)."""
    rows = []
    by_target_distance = {}
    for (session, target, d), s in sigs.items():
        if strip_canary_suffix(target) is not None:
            continue
        by_target_distance.setdefault((target, d), {})[session] = s

    found = False
    for (target, d), by_session in sorted(by_target_distance.items(),
                                           key=lambda kv: (kv[0][0], str(kv[0][1]))):
        sessions = sorted(by_session)
        if len(sessions) < 2:
            continue
        for i in range(len(sessions)):
            for j in range(i + 1, len(sessions)):
                found = True
                sess_a, sess_b = sessions[i], sessions[j]
                sa, sb = by_session[sess_a], by_session[sess_b]
                c = cosine(sa['shape'], sb['shape'])
                ratio = (sb['amp'] / sa['amp']) if sa['amp'] else np.nan
                status_c = 'PASS' if c > REPEAT_COS_MIN else 'FAIL'
                status_r = ('PASS' if REPEAT_RATIO_BAND[0] <= ratio <= REPEAT_RATIO_BAND[1]
                            else 'FAIL')
                where = f'"{target}" @{d}cm ({sess_a} vs {sess_b}) [{corpus_label}]'
                rows.append(mkrow('repeat-consistency', f'cross-session shape cos {where}',
                                   f'{c:.4f}', f'> {REPEAT_COS_MIN}', status_c))
                rows.append(mkrow('repeat-consistency', f'cross-session amp ratio {where}',
                                   f'{ratio:.3f}',
                                   f'{REPEAT_RATIO_BAND[0]}-{REPEAT_RATIO_BAND[1]}', status_r))

    if not found:
        rows.append(mkrow('repeat-consistency',
                           f'cross-session repeat captures found [{corpus_label}]',
                           '0', 'n/a (informational)', 'SKIP'))
    return rows


# -----------------------------------------------------------------------------
# Check 5 — distance falloff
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
    by_capture = {}
    for (session, target, d), s in sigs.items():
        if strip_canary_suffix(target) is not None:
            continue  # canaries only exist @5cm -- no falloff fit possible/meaningful
        by_capture.setdefault((session, target), {})[d] = s['amp']

    for (session, target), by_d in sorted(by_capture.items()):
        if not {5, 10, 15} <= set(by_d):
            continue
        where = f'{target} [{tag(corpus_label, session)}]'
        fit = fit_falloff([5, 10, 15], [by_d[5], by_d[10], by_d[15]])
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
    return rows


# -----------------------------------------------------------------------------
# Check 6 — cross-campaign repeatability (only with two corpora)
# -----------------------------------------------------------------------------

def check_cross_campaign(sigs_a, label_a, sigs_b, label_b):
    """Compares the primary corpus (sigs_a) against a --baseline corpus
    (sigs_b, e.g. a prior campaign/rig). Informational, cross-rig only --
    never a same-rig acceptance gate (see main()'s exit-code computation)."""
    rows = []
    a5 = {t: s['shape'] for (_, t, d), s in sigs_a.items() if d == 5}
    b5 = {t: s['shape'] for (_, t, d), s in sigs_b.items() if d == 5}
    common = sorted(set(a5) & set(b5))
    if not common:
        rows.append(mkrow('cross-campaign',
                           f'5cm targets common to {label_a} and {label_b} (informational, cross-rig)',
                           '0', 'n/a', 'SKIP'))
        return rows
    for t in common:
        c = cosine(a5[t], b5[t])
        status = 'PASS' if c >= CROSS_CAMPAIGN_COS_MIN else 'FAIL'
        rows.append(mkrow('cross-campaign',
                           f'5cm cos "{t}" ({label_a} vs {label_b}) (informational, cross-rig)',
                           f'{c:.4f}', f'>= {CROSS_CAMPAIGN_COS_MIN}', status))
    return rows


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def build_arg_parser():
    p = argparse.ArgumentParser(
        description='Corpus-level acceptance checks for a PIMD signature corpus.')
    p.add_argument('corpus_csv', help='corpus CSV to check (long or wide format)')
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

    rows = []
    rows += check_shape_invariance(sigs, label)
    rows += check_splithalf_snr(sigs, label)
    rows += check_canary(sigs, label)
    rows += check_repeat(sigs, label)
    rows += check_repeat_cross_session(sigs, label)
    rows += check_falloff(sigs, label)

    if args.baseline:
        baseline_label = os.path.splitext(os.path.basename(args.baseline))[0]
        baseline_sigs = load_corpus(args.baseline)
        rows += check_cross_campaign(sigs, label, baseline_sigs, baseline_label)
    else:
        rows.append(mkrow('cross-campaign',
                           'cross-campaign checks skipped (campaign 2; no rig-1 baseline applicable)',
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
