"""Query-cache tests (Phase 4). Uses the in-process cache backend (no Redis)."""
from __future__ import annotations

import app.routers.query as query_router
from app.cache import make_query_key
from ._helpers import upload_text_doc

from conftest import requires_db

pytestmark = requires_db


def test_identical_query_served_from_cache_without_recalling_llm(client, monkeypatch):
    calls = {"generate": 0}
    real_generate = query_router.llm.generate_answer

    def counting_generate(question, context, mode):
        calls["generate"] += 1
        return real_generate(question, context, mode)

    monkeypatch.setattr(query_router.llm, "generate_answer", counting_generate)

    payload = {"question": "What is cached?", "mode": "direct"}
    first = client.post("/api/query", json=payload)
    second = client.post("/api/query", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.json()["answer"] == second.json()["answer"]
    # LLM invoked only once; the second response came from cache.
    assert calls["generate"] == 1


def test_cache_invalidated_when_documents_change(client, monkeypatch):
    calls = {"generate": 0}
    real_generate = query_router.llm.generate_answer

    def counting_generate(question, context, mode):
        calls["generate"] += 1
        return real_generate(question, context, mode)

    monkeypatch.setattr(query_router.llm, "generate_answer", counting_generate)

    # Direct mode always invokes the LLM on a miss (no empty-corpus shortcut).
    payload = {"question": "anything about cats", "mode": "direct"}
    client.post("/api/query", json=payload)  # miss -> generate #1
    client.post("/api/query", json=payload)  # hit -> no generate
    assert calls["generate"] == 1

    # Uploading changes the user's document set and must invalidate all of
    # their cached query answers (prefix covers every mode).
    upload_text_doc(client, "cats.txt", "Cats are small domesticated felines.")
    client.post("/api/query", json=payload)  # miss again -> generate #2
    assert calls["generate"] == 2


def test_cache_disabled_when_ttl_zero(client, monkeypatch):
    monkeypatch.setattr(query_router.settings, "query_cache_ttl_seconds", 0)
    calls = {"generate": 0}
    real_generate = query_router.llm.generate_answer

    def counting_generate(question, context, mode):
        calls["generate"] += 1
        return real_generate(question, context, mode)

    monkeypatch.setattr(query_router.llm, "generate_answer", counting_generate)
    payload = {"question": "no cache please", "mode": "direct"}
    client.post("/api/query", json=payload)
    client.post("/api/query", json=payload)
    assert calls["generate"] == 2  # every request recomputes


def test_make_query_key_normalizes_whitespace_and_case():
    a = make_query_key(1, "  Hello   World  ", "rag")
    b = make_query_key(1, "hello world", "rag")
    assert a == b
    # Different user or mode -> different key.
    assert make_query_key(2, "hello world", "rag") != a
    assert make_query_key(1, "hello world", "direct") != a
