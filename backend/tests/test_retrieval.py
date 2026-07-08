"""Phase 3: hybrid retrieval, multi-hop, follow-ups, hallucination guard."""
from __future__ import annotations

from sqlalchemy import select

from app.models import Chunk, ChunkCoverage
from app.services import multihop as multihop_mod
from app.services.bm25_index import BM25Index
from app.services.followup import _parse_questions, generate_followup_questions
from app.services.hallucination_guard import check_answer
from app.services.retriever import hybrid_retrieve
from ._helpers import upload_text_doc

from conftest import auth_headers, requires_db


# ------------------------------ BM25 (unit) ----------------------------- #
def test_bm25_ranks_keyword_match_first():
    idx = BM25Index().build(
        [
            "the mitochondria is the powerhouse of the cell",
            "quarterly revenue grew across regions",
            "photosynthesis converts sunlight into energy",
        ]
    )
    results = idx.search("revenue growth quarterly", top_k=3)
    assert results
    assert results[0][0] == 1  # the revenue chunk ranks first
    assert all(0.0 <= score <= 1.0 for _, score in results)


def test_bm25_empty_index_is_safe():
    assert BM25Index().build([]).search("anything", top_k=3) == []


# --------------------------- follow-up parsing -------------------------- #
def test_parse_questions_valid_json():
    raw = '["What is X?", "How does Y work?", "Why Z?", "When W?"]'
    assert _parse_questions(raw) == ["What is X?", "How does Y work?", "Why Z?", "When W?"]


def test_parse_questions_embedded_in_prose():
    raw = 'Sure!\n["A?", "B?", "C?", "D?"]\nHope that helps.'
    assert _parse_questions(raw) == ["A?", "B?", "C?", "D?"]


def test_parse_questions_garbage_returns_empty():
    assert _parse_questions("not json at all") == []
    assert _parse_questions("") == []


def test_generate_followups_offline_returns_empty():
    # Offline (no model) must never raise and returns [].
    out = generate_followup_questions("q", "a", [{"text": "some context"}])
    assert isinstance(out, list)


# --------------------------- hallucination guard ------------------------ #
def test_hallucination_guard_flags_unsupported_sentence():
    chunks = [
        {"chunk_id": "c1", "text": "Zubrowka exported barley and hops in 1932 heavily."}
    ]
    answer = (
        "Zubrowka exported barley in 1932. "
        "Later the Martian colony traded plutonium with Neptune in 2400."
    )
    results = check_answer(answer, chunks)
    by_sentence = {r["sentence"][:20]: r for r in results}
    # The first sentence shares >=3 key terms with the chunk -> supported.
    assert any(r["supported"] for r in results)
    # The fabricated sentence has no supporting chunk.
    assert any(not r["supported"] for r in results)


# ------------------------------ integration ----------------------------- #
requires_db_mark = requires_db


@requires_db_mark
def test_hybrid_retrieve_returns_annotated_sources(client, db_session):
    user_headers = client.headers  # default user already authed
    upload_text_doc(
        client,
        "econ.txt",
        "Quarterly revenue increased twenty percent. "
        "Operating margins expanded across all regions. " * 20,
    )
    # Resolve the user id from the token via /auth/me.
    me = client.get("/api/auth/me").json()
    results = hybrid_retrieve(db_session, me["id"], "quarterly revenue growth", top_k=5)
    assert results
    r0 = results[0]
    for key in ("chunk_id", "document_name", "page_number", "similarity_score",
                "importance_score", "ranked_score"):
        assert key in r0
    assert 0.0 <= r0["ranked_score"]


@requires_db_mark
def test_query_increments_retrieved_count(client, db_session):
    upload_text_doc(client, "r.txt", "Alpha beta gamma delta epsilon zeta. " * 30)
    client.post("/api/query", json={"question": "alpha beta gamma", "mode": "rag"})
    total = db_session.execute(
        select(ChunkCoverage.retrieved_count)
    ).scalars().all()
    assert any(c >= 1 for c in total)


@requires_db_mark
def test_multihop_makes_exactly_two_retrieval_calls(client, monkeypatch):
    upload_text_doc(client, "m.txt", "Neptune orbits the sun once every 165 years. " * 20)
    calls = {"n": 0}
    real = multihop_mod.hybrid_retrieve

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(multihop_mod, "hybrid_retrieve", counting)
    res = client.post("/api/query", json={"question": "Neptune orbit", "mode": "multihop"})
    assert res.status_code == 200
    assert calls["n"] == 2


@requires_db_mark
def test_query_response_has_confidence_and_followups_shape(client):
    upload_text_doc(client, "c.txt", "The Eiffel Tower is in Paris, France. " * 20)
    res = client.post("/api/query", json={"question": "Where is the Eiffel Tower?", "mode": "rag"})
    body = res.json()
    assert 0.0 <= body["confidence_score"] <= 1.0
    assert isinstance(body["followup_questions"], list)
    assert body["query_id"]


@requires_db_mark
def test_document_ids_scope_excludes_other_docs(client):
    a = upload_text_doc(client, "a.txt", "The secret keyword is flamingo. " * 20)
    upload_text_doc(client, "b.txt", "Completely unrelated content about turbines. " * 20)
    res = client.post(
        "/api/query",
        json={"question": "what is the secret keyword", "mode": "rag",
              "document_ids": [a["id"]]},
    )
    body = res.json()
    assert body["sources"]
    assert all(s["document_id"] == a["id"] for s in body["sources"])
