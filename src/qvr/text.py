"""Tokenisation shared by all lexical components (BM25 and the TF-IDF stage of the LSA baseline)."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# Lucene / Elasticsearch default English stop-word set (33 words).
LUCENE_ENGLISH_STOPWORDS = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", "that", "the", "their", "then", "there", "these", "they", "this", "to", "was", "will", "with"]
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


class Analyzer:
    """lowercase -> ``[a-z0-9]+`` tokens -> stop-word removal -> Porter stemming.

    This approximates, but is not identical to, Elasticsearch's ``english`` analyzer (no possessive stemmer,
    plain regex tokeniser). The order of operations (stop-words before stemming) follows Elasticsearch.
    """

    def __init__(self, stopwords: Iterable[str] | None = LUCENE_ENGLISH_STOPWORDS, stem: bool = True):
        self.stopwords = frozenset(stopwords or ())
        self._stemmer = None
        if stem:
            import snowballstemmer

            self._stemmer = snowballstemmer.stemmer("porter")
        self._cache: dict[str, str] = {}

    @staticmethod
    def tokenize(text: str) -> list[str]:
        return _TOKEN_RE.findall(_strip_accents(text).lower())

    def _stem(self, token: str) -> str:
        stemmed = self._cache.get(token)
        if stemmed is None:
            stemmed = self._stemmer.stemWord(token)
            self._cache[token] = stemmed
        return stemmed

    def __call__(self, text: str) -> list[str]:
        tokens = [t for t in self.tokenize(text) if t not in self.stopwords]
        if self._stemmer is not None:
            tokens = [self._stem(t) for t in tokens]
        return tokens

    def describe(self) -> dict:
        return {
            "tokenizer": "lowercase, accent-stripped, regex [a-z0-9]+",
            "n_stopwords": len(self.stopwords),
            "stemmer": "porter (snowballstemmer)" if self._stemmer is not None else None,
        }
