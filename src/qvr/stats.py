"""Paired, cluster-aware statistics.

The unit of resampling is always the *original query*: rewrites of one query are never treated as independent.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as sps

_CHUNK = 1_000  # bootstrap replicates drawn per block, so memory stays bounded for large query sets


def percentile_ci(samples: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    """Percentile interval; replicates for which the statistic is undefined (NaN) are ignored."""
    samples = np.asarray(samples, dtype=float)
    if not np.isfinite(samples).any():
        return float("nan"), float("nan")
    a = (1.0 - level) / 2.0
    lo, hi = np.nanquantile(samples, [a, 1.0 - a])
    return float(lo), float(hi)


def bootstrap_mean_ci(x, B: int = 10_000, seed: int = 0, level: float = 0.95) -> tuple[float, tuple[float, float]]:
    x = np.asarray(x, dtype=float)
    rng = np.random.default_rng(seed)
    boot = np.empty(B)
    for start in range(0, B, _CHUNK):
        n = min(_CHUNK, B - start)
        idx = rng.integers(0, len(x), size=(n, len(x)))
        boot[start:start + n] = x[idx].mean(axis=1)
    return float(x.mean()), percentile_ci(boot, level)


def bootstrap_ratio_change_ci(num, den, B: int = 10_000, seed: int = 0, level: float = 0.95):
    """Point estimate and CI of ``mean(num) / mean(den) - 1`` resampling clusters (rows) jointly."""
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    if num.shape != den.shape:
        raise ValueError("num and den must be paired")
    rng = np.random.default_rng(seed)
    boot = np.empty(B)
    with np.errstate(divide="ignore", invalid="ignore"):
        for start in range(0, B, _CHUNK):
            n = min(_CHUNK, B - start)
            idx = rng.integers(0, len(num), size=(n, len(num)))
            boot[start:start + n] = num[idx].mean(axis=1) / den[idx].mean(axis=1) - 1.0
        point = num.mean() / den.mean() - 1.0
    return float(point), percentile_ci(boot, level)


def sign_flip_pvalue(d, B: int = 200_000, seed: int = 0, exact_max_n: int = 16, chunk: int = 20_000) -> float:
    """Two-sided sign-flip permutation test of H0: the paired differences are symmetric around zero.

    Statistic: |sum(d)|. Exact enumeration when at most ``exact_max_n`` differences are non-zero, otherwise
    Monte Carlo with ``B`` random sign patterns and p = (k + 1) / (B + 1).
    """
    d = np.asarray(d, dtype=float)
    d = d[d != 0.0]
    m = len(d)
    if m == 0:
        return 1.0
    observed = abs(d.sum())
    tol = 1e-12 * max(1.0, float(np.abs(d).sum()))
    if m <= exact_max_n:
        patterns = np.arange(2 ** m, dtype=np.int64)[:, None]
        signs = 1.0 - 2.0 * ((patterns >> np.arange(m, dtype=np.int64)) & 1)
        sums = np.abs(signs @ d)
        return float((sums >= observed - tol).sum() / sums.shape[0])
    rng = np.random.default_rng(seed)
    hits = 0
    done = 0
    while done < B:
        n = min(chunk, B - done)
        signs = rng.integers(0, 2, size=(n, m)) * 2.0 - 1.0
        hits += int((np.abs(signs @ d) >= observed - tol).sum())
        done += n
    return (hits + 1) / (B + 1)


def holm_adjust(pvalues) -> np.ndarray:
    """Holm-Bonferroni step-down adjusted p-values (Holm, 1979)."""
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    order = np.argsort(p, kind="stable")
    adjusted = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * p[i])
        adjusted[i] = min(1.0, running)
    return adjusted


def _spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman rho, or NaN when it is undefined (fewer than 3 pairs or a constant variable)."""
    if len(x) < 3 or np.ptp(x) == 0.0 or np.ptp(y) == 0.0:
        return float("nan")
    return float(sps.spearmanr(x, y).statistic)


def spearman_cluster_bootstrap(x, y, clusters, B: int = 2_000, seed: int = 0, level: float = 0.95):
    """Spearman rho over pairs plus a CI from resampling whole clusters (original queries).

    Undefined cases (constant input, e.g. a category in which no ranking changed) give NaN rather than a warning.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    clusters = np.asarray(clusters)
    point = _spearman(x, y)
    if np.isnan(point):
        return point, (float("nan"), float("nan"))
    uniq = np.unique(clusters)
    members = [np.flatnonzero(clusters == u) for u in uniq]
    rng = np.random.default_rng(seed)
    boot = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, len(uniq), size=len(uniq))
        idx = np.concatenate([members[i] for i in pick])
        boot[b] = _spearman(x[idx], y[idx])
    return point, percentile_ci(boot, level)
