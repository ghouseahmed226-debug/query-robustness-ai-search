import pytest

from qvr.fusion import rrf_fuse


def test_rrf_toy_values_and_tiebreak():
    out = rrf_fuse([["a", "b", "c"], ["b", "a", "d"]], k=60)
    scores = dict(out)
    assert scores["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["c"] == pytest.approx(1 / 63)
    assert [d for d, _ in out] == ["a", "b", "c", "d"]  # equal scores: best rank, then doc id


def test_rrf_depth_and_single_list():
    out = rrf_fuse([["a", "b", "c", "d"]], k=60, depth=2)
    assert [d for d, _ in out] == ["a", "b"]
    assert rrf_fuse([[], []]) == []
    assert [d for d, _ in rrf_fuse([["x", "y"], []])] == ["x", "y"]


def test_rrf_out_depth():
    out = rrf_fuse([[str(i) for i in range(50)], [str(i) for i in range(25, 75)]], k=60, out_depth=10)
    assert len(out) == 10
