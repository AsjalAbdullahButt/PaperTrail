"""Retrieval-confidence signal and the abstain-on-low-confidence decision.

A RAG system should say "this is not in the documents" rather than answer from
weak evidence. The cheapest reliable signal is how well the *best* retrieved
passage matches the question. When a cross-encoder re-ranked the candidates, its
sigmoid score for the top passage is used (a calibrated-ish relevance
probability); otherwise the top dense cosine similarity. ``eval/analysis.py``
measures how well each signal separates answerable from unanswerable questions
(AUROC) and proposes a threshold.
"""
from __future__ import annotations

from ..config import settings
from .reranker import sigmoid


def retrieval_signal(retrieved: list[dict]) -> float:
    """Confidence in [0, 1] that the retrieved context can answer the question."""
    if not retrieved:
        return 0.0
    top = retrieved[0]
    if "rerank_score" in top:
        return round(sigmoid(top["rerank_score"]), 4)
    return round(max(0.0, float(top.get("similarity_score", 0.0))), 4)


def signal_kind(retrieved: list[dict]) -> str:
    return "rerank" if retrieved and "rerank_score" in retrieved[0] else "dense"


def should_abstain(retrieved: list[dict], enabled: bool | None = None) -> bool:
    """True when abstention is on and the signal is below its threshold.

    ``enabled`` overrides ``settings.abstain_enabled`` (per-request option). A
    threshold of 0.0 disables the check.
    """
    if not (settings.abstain_enabled if enabled is None else enabled):
        return False
    thr = settings.abstain_threshold_rerank if signal_kind(retrieved) == "rerank" else settings.abstain_threshold
    return thr > 0.0 and retrieval_signal(retrieved) < thr
