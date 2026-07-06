#!/usr/bin/env python3
"""
pimd_pca_explore.py — PCA exploration of the PIMD target-signature corpus.

Version: 1.0
Changelog:
  v1.0 (2026-07-03) — Initial version. Loads PIMD_target_corpus_signatures.csv,
      applies the audited exclusion policy, builds L2-normalized 72-cell shape
      vectors, runs PCA, and produces:
        (1) variance-explained (scree) plot + PC loading heatmaps in the 8x9
            matrix layout, so components can be read like signatures;
        (2) PC1-PC2 scatter of all usable signatures, colored by family,
            marker-sized by distance;
        (3) engineered zero-crossing pulse-width feature vs PC1 score —
            does blind statistics rediscover the bench-derived material
            parameter?
      Plain numpy / pandas / scikit-learn / matplotlib only (repo convention).

Usage:
    python pimd_pca_explore.py <corpus_csv> <output_dir>

Notes:
  - Exclusion policy (from the 2026-07-03 raw-session audit):
      * solder roll 260g: all rows (EXCLUDE flag confirmed: distance falloff
        only ~1.7x even after drift correction)
      * SS shackle 62g: keep 5 cm only (10/15 cm are thermal-drift shapes)
      * brass 370g: drop 15 cm (drifted; the (rpt) capture covers it)
      * SS disk 35g @15 and steel RHS 140g @15: kept but marked low-confidence
        (late session B, drift-heaviest stretch).
  - Signatures ordered (pulse ascending, threshold descending) to match the
    session colmap; shape = 72-vector / L2 norm.
"""

import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

PULSES = [6.0, 9.0, 13.44, 20.0, 30.0, 45.0, 67.2, 100.0]

FAMILY = {  # from DESIGN / handoff, assigned by zero-crossing location
    "steel pipe 140g": "ferrous-rising", "spanner 270g": "ferrous-rising",
    "nut+bolt 150g": "ferrous-rising", "SS shackle 62g": "ferrous-rising",
    "steel RHS 140g": "crossover", "SS disk 35g": "crossover",
    "cast iron trivet 100g": "crossover", "silver cluster 400g": "crossover",
    "SS pipe 220g": "crossover", "lead pipe 200g": "crossover",
    "Al plate 360g": "non-ferrous", "silver spoon 150g": "non-ferrous",
    "copper pipe 120g": "non-ferrous", "brass valve 700g": "non-ferrous",
    "brass block 370g (rpt)": "non-ferrous", "brass 370g": "non-ferrous",
}
FAM_COLOR = {"ferrous-rising": "tab:red", "crossover": "tab:purple",
             "non-ferrous": "tab:blue"}
LOW_CONF = {("SS disk 35g", 15), ("steel RHS 140g", 15), ("lead pipe 200g", 15)}


def load_corpus(path):
    df = pd.read_csv(path)
    # --- exclusion policy ---
    df = df[df.target != "solder roll 260g"]
    df = df[~((df.target == "SS shackle 62g") & (df.distance_cm != 5))]
    df = df[~((df.target == "brass 370g") & (df.distance_cm == 15))]
    rows = []
    for (tg, d), g in df.groupby(["target", "distance_cm"]):
        g = g.sort_values(["pulse_us", "threshold_v"], ascending=[True, False])
        v = g["delta_mV"].to_numpy()
        rows.append(dict(target=tg, distance_cm=d, family=FAMILY[tg],
                         amp=g["plateau_amp_mV"].iloc[0],
                         shape=v / np.linalg.norm(v)))
    return pd.DataFrame(rows)


def crossing_pulse_us(shape72):
    """Engineered feature: pulse width where band-mean response crosses zero
    (eddy/magnetic balance point). Returns (value_us, kind) with kind in
    {'value', '<=6', 'none'}; log-interpolated between band centres."""
    bm = shape72.reshape(8, 9).mean(axis=1)
    if bm[0] >= 0:                      # positive already at the 6 us edge
        return 6.0, "<=6"
    for i in range(7):
        if bm[i] < 0 <= bm[i + 1]:      # first negative->positive crossing
            lp = np.log(PULSES[i]) + (-bm[i]) / (bm[i + 1] - bm[i]) * \
                 (np.log(PULSES[i + 1]) - np.log(PULSES[i]))
            return float(np.exp(lp)), "value"
    return np.nan, "none"               # never crosses: pure non-ferrous


def main(corpus_csv, outdir):
    data = load_corpus(corpus_csv)
    X = np.vstack(data["shape"].to_numpy())          # n x 72
    print(f"{len(data)} usable signatures, {X.shape[1]} cells each")

    # PCA centres the data itself (subtracts the mean signature) then finds
    # orthogonal directions of maximum variance.
    pca = PCA(n_components=10)
    scores = pca.fit_transform(X)                     # n x 10 coordinates
    evr = pca.explained_variance_ratio_
    print("variance explained by PC1..PC5:",
          np.array2string(evr[:5], precision=3, floatmode="fixed"),
          f"| PC1+PC2 = {evr[:2].sum():.1%}")

    data["cross_us"], data["cross_kind"] = zip(
        *[crossing_pulse_us(s) for s in data["shape"]])
    data["pc1"], data["pc2"], data["pc3"] = scores[:, 0], scores[:, 1], scores[:, 2]

    # ---------- figure 1: scree + loading heatmaps ----------
    fig = plt.figure(figsize=(14, 4.4))
    ax = fig.add_subplot(1, 4, 1)
    ax.bar(range(1, 9), evr[:8] * 100, color="0.6")
    ax.plot(range(1, 9), np.cumsum(evr[:8]) * 100, "k.-", label="cumulative")
    ax.set_xlabel("component"); ax.set_ylabel("% variance explained")
    ax.set_title("How many dimensions\nis the corpus, really?")
    ax.legend(fontsize=8)
    vmax = np.abs(pca.components_[:3]).max()
    for k in range(3):
        axh = fig.add_subplot(1, 4, k + 2)
        L = pca.components_[k].reshape(8, 9)
        imh = axh.imshow(L, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
        axh.set_title(f"PC{k+1} loading ({evr[k]:.0%})")
        axh.set_yticks(range(8)); axh.set_yticklabels([f"{p:g}" for p in PULSES],
                                                       fontsize=7)
        axh.set_xticks(range(9))
        axh.set_xticklabels(["4.2", "", "2.47", "", "1.45", "", "0.85", "", "0.5"],
                            fontsize=7)
        axh.set_xlabel("threshold (V)")
        if k == 0:
            axh.set_ylabel("pulse (µs)")
    fig.colorbar(imh, ax=fig.axes[1:], shrink=0.8, label="loading")
    fig.suptitle("PCA of normalized PIMD signatures — variance and component structure",
                 y=1.04)
    fig.savefig(f"{outdir}/PIMD_pca_variance_loadings.png", dpi=140,
                bbox_inches="tight")

    # ---------- figure 2: PC1-PC2 map + crossing comparison ----------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.5))
    for fam, g in data.groupby("family"):
        for _, r in g.iterrows():
            lc = (r.target, r.distance_cm) in LOW_CONF
            ax1.scatter(r.pc1, r.pc2, s={5: 130, 10: 70, 15: 32}[r.distance_cm],
                        color=FAM_COLOR[fam], edgecolor="k" if lc else "none",
                        linewidths=1.4, alpha=0.85,
                        marker="o")
        # label each target once, at its 5 cm point
        for tg, gg in g.groupby("target"):
            r5 = gg[gg.distance_cm == gg.distance_cm.min()].iloc[0]
            ax1.annotate(tg.replace(" 370g (rpt)", " rpt").split(" ")[0] +
                         (" rpt" if "rpt" in tg else ""),
                         (r5.pc1, r5.pc2), fontsize=8, xytext=(4, 4),
                         textcoords="offset points")
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, label=f)
               for f, c in FAM_COLOR.items()]
    handles += [plt.Line2D([], [], marker="o", ls="", color="0.5", ms=s,
                           label=f"{d} cm") for d, s in
                zip((5, 10, 15), (12, 8, 5))]
    ax1.legend(handles=handles, fontsize=8, loc="best")
    ax1.axhline(0, color="0.8", lw=.7); ax1.axvline(0, color="0.8", lw=.7)
    ax1.set_xlabel(f"PC1 score ({evr[0]:.0%} of variance)")
    ax1.set_ylabel(f"PC2 score ({evr[1]:.0%})")
    ax1.set_title("The corpus seen along its two biggest axes\n"
                  "(black edge = low-confidence 15 cm rows)")

    # crossing feature vs PC1
    plot_x = data["cross_us"].copy()
    plot_x[data.cross_kind == "none"] = 300          # park 'no crossing' right
    for fam, g in data.groupby("family"):
        ax2.scatter(plot_x[g.index], g.pc1, color=FAM_COLOR[fam],
                    s=[{5: 130, 10: 70, 15: 32}[d] for d in g.distance_cm],
                    alpha=0.85)
    ax2.set_xscale("log")
    ax2.axvline(6, color="0.7", ls="--", lw=1)
    ax2.text(6, ax2.get_ylim()[0], " ladder edge 6 µs", fontsize=7, rotation=90,
             va="bottom")
    ax2.set_xticks([6, 10, 20, 50, 100, 300])
    ax2.set_xticklabels(["≤6", "10", "20", "50", "100", "never\ncrosses"])
    ax2.set_xlabel("engineered feature: zero-crossing pulse width (µs)")
    ax2.set_ylabel("PC1 score")
    ax2.set_title("Bench physics vs blind statistics —\n"
                  "does PC1 rediscover the crossing point?")
    fig.suptitle("PIMD signature corpus in PCA space", y=1.02)
    fig.savefig(f"{outdir}/PIMD_pca_map_and_crossing.png", dpi=140,
                bbox_inches="tight")

    data.drop(columns="shape").to_csv(f"{outdir}/PIMD_pca_scores.csv",
                                      index=False)
    print(f"wrote figures + scores to {outdir}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else "PIMD_target_corpus_signatures.csv",
         sys.argv[2] if len(sys.argv) > 2 else ".")
