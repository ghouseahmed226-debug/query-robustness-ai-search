"""Per-query effectiveness metrics.

Conventions (identical to ``trec_eval`` / ``pytrec_eval`` as used by BEIR, verified in tests):
* a document is relevant when its judgment is > 0; unjudged documents are non-relevant;
* nDCG uses linear gain (the judgment value) and a log2(rank + 1) discount; the ideal ranking is built from all
  judged-relevant documents;
* Recall@k = relevant retrieved in top k / all relevant;
* MRR@k = reciprocal rank of the first relevant document within the top k (0 if none).
"""
from __future__ import annotations

import math
from typing import Mapping, Sequence


def _dcg(gains: Sequence[float]) -> float:
    return float(sum(g / math.log2(i + 2) for i, g in enumerate(gains)))


def ndcg_at_k(ranked: Sequence[str], rels: Mapping[str, int], k: int = 10) -> float:
    gains = [max(rels.get(d, 0), 0) for d in ranked[:k]]
    ideal = sorted((r for r in rels.values() if r > 0), reverse=True)[:k]
    idcg = _dcg(ideal)
    return _dcg(gains) / idcg if idcg > 0 else 0.0


def recall_at_k(ranked: Sequence[str], rels: Mapping[str, int], k: int = 100) -> float:
    n_rel = sum(1 for r in rels.values() if r > 0)
    if n_rel == 0:
        return 0.0
    return sum(1 for d in ranked[:k] if rels.get(d, 0) > 0) / n_rel


def mrr_at_k(ranked: Sequence[str], rels: Mapping[str, int], k: int = 10) -> float:
    for i, d in enumerate(ranked[:k], start=1):
        if rels.get(d, 0) > 0:
            return 1.0 / i
    return 0.0


METRIC_NAMES = ("ndcg@10", "recall@100", "mrr@10")


def score_ranking(ranked: Sequence[str], rels: Mapping[str, int]) -> dict[str, float]:
    return {
        "ndcg@10": ndcg_at_k(ranked, rels, 10),
        "recall@100": recall_at_k(ranked, rels, 100),
        "mrr@10": mrr_at_k(ranked, rels, 10),
    }
