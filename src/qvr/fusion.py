"""Rank fusion."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence


def rrf_fuse(ranked_lists: Sequence[Sequence[str]], k: int = 60, depth: int | None = 100,
             out_depth: int = 100) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion (Cormack, Clarke & Buettcher, SIGIR 2009).

    ``score(d) = sum_i 1 / (k + rank_i(d))`` with ranks starting at 1; a document absent from a list contributes
    nothing from that list. Ties are broken by best rank in any input list, then by document id, so the output is
    deterministic. Only the first ``depth`` entries of every input list are used.
    """
    scores: dict[str, float] = defaultdict(float)
    best: dict[str, int] = {}
    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked[:depth] if depth else ranked, start=1):
            scores[doc] += 1.0 / (k + rank)
            if doc not in best or rank < best[doc]:
                best[doc] = rank
    ordered = sorted(scores, key=lambda d: (-scores[d], best[d], d))
    return [(d, scores[d]) for d in ordered[:out_depth]]
