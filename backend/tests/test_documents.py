"""Router coverage for /api/documents: upload validation, listing, pagination."""
from __future__ import annotations

import app.routers.documents as documents_router
from ._helpers import make_encrypted_pdf, make_text_pdf, upload_bytes, upload_text_doc

from conftest import requires_db

pytestmark = requires_db


def test_upload_txt_creates_chunks(client):
    body = upload_text_doc(client, "notes.txt", "hello world " * 200)
    assert body["filename"] == "notes.txt"
    assert body["chunks_created"] >= 1


def test_upload_pdf_extracts_text(client):
    pdf = make_text_pdf("Invoice total is 1234 dollars for consulting services")
    res = upload_bytes(client, "invoice.pdf", pdf, "application/pdf")
    assert res.status_code == 200, res.text
    assert res.json()["chunks_created"] >= 1


def test_upload_unsupported_type_rejected(client):
    res = upload_bytes(client, "malware.exe", b"MZ\x90\x00binary", "application/octet-stream")
    assert res.status_code == 415
    assert "Unsupported file type" in res.json()["error"]["message"]


def test_upload_empty_file_rejected(client):
    res = upload_bytes(client, "empty.txt", b"", "text/plain")
    assert res.status_code == 400
    assert "empty" in res.json()["error"]["message"].lower()


def test_upload_oversized_file_rejected(client, monkeypatch):
    # Shrink the ceiling so the test payload is comfortably "too big".
    # max_upload_bytes is derived from max_upload_mb, so patching the latter
    # drives the check (0.001 MB ~= 1048 bytes < 2048-byte payload).
    monkeypatch.setattr(documents_router.settings, "max_upload_mb", 0.001, raising=False)
    res = upload_bytes(client, "big.txt", b"x" * 2048, "text/plain")
    assert res.status_code == 413
    assert "maximum upload size" in res.json()["error"]["message"].lower()


def test_upload_txt_with_binary_content_rejected(client):
    # A binary blob renamed .txt must be rejected by content sniffing.
    res = upload_bytes(client, "fake.txt", b"\x00\x01\x02\x03\xff\xfe" * 100, "text/plain")
    assert res.status_code == 422
    assert "content does not match" in res.json()["error"]["message"].lower()


def test_upload_pdf_that_is_not_a_pdf_rejected(client):
    res = upload_bytes(client, "fake.pdf", b"this is plainly not a pdf file", "application/pdf")
    assert res.status_code == 422


def test_upload_corrupt_pdf_returns_422(client):
    # Valid magic bytes but unreadable structure -> graceful 422, not 500.
    res = upload_bytes(client, "broken.pdf", b"%PDF-1.4\n garbage \xde\xad\xbe\xef", "application/pdf")
    assert res.status_code == 422


def test_upload_password_protected_pdf_returns_422(client):
    res = upload_bytes(client, "locked.pdf", make_encrypted_pdf(), "application/pdf")
    assert res.status_code == 422


def test_list_documents_newest_first_with_chunk_counts(client):
    upload_text_doc(client, "first.txt", "alpha content here")
    upload_text_doc(client, "second.txt", "beta content here")
    res = client.get("/api/documents")
    assert res.status_code == 200
    docs = res.json()
    assert docs[0]["filename"] == "second.txt"  # newest first
    assert all(d["chunk_count"] >= 1 for d in docs)


def test_list_documents_pagination(client):
    for i in range(5):
        upload_text_doc(client, f"doc{i}.txt", f"content number {i}")
    page = client.get("/api/documents?limit=2&offset=0")
    assert page.status_code == 200
    assert len(page.json()) == 2

    # Invalid pagination params are rejected by validation.
    assert client.get("/api/documents?limit=0").status_code == 422
    assert client.get("/api/documents?limit=999").status_code == 422


# --------------------- Phase 2: enriched ingestion ---------------------- #
def _docx_bytes(paras):
    import io

    import docx

    d = docx.Document()
    for text, style in paras:
        d.add_paragraph(text, style=style) if style else d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _xlsx_bytes(rows):
    import io

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_upload_returns_highlights_and_importance(client):
    body = upload_text_doc(
        client,
        "report.txt",
        "Quarterly revenue rose sharply. "
        "Machine learning adoption accelerated across teams. "
        "Legal boilerplate and standard disclaimers appear here. " * 20,
    )
    assert 1 <= len(body["highlights"]) <= 8
    for h in body["highlights"]:
        assert 0.0 <= h["score"] <= 1.0 and "text" in h
    assert body["word_count"] > 0


def test_upload_docx_extracts_outline(client):
    data = _docx_bytes(
        [
            ("PROJECT OVERVIEW", "Heading 1"),
            ("This document describes the overall project scope and goals.", None),
            ("Milestones", "Heading 2"),
            ("Key milestones are tracked on a quarterly cadence here.", None),
        ]
    )
    res = upload_bytes(client, "plan.docx", data)
    assert res.status_code == 200, res.text
    outline = res.json()["outline"]
    assert any(o["heading"] == "PROJECT OVERVIEW" for o in outline)


def test_upload_xlsx_creates_queryable_chunks(client):
    data = _xlsx_bytes([["Product", "Price"], ["Alpha", 10], ["Beta", 20]])
    res = upload_bytes(client, "prices.xlsx", data)
    assert res.status_code == 200, res.text
    assert res.json()["chunks_created"] >= 1
    assert res.json()["file_type"] == "xlsx"


def test_document_status_reports_processed(client):
    body = upload_text_doc(client, "s.txt", "some content to process here " * 10)
    res = client.get(f"/api/documents/{body['id']}/status")
    assert res.status_code == 200
    payload = res.json()
    assert payload["processed"] is True
    assert payload["chunk_count"] >= 1
    assert payload["processed_at"] is not None


def test_document_status_cross_user_forbidden(client, anon_client):
    from conftest import auth_headers

    body = upload_text_doc(client, "mine.txt", "private content here " * 10)
    other = auth_headers(anon_client, "intruder@papertrail.io")
    res = anon_client.get(f"/api/documents/{body['id']}/status", headers=other)
    assert res.status_code == 403
