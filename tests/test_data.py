import json
from pathlib import Path

import pytest

from qvr.data import load_beir, load_vaswani, natural_key

VASWANI = Path(__file__).resolve().parents[1] / "data" / "raw" / "vaswani"


def test_natural_key():
    assert sorted(["q10", "q2", "q1", "10", "9"], key=natural_key) == ["9", "10", "q1", "q2", "q10"]


@pytest.mark.skipif(not (VASWANI / "doc-text.trec").exists(), reason="Vaswani files not downloaded")
def test_vaswani_counts_match_published_description():
    c = load_vaswani(VASWANI)
    assert c.meta["n_docs"] == 11429
    assert c.meta["n_queries"] == 93
    assert c.meta["n_qrels_pairs"] == 2083
    assert c.meta["qrels_docs_missing_from_corpus"] == 0
    assert c.meta["judgment_values"] == {1: 2083}
    assert len(c.judged_queries()) == c.meta["n_queries_with_relevant"]
    assert c.queries["1"] == "measurement of dielectric constant of liquids by the use of microwave techniques"
    assert all(q == q.lower() and "  " not in q for q in c.queries.values())


def test_beir_loader_on_a_synthetic_directory(tmp_path):
    (tmp_path / "qrels").mkdir()
    (tmp_path / "corpus.jsonl").write_text("\n".join(json.dumps(o) for o in [
        {"_id": "d1", "title": "A title", "text": "some text", "metadata": {}},
        {"_id": "d2", "title": "", "text": "only text"}]))
    (tmp_path / "queries.jsonl").write_text("\n".join(json.dumps(o) for o in [
        {"_id": "q1", "text": "first query"}, {"_id": "q2", "text": "second"}]))
    (tmp_path / "qrels" / "test.tsv").write_text("query-id\tcorpus-id\tscore\nq1\td1\t1\nq1\td2\t0\n")
    c = load_beir(tmp_path)
    assert c.doc_ids == ["d1", "d2"] and c.doc_texts == ["A title some text", "only text"]
    assert c.qrels == {"q1": {"d1": 1, "d2": 0}}
    assert c.judged_queries() == ["q1"]
    assert c.meta["n_qrels_pairs"] == 2 and c.meta["judgment_values"] == {1: 1, 0: 1}
