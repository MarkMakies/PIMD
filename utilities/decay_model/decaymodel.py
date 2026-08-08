#!/usr/bin/env python3
"""Air / target decay at the RX front end, model vs measurement, 4 us -> 300 us.
TOOL_VERSION = v5

# History (full detail in CHANGELOG.md):
#   v5 model refitted to the scope trace at the amplifier input; below-rail
#      reconstruction added; comments trimmed
#   v4 roles from material_class; probe column auto-chosen; text from the session
#   v3 --session prefers acquire/acquire-end brackets; plateau is the fallback
#   v2 --session overlay of measured air/ferrous/non-ferrous
#   v1 critically-damped fit to the cal_63 ladder

The model is now MEASURED, not inferred
---------------------------------------
v1-v4 fitted air to the calibrated cal_63 ladder, which only samples the
volt-scale region, and extrapolated past it -- badly: fits agreeing with that
ladder to <=2 % predicted anywhere from +64 to -400 mV at sd 14.7 us.  v5 drops
that and fits the 2026-08-08 scope capture of the LT6203 input directly, which
covers the whole decay including the part the ADC cannot see.

Two real poles with opposite-sign residues, s(t) = A.exp(-t/tf) - B.exp(-t/ts),
plus the measured quiescent DC.  Parameters below are the fit; the RX component
values they imply are an independent check, not an input:

    tau_fast 1.125 us, tau_slow 2.270 us  ->  zeta 1.06, mildly OVERDAMPED
    with R1 = 1.3k:  C = 579 pF, L = 4.41 mH, sqrt(L/C) = 2762 ohm
    -> R_crit = 1381 ohm, against DESIGN Sec 7's MEASURED 1300-1400 ohm.

That agreement is the reason to trust the fit.  It also supersedes v1's "zeta =
1.00": that came from assuming the critically-damped form and fitting tau = 2RC
to it, which cannot report anything else.

What the ADC cannot see, and why the reconstruction exists
---------------------------------------------------------
The signal path is unipolar, so the LT6203 output saturates at ~2.44 mV and the
air trace is CLIPPED through the null.  The scope measures the input, where
nothing is clipped, so multiplying it by the input->ADC gain reconstructs what
the ADC would have recorded with no rail.  Air really reaches about -17 mV in
ADC terms against a 16.47 mV pedestal.  This matters beyond curiosity: where air
is railed the recorded target delta is compressed by up to 3.5x, because
delta = target - air and the air baseline has been clipped upward.

Measured inputs, all 2026-08-08, 2 kHz / 100 us band:
  * scope, LT6203 input: air and steel spanner at 0 mm, 83 traces averaged each,
    scatter 0.3 / 0.6 mV.  Quiescent +14.34 mV.  MCLK-edge ring masked +-250 ns.
  * ADC, rawlog_20260808_145702: air / copper / steel, bracketed segments.
  * input->ADC gain 1.149, from the two quiescent levels (16.472 / 14.34).
"""

import argparse
import json
import os
import shlex
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullFormatter

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.join(HERE, "..", "..", "src", "data", "profiles")
SCOPE = os.path.join(HERE, "..", "..", "References", "scope")

# --- measured constants (2026-08-08, 2 kHz / 100 us) -------------------------
RAIL_MV = 2.441        # LT6203 output saturation, sigma exactly 0 in every class
CLAMP_MV = 4999.0      # input clamp / ADC full scale
PED_ADC_MV = 16.472    # ADC quiescent (air, sd > 40 us)
PED_IN_MV = 14.34      # amplifier-input quiescent (scope, sd > 60 us)
GAIN = PED_ADC_MV / PED_IN_MV
NOISE_MV = 0.08        # air sigma on the settled cells

# --- v5 air model, fitted to the scope trace at the amplifier input ----------
A_MV, TAU_F_US = 2.580e7, 1.125
B_MV, TAU_S_US = 5.047e4, 2.270

C_AIR, C_FE, C_NONFE = "#2a78d6", "#eb6834", "#1baf7a"
C_FLAG = "#e34948"
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#8a8880"
GRID, SURF = "#e3e2dd", "#fcfcfb"


def air_input_mv(sd_us):
    """Modelled air at the LT6203 input: two real poles + the quiescent DC."""
    return (A_MV * np.exp(-sd_us / TAU_F_US)
            - B_MV * np.exp(-sd_us / TAU_S_US) + PED_IN_MV)


def to_adc(v_in_mv, clip=True):
    """Amplifier input -> ADC reading. `clip=False` gives the below-rail value."""
    v = v_in_mv * GAIN
    return np.clip(v, RAIL_MV, CLAMP_MV) if clip else v


def load_band(profile, pulse_us):
    p = json.load(open(os.path.join(PROFILES, profile + ".json")))
    for b in p["bands"]:
        if abs(b["pulse_us"] - pulse_us) < 1e-6:
            return b
    raise KeyError(f"{pulse_us} us band not in {profile}")


def load_scope(path=None):
    """The 2026-08-08 paired scope capture: sample delay, air, spanner (mV)."""
    path = path or os.path.join(SCOPE, "spanner_vs_air_20260808.csv")
    d = np.loadtxt(path, delimiter=",", skiprows=1)
    sd, air, spanner = d[:, 0], d[:, 1], d[:, 2]
    ring = np.abs(sd - 15.5) < 0.25          # MCLK-edge crosstalk, not signal
    clipped = air > 85.5                     # screen top at 20 mV/div
    keep = ~ring & ~clipped
    return sd[keep], air[keep], spanner[keep]


def load_scope_wide(path=None):
    """The 10 µs/div air capture — same node, out to sd 100 µs for the tail.

    One acquisition rather than 83 averaged, so it carries the raw 0.68 mV
    quantisation step; smooth before reading anything off it.
    """
    path = path or os.path.join(SCOPE, "air_wide_20260808.csv")
    d = np.loadtxt(path, delimiter=",", skiprows=1)
    sd, v = d[:, 0], d[:, 1]
    keep = np.abs(sd - 15.5) >= 0.25          # same MCLK-edge ring
    return sd[keep], v[keep]


def smooth(x, y, n=51):
    """Moving average with the ends trimmed — `mode='same'` tapers them toward
    zero, which on a trace sitting at +14 mV invents a step that isn't there."""
    k = n // 2
    return x[k:-k], np.convolve(y, np.ones(n) / n, mode="same")[k:-k]


def load_session(path, profile_name, band_pulse_us, probe_col=None,
                 start_skip_s=20.0, guard_s=8.0, seed_halfwidth_s=20.0):
    """Read a `pimd_rawlog` session; return per-class means for one band.

    Two segmentation modes, chosen by what the log contains:

      bracketed  -- log has `MARK acquire end` (pimd_rawlog v1.16+). Segments are
                    read verbatim between their markers; nothing is inferred.
      plateau    -- fallback for older logs, which have no end markers. Marks only
                    locate each excursion; the window is the top 80 % of the
                    excursion in a probe cell, air is everything outside plus a
                    guard. Inferring the extent is what this replaces: a mark
                    pressed mid-presentation stays in force after the target is
                    lifted, which halved a measured delta in the 2026-08-07 log.

    W lines are `W<idx>,<time_ms>,<ch0>,...` in µV, re-parsed here rather than
    imported because pimd_rawlog pulls in PyQt6.

    Returns (delays_us, {label: (mean, sd, n, pretty, material, distance)},
    windows, (mode, warnings, t0)).
    """
    prof = json.load(open(os.path.join(PROFILES, profile_name + ".json")))
    bands = prof["bands"]
    off, nch = 0, 0
    for b in bands:
        if abs(b["pulse_us"] - band_pulse_us) < 1e-6:
            off, nch = nch, len(b["delays_us"])
            delays = b["delays_us"]
            break
        nch += len(b["delays_us"])
    else:
        raise KeyError(f"{band_pulse_us} us band not in {profile_name}")
    total = sum(len(b["delays_us"]) for b in bands)

    times, vals, marks, ends = [], [], [], []
    with open(path) as fh:
        for line in fh:
            try:
                ts, tag, text = line.rstrip("\n").split(" ", 2)
            except ValueError:
                continue
            if tag == "RAW" and text.startswith("W"):
                try:
                    _, rest = text.split(",", 1)
                    _ms, chans = rest.split(",", 1)
                    v = [float(x) for x in chans.split(",")]
                except ValueError:
                    continue
                if len(v) == total:
                    times.append(datetime.fromisoformat(ts))
                    vals.append(v)
            elif tag == "MARK":
                if text.startswith("acquire end"):
                    f = dict(tok.split("=", 1)
                             for tok in shlex.split(text[len("acquire end"):])
                             if "=" in tok)
                    ends.append((datetime.fromisoformat(ts), f))
                elif text.startswith("acquire target "):
                    f = dict(tok.split("=", 1)
                             for tok in shlex.split(text[len("acquire target "):])
                             if "=" in tok)
                    marks.append((datetime.fromisoformat(ts),
                                  f.get("target_id", "target"),
                                  f.get("short_name", "").strip('"'),
                                  f.get("material_class", "").strip('"').lower(),
                                  f.get("distance_mm", "").strip('"')))
                elif text.startswith("acquire air"):
                    marks.append((datetime.fromisoformat(ts), "air", "air", "air", ""))
    if not times:
        raise ValueError(f"no usable W records in {path}")

    t0 = times[0]
    T = np.array([(t - t0).total_seconds() for t in times])
    V = np.array(vals)[:, off:off + nch] / 1000.0          # µV -> mV
    # Choosing the probe column automatically is not a nicety. A fixed index is
    # only valid for the profile it was picked on: index 3 is a good post-rail
    # cell in cal_110's 150 us band and a CLAMPED cell in the 100 us sweep, where
    # it is constant, has no excursion to find, and takes the whole session as
    # one active run -- leaving no air frames at all.
    if probe_col is None:
        med = np.median(V, axis=0)
        mad = np.median(np.abs(V - med), axis=0)
        span = np.percentile(V, 98, axis=0) - med
        usable = (med < CLAMP_MV * 0.5) & (mad > 0)
        score = np.where(usable, span / (mad + 1e-9), -np.inf)
        probe_col = int(np.argmax(score))
    probe = V[:, probe_col]
    base = np.median(probe)

    # ---------------------------------------------------------------- bracketed
    if ends:
        out, windows, warnings = {}, [], []
        parts = {}                                    # label -> [row blocks]
        pretty_of = {}
        used_ends = 0
        for mt, label, pretty, material, dist in marks:
            nxt = [e for e in ends if e[0] >= mt]
            if not nxt:
                warnings.append(f"{label}: start at {(mt - t0).total_seconds():.1f} s "
                                f"has no end marker (log ends mid-capture) — skipped")
                continue
            et, ef = nxt[0]
            used_ends += 1
            ta = (mt - t0).total_seconds()
            tb = (et - t0).total_seconds()
            sel = np.where((T > ta) & (T <= tb))[0]
            if len(sel) == 0:
                warnings.append(f"{label}: bracket {ta:.1f}–{tb:.1f} s contains no frames "
                                f"— skipped")
                continue
            # The marker states what the logger thought it captured; disagreeing
            # with the frames actually inside the bracket means one of the two is
            # wrong, and silently trusting either would be the same mistake this
            # whole path exists to avoid.
            claimed = ef.get("frames")
            if claimed is not None and int(claimed) != len(sel):
                warnings.append(f"{label}: marker says frames={claimed} but "
                                f"{len(sel)} lie inside the bracket")
            if ef.get("complete") == "no":
                warnings.append(f"{label}: capture incomplete "
                                f"({ef.get('frames')}/{ef.get('requested')}, "
                                f"reason={ef.get('reason', '?')}) — kept, but short")
            got = ef.get("target_id", "air" if ef.get("mode") == "air" else None)
            if got is not None and got != label:
                warnings.append(f"{label}: end marker names {got} — pairing looks wrong")
            parts.setdefault(label, []).append(V[sel])
            pretty_of.setdefault(label, (pretty or label, material, dist))
            windows.append((label, float(T[sel[0]]), float(T[sel[-1]])))
        if len(ends) > used_ends:
            warnings.append(f"{len(ends) - used_ends} end marker(s) had no start — ignored")
        for label, blocks in parts.items():
            blk = np.vstack(blocks)
            nice, material, dist = pretty_of[label]
            out[label] = (blk.mean(0), blk.std(0), len(blk), nice, material, dist)
        if "air" not in out:
            raise ValueError(f"{os.path.basename(path)}: bracketed log has no air "
                             f"segment — nothing to subtract targets against")
        return delays, out, windows, ("bracketed", warnings, times[0])

    # ------------------------------------------------------------------ plateau

    # Group consecutive marks carrying the same label -- a repeated press is the
    # same presentation re-affirmed, not a second one.
    groups = []
    for mt, label, pretty, material, dist in marks:
        ts = (mt - t0).total_seconds()
        if groups and groups[-1][0] == label:
            continue
        groups.append((label, ts, pretty, material, dist))

    out, windows = {}, []
    active = np.zeros(len(T), dtype=bool)
    for label, ts, pretty, material, dist in groups:
        if label == "air":
            continue
        # Seed search is deliberately narrow and skips frames an earlier
        # presentation already claimed -- otherwise a strong target's decaying
        # tail out-peaks the next, weaker target and both windows land on the
        # same excursion.
        near = np.where((np.abs(T - ts) <= seed_halfwidth_s) & ~active)[0]
        if len(near) < 5:
            continue
        pk = near[np.argmax(probe[near])]
        thresh = base + 0.80 * (probe[pk] - base)
        a = b_ = pk
        while a > 0 and probe[a - 1] >= thresh and not active[a - 1]:
            a -= 1
        while b_ + 1 < len(T) and probe[b_ + 1] >= thresh and not active[b_ + 1]:
            b_ += 1
        if b_ - a < 3:
            continue
        active[a:b_ + 1] = True
        block = V[a:b_ + 1]
        out[label] = (block.mean(0), block.std(0), len(block), pretty, material, dist)
        windows.append((label, float(T[a]), float(T[b_])))

    air_mask = ~active & (T >= start_skip_s)
    for _, ta, tb in windows:
        air_mask &= ~((T >= ta - guard_s) & (T <= tb + guard_s))
    blk = V[air_mask]
    out["air"] = (blk.mean(0), blk.std(0), len(blk), "air", "air", "")
    windows.insert(0, ("air", float(T[air_mask][0]), float(T[air_mask][-1])))
    return delays, out, windows, ("plateau", [
        "log has no `MARK acquire end` lines (pre-pimd_rawlog-v1.16), so segment "
        "extents are INFERRED from the probe cell, not recorded"], times[0])
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "decay_model.png"))
    ap.add_argument("--pulse", type=float, default=100.0)
    ap.add_argument("--session", default=None,
                    help="pimd_rawlog session .txt to overlay as measured points")
    ap.add_argument("--profile", default="sweep_100us_asbuilt_20260808",
                    help="profile the session was streamed with (channel layout)")
    args = ap.parse_args()

    sd_s, air_s, span_s = load_scope()
    sd_w, air_w = load_scope_wide()
    print(f"scope: {len(sd_s)} points, sd {sd_s.min():.2f}-{sd_s.max():.2f} µs "
          f"(ring and clipped samples removed)")
    print(f"model: tau_f {TAU_F_US} µs, tau_s {TAU_S_US} µs, gain {GAIN:.3f}, "
          f"pedestal {PED_ADC_MV} mV, rail {RAIL_MV} mV")
    resid = air_input_mv(sd_s) - air_s
    print(f"  model vs scope air: RMS {np.sqrt(np.mean(resid**2)):.2f} mV, "
          f"max |resid| {np.abs(resid).max():.2f} mV")

    meas = None
    if args.session:
        m_delays, m_cls, m_win, (m_mode, m_warn, m_t0) = load_session(
            args.session, args.profile, args.pulse)
        FERROUS = {"steel", "iron", "ferrous", "cast_iron"}
        tgts = [k for k in m_cls if k != "air"]
        fe = [k for k in tgts if m_cls[k][4] in FERROUS]
        nfe = [k for k in tgts if m_cls[k][4] not in FERROUS]
        order = ["air"] + fe + nfe
        meas = (m_delays, m_cls, order, len(fe))
        print(f"\nsession [{m_mode}]: " +
              ", ".join(f"{m_cls[k][3]} n={m_cls[k][2]}" for k in order))
        for w_ in m_warn:
            print(f"  ! {w_}")

    # ---- what the rail hides -------------------------------------------------
    true_adc = to_adc(air_s, clip=False)
    seen_adc = to_adc(air_s, clip=True)
    hidden = true_adc < RAIL_MV
    if hidden.any():
        print(f"\nbelow the rail: air really reaches {true_adc.min():+.1f} mV in ADC "
              f"terms (recorded as {RAIL_MV}), over sd "
              f"{sd_s[hidden].min():.2f}-{sd_s[hidden].max():.2f} µs "
              f"({sd_s[hidden].max()-sd_s[hidden].min():.2f} µs wide)")
    zc = [sd_s[i] for i in range(len(sd_s)-1)
          if (air_s[i]-PED_IN_MV) > 0 >= (air_s[i+1]-PED_IN_MV)]
    if zc:
        print(f"signal crosses its own quiescent level at sd {zc[0]:.2f} µs "
              f"(single crossing — the two-real-pole signature)")

    # ------------------------------------------------------------------ figure
    plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": INK3,
        "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "axes.linewidth": 0.8, "figure.facecolor": SURF, "axes.facecolor": SURF})
    fig = plt.figure(figsize=(13.2, 9.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.2, 1.0], hspace=0.30, wspace=0.20,
                          left=0.075, right=0.975, top=0.835, bottom=0.075)
    axA = fig.add_subplot(gs[0, :]); axB = fig.add_subplot(gs[1, 0])
    axC = fig.add_subplot(gs[1, 1])

    tm = np.logspace(np.log10(7.0), np.log10(300.0), 6000)
    mdl_in = air_input_mv(tm)

    # ---- A: full span, ADC domain, symlog so the below-rail part is visible
    axA.set_xscale("log"); axA.set_yscale("symlog", linthresh=2.0, linscale=0.32)
    axA.axhline(PED_ADC_MV, color=INK3, lw=1.0, ls=(0, (5, 3)), zorder=2)
    axA.axhline(RAIL_MV, color=C_FLAG, lw=0.9, ls=(0, (2, 3)), zorder=2)
    axA.plot(tm, to_adc(mdl_in, clip=False), color=INK3, lw=1.3, ls=(0, (4, 3)),
             zorder=5, label="v5 model, unclipped")
    axA.plot(sd_s, to_adc(air_s, clip=False), color=C_AIR, lw=1.5, alpha=0.55,
             zorder=6, label="scope × gain — what the ADC would read (no rail)")
    axA.plot(sd_s, to_adc(air_s, clip=True), color=C_AIR, lw=2.0, zorder=7,
             label="scope × gain, clipped at the rail")
    tail = sd_w > sd_s.max()
    xw, yw = smooth(sd_w[tail], air_w[tail])
    axA.plot(xw, to_adc(yw, clip=True), color=C_AIR, lw=1.4, alpha=0.7, zorder=6)
    if meas:
        m_delays, m_cls, order, n_fe = meas
        cols = [C_AIR] + [C_FE]*n_fe + [C_NONFE]*(len(order)-1-n_fe)
        for lab, col in zip(order, cols):
            mv, sd_, n, pretty, mat, dist = m_cls[lab]
            axA.plot(m_delays, mv, "o", ms=5.5, mfc=col, mec=SURF, mew=1.1,
                     zorder=9, label=f"{pretty} ({mat or 'air'}) — ADC")
    axA.set_xlim(7, 300); axA.set_ylim(-24, 7000)
    axA.set_xticks([7, 10, 15, 20, 30, 50, 70, 100, 150, 250])
    axA.set_xticklabels(["7","10","15","20","30","50","70","100","150","250"])
    axA.xaxis.set_minor_formatter(NullFormatter())
    axA.set_yticks([-20, -10, 0, 2.441, 16.472, 100, 1000, 4999])
    axA.set_yticklabels(["−20","−10","0","2.44 rail","16.47 pedestal","100","1000","4999"])
    axA.yaxis.set_minor_formatter(NullFormatter())
    axA.set_xlabel("sample delay after coil turn-off  (µs, log)")
    axA.set_ylabel("ADC reading  (mV, symlog)")
    axA.grid(True, which="major", color=GRID, lw=0.7, zorder=0)
    axA.annotate("everything below this line is\nreconstructed — the ADC cannot see it",
                 xy=(16.8, -14), xytext=(30, -8), color=C_FLAG, fontsize=8.5,
                 arrowprops=dict(arrowstyle="->", color=C_FLAG, lw=0.9))
    leg = axA.legend(loc="lower right", frameon=False, fontsize=8.2, ncol=1,
                     bbox_to_anchor=(0.995, 0.0))
    for t_ in leg.get_texts(): t_.set_color(INK2)
    axA.set_title("Air decay in ADC terms — measured, modelled, and the part the rail hides",
                  color=INK, fontsize=11.5, loc="left", pad=10)

    # ---- B: the null, linear, where model and measurement can be compared
    axB.axhline(PED_ADC_MV, color=INK3, lw=1.0, ls=(0, (5, 3)), zorder=2)
    axB.axhline(RAIL_MV, color=C_FLAG, lw=0.9, ls=(0, (2, 3)), zorder=2)
    axB.fill_between(sd_s, to_adc(air_s, clip=False), RAIL_MV,
                     where=to_adc(air_s, clip=False) < RAIL_MV,
                     color=C_FLAG, alpha=0.13, zorder=3)
    axB.plot(sd_s, to_adc(air_s, clip=False), color=C_AIR, lw=2.0, zorder=6,
             label="scope × gain (true)")
    axB.plot(tm, to_adc(air_input_mv(tm), clip=False), color=INK3, lw=1.4,
             ls=(0, (4, 3)), zorder=5, label="v5 model")
    axB.plot(sd_s, to_adc(span_s, clip=False), color=C_FE, lw=1.6, alpha=0.85,
             zorder=6, label="spanner on the coil")
    if meas:
        m_delays, m_cls, order, n_fe = meas
        axB.plot(m_delays, m_cls["air"][0], "o", ms=6, mfc=C_AIR, mec=SURF,
                 mew=1.2, zorder=9, label="air as the ADC records it")
    axB.set_xlim(12, 24); axB.set_ylim(-22, 60)
    axB.set_xlabel("sample delay  (µs)"); axB.set_ylabel("ADC reading  (mV)")
    axB.grid(True, color=GRID, lw=0.7, zorder=0)
    axB.annotate(f"air really reaches {to_adc(air_s, clip=False).min():.0f} mV;\n"
                 f"the ADC records {RAIL_MV} mV",
                 xy=(15.8, to_adc(air_s, clip=False).min()), xytext=(17.6, -18),
                 color=C_FLAG, fontsize=8,
                 arrowprops=dict(arrowstyle="->", color=C_FLAG, lw=0.9))
    axB.set_title("The null, and how much of it the rail removes",
                  color=INK, fontsize=9.5, loc="left", pad=6)
    leg = axB.legend(loc="upper right", frameon=False, fontsize=8)
    for t_ in leg.get_texts(): t_.set_color(INK2)

    # ---- C: model residual against the scope
    axC.axhline(0, color=INK3, lw=1.0, ls=(0, (5, 3)), zorder=2)
    axC.plot(sd_s, air_input_mv(sd_s) - air_s, color=C_AIR, lw=1.5, zorder=6)
    axC.axhspan(-NOISE_MV*GAIN, NOISE_MV*GAIN, color=INK3, alpha=0.25, lw=0, zorder=1)
    xr, yr = smooth(sd_w[tail], air_input_mv(sd_w[tail]) - air_w[tail])
    axC.plot(xr, yr, color=C_AIR, lw=1.2, alpha=0.6, zorder=5)
    print(f"  tail (sd {xr.min():.0f}-{xr.max():.0f} µs): mean residual "
          f"{yr.mean():+.2f} mV — the model runs slightly below the measured tail")
    axC.set_xlim(12, 100); axC.set_xscale("log")
    axC.set_xticks([12, 15, 20, 30, 50, 70, 100])
    axC.set_xticklabels(["12","15","20","30","50","70","100"])
    axC.xaxis.set_minor_formatter(NullFormatter())
    axC.set_ylim(-4, 4)
    axC.set_xlabel("sample delay  (µs, log)")
    axC.set_ylabel("model − scope  (mV at the input)")
    axC.text(0.985, 0.06, "grey band = ±1σ of the settled air noise",
             transform=axC.transAxes, ha="right", color=INK3, fontsize=7.6)
    axC.grid(True, which="major", color=GRID, lw=0.7, zorder=0)
    axC.set_title("v5 residual: RMS %.2f mV across sd %.0f–%.0f µs"
                  % (np.sqrt(np.mean(resid**2)), sd_s.min(), sd_s.max()),
                  color=INK, fontsize=9.5, loc="left", pad=6)

    fig.text(0.062, 0.945, "Model fitted to the 2026-08-08 scope capture at the "
             "LT6203 input, not to the calibrated ladder — τ_fast %.3f µs, τ_slow "
             "%.3f µs, ζ = 1.06 (mildly overdamped)."
             % (TAU_F_US, TAU_S_US), color=INK2, fontsize=9.2)
    fig.text(0.062, 0.912, "Implied RX values are an independent check, not an "
             "input: C = 579 pF, L = 4.41 mH → R_crit = 1381 Ω, against DESIGN §7's "
             "measured 1300–1400 Ω.", color=INK, fontsize=9.2)
    fig.text(0.062, 0.879, "Input → ADC gain %.3f, from the two quiescent levels "
             "(%.2f mV at the input, %.3f mV at the ADC). MCLK-edge ring masked "
             "±250 ns; clipped scope samples removed."
             % (GAIN, PED_IN_MV, PED_ADC_MV), color=INK3, fontsize=8.5)
    fig.savefig(args.out, dpi=150)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
