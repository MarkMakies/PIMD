#!/usr/bin/env python3
"""Pack discharge-rate analysis from classviz session dumps.  TOOL_VERSION = v3

Reads the `# pack_v:` comment lines a classviz session dump already carries and
derives the pack's discharge rate, state of charge, and remaining runway under
continuous streaming load.  Emits JSON on stdout; `build_page.py` renders it.

Read-only with respect to the repo: opens session dumps, writes only its own output.

# History (full detail in CHANGELOG.md):
#   v3 'sag' renamed to a curve-alignment offset — it is NOT the IR drop
#   v2 charge-cycle detection; refuse to fit across a recharge; fit-quality warnings
#   v1 initial — age_s correction, streaming-time axis, auto-calibrated SoC curve

Why the model is shaped the way it is
-------------------------------------
The classviz profile loop draws a fixed duty, so pack current is constant, so
charge drains linearly in time.  State of charge is therefore a straight line in
*streaming* time by construction, and that is the axis everything is fitted
against.  Rather than trust a datasheet curve, two free parameters are fitted to
the readings themselves:

    T       streaming minutes from a full pack to the empty-cell voltage
    offset  constant volts/cell aligning the assumed OCV curve to these readings

    V_pack(t) = N_CELLS * ( Vcell_ocv(100 * (1 - t/T)) - offset )

**`offset` is not the IR drop, and must not be reported as one.**  It is a fitting
constant that absorbs whatever mismatch exists between the nominal ICR18650 OCV
curve above and this pack, and it comes out around 3x the real IR sag: the operator
measured pack B directly at 25.04 V no-load / 24.96 MCU-only / 24.75 V running,
i.e. 0.29 V at the pack (CHANGELOG.md, 2026-07-30 findings entry), against ~0.95 V
for 6 * offset here.  The gap is curve-shape error, and it bounds how literally the
fitted curve can be read: trust the runtime it implies, not the shape.

Three corrections the raw log requires
--------------------------------------
1. `age_s` must be applied.  The `# pack_v:` line in a dump's *header* is the
   spinbox value restored from settings at session open, not a fresh reading.
   True measurement time is `logged - age_s`.  Applying this recovers genuine
   readings that predate their own session and collapses phantom duplicates.
   A header line with no `age_s` (the pre-v1.66 two-field form, or an explicit
   `age_s=unknown`) cannot be dated at all and is dropped.
2. The x axis must be accumulated *streaming* minutes, not wall clock.  Idle
   drain is roughly an order of magnitude below streaming drain, so wall clock
   would flatten the slope through every gap between sessions.
3. Readings taken within RESTED_MIN of load-on are rested voltage, not
   settled-under-load, and sit high.  They are excluded from the fit.

Caveat that no amount of fitting removes: t = 0 assumes the pack was full when
the first session of the day began.  If it was not, T is not full-pack capacity
but a scaled equivalent, and every projection shifts with it.

Usage
-----
    python packv.py                     # today's sessions, JSON to stdout
    python packv.py --date 20260730 --out packv.json
    python packv.py --sessions-dir /path/to/sessions --end-cell 2.75
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
from statistics import mean

TOOL_VERSION = 'v3'

N_CELLS = 6
V_FULL_CELL = 4.20          # ideal fresh cell -> 25.2 V for a 6S pack
DEFAULT_END_CELL = 3.00     # allowable discharge floor -> 18.0 V
DEFAULT_RESTED_MIN = 5.0    # readings this soon after load-on are rested
DEFAULT_RECHARGE_V = 0.8    # a rise this large means a recharge or pack swap

def default_sessions_dir():
    """Sessions dir, resolved relative to this script when it lives in the repo.

    Installed at <repo>/utilities/pack_discharge/packv.py, the dumps are two
    levels up under src/data/sessions.  Falls back to the known absolute path so
    the tool still works if it is copied somewhere outside the repo.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    guess = os.path.join(os.path.dirname(os.path.dirname(here)),
                         'src', 'data', 'sessions')
    if os.path.isdir(guess):
        return guess
    return '/home/mark/Projects/PIMD/src/data/sessions'
TICK_VOLTS = (25.2, 25.0, 24.5, 24.0, 23.5, 23.0, 22.5, 22.0,
              21.5, 21.0, 20.5, 20.0, 19.5, 19.0, 18.5, 18.0)

PACK_V_RE = re.compile(r'^#\s*pack_v:\s*(\S+?),\s*([0-9.]+)(?:,\s*age_s=(\S+))?\s*$')

# Nominal Samsung ICR18650-26C (LCO) open-circuit shape, per cell -> SoC %.
# The two fitted parameters stretch and offset this shape; they cannot change it,
# which is the model's main structural limitation.
NOMINAL = [(4.20, 100), (4.15, 95), (4.11, 90), (4.06, 85), (4.02, 80),
           (3.98, 75), (3.95, 70), (3.91, 65), (3.87, 60), (3.83, 55),
           (3.80, 50), (3.77, 45), (3.75, 40), (3.72, 35), (3.70, 30),
           (3.67, 25), (3.63, 20), (3.57, 15), (3.49, 10), (3.35, 5), (3.00, 0)]


def soc_nominal(vcell):
    """Cell open-circuit volts -> SoC %, piecewise-linear on NOMINAL."""
    if vcell >= NOMINAL[0][0]:
        return 100.0
    if vcell <= NOMINAL[-1][0]:
        return 0.0
    for (v1, s1), (v2, s2) in zip(NOMINAL, NOMINAL[1:]):
        if v2 <= vcell <= v1:
            return s2 + (s1 - s2) * (vcell - v2) / (v1 - v2)
    return 0.0


def vcell_at_soc(soc):
    """SoC % -> cell open-circuit volts (inverse of soc_nominal)."""
    pts = [(s, v) for v, s in NOMINAL]          # descending in SoC
    if soc >= pts[0][0]:
        return pts[0][1]
    if soc <= pts[-1][0]:
        return pts[-1][1]
    for (s1, v1), (s2, v2) in zip(pts, pts[1:]):
        if s2 <= soc <= s1:
            return v2 + (v1 - v2) * (soc - s2) / (s1 - s2)
    return pts[-1][1]


def load_sessions(sessions_dir, date):
    """Parse every dump for `date`, oldest first.  Returns session dicts."""
    pattern = os.path.join(sessions_dir, f'session_{date}_*.csv')
    out = []
    for path in sorted(glob.glob(pattern)):
        start_iso = first_row = last_row = None
        fw = profile = None
        reads = []
        with open(path, errors='replace') as fh:
            for line in fh:
                if line.startswith('#'):
                    if line.startswith('# session_start_iso:'):
                        start_iso = line.split(':', 1)[1].strip()
                    elif line.startswith('# fw_version:'):
                        fw = line.split(':', 1)[1].strip()
                    elif line.startswith('# profile_sha8:'):
                        profile = line.split(':', 1)[1].strip()
                    else:
                        m = PACK_V_RE.match(line.strip())
                        if m:            # `(not measured)` fails the numeric group
                            age = m.group(3)
                            reads.append({
                                'logged': dt.datetime.fromisoformat(m.group(1)),
                                'volts': float(m.group(2)),
                                'age_s': None if age in (None, 'unknown') else int(age)})
                    continue
                if line.startswith('pc_wallclock'):
                    continue
                ts = line.split(',', 1)[0]   # repo convention: plain split, no quoting
                if len(ts) < 4 or not ts[:4].isdigit():
                    continue
                if first_row is None:
                    first_row = ts
                last_row = ts
        if first_row is None:
            continue                          # dump with no data rows
        out.append({
            'path': path, 'name': os.path.basename(path),
            'start': dt.datetime.fromisoformat(start_iso) if start_iso else None,
            'first': dt.datetime.fromisoformat(first_row),
            'last': dt.datetime.fromisoformat(last_row),
            'fw': fw, 'profile': profile, 'reads': reads})
    return out


def fit_curve(xs, ys, model):
    """Grid-search then refine (T, offset) by least squares.

    Returns (sse, T, offset).  `offset` is a curve-alignment constant, not IR sag —
    see the module docstring.
    """
    def sse(T, offset):
        return sum((model(x, T, offset) - y) ** 2 for x, y in zip(xs, ys))

    best = None
    T_lo, T_hi, s_lo, s_hi = 200.0, 4000.0, -0.30, 0.30
    for _ in range(6):
        cand = None
        for i in range(90):
            T = T_lo + (T_hi - T_lo) * i / 89
            for j in range(90):
                sg = s_lo + (s_hi - s_lo) * j / 89
                e = sse(T, sg)
                if cand is None or e < cand[0]:
                    cand = (e, T, sg)
        best = cand
        _, T, sg = cand
        dT, dS = (T_hi - T_lo) / 12.0, (s_hi - s_lo) / 12.0
        T_lo, T_hi = max(60.0, T - dT), T + dT
        s_lo, s_hi = sg - dS, sg + dS
    return best


def ols(xs, ys):
    """Least-squares slope/intercept plus R^2 and slope standard error."""
    n = len(xs)
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return 0.0, my, 0.0, 0.0
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    rss = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    tss = sum((y - my) ** 2 for y in ys) or 1e-12
    se = (rss / max(n - 2, 1) / sxx) ** 0.5
    return b, a, 1 - rss / tss, se


def analyse(sessions, end_cell, rested_min, cycle='latest',
            recharge_v=DEFAULT_RECHARGE_V):
    bouts = [(s['first'], s['last']) for s in sessions]

    def stream_min(t):
        """Accumulated load-on minutes at wallclock t."""
        tot = 0.0
        for a, b in bouts:
            if t >= b:
                tot += (b - a).total_seconds()
            elif t > a:
                tot += (t - a).total_seconds()
                break
            else:
                break
        return tot / 60.0

    def min_into_bout(t):
        # 5 s tolerance: a session-open reading is logged microseconds *before*
        # the first data row, so an exact `a <= t` test misses it.
        for a, b in bouts:
            if a - dt.timedelta(seconds=5) <= t <= b:
                return max(0.0, (t - a).total_seconds() / 60.0)
        return None

    raw = []
    for s in sessions:
        for r in s['reads']:
            meas = (r['logged'] - dt.timedelta(seconds=r['age_s'])
                    if r['age_s'] is not None else r['logged'])
            raw.append({**r, 'meas': meas, 'session': s['name']})
    raw.sort(key=lambda r: (r['meas'], r['logged']))

    starts = {s['start'] for s in sessions if s['start']}

    def is_header_line(t):
        return any(abs((t - a).total_seconds()) <= 2 for a in starts)

    seen, rows = {}, []
    for r in raw:
        key = (r['meas'].replace(microsecond=0), r['volts'])
        dup = key in seen
        stale = (not dup and r['age_s'] is None and is_header_line(r['logged']))
        into = min_into_bout(r['meas'])
        rows.append({**r, 'stream_min': stream_min(r['meas']), 'into_bout': into,
                     'dup': dup, 'stale': stale,
                     'rested': into is not None and into < rested_min,
                     'vcell': r['volts'] / N_CELLS})
        seen.setdefault(key, True)

    # --- Charge cycles.  The whole model rests on a single monotonic discharge;
    # fitting across a recharge or pack swap produces confident nonsense (a 3 V
    # step reads as negative discharge and blows the residual out by ~20x).  Any
    # rise beyond recharge_v between consecutive datable readings opens a new
    # cycle.  The threshold sits well clear of rest recovery, measured at +0.29 V
    # across a 2 h load-off gap on 2026-07-30.
    cyc, prev_v = 0, None
    for r in rows:
        if not (r['dup'] or r['stale']):
            if prev_v is not None and r['volts'] - prev_v > recharge_v:
                cyc += 1
            prev_v = r['volts']
        r['cycle'] = cyc
    n_cycles = cyc + 1

    if cycle == 'all':
        sel, sel_cycle = rows, None
    else:
        sel_cycle = n_cycles - 1 if cycle == 'latest' else int(cycle)
        if not 0 <= sel_cycle < n_cycles:
            raise SystemExit(f'--cycle {cycle}: only {n_cycles} cycle(s) found '
                             f'(0..{n_cycles - 1})')
        sel = [r for r in rows if r['cycle'] == sel_cycle]

    # Streaming time restarts with the pack: re-zero to the cycle's first reading.
    # (This makes the x = 0 assumption explicit per cycle rather than per day.)
    t_zero = min((r['stream_min'] for r in sel), default=0.0) if sel_cycle else 0.0
    if t_zero:
        for r in sel:
            r['stream_min'] -= t_zero
    rows = sel

    fit_rows = [r for r in rows if not (r['dup'] or r['stale'] or r['rested'])]
    if len(fit_rows) < 3:
        raise SystemExit(
            f'cycle {sel_cycle if sel_cycle is not None else "all"} has only '
            f'{len(fit_rows)} usable readings — need at least 3.\n'
            f'{n_cycles} charge cycle(s) detected today. Press Log V a few more '
            f'times, or analyse an earlier one with --cycle 0.')

    def model(t, T, offset):
        soc = max(0.0, min(100.0, 100.0 * (1.0 - t / T)))
        return N_CELLS * (vcell_at_soc(soc) - offset)

    xs = [r['stream_min'] for r in fit_rows]
    ys = [r['volts'] for r in fit_rows]
    sse_best, T_fit, off_fit = fit_curve(xs, ys, model)
    n = len(fit_rows)
    rmse_v = (sse_best / n) ** 0.5

    def soc_cal(t):
        return max(0.0, min(100.0, 100.0 * (1.0 - t / T_fit)))

    def soc_from_volts(v):
        """Loaded pack volts -> SoC %.  Plotting readings through this makes
        departure from the straight constant-current line show as scatter."""
        return soc_nominal(v / N_CELLS + off_fit)

    def t_at_volts(v):
        return T_fit * (1.0 - soc_from_volts(v) / 100.0)

    # --- T uncertainty: rescan T with the offset re-optimised, keep the span where RMSE
    # stays within +10 mV of best (readings are 10 mV resolution, and curve-shape
    # mismatch dominates reading noise anyway).
    def best_offset(T):
        lo, hi = -0.4, 0.4
        for _ in range(40):
            m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
            if sum((model(x, T, m1) - y) ** 2 for x, y in zip(xs, ys)) < \
               sum((model(x, T, m2) - y) ** 2 for x, y in zip(xs, ys)):
                hi = m2
            else:
                lo = m1
        return (lo + hi) / 2

    thresh = ((rmse_v + 0.010) ** 2) * n
    span = [200.0 + (2000.0 - 200.0) * i / 399 for i in range(400)]
    span = [T for T in span
            if sum((model(x, T, best_offset(T)) - y) ** 2 for x, y in zip(xs, ys)) <= thresh]

    # --- robustness.  Leave-one-out is the check that actually means something
    # here: refit dropping each reading in turn and see how far T moves.
    loo_T = []
    for i in range(len(fit_rows)):
        sub = fit_rows[:i] + fit_rows[i + 1:]
        if len(sub) < 3:
            continue
        _, Tv, _ = fit_curve([r['stream_min'] for r in sub],
                             [r['volts'] for r in sub], model)
        loo_T.append({'dropped': fit_rows[i]['meas'].isoformat(),
                      'volts': fit_rows[i]['volts'], 'T_min': Tv})
    loo = {}
    if loo_T:
        vals = sorted(x['T_min'] for x in loo_T)
        med = vals[len(vals) // 2]
        loo = {'n': len(vals), 'T_lo': vals[0], 'T_hi': vals[-1], 'T_median': med,
               'spread_pct': (vals[-1] - vals[0]) / med * 100.0, 'each': loo_T}

    # --- subset fits, kept for the conditioning story rather than as validation.
    # Splitting by session is NOT a valid cross-check: a subset confined to the
    # plateau spans too little voltage to separate T from the curve offset (they
    # trade off), so it can return a wildly different T with a compensating
    # offset.  Only a
    # subset carrying real curvature has leverage on T.  The voltage span is
    # reported alongside each fit so that degeneracy is visible, not hidden.
    newest = sessions[-1]['name']
    subsets = {}
    for label, subset in (('live', [r for r in fit_rows if r['session'] == newest]),
                          ('earlier', [r for r in fit_rows if r['session'] != newest])):
        if len(subset) >= 3:
            sv = [r['volts'] for r in subset]
            e, Tv, sg = fit_curve([r['stream_min'] for r in subset], sv, model)
            subsets[label] = {'n': len(subset), 'T_min': Tv, 'offset': sg,
                              'rmse_v': (e / len(subset)) ** 0.5,
                              'v_span': max(sv) - min(sv)}

    # --- straight voltage-vs-time fit over the newest session, as a cruder
    # cross-check and an optimistic bound on the runway.
    live_rows = [r for r in fit_rows if r['session'] == newest] or fit_rows
    b_lin, a_lin, r2, se_b = ols([r['stream_min'] for r in live_rows],
                                 [r['volts'] for r in live_rows])

    now_stream = stream_min(sessions[-1]['last']) - t_zero
    last = max(fit_rows, key=lambda r: r['stream_min'])
    v_floor = end_cell * N_CELLS

    out = {
        'generated': dt.datetime.now().isoformat(timespec='seconds'),
        'tool_version': TOOL_VERSION,
        'cycles': {'n': n_cycles, 'analysed': sel_cycle,
                   'recharge_v': recharge_v},
        'params': {'end_cell': end_cell, 'rested_min': rested_min,
                   'n_cells': N_CELLS, 'v_full_cell': V_FULL_CELL},
        'sessions': [{'name': s['name'],
                      'start': s['start'].isoformat() if s['start'] else None,
                      'first': s['first'].isoformat(), 'last': s['last'].isoformat(),
                      'span_min': (s['last'] - s['first']).total_seconds() / 60.0,
                      'fw': s['fw'], 'profile': s['profile'],
                      'n_reads': len(s['reads'])} for s in sessions],
        'rows': [{'logged': r['logged'].isoformat(), 'meas': r['meas'].isoformat(),
                  'age_s': r['age_s'], 'volts': r['volts'], 'vcell': r['vcell'],
                  'stream_min': r['stream_min'], 'into_bout': r['into_bout'],
                  'dup': r['dup'], 'stale': r['stale'], 'rested': r['rested'],
                  'session': r['session'], 'soc_model': soc_cal(r['stream_min']),
                  'soc': soc_from_volts(r['volts'])} for r in rows],
        'fit': {'T_min': T_fit, 'T_h': T_fit / 60.0,
                'curve_offset_v_per_cell': off_fit,
                'rmse_v': rmse_v, 'n': n,
                'soc_rate_pct_per_h': -100.0 / (T_fit / 60.0),
                'T_min_lo': min(span) if span else None,
                'T_min_hi': max(span) if span else None},
        'loo': loo,
        'subsets': subsets,
        'linfit': {'slope_v_per_h': b_lin * 60.0, 'se_v_per_h': se_b * 60.0,
                   'intercept_v': a_lin, 'r2': r2, 'n': len(live_rows),
                   'h_to_floor': ((last['volts'] - v_floor) / abs(b_lin * 60.0)
                                  if b_lin else None)},
        'now_stream_min': now_stream,
        'now_soc': soc_cal(now_stream),
        'last_reading': {'meas': last['meas'].isoformat(), 'volts': last['volts'],
                         'vcell': last['volts'] / N_CELLS,
                         'stream_min': last['stream_min'],
                         'soc': soc_from_volts(last['volts'])},
        'implied_ah_at_0p5A': 0.5 * (T_fit / 60.0),
        'vticks': [{'volts': v, 'soc': soc_from_volts(v)} for v in TICK_VOLTS],
    }

    # --- honesty flags: conditions under which the numbers above should not be
    # trusted.  Surfaced on the page, not buried in stderr.
    warn = []
    v_span = max(ys) - min(ys)
    if n_cycles > 1 and sel_cycle is not None:
        warn.append(f'{n_cycles} charge cycles detected today — this is cycle '
                    f'{sel_cycle}; readings from the others are excluded. '
                    f'Use --cycle N to pick another.')
    if v_span < 0.5:
        warn.append(f'the fitted readings span only {v_span:.2f} V and sit on the '
                    f'plateau, which is too little curvature to constrain the '
                    f'runtime — treat it and every projection as indicative only.')
    if n < 5:
        warn.append(f'only {n} settled readings in this cycle.')
    if rmse_v > 0.20:
        warn.append(f'residual RMS is {rmse_v*1000:.0f} mV against the ~50 mV a '
                    f'clean single discharge gives — these readings may not be one '
                    f'monotonic discharge.')
    out['warnings'] = warn

    out['milestones'] = []
    for v, lbl in ((V_FULL_CELL * N_CELLS, f'ideal fresh pack — {V_FULL_CELL:.2f} V/cell'),
                   (23.00, '3.83 V/cell'), (22.00, '3.67 V/cell'), (21.50, '3.58 V/cell'),
                   (21.00, 'DESIGN §12 working floor — 3.50 V/cell'),
                   (19.80, 'DESIGN §12 pack minimum — 3.30 V/cell'),
                   (v_floor, f'allowable floor / L7815 dropout — {end_cell:.2f} V/cell')):
        t = t_at_volts(v)
        out['milestones'].append({'volts': v, 'label': lbl, 'stream_min': t,
                                  'soc': soc_cal(t),
                                  'h_from_now': (t - now_stream) / 60.0})

    # --- idle-drain control: longest load-off gap between two datable readings.
    # Prefer a gap that actually shows a drop; a rise is rest recovery, not drain.
    datable = [r for r in rows if not (r['dup'] or r['stale'])]
    cands = []
    for a, b in zip(datable, datable[1:]):
        gap_h = (b['meas'] - a['meas']).total_seconds() / 3600.0
        idle_h = gap_h - (b['stream_min'] - a['stream_min']) / 60.0
        if idle_h > 0.5:
            cands.append({'from': a['meas'].isoformat(), 'to': b['meas'].isoformat(),
                          'idle_h': idle_h, 'dv': b['volts'] - a['volts'],
                          'v_per_h': (a['volts'] - b['volts']) / idle_h,
                          'v_from': a['volts'], 'v_to': b['volts']})
    out['idle_all'] = cands
    drops = [c for c in cands if c['dv'] < 0]
    out['idle'] = (max(drops, key=lambda c: c['idle_h']) if drops else
                   (max(cands, key=lambda c: c['idle_h']) if cands else {}))

    out['segments'] = []
    for a, b in zip(fit_rows, fit_rows[1:]):
        dh = (b['stream_min'] - a['stream_min']) / 60.0
        if dh > 0:
            out['segments'].append({
                'from': a['meas'].isoformat(), 'to': b['meas'].isoformat(),
                'stream_h': dh, 'dv': b['volts'] - a['volts'],
                'v_per_h': (a['volts'] - b['volts']) / dh})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sessions-dir', default=default_sessions_dir(),
                    help='directory of classviz session dumps '
                         '(default: the repo\'s src/data/sessions)')
    ap.add_argument('--date', default=dt.date.today().strftime('%Y%m%d'),
                    help='session date YYYYMMDD (default: today). One charge cycle per run.')
    ap.add_argument('--end-cell', type=float, default=DEFAULT_END_CELL,
                    help=f'allowable discharge floor, volts per cell (default {DEFAULT_END_CELL})')
    ap.add_argument('--rested-min', type=float, default=DEFAULT_RESTED_MIN,
                    help=f'exclude readings this soon after load-on '
                         f'(default {DEFAULT_RESTED_MIN} min)')
    ap.add_argument('--cycle', default='latest',
                    help="charge cycle to analyse: 'latest' (default), 'all', "
                         "or an index (0 = first of the day). A recharge or pack "
                         "swap starts a new cycle.")
    ap.add_argument('--recharge-v', type=float, default=DEFAULT_RECHARGE_V,
                    help=f'voltage rise that counts as a recharge '
                         f'(default {DEFAULT_RECHARGE_V} V)')
    ap.add_argument('--out', help='write JSON here instead of stdout')
    args = ap.parse_args()

    if not os.path.isdir(args.sessions_dir):
        raise SystemExit(f'no such sessions directory: {args.sessions_dir}')
    sessions = load_sessions(args.sessions_dir, args.date)
    if not sessions:
        raise SystemExit(f'no session dumps with data rows for {args.date} '
                         f'in {args.sessions_dir}')

    result = analyse(sessions, args.end_cell, args.rested_min,
                     cycle=args.cycle, recharge_v=args.recharge_v)
    text = json.dumps(result, indent=1)
    if args.out:
        with open(args.out, 'w') as fh:
            fh.write(text)
        c = result['cycles']
        print(f'wrote {args.out}  ({len(result["rows"])} readings, '
              f'{result["fit"]["n"]} in fit, cycle {c["analysed"]} of {c["n"]})',
              file=sys.stderr)
        for w in result['warnings']:
            print(f'  warning: {w}', file=sys.stderr)
    else:
        print(text)


if __name__ == '__main__':
    main()
