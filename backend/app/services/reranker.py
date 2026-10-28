"""Cross-encoder re-ranking of retrieval candidates.

First-stage retrieval (dense + BM25) scores query and passage *independently*;
a cross-encoder reads them *together* and so judges relevance much more
precisely, at the cost of one forward pass per candidate. The standard recipe,
used here, is to retrieve a generous candidate set cheaply and re-rank only that.

``sentence-transformers`` is a dev/eval dependency imported lazily; if it (or the
model download) is unavailable, ``rerank`` raises and callers fall back to the
first-stage order.
"""
from __future__ import annotations

import logging
import math
import threading

from ..config import settings

logger = logging.getLogger("papertrail.reranker")

_MODELS: dict[str, object] = {}
_LOCK = threading.Lock()


def available() -> bool:
    """True when the library needed to run the re-ranker can be imported."""
    try:
        import sentence_transformers  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


def _model():
    name = settings.rerank_model
    with _LOCK:
        model = _MODELS.get(name)
        if model is None:
            from sentence_transformers import CrossEncoder

            model = _MODELS[name] = CrossEncoder(name, max_length=512)
    return model


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


def rerank(query: str, items: list[dict], top_k: int) -> list[dict]:
    """Return copies of ``items`` re-ordered by cross-encoder score, best first,
    each with ``rerank_score`` (raw logit) added. ``items`` need a ``text`` key."""
    if not items:
        return []
    scores = _model().predict([(query, it["text"]) for it in items], show_progress_bar=False)
    out = [{**it, "rerank_score": float(sc)} for it, sc in zip(items, scores)]
    out.sort(key=lambda d: d["rerank_score"], reverse=True)
    return out[: max(0, top_k)]
