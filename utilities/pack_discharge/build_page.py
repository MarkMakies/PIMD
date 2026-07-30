#!/usr/bin/env python3
"""Render the pack-discharge page from packv.py's JSON.  TOOL_VERSION = v3

Emits a single self-contained HTML fragment — no external assets, no <html>/<head>
wrapper — suitable for publishing as a Claude artifact or opening directly.

# History (full detail in CHANGELOG.md):
#   v3 states plainly that the fitted offset is not internal resistance
#   v2 warning banner for fit-quality caveats; 'passed' state on the floor tile
#   v1 initial — SoC-linear y axis with non-linear voltage relabelling

Chart design notes
------------------
The y axis is linear in state of charge; the right-hand voltage ticks are the
*same* axis relabelled through the calibrated cell curve, so they crowd together
through the plateau.  That is one scale with two labellings, not a dual axis —
there is no second scale and no second series.  Because constant current makes
SoC linear in time, the fitted model is a straight line, and the readings'
scatter around it is the residual.

Colours are the two validated slots (series blue, status critical) plus the
documented neutral chrome; the palette clears every check of the data-viz
validator in both light and dark mode.

Usage
-----
    python packv.py --out packv.json && python build_page.py
    python build_page.py --json packv.json --out pack-discharge.html
"""
import argparse
import datetime as dt
import html
import json
import os

TOOL_VERSION = 'v3'
HERE = os.path.dirname(os.path.abspath(__file__))

# ---- plot geometry (SVG user units; the page scales it to width) -----------
W, H = 1000.0, 500.0
L, R, TOP, BOT = 62.0, 92.0, 26.0, 66.0
XMAX = 620.0
PW, PH = W - L - R, H - TOP - BOT


def build(D):
    fit, lin, lr = D['fit'], D['linfit'], D['last_reading']
    cv = D.get('loo', {})
    T, T_lo, T_hi = fit['T_min'], fit['T_min_lo'], fit['T_min_hi']
    now_x = D['now_stream_min']
    rows = D['rows']
    ms = {m['volts']: m for m in D['milestones']}
    end_v = D['params']['end_cell'] * D['params']['n_cells']

    def px(x):
        return L + (x / XMAX) * PW

    def py(s):
        return TOP + (1.0 - s / 100.0) * PH

    def soc_at(x):
        return max(0.0, min(100.0, 100.0 * (1.0 - x / T)))

    def f(v, n=1):
        return f'{v:.{n}f}'

    parts = []
    A = parts.append

    for s in range(0, 101, 10):
        A(f'<line class="grid" x1="{f(px(0),2)}" y1="{f(py(s),2)}" '
          f'x2="{f(px(XMAX),2)}" y2="{f(py(s),2)}"/>')
        A(f'<text class="tick tick-l" x="{f(L-12,2)}" y="{f(py(s)+4,2)}">{s}</text>')

    h = 0
    while h * 60 <= XMAX:
        x = px(h * 60)
        A(f'<line class="grid" x1="{f(x,2)}" y1="{f(TOP,2)}" '
          f'x2="{f(x,2)}" y2="{f(TOP+PH,2)}"/>')
        A(f'<text class="tick tick-x" x="{f(x,2)}" y="{f(TOP+PH+22,2)}">{h}</text>')
        h += 1

    # capacity-uncertainty band, clipped to the plot rect
    A(f'<clipPath id="plotclip"><rect x="{f(L,2)}" y="{f(TOP,2)}" '
      f'width="{f(PW,2)}" height="{f(PH,2)}"/></clipPath>')
    band = (f'{f(px(0),2)},{f(py(100),2)} {f(px(T_hi),2)},{f(py(0),2)} '
            f'{f(px(T_lo),2)},{f(py(0),2)}')
    A(f'<polygon class="band" points="{band}" clip-path="url(#plotclip)"/>')

    # right-hand voltage ticks: non-linear by construction, so drop any that
    # would collide with the last one drawn
    last_y = None
    for vt in D['vticks']:
        s = vt['soc']
        if s <= 1.2 or s >= 99.6:
            continue
        y = py(s)
        if last_y is not None and abs(y - last_y) < 13:
            continue
        last_y = y
        A(f'<line class="vtick" x1="{f(px(XMAX),2)}" y1="{f(y,2)}" '
          f'x2="{f(px(XMAX)+6,2)}" y2="{f(y,2)}"/>')
        A(f'<text class="tick tick-r" x="{f(px(XMAX)+11,2)}" y="{f(y+4,2)}">'
          f'{vt["volts"]:.1f}</text>')

    def thresh(v, cls, label, dy=-7):
        if v not in ms:
            return
        y = py(ms[v]['soc'])
        A(f'<line class="{cls}" x1="{f(px(0),2)}" y1="{f(y,2)}" '
          f'x2="{f(px(XMAX),2)}" y2="{f(y,2)}"/>')
        A(f'<text class="thlab {cls}-t" x="{f(px(0)+8,2)}" y="{f(y+dy,2)}">{label}</text>')

    thresh(21.0, 'th-crit', '21.0 V · working floor — stop here (DESIGN §12)')
    thresh(19.8, 'th-mute', '19.8 V · pack minimum')
    thresh(end_v, 'th-mute', f'{end_v:.1f} V · allowable floor / L7815 dropout')

    # model line: solid to now, dashed beyond, stopping at the allowable floor
    x_end = ms[end_v]['stream_min']
    A(f'<line class="model" x1="{f(px(0),2)}" y1="{f(py(100),2)}" '
      f'x2="{f(px(now_x),2)}" y2="{f(py(soc_at(now_x)),2)}"/>')
    A(f'<line class="model proj" x1="{f(px(now_x),2)}" y1="{f(py(soc_at(now_x)),2)}" '
      f'x2="{f(px(x_end),2)}" y2="{f(py(soc_at(x_end)),2)}"/>')

    A(f'<line class="nowline" x1="{f(px(now_x),2)}" y1="{f(TOP,2)}" '
      f'x2="{f(px(now_x),2)}" y2="{f(TOP+PH,2)}"/>')
    A(f'<text class="nowlab" x="{f(px(now_x)-8,2)}" y="{f(TOP+13,2)}">now</text>')

    pts = []
    for r in rows:
        excl = r['dup'] or r['stale'] or r['rested']
        x, y = px(r['stream_min']), py(r['soc'])
        A(f'<circle class="{"pt-out" if excl else "pt-in"}" '
          f'cx="{f(x,2)}" cy="{f(y,2)}" r="4.5"/>')
        why = ('duplicate of an earlier reading (age_s collapses them)' if r['dup']
               else 'header restore — undatable, no age_s' if r['stale']
               else f'rested — only {r["into_bout"]:.1f} min after load came on'
               if r['rested'] else 'used in fit')
        pts.append({'x': x, 'y': y, 'sx': r['stream_min'], 'v': r['volts'],
                    'vc': r['vcell'], 'soc': r['soc'], 'meas': r['meas'][11:19],
                    'logged': r['logged'][11:19], 'age': r['age_s'],
                    'excl': excl, 'why': why})

    lx, ly = px(lr['stream_min']), py(lr['soc'])
    A(f'<circle class="pt-last" cx="{f(lx,2)}" cy="{f(ly,2)}" r="4.5"/>')
    A(f'<text class="endlab" x="{f(lx+13,2)}" y="{f(ly+19,2)}">'
      f'{lr["volts"]:.2f} V · {lr["soc"]:.0f}%</text>')

    A(f'<line class="axis" x1="{f(L,2)}" y1="{f(TOP+PH,2)}" '
      f'x2="{f(L+PW,2)}" y2="{f(TOP+PH,2)}"/>')
    A(f'<line class="axis" x1="{f(L,2)}" y1="{f(TOP,2)}" '
      f'x2="{f(L,2)}" y2="{f(TOP+PH,2)}"/>')
    A(f'<text class="axtitle" x="{f(L,2)}" y="{f(H-14,2)}">'
      f'hours of classviz streaming since the pack was full '
      f'— x&#8202;=&#8202;0 is {D["params"]["v_full_cell"]*D["params"]["n_cells"]:.1f} V '
      f'at rest</text>')
    A(f'<text class="axtitle axtitle-l" '
      f'transform="translate(16,{f(TOP+PH/2,2)}) rotate(-90)">'
      f'state of charge  %</text>')
    A(f'<text class="axtitle axtitle-r" '
      f'transform="translate({f(W-16,2)},{f(TOP+PH/2,2)}) rotate(-90)">'
      f'pack volts under load</text>')

    svg = '\n        '.join(parts)

    # ---- load-on ribbon ---------------------------------------------------
    rib, cum = [], 0.0
    newest = D['sessions'][-1]['name']
    for s in D['sessions']:
        span = s['span_min']
        x0, x1 = px(cum), px(cum + span)
        rib.append(
            f'<div class="bout{" live" if s["name"] == newest else ""}" '
            f'style="left:{x0/W*100:.4f}%;width:{max((x1-x0)/W*100,0.18):.4f}%" '
            f'title="{html.escape(s["name"])} — {s["first"][11:19]}–{s["last"][11:19]} '
            f'({span:.0f} min)"></div>')
        cum += span
    ribbon = '\n      '.join(rib)

    # ---- tables -----------------------------------------------------------
    trs = []
    for r in rows:
        if r['dup']:
            tag, cl = 'duplicate', 'x'
        elif r['stale']:
            tag, cl = 'header restore', 'x'
        elif r['rested']:
            tag, cl = 'rested', 'x'
        else:
            tag, cl = 'in fit', 'ok'
        age = '—' if r['age_s'] is None else str(r['age_s'])
        shifted = ' shifted' if (r['age_s'] or 0) > 30 else ''
        ib = '—' if r['into_bout'] is None else f'{r["into_bout"]:.1f}'
        trs.append(
            f'<tr class="{cl}"><td class="m">{r["logged"][11:19]}</td>'
            f'<td class="m{shifted}">{r["meas"][11:19]}</td>'
            f'<td class="m n">{age}</td>'
            f'<td class="m n strong">{r["volts"]:.2f}</td>'
            f'<td class="m n">{r["vcell"]:.3f}</td>'
            f'<td class="m n">{r["soc"]:.1f}</td>'
            f'<td class="m n">{r["stream_min"]:.1f}</td>'
            f'<td class="m n">{ib}</td>'
            f'<td><span class="pill {cl}">{tag}</span></td></tr>')
    table = '\n  '.join(trs)

    segtable = '\n  '.join(
        f'<tr><td class="m">{s["from"][11:19]} → {s["to"][11:19]}</td>'
        f'<td class="m n">{s["stream_h"]*60:.1f}</td>'
        f'<td class="m n">{s["dv"]:+.3f}</td>'
        f'<td class="m n strong">{s["v_per_h"]:.3f}</td></tr>' for s in D['segments'])

    sess_rows = '\n  '.join(
        f'<tr><td class="m">{s["name"].replace("session_","")}</td>'
        f'<td class="m">{s["first"][11:19]}–{s["last"][11:19]}</td>'
        f'<td class="m n">{s["span_min"]:.1f}</td>'
        f'<td class="m n">{s["n_reads"]}</td></tr>' for s in D['sessions'])

    n_fit = sum(1 for r in rows if not (r['dup'] or r['stale'] or r['rested']))
    idle = D['idle']
    gen = dt.datetime.fromisoformat(D['generated'])
    h_floor = ms[21.0]['h_from_now'] if 21.0 in ms else float('nan')
    ratio = (abs(lin['slope_v_per_h']) / idle['v_per_h']
             if idle.get('v_per_h') else float('nan'))
    # straight voltage extrapolation to the 21.0 V working floor, as the
    # optimistic bound against the curve's own figure
    h_lin_21 = ((lr['volts'] - 21.0) / abs(lin['slope_v_per_h'])
                if lin['slope_v_per_h'] else float('nan'))

    loo = D.get('loo', {})
    sub = D.get('subsets', {})
    if loo:
        cvtext = (
            f'''<p>The fit is robust to any single reading:
  <strong class="k">leave-one-out</strong> — refitting {loo['n']} times, dropping each
  reading in turn — moves the runtime only between
  <strong class="k">{loo['T_lo']:.0f}</strong> and
  <strong class="k">{loo['T_hi']:.0f} min</strong>, a spread of
  {loo['spread_pct']:.1f}%. And at DESIGN §17.1's measured ~0.5 A average the fit implies
  <strong class="k">{D['implied_ah_at_0p5A']:.2f} Ah</strong>, against 5.20 Ah nominal
  for a 6S2P pack of ICR18650-26C cells —
  <strong class="k">{D['implied_ah_at_0p5A']/5.20*100:.0f}% of nominal</strong>,
  plausible for recovered laptop cells.</p>''')
    else:
        cvtext = (
            f'''<p>At DESIGN §17.1's measured ~0.5 A average the fit implies
  <strong class="k">{D['implied_ah_at_0p5A']:.2f} Ah</strong>. Too few readings to
  run leave-one-out on this set.</p>''')

    if 'live' in sub and 'earlier' in sub:
        cvtext += (
            f'''\n  <p>What does <em>not</em> work is splitting the day in half and
  comparing: the readings from the newest session span only
  {sub['live']['v_span']:.2f} V, all of it plateau, and across so little voltage the
  runtime and the curve offset trade off against each other freely — that subset alone returns
  <strong class="k">{sub['live']['T_min']:.0f} min</strong> with a compensating
  {sub['live']['offset']*1000:.0f} mV/cell offset, which is not a disagreement so much as an
  absence of leverage. The earlier readings, sitting where the curve actually bends,
  give <strong class="k">{sub['earlier']['T_min']:.0f} min</strong> from just
  {sub['earlier']['n']} points. Constraining the runtime needs curvature, not more
  points on the flat.</p>''')

    warns = D.get('warnings', [])
    cyc = D.get('cycles', {})
    if warns:
        items = '\n      '.join(f'<li>{w}</li>' for w in warns)
        warnbox = (
            '<div class="warnbox"><div class="wh"><span class="wi">&#9888;</span>'
            'Read the numbers below with these caveats</div>\n      '
            f'<ul>\n      {items}\n      </ul></div>')
    else:
        warnbox = ''

    PTS = json.dumps(pts, separators=(',', ':'))
    full_v = D['params']['v_full_cell'] * D['params']['n_cells']
    off_pack = D['params']['n_cells'] * fit['curve_offset_v_per_cell']

    return f'''<title>6S pack discharge under classviz load</title>
<style>
  :root {{
    --page:#f9f9f7; --surface:#fcfcfb;
    --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
    --grid:#e1e0d9; --axis:#c3c2b7; --hair:rgba(11,11,11,.10);
    --series:#2a78d6; --crit:#d03b3b;
    --band:rgba(42,120,214,.13); --okbg:rgba(42,120,214,.09);
    --xbg:rgba(11,11,11,.05);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:where(:not([data-theme="light"])) {{
      --page:#0d0d0d; --surface:#1a1a19;
      --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
      --grid:#2c2c2a; --axis:#383835; --hair:rgba(255,255,255,.10);
      --series:#3987e5; --crit:#d03b3b;
      --band:rgba(57,135,229,.18); --okbg:rgba(57,135,229,.13);
      --xbg:rgba(255,255,255,.06);
    }}
  }}
  :root[data-theme="dark"] {{
    --page:#0d0d0d; --surface:#1a1a19;
    --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --hair:rgba(255,255,255,.10);
    --series:#3987e5; --crit:#d03b3b;
    --band:rgba(57,135,229,.18); --okbg:rgba(57,135,229,.13);
    --xbg:rgba(255,255,255,.06);
  }}
  * {{ box-sizing:border-box; }}
  body {{
    margin:0; background:var(--page); color:var(--ink);
    font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
    -webkit-font-smoothing:antialiased;
  }}
  .m {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .n {{ font-variant-numeric:tabular-nums; text-align:right; }}
  .wrap {{ max-width:1120px; margin:0 auto; padding:34px 22px 70px; }}

  .eyebrow {{
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
    font-size:11.5px; letter-spacing:.13em; text-transform:uppercase;
    color:var(--muted); margin:0 0 10px;
  }}
  h1 {{ font-size:27px; line-height:1.2; margin:0 0 8px; text-wrap:balance;
       letter-spacing:-.015em; font-weight:620; }}
  .sub {{ color:var(--ink2); margin:0 0 26px; max-width:66ch; font-size:15px; }}
  h2 {{ font-size:15px; margin:34px 0 12px; letter-spacing:-.005em; font-weight:640; }}
  h2 .cnt {{ color:var(--muted); font-weight:400; }}
  p {{ max-width:70ch; color:var(--ink2); font-size:14.5px; }}
  strong.k {{ color:var(--ink); font-weight:620; }}

  .tiles {{ display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(168px,1fr));
            margin-bottom:24px; }}
  .tile {{ background:var(--surface); border:1px solid var(--hair); border-radius:7px;
           padding:13px 15px 14px; }}
  .tile .lab {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
                font-size:10.5px; letter-spacing:.09em; text-transform:uppercase;
                color:var(--muted); }}
  .tile .val {{ font-size:26px; font-weight:600; letter-spacing:-.02em; margin-top:5px; }}
  .tile .val small {{ font-size:14px; font-weight:500; color:var(--ink2); }}
  .tile .note {{ font-size:12px; color:var(--muted); margin-top:3px; }}
  .tile.warn .val {{ color:var(--crit); }}

  .warnbox {{ background:var(--surface); border:1px solid var(--crit);
              border-left-width:3px; border-radius:7px; padding:12px 15px;
              margin-bottom:22px; }}
  .warnbox .wh {{ display:flex; align-items:center; gap:7px; color:var(--crit);
                  font-weight:640; font-size:13px; margin-bottom:6px; }}
  .warnbox .wi {{ font-size:14px; }}
  .warnbox ul {{ margin:0; padding-left:20px; font-size:13.5px; }}
  .warnbox li {{ margin:4px 0; }}
  .card {{ background:var(--surface); border:1px solid var(--hair);
           border-radius:9px; padding:16px 16px 10px; }}
  .legend {{ display:flex; flex-wrap:wrap; gap:7px 20px; margin:0 0 12px; padding:0 2px;
             font-size:12.5px; color:var(--ink2); }}
  .legend span {{ display:inline-flex; align-items:center; gap:7px; }}
  .sw {{ width:22px; height:0; border-top-width:2px; border-top-style:solid; flex:none; }}
  .sw.mdl {{ border-color:var(--series); }}
  .sw.prj {{ border-color:var(--series); border-top-style:dashed; }}
  .sw.cr  {{ border-color:var(--crit); border-top-style:dashed; }}
  .dot {{ width:10px; height:10px; border-radius:50%; flex:none; }}
  .dot.i {{ background:var(--series); }}
  .dot.o {{ background:var(--surface); border:2px solid var(--series); }}
  .bandsw {{ width:22px; height:10px; background:var(--band); flex:none; border-radius:2px; }}

  .plot {{ position:relative; overflow-x:auto; overflow-y:hidden; }}
  svg {{ display:block; width:100%; min-width:700px; height:auto; overflow:visible; }}
  .grid {{ stroke:var(--grid); stroke-width:1; }}
  .axis {{ stroke:var(--axis); stroke-width:1; }}
  .vtick {{ stroke:var(--axis); stroke-width:1; }}
  .band {{ fill:var(--band); }}
  .model {{ stroke:var(--series); stroke-width:2; fill:none; stroke-linecap:round; }}
  .model.proj {{ stroke-dasharray:7 5; }}
  .th-crit {{ stroke:var(--crit); stroke-width:1.5; stroke-dasharray:6 4; }}
  .th-mute {{ stroke:var(--muted); stroke-width:1; stroke-dasharray:4 4; }}
  .thlab {{ font-size:11px; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .th-crit-t {{ fill:var(--crit); }}
  .th-mute-t {{ fill:var(--muted); }}
  .nowline {{ stroke:var(--ink2); stroke-width:1; }}
  .nowlab {{ font-size:11px; fill:var(--ink2); text-anchor:end;
             font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .pt-in {{ fill:var(--series); stroke:var(--surface); stroke-width:2; }}
  .pt-out {{ fill:var(--surface); stroke:var(--series); stroke-width:1.75; }}
  .pt-last {{ fill:var(--series); stroke:var(--surface); stroke-width:2; }}
  .endlab {{ font-size:12px; fill:var(--ink); text-anchor:start; font-weight:600;
             font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .tick {{ font-size:11px; fill:var(--muted); font-variant-numeric:tabular-nums;
           font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .tick-l {{ text-anchor:end; }}
  .tick-r {{ text-anchor:start; }}
  .tick-x {{ text-anchor:middle; }}
  .axtitle {{ font-size:11.5px; fill:var(--muted); letter-spacing:.05em;
              text-transform:uppercase;
              font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .axtitle-l, .axtitle-r {{ text-anchor:middle; }}
  .hl {{ stroke:var(--ink2); stroke-width:1; opacity:0; }}
  .hp {{ fill:none; stroke:var(--ink); stroke-width:2; opacity:0; }}

  .ribwrap {{ margin:8px 0 2px; }}
  .riblab {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
             font-size:10.5px; letter-spacing:.09em; text-transform:uppercase;
             color:var(--muted); margin-bottom:5px; }}
  .rib {{ position:relative; height:9px; background:var(--xbg); border-radius:3px; }}
  .bout {{ position:absolute; top:0; height:9px; background:var(--axis); border-radius:2px; }}
  .bout.live {{ background:var(--series); }}

  .tip {{ position:absolute; pointer-events:none; opacity:0; transition:opacity .1s;
          background:var(--surface); border:1px solid var(--hair);
          border-radius:6px; padding:8px 10px; font-size:12px; min-width:172px;
          box-shadow:0 6px 22px rgba(0,0,0,.16); z-index:5; color:var(--ink); }}
  .tip .tv {{ font-size:15px; font-weight:640; margin-bottom:3px;
              font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .tip .tr {{ display:flex; justify-content:space-between; gap:14px; color:var(--ink2);
              font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
              font-variant-numeric:tabular-nums; }}
  .tip .tw {{ margin-top:5px; padding-top:5px; border-top:1px solid var(--hair);
              color:var(--muted); font-size:11.5px; }}

  .scroll {{ overflow-x:auto; border:1px solid var(--hair); border-radius:9px;
             background:var(--surface); }}
  table {{ border-collapse:collapse; width:100%; font-size:13px; }}
  th {{ text-align:left; font-size:10.5px; letter-spacing:.08em; text-transform:uppercase;
        color:var(--muted); font-weight:500; padding:10px 11px; white-space:nowrap;
        border-bottom:1px solid var(--hair);
        font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  th.n {{ text-align:right; }}
  td {{ padding:7px 11px; border-bottom:1px solid var(--grid); white-space:nowrap; }}
  tr:last-child td {{ border-bottom:none; }}
  tbody tr.ok {{ background:var(--okbg); }}
  td.strong {{ color:var(--ink); font-weight:640; }}
  td.shifted {{ color:var(--crit); }}
  .pill {{ font-size:10.5px; padding:2px 7px; border-radius:20px; white-space:nowrap;
           border:1px solid var(--hair); color:var(--ink2);
           font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  .pill.ok {{ color:var(--series); border-color:var(--series); }}

  ul {{ max-width:70ch; color:var(--ink2); font-size:14.5px; padding-left:20px; }}
  li {{ margin:7px 0; }}
  .foot {{ margin-top:34px; padding-top:16px; border-top:1px solid var(--hair);
           color:var(--muted); font-size:12px; }}
  .foot code {{ font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; }}
  @media (max-width:600px) {{ h1 {{ font-size:22px; }} .tile .val {{ font-size:22px; }} }}
</style>

<div class="wrap">
  <p class="eyebrow">PIMD · bench · {gen:%Y-%m-%d %H:%M} local</p>
  <h1>6S pack discharge under continuous classviz load</h1>
  <p class="sub">Reconstructed from the <span class="m">#&#8202;pack_v:</span> lines your
  session dumps already carry — {len(rows)} hand readings across today's
  {len(D['sessions'])} sessions, {n_fit} of them usable. Pack voltage is not telemetry:
  there is no voltage field in the serial protocol (DESIGN §9) and no sensing in
  firmware, so every point here is a DMM value you typed and pressed <em>Log V</em> on.
  {'' if cyc.get('n', 1) < 2 else
   f"This is <strong class='k'>charge cycle {cyc['analysed']}</strong> of "
   f"{cyc['n']} detected today — a recharge or pack swap starts a new one, and "
   f"fitting across it would be meaningless."}</p>

  <div class="tiles">
    <div class="tile"><div class="lab">last reading</div>
      <div class="val">{lr['volts']:.2f}<small> V</small></div>
      <div class="note">{lr['vcell']:.3f} V/cell · {lr['meas'][11:19]}</div></div>
    <div class="tile"><div class="lab">state of charge</div>
      <div class="val">{lr['soc']:.0f}<small> %</small></div>
      <div class="note">calibrated curve, not nominal</div></div>
    <div class="tile"><div class="lab">discharge rate</div>
      <div class="val">{abs(lin['slope_v_per_h']):.3f}<small> V/h</small></div>
      <div class="note">{abs(fit['soc_rate_pct_per_h']):.1f} %SoC/h · streaming</div></div>
    <div class="tile warn"><div class="lab">to 21.0 V floor</div>
      <div class="val">{'passed' if h_floor <= 0 else f'{h_floor:.1f}'}{
        '' if h_floor <= 0 else '<small> h</small>'}</div>
      <div class="note">{f'crossed about {abs(h_floor)*60:.0f} min of streaming ago'
        if h_floor <= 0 else 'of further streaming'}</div></div>
    <div class="tile"><div class="lab">pack runtime</div>
      <div class="val">{fit['T_h']:.1f}<small> h</small></div>
      <div class="note">full → empty, {T_lo/60:.1f}–{T_hi/60:.1f} h</div></div>
  </div>

  {warnbox}

  <div class="card">
    <div class="legend">
      <span><i class="sw mdl"></i>constant-current discharge (fitted)</span>
      <span><i class="sw prj"></i>projection beyond now</span>
      <span><i class="bandsw"></i>capacity uncertainty</span>
      <span><i class="dot i"></i>reading used in fit</span>
      <span><i class="dot o"></i>reading excluded</span>
      <span><i class="sw cr"></i>21.0 V working floor</span>
    </div>
    <div class="plot" id="plot">
      <svg viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-label="Pack state of charge against
        hours of classviz streaming since the pack was full. State of charge falls linearly
        from 100 percent to zero over {fit['T_h']:.1f} hours; the {len(rows)} logged voltage
        readings track that line. The right-hand voltage scale is non-linear.">
        {svg}
        <line class="hl" id="hl" y1="{TOP:.0f}" y2="{TOP+PH:.0f}"/>
        <circle class="hp" id="hp" r="7.5"/>
        <rect id="hit" x="{L:.0f}" y="{TOP:.0f}" width="{PW:.0f}" height="{PH:.0f}"
              fill="transparent"/>
      </svg>
      <div class="tip" id="tip"></div>
    </div>
    <div class="ribwrap">
      <div class="riblab">load on — today's stream bouts, in the same streaming-time axis</div>
      <div class="rib">{ribbon}</div>
    </div>
  </div>

  <h2>Why the state-of-charge line is straight, and the voltage scale isn't</h2>
  <p>The classviz profile loop draws a fixed duty, so the current is constant — and under
  constant current, charge drains linearly in time. That makes state of charge a
  <strong class="k">straight line by construction</strong>, and it is the reason the
  readings are plotted against <em>streaming</em> minutes rather than wall clock. The
  right-hand voltage scale is the same axis relabelled through the cell curve, so its
  ticks bunch up through the plateau: <strong class="k">that compression is the pack's
  plateau made visible</strong>, and it is why voltage alone is a poor fuel gauge here.</p>

  <p>Rather than trust a datasheet curve, the shape was
  <strong class="k">auto-calibrated against your own readings</strong> — two free
  parameters, the streaming time to full discharge and a curve-alignment offset, fitted to the
  {n_fit} settled readings. Result: <strong class="k">{T:.0f} streaming minutes
  ({fit['T_h']:.2f} h) full to empty</strong> with
  a <strong class="k">{fit['curve_offset_v_per_cell']*1000:.0f} mV/cell</strong>
  curve-alignment offset, residual RMS {fit['rmse_v']*1000:.0f} mV. That offset is why the
  right-hand scale tops out near {full_v - off_pack:.1f} V rather than {full_v:.1f} V.</p>

  <p><strong class="k">The offset is not the pack's internal resistance</strong>, and is worth
  being explicit about because it looks like it should be. Measured directly, this pack sags
  about <strong class="k">0.29 V</strong> under load — 25.04 V open-circuit, 24.75 V running.
  The fit wants {off_pack:.2f} V, roughly three times that, so most of it is the assumed
  ICR18650 curve not quite matching these cells rather than anything electrical. The practical
  consequence: <strong class="k">trust the runtime the fit implies, not the curve's shape</strong>,
  and read the voltage scale as an alignment of a nominal curve rather than a measured one.</p>

  {cvtext}

  <h2>What the log needed before it could be read</h2>
  <ul>
    <li><strong class="k">age_s has to be applied.</strong> A dump's header
    <span class="m">#&#8202;pack_v:</span> line is the spinbox value restored at session
    open, not a fresh measurement. The live session's opens at
    <span class="m">22.25, age_s=5659</span> — measured at 15:36, 95 min before that
    session existed. Correcting this recovers one genuine reading and collapses two
    phantom duplicates.</li>
    <li><strong class="k">Wall clock would flatten the slope.</strong> Across the
    {idle.get('idle_h', 0):.1f} h gap between sessions the pack fell
    {abs(idle.get('dv', 0)):.2f} V
    — <strong class="k">{idle.get('v_per_h', 0):.3f} V/h</strong> idle against
    {abs(lin['slope_v_per_h']):.3f} V/h streaming, a
    <strong class="k">{ratio:.0f}×</strong> ratio. Only load-on time belongs on the
    axis.</li>
    <li><strong class="k">Readings taken just after the stream starts sit high.</strong>
    They are rested voltage, not settled-under-load: 15:01:45 reads 22.85 V, above
    12:38's 22.56 V, after a 2 h rest. Anything within
    {D['params']['rested_min']:.0f} min of load-on is excluded from the fit and drawn
    hollow.</li>
  </ul>

  <h2>Where this could be wrong</h2>
  <ul>
    <li><strong class="k">x = 0 assumes the pack was full when today's first session
    began ({D['sessions'][0]['first'][11:16]}).</strong> No voltage was logged before
    11:29, so nothing in the data confirms it. If the pack started the day already down,
    the fitted runtime is not full-pack capacity but a scaled equivalent, and every
    projection shifts with it.</li>
    <li><strong class="k">The cell count per parallel string is unconfirmed.</strong> The
    {D['implied_ah_at_0p5A']:.2f} Ah cross-check only <em>suggests</em> 6S2P; the readings
    constrain the pack's behaviour, not its construction.</li>
    <li><strong class="k">A nominal ICR18650 shape underlies the calibration.</strong> The
    two fitted parameters stretch and offset that shape but cannot change it, and the
    residuals do carry a slight systematic S — tens of millivolts, largest at the
    ends of the fitted span.</li>
    <li><strong class="k">The terminal knee is extrapolated, not observed.</strong> Your
    readings stop at {lr['volts']:.2f} V; everything below is the curve's shape, not
    measurement. A straight extrapolation of the voltage trend instead of the curve puts
    21.0 V at {h_lin_21:.1f} h away rather than {h_floor:.1f} h — treat that as
    the optimistic bound.</li>
  </ul>

  <h2>Segment rates <span class="cnt">· consecutive fitted readings</span></h2>
  <p>The early figures are load-onset sag, not discharge — which is why a single rate
  over the whole day would mislead. The last several hold near
  {abs(lin['slope_v_per_h']):.2f} V/h.</p>
  <div class="scroll"><table><thead><tr>
    <th>between (measured)</th><th class="n">stream min</th><th class="n">ΔV</th>
    <th class="n">V/h</th></tr></thead><tbody>
  {segtable}
  </tbody></table></div>

  <h2>All readings <span class="cnt">· {len(rows)} logged, {n_fit} in fit</span></h2>
  <div class="scroll"><table><thead><tr>
    <th>logged</th><th>measured</th><th class="n">age_s</th><th class="n">V</th>
    <th class="n">V/cell</th><th class="n">SoC %</th><th class="n">stream min</th>
    <th class="n">min into bout</th><th>status</th></tr></thead><tbody>
  {table}
  </tbody></table></div>

  <h2>Sessions read</h2>
  <div class="scroll"><table><thead><tr>
    <th>dump</th><th>data rows span</th><th class="n">min</th>
    <th class="n">pack_v lines</th></tr></thead><tbody>
  {sess_rows}
  </tbody></table></div>

  <p class="foot">Read-only from <code>src/data/sessions/session_*.csv</code>
  · fw {D['sessions'][-1]['fw']} · profile
  <code>{D['sessions'][-1]['profile']}</code> · total streaming today
  {now_x:.0f} min ({now_x/60:.2f} h) · floors from DESIGN §12 · generated by
  <code>packv.py {D.get('tool_version','?')}</code> +
  <code>build_page.py {TOOL_VERSION}</code>. No repo files were changed.</p>
</div>

<script>
const PTS = {PTS};
const VB = {{w:{W:.0f}, h:{H:.0f}}};
const plot = document.getElementById('plot');
const svg  = plot.querySelector('svg');
const hit  = document.getElementById('hit');
const hl   = document.getElementById('hl');
const hp   = document.getElementById('hp');
const tip  = document.getElementById('tip');

function show(e) {{
  const r = svg.getBoundingClientRect();
  const sx = (e.clientX - r.left) * VB.w / r.width;
  let best = null, bd = Infinity;
  for (const p of PTS) {{
    const d = Math.abs(p.x - sx);
    if (d < bd) {{ bd = d; best = p; }}
  }}
  if (!best) return;
  hl.setAttribute('x1', best.x); hl.setAttribute('x2', best.x);
  hl.style.opacity = .45;
  hp.setAttribute('cx', best.x); hp.setAttribute('cy', best.y);
  hp.style.opacity = 1;
  tip.innerHTML =
    '<div class="tv">' + best.v.toFixed(2) + ' V &middot; ' + best.soc.toFixed(1) + ' %</div>' +
    '<div class="tr"><span>per cell</span><span>' + best.vc.toFixed(3) + ' V</span></div>' +
    '<div class="tr"><span>measured</span><span>' + best.meas + '</span></div>' +
    '<div class="tr"><span>logged</span><span>' + best.logged +
      (best.age === null ? '' : ' (+' + best.age + 's)') + '</span></div>' +
    '<div class="tr"><span>streaming</span><span>' + best.sx.toFixed(1) + ' min</span></div>' +
    '<div class="tw">' + best.why + '</div>';
  tip.style.opacity = 1;
  const cx = best.x / VB.w * r.width, cy = best.y / VB.h * r.height;
  const tw = tip.offsetWidth, th = tip.offsetHeight;
  let tx = cx + 16; if (tx + tw > r.width) tx = cx - tw - 16;
  let ty = cy - th / 2; ty = Math.max(2, Math.min(ty, r.height - th - 2));
  tip.style.left = tx + 'px'; tip.style.top = ty + 'px';
}}
function hide() {{
  hl.style.opacity = 0; hp.style.opacity = 0; tip.style.opacity = 0;
}}
hit.addEventListener('mousemove', show);
hit.addEventListener('mouseleave', hide);
hit.addEventListener('touchmove', e => {{ if (e.touches[0]) show(e.touches[0]); }},
                     {{passive:true}});
</script>
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json', default=os.path.join(HERE, 'packv.json'),
                    help='packv.py output (default: packv.json beside this script)')
    ap.add_argument('--out', default=os.path.join(HERE, 'pack-discharge.html'),
                    help='HTML to write (default: pack-discharge.html beside this script)')
    args = ap.parse_args()

    if not os.path.exists(args.json):
        raise SystemExit(f'{args.json} not found — run:  python packv.py --out {args.json}')
    with open(args.json) as fh:
        D = json.load(fh)
    page = build(D)
    with open(args.out, 'w') as fh:
        fh.write(page)
    print(f'wrote {args.out}  ({len(page)} bytes)')


if __name__ == '__main__':
    main()
