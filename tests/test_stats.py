import numpy as np
import pytest
from scipy import stats as sps

from qvr.stats import (
    bootstrap_mean_ci,
    bootstrap_ratio_change_ci,
    holm_adjust,
    sign_flip_pvalue,
    spearman_cluster_bootstrap,
)


def test_bootstrap_mean_ci_matches_t_interval():
    x = np.random.default_rng(0).normal(0.3, 1.0, 400)
    mean, (lo, hi) = bootstrap_mean_ci(x, B=20_000, seed=1)
    se = x.std(ddof=1) / np.sqrt(len(x))
    t = sps.t.ppf(0.975, len(x) - 1)
    assert mean == pytest.approx(x.mean())
    assert lo == pytest.approx(mean - t * se, abs=0.01)
    assert hi == pytest.approx(mean + t * se, abs=0.01)


def test_ratio_change_point_and_ci():
    rng = np.random.default_rng(1)
    den = rng.uniform(0.2, 0.9, 200)
    num = den * 0.8 + rng.normal(0, 0.02, 200)
    point, (lo, hi) = bootstrap_ratio_change_ci(num, den, B=5000, seed=2)
    assert point == pytest.approx(num.mean() / den.mean() - 1)
    assert lo < point < hi
    assert -0.25 < lo and hi < -0.15  # true relative change is about -20%


@pytest.mark.parametrize("n", [6, 9, 12])
def test_exact_sign_flip_matches_scipy(n):
    d = np.random.default_rng(n).normal(0.4, 1.0, n)
    ref = sps.permutation_test((d, np.zeros(n)), lambda a, b, axis: np.mean(a - b, axis=axis),
                               permutation_type="samples", alternative="two-sided", n_resamples=np.inf).pvalue
    assert sign_flip_pvalue(d) == pytest.approx(ref, abs=1e-12)


def test_monte_carlo_sign_flip_close_to_t_test():
    d = np.random.default_rng(5).normal(0.25, 1.0, 60)
    mc = sign_flip_pvalue(d, B=100_000, seed=3)
    t_p = sps.ttest_1samp(d, 0.0).pvalue
    assert mc == pytest.approx(t_p, abs=0.02)


def test_sign_flip_degenerate():
    assert sign_flip_pvalue(np.zeros(10)) == 1.0
    assert sign_flip_pvalue([]) == 1.0
    assert sign_flip_pvalue(np.full(30, 0.1), B=20_000) < 0.001


def test_holm():
    adj = holm_adjust([0.01, 0.04, 0.03, 0.005])
    np.testing.assert_allclose(adj, [0.03, 0.06, 0.06, 0.02])
    assert (holm_adjust([0.5, 0.6]) <= 1.0).all()


def test_spearman_cluster_bootstrap():
    rng = np.random.default_rng(7)
    x = rng.normal(size=150)
    y = x + rng.normal(scale=0.7, size=150)
    clusters = np.repeat(np.arange(30), 5)
    rho, (lo, hi) = spearman_cluster_bootstrap(x, y, clusters, B=500, seed=1)
    assert rho == pytest.approx(sps.spearmanr(x, y).statistic)
    assert lo < rho < hi
