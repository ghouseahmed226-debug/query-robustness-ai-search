#!/usr/bin/env python
"""Run the query-variation robustness experiment on one collection.

Examples
--------
Pilot (Vaswani/NPL, no model downloads needed)::

    python scripts/run_experiment.py --dataset vaswani --data-dir data/raw/vaswani \
        --rewrites data/rewrites/vaswani_rewrites.jsonl \
        --allowed-statuses automatic_by_construction llm_reviewed \
        --systems bm25 lsa rrf_bm25_lsa --out results/vaswani_pilot

BEIR collection with a neural bi-encoder (needs the dataset folder and the model on local disk or a hub)::

    python scripts/run_experiment.py --dataset beir --data-dir /path/to/scifact \
        --rewrites data/rewrites/scifact_rewrites.jsonl \
        --allowed-statuses human_verified \
        --systems bm25 dense rrf_bm25_dense --dense-model sentence-transformers/all-MiniLM-L6-v2 \
        --out results/scifact

By default only ``human_verified`` rewrites are used (the original kit's rule). Anything weaker must be requested
explicitly with ``--allowed-statuses`` and is recorded in ``run_metadata.json``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from qvr.data import load_beir, load_vaswani
from qvr.rewrites import HUMAN_VERIFIED, load_rewrites
from qvr.run import ALL_SYSTEMS, RunConfig, run_experiment

ROOT = Path(__file__).resolve().parents[1]


def code_hashes() -> dict:
    out = {}
    for p in sorted((ROOT / "src" / "qvr").glob("*.py")):
        out[f"src/qvr/{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", choices=["vaswani", "beir"], required=True)
    ap.add_argument("--data-dir", required=True, help="vaswani: folder with doc-text.trec, query-text.trec, qrels; "
                    "beir: dataset folder with corpus.jsonl, queries.jsonl, qrels/<split>.tsv")
    ap.add_argument("--split", default="test", help="BEIR qrels split")
    ap.add_argument("--rewrites", required=True, help="rewrite file (jsonl)")
    ap.add_argument("--allowed-statuses", nargs="+", default=[HUMAN_VERIFIED],
                    help="review_status values to accept (default: human_verified only)")
    ap.add_argument("--systems", nargs="+", default=["bm25", "lsa", "rrf_bm25_lsa"], choices=list(ALL_SYSTEMS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--top-k", type=int, default=100)
    ap.add_argument("--k-rrf", type=int, default=60)
    ap.add_argument("--lsa-dim", type=int, default=300)
    ap.add_argument("--dense-model", default=None, help="sentence-transformers model name or local path")
    ap.add_argument("--dense-query-prefix", default="")
    ap.add_argument("--dense-doc-prefix", default="")
    ap.add_argument("--dense-batch-size", type=int, default=32)
    ap.add_argument("--dense-max-seq-length", type=int, default=None)
    ap.add_argument("--max-queries", type=int, default=None, help="debug only: use the first N judged queries")
    ap.add_argument("--ignore-identical-ids", action="store_true",
                    help="drop a document whose id equals the query id (BEIR ArguAna and Quora convention)")
    ap.add_argument("--keep-identical-rewrites", action="store_true",
                    help="keep rewrites identical to the original query (default: discard)")
    ap.add_argument("--plan", default=str(ROOT / "docs" / "ANALYSIS_PLAN.md"), help="analysis plan to hash into the metadata")
    args = ap.parse_args(argv)

    data_dir = Path(args.data_dir)
    coll = load_vaswani(data_dir) if args.dataset == "vaswani" else load_beir(data_dir, args.split)
    rewrites, dropped = load_rewrites(args.rewrites, allowed_statuses=args.allowed_statuses)
    if not rewrites:
        print("no usable rewrites after the status/meaning filter; nothing to measure", file=sys.stderr)
        return 2

    cfg = RunConfig(
        systems=tuple(args.systems), top_k=args.top_k, k_rrf=args.k_rrf, lsa_dim=args.lsa_dim,
        dense_model=args.dense_model, dense_query_prefix=args.dense_query_prefix,
        dense_doc_prefix=args.dense_doc_prefix, dense_batch_size=args.dense_batch_size,
        dense_max_seq_length=args.dense_max_seq_length, max_queries=args.max_queries,
        ignore_identical_ids=args.ignore_identical_ids, discard_identical_rewrites=not args.keep_identical_rewrites,
    )
    info = run_experiment(
        coll, rewrites, cfg, args.out, rewrite_file=args.rewrites, rewrite_drops=dict(dropped),
        plan_path=args.plan if Path(args.plan).exists() else None,
        extra_meta={"allowed_statuses": list(args.allowed_statuses), "code_sha256": code_hashes(),
                    "command": " ".join(sys.argv)},
    )
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
