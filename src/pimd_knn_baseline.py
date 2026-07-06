#!/usr/bin/env python3
"""
pimd_knn_baseline.py — first classifiers for the PIMD signature corpus.

Version: 1.1
Changelog:
  v1.1 (2026-07-04) — main() now creates outdir (os.makedirs) before
      saving the confusion-matrix figure; previously crashed with
      FileNotFoundError if the output directory didn't already exist.
  v1.0 (2026-07-03) — Initial version. Tasks: (a) family classification
      (ferrous-rising / crossover / non-ferrous), (b) per-target ID (16
      classes). Models: 1-NN with cosine distance on L2-normalized 72-cell
      shapes; multinomial logistic regression (L2, C=1) on the same features;
      and a 2-feature physics baseline for family (zero-crossing pulse width
      + band-8 sign). Validation: leave-one-distance-out (LODO) for both
      tasks; leave-one-target-out (LOTO) for family (unseen-object test).
      Outputs confusion matrices and per-fold accuracy.

Usage:
    python pimd_knn_baseline.py <corpus_csv> <output_dir>
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression

PULSES = [6.0, 9.0, 13.44, 20.0, 30.0, 45.0, 67.2, 100.0]
FAMILY = {
    "steel pipe 140g": "ferrous", "spanner 270g": "ferrous",
    "nut+bolt 150g": "ferrous", "SS shackle 62g": "ferrous",
    "steel RHS 140g": "crossover", "SS disk 35g": "crossover",
    "cast iron trivet 100g": "crossover", "silver cluster 400g": "crossover",
    "SS pipe 220g": "crossover", "lead pipe 200g": "crossover",
    "Al plate 360g": "non-ferrous", "silver spoon 150g": "non-ferrous",
    "copper pipe 120g": "non-ferrous", "brass valve 700g": "non-ferrous",
    "brass block 370g (rpt)": "non-ferrous", "brass 370g": "non-ferrous",
}
FAMS = ["ferrous", "crossover", "non-ferrous"]


def load_corpus(path):
    df = pd.read_csv(path)
    df = df[df.target != "solder roll 260g"]
    df = df[~((df.target == "SS shackle 62g") & (df.distance_cm != 5))]
    df = df[~((df.target == "brass 370g") & (df.distance_cm == 15))]
    rows = []
    for (tg, d), g in df.groupby(["target", "distance_cm"]):
        g = g.sort_values(["pulse_us", "threshold_v"], ascending=[True, False])
        v = g["delta_mV"].to_numpy()
        rows.append(dict(target=tg, distance_cm=d, family=FAMILY[tg],
                         shape=v / np.linalg.norm(v)))
    return pd.DataFrame(rows)


def crossing_features(shape72):
    """[log crossing pulse width (sentinels at edges), band-8 mean sign]."""
    bm = shape72.reshape(8, 9).mean(axis=1)
    if bm[0] >= 0:
        lx = np.log(6.0) - 0.3          # 'at or below ladder edge'
    else:
        lx = np.log(300.0)              # 'never crosses' sentinel
        for i in range(7):
            if bm[i] < 0 <= bm[i + 1]:
                lx = np.log(PULSES[i]) + (-bm[i]) / (bm[i + 1] - bm[i]) * \
                     (np.log(PULSES[i + 1]) - np.log(PULSES[i]))
                break
    return np.array([lx, np.sign(bm[7])])


def run_cv(X, y, folds, model_fn):
    """Generic cross-validation. folds = list of boolean test masks."""
    y = np.asarray(y)
    pred = np.empty(len(y), dtype=object)
    for te in folds:
        tr = ~te
        m = model_fn()
        m.fit(X[tr], y[tr])
        pred[te] = m.predict(X[te])
    return pred


def confmat(y, pred, labels):
    cm = np.zeros((len(labels), len(labels)), int)
    for a, b in zip(y, pred):
        cm[labels.index(a), labels.index(b)] += 1
    return cm


def plot_cm(ax, cm, labels, title, small=False):
    ax.imshow(cm, cmap="Blues", vmin=0)
    fs = 6 if small else 10
    for i in range(len(labels)):
        for j in range(len(labels)):
            if cm[i, j]:
                ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=fs,
                        color="white" if cm[i, j] > cm.max() * .6 else "black")
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    short = [l.replace(" 370g (rpt)", " rpt") for l in labels]
    short = [" ".join(s.split()[:2]) for s in short]
    ax.set_xticklabels(short, rotation=90, fontsize=fs)
    ax.set_yticklabels(short, fontsize=fs)
    ax.set_xlabel("predicted", fontsize=8)
    ax.set_ylabel("true", fontsize=8)
    acc = np.trace(cm) / cm.sum()
    ax.set_title(f"{title}\naccuracy {np.trace(cm)}/{cm.sum()} = {acc:.0%}",
                 fontsize=9)


def main(corpus_csv, outdir):
    os.makedirs(outdir, exist_ok=True)
    data = load_corpus(corpus_csv)
    Xs = np.vstack(data["shape"].to_numpy())
    Xc = np.vstack([crossing_features(s) for s in data["shape"]])
    yfam = data["family"].to_numpy()
    ytg = data["target"].to_numpy()
    targets = sorted(data["target"].unique())
    dist = data["distance_cm"].to_numpy()

    lodo = [dist == d for d in (5, 10, 15)]
    loto = [ytg == t for t in targets]

    knn = lambda: KNeighborsClassifier(n_neighbors=1, metric="cosine")
    lr = lambda: LogisticRegression(max_iter=5000)

    results = {}
    results["family LODO 1-NN shape"] = (yfam, run_cv(Xs, yfam, lodo, knn), FAMS)
    results["family LOTO 1-NN shape"] = (yfam, run_cv(Xs, yfam, loto, knn), FAMS)
    results["family LOTO crossing+band8 (2 features, 1-NN)"] = (
        yfam, run_cv(Xc, yfam, loto, knn), FAMS)
    results["target LODO 1-NN shape"] = (ytg, run_cv(Xs, ytg, lodo, knn), targets)
    results["target LODO logistic regression"] = (
        ytg, run_cv(Xs, ytg, lodo, lr), targets)

    fig = plt.figure(figsize=(15, 9))
    grid = [(0, 0, 1), (0, 1, 1), (0, 2, 1), (1, 0, 2), (1, 2, 2)]
    axes = [plt.subplot2grid((2, 4), (r, c), colspan=w, fig=fig)
            for r, c, w in [(0, 0, 1), (0, 1, 1), (0, 2, 1), (1, 0, 2), (1, 2, 2)]]
    for ax, (name, (y, p, labels)) in zip(axes, results.items()):
        plot_cm(ax, confmat(y, p, labels), labels, name, small=len(labels) > 5)
        print(f"{name}: {np.mean(y == p):.0%}")
        wrong = [(t, d, pr) for t, d, tr, pr in
                 zip(data.target, data.distance_cm, y, p) if tr != pr]
        for t, d, pr in wrong:
            print(f"    miss: {t} @{d} cm -> {pr}")
    fig.suptitle("PIMD first classifiers — honest cross-validation "
                 "(LODO = unseen distance, LOTO = unseen object)", y=1.0)
    fig.tight_layout()
    fig.savefig(f"{outdir}/PIMD_baseline_confusion.png", dpi=140,
                bbox_inches="tight")
    print(f"wrote {outdir}/PIMD_baseline_confusion.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else "PIMD_target_corpus_signatures.csv",
         sys.argv[2] if len(sys.argv) > 2 else ".")
