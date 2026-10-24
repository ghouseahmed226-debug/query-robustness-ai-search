"""Deterministic top-k selection shared by every retrieval component."""
from __future__ import annotations

import numpy as np


def top_k_indices(scores: np.ndarray, k: int) -> np.ndarray:
    """Indices of the ``k`` largest scores ordered by (score descending, index ascending).

    Ties are broken by ascending index so that every run is exactly reproducible. Ties that straddle the
    cut-off are resolved the same way: all candidates >= the k-th largest value are sorted and then truncated.
    """
    scores = np.asarray(scores)
    n = scores.shape[0]
    if n == 0 or k <= 0:
        return np.empty(0, dtype=np.int64)
    if k >= n:
        idx = np.arange(n)
    else:
        kth = np.partition(scores, n - k)[n - k]
        idx = np.flatnonzero(scores >= kth)
    order = np.lexsort((idx, -scores[idx]))
    return idx[order][:k]
