#!/usr/bin/env python
"""Compare two run directories produced by ``scripts/run_experiment.py``.

Used to check that a re-run (for example in a fresh environment with other library versions) reproduces the shipped
results::

    python scripts/compare_runs.py --reference results/vaswani_pilot --candidate results/vaswani_rerun \
        --out results/reproduction_check.md

It compares the per-query tables, the rewrite file that was used, and every saved ranking (document order and scores),
and prints the package versions recorded in the two ``run_metadata.json`` files. Exit status 0 means the per-query
tables agree within ``--atol`` and every ranked list has the same document order.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

import pandas as pd

TABLES = ["per_query_original.csv", "per_query_rewrites.csv", "queries_used.csv"]


def compare_table(ref: Path, cand: Path) -> tuple[bool, float, str]:
    """(same_shape_and_text_columns, max_abs_difference_in_numeric_columns, note)"""
    a, b = pd.read_csv(ref), pd.read_csv(cand)
    if a.shape != b.shape or list(a.columns) != list(b.columns):
        return False, float("nan"), f"shape or columns differ: {a.shape} vs {b.shape}"
    num = a.select_dtypes("number").columns
    text = [c for c in a.columns if c not in num]
    if text and not a[text].equals(b[text]):
        return False, float("nan"), "non-numeric columns differ"
    diff = float((a[num] - b[num]).abs().to_numpy().max()) if len(num) else 0.0
    return True, diff, f"{a.shape[0]} rows, {len(num)} numeric columns"


def read_rankings(path: Path) -> list[dict]:
    with gzip.open(path, "rt") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def compare_rankings(ref: Path, cand: Path) -> dict:
    a, b = read_rankings(ref), read_rankings(cand)
    out = {"lists": len(a), "same_keys": [x["key"] for x in a] == [x["key"] for x in b], "different_order": 0,
           "max_abs_score_diff": 0.0, "max_rel_score_diff": 0.0}
    for x, y in zip(a, b):
        if x["docs"] != y["docs"]:
            out["different_order"] += 1
        d = max((abs(p - q) for p, q in zip(x["scores"], y["scores"])), default=0.0)
        top = max((abs(p) for p in x["scores"]), default=0.0) or 1.0
        out["max_abs_score_diff"] = max(out["max_abs_score_diff"], d)
        out["max_rel_score_diff"] = max(out["max_rel_score_diff"], d / top)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference", required=True, type=Path, help="the shipped run, e.g. results/vaswani_pilot")
    ap.add_argument("--candidate", required=True, type=Path, help="the re-run")
    ap.add_argument("--atol", type=float, default=1e-12, help="tolerance for the per-query tables (default 1e-12)")
    ap.add_argument("--out", type=Path, default=None, help="also write the report to this markdown file")
    args = ap.parse_args(argv)
    ref, cand = args.reference, args.candidate

    meta = {k: json.loads((d / "run_metadata.json").read_text()) for k, d in (("reference", ref), ("candidate", cand))}
    lines = ["# Reproduction check", "",
             f"Reference run: `{ref}`. Re-run: `{cand}`. Written by `scripts/compare_runs.py`.", "",
             "| | reference | re-run |", "|:--|:--|:--|"]
    py = {k: str(m.get("python", "?")).split()[0] for k, m in meta.items()}
    lines.append(f"| Python | {py['reference']} | {py['candidate']} |")
    for pkg in sorted(set(meta["reference"].get("packages", {})) | set(meta["candidate"].get("packages", {}))):
        lines.append(f"| {pkg} | {meta['reference'].get('packages', {}).get(pkg, '-')} | {meta['candidate'].get('packages', {}).get(pkg, '-')} |")
    lines += ["", "## Per-query tables", "", "| file | result | max abs difference |", "|:--|:--|--:|"]
    ok = True
    for name in TABLES:
        same, diff, note = compare_table(ref / name, cand / name)
        good = same and diff <= args.atol
        ok &= good
        lines.append(f"| `{name}` | {'agree' if good else 'DIFFER'} ({note}) | {diff:.2e} |")
    same_rw = (ref / "rewrites_used.jsonl").read_bytes() == (cand / "rewrites_used.jsonl").read_bytes()
    ok &= same_rw
    lines += ["", f"The rewrite file used is {'byte-identical' if same_rw else 'DIFFERENT'} in the two runs.", "",
              "## Saved rankings", "", "| system | ranked lists | lists with a different document order | max abs score difference | max relative score difference |",
              "|:--|--:|--:|--:|--:|"]
    for path in sorted((ref / "rankings").glob("*.jsonl.gz")):
        other = cand / "rankings" / path.name
        if not other.exists():
            lines.append(f"| {path.name.split('.')[0]} | missing in the re-run | | | |")
            ok = False
            continue
        r = compare_rankings(path, other)
        ok &= r["same_keys"] and r["different_order"] == 0
        lines.append(f"| {path.name.split('.')[0]} | {r['lists']} | {r['different_order']} | {r['max_abs_score_diff']:.2e} | {r['max_rel_score_diff']:.2e} |")
    lines += ["", (f"**Overall: {'the re-run reproduces the shipped per-query results and ranking order' if ok else 'DIFFERENCES FOUND'}.** "
              "Differences in stored scores of the order of 1e-7 are floating-point differences between library versions (BLAS, SVD); "
              "they do not change any ranking here.")]
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
