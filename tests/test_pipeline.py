import gzip
import json

import pandas as pd
import pytest
from synthetic import HashingEncoder, build_collection, make_rewrites

from qvr.metrics import score_ranking
from qvr.run import RunConfig, run_experiment

SYSTEMS = ["bm25", "lsa", "dense", "rrf_bm25_lsa", "rrf_bm25_dense"]


def load(out):
    orig = pd.read_csv(out / "per_query_original.csv", dtype={"qid": str})
    rew = pd.read_csv(out / "per_query_rewrites.csv", dtype={"qid": str, "rewrite_id": str})
    return orig, rew


def test_all_systems_present(synthetic_run):
    out, coll, recs = synthetic_run
    orig, rew = load(out)
    assert sorted(orig.system.unique()) == sorted(SYSTEMS)
    assert len(orig) == len(SYSTEMS) * len(coll.queries)
    assert len(rew) == len(SYSTEMS) * len(recs)
    meta = json.loads((out / "run_metadata.json").read_text())
    assert meta["counts"]["rewrites_kept"] == len(recs)
    assert meta["collection"]["name"] == "synthetic"


def test_bag_of_words_systems_ignore_word_order_and_identical_queries(synthetic_run):
    """Every system in this test is order-invariant, so 'reversed' and 'identical' rewrites must change nothing."""
    out, _, _ = synthetic_run
    _, rew = load(out)
    same = rew[rew.category.isin(["reversed", "identical"])]
    assert len(same) > 0
    for col in ("d_ndcg@10", "d_recall@100", "d_mrr@10"):
        assert (same[col] == 0).all(), col
    assert (same["rbo_p0.9"] - 1.0).abs().max() < 1e-12
    full = same[same["n_returned"] >= 10]
    assert len(full) > 0 and (full["overlap@10"] == 1.0).all()


def test_dropword_changes_something(synthetic_run):
    out, _, _ = synthetic_run
    _, rew = load(out)
    d = rew[rew.category == "dropword"]
    assert (d["rbo_p0.9"] < 1.0).any()


def test_csv_metrics_equal_recomputation_from_saved_rankings(synthetic_run):
    out, coll, _recs = synthetic_run
    orig, rew = load(out)
    for system in ("bm25", "rrf_bm25_lsa"):
        rankings = {}
        with gzip.open(out / "rankings" / f"{system}.jsonl.gz", "rt", encoding="utf-8") as f:
            for line in f:
                o = json.loads(line)
                rankings[o["key"]] = o
        for _, row in rew[rew.system == system].head(40).iterrows():
            m = score_ranking(rankings[row.rewrite_id]["docs"], coll.qrels[row.qid])
            assert row["ndcg@10"] == pytest.approx(m["ndcg@10"], abs=1e-12)
            assert row["recall@100"] == pytest.approx(m["recall@100"], abs=1e-12)
            o = orig[(orig.system == system) & (orig.qid == row.qid)].iloc[0]
            assert row["d_ndcg@10"] == pytest.approx(m["ndcg@10"] - o["ndcg@10"], abs=1e-12)


def _load_rankings(out, system):
    rankings = {}
    with gzip.open(out / "rankings" / f"{system}.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            rankings[o["key"]] = o["docs"]
    return rankings


def test_stability_columns_equal_independent_recomputation(synthetic_run):
    rbo_pkg = pytest.importorskip("rbo")
    out, _, _ = synthetic_run
    _, rew = load(out)
    n_checked = n_partial = 0
    for system in ("bm25", "lsa", "rrf_bm25_dense"):
        rankings = _load_rankings(out, system)
        for _, row in rew[rew.system == system].iterrows():
            a, b = rankings[row.qid][:100], rankings[row.rewrite_id][:100]
            assert row["overlap@10"] == pytest.approx(len(set(a[:10]) & set(b[:10])) / 10, abs=1e-12)
            if a and b:
                ref = rbo_pkg.RankingSimilarity(a, b).rbo_ext(p=0.9)
            else:
                ref = 1.0 if (not a and not b) else 0.0
            assert row["rbo_p0.9"] == pytest.approx(ref, abs=1e-9), (system, row.rewrite_id)
            n_checked += 1
            n_partial += int(0.0 < row["rbo_p0.9"] < 1.0)
    assert n_checked > 100 and n_partial > 10  # the check is not vacuous: many genuinely partial overlaps


def test_runs_are_deterministic(tmp_path, synthetic_run):
    out, coll, recs = synthetic_run
    again = tmp_path / "again"
    cfg = RunConfig(systems=tuple(SYSTEMS), lsa_dim=20, discard_identical_rewrites=False)
    run_experiment(coll, recs, cfg, again, encoders={"dense": HashingEncoder()})
    for name in ("per_query_original.csv", "per_query_rewrites.csv"):
        assert (out / name).read_bytes() == (again / name).read_bytes(), name


def test_identical_rewrites_are_discarded_by_default(tmp_path):
    coll = build_collection()
    recs = make_rewrites(coll)
    run_experiment(coll, recs, RunConfig(systems=("bm25",)), tmp_path)
    meta = json.loads((tmp_path / "run_metadata.json").read_text())
    assert meta["counts"]["rewrites_dropped"]["identical_to_original"] == len(coll.queries)
    assert "identical" not in meta["counts"]["rewrites_kept_by_category"]


def test_ignore_identical_ids(tmp_path):
    coll = build_collection()
    qid = "q0_0"
    coll.doc_ids.append(qid)  # a document whose id equals a query id, containing exactly that query
    coll.doc_texts.append(coll.queries[qid] + " " + coll.queries[qid])
    rank = {}
    for flag in (False, True):
        out = tmp_path / str(flag)
        run_experiment(coll, [], RunConfig(systems=("bm25",), ignore_identical_ids=flag), out)
        with gzip.open(out / "rankings" / "bm25.jsonl.gz", "rt") as f:
            rank[flag] = {json.loads(line)["key"]: json.loads(line)["docs"] for line in f}[qid]
    assert qid in rank[False][:3]
    assert qid not in rank[True]


def test_unknown_system_and_missing_dense_model(tmp_path):
    coll = build_collection()
    with pytest.raises(ValueError):
        run_experiment(coll, [], RunConfig(systems=("nope",)), tmp_path)
    with pytest.raises(ValueError):
        run_experiment(coll, [], RunConfig(systems=("dense",)), tmp_path)


def test_retrieval_depth_is_exactly_top_k(tmp_path):
    """The reported depth (100 in the real runs) must really be applied to every ranking."""
    coll = build_collection()
    recs = make_rewrites(coll)
    shallow, deep = tmp_path / "shallow", tmp_path / "deep"
    base = {"lsa_dim": 20, "discard_identical_rewrites": False}
    run_experiment(coll, recs, RunConfig(systems=("bm25", "lsa", "rrf_bm25_lsa"), top_k=15, **base), shallow)
    run_experiment(coll, recs, RunConfig(systems=("bm25", "lsa"), top_k=100, **base), deep)
    for system in ("bm25", "lsa", "rrf_bm25_lsa"):
        lengths = [len(d) for d in _load_rankings(shallow, system).values()]
        assert max(lengths) == 15, system  # never deeper than top_k, and the cut-off is actually reached
        if system != "bm25":
            assert min(lengths) == 15  # dense / fused systems always fill the list
    for system in ("bm25", "lsa"):  # a shallower run is exactly the prefix of a deeper one
        s, d = _load_rankings(shallow, system), _load_rankings(deep, system)
        assert all(d[k][:15] == s[k] for k in s)
    deep_lengths = [len(d) for d in _load_rankings(deep, "lsa").values()]
    assert min(deep_lengths) == max(deep_lengths) == 100
