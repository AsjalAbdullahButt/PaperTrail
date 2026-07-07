"""Tests for ingestion: PDF extraction, content sniffing, error handling."""
from __future__ import annotations

import pytest

from app.ingestion import extract_text, sniff_content_ok
from ._helpers import make_encrypted_pdf, make_text_pdf


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
