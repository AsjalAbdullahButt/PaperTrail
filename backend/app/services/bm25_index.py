"""Sparse lexical retrieval via BM25 (rank_bm25.BM25Okapi).

Complements dense (embedding) retrieval: BM25 rewards exact keyword overlap,
which embeddings can miss. Scores are min-max normalized to [0, 1] so they can
be fused with cosine similarity on the same scale.
"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    """A BM25 index over a fixed list of chunk texts (positional)."""

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._n = 0

    def build(self, chunks: list[str]) -> "BM25Index":
        tokenized = [_tokenize(c) for c in chunks]
        self._n = len(tokenized)
        # BM25Okapi requires at least one document; guard empty corpora.
        self._bm25 = BM25Okapi(tokenized) if tokenized else None
        return self

    def search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        """Return up to ``top_k`` ``(chunk_index, normalized_score)`` pairs.

        Scores are min-max normalized to [0, 1]; when every raw score is equal
        (or zero) all results get 0.0 (no lexical signal).
        """
        if self._bm25 is None or self._n == 0 or top_k <= 0:
            return []
        raw = self._bm25.get_scores(_tokenize(query))
        lo, hi = float(min(raw)), float(max(raw))
        span = hi - lo
        if span < 1e-12:
            normed = [0.0] * len(raw)
        else:
            normed = [(float(s) - lo) / span for s in raw]
        ranked = sorted(enumerate(normed), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
