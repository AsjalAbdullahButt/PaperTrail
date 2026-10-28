"""Resolve which optional NLP stages run for a request.

Server settings give the defaults; ``QueryRequest.options`` overrides them per
request. A stage whose library is not installed is switched off and a note is
recorded, so the API degrades gracefully instead of failing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import settings
from ..schemas import QueryOptions
from . import nli_guard, reranker


@dataclass
class PipelineConfig:
    rerank: bool = False
    expansion: str = "none"  # "none" | "hyde"
    grounding: str = "lexical"  # "lexical" | "nli"
    abstain: bool = False
    notes: list[str] = field(default_factory=list)
    # True when the request asked for something other than the server defaults
    # (such responses must not share the default-pipeline query cache).
    customised: bool = False


def resolve(options: QueryOptions | None) -> PipelineConfig:
    opts = options or QueryOptions()
    cfg = PipelineConfig(
        rerank=settings.rerank_enabled if opts.rerank is None else opts.rerank,
        expansion=settings.query_expansion if opts.expansion is None else opts.expansion,
        grounding=settings.grounding_method if opts.grounding is None else opts.grounding,
        abstain=settings.abstain_enabled if opts.abstain is None else opts.abstain,
    )
    cfg.customised = any(v is not None for v in (opts.rerank, opts.expansion, opts.grounding, opts.abstain))

    if cfg.rerank and not reranker.available():
        cfg.rerank = False
        cfg.notes.append("Re-ranking skipped: sentence-transformers is not installed on the server.")
    if cfg.grounding == "nli" and not nli_guard.available():
        cfg.grounding = "lexical"
        cfg.notes.append("NLI grounding skipped: transformers/torch are not installed; used the lexical check.")
    return cfg


def capabilities() -> dict:
    """What the UI may offer: availability of each stage and the server default."""
    rr, nli = reranker.available(), nli_guard.available()
    return {
        "rerank": {"available": rr, "default": settings.rerank_enabled and rr, "model": settings.rerank_model},
        "expansion": {"available": True, "default": settings.query_expansion, "options": ["none", "hyde"]},
        "grounding": {"available": nli, "default": settings.grounding_method if nli else "lexical",
                      "options": ["lexical", "nli"] if nli else ["lexical"], "model": settings.nli_model},
        "abstain": {
            "available": True,
            "default": settings.abstain_enabled,
            "calibrated": settings.abstain_threshold > 0 or settings.abstain_threshold_rerank > 0,
        },
        "contextual_chunk_headers": settings.contextual_chunk_headers,
    }
