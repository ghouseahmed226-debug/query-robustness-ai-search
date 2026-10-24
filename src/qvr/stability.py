"""Ranking-stability measures between two ranked lists (no relevance judgments involved).

Stability is not effectiveness: two different rankings can be equally relevant. These measures only say how much
the system's output moved when the query was rewritten.
"""
from __future__ import annotations

from typing import Sequence


def overlap_at_k(a: Sequence[str], b: Sequence[str], k: int = 10) -> float:
    """|top-k(a) intersect top-k(b)| / k."""
    return len(set(a[:k]) & set(b[:k])) / k


def jaccard_at_k(a: Sequence[str], b: Sequence[str], k: int = 10) -> float:
    sa, sb = set(a[:k]), set(b[:k])
    union = sa | sb
    return len(sa & sb) / len(union) if union else 1.0


def rbo_ext(a: Sequence[str], b: Sequence[str], p: float = 0.9, depth: int | None = None) -> float:
    """Extrapolated rank-biased overlap (Webber, Moffat & Zobel, TOIS 2010, Eq. 32).

    Handles lists of different lengths (for example when BM25 returns fewer than ``depth`` matching documents).
    Lists must not contain duplicates. Conventions for degenerate input: two empty rankings are identical (1.0);
    exactly one empty ranking shares nothing with the other (0.0).
    """
    if not 0 < p < 1:
        raise ValueError("p must be in (0, 1)")
    s_list, t_list = list(a), list(b)
    if depth is not None:
        s_list, t_list = s_list[:depth], t_list[:depth]
    if not s_list and not t_list:
        return 1.0
    if not s_list or not t_list:
        return 0.0
    if len(s_list) > len(t_list):
        s_list, t_list = t_list, s_list  # S is the shorter list, T the longer
    s_len, l_len = len(s_list), len(t_list)

    x_at: list[int] = []
    seen_s: set[str] = set()
    seen_t: set[str] = set()
    overlap = 0
    for d in range(1, l_len + 1):
        sd = s_list[d - 1] if d <= s_len else None
        td = t_list[d - 1]
        if sd is not None and sd == td:
            overlap += 1
        else:
            if sd is not None and sd in seen_t:
                overlap += 1
            if td in seen_s:
                overlap += 1
        if sd is not None:
            seen_s.add(sd)
        seen_t.add(td)
        x_at.append(overlap)

    x_s, x_l = x_at[s_len - 1], x_at[l_len - 1]
    total = 0.0
    for d in range(1, l_len + 1):
        total += x_at[d - 1] / d * p ** d
    for d in range(s_len + 1, l_len + 1):
        total += x_s * (d - s_len) / (s_len * d) * p ** d
    return (1 - p) / p * total + ((x_l - x_s) / l_len + x_s / s_len) * p ** l_len
