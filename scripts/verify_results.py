#!/usr/bin/env python
"""Independent re-computation of the numbers reported in the manuscript.

    python scripts/verify_results.py [--out results/verification_report.md] [--run-tests]

This script does NOT import ``qvr``. It re-derives every effectiveness number from the saved rankings
(``results/vaswani_pilot/rankings/*.jsonl.gz``) and the relevance judgments (``data/raw/vaswani/qrels``) with a separate,
deliberately plain implementation (numpy/pandas/scipy only), then compares

  1. per-query nDCG@10, Recall@100, MRR@10 and overlap@10 with ``per_query_*.csv``  (tolerance 1e-9),
  2. RBO (p = 0.9) with the CSV for the pairs where both rankings have 100 documents,
  3. baseline means, category means, relative changes, per-generator relative changes, hybrid-minus-component differences and
     the Spearman correlations with the ``summary_*.csv`` files  (tolerance 1e-9),
  4. the 95% cluster-bootstrap intervals and the sign-flip p-values / Holm adjustment with fresh Monte-Carlo runs under
     different seeds  (tolerance: Monte-Carlo error),
  5. provenance: SHA-256 of the analysis plan prefix, rewrite file, code files and raw data against ``run_metadata.json``,
  6. that ``paper/manuscript_draft.md`` is exactly what ``scripts/build_paper.py`` produces from the result files and that the
     test count quoted in the manuscript equals the number of collected tests (needs pytest).

Exit status 0 only if every check passes.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import itertools
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results" / "vaswani_pilot"
SYSTEMS = ["bm25", "lsa", "rrf_bm25_lsa"]
CATEGORIES = ["misspelling", "paraphrasing", "naturality", "ordering"]
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))


# ------------------------------------------------------------------------------------------ metrics, plain versions
def load_qrels(path: Path) -> dict[str, set[str]]:
    rel: dict[str, set[str]] = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) == 4 and int(parts[3]) > 0:
            rel.setdefault(parts[0], set()).add(parts[2])
    return rel


def ndcg10(docs: list[str], rel: set[str]) -> float:
    dcg = sum(1.0 / math.log2(i + 2) for i, d in enumerate(docs[:10]) if d in rel)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel), 10)))
    return dcg / idcg


def recall100(docs: list[str], rel: set[str]) -> float:
    return len(rel.intersection(docs[:100])) / len(rel)


def mrr10(docs: list[str], rel: set[str]) -> float:
    for i, d in enumerate(docs[:10]):
        if d in rel:
            return 1.0 / (i + 1)
    return 0.0


def overlap10(a: list[str], b: list[str]) -> float:
    return len(set(a[:10]) & set(b[:10])) / 10.0


def rbo_ext_equal_length(a: list[str], b: list[str], p: float = 0.9) -> float:
    """Extrapolated RBO (Webber et al. 2010, eq. 32) for two duplicate-free rankings of the same length k."""
    k = len(a)
    assert len(b) == k
    seen_a: set[str] = set()
    seen_b: set[str] = set()
    x = 0
    total = 0.0
    for d in range(1, k + 1):
        da, db = a[d - 1], b[d - 1]
        if da == db:
            x += 1
        else:
            x += (da in seen_b) + (db in seen_a)
        seen_a.add(da)
        seen_b.add(db)
        total += (x / d) * p ** d
    return (x / k) * p ** k + (1 - p) / p * total


def read_rankings(path: Path) -> dict[str, dict]:
    out = {}
    with gzip.open(path, "rt") as f:
        for line in f:
            r = json.loads(line)
            out[r["key"]] = r
    return out


# ------------------------------------------------------------------------------------------ resampling, plain versions
def boot_ci_ratio(m0: np.ndarray, mb: np.ndarray, B: int, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(m0)
    vals = np.empty(B)
    step = 2000
    for s in range(0, B, step):
        idx = rng.integers(0, n, size=(min(step, B - s), n))
        vals[s:s + idx.shape[0]] = mb[idx].mean(1) / m0[idx].mean(1) - 1
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def sign_flip_p(d: np.ndarray, B: int, seed: int, exact_max: int = 16) -> float:
    d = d[np.abs(d) > 1e-15]
    m = len(d)
    if m == 0:
        return 1.0
    obs = abs(d.sum())
    if m <= exact_max:
        signs = np.array(list(itertools.product([-1.0, 1.0], repeat=m)))
        return float(np.mean(np.abs(signs @ d) >= obs - 1e-12))
    rng = np.random.default_rng(seed)
    hits = 0
    step = 20000
    for s in range(0, B, step):
        n = min(step, B - s)
        flips = rng.choice([-1.0, 1.0], size=(n, m))
        hits += int(np.sum(np.abs(flips @ d) >= obs - 1e-12))
    return (hits + 1) / (B + 1)


def holm(p: list[float]) -> list[float]:
    m = len(p)
    order = sorted(range(m), key=lambda i: p[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj


# ------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="write a markdown report here")
    ap.add_argument("--run-tests", action="store_true", help="also run the whole test suite with pytest")
    ap.add_argument("--run-dir", default=str(RUN))
    args = ap.parse_args(argv)
    run = Path(args.run_dir)
    meta = json.loads((run / "run_metadata.json").read_text())
    missing = [n for n in meta["collection"]["file_sha256"] if not (ROOT / "data/raw/vaswani" / n).exists()]
    if missing:
        print(f"Cannot verify: the Vaswani file(s) {', '.join(missing)} are not in data/raw/vaswani.\n"
              "Run `python scripts/fetch_vaswani.py` first (it downloads and checks them), then run this script again.",
              file=sys.stderr)
        return 2
    qrels = load_qrels(ROOT / "data/raw/vaswani/qrels")
    queries = pd.read_csv(run / "queries_used.csv", dtype={"qid": str})
    pq_o = pd.read_csv(run / "per_query_original.csv", dtype={"qid": str})
    pq_r = pd.read_csv(run / "per_query_rewrites.csv", dtype={"qid": str})
    summ = {n: pd.read_csv(run / "analysis" / f"summary_{n}.csv") for n in
            ("baseline", "primary", "by_generator", "hybrid_vs_components", "stability_vs_effectiveness")}

    check("collection: queries with judgments", len(qrels) == meta["collection"]["n_queries"] == len(queries),
          f"{len(qrels)} / {meta['collection']['n_queries']}")
    check("collection: judged pairs", sum(len(v) for v in qrels.values()) == meta["collection"]["n_qrels_pairs"],
          str(sum(len(v) for v in qrels.values())))

    # 1-2: per-query metrics from the saved rankings ---------------------------------------------------------
    rewrite_ids = {r["rewrite_id"]: r for r in (json.loads(l) for l in (run / "rewrites_used.jsonl").read_text().splitlines())}
    max_diff = {"ndcg@10": 0.0, "recall@100": 0.0, "mrr@10": 0.0, "overlap@10": 0.0}
    rbo_pairs, rbo_max = 0, 0.0
    mine_o: dict[tuple[str, str], dict] = {}
    mine_r: dict[tuple[str, str], dict] = {}
    for s in SYSTEMS:
        rk = read_rankings(run / "rankings" / f"{s}.jsonl.gz")
        sub_o = pq_o[pq_o.system == s].set_index("qid")
        sub_r = pq_r[pq_r.system == s].set_index("rewrite_id")
        for qid in queries["qid"]:
            docs = rk[qid]["docs"]
            vals = {"ndcg@10": ndcg10(docs, qrels[qid]), "recall@100": recall100(docs, qrels[qid]), "mrr@10": mrr10(docs, qrels[qid])}
            mine_o[(s, qid)] = {**vals, "docs": docs}
            for k, v in vals.items():
                max_diff[k] = max(max_diff[k], abs(v - sub_o.loc[qid, k]))
        for rid, row in sub_r.iterrows():
            qid = row["qid"]
            docs = rk[rid]["docs"]
            vals = {"ndcg@10": ndcg10(docs, qrels[qid]), "recall@100": recall100(docs, qrels[qid]), "mrr@10": mrr10(docs, qrels[qid])}
            ov = overlap10(mine_o[(s, qid)]["docs"], docs)
            vals["overlap@10"] = ov
            mine_r[(s, rid)] = {**vals, "qid": qid, "category": row["category"], "generator": row["generator"]}
            for k, v in vals.items():
                max_diff[k] = max(max_diff[k], abs(v - row[k]))
            a = mine_o[(s, qid)]["docs"]
            if len(a) == 100 and len(docs) == 100:
                rbo_pairs += 1
                rbo_max = max(rbo_max, abs(rbo_ext_equal_length(a, docs) - row["rbo_p0.9"]))
    for k, v in max_diff.items():
        check(f"per-query {k} recomputed from rankings", v < 1e-9, f"max abs diff {v:.2e}")
    check("RBO(p=0.9) recomputed for pairs of full-length rankings", rbo_pairs > 0 and rbo_max < 1e-9,
          f"{rbo_pairs} pairs, max abs diff {rbo_max:.2e}")
    check("every kept rewrite has a ranking for every system", len(mine_r) == len(SYSTEMS) * meta["counts"]["rewrites_kept"],
          str(len(mine_r)))

    # 3: summaries ------------------------------------------------------------------------------------------
    tol = 1e-9
    base = summ["baseline"].set_index("system")
    worst = 0.0
    for s in SYSTEMS:
        for k in ("ndcg@10", "recall@100", "mrr@10"):
            mean = float(np.mean([mine_o[(s, q)][k] for q in queries["qid"]]))
            worst = max(worst, abs(mean - base.loc[s, k]))
    check("baseline means (nDCG@10, Recall@100, MRR@10)", worst < tol, f"max abs diff {worst:.2e}")

    prim = summ["primary"].set_index(["system", "category"])
    by_gen = summ["by_generator"].set_index(["system", "generator"])
    qids = list(queries["qid"])

    def per_query(s: str, key: str, value: str, metric: str):
        """qid -> (original metric, mean rewrite metric) for queries with at least one kept rewrite of this category/generator."""
        grouped: dict[str, list[float]] = {}
        for (sys_, rid), r in mine_r.items():
            if sys_ == s and r[key] == value:
                grouped.setdefault(r["qid"], []).append(r[metric])
        ids = sorted(grouped, key=lambda q: qids.index(q))
        orig = np.array([mine_o[(s, q)][metric] for q in ids]) if metric in mine_o[(s, qids[0])] else None
        return ids, orig, np.array([np.mean(grouped[q]) for q in ids])

    worst_rel = worst_mean = worst_ov = 0.0
    n_ok = True
    for s in SYSTEMS:
        for c in CATEGORIES:
            ids, m0, mb = per_query(s, "category", c, "ndcg@10")
            row = prim.loc[(s, c)]
            n_ok &= (len(ids) == row["n_queries"])
            worst_mean = max(worst_mean, abs(m0.mean() - row["ndcg@10_orig"]), abs(mb.mean() - row["ndcg@10_rewrite"]))
            worst_rel = max(worst_rel, abs((mb.mean() / m0.mean() - 1) - row["ndcg@10_rel"]))
            _, _, ov = per_query(s, "category", c, "overlap@10")
            worst_ov = max(worst_ov, abs(ov.mean() - row["overlap@10"]))
    check("primary table: number of queries per category", n_ok)
    check("primary table: original / rewrite means of nDCG@10", worst_mean < tol, f"max abs diff {worst_mean:.2e}")
    check("primary table: relative changes", worst_rel < tol, f"max abs diff {worst_rel:.2e}")
    check("primary table: overlap@10", worst_ov < tol, f"max abs diff {worst_ov:.2e}")

    worst_g = 0.0
    for s in SYSTEMS:
        for g in sorted({r["generator"] for r in rewrite_ids.values()}):
            _, m0, mb = per_query(s, "generator", g, "ndcg@10")
            worst_g = max(worst_g, abs((mb.mean() / m0.mean() - 1) - by_gen.loc[(s, g), "ndcg@10_rel"]))
    check("by-generator table: relative changes", worst_g < tol, f"max abs diff {worst_g:.2e}")

    hyb = summ["hybrid_vs_components"].set_index(["component", "category"])
    worst_h = 0.0
    for comp in ("bm25", "lsa"):
        for c in CATEGORIES:
            ids, h0, hb = per_query("rrf_bm25_lsa", "category", c, "ndcg@10")
            _, c0, cb = per_query(comp, "category", c, "ndcg@10")
            worst_h = max(worst_h, abs(np.mean((hb - h0) - (cb - c0)) - hyb.loc[(comp, c), "diff_in_absolute_ndcg@10_change"]))
    check("hybrid-minus-component differences", worst_h < tol, f"max abs diff {worst_h:.2e}")

    stab = summ["stability_vs_effectiveness"].set_index("system")
    worst_sp = worst_sp_rounded = 0.0
    rbo_by_key = {(r["system"], r["rewrite_id"]): r["rbo_p0.9"] for _, r in pq_r.iterrows()}
    for s in SYSTEMS:
        xs, ys = [], []
        for (sys_, rid), r in mine_r.items():
            if sys_ == s:
                xs.append(rbo_by_key[(s, rid)])
                ys.append(abs(r["ndcg@10"] - mine_o[(s, r["qid"])]["ndcg@10"]))
        reported = stab.loc[s, "spearman_rbo_vs_abs_delta_ndcg@10"]
        worst_sp = max(worst_sp, abs(spearmanr(xs, ys).statistic - reported))
        # exact ties in |delta nDCG@10| are split by floating-point noise (differences of about 1e-17) in the pipeline's values;
        # ranking the values rounded to 12 decimals treats them as the ties they are
        worst_sp_rounded = max(worst_sp_rounded, abs(spearmanr(np.round(xs, 12), np.round(ys, 12)).statistic - reported))
    check("Spearman(RBO, |delta nDCG@10|) point estimates (tolerance 1e-4, see note)", worst_sp < 1e-4 and worst_sp_rounded < 1e-4,
          f"max abs diff {worst_sp:.1e} as computed, {worst_sp_rounded:.1e} with ties resolved by rounding; "
          "the pipeline ranks unrounded values, so exact ties are split by floating-point noise")

    # 4: fresh Monte-Carlo ----------------------------------------------------------------------------------
    worst_ci = 0.0
    raw_p, keys = [], []
    for s in SYSTEMS:
        for c in CATEGORIES:
            _, m0, mb = per_query(s, "category", c, "ndcg@10")
            row = prim.loc[(s, c)]
            lo, hi = boot_ci_ratio(m0, mb, B=20000, seed=777)
            worst_ci = max(worst_ci, abs(lo - row["ndcg@10_rel_lo"]), abs(hi - row["ndcg@10_rel_hi"]))
            raw_p.append(sign_flip_p(mb - m0, B=400000, seed=778))
            keys.append((s, c))
    check("95% cluster-bootstrap intervals re-estimated with another seed (20,000 resamples)", worst_ci < 0.012,
          f"max endpoint difference {worst_ci:.4f} (Monte-Carlo tolerance 0.012)")
    worst_p = max(abs(p - prim.loc[k, "p_signflip"]) for p, k in zip(raw_p, keys))
    check("sign-flip p-values re-estimated with another seed (400,000 flips)", worst_p < 0.004, f"max abs diff {worst_p:.4f}")
    adj = holm(raw_p)
    # the reported Holm values are computed from the reported raw p-values; compare decisions and values within MC error
    worst_holm = max(abs(a - prim.loc[k, "p_holm"]) for a, k in zip(adj, keys))
    same_decisions = all((a < 0.05) == (prim.loc[k, "p_holm"] < 0.05) for a, k in zip(adj, keys))
    check("Holm-adjusted p-values and decisions", same_decisions and worst_holm < 0.03, f"max abs diff {worst_holm:.4f}")

    # 5: provenance -----------------------------------------------------------------------------------------
    def sha(path: Path, n: int | None = None) -> str:
        data = path.read_bytes()
        return hashlib.sha256(data if n is None else data[:n]).hexdigest()

    plan_ok = sha(ROOT / "docs/ANALYSIS_PLAN.md", 8130) == meta["inputs"]["analysis_plan_sha256"]
    check("analysis plan: first 8,130 bytes hash to the value stored at run time", plan_ok)
    check("rewrite file hash equals the value stored at run time",
          sha(ROOT / "data/rewrites/vaswani_rewrites.jsonl") == meta["inputs"]["rewrite_file_sha256"])
    code_bad = [p for p, h in meta["code_sha256"].items() if sha(ROOT / p) != h]
    check("code files that produced the run are unchanged since the run", not code_bad, ", ".join(code_bad))
    raw = {n: ROOT / "data/raw/vaswani" / n for n in meta["collection"]["file_sha256"]}
    if all(p.exists() for p in raw.values()):
        bad = [n for n, p in raw.items() if sha(p) != meta["collection"]["file_sha256"][n]]
        check("raw Vaswani files match the checksums recorded at run time", not bad, ", ".join(bad))
    else:
        check("raw Vaswani files present (run scripts/fetch_vaswani.py)", False)

    # 6: manuscript -----------------------------------------------------------------------------------------
    spec = importlib.util.spec_from_file_location("build_paper", ROOT / "scripts/build_paper.py")
    bp = importlib.util.module_from_spec(spec)
    sys.modules["build_paper"] = bp
    spec.loader.exec_module(bp)
    data = bp.load_all(ROOT)
    fresh = bp.Resolver(data).sub((ROOT / "paper/manuscript_template.md").read_text(encoding="utf-8"))
    saved = (ROOT / "paper/manuscript_draft.md").read_text(encoding="utf-8")
    check("paper/manuscript_draft.md equals a fresh build from the template and the result files", fresh == saved)
    readme_fresh = bp.Resolver(data).sub((ROOT / "docs/README_template.md").read_text(encoding="utf-8"))
    check("README.md equals a fresh build from docs/README_template.md and the result files",
          readme_fresh == (ROOT / "README.md").read_text(encoding="utf-8"))
    failed_claims = [n for n, ok in bp.claims(data) if not ok]
    check("all data-dependent sentences of the manuscript hold", not failed_claims, "; ".join(failed_claims))
    quoted = {int(m) for m in re.findall(r"(\d+) automated tests", saved)}
    try:
        out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", str(ROOT / "tests")],
                             capture_output=True, text=True, cwd=ROOT, timeout=300)
        m = re.search(r"(\d+) tests? collected", out.stdout)
        if m:
            n_collected = int(m.group(1))
        else:  # pytest -q prints one "path: count" line per file (newer versions) or one node id per test (older versions)
            per_file = [int(x) for x in re.findall(r"^\S+\.py: (\d+)$", out.stdout, re.M)]
            n_collected = sum(per_file) if per_file else len([l for l in out.stdout.splitlines() if "::" in l])
        check("test count quoted in the manuscript equals the number of collected tests", quoted == {n_collected},
              f"manuscript {sorted(quoted)}, collected {n_collected}")
        if args.run_tests:
            res = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", str(ROOT / "tests")],
                                 capture_output=True, text=True, cwd=ROOT, timeout=1800)
            summary = next((l.strip(" =") for l in reversed(res.stdout.splitlines()) if re.search(r"\d+ passed", l)), res.stderr[-200:])
            check("full test suite passes", res.returncode == 0, summary)
    except Exception as exc:  # noqa: BLE001
        check("pytest available to count tests", False, str(exc))

    n_fail = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n{len(RESULTS) - n_fail} of {len(RESULTS)} checks passed")
    if args.out:
        lines = ["# Independent verification report", "",
                 "Produced by `scripts/verify_results.py`, which recomputes the reported numbers from the saved rankings and the relevance "
                 "judgments without using the `qvr` package. See the docstring of the script for what each check does.", "",
                 "| result | check | detail |", "|:--|:--|:--|"]
        lines += [f"| {'PASS' if ok else '**FAIL**'} | {n} | {d} |" for n, ok, d in RESULTS]
        lines += ["", f"{len(RESULTS) - n_fail} of {len(RESULTS)} checks passed."]
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
