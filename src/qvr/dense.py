"""Dense retrieval: exact inner-product search over pluggable encoders.

Encoders implement ``encode_documents(texts)`` and ``encode_queries(texts)`` returning L2-normalised float32
matrices (so the inner product is the cosine similarity). Two are provided:

* ``LSAEncoder`` - a *non-neural* latent-semantic baseline (TF-IDF -> truncated SVD). It needs no model download
  and exists so the dense/fusion code paths can be exercised on real data in offline environments. It is NOT a
  substitute for a pretrained neural retriever and results from it must never be described as such.
* ``SentenceTransformerEncoder`` - a thin wrapper around a ``sentence-transformers`` bi-encoder (optional
  dependency; needs the model weights locally or access to a model hub).
"""
from __future__ import annotations

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from .ranking import top_k_indices
from .text import Analyzer


class LSAEncoder:
    name = "lsa"

    def __init__(self, n_components: int = 300, analyzer: Analyzer | None = None, seed: int = 0, n_iter: int = 7):
        self.n_components = int(n_components)
        self.analyzer = analyzer or Analyzer()
        self.seed = int(seed)
        self.n_iter = int(n_iter)
        self.vectorizer: TfidfVectorizer | None = None
        self.svd: TruncatedSVD | None = None
        self._doc: np.ndarray | None = None
        self.n_components_: int | None = None

    def fit(self, texts) -> LSAEncoder:
        texts = list(texts)
        self.vectorizer = TfidfVectorizer(
            analyzer=self.analyzer, sublinear_tf=True, use_idf=True, smooth_idf=True, norm="l2"
        )
        x = self.vectorizer.fit_transform(texts)
        k = max(1, min(self.n_components, min(x.shape) - 1))
        self.svd = TruncatedSVD(n_components=k, algorithm="randomized", n_iter=self.n_iter, random_state=self.seed)
        z = self.svd.fit_transform(x)
        self._doc = normalize(z).astype(np.float32)
        self.n_components_ = k
        return self

    def encode_documents(self, texts) -> np.ndarray:
        if self._doc is None or len(self._doc) != len(list(texts)):
            raise RuntimeError("LSAEncoder.fit must be called with the same document list first")
        return self._doc

    def encode_queries(self, texts) -> np.ndarray:
        z = self.svd.transform(self.vectorizer.transform(list(texts)))
        return normalize(z).astype(np.float32)

    def describe(self) -> dict:
        return {
            "system": "lsa",
            "kind": "non-neural latent semantic analysis (TF-IDF + truncated SVD)",
            "n_components_requested": self.n_components,
            "n_components_used": self.n_components_,
            "seed": self.seed,
            "svd_n_iter": self.n_iter,
            "analyzer": self.analyzer.describe(),
        }


class SentenceTransformerEncoder:
    """Wrapper for a sentence-transformers bi-encoder.

    ``model`` may be a preloaded object exposing ``encode`` (used by tests with a stub). Query/document
    prefixes are model specific (for example E5 expects ``"query: "`` / ``"passage: "``) and are never guessed.
    """

    name = "dense"

    def __init__(self, model_name_or_path: str | None = None, query_prefix: str = "", doc_prefix: str = "",
                 batch_size: int = 32, device: str | None = None, max_seq_length: int | None = None, model=None):
        if model is None:
            from sentence_transformers import SentenceTransformer  # optional dependency

            model = SentenceTransformer(model_name_or_path, device=device)
        if max_seq_length:
            model.max_seq_length = max_seq_length
        self.model = model
        self.model_name_or_path = model_name_or_path
        self.query_prefix = query_prefix
        self.doc_prefix = doc_prefix
        self.batch_size = int(batch_size)

    def _encode(self, texts, prefix: str) -> np.ndarray:
        arr = self.model.encode(
            [prefix + t for t in texts],
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(arr, dtype=np.float32)

    def encode_documents(self, texts) -> np.ndarray:
        return self._encode(list(texts), self.doc_prefix)

    def encode_queries(self, texts) -> np.ndarray:
        return self._encode(list(texts), self.query_prefix)

    def describe(self) -> dict:
        return {
            "system": "dense",
            "kind": "sentence-transformers bi-encoder",
            "model": self.model_name_or_path,
            "query_prefix": self.query_prefix,
            "doc_prefix": self.doc_prefix,
            "batch_size": self.batch_size,
            "max_seq_length": getattr(self.model, "max_seq_length", None),
        }


class DenseIndex:
    def __init__(self, encoder, name: str = "dense"):
        self.encoder = encoder
        self.name = name
        self.doc_ids: list[str] = []
        self.D: np.ndarray | None = None

    def fit(self, doc_ids, texts) -> DenseIndex:
        self.doc_ids = list(doc_ids)
        texts = list(texts)
        if hasattr(self.encoder, "fit"):
            self.encoder.fit(texts)
        self.D = np.asarray(self.encoder.encode_documents(texts), dtype=np.float32)
        if self.D.shape[0] != len(self.doc_ids):
            raise ValueError("encoder returned a different number of document vectors than documents")
        return self

    def search(self, queries: dict[str, str], k: int = 100, batch: int = 64) -> dict[str, list[tuple[str, float]]]:
        qids = list(queries)
        out: dict[str, list[tuple[str, float]]] = {}
        for start in range(0, len(qids), batch):
            chunk = qids[start:start + batch]
            q = np.asarray(self.encoder.encode_queries([queries[x] for x in chunk]), dtype=np.float32)
            scores = q @ self.D.T
            norms = np.linalg.norm(q, axis=1)
            for row, qid in enumerate(chunk):
                if norms[row] == 0:  # query has no representable content: no ranking rather than an arbitrary one
                    out[qid] = []
                    continue
                idx = top_k_indices(scores[row], k)
                out[qid] = [(self.doc_ids[i], float(scores[row, i])) for i in idx]
        return out

    def describe(self) -> dict:
        info = self.encoder.describe() if hasattr(self.encoder, "describe") else {"system": self.name}
        info["n_docs"] = len(self.doc_ids)
        return info
