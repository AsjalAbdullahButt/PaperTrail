"""Chunk importance scoring and highlight extraction (pure Python, no sklearn).

``score_chunks`` blends a TF-IDF informativeness signal with a positional prior
(boilerplate at the very start/end of a document is down-weighted) and
normalizes to [0, 1]. ``extract_highlights`` picks the most representative
sentence from the top-scoring chunks.
"""
from __future__ import annotations

import math
import re
from collections import Counter

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")
_SENT_RE = re.compile(r"(?<=[.!?])\s+")

# Very common words carry little topical signal; excluded from TF-IDF.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "at", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "it", "this", "that", "these", "those", "i", "you", "he", "she", "we", "they",
    "not", "no", "do", "does", "did", "has", "have", "had", "will", "would",
    "can", "could", "should", "may", "might", "must", "if", "then", "than",
    "so", "such", "there", "here", "which", "who", "whom", "whose", "what",
    "when", "where", "why", "how", "all", "any", "both", "each", "more", "most",
    "other", "some", "only", "own", "same", "too", "very", "s", "t", "just",
}


def _tokens(text: str) -> list[str]:
    return [
        w for w in (m.group(0).lower() for m in _WORD_RE.finditer(text))
        if w not in _STOPWORDS and len(w) > 1
    ]


def _normalize(values: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]. Constant input -> all 0.5 (no signal)."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def score_chunks(chunks: list[str]) -> list[float]:
    """Importance score in [0, 1] for each chunk, aligned with the input order."""
    n = len(chunks)
    if n == 0:
        return []
    if n == 1:
        return [1.0]

    tokenized = [_tokens(c) for c in chunks]

    # Document frequency per term, then idf.
    df: Counter[str] = Counter()
    for toks in tokenized:
        df.update(set(toks))
    idf = {term: math.log((n + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}

    # Mean TF-IDF weight of a chunk's terms = average informativeness.
    raw_tfidf: list[float] = []
    for toks in tokenized:
        if not toks:
            raw_tfidf.append(0.0)
            continue
        counts = Counter(toks)
        total = len(toks)
        weight = sum((c / total) * idf.get(term, 0.0) for term, c in counts.items())
        raw_tfidf.append(weight)

    tfidf_norm = _normalize(raw_tfidf)

    # Positional prior: first/last 5% of chunks are likely boilerplate (cover
    # pages, footers) and get half weight; the body gets full weight.
    edge = max(1, int(round(n * 0.05)))
    position_score = [
        0.5 if (i < edge or i >= n - edge) else 1.0 for i in range(n)
    ]

    blended = [0.6 * tfidf_norm[i] + 0.4 * position_score[i] for i in range(n)]
    return _normalize(blended)


def _representative_sentence(text: str) -> str:
    """Longest sentence with the highest density of capitalized words."""
    sentences = [s.strip() for s in _SENT_RE.split(text.strip()) if s.strip()]
    if not sentences:
        return text.strip()[:280]

    def sent_score(s: str) -> tuple[float, int]:
        words = s.split()
        if not words:
            return (0.0, 0)
        caps = sum(1 for w in words if w[:1].isupper())
        density = caps / len(words)
        return (density, len(words))  # density first, length as tie-breaker

    best = max(sentences, key=sent_score)
    return best[:280]


def extract_highlights(
    chunks: list[str], scores: list[float], n: int = 8
) -> list[dict]:
    """Top-``n`` chunks by score, each reduced to a representative sentence.

    Returns ``[{"text","score","chunk_index"}]`` ordered by descending score.
    """
    if not chunks:
        return []
    indexed = sorted(
        range(len(chunks)), key=lambda i: scores[i] if i < len(scores) else 0.0,
        reverse=True,
    )
    highlights: list[dict] = []
    for i in indexed[: max(0, n)]:
        highlights.append(
            {
                "text": _representative_sentence(chunks[i]),
                "score": round(float(scores[i]) if i < len(scores) else 0.0, 4),
                "chunk_index": i,
            }
        )
    return highlights
