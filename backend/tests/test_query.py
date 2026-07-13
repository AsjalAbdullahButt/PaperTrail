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


# ------------------- V3 Phase 6: document comparison mode ---------------- #
def _upload_two_docs(client) -> tuple[str, str]:
    a = upload_text_doc(
        client, "alpha.txt", "Alpha corp reported revenue of 10 million dollars this year."
    )
    b = upload_text_doc(
        client, "beta.txt", "Beta corp reported revenue of 20 million dollars this year."
    )
    return a["id"], b["id"]


def test_compare_mode_with_one_document_returns_400(client):
    doc_id, _ = _upload_two_docs(client)
    res = client.post(
        "/api/query",
        json={"question": "Compare them", "mode": "compare", "document_ids": [doc_id]},
    )
    assert res.status_code == 400


def test_compare_mode_stream_with_one_document_returns_400(client):
    doc_id, _ = _upload_two_docs(client)
    res = client.post(
        "/api/query/stream",
        json={"question": "Compare them", "mode": "compare", "document_ids": [doc_id]},
    )
    assert res.status_code == 400


def test_compare_mode_calls_hybrid_retrieve_once_per_document(client, monkeypatch):
    doc_a, doc_b = _upload_two_docs(client)
    calls = []
    real_hybrid_retrieve = query_router.hybrid_retrieve

    def counting_hybrid_retrieve(db, user_id, question, **kwargs):
        calls.append(kwargs.get("document_ids"))
        return real_hybrid_retrieve(db, user_id, question, **kwargs)

    monkeypatch.setattr(query_router, "hybrid_retrieve", counting_hybrid_retrieve)

    res = client.post(
        "/api/query",
        json={
            "question": "Compare revenue",
            "mode": "compare",
            "document_ids": [doc_a, doc_b],
        },
    )
    assert res.status_code == 200
    assert len(calls) == 2
    assert {doc_a} in [set(c) for c in calls]
    assert {doc_b} in [set(c) for c in calls]


def test_compare_mode_groups_chunks_by_document_name(client, monkeypatch):
    doc_a, doc_b = _upload_two_docs(client)
    captured = {}

    def fake_generate_compare(question, chunks_by_doc):
        captured["chunks_by_doc"] = chunks_by_doc
        return "comparison answer"

    monkeypatch.setattr(query_router.llm, "generate_compare_answer", fake_generate_compare)

    res = client.post(
        "/api/query",
        json={
            "question": "Compare revenue",
            "mode": "compare",
            "document_ids": [doc_a, doc_b],
        },
    )
    assert res.status_code == 200
    assert set(captured["chunks_by_doc"]) == {"alpha.txt", "beta.txt"}
    assert any("10 million" in t for t in captured["chunks_by_doc"]["alpha.txt"])
    assert any("20 million" in t for t in captured["chunks_by_doc"]["beta.txt"])


def test_compare_mode_response_includes_sources_from_both_documents(client):
    doc_a, doc_b = _upload_two_docs(client)
    res = client.post(
        "/api/query",
        json={
            "question": "Compare the revenue figures",
            "mode": "compare",
            "document_ids": [doc_a, doc_b],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "compare"
    titles = {s["title"] for s in body["sources"]}
    assert titles == {"alpha.txt", "beta.txt"}


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


# ------------------- V3 Phase 8: calibrated confidence -------------------- #
def _chunk(similarity_score: float, ranked_score: float) -> dict:
    return {"similarity_score": similarity_score, "ranked_score": ranked_score}


def test_confidence_low_similarity_caps_score_below_035():
    retrieved = [_chunk(0.2, 0.2)]
    confidence = query_router._confidence(retrieved, "An answer.", [])
    assert confidence < 0.35
    assert confidence == 0.2  # min(0.35, top_sim) when top_sim < 0.4


def test_confidence_high_similarity_with_no_unsupported_sentences():
    retrieved = [_chunk(0.9, 0.9), _chunk(0.85, 0.85), _chunk(0.8, 0.8)]
    confidence = query_router._confidence(retrieved, "Sentence one. Sentence two.", [])
    assert confidence > 0.7


def test_confidence_penalized_by_unsupported_sentences():
    retrieved = [_chunk(0.9, 0.9), _chunk(0.85, 0.85), _chunk(0.8, 0.8)]
    answer = "Sentence one. Sentence two."
    no_penalty = query_router._confidence(retrieved, answer, [])
    # Half the sentences flagged unsupported.
    with_penalty = query_router._confidence(retrieved, answer, [{"sentence": "Sentence two."}])
    assert with_penalty < no_penalty


def test_confidence_never_exceeds_1_or_goes_below_0():
    # Pathological inputs: scores > 1, many chunks, all sentences unsupported.
    retrieved = [_chunk(1.5, 1.5) for _ in range(50)]
    high = query_router._confidence(retrieved, "One sentence only.", [])
    assert 0.0 <= high <= 1.0

    all_unsupported = [{"sentence": "x"}] * 20
    low = query_router._confidence(retrieved, "One sentence only.", all_unsupported)
    assert 0.0 <= low <= 1.0

    empty = query_router._confidence([], "anything", [])
    assert empty == 0.0


def test_query_rag_response_confidence_within_bounds(client):
    upload_text_doc(
        client,
        "facts2.txt",
        "The capital of the fictional country Zubrowka is Lutz. "
        "Lutz is home to the grand budapest hotel.",
    )
    res = client.post(
        "/api/query", json={"question": "What is the capital of Zubrowka?", "mode": "rag"}
    )
    assert res.status_code == 200
    confidence = res.json()["confidence_score"]
    assert 0.0 <= confidence <= 1.0
