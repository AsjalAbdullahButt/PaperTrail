"""HyDE-style query expansion (Gao et al., 2022, "Precise Zero-Shot Dense
Retrieval without Relevance Labels").

Questions and answer passages live in different parts of embedding space. HyDE
asks an LLM to write a short *hypothetical* answer passage, then retrieves with
the embedding of that passage instead of the question's. The hypothetical text
may be factually wrong; it only has to look like a relevant document.
"""
from __future__ import annotations

from .. import llm

_SYSTEM = (
    "You write short passages in the style of a research paper. Given a question, write a "
    "2-3 sentence passage that would directly answer it, using precise technical terminology. "
    "Do not mention that the passage is hypothetical and do not restate the question."
)


def hyde_passage(question: str) -> str:
    """Hypothetical answer passage for ``question``; empty if no LLM is configured."""
    return llm.complete_text(question, system=_SYSTEM, temperature=0.2).strip()
