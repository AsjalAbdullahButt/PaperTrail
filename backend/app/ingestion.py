"""Reusable ingestion helpers: text extraction and chunking.

Kept separate from the router so the chunker can be unit-tested in isolation
(Phase 6) and reused anywhere.
"""
from __future__ import annotations

import io
import re

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
CHUNK_OVERLAP_SENTENCES = 2
# Rough token estimate used only to size semantic chunks (no tokenizer dep).
CHARS_PER_TOKEN = 4

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


# Titles/initials that end in a period without ending the sentence (Mr. Smith,
# Dr. Jones, U.S. policy, etc.) — checked against the *end* of an accumulated
# sentence, so "Mr." merges with the words that follow it.
_ABBREVIATION_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|Vs|vs|etc|e\.g|i\.e|Inc|Ltd|Co|Corp|"
    r"Gov|Sen|Rep|Gen|Col|Capt|Lt|Ave|No|Vol|Fig|approx|U\.S|U\.K)\.$",
    re.IGNORECASE,
)
# Candidate sentence boundary: end punctuation followed by whitespace. Split
# eagerly here, then re-merge pieces whose preceding fragment ends in a known
# abbreviation (handles "Mr. Smith said" without a spaCy/NLTK dependency).
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Split ``text`` into sentences, keeping known abbreviations intact."""
    text = text.strip()
    if not text:
        return []
    pieces = _SENTENCE_BOUNDARY_RE.split(text)
    sentences: list[str] = []
    for piece in pieces:
        if sentences and _ABBREVIATION_RE.search(sentences[-1]):
            sentences[-1] = f"{sentences[-1]} {piece}"
        else:
            sentences.append(piece)
    return [s.strip() for s in sentences if s.strip()]


def chunk_blocks_semantic(
    blocks: list[dict],
    chunk_size: int = CHUNK_SIZE,
    overlap_sentences: int = CHUNK_OVERLAP_SENTENCES,
) -> list[dict]:
    """Sentence-boundary-aware alternative to ``chunk_blocks``.

    Joins block text (preserving page/section provenance exactly like
    ``chunk_blocks``), splits it into sentences, and accumulates whole
    sentences into chunks that stay within ``chunk_size`` tokens (approximated
    as ``chunk_size * CHARS_PER_TOKEN`` characters — no tokenizer dependency).
    Consecutive chunks overlap by ``overlap_sentences`` whole sentences instead
    of a character window, so a chunk boundary never lands mid-sentence.

    Returns the same ``[{"text","page_number","section_heading"}]`` schema as
    ``chunk_blocks``.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap_sentences < 0:
        raise ValueError("overlap_sentences must be >= 0")

    max_chars = chunk_size * CHARS_PER_TOKEN

    # (sentence, page, section) in document order, carrying forward the
    # section heading exactly like chunk_blocks does.
    sentences: list[tuple[str, int, str | None]] = []
    current_section: str | None = None
    for b in blocks:
        text = (b.get("text") or "").strip()
        if not text:
            continue
        if b.get("is_heading"):
            current_section = b.get("heading") or text
        section = b.get("heading") if b.get("is_heading") else current_section
        page = int(b.get("page", 1))
        for sent in split_sentences(text):
            sentences.append((sent, page, section))

    if not sentences:
        return []

    out: list[dict] = []
    i = 0
    n = len(sentences)
    while i < n:
        window_start = i
        current: list[tuple[str, int, str | None]] = []
        current_len = 0
        while i < n:
            sent, page, section = sentences[i]
            added_len = len(sent) + (1 if current else 0)  # + joining space
            if current and current_len + added_len > max_chars:
                break
            current.append(sentences[i])
            current_len += added_len
            i += 1
        if not current:
            # A single sentence longer than max_chars: take it alone so the
            # loop still makes progress.
            current = [sentences[i]]
            i += 1

        text = " ".join(s for s, _, _ in current)
        page = current[0][1]
        section = current[0][2]
        out.append({"text": text, "page_number": page, "section_heading": section})

        if i >= n:
            break
        # Step back by overlap_sentences for the next chunk, but always past
        # window_start so the loop is guaranteed to make forward progress.
        i = max(window_start + 1, i - overlap_sentences)
    return out
