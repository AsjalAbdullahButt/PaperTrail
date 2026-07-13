"""Coverage for GET /api/export/my-data, in particular that original files are
retrieved through the storage abstraction (not raw filesystem paths)."""
from __future__ import annotations

import io
import json
import zipfile

from conftest import requires_db

from ._helpers import upload_text_doc

pytestmark = requires_db


def test_export_includes_json_files(client):
    upload_text_doc(client, "notes.txt", "hello world " * 50)
    res = client.get("/api/export/my-data")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(res.content))
    names = zf.namelist()
    assert "documents.json" in names
    assert "queries.json" in names
    assert "highlights.json" in names

    docs = json.loads(zf.read("documents.json"))
    assert any(d["filename"] == "notes.txt" for d in docs)


def test_export_includes_original_file_via_storage(client, monkeypatch):
    import app.routers.documents as documents_router

    # Override the autouse fixture that disables STORE_ORIGINALS for this test.
    monkeypatch.setattr(documents_router.settings, "store_originals", True, raising=False)

    body = upload_text_doc(client, "original.txt", "content that must survive export " * 10)
    res = client.get("/api/export/my-data")
    assert res.status_code == 200

    zf = zipfile.ZipFile(io.BytesIO(res.content))
    expected_name = f"files/{body['id']}_original.txt"
    assert expected_name in zf.namelist()
    assert b"content that must survive export" in zf.read(expected_name)


def test_export_skips_document_with_missing_storage_key(client, db_session):
    """A document whose storage_key points at nothing (e.g. purged file) must
    not crash the export — it is silently skipped."""
    from sqlalchemy import select

    from app.models import Document

    body = upload_text_doc(client, "ghost.txt", "will be orphaned " * 10)
    doc = db_session.execute(
        select(Document).where(Document.id == body["id"])
    ).scalar_one()
    doc.storage_key = "uploads/nonexistent/does-not-exist.txt"
    db_session.commit()

    res = client.get("/api/export/my-data")
    assert res.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(res.content))
    assert not any(n.startswith("files/") for n in zf.namelist())
