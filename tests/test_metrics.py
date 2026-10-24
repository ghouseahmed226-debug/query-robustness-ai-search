import math

import numpy as np
import pytest

from qvr.metrics import mrr_at_k, ndcg_at_k, recall_at_k, score_ranking

pytrec_eval = pytest.importorskip("pytrec_eval")


def random_case(seed, n_docs=300, n_q=40, run_len=100):
    rng = np.random.default_rng(seed)
    docs = [f"d{i}" for i in range(n_docs)]
    qrels, run = {}, {}
    for q in range(n_q):
        qid = f"q{q}"
        rel_idx = rng.choice(n_docs, size=int(rng.integers(1, 25)), replace=False)
        qrels[qid] = {docs[i]: int(rng.integers(1, 4)) for i in rel_idx}
        for i in rng.choice(n_docs, size=10, replace=False):
            qrels[qid].setdefault(docs[i], 0)
        rel_vec = np.array([qrels[qid].get(d, 0) for d in docs], dtype=float)
        scores = rng.random(n_docs) + 0.7 * rel_vec * rng.random(n_docs)
        run[qid] = [docs[i] for i in np.argsort(-scores)[:run_len]]
    return qrels, run


def test_matches_pytrec_eval_graded():
    qrels, run = random_case(1)
    full = {q: {d: float(len(r) - i) for i, d in enumerate(r)} for q, r in run.items()}
    top10 = {q: {d: float(10 - i) for i, d in enumerate(r[:10])} for q, r in run.items()}
    ref_full = pytrec_eval.RelevanceEvaluator(qrels, {"ndcg_cut_10", "recall_100"}).evaluate(full)
    ref_10 = pytrec_eval.RelevanceEvaluator(qrels, {"recip_rank"}).evaluate(top10)
    for q in run:
        ours = score_ranking(run[q], qrels[q])
        assert ours["ndcg@10"] == pytest.approx(ref_full[q]["ndcg_cut_10"], abs=1e-9)
        assert ours["recall@100"] == pytest.approx(ref_full[q]["recall_100"], abs=1e-9)
        assert ours["mrr@10"] == pytest.approx(ref_10[q]["recip_rank"], abs=1e-9)


def test_matches_ranx_means():
    ranx = pytest.importorskip("ranx")
    qrels, run = random_case(2)
    pos = {q: {d: r for d, r in v.items() if r > 0} for q, v in qrels.items()}
    scored = {q: {d: float(len(r) - i) for i, d in enumerate(r)} for q, r in run.items()}
    ref = ranx.evaluate(ranx.Qrels(pos), ranx.Run(scored), ["ndcg@10", "recall@100", "mrr@10"])
    ours = {m: np.mean([score_ranking(run[q], qrels[q])[m] for q in run]) for m in ("ndcg@10", "recall@100", "mrr@10")}
    for m, val in ours.items():
        assert val == pytest.approx(ref[m], abs=1e-9), m


def test_hand_computed_ndcg():
    rels = {"a": 3, "b": 2, "c": 0}
    got = ndcg_at_k(["b", "a"], rels, 10)
    dcg = 2 / math.log2(2) + 3 / math.log2(3)
    idcg = 3 / math.log2(2) + 2 / math.log2(3)
    assert got == pytest.approx(dcg / idcg)


def test_edge_cases():
    assert ndcg_at_k([], {"a": 1}, 10) == 0.0
    assert recall_at_k([], {"a": 1}, 100) == 0.0
    assert mrr_at_k([], {"a": 1}, 10) == 0.0
    assert ndcg_at_k(["a"], {}, 10) == 0.0  # no relevant documents -> defined as 0, such queries are excluded upstream
    assert mrr_at_k(["x", "y", "a"], {"a": 1}, 2) == 0.0  # relevant doc beyond the cutoff
    assert mrr_at_k(["x", "y", "a"], {"a": 1}, 3) == pytest.approx(1 / 3)
    assert recall_at_k(["a", "b"], {"a": 1, "z": 2}, 100) == 0.5
    assert ndcg_at_k(["a"], {"a": 1}, 10) == 1.0


def test_cutoffs_when_runs_are_longer_than_the_cutoffs():
    """pytrec_eval cuts at 10 / 100 itself; our functions must as well when handed a longer ranking."""
    qrels, run = random_case(3, n_docs=400, n_q=30, run_len=250)
    full = {q: {d: float(len(r) - i) for i, d in enumerate(r)} for q, r in run.items()}
    ref = pytrec_eval.RelevanceEvaluator(qrels, {"ndcg_cut_10", "recall_100", "recip_rank"}).evaluate(full)
    n_beyond = 0
    for q in run:
        ours = score_ranking(run[q], qrels[q])
        assert ours["ndcg@10"] == pytest.approx(ref[q]["ndcg_cut_10"], abs=1e-9)
        assert ours["recall@100"] == pytest.approx(ref[q]["recall_100"], abs=1e-9)
        # trec_eval's recip_rank is uncut; MRR@10 equals it whenever the first relevant document is in the top 10
        first = next((i for i, d in enumerate(run[q], 1) if qrels[q].get(d, 0) > 0), None)
        if first is not None and first <= 10:
            assert ours["mrr@10"] == pytest.approx(ref[q]["recip_rank"], abs=1e-9)
        else:
            assert ours["mrr@10"] == 0.0
        n_beyond += sum(1 for d in run[q][100:] if qrels[q].get(d, 0) > 0)
    assert n_beyond > 0  # the test really contains relevant documents beyond rank 100


def test_cutoff_boundaries():
    ranked = [f"x{i}" for i in range(100)] + ["rel"]  # relevant document at rank 101
    assert recall_at_k(ranked, {"rel": 1}, 100) == 0.0
    ranked = [f"x{i}" for i in range(99)] + ["rel"]  # rank 100
    assert recall_at_k(ranked, {"rel": 1}, 100) == 1.0
    ranked = [f"x{i}" for i in range(10)] + ["rel"]  # rank 11
    assert ndcg_at_k(ranked, {"rel": 1}, 10) == 0.0 and mrr_at_k(ranked, {"rel": 1}, 10) == 0.0
    ranked = [f"x{i}" for i in range(9)] + ["rel"]  # rank 10
    assert mrr_at_k(ranked, {"rel": 1}, 10) == pytest.approx(0.1)
    assert ndcg_at_k(ranked, {"rel": 1}, 10) == pytest.approx(1 / math.log2(11))
