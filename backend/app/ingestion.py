"""Reusable ingestion helpers: text extraction and chunking.

Kept separate from the router so the chunker can be unit-tested in isolation
(Phase 6) and reused anywhere.
"""
from __future__ import annotations

import io

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

SUPPORTED_TYPES = {"pdf", "txt", "md"}


def file_type_from_name(filename: str) -> str:
    """Lowercase extension without the dot (e.g. 'report.PDF' -> 'pdf')."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def sniff_content_ok(data: bytes, file_type: str) -> bool:
    """Best-effort content validation by magic bytes / decodability.

    Guards against a file whose extension lies about its content (a binary
    blob renamed ``.txt``, or a non-PDF renamed ``.pdf``). Extension checks
    alone are not enough.
    """
    file_type = file_type.lower()
    if file_type == "pdf":
        # Every PDF begins with "%PDF-" (optionally after a few junk bytes).
        return data[:1024].lstrip()[:5] == b"%PDF-"
    if file_type in {"txt", "md"}:
        # Reject content with NUL bytes (a strong binary signal) and anything
        # that is not decodable as UTF-8/Latin-1 text.
        if b"\x00" in data[:8192]:
            return False
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            # Fall back to a tolerant check: mostly-printable bytes.
            sample = data[:8192]
            printable = sum(
                1 for b in sample if b in (9, 10, 13) or 32 <= b <= 126 or b >= 160
            )
            return printable / max(1, len(sample)) > 0.85
    # Unknown types are handled by the extension allow-list upstream.
    return True


def extract_text(data: bytes, file_type: str) -> tuple[str, int | None]:
    """Extract plain text from raw bytes.

    Returns ``(text, page_count)``. ``page_count`` is None for non-paged formats
    (txt/md) and the number of PDF pages for PDFs.
    """
    file_type = file_type.lower()
    if file_type == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = reader.pages
        text = "\n\n".join((page.extract_text() or "") for page in pages)
        return text, len(pages)

    if file_type in {"txt", "md"}:
        # Decode tolerantly; source encodings vary.
        return data.decode("utf-8", errors="replace"), None

    raise ValueError(f"Unsupported file type: {file_type!r}")


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split text into overlapping, whitespace-trimmed chunks.

    ~``chunk_size`` characters each with ~``overlap`` characters of overlap
    between consecutive chunks. Empty/whitespace-only chunks are dropped.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    normalized = text.strip()
    if not normalized:
        return []

    step = chunk_size - overlap
    chunks: list[str] = []
    start = 0
    n = len(normalized)
    while start < n:
        piece = normalized[start : start + chunk_size].strip()
        if piece:
            chunks.append(piece)
        # Stop once this window reaches the end, so we don't emit a tiny
        # trailing chunk that is fully contained in the previous one.
        if start + chunk_size >= n:
            break
        start += step
    return chunks
