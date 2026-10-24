"""Collection loaders (BEIR directory format and the TREC-style Vaswani/NPL files) and small helpers."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


def natural_key(s: str):
    """Sort key that orders ``q2`` before ``q10`` (parts alternate str / int, so keys are always comparable)."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


def sha256_file(path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def normalise_text(text: str, lowercase: bool = False) -> str:
    t = " ".join(text.split())
    return t.lower() if lowercase else t


@dataclass
class Collection:
    name: str
    doc_ids: list
    doc_texts: list
    queries: dict
    qrels: dict
    meta: dict = field(default_factory=dict)

    def judged_queries(self) -> list:
        """Queries with at least one judged-relevant document (judgment > 0), in natural id order."""
        ids = [q for q in self.queries if any(r > 0 for r in self.qrels.get(q, {}).values())]
        return sorted(ids, key=natural_key)


_DOC_RE = re.compile(r"<DOC>\s*<DOCNO>\s*(\S+?)\s*</DOCNO>(.*?)</DOC>", re.S | re.I)
_TOP_RE = re.compile(r"<top>\s*<num>\s*(\S+?)\s*</num>\s*<title>(.*?)</title>\s*</top>", re.S | re.I)


def load_vaswani(root, lowercase_queries: bool = True) -> Collection:
    """Vaswani / NPL as distributed in PyTerrier's ``tests/fixtures/vaswani_npl`` (doc-text.trec, query-text.trec, qrels).

    The corpus is already lower-cased; the queries are upper-case, so they are lower-cased (and whitespace-collapsed)
    here to put queries and documents on the same footing. Every rewrite is lower-cased the same way.
    """
    root = Path(root)
    doc_ids: list[str] = []
    doc_texts: list[str] = []
    for m in _DOC_RE.finditer((root / "doc-text.trec").read_text(encoding="utf-8")):
        doc_ids.append(m.group(1))
        doc_texts.append(normalise_text(m.group(2)))
    if len(set(doc_ids)) != len(doc_ids):
        raise ValueError("duplicate document ids in corpus")
    queries: dict[str, str] = {}
    for m in _TOP_RE.finditer((root / "query-text.trec").read_text(encoding="utf-8")):
        queries[m.group(1)] = normalise_text(m.group(2), lowercase=lowercase_queries)
    qrels: dict[str, dict[str, int]] = {}
    with open(root / "qrels", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 4:
                continue
            qrels.setdefault(parts[0], {})[parts[2]] = int(parts[3])
    known = set(doc_ids)
    meta = {
        "format": "trec (vaswani_npl)",
        "n_docs": len(doc_ids),
        "n_queries": len(queries),
        "n_qrels_pairs": sum(len(v) for v in qrels.values()),
        "n_queries_with_qrels": len(qrels),
        "n_queries_with_relevant": sum(1 for v in qrels.values() if any(r > 0 for r in v.values())),
        "judgment_values": dict(Counter(r for v in qrels.values() for r in v.values())),
        "qrels_docs_missing_from_corpus": sum(1 for v in qrels.values() for d in v if d not in known),
        "queries_lowercased": lowercase_queries,
        "file_sha256": {n: sha256_file(root / n) for n in ("doc-text.trec", "query-text.trec", "qrels")},
    }
    return Collection("vaswani", doc_ids, doc_texts, queries, qrels, meta)


def load_beir(root, split: str = "test") -> Collection:
    """A BEIR dataset directory: corpus.jsonl, queries.jsonl, qrels/<split>.tsv.

    Documents are indexed as ``title + " " + text`` (one field). BEIR's own Elasticsearch baseline indexes title and
    text as separate fields, so BM25 numbers are close to, but not identical with, the published BEIR BM25 numbers.
    """
    root = Path(root)
    doc_ids: list[str] = []
    doc_texts: list[str] = []
    with open(root / "corpus.jsonl", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            o = json.loads(line)
            title = (o.get("title") or "").strip()
            text = (o.get("text") or "").strip()
            doc_ids.append(str(o["_id"]))
            doc_texts.append((title + " " + text).strip())
    if len(set(doc_ids)) != len(doc_ids):
        raise ValueError("duplicate document ids in corpus")
    queries: dict[str, str] = {}
    with open(root / "queries.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                o = json.loads(line)
                queries[str(o["_id"])] = o["text"]
    qrels: dict[str, dict[str, int]] = {}
    qrels_path = root / "qrels" / f"{split}.tsv"
    with open(qrels_path, encoding="utf-8") as f:
        for n, line in enumerate(f):
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            try:
                score = int(float(parts[2]))
            except ValueError:
                if n == 0:  # header line
                    continue
                raise
            qrels.setdefault(parts[0], {})[parts[1]] = score
    known = set(doc_ids)
    meta = {
        "format": "beir",
        "split": split,
        "n_docs": len(doc_ids),
        "n_queries": len(queries),
        "n_qrels_pairs": sum(len(v) for v in qrels.values()),
        "n_queries_with_qrels": len(qrels),
        "n_queries_with_relevant": sum(1 for v in qrels.values() if any(r > 0 for r in v.values())),
        "judgment_values": dict(Counter(r for v in qrels.values() for r in v.values())),
        "qrels_docs_missing_from_corpus": sum(1 for v in qrels.values() for d in v if d not in known),
        "file_sha256": {
            "corpus.jsonl": sha256_file(root / "corpus.jsonl"),
            "queries.jsonl": sha256_file(root / "queries.jsonl"),
            f"qrels/{split}.tsv": sha256_file(qrels_path),
        },
    }
    return Collection(root.name, doc_ids, doc_texts, queries, qrels, meta)
