"""A self-contained BM25 implementation (no Elasticsearch / Java needed).

Scoring (classic Robertson-Sparck Jones form with Lucene's non-negative IDF)::

    score(q, d) = sum over query-term occurrences t of
                  idf(t) * tf(t, d) * (k1 + 1) / (tf(t, d) + k1 * (1 - b + b * |d| / avgdl))
    idf(t)      = ln(1 + (N - df(t) + 0.5) / (df(t) + 0.5))

Lucene >= 8 drops the constant (k1 + 1) numerator; that rescales every score by the same factor and does not
change any ranking (checked in tests/test_bm25.py against ``bm25s``). A repeated query term is counted once per
occurrence, as in Lucene's BooleanQuery and in ``rank_bm25``. Document length is the exact number of analysed
tokens (Lucene stores a lossy 1-byte norm instead). Documents with score 0 are not returned.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import scipy.sparse as sp

from .ranking import top_k_indices
from .text import Analyzer


class BM25Index:
    name = "bm25"

    def __init__(self, k1: float = 1.2, b: float = 0.75, analyzer: Analyzer | None = None):
        self.k1 = float(k1)
        self.b = float(b)
        self.analyzer = analyzer or Analyzer()
        self.doc_ids: list[str] = []
        self.vocab: dict[str, int] = {}
        self.W: sp.csr_matrix | None = None
        self.idf: np.ndarray | None = None
        self.doc_len: np.ndarray | None = None
        self.avgdl: float = 0.0

    def fit(self, doc_ids, texts) -> "BM25Index":
        doc_ids = list(doc_ids)
        texts = list(texts)
        if len(doc_ids) != len(texts):
            raise ValueError("doc_ids and texts differ in length")
        n = len(doc_ids)
        self.doc_ids = doc_ids
        vocab: dict[str, int] = {}
        rows: list[int] = []
        cols: list[int] = []
        vals: list[int] = []
        dl = np.zeros(n, dtype=np.float64)
        for i, text in enumerate(texts):
            tokens = self.analyzer(text)
            dl[i] = len(tokens)
            for term, count in Counter(tokens).items():
                j = vocab.get(term)
                if j is None:
                    j = len(vocab)
                    vocab[term] = j
                rows.append(i)
                cols.append(j)
                vals.append(count)
        n_terms = len(vocab)
        rows_a = np.asarray(rows, dtype=np.int64)
        cols_a = np.asarray(cols, dtype=np.int64)
        tf = np.asarray(vals, dtype=np.float64)
        df = np.bincount(cols_a, minlength=n_terms).astype(np.float64)
        self.avgdl = float(dl.mean()) if n else 0.0
        self.idf = np.log1p((n - df + 0.5) / (df + 0.5))
        avgdl = self.avgdl if self.avgdl > 0 else 1.0
        denom = tf + self.k1 * (1.0 - self.b + self.b * dl[rows_a] / avgdl)
        weights = self.idf[cols_a] * tf * (self.k1 + 1.0) / denom
        self.W = sp.csr_matrix((weights, (rows_a, cols_a)), shape=(n, n_terms))
        self.vocab = vocab
        self.doc_len = dl
        return self

    def _query_matrix(self, texts) -> sp.csc_matrix:
        rows: list[int] = []
        cols: list[int] = []
        vals: list[float] = []
        for j, text in enumerate(texts):
            for term, count in Counter(self.analyzer(text)).items():
                i = self.vocab.get(term)
                if i is not None:
                    rows.append(i)
                    cols.append(j)
                    vals.append(float(count))
        return sp.csc_matrix((vals, (rows, cols)), shape=(len(self.vocab), len(texts)))

    def score_all(self, text: str) -> np.ndarray:
        """BM25 score of every document for one query (used by tests)."""
        return np.asarray((self.W @ self._query_matrix([text])).todense()).ravel()

    def search(self, queries: dict[str, str], k: int = 100, batch: int = 32) -> dict[str, list[tuple[str, float]]]:
        qids = list(queries)
        out: dict[str, list[tuple[str, float]]] = {}
        for start in range(0, len(qids), batch):
            chunk = qids[start:start + batch]
            scores = np.asarray((self.W @ self._query_matrix([queries[q] for q in chunk])).todense())
            for col, qid in enumerate(chunk):
                column = scores[:, col]
                idx = top_k_indices(column, k)
                idx = idx[column[idx] > 0]
                out[qid] = [(self.doc_ids[i], float(column[i])) for i in idx]
        return out

    def describe(self) -> dict:
        return {
            "system": "bm25",
            "k1": self.k1,
            "b": self.b,
            "n_docs": len(self.doc_ids),
            "n_terms": len(self.vocab),
            "avgdl": self.avgdl,
            "analyzer": self.analyzer.describe(),
        }
