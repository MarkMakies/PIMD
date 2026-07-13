# SPDX-License-Identifier: GPL-3.0-or-later
###############################################################################
# pimd_v2_findings.py v1.0 — reproduction script for ML_Findings_v2.md
#
# Every number in ML_Findings_v2.md (findings F12-F21) is printed by this
# script from the campaign-2 corpus alone; no value is chat-derived (closes
# the "open gaps" pattern flagged in ML_FINDINGS.md v1.0).
#
# Usage:
#   python pimd_v2_findings.py PIMD_target_corpus_signatures_v2.csv <outdir>
#
# Requires numpy, pandas, scikit-learn, matplotlib (already in
# src/requirements.txt since the 2026-07-07 update).
#
# Conventions match pimd_corpus_check.py: long-format corpus, shape vector =
# 72 delta_mV cells sorted (pulse_us ascending, threshold_v descending);
# SNR = plateau_amp_mV / splithalf_floor (both L2, pimd_features.py v5).
# Canary rows are excluded from all per-target analysis, used only in the
# canary section. Usable set = SNR >= 10 (same gate as SPLITHALF_SNR_MIN).
###############################################################################
import sys, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

SNR_GATE = 10.0

# family labels (three-family convention of ML_FINDINGS F6; assignments per
# the crossing-continuum data in finding F13 — see doc for the edge cases)
FAM3 = {'steel spanner': 'ferrous', 'galvanized pipe': 'ferrous',
        'stainless scissors': 'ferrous',
        'cast iron trivet': 'crossover', 'stainless steel disc': 'crossover',
        'lead pipe': 'crossover',
        'copper pipe': 'non-ferrous', 'aluminium plate': 'non-ferrous',
        'silver cake server': 'non-ferrous', 'brass block': 'non-ferrous',
        'solder': 'non-ferrous'}
FAMCOL = {'ferrous': 'tab:red', 'crossover': 'tab:purple',
          'non-ferrous': 'tab:blue'}


def norm(v):
    return v / np.linalg.norm(v)


def cosv(a, b):
    return float(np.dot(norm(a), norm(b)))


def load(path):
    df = pd.read_csv(path, comment='#')
    pulses = np.array(sorted(df['pulse_us'].unique()))
    sigs = {}
    for (s, t, d), g in df.groupby(['session', 'target', 'distance_cm']):
        g = g.sort_values(['pulse_us', 'threshold_v'],
                          ascending=[True, False])
        assert len(g) == 72, f"{(s, t, d)}: {len(g)} cells"
        sigs[(s, t, int(d))] = dict(
            shape=g['delta_mV'].to_numpy(float),
            amp=float(g['plateau_amp_mV'].iloc[0]),
            sh=float(g['splithalf_floor'].iloc[0]),
            q=str(g['quality'].iloc[0]))
    return sigs, pulses


def bandmeans(v):
    return v.reshape(8, 9).mean(axis=1)


def crossing_us(v, pulses):
    """Zero-crossing pulse width from band means, interpolated in log
    pulse; None if no sign change on the ladder."""
    bm = bandmeans(v)
    lp = np.log(pulses)
    for i in range(7):
        if bm[i] * bm[i + 1] < 0:
            f = bm[i] / (bm[i] - bm[i + 1])
            return float(np.exp(lp[i] + f * (lp[i + 1] - lp[i])))
    return None


def continuum(v, pulses):
    """Crossing continuum in us; ladder-clamped for non-crossing targets
    (5 us = pure ferrous end, 150 us = pure non-ferrous end)."""
    c = crossing_us(v, pulses)
    if c is not None:
        return c
    return 5.0 if bandmeans(v)[7] > 0 else 150.0


def snr(sig):
    return sig['amp'] / sig['sh']


def pred_cos(s1, s2):
    """Expected cosine between two noisy unit vectors whose true shapes are
    identical, with per-vector amplitude SNRs s1, s2 (isotropic noise):
    E[cos] ~= 1/sqrt((1+1/s1^2)(1+1/s2^2))."""
    return 1.0 / np.sqrt((1 + 1 / s1 ** 2) * (1 + 1 / s2 ** 2))


def main():
    corpus, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    sigs, pulses = load(corpus)

    is_canary = lambda t: 'CANARY' in t
    caps = [k for k in sigs if not is_canary(k[1])]
    usable = [k for k in caps if snr(sigs[k]) >= SNR_GATE]
    subgate = [k for k in caps if snr(sigs[k]) < SNR_GATE]
    tnames = sorted(set(k[1] for k in usable))

    print(f"corpus: {len(sigs)} plateaus | {len(caps)} target captures | "
          f"{len(usable)} usable (SNR>={SNR_GATE:g}) | {len(subgate)} sub-gate:")
    for k in sorted(subgate, key=lambda k: (k[1], k[2])):
        print(f"    {k[1]} @{k[2]}cm SNR={snr(sigs[k]):.1f} q={sigs[k]['q']}")

    # ---------------- F13: crossing continuum table -----------------------
    print("\n== F13: crossing continuum (per capture) ==")
    for k in sorted(caps, key=lambda k: (k[1], k[2])):
        bm = bandmeans(sigs[k]['shape'])
        c = crossing_us(sigs[k]['shape'], pulses)
        print(f"  {k[1]:22s} @{k[2]:2d} b1={bm[0]:+7.2f} b8={bm[7]:+7.2f} "
              f"cross={('%6.1f us' % c) if c else '   none'} "
              f"amp={sigs[k]['amp']:7.2f} SNR={snr(sigs[k]):5.1f}")

    # threshold-axis late/early ratio
    print("\n== F13b: threshold-axis |last cell|/|first cell| "
          "(bands with |mean|>0.5 mV, @10 cm) ==")
    for t in tnames:
        ks = [k for k in usable if k[1] == t and k[2] == 10]
        if not ks:
            ks = [k for k in usable if k[1] == t]
        m = sigs[ks[0]]['shape'].reshape(8, 9)
        sel = np.abs(m.mean(axis=1)) > 0.5
        r = np.abs(m[sel, -1]) / np.maximum(np.abs(m[sel, 0]), 1e-9)
        print(f"  {t:22s} ratio={r.mean():.2f} (n={sel.sum()} bands)")

    # ---------------- F14: PCA --------------------------------------------
    X = np.array([norm(sigs[k]['shape']) for k in usable])
    pca = PCA().fit(X)
    ev = pca.explained_variance_ratio_
    sc = pca.transform(X)
    cont = np.array([np.log(continuum(sigs[k]['shape'], pulses))
                     for k in usable])
    r_pc1 = np.corrcoef(cont, sc[:, 0])[0, 1]
    print(f"\n== F14: PCA on {len(usable)} normalized shapes ==")
    print(f"  PC1 {100*ev[0]:.1f}%  PC1+2 {100*ev[:2].sum():.1f}%  "
          f"PC1+2+3 {100*ev[:3].sum():.1f}%")
    print(f"  corr(PC1 score, log crossing continuum) = {r_pc1:.3f}")

    # ---------------- F15: confusability ---------------------------------
    means = {t: norm(np.mean([norm(sigs[k]['shape'])
                              for k in usable if k[1] == t], axis=0))
             for t in tnames}
    M = np.array([[cosv(means[a], means[b]) for b in tnames]
                  for a in tnames])
    cp = [k for k in usable if k[1] == 'copper pipe' and k[2] == 10]
    floor = 1 - cosv(sigs[cp[0]]['shape'], sigs[cp[1]]['shape']) \
        if len(cp) == 2 else float('nan')
    print(f"\n== F15: shape confusability (mean shapes, usable set) ==")
    print(f"  cross-session repeat floor (copper @10): 1-cos = {floor:.4f}")
    idx = {t: i for i, t in enumerate(tnames)}
    for a, b in [('copper pipe', 'aluminium plate'),
                 ('copper pipe', 'silver cake server'),
                 ('copper pipe', 'brass block'),
                 ('brass block', 'silver cake server'),
                 ('cast iron trivet', 'stainless steel disc'),
                 ('galvanized pipe', 'stainless steel disc'),
                 ('galvanized pipe', 'steel spanner'),
                 ('stainless scissors', 'steel spanner')]:
        d = 1 - M[idx[a], idx[b]]
        print(f"  {a} <-> {b}: 1-cos = {d:.4f} ({d/floor:.1f}x floor)")

    # ---------------- F16: family classification -------------------------
    print("\n== F16: LOTO family classification (usable set) ==")
    labelled = [(k, FAM3[k[1]]) for k in usable]
    hit, misses = 0, []
    for k, f in labelled:
        train = [(kk, ff) for kk, ff in labelled if kk[1] != k[1]]
        best = max(train, key=lambda kf: cosv(sigs[k]['shape'],
                                              sigs[kf[0]]['shape']))
        if best[1] == f:
            hit += 1
        else:
            misses.append((k[1], k[2], f, '->', best[1], 'nn:', best[0][1]))
    print(f"  1-NN cosine, 72 features: {hit}/{len(labelled)} "
          f"= {100*hit/len(labelled):.0f}%")
    for m in misses:
        print("    miss:", *m)

    feat = {k: np.array([np.log(continuum(sigs[k]['shape'], pulses)),
                         np.sign(bandmeans(sigs[k]['shape'])[7])])
            for k, _ in labelled}
    F = np.array([feat[k] for k, _ in labelled])
    mu, sd = F.mean(0), F.std(0)
    hit, misses = 0, []
    for k, f in labelled:
        x = (feat[k] - mu) / sd
        train = [(kk, ff) for kk, ff in labelled if kk[1] != k[1]]
        best = min(train, key=lambda kf:
                   np.linalg.norm(x - (feat[kf[0]] - mu) / sd))
        if best[1] == f:
            hit += 1
        else:
            misses.append((k[1], k[2], f, '->', best[1]))
    print(f"  physics 2-feature (log crossing + band-8 sign), 1-NN: "
          f"{hit}/{len(labelled)} = {100*hit/len(labelled):.0f}%")
    for m in misses:
        print("    miss:", *m)

    # ---------------- F17: LODO target ID --------------------------------
    print("\n== F17: LODO target ID, 1-NN cosine (usable set) ==")
    tot_hit = tot_n = 0
    for held in (5, 10, 15):
        train = [k for k in usable if k[2] != held]
        test = [k for k in usable if k[2] == held]
        hit, misses = 0, []
        for k in test:
            best = max(train, key=lambda kk: cosv(sigs[k]['shape'],
                                                  sigs[kk]['shape']))
            if best[1] == k[1]:
                hit += 1
            else:
                misses.append(f"{k[1]}->{best[1]}")
        tot_hit += hit
        tot_n += len(test)
        print(f"  hold {held:2d} cm: {hit}/{len(test)}"
              + (f"  misses: {misses}" if misses else ""))
    print(f"  pooled: {tot_hit}/{tot_n} = {100*tot_hit/tot_n:.0f}%")

    # ---------------- F18: invariance vs noise model ---------------------
    print("\n== F18: observed cos(d1,d2) vs random-noise prediction ==")
    obs_pred = []
    for t in sorted(set(k[1] for k in caps)):
        for d1, d2 in [(5, 10), (5, 15), (10, 15)]:
            k1 = [k for k in caps if k[1] == t and k[2] == d1]
            k2 = [k for k in caps if k[1] == t and k[2] == d2]
            for a in k1:
                for b in k2:
                    if a[0] != b[0]:
                        continue
                    c = cosv(sigs[a]['shape'], sigs[b]['shape'])
                    p = pred_cos(snr(sigs[a]), snr(sigs[b]))
                    obs_pred.append((t, d1, d2, c, p))
                    tag = ' **systematic' if c < p - 0.005 else ''
                    print(f"  {t:22s} cos({d1},{d2})={c:.4f} "
                          f"noise-pred~{p:.4f}{tag}")
    n_sys = sum(1 for *_, c, p in obs_pred if c < p - 0.005)
    print(f"  {n_sys}/{len(obs_pred)} pairs degraded beyond the "
          f"random-noise prediction (systematic shape change)")
    s_gate = 1 / np.sqrt(1 / 0.97 - 1) if False else None
    # SNR needed for E[cos]=0.97 with s1=s2=s: (1+1/s^2)=1/0.97 -> s=5.66
    s97 = 1 / np.sqrt(1 / 0.97 - 1)
    print(f"  cos gate 0.97 is unreachable in expectation below "
          f"SNR={s97:.1f} per capture (equal-SNR case)")

    # near-field decomposition
    print("\n== F18b: norm(5cm)-norm(15cm) band decomposition ==")
    for t in tnames:
        k5 = [k for k in usable if k[1] == t and k[2] == 5]
        k15 = [k for k in usable if k[1] == t and k[2] == 15]
        if k5 and k15:
            d = norm(sigs[k5[0]]['shape']) - norm(sigs[k15[0]]['shape'])
            print(f"  {t:22s} {np.array2string(bandmeans(d), precision=3, suppress_small=False)}")

    # ---------------- F19: falloff / g(r) ---------------------------------
    print("\n== F19: amplitude falloff 5->15 cm ==")
    ns = []
    for t in sorted(set(k[1] for k in caps)):
        ks = {k[2]: sigs[k]['amp'] for k in caps if k[1] == t}
        if 5 in ks and 15 in ks:
            n = np.log(ks[5] / ks[15]) / np.log(3)
            ns.append(n)
            print(f"  {t:22s} {ks[5]:7.1f} -> {ks[15]:6.1f} mV  "
                  f"ratio {ks[5]/ks[15]:.2f}x  n={n:.2f}")
    print(f"  n across all targets: mean={np.mean(ns):.2f} "
          f"sd={np.std(ns):.2f} range {min(ns):.2f}-{max(ns):.2f}")

    # ---------------- F20: canary / platform stability ---------------------
    print("\n== F20: canary stability ==")
    for kind in ('CANARY-START', 'CANARY-END'):
        amps = [sigs[k]['amp'] for k in sigs if k[1].endswith(kind)]
        print(f"  {kind}: " + ", ".join(f"{a:.2f}" for a in amps)
              + f"  (mean {np.mean(amps):.2f}, sd {np.std(amps):.2f} mV "
              f"= {100*np.std(amps)/np.mean(amps):.1f}%)")
    for s in sorted(set(k[0] for k in sigs)):
        a1 = [sigs[k] for k in sigs
              if k[0] == s and k[1].endswith('CANARY-START')]
        a2 = [sigs[k] for k in sigs
              if k[0] == s and k[1].endswith('CANARY-END')]
        if a1 and a2:
            print(f"  {s}: START->END amp {a1[0]['amp']:.2f} -> "
                  f"{a2[0]['amp']:.2f} ({100*(a2[0]['amp']/a1[0]['amp']-1):+.1f}%), "
                  f"shape cos {cosv(a1[0]['shape'], a2[0]['shape']):.4f}")

    # ---------------- figures ---------------------------------------------
    fam_of = lambda t: FAM3[t]

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
    ax = axes[0]
    for t in tnames:
        k = [k for k in usable if k[1] == t and k[2] == 10] or \
            [k for k in usable if k[1] == t]
        bm = bandmeans(norm(sigs[k[0]]['shape']))
        ax.plot(pulses, bm, 'o-', color=FAMCOL[fam_of(t)], alpha=0.75, lw=1.2)
        ax.annotate(t, (pulses[-1], bm[-1]), fontsize=6, xytext=(3, 0),
                    textcoords='offset points')
    ax.axhline(0, color='k', lw=0.5)
    ax.set_xscale('log')
    ax.set_xlabel('pulse width (µs)')
    ax.set_ylabel('normalized band mean')
    ax.set_title('Signature profiles along the pulse ladder\n'
                 '(red ferrous, purple crossover, blue non-ferrous)')

    ax = axes[1]
    for i, k in enumerate(usable):
        ax.scatter(sc[i, 0], sc[i, 1], s=8 + (16 - k[2]) * 5,
                   color=FAMCOL[fam_of(k[1])], alpha=0.75)
    ax.set_xlabel(f'PC1 ({100*ev[0]:.1f}%)')
    ax.set_ylabel(f'PC2 ({100*ev[1]:.1f}%)')
    ax.set_title('PC1-PC2 (marker size = closer distance)')

    ax = axes[2]
    ax.scatter(cont, sc[:, 0], c=[FAMCOL[fam_of(k[1])] for k in usable])
    ax.set_xlabel('log crossing continuum (µs, ladder-clamped)')
    ax.set_ylabel('PC1 score')
    ax.set_title(f'PC1 vs engineered crossing feature (r={r_pc1:.3f})')
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, 'V2_pca_continuum.png'), dpi=150)

    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    im = ax.imshow(M, vmin=-1, vmax=1, cmap='RdBu_r')
    ax.set_xticks(range(len(tnames)))
    ax.set_xticklabels(tnames, rotation=90, fontsize=7)
    ax.set_yticks(range(len(tnames)))
    ax.set_yticklabels(tnames, fontsize=7)
    for i in range(len(tnames)):
        for j in range(len(tnames)):
            ax.text(j, i, f"{M[i, j]:.2f}", ha='center', va='center',
                    fontsize=5.5,
                    color='w' if abs(M[i, j]) > 0.6 else 'k')
    fig.colorbar(im, label='cosine similarity (mean shapes)')
    ax.set_title('V2 target confusability')
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, 'V2_confusability.png'), dpi=150)

    fig, ax = plt.subplots(figsize=(6, 5.5))
    for t, d1, d2, c, p in obs_pred:
        ax.scatter(p, c, color=FAMCOL[fam_of(t)], alpha=0.8)
    lo = min(min(c for *_, c, _ in obs_pred),
             min(p for *_, _, p in obs_pred)) - 0.01
    ax.plot([lo, 1], [lo, 1], 'k--', lw=0.8, label='obs = noise prediction')
    ax.axhline(0.97, color='grey', lw=0.7, ls=':', label='0.97 gate')
    ax.set_xlabel('noise-model predicted cosine (from split-half SNR)')
    ax.set_ylabel('observed cross-distance cosine')
    ax.set_title('Shape invariance: points below the diagonal\n'
                 'are systematic shape change, not noise')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, 'V2_invariance_noise_model.png'),
                dpi=150)
    print(f"\nfigures written to {outdir}/")


if __name__ == '__main__':
    main()
