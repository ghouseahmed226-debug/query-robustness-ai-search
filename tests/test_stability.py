import random

import pytest

from qvr.stability import jaccard_at_k, overlap_at_k, rbo_ext


def test_identities():
    a = [f"d{i}" for i in range(30)]
    assert rbo_ext(a, a, 0.9) == pytest.approx(1.0, abs=1e-12)
    assert rbo_ext(a, [f"x{i}" for i in range(30)], 0.9) == 0.0
    assert rbo_ext([], [], 0.9) == 1.0
    assert rbo_ext(a, [], 0.9) == 0.0


def test_hand_computed_examples():
    # S=[a,b], T=[b,a], p=0.9: X_1=0, X_2=2 -> 1*0.81 + (0.1/0.9)*(1*0.81) = 0.9
    assert rbo_ext(["a", "b"], ["b", "a"], 0.9) == pytest.approx(0.9)
    # S=[a], T=[a,b]: the shorter list is fully consistent with the longer one -> 1.0
    assert rbo_ext(["a"], ["a", "b"], 0.9) == pytest.approx(1.0)


def test_symmetry_and_range():
    rng = random.Random(0)
    pool = [f"d{i}" for i in range(60)]
    for _ in range(100):
        a = rng.sample(pool, rng.randint(1, 40))
        b = rng.sample(pool, rng.randint(1, 40))
        v = rbo_ext(a, b, 0.9)
        assert 0.0 <= v <= 1.0 + 1e-12
        assert v == pytest.approx(rbo_ext(b, a, 0.9), abs=1e-12)


def test_matches_rbo_package_on_random_lists():
    rbo_pkg = pytest.importorskip("rbo")
    rng = random.Random(1)
    pool = [f"d{i}" for i in range(80)]
    for _ in range(200):
        a = rng.sample(pool, rng.randint(1, 50))
        b = rng.sample(pool, rng.randint(1, 50))
        for p in (0.8, 0.9, 0.95):
            ref = rbo_pkg.RankingSimilarity(a, b).rbo_ext(p=p)
            assert rbo_ext(a, b, p) == pytest.approx(ref, abs=1e-9), (a, b, p)


def test_overlap_and_jaccard():
    a = list("abcdefghij")
    b = list("abcdefghik")
    assert overlap_at_k(a, b, 10) == 0.9
    assert overlap_at_k(a, a, 10) == 1.0
    assert overlap_at_k(a, list("klmnopqrst"), 10) == 0.0
    assert jaccard_at_k(a, b, 10) == pytest.approx(9 / 11)
    assert overlap_at_k(a[:5], a[:5], 10) == 0.5  # normalised by k, as pre-specified


def test_invalid_p():
    with pytest.raises(ValueError):
        rbo_ext(["a"], ["a"], 1.0)
