"""embedding_provider switch in llm.embed_texts (default behaviour unchanged)."""
from __future__ import annotations

import math

from app import llm
from app.config import settings


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def test_default_provider_is_openai():
    assert type(settings).model_fields["embedding_provider"].default == "openai"
    assert type(settings).model_fields["hf_embedding_model"].default == "sentence-transformers/all-MiniLM-L6-v2"


def test_offline_provider_uses_hashing_embedder(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "offline")
    # Even with an OpenAI key present, "offline" must never call OpenAI.
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-key-that-must-not-be-used")
    monkeypatch.setattr(llm, "_openai_embed", lambda texts: (_ for _ in ()).throw(AssertionError("called OpenAI")))
    vecs = llm.embed_texts(["dense retrieval"])
    assert len(vecs[0]) == llm._OFFLINE_DIM
    assert abs(_norm(vecs[0]) - 1.0) < 1e-6


def test_hf_provider_routes_to_hf_embed(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "hf")
    monkeypatch.setattr(llm, "_hf_embed", lambda texts: [[1.0, 0.0] for _ in texts])
    assert llm.embed_texts(["a", "b"]) == [[1.0, 0.0], [1.0, 0.0]]


def test_hf_failure_falls_back_to_offline(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "hf")

    def boom(texts):
        raise ImportError("sentence-transformers not installed")

    monkeypatch.setattr(llm, "_hf_embed", boom)
    vecs = llm.embed_texts(["x"])
    assert len(vecs[0]) == llm._OFFLINE_DIM


def test_openai_provider_without_key_is_offline(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    vecs = llm.embed_texts(["x"])
    assert len(vecs[0]) == llm._OFFLINE_DIM
