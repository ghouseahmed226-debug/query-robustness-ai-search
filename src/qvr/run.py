"""Experiment orchestration: retrieve for original queries and rewrites, score, measure stability, write raw outputs."""
from __future__ import annotations

import csv
import gzip
import json
import platform
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from . import __version__
from .bm25 import BM25Index
from .data import Collection, sha256_file
from .dense import DenseIndex, LSAEncoder, SentenceTransformerEncoder
from .fusion import rrf_fuse
from .metrics import METRIC_NAMES, score_ranking
from .rewrites import normalise_query
from .stability import overlap_at_k, rbo_ext

BASE_SYSTEMS = ("bm25", "lsa", "dense")
HYBRID_SYSTEMS = {"rrf_bm25_lsa": ("bm25", "lsa"), "rrf_bm25_dense": ("bm25", "dense")}
ALL_SYSTEMS = BASE_SYSTEMS + tuple(HYBRID_SYSTEMS)


@dataclass
class RunConfig:
    systems: tuple = ("bm25", "lsa", "rrf_bm25_lsa")
    top_k: int = 100
    k_rrf: int = 60
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    lsa_dim: int = 300
    lsa_seed: int = 0
    dense_model: str | None = None
    dense_query_prefix: str = ""
    dense_doc_prefix: str = ""
    dense_batch_size: int = 32
    dense_max_seq_length: int | None = None
    max_queries: int | None = None
    ignore_identical_ids: bool = False
    discard_identical_rewrites: bool = True
    rbo_p: float = 0.9
    overlap_k: int = 10


def _versions() -> dict:
    out = {}
    for name in ("numpy", "scipy", "pandas", "scikit-learn", "snowballstemmer", "sentence-transformers",
                 "torch", "transformers"):
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    return out


def _build_base(name: str, coll: Collection, cfg: RunConfig, encoders: dict | None):
    if name == "bm25":
        index = BM25Index(cfg.bm25_k1, cfg.bm25_b)
    elif name == "lsa":
        index = DenseIndex(LSAEncoder(cfg.lsa_dim, seed=cfg.lsa_seed), name="lsa")
    elif name == "dense":
        enc = (encoders or {}).get("dense")
        if enc is None:
            if not cfg.dense_model:
                raise ValueError("system 'dense' needs --dense-model (a sentence-transformers model name or path)")
            enc = SentenceTransformerEncoder(
                cfg.dense_model, query_prefix=cfg.dense_query_prefix, doc_prefix=cfg.dense_doc_prefix,
                batch_size=cfg.dense_batch_size, max_seq_length=cfg.dense_max_seq_length,
            )
        index = DenseIndex(enc, name="dense")
    else:
        raise ValueError(f"unknown base system {name!r}")
    return index.fit(coll.doc_ids, coll.doc_texts)


def _write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def run_experiment(collection: Collection, rewrites: list[dict], cfg: RunConfig, out_dir, *, rewrite_file=None,
                   rewrite_drops=None, plan_path=None, encoders: dict | None = None, extra_meta: dict | None = None):
    t_start = time.time()
    out = Path(out_dir)
    (out / "rankings").mkdir(parents=True, exist_ok=True)

    qids = collection.judged_queries()
    if cfg.max_queries:
        qids = qids[: cfg.max_queries]
    queries = {q: collection.queries[q] for q in qids}

    kept: list[dict] = []
    drops = Counter(rewrite_drops or {})
    seen: set[str] = set()
    for r in rewrites:
        qid = str(r["qid"])
        if qid not in queries:
            drops["query_not_selected"] += 1
            continue
        if cfg.discard_identical_rewrites and normalise_query(r["query"]) == normalise_query(queries[qid]):
            drops["identical_to_original"] += 1
            continue
        rid = str(r["rewrite_id"])
        if rid in seen or rid in queries:
            raise ValueError(f"duplicate or colliding rewrite_id {rid!r}")
        seen.add(rid)
        kept.append({**r, "qid": qid, "rewrite_id": rid})

    wanted = set()
    for s in cfg.systems:
        if s in HYBRID_SYSTEMS:
            wanted.update(HYBRID_SYSTEMS[s])
        elif s in BASE_SYSTEMS:
            wanted.add(s)
        else:
            raise ValueError(f"unknown system {s!r}; choose from {ALL_SYSTEMS}")
    needed = [s for s in BASE_SYSTEMS if s in wanted]

    all_queries = dict(queries)
    all_queries.update({r["rewrite_id"]: r["query"] for r in kept})
    qid_of = {q: q for q in queries}
    qid_of.update({r["rewrite_id"]: r["qid"] for r in kept})
    k_ret = cfg.top_k + (1 if cfg.ignore_identical_ids else 0)

    base_runs: dict[str, dict] = {}
    sys_info: dict[str, dict] = {}
    timings: dict[str, dict] = {}
    for name in needed:
        t0 = time.time()
        index = _build_base(name, collection, cfg, encoders)
        t1 = time.time()
        res = index.search(all_queries, k=k_ret)
        t2 = time.time()
        cleaned = {}
        for key, lst in res.items():
            if cfg.ignore_identical_ids:
                lst = [(d, s) for d, s in lst if d != qid_of[key]]
            cleaned[key] = lst[: cfg.top_k]
        base_runs[name] = cleaned
        sys_info[name] = index.describe()
        timings[name] = {"index_s": round(t1 - t0, 3), "search_s": round(t2 - t1, 3)}

    runs = dict(base_runs)
    for h, comps in HYBRID_SYSTEMS.items():
        if h in cfg.systems:
            runs[h] = {
                key: rrf_fuse([[d for d, _ in base_runs[c][key]] for c in comps], k=cfg.k_rrf,
                              depth=cfg.top_k, out_depth=cfg.top_k)
                for key in all_queries
            }
            sys_info[h] = {"system": h, "kind": "reciprocal rank fusion", "components": list(comps),
                           "k": cfg.k_rrf, "input_depth": cfg.top_k, "output_depth": cfg.top_k}

    rbo_col = f"rbo_p{cfg.rbo_p}"
    ov_col = f"overlap@{cfg.overlap_k}"
    orig_rows: list[dict] = []
    rew_rows: list[dict] = []
    for sysname, run in runs.items():
        ranked = {key: [d for d, _ in lst] for key, lst in run.items()}
        base_metrics = {}
        for qid in qids:
            m = score_ranking(ranked[qid], collection.qrels[qid])
            base_metrics[qid] = m
            orig_rows.append({"system": sysname, "qid": qid, "query": queries[qid],
                              "n_returned": len(ranked[qid]), **m})
        for r in kept:
            rid, qid = r["rewrite_id"], r["qid"]
            m = score_ranking(ranked[rid], collection.qrels[qid])
            row = {
                "system": sysname, "qid": qid, "rewrite_id": rid, "category": r["category"],
                "generator": r.get("generator", ""), "review_status": r["review_status"],
                "original_query": queries[qid], "rewrite_query": r["query"], "n_returned": len(ranked[rid]),
            }
            for name in METRIC_NAMES:
                row[name] = m[name]
            for name in METRIC_NAMES:
                row["d_" + name] = m[name] - base_metrics[qid][name]
            row[ov_col] = overlap_at_k(ranked[qid], ranked[rid], cfg.overlap_k)
            row[rbo_col] = rbo_ext(ranked[qid], ranked[rid], p=cfg.rbo_p, depth=cfg.top_k)
            rew_rows.append(row)

    _write_csv(out / "per_query_original.csv", orig_rows)
    if rew_rows:
        _write_csv(out / "per_query_rewrites.csv", rew_rows)
    with open(out / "rewrites_used.jsonl", "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    _write_csv(out / "queries_used.csv", [
        {"qid": q, "query": queries[q], "n_relevant": sum(1 for v in collection.qrels[q].values() if v > 0),
         "n_judged": len(collection.qrels[q])} for q in qids])
    for sysname, run in runs.items():
        with gzip.open(out / "rankings" / f"{sysname}.jsonl.gz", "wt", encoding="utf-8") as f:
            for key, lst in run.items():
                f.write(json.dumps({"key": key, "qid": qid_of[key], "kind": "original" if key in queries else "rewrite",
                                    "docs": [d for d, _ in lst], "scores": [s for _, s in lst]}) + "\n")

    meta = {
        "qvr_version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": _versions(),
        "config": asdict(cfg),
        "systems": sys_info,
        "collection": {"name": collection.name, **collection.meta},
        "counts": {
            "queries_selected": len(qids),
            "rewrites_kept": len(kept),
            "rewrites_kept_by_category": dict(Counter(r["category"] for r in kept)),
            "rewrites_kept_by_generator": dict(Counter(r.get("generator", "") for r in kept)),
            "rewrites_kept_by_status": dict(Counter(r["review_status"] for r in kept)),
            "rewrites_dropped": dict(drops),
        },
        "inputs": {
            "rewrite_file": str(rewrite_file) if rewrite_file else None,
            "rewrite_file_sha256": sha256_file(rewrite_file) if rewrite_file else None,
            "analysis_plan": str(plan_path) if plan_path else None,
            "analysis_plan_sha256": sha256_file(plan_path) if plan_path and Path(plan_path).exists() else None,
        },
        "timings_s": timings,
        "total_runtime_s": round(time.time() - t_start, 3),
    }
    if extra_meta:
        meta.update(extra_meta)
    (out / "run_metadata.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return {"out_dir": str(out), "n_queries": len(qids), "n_rewrites": len(kept), "systems": list(runs)}
