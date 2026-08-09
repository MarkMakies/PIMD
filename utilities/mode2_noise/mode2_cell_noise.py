#!/usr/bin/env python3
"""Recover per-cell single-sample noise from a Mode 2 session dump.
TOOL_VERSION = v1.01

Offline. Reads a `pimd_classviz` session CSV (or `pimd_gui` dump in the same
format) and scores each channel for the two failure modes that look identical
on delaycal's live "Std dev" table but have different causes:

  * an index-locked SINGLE-SAMPLE outlier population (a discrete, level-
    independent excursion that hits one sweep position), and
  * a band-boundary SETTLING gradient (a smooth excess decaying across the
    first few cells of a band).

Read-only. Writes nothing.

# History (full detail in CHANGELOG.md):
#   v1.01 absolute-excursion column -- the relative gate is not comparable between runs
#   v1 initial -- boxcar deconvolution, matched-pair outlier detection,
#      equivalent-timing-jitter column, band-boundary gradient report

Why the numbers here are recoverable at all
-------------------------------------------
Mode 2 does NOT emit samples.  Each W record carries, per cell, a rolling mean
`averages` deep (DESIGN Sec 9), and the firmware adds exactly ONE new sample per
cell per sweep (`acquire_mode2`: `rolling_sum[prev] += raw - rolling[prev][idx]`).
So for a channel's emitted mean series m[]:

    m[i] - m[i-1] = ( x[i] - x[i-N] ) / N          N = averages

which recovers the single-sample series x[] up to one unknown constant per
residue class i mod N.  Two consequences this tool leans on:

1. **A single outlier sample is a MATCHED PAIR.**  x[k] entering the window
   steps the mean by +d, and leaving it exactly N frames later steps it by -d.
   Detecting `|m[i]-m[i-1]| > k*sigma` AND `m[i+N]-m[i-1+N] ~= -(m[i]-m[i-1])`
   needs no detrending and cannot be manufactured by drift, by the per-class
   constants, or by the reconstruction itself.  This is the primary statistic.
2. **Robust per-sample sigma** is `1.4826 * MAD(diff(m)) * N / sqrt(2)`, using
   the median absolute deviation so the outlier population does not inflate the
   estimate of the population it is being compared against.

Both need CONSECUTIVE frames.  Any host-side frame drop breaks the N-frame
pairing, so the tool checks the firmware clock for gaps and says so.

The event rate is a slight UNDER-count, by construction: two outliers landing
within N frames of each other spoil the +d/-d cancellation and neither is
counted.  Measured against synthetic data with a known planted rate, recovery
is ~85 % at a 5-6 % event rate (52.2 planted -> 44.5 reported per 1000).  The
bias is a function of the rate itself, so it is consistent between runs at
similar rates and does not affect A/B comparisons; treat the absolute number
as a floor rather than an estimate.

Equivalent timing jitter
------------------------
A cell's sigma is only interpretable against its own local decay slope: the same
5 ns of jitter is 6 mV on a steep cell and 0.4 mV on a flat one.  The tool
divides each cell's sigma by dV/dt estimated from its neighbouring cells'
(delay, mean) pairs and reports nanoseconds.  On a healthy band this column is
FLAT at the DESIGN Sec 8 timing precision (~5 ns).  A cell that stands out in
mV but not in ns is on a steep slope and is behaving normally; a cell that
stands out in ns is not.

Usage
-----
    python utilities/mode2_noise/mode2_cell_noise.py <session.csv> [more.csv ...]
    python utilities/mode2_noise/mode2_cell_noise.py --hist 0 <session.csv>

`--hist <ch>` adds the excursion-size histogram for one channel, which is what
separates a discrete two-state mechanism from a heavy Gaussian tail.
"""

import argparse
import json
import sys

import numpy as np

TOOL_VERSION = '1.01'

# A step is a candidate outlier at this many robust sigmas of the step series.
# WITHIN one run this finds the anomalous cell. BETWEEN runs it is NOT
# comparable: the gate moves with the run's own sigma, so halving a channel's
# noise makes smaller events start crossing it and the count can RISE while
# everything else improves. That is not hypothetical -- it happened on the
# v4.33 -> v4.34 A/B (ch0 62.5 -> 76.5 per 1000 while sigma halved and the
# median excursion fell 132 -> 60 mV). Use the absolute column for A/B.
STEP_SIGMA = 4.0
# Absolute excursion gate, mV, for cross-run comparison. A single sample this
# far out steps an N-deep boxcar by ABS_GATE_MV/N, which is what is detected.
ABS_GATE_MV = 100.0
# ...and is confirmed only if the partner step N frames later cancels it to
# within this fraction.  0.3 is loose enough to survive a second sample landing
# in the window, tight enough that ordinary noise does not pair up by chance.
PAIR_TOL = 0.3
# Below this the channel is at the raw path's quantisation floor (1 LSB =
# 10 V / 2**14 = 610 uV) and no sigma is meaningful.
QUANT_MV = 10_000.0 / 2 ** 14
# Cells flatter than this carry no timing information: dividing sigma by a
# near-zero slope reports thousands of nanoseconds and means nothing.  20 mV/us
# excludes the rail and the ~16.5 mV pedestal (DESIGN Sec 7) and keeps every
# cell that is on the volt-scale decay.
SLOPE_MIN_MV_PER_NS = 0.02


def load_session(path):
    """Return (meta, t_ms, v_mV, colmap). Tolerates either field separator."""
    colmap, meta, rows, ncols = [], {}, [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith('#'):
                if line.startswith('# colmap: '):
                    colmap.append(line.split('# colmap: ', 1)[1].strip().split(','))
                elif line.startswith('# profile_json: '):
                    meta['profile_raw'] = line.split('# profile_json: ', 1)[1].strip()
                elif ': ' in line:
                    k, val = line[2:].split(': ', 1)
                    meta.setdefault(k.strip(), val.strip())
                continue
            f = line.rstrip('\n').split(',')
            if f and f[0].startswith('pc_wallclock'):
                ncols = sum(1 for c in f if c.startswith('ch'))
                continue
            if ncols is None or len(f) < 2 + ncols:
                continue
            rows.append([int(f[1])] + [int(x) for x in f[2:2 + ncols]])
    if not rows:
        raise SystemExit(f'{path}: no data rows (is this a session dump?)')
    a = np.array(rows, dtype=np.int64)
    return meta, a[:, 0], a[:, 1:] / 1000.0, colmap


def averages_of(meta, default=32):
    """`averages` from the embedded profile JSON. The header line is truncated
    by classviz, so fall back rather than fail -- but say which was used."""
    raw = meta.get('profile_raw', '')
    try:
        return json.loads(raw)['averages'], True
    except Exception:
        pass
    # Truncated JSON: the field is a plain integer, so read it textually.
    key = '"averages":'
    if key in raw:
        tail = raw.split(key, 1)[1].lstrip()
        digits = ''
        for c in tail:
            if c.isdigit():
                digits += c
            else:
                break
        if digits:
            return int(digits), True
    return default, False


def matched_pairs(m, n_avg, gate_mv=None):
    """Indices and signed step sizes of confirmed single-sample outliers.

    gate_mv=None uses the relative STEP_SIGMA gate (finds the odd cell within
    one run); a number uses that absolute excursion in mV (comparable between
    runs). See the STEP_SIGMA comment for why the distinction matters.
    """
    d = np.diff(m)
    sig = 1.4826 * np.median(np.abs(d - np.median(d)))
    if gate_mv is None:
        if sig <= 0:
            return np.array([], int), np.array([]), 0.0
        thr = STEP_SIGMA * sig
    else:
        thr = gate_mv / n_avg
    cand = np.where(np.abs(d) > thr)[0]
    idx = [i for i in cand
           if i + n_avg < len(d) and abs(d[i + n_avg] + d[i]) < PAIR_TOL * abs(d[i])]
    idx = np.array(idx, int)
    return idx, (d[idx] * n_avg if len(idx) else np.array([])), sig


def local_slope_mv_per_ns(delays_us, means_mv, i):
    """dV/dt at cell i from its neighbours, in mV/ns. None if not derivable."""
    lo, hi = max(i - 1, 0), min(i + 1, len(delays_us) - 1)
    if hi == lo:
        return None
    dt_ns = (delays_us[hi] - delays_us[lo]) * 1000.0
    if dt_ns == 0:
        return None
    return abs((means_mv[hi] - means_mv[lo]) / dt_ns)


def report(path, hist_ch=None):
    meta, t, v, colmap = load_session(path)
    n_avg, avg_known = averages_of(meta)
    n_frames, n_ch = v.shape

    print(f'\n=== {path}')
    print(f'    fw {meta.get("fw_version", "?")}  '
          f'profile_sha8 {meta.get("profile_sha8", "?")}  '
          f'{n_ch} channels  {n_frames} frames  '
          f'averages {n_avg}{"" if avg_known else " (ASSUMED -- not in header)"}')

    dt = np.diff(t).astype(float)
    med = np.median(dt)
    print(f'    sweep {1000/dt.mean():.2f} Hz  (mean {dt.mean():.1f} ms, '
          f'min {dt.min():.0f}, max {dt.max():.0f})  span {(t[-1]-t[0])/1000:.0f} s')
    # A dropped frame doubles an interval and breaks the N-frame pairing.
    gaps = int((dt > 1.6 * med).sum())
    if gaps:
        print(f'    WARNING: {gaps} interval(s) > 1.6x median -- likely dropped '
              f'frames. Outlier pairing is unreliable across those points.')

    # Group channels by band so the boundary gradient is readable.
    bands = {}
    for cm in colmap:
        bands.setdefault(int(cm[1]), []).append(
            (int(cm[0]), float(cm[4]), cm[2], cm[3], cm[5]))
    if not bands:
        bands = {0: [(c, float(c), '?', '?', '?') for c in range(n_ch)]}

    for b in sorted(bands):
        cells = sorted(bands[b])
        chs = [c[0] for c in cells]
        delays = [c[1] for c in cells]
        means = [v[:, c].mean() for c in chs]
        print(f'\n    band {b}: {cells[0][2]} Hz / {cells[0][3]} us  '
              f'({len(chs)} cells)')
        print(f'      ch  delay_us  target_V     mean_mV   sigma_mV   jitter_ns'
              f'   rel/1000   >{ABS_GATE_MV:.0f}mV/1000   median_mV')
        jits, rates = [], []
        for k, ch in enumerate(chs):
            idx, amp, _ = matched_pairs(v[:, ch], n_avg)
            abs_idx, _, _ = matched_pairs(v[:, ch], n_avg, gate_mv=ABS_GATE_MV)
            d = np.diff(v[:, ch])
            sig_d = 1.4826 * np.median(np.abs(d - np.median(d)))
            sigma = sig_d * n_avg / np.sqrt(2)
            slope = local_slope_mv_per_ns(delays, means, k)
            # Only quote nanoseconds where they mean something: the cell has to
            # be resolvable (above 1 LSB) AND on a slope steep enough to convert.
            if sigma >= QUANT_MV and slope and slope >= SLOPE_MIN_MV_PER_NS:
                jits.append(sigma / slope)
                jit = f'{jits[-1]:7.1f}'
            else:
                jits.append(None)
                jit = '     --'
            rates.append(1000.0 * len(idx) / max(len(d), 1))
            abs_rate = 1000.0 * len(abs_idx) / max(len(d), 1)
            medamp = np.median(np.abs(amp)) if len(amp) else 0.0
            print(f'      {ch:2d}  {delays[k]:8.3f}  {cells[k][4]:>8}  '
                  f'{means[k]:10.1f} {sigma:10.2f} {jit}   '
                  f'{rates[-1]:8.1f}   {abs_rate:11.1f}   {medamp:9.0f}')

        # Flag the two signatures explicitly rather than leaving it to the eye.
        # Baseline is the band's own settled cells, so it travels across bands,
        # pack states and epochs without a hard-coded expectation.
        settled = [j for j in jits[3:] if j is not None]
        lead = [j for j in jits[:3] if j is not None]
        if settled and lead:
            base = float(np.median(settled))
            if max(lead) > 2 * base:
                print(f'      -> boundary-settling gradient: first cells '
                      f'{", ".join(f"{j:.1f}" for j in lead)} ns against this '
                      f'band\'s own {base:.1f} ns settled baseline')
        worst = int(np.argmax(rates))
        others = [r for i, r in enumerate(rates) if i != worst]
        peer = max(others) if others else 0.0
        if rates[worst] > 20 and rates[worst] > 5 * peer:
            print(f'      -> index-locked outlier population at ch{chs[worst]} '
                  f'(sweep position {chs[worst]}): {rates[worst]:.1f} events per '
                  f'1000 sweeps against {peer:.1f} for the worst other cell in '
                  f'the band')

    if hist_ch is not None:
        idx, amp, _ = matched_pairs(v[:, hist_ch], n_avg)
        print(f'\n    ch{hist_ch} excursion sizes ({len(amp)} confirmed events) '
              f'-- two sharp modes mean a discrete mechanism, a single broad '
              f'peak means a heavy tail:')
        if len(amp):
            step = 40
            edges = np.arange(np.floor(amp.min()/step)*step,
                              np.ceil(amp.max()/step)*step + step, step)
            h, e = np.histogram(amp, bins=edges)
            for c, lo in zip(h, e[:-1]):
                if c:
                    print(f'      {lo:+6.0f}..{lo+step:+6.0f} mV  '
                          f'{"#" * min(int(c), 50)} {c}')
            # Residue-class spread: real events do not favour i mod N.
            cls = np.bincount(idx % n_avg, minlength=n_avg)
            verdict = ('spread across classes -- not a reconstruction artefact'
                       if cls.max() < 4 * max(cls.mean(), 1) else
                       'CLUSTERED in few classes -- suspect artefact')
            print(f'      residue class (i mod {n_avg}): min {cls.min()} '
                  f'max {cls.max()} mean {cls.mean():.1f} -- {verdict}')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('sessions', nargs='+')
    ap.add_argument('--hist', type=int, default=None, metavar='CH',
                    help='excursion-size histogram + artefact control for one channel')
    args = ap.parse_args()
    print(f'mode2_cell_noise v{TOOL_VERSION}')
    for p in args.sessions:
        report(p, args.hist)
    print()


if __name__ == '__main__':
    sys.exit(main())
