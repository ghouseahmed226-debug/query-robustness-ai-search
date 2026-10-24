"""Tiny synthetic collection and stub encoder used ONLY to test plumbing (never to produce reported results)."""
from __future__ import annotations

import random
import zlib

import numpy as np

from qvr.data import Collection


def build_collection(n_topics: int = 8, docs_per_topic: int = 24, words_per_topic: int = 30, seed: int = 0) -> Collection:
    """Topic-structured toy collection. Documents mix their own topic's words with a few words of the next topic
    and background noise; each query has 3 words of its topic plus one distractor word from the next topic, so
    effectiveness varies across queries (it is not saturated at 1.0)."""
    rng = random.Random(seed)
    topic_words = [[f"t{t}w{i}" for i in range(words_per_topic)] for t in range(n_topics)]
    background = [f"bg{i}" for i in range(80)]
    doc_ids, texts, topic_of = [], [], {}
    for t in range(n_topics):
        nxt = (t + 1) % n_topics
        for j in range(docs_per_topic):
            did = f"d{t}_{j}"
            words = rng.sample(topic_words[t], 9) + rng.sample(topic_words[nxt], 4) + rng.sample(background, 9)
            rng.shuffle(words)
            doc_ids.append(did)
            texts.append(" ".join(words))
            topic_of[did] = t
    queries, qrels = {}, {}
    for t in range(n_topics):
        nxt = (t + 1) % n_topics
        for j in range(5):
            qid = f"q{t}_{j}"
            words = rng.sample(topic_words[t], 3) + rng.sample(topic_words[nxt], 1)
            rng.shuffle(words)
            queries[qid] = " ".join(words)
            qrels[qid] = {d: 1 for d, tt in topic_of.items() if tt == t}
    return Collection("synthetic", doc_ids, texts, queries, qrels, {})


class HashingEncoder:
    """Deterministic stand-in for a neural encoder: hashed bag of words, L2-normalised."""

    name = "dense"

    def __init__(self, dim: int = 64):
        self.dim = dim

    def _enc(self, texts):
        m = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in t.lower().split():
                m[i, zlib.crc32(w.encode()) % self.dim] += 1.0
        n = np.linalg.norm(m, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return m / n

    def encode_documents(self, texts):
        return self._enc(list(texts))

    def encode_queries(self, texts):
        return self._enc(list(texts))

    def describe(self):
        return {"system": "dense", "kind": "test stub (hashed bag of words)", "dim": self.dim}


def make_rewrites(coll: Collection) -> list[dict]:
    recs = []
    for qid, q in coll.queries.items():
        words = q.split()
        base = {"qid": qid, "meaning_preserved": True, "review_status": "automatic_by_construction"}
        recs.append({**base, "rewrite_id": f"{qid}__drop", "category": "dropword", "generator": "DropLast",
                     "query": " ".join(words[:-1])})
        recs.append({**base, "rewrite_id": f"{qid}__rev", "category": "reversed", "generator": "Reverse",
                     "query": " ".join(reversed(words))})
        recs.append({**base, "rewrite_id": f"{qid}__same", "category": "identical", "generator": "Copy", "query": q})
    return recs
