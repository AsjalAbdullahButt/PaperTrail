"""Router coverage for POST /api/query (RAG + direct) and edge cases."""
from __future__ import annotations

import json

from sqlalchemy import select

import app.routers.documents as documents_router
import app.routers.query as query_router
from app.models import Chunk
from ._helpers import upload_text_doc

from conftest import requires_db

pytestmark = requires_db


def test_query_empty_corpus_returns_helpful_message(client):
    res = client.post("/api/query", json={"question": "anything?", "mode": "rag"})
    assert res.status_code == 200
    body = res.json()
    assert body["sources"] == []
    assert "no documents" in body["answer"].lower()


def test_query_rag_returns_sources_from_uploaded_doc(client):
    upload_text_doc(
        client,
        "facts.txt",
        "The capital of the fictional country Zubrowka is Lutz. "
        "Lutz is home to the grand budapest hotel.",
    )
    res = client.post(
        "/api/query", json={"question": "What is the capital of Zubrowka?", "mode": "rag"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "rag"
    assert len(body["sources"]) >= 1
    assert body["sources"][0]["title"] == "facts.txt"
    assert 0.0 <= body["sources"][0]["score"] <= 100.0


def test_query_direct_mode_has_no_sources(client):
    res = client.post("/api/query", json={"question": "Say hi.", "mode": "direct"})
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "direct"
    assert body["sources"] == []


# --------------- V3 Phase 3: conversation history / follow-ups ----------- #
def test_query_rag_threads_conversation_history_to_the_llm_call(client, monkeypatch):
    upload_text_doc(
        client,
        "report.txt",
        "The quarterly report highlights strong revenue growth this year overall.",
    )
    captured = {}

    def fake_generate(question, context_chunks, history=None):
        captured["history"] = history
        return "Here's more detail.", ""

    monkeypatch.setattr(query_router.llm, "generate_rag_answer_with_followups", fake_generate)

    history = [
        {"role": "user", "content": "What is this document about?"},
        {"role": "assistant", "content": "It's a quarterly report."},
    ]
    res = client.post(
        "/api/query",
        json={
            "question": "Tell me more about the first point",
            "mode": "rag",
            "conversation_history": history,
        },
    )
    assert res.status_code == 200
    assert captured["history"] == history


def test_query_direct_mode_threads_conversation_history(client, monkeypatch):
    captured = {}

    def fake_generate(question, context_chunks, mode, history=None):
        captured["history"] = history
        return "direct follow-up"

    monkeypatch.setattr(query_router.llm, "generate_answer", fake_generate)

    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    res = client.post(
        "/api/query",
        json={"question": "how are you?", "mode": "direct", "conversation_history": history},
    )
    assert res.status_code == 200
    assert res.json()["answer"] == "direct follow-up"
    assert captured["history"] == history


def test_query_conversation_history_over_8_turns_truncated_before_reaching_llm(client, monkeypatch):
    captured = {}

    def fake_generate(question, context_chunks, mode, history=None):
        captured["history"] = history
        return "ok"

    monkeypatch.setattr(query_router.llm, "generate_answer", fake_generate)

    turns = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
        for i in range(8)
    ]
    res = client.post(
        "/api/query",
        json={"question": "q", "mode": "direct", "conversation_history": turns},
    )
    assert res.status_code == 200
    assert len(captured["history"]) == 6
    assert captured["history"][0]["content"] == "turn 2"  # oldest 2 dropped
    assert captured["history"][-1]["content"] == "turn 7"


def test_query_malformed_mode_rejected(client):
    res = client.post("/api/query", json={"question": "hi", "mode": "banana"})
    assert res.status_code == 422


def test_query_missing_question_rejected(client):
    res = client.post("/api/query", json={"mode": "rag"})
    assert res.status_code == 422


def test_query_survives_mismatched_embedding_dimensions(client, db_session):
    """Regression: a chunk stored with a different embedding dimensionality
    (e.g. a corpus embedded offline at 512 dims, later queried after an OpenAI
    key is added at 1536 dims) must be skipped, not 500 the whole query.
    """
    doc = upload_text_doc(
        client,
        "mixed.txt",
        "The capital of the fictional country Zubrowka is Lutz. " * 60,
    )
    chunks = (
        db_session.execute(
            select(Chunk)
            .where(Chunk.document_id == doc["id"])
            .order_by(Chunk.chunk_index)
        )
        .scalars()
        .all()
    )
    assert len(chunks) >= 1
    # Corrupt the first chunk's embedding to a wrong (3-dim) vector.
    bad_index = chunks[0].chunk_index
    chunks[0].embedding = json.dumps([0.1, 0.2, 0.3])
    db_session.commit()

    res = client.post(
        "/api/query",
        json={"question": "What is the capital of Zubrowka?", "mode": "rag"},
    )
    # The query completes instead of raising a 500 inside NumPy.
    assert res.status_code == 200, res.text
    # The dimensionally-broken chunk never appears as a citation.
    assert not any(
        s["document_id"] == doc["id"] and s["chunk_index"] == bad_index
        for s in res.json()["sources"]
    )


def test_upload_embedding_count_mismatch_returns_500(client, monkeypatch):
    # Force embed_texts to always return one fewer vector than there are
    # chunks, regardless of chunking strategy/count, so the mismatch is
    # guaranteed to trigger.
    monkeypatch.setattr(
        documents_router.llm,
        "embed_texts",
        lambda chunks: [[0.0, 1.0]] * max(0, len(chunks) - 1),
    )
    res = client.post(
        "/api/documents/upload",
        files={"file": ("many.txt", ("word " * 500).encode(), "text/plain")},
    )
    assert res.status_code == 500
    assert "embedding count mismatch" in res.json()["error"]["message"].lower()
