import math
import random

import pytest
from scipy import stats as sps
from sklearn.metrics import cohen_kappa_score

from qvr.audit import (
    apply_human_labels,
    cohen_kappa,
    make_blind_sheet,
    score_audit,
    wilson_interval,
)
from qvr.rewrites import HUMAN_VERIFIED, REVIEW_LABELS


def records():
    out = []
    for g, cat, status in (("NeighbCharSwap", "misspelling", "automatic_by_construction"),
                           ("LLM_Paraphrase", "paraphrasing", "llm_reviewed"),
                           ("RandomOrderSwap", "ordering", "llm_reviewed")):
        for i in range(10):
            out.append({"qid": str(i), "rewrite_id": f"{i}__{g}", "category": cat, "generator": g,
                        "query": f"{g} rewrite {i}", "original_query": f"original {i}",
                        "meaning_preserved": i < 7, "review_status": status,
                        "review_label": "" if status.startswith("auto") else ("equivalent" if i < 7 else "different")})
    out.append({"qid": "99", "rewrite_id": "99__X", "category": "ordering", "generator": "RandomOrderSwap",
                "query": "q", "original_query": "o", "meaning_preserved": None, "review_status": "unreviewed"})
    return out


def test_wilson_matches_scipy():
    for k, n in ((0, 10), (10, 10), (3, 17), (50, 93)):
        lo, hi = wilson_interval(k, n)
        ref = sps.binomtest(k, n).proportion_ci(confidence_level=0.95, method="wilson")
        assert lo == pytest.approx(ref.low, abs=1e-9) and hi == pytest.approx(ref.high, abs=1e-9)
    assert all(math.isnan(x) for x in wilson_interval(0, 0))


def test_kappa_matches_sklearn_and_edge_cases():
    rng = random.Random(4)
    for _ in range(20):
        a = [rng.choice(REVIEW_LABELS) for _ in range(60)]
        b = [x if rng.random() < 0.6 else rng.choice(REVIEW_LABELS) for x in a]
        assert cohen_kappa(a, b) == pytest.approx(cohen_kappa_score(a, b), abs=1e-12)
    assert cohen_kappa(["equivalent"] * 5, ["equivalent"] * 5) != cohen_kappa(["equivalent"] * 5, ["equivalent"] * 5)  # nan
    assert cohen_kappa(["equivalent", "different"], ["equivalent", "different"]) == 1.0
    with pytest.raises(ValueError):
        cohen_kappa(["a"], ["a", "b"])


def test_blind_sheet_hides_everything_but_the_pair_and_is_reproducible():
    recs = records()
    blind, key = make_blind_sheet(recs, per_generator=4, seed=1)
    assert (blind, key) == make_blind_sheet(recs, per_generator=4, seed=1)
    assert len(blind) == 12 and len({b["audit_id"] for b in blind}) == 12  # unreviewed candidate skipped
    assert set(blind[0]) == {"audit_id", "original_query", "rewrite_query", "human_label", "human_notes"}
    assert all(b["human_label"] == "" for b in blind)
    text = " ".join(str(v) for b in blind for k, v in b.items() if k in ("audit_id", "original_query"))
    assert "Neighb" not in text and "LLM" not in text and "equivalent" not in text
    assert [k["audit_id"] for k in key] == [b["audit_id"] for b in blind]
    ids = [k["rewrite_id"] for k in key]
    assert ids != sorted(ids)  # shuffled
    assert len(make_blind_sheet(recs, per_generator=None)[0]) == 30
    with pytest.raises(ValueError):
        make_blind_sheet([{**recs[0], "original_query": ""}])


def _filled(blind, key, human):
    out = []
    for b, k in zip(blind, key):
        row = dict(b)
        row["human_label"] = human(k)
        out.append(row)
    return out


def test_score_audit_by_hand():
    blind, key = make_blind_sheet(records(), per_generator=None, seed=2)
    # the human agrees with the analysis everywhere except two kept rewrites and one dropped rewrite
    flips = {k["rewrite_id"] for k in key if k["meaning_preserved_in_analysis"] is True}
    flips = set(sorted(flips)[:2])
    dropped_flip = min(k["rewrite_id"] for k in key if k["meaning_preserved_in_analysis"] is False)

    def human(k):
        valid = bool(k["meaning_preserved_in_analysis"]) ^ (k["rewrite_id"] in flips) ^ (k["rewrite_id"] == dropped_flip)
        return "equivalent" if valid else "different"

    rep = score_audit(_filled(blind, key, human), key)
    assert rep["n_labelled"] == 30
    assert rep["analysis_set_validity"]["n"] == 21 and rep["analysis_set_validity"]["human_equivalent"] == 19
    assert rep["false_drop_rate"]["n"] == 9 and rep["false_drop_rate"]["human_equivalent"] == 1
    assert rep["analysis_set_validity_by_generator"]["NeighbCharSwap"]["n"] == 7
    ra = rep["reviewer_agreement"]
    assert ra["n"] == 20  # typos have no reviewer label
    # the reviewer said equivalent for 14 of its 20 labels; the human disagrees with it on exactly the flipped ones
    n_dis = sum(1 for k in key if k["reviewer_label"] and
                (k["reviewer_label"] == "equivalent") != (human(k) == "equivalent"))
    assert ra["raw_agreement"] == pytest.approx((20 - n_dis) / 20)


def test_score_audit_ignores_blank_rows_and_rejects_bad_labels():
    blind, key = make_blind_sheet(records(), per_generator=3, seed=2)
    rows = _filled(blind, key, lambda k: "")
    rows[0]["human_label"] = "Equivalent "
    assert score_audit(rows, key)["n_labelled"] == 1
    rows[1]["human_label"] = "maybe"
    with pytest.raises(ValueError):
        score_audit(rows, key)
    with pytest.raises(ValueError):
        score_audit([{"audit_id": "nope", "human_label": "equivalent"}], key)


def test_apply_human_labels_is_explicit_and_partial():
    recs = records()
    blind, key = make_blind_sheet(recs, per_generator=5, seed=3)
    rows = _filled(blind, key, lambda k: "")
    rows[0]["human_label"], rows[1]["human_label"] = "equivalent", "narrower"
    rows[1]["human_notes"] = "adds a constraint"
    with pytest.raises(ValueError):
        apply_human_labels(recs, rows, key, annotator="  ")
    new, n = apply_human_labels(recs, rows, key, annotator="A. Person")
    assert n == 2 and len(new) == len(recs)
    by_id = {r["rewrite_id"]: r for r in new}
    first, second = key[0]["rewrite_id"], key[1]["rewrite_id"]
    assert by_id[first]["review_status"] == HUMAN_VERIFIED and by_id[first]["meaning_preserved"] is True
    assert by_id[second]["meaning_preserved"] is False and by_id[second]["review_note"] == "adds a constraint"
    assert by_id[first]["reviewer"] == "human: A. Person"
    assert by_id[first]["previous_review_status"] == next(r for r in recs if r["rewrite_id"] == first)["review_status"]
    untouched = [r for r in new if r["rewrite_id"] not in (first, second)]
    assert all(r["review_status"] != HUMAN_VERIFIED for r in untouched)
    assert next(r for r in recs if r["rewrite_id"] == first)["review_status"] != HUMAN_VERIFIED  # input not mutated
    with pytest.raises(ValueError):
        apply_human_labels([r for r in recs if r["rewrite_id"] != first], rows, key, annotator="A")
