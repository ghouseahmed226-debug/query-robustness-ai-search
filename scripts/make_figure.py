#!/usr/bin/env python
"""Figure 1: relative change of nDCG@10 per variation category and system, with 95% cluster-bootstrap intervals.

    python scripts/make_figure.py --analysis-dir results/vaswani_pilot/analysis --out paper/figures/fig1_ndcg_change

Reads only ``summary_primary.csv``; every plotted number is a cell of that file. Needs matplotlib (``pip install -e .[plots]``).
Colours are the first three slots of the validated categorical palette (they pass the all-pairs colour-vision checks);
marker shapes carry identity as well, so the figure also reads in greyscale.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

SURFACE, INK, INK2, GRID = "#ffffff", "#0b0b0b", "#52514e", "#e3e2de"
SYSTEMS = [("bm25", "BM25", "#2a78d6", "o"), ("lsa", "LSA (non-neural)", "#eb6834", "s"),
           ("rrf_bm25_lsa", "RRF hybrid of the two", "#1baf7a", "D")]
CATEGORIES = ["misspelling", "paraphrasing", "naturality", "ordering"]
DODGE = {"bm25": 0.24, "lsa": 0.0, "rrf_bm25_lsa": -0.24}  # top to bottom = legend order


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analysis-dir", required=True)
    ap.add_argument("--out", required=True, help="path without extension; .pdf and .png are written")
    args = ap.parse_args(argv)

    p = pd.read_csv(Path(args.analysis_dir) / "summary_primary.csv")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": INK2,
                         "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK})
    fig, ax = plt.subplots(figsize=(6.6, 3.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ypos = {c: len(CATEGORIES) - 1 - i for i, c in enumerate(CATEGORIES)}  # first category on top
    for sys_id, label, colour, marker in SYSTEMS:
        for c in CATEGORIES:
            row = p[(p.system == sys_id) & (p.category == c)].iloc[0]
            y = ypos[c] + DODGE[sys_id]
            x, lo, hi = 100 * row["ndcg@10_rel"], 100 * row["ndcg@10_rel_lo"], 100 * row["ndcg@10_rel_hi"]
            ax.plot([lo, hi], [y, y], color=colour, lw=1.6, solid_capstyle="round", zorder=3)
            ax.plot([x], [y], marker=marker, ms=7.5, color=colour, mec=SURFACE, mew=1.6, ls="none", zorder=4)
    ax.axvline(0, color=INK2, lw=0.9, zorder=2)
    ax.set_yticks([ypos[c] for c in CATEGORIES])
    labels = []
    for c in CATEGORIES:
        n_rew = int(p[p.category == c]["n_rewrites"].iloc[0])
        n_q = int(p[p.category == c]["n_queries"].iloc[0])
        labels.append(f"{c}\n{n_rew} rewrites of {n_q} queries")
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_ylim(-0.6, len(CATEGORIES) - 0.4)
    ax.set_xlabel("Relative change in nDCG@10 versus the original query (%), 95% cluster-bootstrap interval")
    ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.annotate("exactly 0 by construction:\nthese systems ignore word order", xy=(0, ypos["ordering"]), xytext=(5.5, ypos["ordering"]),
                va="center", fontsize=7.5, color=INK2)
    handles = [Line2D([0], [0], marker=m, color=c, lw=1.6, ms=7.5, mec=SURFACE, mew=1.2, label=sys_label) for _, sys_label, c, m in SYSTEMS]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=3, frameon=False, fontsize=8,
              handletextpad=0.5, columnspacing=1.6, borderaxespad=0.2)
    fig.tight_layout()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out.with_suffix(".pdf"), facecolor=SURFACE)
    fig.savefig(out.with_suffix(".png"), facecolor=SURFACE, dpi=300)
    print(f"wrote {out.with_suffix('.pdf')} and {out.with_suffix('.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
