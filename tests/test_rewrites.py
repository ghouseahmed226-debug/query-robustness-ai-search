import json
import random

import pytest

from qvr.rewrites import (
    NLTK_ENGLISH_STOPWORDS,
    QWERTY_NEIGHBORS,
    audit_sample,
    generate_automatic,
    load_rewrites,
    merge_reviews,
    neighb_char_swap,
    qwerty_char_sub,
    random_char_sub,
    random_order_swap,
    remove_stopwords,
    swap_touches_only_function_words,
)

QUERIES = {
    "1": "measurement of dielectric constant of liquids by the use of microwave techniques",
    "2": "mathematical analysis and design details of waveguide fed microwave radiations",
    "3": "fast transistor counters",
    "4": "i would like information on the range of static relays suitable for use at high switching rates",
    "5": "a to be",
}


def hamming(a, b):
    assert len(a) == len(b)
    return sum(x != y for x, y in zip(a, b))


def diff_tokens(a, b):
    ta, tb = a.split(), b.split()
    assert len(ta) == len(tb)
    return [(x, y) for x, y in zip(ta, tb) if x != y]


def test_stopword_resource():
    assert len(NLTK_ENGLISH_STOPWORDS) == 198
    assert {"the", "of", "you're", "he'll"} <= NLTK_ENGLISH_STOPWORDS


@pytest.mark.parametrize("seed", range(20))
def test_typo_generators_edit_exactly_one_long_word(seed):
    rng = random.Random(seed)
    for q in list(QUERIES.values())[:4]:
        out = neighb_char_swap(q, rng)
        (x, y), = diff_tokens(q, out)
        assert len(x) >= 4 and sorted(x) == sorted(y) and hamming(x, y) == 2
        out = random_char_sub(q, rng)
        (x, y), = diff_tokens(q, out)
        assert len(x) >= 4 and hamming(x, y) == 1
        out = qwerty_char_sub(q, rng)
        (x, y), = diff_tokens(q, out)
        assert len(x) >= 4 and hamming(x, y) == 1
        pos = next(i for i, (a, b) in enumerate(zip(x, y)) if a != b)
        assert y[pos] in QWERTY_NEIGHBORS[x[pos]]


def test_short_queries_are_not_editable():
    rng = random.Random(0)
    assert neighb_char_swap("a to be", rng) is None
    assert random_char_sub("a to be", rng) is None
    assert qwerty_char_sub("a to be", rng) is None


def test_order_swap_preserves_multiset():
    rng = random.Random(3)
    for q in QUERIES.values():
        out = random_order_swap(q, rng)
        if out is None:
            continue
        assert sorted(out.split()) == sorted(q.split())
        assert out != q
        assert sum(a != b for a, b in zip(q.split(), out.split())) == 2
    assert random_order_swap("same same same", rng) is None


def test_remove_stopwords():
    out = remove_stopwords(QUERIES["4"])
    # i / on / the / of / for / at are in the NLTK list; "would" is not (only "wouldn" is)
    assert out == "would like information range static relays suitable use high switching rates"
    assert remove_stopwords("of the and") is None


def test_generate_automatic_is_deterministic_and_skips_identical():
    r1, s1 = generate_automatic(QUERIES, seed=13)
    r2, s2 = generate_automatic(QUERIES, seed=13)
    assert r1 == r2 and s1 == s2
    r3, _ = generate_automatic(QUERIES, seed=14)
    assert r1 != r3
    ids = [r["rewrite_id"] for r in r1]
    assert len(ids) == len(set(ids))
    assert all(r["query"] != r["original_query"] for r in r1)
    # query 3 has no stop words -> RemoveStopWords is identical and must be skipped
    assert ("RemoveStopWords", "identical_to_original") in s1
    assert "3__RemoveStopWords" not in ids
    # ordering rewrites still need a validity judgment, typos do not
    by_gen = {r["generator"]: r for r in r1}
    assert by_gen["RandomOrderSwap"]["review_status"] == "unreviewed" and by_gen["RandomOrderSwap"]["meaning_preserved"] is None
    assert by_gen["NeighbCharSwap"]["review_status"] == "automatic_by_construction"
    # stop-word removal can drop negations or quantifiers, so it is not valid by construction either
    assert by_gen["RemoveStopWords"]["review_status"] == "unreviewed" and by_gen["RemoveStopWords"]["meaning_preserved"] is None


def test_load_rewrites_status_filter(tmp_path):
    recs = [
        {"qid": 1, "rewrite_id": "a", "category": "c", "query": "x", "meaning_preserved": True, "review_status": "human_verified"},
        {"qid": 1, "rewrite_id": "b", "category": "c", "query": "y", "meaning_preserved": True, "review_status": "llm_reviewed"},
        {"qid": 1, "rewrite_id": "c", "category": "c", "query": "z", "meaning_preserved": False, "review_status": "human_verified"},
        {"qid": 2, "rewrite_id": "d", "category": "c", "query": "w", "meaning_preserved": None, "review_status": "unreviewed"},
    ]
    p = tmp_path / "r.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in recs))
    kept, dropped = load_rewrites(p)  # strict default: human_verified only
    assert [r["rewrite_id"] for r in kept] == ["a"]
    assert dropped["status_not_allowed"] == 2 and dropped["not_meaning_preserved"] == 1
    kept, _ = load_rewrites(p, allowed_statuses=("human_verified", "llm_reviewed"))
    assert [r["rewrite_id"] for r in kept] == ["a", "b"]
    assert kept[0]["qid"] == "1"  # ids are normalised to str
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"qid": 1}))
    with pytest.raises(ValueError):
        load_rewrites(bad)


def test_merge_reviews_and_audit_sample():
    cands = [{"qid": "1", "rewrite_id": f"r{i}", "category": "paraphrasing" if i % 2 else "ordering", "query": f"q{i}",
              "meaning_preserved": None, "review_status": "unreviewed"} for i in range(10)]
    reviews = [{"rewrite_id": f"r{i}", "label": "equivalent" if i < 6 else "narrower", "reviewer": "x"} for i in range(9)]
    merged, stats = merge_reviews(cands, reviews)
    assert stats["reviewed:equivalent"] == 6 and stats["reviewed:narrower"] == 3 and stats["unreviewed"] == 1
    assert merged[0]["meaning_preserved"] is True and merged[8]["meaning_preserved"] is False
    assert merged[9]["review_status"] == "unreviewed"
    rows = audit_sample([m for m in merged if m["review_status"] == "llm_reviewed"], per_category=2, seed=1)
    assert len(rows) == 4 and all(r["human_label_equivalent_broader_narrower_different"] == "" for r in rows)
    with pytest.raises(ValueError):
        merge_reviews(cands, [{"rewrite_id": "r0", "label": "maybe"}])


def test_audit_sample_by_generator_is_stratified_and_deterministic():
    recs = [{"qid": str(i), "rewrite_id": f"{g}{i}", "category": c, "generator": g, "query": f"{g} {i}",
             "original_query": "o", "review_label": "equivalent"}
            for g, c in (("GenA", "naturality"), ("GenB", "naturality"), ("GenC", "paraphrasing")) for i in range(12)]
    rows = audit_sample(recs, per_category=5, seed=3, by="generator")
    assert [sum(r["generator"] == g for r in rows) for g in ("GenA", "GenB", "GenC")] == [5, 5, 5]
    assert rows == audit_sample(recs, per_category=5, seed=3, by="generator")
    assert len(audit_sample(recs, per_category=5, seed=3, by="category")) == 10  # 2 categories x 5
    with pytest.raises(ValueError):
        audit_sample(recs, by="nonsense")


def test_function_word_only_rule():
    assert swap_touches_only_function_words("use of the cathode", "use the of cathode")  # of <-> the
    assert not swap_touches_only_function_words("variable capacitance amplifiers", "capacitance variable amplifiers")
    assert not swap_touches_only_function_words("studies of the source", "studies source the of")  # content word moved
    assert not swap_touches_only_function_words("number representation in binary machines",
                                                "number in representation binary machines")  # 'representation' moved
    assert not swap_touches_only_function_words("a b", "a b")  # nothing moved
    with pytest.raises(ValueError):
        swap_touches_only_function_words("a b", "a c")
