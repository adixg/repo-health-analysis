"""Dependency-free TF-IDF cosine-similarity index.

This provides deterministic, reproducible text retrieval over the ingested
repository corpus (issues, comments, documentation) without requiring an
external vector database or embedding service. A pluggable embedding backend
(pgvector / ChromaDB) can be swapped in later behind the same ``search``
interface; the default backend keeps Checkpoint 3 runnable and testable with no
extra infrastructure.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class TfidfIndex:
    """A small in-memory TF-IDF index with cosine-similarity querying."""

    def __init__(self) -> None:
        self._doc_vectors: list[dict[str, float]] = []
        self._doc_norms: list[float] = []
        self._idf: dict[str, float] = {}
        self._fitted = False

    def fit(self, documents: list[str]) -> "TfidfIndex":
        n_docs = len(documents)
        tokenized = [tokenize(doc) for doc in documents]

        document_frequency: Counter[str] = Counter()
        for tokens in tokenized:
            for term in set(tokens):
                document_frequency[term] += 1

        # Smoothed inverse document frequency.
        self._idf = {
            term: math.log((1 + n_docs) / (1 + df)) + 1.0
            for term, df in document_frequency.items()
        }

        self._doc_vectors = []
        self._doc_norms = []
        for tokens in tokenized:
            vector = self._vectorize(tokens)
            self._doc_vectors.append(vector)
            self._doc_norms.append(math.sqrt(sum(w * w for w in vector.values())))

        self._fitted = True
        return self

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        counts = Counter(tokens)
        total = len(tokens)
        return {
            term: (count / total) * self._idf.get(term, 0.0)
            for term, count in counts.items()
            if self._idf.get(term, 0.0) > 0.0
        }

    def query(self, text: str, top_k: int = 5) -> list[tuple[int, float]]:
        """Return ``(document_index, similarity)`` pairs sorted by relevance."""
        if not self._fitted:
            raise RuntimeError("TfidfIndex.query called before fit()")

        query_vector = self._vectorize(tokenize(text))
        query_norm = math.sqrt(sum(w * w for w in query_vector.values()))
        if query_norm == 0.0:
            return []

        scored: list[tuple[int, float]] = []
        for index, (vector, norm) in enumerate(zip(self._doc_vectors, self._doc_norms)):
            if norm == 0.0:
                continue
            dot = sum(weight * vector.get(term, 0.0) for term, weight in query_vector.items())
            if dot <= 0.0:
                continue
            scored.append((index, dot / (query_norm * norm)))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]
