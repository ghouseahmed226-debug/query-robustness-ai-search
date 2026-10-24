import pandas as pd
import pytest

from qvr.analysis import md_table, summarise


@pytest.fixture(scope="module")
def tables(synthetic_run, tmp_path_factory):
    out, _, _ = synthetic_run
    return summarise(out, tmp_path_factory.mktemp("analysis"), B=500, flip_B=4000, spearman_B=100), out


def test_primary_cell_matches_manual_computation(tables):
    res, out = tables
    orig = pd.read_csv(out / "per_query_original.csv", dtype={"qid": str})
    rew = pd.read_csv(out / "per_query_rewrites.csv", dtype={"qid": str, "rewrite_id": str})
    o = orig[orig.system == "bm25"].set_index("qid")["ndcg@10"]
    r = rew[(rew.system == "bm25") & (rew.category == "dropword")].groupby("qid")["ndcg@10"].mean()
    manual_delta = float((r - o.loc[r.index]).mean())
    manual_rel = float(r.mean() / o.loc[r.index].mean() - 1)
    row = res["primary"].query("system == 'bm25' and category == 'dropword'").iloc[0]
    assert row["n_queries"] == len(r)
    assert row["ndcg@10_delta"] == pytest.approx(manual_delta, abs=1e-12)
    assert row["ndcg@10_rel"] == pytest.approx(manual_rel, abs=1e-12)
    assert row["ndcg@10_delta_lo"] <= manual_delta <= row["ndcg@10_delta_hi"]


def test_zero_change_categories_and_holm(tables):
    res, _ = tables
    p = res["primary"]
    z = p[p.category.isin(["identical", "reversed"])]
    assert len(z) == 10  # 5 systems x 2 categories
    assert (z["ndcg@10_delta"].abs() < 1e-12).all() and (z["p_signflip"] == 1.0).all()
    assert (p["p_holm"] >= p["p_signflip"] - 1e-12).all()
    assert (p["p_holm"] <= 1.0).all() and (p["holm_family_size"] == len(p)).all()
    assert len(p) == 5 * 3


def test_other_tables_exist(tables):
    res, _ = tables
    assert set(res["baseline"].system) == {"bm25", "lsa", "dense", "rrf_bm25_lsa", "rrf_bm25_dense"}
    hv = res["hybrid_vs_components"]
    assert set(hv.hybrid) == {"rrf_bm25_lsa", "rrf_bm25_dense"}
    assert len(hv) == 2 * 2 * 3  # 2 hybrids x 2 components x 3 categories
    assert len(res["stability_vs_effectiveness"]) == 5
    assert "overlap@10" in res["primary"].columns and "rbo_p0.9" in res["primary"].columns


def test_md_table_renders():
    df = pd.DataFrame({"a": ["x", "y"], "b": [0.12345, float("nan")]})
    text = md_table(df, ["a", "b"], "{:.2f}")
    assert text.splitlines()[0] == "| a | b |" and "0.12" in text and "nan" in text


# ---------------------------------------------------------------------------------------------------------------
# Hand-computed check of summarise(): every expected number below is simple arithmetic done by hand.
# ---------------------------------------------------------------------------------------------------------------
def _handcrafted_run(tmp_path):
    qs = ["q1", "q2", "q3", "q4", "q5", "q6"]
    o_ndcg = dict(zip(qs, [.8, .6, .5, .4, .3, .2]))
    o_rec = dict(zip(qs, [1.0, 1.0, .5, .5, .0, .0]))
    o_mrr = dict(zip(qs, [1.0, .5, .5, .25, .0, .0]))
    orig = pd.DataFrame([{"system": "s", "qid": q, "query": "t", "n_returned": 10, "ndcg@10": o_ndcg[q],
                          "recall@100": o_rec[q], "mrr@10": o_mrr[q]} for q in qs])
    rows = []

    def add(qid, rid, cat, gen, ndcg, rec, mrr, ov, rbo):
        rows.append({"system": "s", "qid": qid, "rewrite_id": rid, "category": cat, "generator": gen,
                     "review_status": "x", "original_query": "t", "rewrite_query": "u", "n_returned": 10,
                     "ndcg@10": ndcg, "recall@100": rec, "mrr@10": mrr,
                     "d_ndcg@10": ndcg - o_ndcg[qid], "d_recall@100": rec - o_rec[qid], "d_mrr@10": mrr - o_mrr[qid],
                     "overlap@10": ov, "rbo_p0.9": rbo})

    add("q1", "a1", "A", "g1", .6, 1.0, 1.0, .5, .4)
    add("q1", "a2", "A", "g1", .4, .5, .5, .3, .2)  # q1 has two rewrites in A: their mean (not each) is the data point
    add("q2", "a3", "A", "g2", .5, 1.0, .5, .9, .8)
    add("q3", "a4", "A", "g2", .2, .5, .25, .1, .05)
    add("q4", "a5", "A", "g1", .3, .5, .25, .6, .5)
    add("q5", "a6", "A", "g2", .1, .0, .0, .2, .1)
    add("q6", "a7", "A", "g1", .0, .0, .0, .0, .0)
    add("q1", "b1", "B", "g3", .9, 1.0, 1.0, .7, .6)  # category B covers only q1-q3
    add("q2", "b2", "B", "g3", .6, 1.0, .5, 1.0, 1.0)
    add("q3", "b3", "B", "g3", .6, .5, .5, .8, .7)
    run_dir = tmp_path / "hand_run"
    run_dir.mkdir()
    orig.to_csv(run_dir / "per_query_original.csv", index=False)
    pd.DataFrame(rows).to_csv(run_dir / "per_query_rewrites.csv", index=False)
    return run_dir


def test_summarise_matches_hand_computation(tmp_path):
    res = summarise(_handcrafted_run(tmp_path), tmp_path / "hand_out", B=3000, flip_B=1000, spearman_B=50)
    p = res["primary"].set_index("category")
    a, b = p.loc["A"], p.loc["B"]
    assert (a["n_queries"], a["n_rewrites"], b["n_queries"], b["n_rewrites"]) == (6, 7, 3, 3)
    # category A: per-query mean of rewrites, then the mean over the six queries
    assert a["ndcg@10_orig"] == pytest.approx(2.8 / 6) and a["ndcg@10_rewrite"] == pytest.approx(1.6 / 6)
    assert a["ndcg@10_delta"] == pytest.approx(-0.2)
    assert a["ndcg@10_rel"] == pytest.approx(1.6 / 2.8 - 1)  # ratio of means, not the mean of per-query ratios
    assert a["recall@100_delta"] == pytest.approx(2.75 / 6 - 0.5)
    assert a["mrr@10_delta"] == pytest.approx(1.75 / 6 - 2.25 / 6)
    assert a["overlap@10"] == pytest.approx(2.2 / 6) and a["rbo_p0.9"] == pytest.approx(1.75 / 6)
    # category B (three queries)
    assert b["ndcg@10_delta"] == pytest.approx(0.2 / 3) and b["ndcg@10_rel"] == pytest.approx(2.1 / 1.9 - 1)
    # exact sign-flip tests: six same-sign differences -> 2 / 2^6 ; two equal positive differences -> 2 / 4
    assert a["p_signflip"] == pytest.approx(2 / 64) and b["p_signflip"] == pytest.approx(0.5)
    # Holm over the two cells: smallest p x 2, then monotone
    assert a["p_holm"] == pytest.approx(0.0625) and b["p_holm"] == pytest.approx(0.5)
    assert a["holm_family_size"] == b["holm_family_size"] == 2
    for row, prefix in ((a, "ndcg@10_delta"), (a, "ndcg@10_rel"), (b, "ndcg@10_delta"), (b, "ndcg@10_rel")):
        assert row[prefix + "_lo"] <= row[prefix] <= row[prefix + "_hi"]
    # baseline and generator breakdown
    base = res["baseline"].iloc[0]
    assert base["ndcg@10"] == pytest.approx(2.8 / 6) and base["recall@100"] == pytest.approx(0.5)
    g = res["by_generator"].set_index("generator")
    assert set(g.index) == {"g1", "g2", "g3"} and g.loc["g1", "n_queries"] == 3
    assert g.loc["g1", "ndcg@10_delta"] == pytest.approx(-0.2) and g.loc["g2", "ndcg@10_delta"] == pytest.approx(-0.2)
    assert "p_signflip" not in res["by_generator"].columns  # descriptive only: no tests outside the primary family


def test_summarise_is_reproducible(tmp_path):
    run_dir = _handcrafted_run(tmp_path)
    r1 = summarise(run_dir, tmp_path / "o1", B=500, flip_B=500, spearman_B=20)
    r2 = summarise(run_dir, tmp_path / "o2", B=500, flip_B=500, spearman_B=20)
    for name in ("baseline", "primary", "by_generator", "stability_vs_effectiveness"):
        pd.testing.assert_frame_equal(r1[name], r2[name])
