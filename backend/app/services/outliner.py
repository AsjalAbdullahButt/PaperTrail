"""Document outline extraction.

For DOCX the extractor already tags heading blocks with explicit levels, which
are used directly. For other formats headings are detected heuristically:
ALL-CAPS lines, or short title-case lines that don't end in a sentence
terminator. Each outline entry is anchored to the chunk it first appears in.
"""
from __future__ import annotations

_MAX_HEADING_CHARS = 80
_MAX_HEADING_WORDS = 12


def _detect_heading(line: str) -> str | None:
    """Return a cleaned heading if ``line`` looks like one, else None."""
    s = line.strip()
    if not s or len(s) > _MAX_HEADING_CHARS:
        return None
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 2:
        return None
    words = s.split()
    if len(words) > _MAX_HEADING_WORDS:
        return None
    # ALL CAPS (e.g. "EXECUTIVE SUMMARY").
    if s.upper() == s:
        return s
    # Title-ish: starts uppercase, no terminal punctuation, reasonably short.
    if s[0].isupper() and not s.endswith((".", ",", ";", ":", "!", "?")) and len(words) <= 8:
        return s
    return None


def _first_chunk_with(heading: str, chunk_texts: list[str]) -> int:
    needle = heading.strip().lower()
    for i, text in enumerate(chunk_texts):
        if needle and needle in text.lower():
            return i
    return 0


def extract_outline(blocks: list[dict], chunk_texts: list[str]) -> list[dict]:
    """Build ``[{"heading","level","chunk_index"}]`` from extractor blocks.

    Explicit DOCX heading levels are preferred; otherwise headings are detected
    per line. Duplicate headings (case-insensitive) are emitted once.
    """
    out: list[dict] = []
    seen: set[str] = set()

    for b in blocks:
        candidates: list[tuple[str, int]] = []
        if b.get("is_heading") and b.get("heading"):
            candidates.append((str(b["heading"]), int(b.get("level") or 1)))
        else:
            for line in (b.get("text") or "").splitlines():
                det = _detect_heading(line)
                if det:
                    candidates.append((det, 1))

        for heading, level in candidates:
            key = heading.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "heading": heading.strip()[:500],
                    "level": max(1, min(3, level)),
                    "chunk_index": _first_chunk_with(heading, chunk_texts),
                }
            )
    return out
