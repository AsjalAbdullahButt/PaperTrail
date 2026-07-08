"""Phase 8: soft delete/restore, retrieval exclusion, health, export, resilience."""
from __future__ import annotations

import io
import zipfile

from sqlalchemy.exc import OperationalError

import app.ratelimit as ratelimit
from app.database import get_db, purge_soft_deleted
from app.main import app
from ._helpers import upload_bytes, upload_text_doc

from conftest import requires_db

pytestmark = requires_db


# ------------------------------ soft delete ----------------------------- #
def test_soft_delete_hides_document(client):
    doc = upload_text_doc(client, "gone.txt", "content to be deleted " * 10)
    assert client.delete(f"/api/documents/{doc['id']}").status_code == 200
    ids = {d["id"] for d in client.get("/api/documents").json()}
    assert doc["id"] not in ids


def test_deleted_document_not_retrievable(client):
    upload_text_doc(client, "secret.txt", "The password is hummingbird. " * 20)
    doc_id = client.get("/api/documents").json()[0]["id"]
    client.delete(f"/api/documents/{doc_id}")
    res = client.post("/api/query", json={"question": "what is the password", "mode": "rag"})
    assert res.json()["sources"] == []


def test_restore_document(client):
    doc = upload_text_doc(client, "restore.txt", "bring me back " * 10)
    client.delete(f"/api/documents/{doc['id']}")
    assert client.post(f"/api/documents/{doc['id']}/restore").status_code == 200
    ids = {d["id"] for d in client.get("/api/documents").json()}
    assert doc["id"] in ids


def test_trash_lists_deleted_documents(client):
    doc = upload_text_doc(client, "trash.txt", "throw me away " * 10)
    client.delete(f"/api/documents/{doc['id']}")
    trash = client.get("/api/documents/trash").json()
    assert any(d["id"] == doc["id"] for d in trash)


def test_purge_soft_deleted_runs(client):
    # Smoke: the cleanup job executes and returns a count without error.
    assert isinstance(purge_soft_deleted(retention_days=30), int)


# ------------------------------- health --------------------------------- #
def test_detailed_health_shape(anon_client):
    res = anon_client.get("/api/health/detailed")
    body = res.json()
    for key in ("status", "database", "ai_service", "uptime_seconds", "version"):
        assert key in body
    assert body["version"] == "2.0.0"


# --------------------------- upload integrity --------------------------- #
def test_corrupted_upload_leaves_no_partial_record(client):
    before = len(client.get("/api/documents").json())
    res = upload_bytes(client, "broken.pdf", b"%PDF-1.4\n garbage \xde\xad", "application/pdf")
    assert res.status_code == 422
    after = len(client.get("/api/documents").json())
    assert after == before  # nothing persisted


# ------------------------------- export --------------------------------- #
def test_export_returns_zip_with_all_files(client):
    upload_text_doc(client, "e.txt", "exportable content here " * 10)
    client.post("/api/query", json={"question": "content", "mode": "rag"})
    res = client.get("/api/export/my-data")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = set(zf.namelist())
    assert {"documents.json", "queries.json", "highlights.json"} <= names


def test_export_rate_limited(client, monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "rate_limit_export", "1/hour")
    assert client.get("/api/export/my-data").status_code == 200
    assert client.get("/api/export/my-data").status_code == 429


# ------------------------------ DB resilience --------------------------- #
def test_database_operational_error_returns_503(client):
    def _boom():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_db] = _boom
    try:
        res = client.get("/api/documents")
        assert res.status_code == 503
        assert res.json()["error"]["status_code"] == 503
    finally:
        # Restore the rolled-back test session override from conftest.
        app.dependency_overrides.pop(get_db, None)
