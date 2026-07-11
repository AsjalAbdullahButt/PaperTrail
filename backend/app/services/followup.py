"""Follow-up question generation. Best-effort: returns [] on any failure, never
raises, so a query response is never blocked by this optional feature."""
from __future__ import annotations

import json
import logging
import re

from .. import llm

logger = logging.getLogger("papertrail.followup")

_SYSTEM = (
    "You generate follow-up questions. Return ONLY a JSON array of exactly 4 "
    "short question strings — no prose, no markdown, no keys."
)


def _parse_questions(raw: str) -> list[str]:
    """Extract a list of question strings from a model response."""
    if not raw:
        return []
    # Prefer a clean JSON array; fall back to the first [...] block in the text.
    candidates = [raw]
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for text in candidates:
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, list):
            questions = [str(q).strip() for q in data if str(q).strip()]
            if questions:
                return questions[:4]
    return []


def generate_followup_questions(
    query: str, answer: str, chunks: list[dict]
) -> list[str]:
    """Up to 4 follow-up questions; ``[]`` when unavailable (e.g. offline)."""
    summaries = "\n".join(f"- {c.get('text', '')[:200]}" for c in chunks[:4])
    prompt = (
        f"Question: {query}\n\nAnswer: {answer}\n\n"
        f"Relevant context:\n{summaries}\n\n"
        "Generate exactly 4 follow-up questions a user might ask next. "
        "Return as a JSON array of strings only."
    )
    try:
        raw = llm.complete_text(prompt, system=_SYSTEM, temperature=0.5)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Follow-up generation failed: %s", exc)
        return []
    return _parse_questions(raw)


def parse_followup_questions(raw: str) -> list[str]:
    """Public entry point for parsing a raw follow-ups blob, e.g. the trailing
    block ``llm.generate_rag_answer_with_followups`` splits off of a combined
    answer+follow-ups completion. Same parsing/validation as the standalone
    call above, just decoupled from making the model call itself."""
    return _parse_questions(raw)
