import math

import numpy as np
import pytest

from qvr.bm25 import BM25Index
from qvr.ranking import top_k_indices
from qvr.text import Analyzer

TEXTS = [
    "the cat sat on the mat",
    "dogs chase cats and cats chase mice",
    "a quick brown fox jumps over the lazy dog",
    "microwave measurement of dielectric constant",
    "dielectric liquids and microwave techniques for measurement of loss",
    "cats are small mammals",
    "measurement of the temperature of plasma using shock waves",
    "transistor amplifiers with low drift",
]
IDS = [f"d{i}" for i in range(len(TEXTS))]
QUERIES = ["dielectric measurement", "cats", "microwave liquids techniques", "cats cats chase", "zzzz unknownterm",
           "measurement of plasma temperature"]


def naive(texts, query, k1, b, analyzer):
    toks = [analyzer(t) for t in texts]
    n = len(texts)
    avgdl = sum(len(t) for t in toks) / n
    df = {}
    for t in toks:
        for term in set(t):
            df[term] = df.get(term, 0) + 1
    out = []
    for t in toks:
        s = 0.0
        for term in analyzer(query):  # one contribution per query-term occurrence
            tf = t.count(term)
            if tf:
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(t) / avgdl))
        out.append(s)
    return np.array(out)


@pytest.mark.parametrize("k1,b", [(1.2, 0.75), (0.9, 0.4), (2.0, 0.0)])
def test_matches_naive_formula(k1, b):
    an = Analyzer()
    idx = BM25Index(k1, b, an).fit(IDS, TEXTS)
    for q in QUERIES:
        np.testing.assert_allclose(idx.score_all(q), naive(TEXTS, q, k1, b, an), rtol=1e-12, atol=1e-12)


def test_matches_bm25s_lucene_up_to_constant_factor():
    bm25s = pytest.importorskip("bm25s")
    an = Analyzer()
    tokens = [an(t) for t in TEXTS]
    ref = bm25s.BM25(method="lucene", k1=1.2, b=0.75)
    ref.index(tokens, show_progress=False)
    idx = BM25Index(1.2, 0.75, an).fit(IDS, TEXTS)
    for q in ["dielectric measurement", "cats", "microwave liquids techniques", "measurement of plasma temperature"]:
        theirs = np.asarray(ref.get_scores(an(q)))
        np.testing.assert_allclose(idx.score_all(q) / (1.2 + 1.0), theirs, rtol=1e-5, atol=1e-8)


def test_search_order_and_zero_scores_excluded():
    idx = BM25Index().fit(IDS, TEXTS)
    res = idx.search({"q": "dielectric measurement", "none": "zzzz"}, k=100)
    scores = [s for _, s in res["q"]]
    assert scores == sorted(scores, reverse=True)
    assert all(s > 0 for s in scores)
    assert res["none"] == []
    full = idx.score_all("dielectric measurement")
    assert [d for d, _ in res["q"]] == [IDS[i] for i in np.argsort(-full, kind="stable") if full[i] > 0]
    assert len(idx.search({"q": "cats measurement"}, k=2)["q"]) == 2


def test_word_order_invariance_is_exact():
    idx = BM25Index().fit(IDS, TEXTS)
    a = idx.search({"q": "microwave dielectric liquids measurement"}, k=100)["q"]
    b = idx.search({"q": "measurement liquids dielectric microwave"}, k=100)["q"]
    assert a == b


def test_top_k_tie_breaking_is_by_index():
    scores = np.array([1.0, 3.0, 3.0, 2.0, 3.0, 0.0])
    assert list(top_k_indices(scores, 2)) == [1, 2]
    assert list(top_k_indices(scores, 4)) == [1, 2, 4, 3]
    assert list(top_k_indices(scores, 100)) == [1, 2, 4, 3, 0, 5]
    assert len(top_k_indices(scores, 0)) == 0
