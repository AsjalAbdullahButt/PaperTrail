"""Tests for the reusable chunking function."""
import pytest

from app.ingestion import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\t  ") == []


def test_short_text_is_a_single_chunk():
    chunks = chunk_text("hello world", chunk_size=800, overlap=150)
    assert chunks == ["hello world"]


def test_chunks_respect_size_and_overlap():
    text = "".join(chr(ord("a") + (i % 26)) for i in range(2000))
    chunks = chunk_text(text, chunk_size=800, overlap=150)

    # start indices step by (800-150)=650: 0, 650, 1300 (window 1300..2000
    # reaches the end, so we stop) -> 3 chunks of lengths 800, 800, 700.
    assert len(chunks) == 3
    assert len(chunks[0]) == 800
    assert len(chunks[1]) == 800
    assert len(chunks[2]) == 700
    assert all(len(c) <= 800 for c in chunks)

    # Consecutive chunks overlap by exactly `overlap` characters.
    assert text[650:800] == chunks[0][650:800] == chunks[1][:150]
    assert text[1300:1450] == chunks[1][650:800] == chunks[2][:150]


def test_invalid_overlap_raises():
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=100, overlap=100)
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=0, overlap=0)
