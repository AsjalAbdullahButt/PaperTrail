"""Post-generation grounding check.

Splits an answer into sentences and flags any whose key terms (capitalized
words and numbers) are not supported by at least one retrieved chunk. Purely
lexical and conservative — it catches obviously unsupported claims without an
extra model call.
"""
from __future__ import annotations

import re

_SENT_RE = re.compile(r"(?<=[.!?])\s+")
_CAP_RE = re.compile(r"\b[A-Z][A-Za-z]{2,}\b")
_NUM_RE = re.compile(r"\b\d[\d,.%]*\b")
_WORD_RE = re.compile(r"\b[A-Za-z]{5,}\b")

# Sentence-initial capitals and citation markers aren't evidence of a claim.
_STOP_CAPS = {"The", "This", "That", "These", "Those", "It", "There", "A", "An",
              "In", "On", "For", "And", "But", "As", "If", "When", "While",
              "However", "Based"}
_STOP_WORDS = {"which", "there", "their", "these", "those", "about", "would",
               "could", "should", "where", "while", "after", "before", "being",
               "other", "using", "under", "above", "below"}


def _key_terms(text: str) -> set[str]:
    """Content terms of a sentence: proper nouns, numbers, and longer words —
    a lexical proxy for the noun/number 'claim carriers' the guard checks."""
    caps = {w for w in _CAP_RE.findall(text) if w not in _STOP_CAPS}
    nums = set(_NUM_RE.findall(text))
    words = {w for w in _WORD_RE.findall(text.lower()) if w not in _STOP_WORDS}
    return {t.lower() for t in caps} | nums | words


def check_answer(answer: str, chunks: list[dict]) -> list[dict]:
    """Return ``[{"sentence","supported","source_chunk_id"}]`` per sentence."""
    sentences = [s.strip() for s in _SENT_RE.split(answer.strip()) if s.strip()]
    chunk_terms = [
        (c.get("chunk_id"), _key_terms(c.get("text", ""))) for c in chunks
    ]

    results: list[dict] = []
    for sentence in sentences:
        terms = _key_terms(sentence)
        supported = False
        source_id = None
        if terms:
            for cid, cterms in chunk_terms:
                if len(terms & cterms) >= 3:
                    supported = True
                    source_id = cid
                    break
        else:
            # No checkable key terms (e.g. a generic transition) -> not flagged.
            supported = True
        results.append(
            {"sentence": sentence, "supported": supported, "source_chunk_id": source_id}
        )
    return results
