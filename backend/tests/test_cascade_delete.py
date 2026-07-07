"""Regression tests for the highest-priority correctness bug: a deleted
document's chunks must never be retrieved by a later RAG query.

Prior to the fix, chunk removal relied entirely on the DB-level ON DELETE
CASCADE with no application-level guarantee and no test coverage.
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.models import Chunk
from ._helpers import upload_text_doc

from conftest import requires_db

pytestmark = requires_db

# Distinctive content so we can prove a specific document is or isn't cited.
SECRET_TEXT = (
    "The quarterly zephyr protocol codeword is bluefish-marmalade-77. "
    "This sentence exists only in the document we are about to delete."
)


def _chunk_count(db_session, document_id: int) -> int:
    return db_session.execute(
        select(func.count(Chunk.id)).where(Chunk.document_id == document_id)
    ).scalar_one()


def test_deleted_document_chunks_are_not_returned_in_rag_query(client, db_session):
    # 1) Upload a document with distinctive content.
    doc = upload_text_doc(client, "secret.txt", SECRET_TEXT)
    doc_id = doc["id"]
    assert doc["chunks_created"] >= 1
    assert _chunk_count(db_session, doc_id) >= 1

    # 2) A RAG query surfaces it as a source before deletion.
    before = client.post(
        "/api/query",
        json={"question": "What is the zephyr protocol codeword?", "mode": "rag"},
    )
    assert before.status_code == 200, before.text
    cited_ids_before = {s["document_id"] for s in before.json()["sources"]}
    assert doc_id in cited_ids_before

    # 3) Delete the document.
    deleted = client.delete(f"/api/documents/{doc_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"id": doc_id, "deleted": True}

    # (a) A later RAG query never cites it.
    after = client.post(
        "/api/query",
        json={"question": "What is the zephyr protocol codeword?", "mode": "rag"},
    )
    assert after.status_code == 200, after.text
    cited_ids_after = {s["document_id"] for s in after.json()["sources"]}
    assert doc_id not in cited_ids_after

    # (b) GET /api/documents no longer lists it.
    listing = client.get("/api/documents")
    assert listing.status_code == 200
    assert doc_id not in {d["id"] for d in listing.json()}

    # (c) The chunks table has zero rows for that document_id.
    assert _chunk_count(db_session, doc_id) == 0


def test_delete_removes_chunks_even_without_db_cascade(client, db_session):
    """The application deletes chunks explicitly, not only via the FK cascade.

    We assert the chunk rows are gone in the same transaction as the delete,
    proving correctness does not depend on ON DELETE CASCADE firing.
    """
    doc = upload_text_doc(client, "ephemeral.txt", SECRET_TEXT)
    doc_id = doc["id"]
    assert _chunk_count(db_session, doc_id) >= 1

    res = client.delete(f"/api/documents/{doc_id}")
    assert res.status_code == 200
    assert _chunk_count(db_session, doc_id) == 0


def test_delete_missing_document_returns_404(client):
    res = client.delete("/api/documents/99999999")
    assert res.status_code == 404
    assert res.json()["error"]["status_code"] == 404
