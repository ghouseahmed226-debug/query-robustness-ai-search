"""Turn the per-query CSVs of a run into the tables defined in docs/ANALYSIS_PLAN.md.

Unit of analysis: the original query. For each (system, category) every query contributes the mean of its valid
rewrites in that category, compared with its own original-query score. Resampling is over original queries.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .stats import (bootstrap_mean_ci, bootstrap_ratio_change_ci, holm_adjust, sign_flip_pvalue,
                    spearman_cluster_bootstrap)

PRIMARY = "ndcg@10"
EFFECT_METRICS = ("ndcg@10", "recall@100", "mrr@10")
HYBRID_COMPONENTS = {"rrf_bm25_lsa": ("bm25", "lsa"), "rrf_bm25_dense": ("bm25", "dense")}


def _stability_columns(rew: pd.DataFrame) -> list[str]:
    return [c for c in rew.columns if c.startswith("overlap@") or c.startswith("rbo_p")]


def _category_frame(rew_s: pd.DataFrame, orig_s: pd.DataFrame, category: str, stab: list[str], group: str = "category"):
    rc = rew_s[rew_s[group] == category]
    cols = list(EFFECT_METRICS) + stab
    mean_rew = rc.groupby("qid")[cols].mean()
    n_rew = rc.groupby("qid").size()
    base = orig_s.set_index("qid").loc[mean_rew.index, list(EFFECT_METRICS)]
    return mean_rew, base, n_rew


def summarise(run_dir, out_dir=None, B: int = 10_000, boot_seed: int = 20261017, flip_B: int = 200_000,
              flip_seed: int = 20261017, spearman_B: int = 2_000) -> dict:
    run_dir = Path(run_dir)
    out_dir = Path(out_dir) if out_dir else run_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    orig = pd.read_csv(run_dir / "per_query_original.csv", dtype={"qid": str})
    rew = pd.read_csv(run_dir / "per_query_rewrites.csv", dtype={"qid": str, "rewrite_id": str})
    stab = _stability_columns(rew)
    systems = list(orig["system"].unique())
    categories = sorted(rew["category"].unique())

    # baseline effectiveness of the original queries
    base_rows = []
    for s in systems:
        o = orig[orig.system == s]
        row = {"system": s, "n_queries": len(o)}
        for m in EFFECT_METRICS:
            mean, (lo, hi) = bootstrap_mean_ci(o[m].to_numpy(), B, boot_seed)
            row.update({m: mean, f"{m}_lo": lo, f"{m}_hi": hi})
        base_rows.append(row)
    baseline = pd.DataFrame(base_rows)

    def one_cell(s: str, group: str, value: str, with_test: bool):
        o = orig[orig.system == s]
        r = rew[rew.system == s]
        mean_rew, base, n_rew = _category_frame(r, o, value, stab, group)
        row = {"system": s, group: value, "n_queries": len(mean_rew), "n_rewrites": int(n_rew.sum())}
        per_query_delta = {}
        for m in EFFECT_METRICS:
            m0 = base[m].to_numpy()
            mb = mean_rew[m].to_numpy()
            d = mb - m0
            per_query_delta[m] = pd.Series(d, index=mean_rew.index)
            dmean, (dlo, dhi) = bootstrap_mean_ci(d, B, boot_seed)
            rel, (rlo, rhi) = bootstrap_ratio_change_ci(mb, m0, B, boot_seed)
            row.update({f"{m}_orig": float(m0.mean()), f"{m}_rewrite": float(mb.mean()), f"{m}_delta": dmean,
                        f"{m}_delta_lo": dlo, f"{m}_delta_hi": dhi, f"{m}_rel": rel, f"{m}_rel_lo": rlo,
                        f"{m}_rel_hi": rhi})
            if with_test and m == PRIMARY:
                row["p_signflip"] = sign_flip_pvalue(d, flip_B, flip_seed)
        for c in stab:
            mean, (lo, hi) = bootstrap_mean_ci(mean_rew[c].to_numpy(), B, boot_seed)
            row.update({c: mean, f"{c}_lo": lo, f"{c}_hi": hi})
        return row, per_query_delta

    # primary family: system x category on nDCG@10, Holm-corrected
    primary_rows, deltas = [], {}
    for s in systems:
        for c in categories:
            row, dq = one_cell(s, "category", c, with_test=True)
            primary_rows.append(row)
            deltas[(s, c)] = dq
    primary = pd.DataFrame(primary_rows)
    primary["p_holm"] = holm_adjust(primary["p_signflip"].to_numpy())
    primary["holm_family_size"] = len(primary)

    # descriptive generator-level breakdown (no tests)
    gen_rows = []
    if "generator" in rew.columns:
        for s in systems:
            for g in sorted(rew["generator"].dropna().unique()):
                if g == "":
                    continue
                row, _ = one_cell(s, "generator", g, with_test=False)
                gen_rows.append(row)
    by_generator = pd.DataFrame(gen_rows)

    # exploratory: does the hybrid change less than its components? (paired by query, CI only)
    hyb_rows = []
    for h, comps in HYBRID_COMPONENTS.items():
        if h not in systems:
            continue
        for comp in comps:
            if comp not in systems:
                continue
            for c in categories:
                dh = deltas[(h, c)][PRIMARY]
                dc = deltas[(comp, c)][PRIMARY]
                idx = dh.index.intersection(dc.index)
                diff = dh.loc[idx].to_numpy() - dc.loc[idx].to_numpy()
                mean, (lo, hi) = bootstrap_mean_ci(diff, B, boot_seed)
                hyb_rows.append({"hybrid": h, "component": comp, "category": c, "n_queries": len(idx),
                                 "diff_in_absolute_ndcg@10_change": mean, "lo": lo, "hi": hi})
    hybrid_vs = pd.DataFrame(hyb_rows)

    # stability vs effectiveness
    rbo_cols = [c for c in stab if c.startswith("rbo_p")]
    sv_rows = []
    if rbo_cols:
        for s in systems:
            r = rew[rew.system == s]
            rho, (lo, hi) = spearman_cluster_bootstrap(r[rbo_cols[0]].to_numpy(), r["d_ndcg@10"].abs().to_numpy(),
                                                       r["qid"].to_numpy(), B=spearman_B, seed=boot_seed)
            sv_rows.append({"system": s, "n_pairs": len(r), "spearman_rbo_vs_abs_delta_ndcg@10": rho,
                            "lo": lo, "hi": hi})
    stab_vs_eff = pd.DataFrame(sv_rows)

    tables = {"baseline": baseline, "primary": primary, "by_generator": by_generator,
              "hybrid_vs_components": hybrid_vs, "stability_vs_effectiveness": stab_vs_eff}
    for name, df in tables.items():
        if len(df):
            df.to_csv(out_dir / f"summary_{name}.csv", index=False)
    (out_dir / "analysis_parameters.json").write_text(json.dumps({
        "bootstrap_B": B, "bootstrap_seed": boot_seed, "sign_flip_B": flip_B, "sign_flip_seed": flip_seed,
        "spearman_bootstrap_B": spearman_B, "primary_metric": PRIMARY, "ci_level": 0.95,
        "primary_family_size": len(primary)}, indent=2), encoding="utf-8")
    return {"out_dir": str(out_dir), **tables}


def md_table(df: pd.DataFrame, cols: list[str], fmt: str = "{:.3f}") -> str:
    """Render selected columns as a GitHub-flavoured markdown table (no tabulate dependency)."""
    head = "| " + " | ".join(cols) + " |"
    rule = "|" + "|".join("---" for _ in cols) + "|"
    lines = [head, rule]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, (float, np.floating)):
                cells.append("nan" if np.isnan(v) else fmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
