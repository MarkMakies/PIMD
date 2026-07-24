#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2022-2026 Mark Makies
###############################################################################
# PIMD Signature Shape Features (pimd_shape.py) v1
# — shared signature-geometry maths: the small set of scalar features that
#   summarise a baseline-corrected delta_mV signature (family quadrant,
#   zero-crossing pulse width, decay persistence, amplitude, SNR).
# Runs on Ubuntu desktop / laptop, pure NumPy + stdlib CLI (no GUI, no Qt).
#
# Deliberately standalone: pimd_classviz.py's Shape Space tab imports it for
# live/plotted features, and a future classifier will import the same
# functions for its feature vector, so nothing here may pull in Qt or
# pyqtgraph, and nothing may be hard-coded to the 63-cell operating profile.
# Every function takes its geometry explicitly.
#
# Vector convention (matches the corpus row sort used by pimd_features.py,
# pimd_corpus_check.load_corpus() and pimd_classviz._scan_editable_signature_
# file(), so a stored capture and a live frame are directly comparable):
#
#   vec  1-D, length n_bands * n_delays, BAND-MAJOR
#        bands   ordered by pulse width ASCENDING   (9 -> 100 us)
#        delays  ordered by threshold voltage DESCENDING (4.9 -> 0.5 V),
#                i.e. earliest/highest point on the decay first
#        values  baseline-corrected delta_mV (mV), sign per DESIGN §2:
#                ferrous positive, non-ferrous negative
#   pulses_us    list, len n_bands, ascending, microseconds
#
# The two crossing sentinels are values, not error codes -- they are chosen to
# plot sensibly on a log pulse-width axis just outside the profile's real
# range, so "already positive at the shortest pulse" and "never crosses" each
# land on their own rail rather than being dropped from a plot.
#
# History (full detail in CHANGELOG.md):
#   v1 initial version: family/crossing/decay-persistence features + --selftest
###############################################################################

import argparse
import csv
import sys

import numpy as np

TOOL_VERSION = 'pimd_shape.py v1'

# Crossing-width sentinels, microseconds. Both sit just outside the operating
# profile's 9-100 us ladder so they render as distinct rails on a log axis.
CROSS_ALREADY_POS = 8.0     # band 0's mean is already positive -- crossed before the ladder starts
CROSS_NEVER       = 200.0   # no negative->positive transition anywhere on the ladder

# Default amplitude/noise ratio below which a shape is not worth interpreting.
# 5.0 is the reciprocal of pimd_features.NOISY_RATIO_THRESHOLD (0.20), the
# ratio that stamps a capture 'noisy' -- same line, read as an SNR.
DEFAULT_SNR_GATE = 5.0

FAMILIES = ('ferrous', 'non_ferrous', 'crossover')
LOW_SNR = 'low_snr'


# ---------------------------------------------------------------------------
# Basic shape helpers
# ---------------------------------------------------------------------------

def amp_l2(vec):
    """||vec||_2 in mV -- the corpus's plateau_amp_mV convention (see
    pimd_features.compute_plateau_stats, which is explicit that this column
    must stay L2 for cross-campaign comparability)."""
    return float(np.linalg.norm(np.asarray(vec, dtype=float)))


def unit_shape(vec):
    """vec / ||vec||_2 -- the amplitude-invariant shape. A target's family and
    crossing width must not depend on how close it was held, so every
    sign-based feature below is taken on this. Zero-safe: an all-zero vector
    is returned unchanged rather than producing NaNs."""
    vec = np.asarray(vec, dtype=float)
    norm = np.linalg.norm(vec)
    return vec / norm if norm > 0 else vec.copy()


def snr(amp, noise):
    """Amplitude-to-noise ratio. `noise` is the corpus's splithalf_floor (or,
    for a live frame, the same split-half statistic computed over the settle
    window) so one gate value means the same thing for stored and live
    shapes. inf when the noise floor is effectively zero."""
    amp, noise = float(amp), float(noise)
    return amp / noise if noise > 1e-9 else float('inf')


def _as_matrix(vec, n_bands, n_delays):
    """(n_bands, n_delays) view, with a loud shape check -- a silent reshape
    of a mismatched vector would produce plausible-looking nonsense."""
    vec = np.asarray(vec, dtype=float)
    if vec.size != n_bands * n_delays:
        raise ValueError(
            'vector has {0} cells, geometry says {1} bands x {2} delays = {3}'.format(
                vec.size, n_bands, n_delays, n_bands * n_delays))
    return vec.reshape(n_bands, n_delays)


def band_means(vec, n_bands, n_delays):
    """Mean delta_mV per band -- the response profile along the pulse-width
    axis, shape (n_bands,). This is the curve crossing_us() interpolates."""
    return _as_matrix(vec, n_bands, n_delays).mean(axis=1)


def band_range_mean(u, band_lo, band_hi, n_bands, n_delays):
    """Mean of `u` over an inclusive band range. Feed it a unit_shape() so the
    result is amplitude-invariant -- this one function backs the 'early',
    'mid', 'late' and custom-range axes alike, the only difference being
    which band indices are passed."""
    if not 0 <= band_lo <= band_hi < n_bands:
        raise ValueError('band range {0}..{1} outside 0..{2}'.format(
            band_lo, band_hi, n_bands - 1))
    return float(_as_matrix(u, n_bands, n_delays)[band_lo:band_hi + 1].mean())


def default_band_ranges(n_bands):
    """(early, mid, late) inclusive (lo, hi) band-index pairs for a profile of
    `n_bands` bands: outer thirds early/late, everything between is mid.

    For the 7-band operating profile (cal_63_air_v2) this gives exactly the
    ranges the 2026-07-23 corpus analysis used -- early 0-1 (9, 13.44 us),
    mid 2-4 (20, 30, 45 us), late 5-6 (67.2, 100 us). Derived rather than
    hard-coded so a re-banded profile still gets a sane split."""
    if n_bands < 2:
        raise ValueError('need at least 2 bands, got {0}'.format(n_bands))
    n_outer = max(1, n_bands // 3)
    if 2 * n_outer >= n_bands:          # too few bands for a distinct middle
        n_outer = max(1, (n_bands - 1) // 2)
    early = (0, n_outer - 1)
    late  = (n_bands - n_outer, n_bands - 1)
    mid   = (early[1] + 1, late[0] - 1) if late[0] - 1 >= early[1] + 1 else early
    return early, mid, late


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

def crossing_us(vec, pulses_us, n_delays):
    """Pulse width (us) at which the band-mean profile crosses from negative
    to positive -- the crossover target's signature coordinate (DESIGN §17.6:
    eddy response dominates at short pulses, magnetic response at long, and
    where that swap happens orders the crossover family).

    Log-linear interpolation between the two bracketing bands: the pulse
    ladder is geometric (x1.5, DESIGN §10), so equal information sits in equal
    log-width steps and interpolating in log space is the natural reading.

    The FIRST negative->positive transition wins -- a noisy late band that dips
    back through zero must not move the reported crossing.

    Returns CROSS_ALREADY_POS when band 0's mean is already positive (a solid
    ferrous target: it never crosses inside the ladder because it started
    positive), CROSS_NEVER when no transition occurs (non-ferrous)."""
    pulses_us = [float(p) for p in pulses_us]
    n_bands = len(pulses_us)
    means = band_means(vec, n_bands, n_delays)
    if means[0] > 0:
        return CROSS_ALREADY_POS
    for i in range(n_bands - 1):
        y0, y1 = means[i], means[i + 1]
        if y0 <= 0 < y1:
            x0, x1 = np.log(pulses_us[i]), np.log(pulses_us[i + 1])
            frac = -y0 / (y1 - y0)
            return float(np.exp(x0 + frac * (x1 - x0)))
    return CROSS_NEVER


def decay_persistence(vec, n_bands, n_delays):
    """mean(|delta|) over the two LOWEST-voltage threshold columns divided by
    mean(|delta|) over the two HIGHEST, across all bands.

    Reads the threshold axis rather than the pulse axis: DESIGN §17.6 found
    ferrous perturbation stays flat late into the decay while non-ferrous
    concentrates early and falls away. So this ratio is large for
    iron-bearing targets and small for non-ferrous ones -- an independent
    second opinion on family that does not use sign at all, which is exactly
    what separates a ferrite (positive signs, non-ferrous-like decay) from
    real iron.

    Column 0 is the highest threshold voltage by the module's vector
    convention, so 'lowest two' are the last two columns."""
    mag = np.abs(_as_matrix(vec, n_bands, n_delays))
    if n_delays < 4:
        raise ValueError('need at least 4 delay columns, got {0}'.format(n_delays))
    early = float(mag[:, :2].mean())     # highest thresholds -- top of the decay
    late  = float(mag[:, -2:].mean())    # lowest thresholds -- tail of the decay
    return late / early if early > 1e-12 else float('inf')


def family(vec, n_bands, n_delays, early=None, late=None):
    """'ferrous' | 'non_ferrous' | 'crossover' from the signs of the early and
    late band-range means of the unit shape (DESIGN §2 polarity convention:
    ferrous positive, non-ferrous negative).

      early < 0 and late > 0  -> crossover  (sign flips along the pulse ladder)
      late  < 0               -> non_ferrous
      otherwise               -> ferrous

    Note this is a SIGN verdict only. A ferrite toroid reads 'ferrous' here
    while its decay_persistence() reads non-ferrous -- both are true of it,
    and callers displaying family should show the decay reading alongside
    rather than picking a winner.

    `early`/`late` are inclusive (lo, hi) band-index pairs; they default to
    default_band_ranges(n_bands)."""
    if early is None or late is None:
        d_early, _, d_late = default_band_ranges(n_bands)
        early = early if early is not None else d_early
        late  = late  if late  is not None else d_late
    u = unit_shape(vec)
    early_mean = band_range_mean(u, early[0], early[1], n_bands, n_delays)
    late_mean  = band_range_mean(u, late[0],  late[1],  n_bands, n_delays)
    if early_mean < 0 and late_mean > 0:
        return 'crossover'
    if late_mean < 0:
        return 'non_ferrous'
    return 'ferrous'


def family_gated(vec, amp, noise, n_bands, n_delays, gate=DEFAULT_SNR_GATE,
                 early=None, late=None):
    """family(), but returns LOW_SNR when amp/noise is below `gate`.

    Below the gate the unit shape is normalised noise: it has a family
    verdict, that verdict is stable-looking, and it means nothing. Callers
    should treat LOW_SNR as 'no answer', not as a fourth class."""
    return (family(vec, n_bands, n_delays, early=early, late=late)
            if snr(amp, noise) >= gate else LOW_SNR)


# ---------------------------------------------------------------------------
# Corpus loading (selftest + offline callers; the GUI has its own reader)
# ---------------------------------------------------------------------------

def load_corpus_captures(path):
    """Reads a v1.32+ gui_signatures_*.csv (pimd_features.CORPUS_HEADER
    schema) into one dict per capture, keyed (session, capture_id).

    Same regrouping and row sort as pimd_corpus_check.load_corpus() and
    pimd_classviz._scan_editable_signature_file() -- sort each capture's cell
    rows by pulse_us ascending then threshold_v descending -- which is what
    puts `vec` in this module's convention.

    Geometry is DERIVED from the file (distinct pulse_us values -> n_bands,
    rows/n_bands -> n_delays) rather than assumed, so a corpus captured under
    a different profile still loads correctly.

    Returns dict[(session, capture_id)] -> dict with vec, pulses_us, n_bands,
    n_delays, target_id, short_name, distance_mm, amp, splithalf, quality."""
    groups, order = {}, []
    with open(path, newline='') as f:
        reader = csv.DictReader(line for line in f if not line.startswith('#'))
        if reader.fieldnames is None:
            raise ValueError('{0}: empty file'.format(path))
        missing = {'session', 'capture_id', 'target_id', 'distance_mm', 'pulse_us',
                   'threshold_v', 'delta_mV'} - set(reader.fieldnames)
        if missing:
            raise ValueError('{0}: not a v1.32+ signature corpus -- missing columns '
                              '{1}'.format(path, sorted(missing)))
        for row in reader:
            key = (row['session'], row['capture_id'])
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(row)

    caps = {}
    for key in order:
        rows = sorted(groups[key],
                      key=lambda r: (float(r['pulse_us']), -float(r['threshold_v'])))
        pulses_us = sorted({float(r['pulse_us']) for r in rows})
        n_bands = len(pulses_us)
        if n_bands == 0 or len(rows) % n_bands:
            raise ValueError("{0}: capture '{1}' has {2} cells over {3} bands -- not a "
                              'rectangular profile geometry'.format(
                                  path, key[1], len(rows), n_bands))
        first = rows[0]
        caps[key] = dict(
            session=key[0], capture_id=key[1],
            vec=np.array([float(r['delta_mV']) for r in rows], dtype=float),
            pulses_us=pulses_us, n_bands=n_bands, n_delays=len(rows) // n_bands,
            target_id=first['target_id'], short_name=first.get('short_name', ''),
            distance_mm=first['distance_mm'],
            amp=float(first['plateau_amp_mV']), splithalf=float(first['splithalf_floor']),
            quality=first['quality'],
        )
    return caps


# ---------------------------------------------------------------------------
# Selftest -- the CC_BRIEF_shape_space.md acceptance items 1-4, run against a
# corpus CSV. These are measured properties of the 2026-07-23 targets_v1
# corpus, so this doubles as a regression gate on the maths above.
# ---------------------------------------------------------------------------

# (target_id, distance_mm) -> expected crossing us, +/- CROSS_TOL_US.
_EXPECT_CROSSING = {
    ('Fe_Cast_iron_trivet_01', '60'):  34.3,
    ('Fe_Cast_iron_trivet_01', '120'): 33.9,
    ('Fe_SS_disc_01', '60'):           30.6,
    ('Fe_SS_disc_01', '120'):          26.4,
    ('Fe_SS_disc_01', '180'):          30.9,
    ('Fe_Zn_gal_rhs_01', '60'):        21.4,
    ('Fe_Zn_gal_rhs_01', '120'):       20.8,
    ('Fe_Zn_gal_rhs_01', '180'):       23.4,
    ('Fe_Zn_gal_pipe_01', '60'):       14.9,
    ('Fe_Zn_gal_pipe_01', '120'):      16.6,
    ('Fe_Zn_gal_pipe_01', '180'):      21.1,
    ('Fe_SS_shackle_01', '60'):        14.6,
}
CROSS_TOL_US = 1.5

# Family verdict is a sign test, so a ferrite toroid lands in 'ferrous' while
# its decay ratio says otherwise -- exempt it from the decay band checks and
# assert the split explicitly instead (brief item 4).
_FERRITE_ID = 'ferrite_toroid_01'
_DECAY_FERROUS_MIN     = 2.4
_DECAY_NON_FERROUS_MAX = 1.8
_FERRITE_DECAY_MAX     = 1.8


def _selftest(path, gate=DEFAULT_SNR_GATE, verbose=False):
    """Returns a list of failure strings -- empty means everything passed."""
    caps = load_corpus_captures(path)
    fails = []

    def check(ok, msg):
        if not ok:
            fails.append(msg)

    # -- item 1: point count and gate split ---------------------------------
    gated = {}
    for key, c in caps.items():
        c['snr'] = snr(c['amp'], c['splithalf'])
        if c['snr'] >= gate:
            gated[key] = c
    print('1. captures={0}  gated={1}  below-gate={2}'.format(
        len(caps), len(gated), len(caps) - len(gated)))
    check(len(caps) == 66, 'item 1: expected 66 captures, got {0}'.format(len(caps)))
    check(len(gated) == 46, 'item 1: expected 46 gated at SNR>={0}, got {1}'.format(
        gate, len(gated)))
    check(len(caps) - len(gated) == 20, 'item 1: expected 20 below gate, got {0}'.format(
        len(caps) - len(gated)))

    # -- item 2: family quadrant counts -------------------------------------
    counts = {f: 0 for f in FAMILIES}
    for c in gated.values():
        c['family'] = family(c['vec'], c['n_bands'], c['n_delays'])
        counts[c['family']] += 1
    print('2. families (gated): non_ferrous={non_ferrous}  crossover={crossover}  '
          'ferrous={ferrous}'.format(**counts))
    for fam, want in (('non_ferrous', 26), ('crossover', 12), ('ferrous', 8)):
        check(counts[fam] == want,
              'item 2: expected {0} {1}, got {2}'.format(want, fam, counts[fam]))

    # -- item 3: crossing widths --------------------------------------------
    seen_expect = set()
    earliest = (None, float('inf'))
    for c in gated.values():
        c['crossing_us'] = crossing_us(c['vec'], c['pulses_us'], c['n_delays'])
        ident = (c['target_id'], c['distance_mm'])
        want = _EXPECT_CROSSING.get(ident)
        if want is not None:
            seen_expect.add(ident)
            check(abs(c['crossing_us'] - want) <= CROSS_TOL_US,
                  'item 3: {0} @{1} crossing {2:.2f} us, expected {3} +/-{4}'.format(
                      ident[0], ident[1], c['crossing_us'], want, CROSS_TOL_US))
        if c['family'] == 'crossover' and c['crossing_us'] < earliest[1]:
            earliest = (ident, c['crossing_us'])
        if c['family'] == 'ferrous':
            check(c['crossing_us'] <= 11.0,
                  'item 3: gated ferrous {0} @{1} crossing {2:.2f} us, expected <= 11'.format(
                      ident[0], ident[1], c['crossing_us']))
        if c['family'] == 'non_ferrous':
            check(c['crossing_us'] == CROSS_NEVER,
                  'item 3: gated non-ferrous {0} @{1} crossing {2:.2f}, expected '
                  'CROSS_NEVER'.format(ident[0], ident[1], c['crossing_us']))
        if c['target_id'] == _FERRITE_ID:
            check(c['crossing_us'] == CROSS_ALREADY_POS,
                  'item 3: ferrite @{0} crossing {1:.2f}, expected '
                  'CROSS_ALREADY_POS'.format(ident[1], c['crossing_us']))
    missing = sorted(set(_EXPECT_CROSSING) - seen_expect)
    check(not missing, 'item 3: expected captures absent from the gated set: {0}'.format(missing))
    check(earliest[0] == ('Fe_SS_shackle_01', '60'),
          'item 3: earliest crossover should be Fe_SS_shackle_01 @60, got {0} at '
          '{1:.2f} us'.format(earliest[0], earliest[1]))
    print('3. crossing widths: {0} expected captures checked, earliest crossover '
          '{1} @{2} = {3:.2f} us'.format(
              len(seen_expect), earliest[0][0], earliest[0][1], earliest[1]))

    # -- item 4: decay persistence ------------------------------------------
    fer_min, non_max, ferrite_dp = float('inf'), 0.0, None
    for c in gated.values():
        c['decay'] = decay_persistence(c['vec'], c['n_bands'], c['n_delays'])
        if c['target_id'] == _FERRITE_ID:
            ferrite_dp = c['decay']
            check(c['decay'] < _FERRITE_DECAY_MAX,
                  'item 4: ferrite decay {0:.2f}, expected < {1} (sign says ferrous, '
                  'decay must not)'.format(c['decay'], _FERRITE_DECAY_MAX))
            continue
        if c['family'] in ('ferrous', 'crossover'):
            fer_min = min(fer_min, c['decay'])
            check(c['decay'] > _DECAY_FERROUS_MIN,
                  'item 4: {0} @{1} ({2}) decay {3:.2f}, expected > {4}'.format(
                      c['target_id'], c['distance_mm'], c['family'], c['decay'],
                      _DECAY_FERROUS_MIN))
        else:
            non_max = max(non_max, c['decay'])
            check(c['decay'] < _DECAY_NON_FERROUS_MAX,
                  'item 4: {0} @{1} (non_ferrous) decay {2:.2f}, expected < {3}'.format(
                      c['target_id'], c['distance_mm'], c['decay'], _DECAY_NON_FERROUS_MAX))
    check(ferrite_dp is not None, 'item 4: no gated ferrite capture found')
    print('4. decay persistence: ferrous/crossover min={0:.2f} (>{1})  non-ferrous '
          'max={2:.2f} (<{3})  ferrite={4}'.format(
              fer_min, _DECAY_FERROUS_MIN, non_max, _DECAY_NON_FERROUS_MAX,
              '{0:.2f}'.format(ferrite_dp) if ferrite_dp is not None else 'n/a'))

    if verbose:
        print('\n{0:28s} {1:>6s}  {2:12s} {3:>9s} {4:>7s} {5:>8s}'.format(
            'target', 'dist', 'family', 'crossing', 'decay', 'snr'))
        for c in sorted(gated.values(), key=lambda c: (c['target_id'], c['distance_mm'])):
            print('{0:28s} {1:>6s}  {2:12s} {3:9.2f} {4:7.2f} {5:8.1f}'.format(
                c['target_id'], c['distance_mm'] or 'air', c['family'],
                c['crossing_us'], c['decay'], c['snr']))
    return fails


def main(argv=None):
    p = argparse.ArgumentParser(
        description='PIMD signature shape features ({0}). With --selftest, '
                    'checks the feature maths against a known corpus.'.format(TOOL_VERSION))
    p.add_argument('--selftest', metavar='CORPUS_CSV',
                   help='run the CC_BRIEF_shape_space acceptance checks 1-4 against this '
                        'gui_signatures_*.csv corpus')
    p.add_argument('--gate', type=float, default=DEFAULT_SNR_GATE,
                   help='SNR gate for the selftest (default: %(default)s)')
    p.add_argument('--verbose', action='store_true',
                   help='print the full per-capture feature table')
    args = p.parse_args(argv)

    if not args.selftest:
        p.error('nothing to do -- pass --selftest <corpus csv>')

    print('{0} selftest: {1}'.format(TOOL_VERSION, args.selftest))
    fails = _selftest(args.selftest, gate=args.gate, verbose=args.verbose)
    if fails:
        print('\nFAIL ({0} problem(s)):'.format(len(fails)))
        for f in fails:
            print('  - ' + f)
        return 1
    print('\nPASS — acceptance items 1-4')
    return 0


if __name__ == '__main__':
    sys.exit(main())
