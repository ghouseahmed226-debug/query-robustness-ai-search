import argparse
import json
import platform
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from beir import util
from beir.datasets.data_loader import GenericDataLoader
from beir.retrieval.evaluation import EvaluateRetrieval
from beir.retrieval.search.lexical import BM25Search


def load_rewrites(path):
    rewrites = defaultdict(list)
    if not path:
        return rewrites
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            required = {"qid", "rewrite_id", "query", "category", "meaning_preserved", "review_status"}
            missing = required - set(item)
            if missing:
                raise ValueError(f"Rewrite line {line_no} missing fields: {sorted(missing)}")
            if item["meaning_preserved"] is not True or item["review_status"] != "human_verified":
                continue
            rewrites[str(item["qid"])].append(item)
    return rewrites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="scifact")
    ap.add_argument("--data-dir", default="data/beir")
    ap.add_argument("--output-dir", default="results/run")
    ap.add_argument("--rewrite-file", default=None)
    ap.add_argument("--max-queries", type=int, default=100)
    ap.add_argument("--methods", nargs="+", default=["bm25"], choices=["bm25"])
    ap.add_argument("--top-k", type=int, default=100)
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    data_root = Path(args.data_dir)
    data_root.mkdir(parents=True, exist_ok=True)

    url = f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{args.dataset}.zip"
    data_path = data_root / args.dataset
    if not data_path.exists():
        downloaded = util.download_and_unzip(url, str(data_root))
        data_path = Path(downloaded)

    corpus, queries, qrels = GenericDataLoader(data_folder=str(data_path)).load(split="test")
    qids = sorted(set(queries) & set(qrels))
    if args.max_queries and args.max_queries > 0:
        qids = qids[:args.max_queries]
    queries = {qid: queries[qid] for qid in qids}
    qrels = {qid: qrels[qid] for qid in qids if qid in qrels}

    metadata = {
        "dataset": args.dataset,
        "split": "test",
        "query_count": len(queries),
        "corpus_count": len(corpus),
        "qrels_query_count": len(qrels),
        "python_version": sys.version,
        "platform": platform.platform(),
        "methods_requested": args.methods,
        "top_k": args.top_k,
        "rewrite_file": args.rewrite_file,
        "note": "Initial reproducibility scaffold; verify split and package versions before research use."
    }
    (out / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # BEIR's BM25Search API is version-sensitive. This follows common BEIR usage;
    # if package updates change the constructor, pin the version and document it.
    results_by_condition = {}
    bm25 = BM25Search(index_name=args.dataset, hostname="localhost", initialize=True)
    retriever = EvaluateRetrieval(bm25, score_function="bm25")
    base_results = retriever.retrieve(corpus, queries)
    results_by_condition["original"] = base_results

    rewrites = load_rewrites(args.rewrite_file)
    rewrite_rows = []
    for qid, items in rewrites.items():
        if qid not in queries:
            continue
        for item in items:
            rewrite_rows.append({
                "qid": qid,
                "rewrite_id": item["rewrite_id"],
                "category": item["category"],
                "query": item["query"],
                "meaning_preserved": item["meaning_preserved"],
                "review_status": item["review_status"],
            })

    # Run each rewrite as an isolated one-query retrieval. Reuse the same corpus
    # and qrels. This simple version prioritizes clarity over speed.
    per_query_rows = []
    for row in rewrite_rows:
        qid = row["qid"]
        one_query = {qid: row["query"]}
        one_result = retriever.retrieve(corpus, one_query)
        result_dict = one_result
        ndcg, _map, recall, mrr = EvaluateRetrieval.evaluate(qrels, result_dict, [1, 3, 5, 10, 100])
        per_query_rows.append({
            **row,
            "ndcg@10": ndcg.get("NDCG@10", np.nan),
            "recall@100": recall.get("Recall@100", np.nan),
            "mrr@10": mrr.get("MRR@10", np.nan),
        })

    # Aggregate original run using the same qrels subset.
    ndcg, _map, recall, mrr = EvaluateRetrieval.evaluate(qrels, base_results, [1, 3, 5, 10, 100])
    summary = {
        "condition": "original",
        "n_queries": len(queries),
        "nDCG@10": ndcg.get("NDCG@10"),
        "Recall@100": recall.get("Recall@100"),
        "MRR@10": mrr.get("MRR@10"),
    }
    (out / "original_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if per_query_rows:
        pd.DataFrame(per_query_rows).to_csv(out / "rewrite_results.csv", index=False)
    else:
        (out / "rewrite_results_README.txt").write_text(
            "No eligible human-verified rewrites were supplied. Add a validated JSONL file before drawing conclusions.\n",
            encoding="utf-8"
        )

    (out / "IMPORTANT.txt").write_text(
        "This is a starter run, not a completed scientific result. Inspect all outputs and logs. "
        "Do not treat a 100-query smoke test as evidence for a publication claim. "
        "The current script implements BM25 only; dense and hybrid systems require a separately tested implementation.\n",
        encoding="utf-8"
    )
    print(json.dumps({"metadata": metadata, "original_summary": summary, "rewrite_rows": len(per_query_rows)}, indent=2))


if __name__ == "__main__":
    main()
