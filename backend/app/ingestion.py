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


def chunk_blocks(
    blocks: list[dict], chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[dict]:
    """Chunk provenance-carrying blocks (from services.extractor.extract_blocks).

    Concatenates block texts, windows them exactly like ``chunk_text``, and
    attributes each chunk the ``page_number`` and ``section_heading`` of the
    block that its start position falls in (the current heading section carries
    forward across body blocks). Returns
    ``[{"text","page_number","section_heading"}]``.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    sep = "\n\n"
    full = ""
    # (start, end, page, section) spans into the joined text.
    spans: list[tuple[int, int, int, str | None]] = []
    current_section: str | None = None
    for b in blocks:
        text = (b.get("text") or "").strip()
        if not text:
            continue
        if b.get("is_heading"):
            current_section = b.get("heading") or text
        section = b.get("heading") if b.get("is_heading") else current_section
        start = len(full)
        full += text
        spans.append((start, len(full), int(b.get("page", 1)), section))
        full += sep

    full = full.rstrip()
    if not full:
        return []

    def _attr(pos: int) -> tuple[int, str | None]:
        for s, e, page, section in spans:
            if s <= pos < e:
                return page, section
        # Position fell in a separator between blocks: use the preceding block.
        prev = [sp for sp in spans if sp[0] <= pos]
        if prev:
            _, _, page, section = prev[-1]
            return page, section
        return 1, None

    step = chunk_size - overlap
    out: list[dict] = []
    start = 0
    n = len(full)
    while start < n:
        window = full[start : start + chunk_size]
        piece = window.strip()
        if piece:
            page, section = _attr(start)
            out.append(
                {"text": piece, "page_number": page, "section_heading": section}
            )
        if start + chunk_size >= n:
            break
        start += step
    return out
