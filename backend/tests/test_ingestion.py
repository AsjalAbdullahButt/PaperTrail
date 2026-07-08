"""Tests for ingestion: extraction, chunking provenance, importance, outline."""
from __future__ import annotations

import io

import pytest

from app.ingestion import chunk_blocks, extract_text, sniff_content_ok
from app.services import extractor
from app.services.importance import extract_highlights, score_chunks
from app.services.outliner import extract_outline
from ._helpers import make_encrypted_pdf, make_text_pdf


def _make_docx(paras: list[tuple[str, str | None]]) -> bytes:
    """Build a .docx from (text, style) pairs; style None => body paragraph."""
    import docx

    d = docx.Document()
    for text, style in paras:
        d.add_paragraph(text, style=style) if style else d.add_paragraph(text)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _make_xlsx(rows: list[list]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_extract_text_from_pdf():
    pdf = make_text_pdf("Hello PaperTrail ingestion test")
    text, pages = extract_text(pdf, "pdf")
    assert "Hello PaperTrail ingestion test" in text
    assert pages == 1


def test_extract_text_from_txt():
    text, pages = extract_text(b"plain text body", "txt")
    assert text == "plain text body"
    assert pages is None


def test_extract_encrypted_pdf_raises():
    with pytest.raises(Exception):
        extract_text(make_encrypted_pdf(), "pdf")


def test_extract_corrupt_pdf_raises():
    with pytest.raises(Exception):
        extract_text(b"%PDF-1.4 not really a pdf \xde\xad", "pdf")


def test_sniff_valid_pdf():
    assert sniff_content_ok(make_text_pdf("x"), "pdf") is True


def test_sniff_rejects_non_pdf_with_pdf_extension():
    assert sniff_content_ok(b"just text, not a pdf", "pdf") is False


def test_sniff_accepts_utf8_text():
    assert sniff_content_ok("café — résumé".encode("utf-8"), "txt") is True


def test_sniff_rejects_binary_as_text():
    assert sniff_content_ok(b"\x00\x01\x02\x03" * 100, "txt") is False
