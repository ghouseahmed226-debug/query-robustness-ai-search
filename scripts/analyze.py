#!/usr/bin/env python
"""Summarise a finished run into the tables of docs/ANALYSIS_PLAN.md (CSV files plus a readable summary.md).

    python scripts/analyze.py --run-dir results/vaswani_pilot
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from qvr.analysis import md_table, summarise


def build_markdown(res: dict, meta: dict) -> str:
    out = ["# Summary of run", ""]
    counts = meta["counts"]
    out += [f"* collection: `{meta['collection']['name']}` ({meta['collection'].get('n_docs')} documents)",
            f"* queries analysed: {counts['queries_selected']}",
            (f"* valid rewrites analysed: {counts['rewrites_kept']} "
            f"(by category: {counts['rewrites_kept_by_category']}; by status: {counts['rewrites_kept_by_status']})"),
            f"* rewrites dropped before the run: {counts['rewrites_dropped']}", ""]
    out += ["## Original queries", "", md_table(res["baseline"], ["system", "n_queries", "ndcg@10", "ndcg@10_lo", "ndcg@10_hi",
                                                                  "recall@100", "mrr@10"]), ""]
    p = res["primary"].copy()
    out += ["## Primary: nDCG@10 under each variation category", "",
            ("`rel` is the relative change of the mean (ratio of means over the queries that have a valid rewrite in the "
            "category); intervals are 95% cluster-bootstrap CIs over original queries; `p_holm` is Holm-adjusted over "
            f"{int(p['holm_family_size'].iloc[0])} tests."), "",
            md_table(p, ["system", "category", "n_queries", "n_rewrites", "ndcg@10_orig", "ndcg@10_rewrite", "ndcg@10_delta",
                         "ndcg@10_delta_lo", "ndcg@10_delta_hi", "ndcg@10_rel", "ndcg@10_rel_lo", "ndcg@10_rel_hi",
                         "p_signflip", "p_holm"], "{:.4f}"), ""]
    out += ["## Secondary metrics", "",
            md_table(p, ["system", "category", "recall@100_delta", "recall@100_rel", "mrr@10_delta", "mrr@10_rel"], "{:.4f}"), ""]
    stab_cols = [c for c in p.columns if (c.startswith(("overlap@", "rbo_p"))) and not c.endswith(("_lo", "_hi"))]
    out += ["## Ranking stability (original vs rewrite ranking of the same system)", "",
            md_table(p, ["system", "category"] + stab_cols, "{:.3f}"), ""]
    if len(res["by_generator"]):
        out += ["## Descriptive breakdown by generator (no tests)", "",
                md_table(res["by_generator"], ["system", "generator", "n_queries", "n_rewrites", "ndcg@10_delta", "ndcg@10_delta_lo",
                                               "ndcg@10_delta_hi", "ndcg@10_rel"], "{:.4f}"), ""]
    if len(res["hybrid_vs_components"]):
        out += ["## Exploratory: hybrid vs component (difference in absolute nDCG@10 change)", "",
                md_table(res["hybrid_vs_components"], ["hybrid", "component", "category", "n_queries",
                                                       "diff_in_absolute_ndcg@10_change", "lo", "hi"], "{:.4f}"), ""]
    if len(res["stability_vs_effectiveness"]):
        out += ["## Stability vs effectiveness (Spearman, RBO vs |change in nDCG@10|)", "",
                md_table(res["stability_vs_effectiveness"], list(res["stability_vs_effectiveness"].columns), "{:.3f}"), ""]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--B", type=int, default=10_000, help="bootstrap replicates")
    ap.add_argument("--flip-B", type=int, default=200_000, help="random sign flips per Monte-Carlo permutation test")
    ap.add_argument("--spearman-B", type=int, default=2_000)
    args = ap.parse_args(argv)

    run_dir = Path(args.run_dir)
    res = summarise(run_dir, args.out_dir, B=args.B, flip_B=args.flip_B, spearman_B=args.spearman_B)
    meta = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    out_dir = Path(res["out_dir"])
    (out_dir / "summary.md").write_text(build_markdown(res, meta), encoding="utf-8")
    pd.set_option("display.width", 200)
    print((out_dir / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
