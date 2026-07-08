"""Single AI service module.

Every embedding and chat-completion call lives here so the provider can be
swapped by editing only this file.

Two paths:
  * **OpenAI** (default) when a real ``OPENAI_API_KEY`` is configured.
  * **Offline deterministic fallback** when no valid key is present. It produces
    stable hashing-based embeddings and an extractive answer, so the entire RAG
    pipeline runs, is testable, and gives meaningful retrieval without any paid
    API. Drop a real ``sk-...`` key into .env and it transparently switches.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re

from .config import settings

logger = logging.getLogger("papertrail.llm")

# Offline embedding dimensionality. Fixed so questions and chunks are comparable.
_OFFLINE_DIM = 512
_TOKEN_RE = re.compile(r"[a-z0-9]+")


# --------------------------------------------------------------------------- #
# Embeddings
# --------------------------------------------------------------------------- #
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one embedding vector per input string.

    Empty input -> empty output. On OpenAI failure we log and fall back to the
    offline embedder so ingestion never hard-crashes.
    """
    if not texts:
        return []

    if settings.openai_ready:
        try:
            return _openai_embed(texts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI embeddings failed (%s); using offline fallback.", exc)

    return [_offline_embed(t) for t in texts]


def _openai_embed(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    out: list[list[float]] = []
    # Batch to stay well within request limits for large documents.
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(model=settings.openai_embedding_model, input=batch)
        # Order by `index` so chunk<->embedding alignment never depends on the
        # order the API returns items in; a misalignment would silently corrupt
        # retrieval (wrong snippets cited) with no error.
        out.extend(item.embedding for item in sorted(resp.data, key=lambda d: d.index))
    return out


def _offline_embed(text: str) -> list[float]:
    """Deterministic bag-of-words hashing embedding, L2-normalized.

    Cosine similarity of these vectors reflects word overlap, which is enough
    for the retrieval step to surface the right chunk during offline testing.
    """
    vec = [0.0] * _OFFLINE_DIM
    for token in _TOKEN_RE.findall(text.lower()):
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        idx = h % _OFFLINE_DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
def generate_answer(question: str, context_chunks: list[str], mode: str) -> str:
    """Answer a question.

    RAG mode: answer strictly from ``context_chunks``. Direct mode: answer from
    the model's own knowledge (no retrieval), ``context_chunks`` ignored.
    """
    if settings.openai_ready:
        try:
            return _openai_generate(question, context_chunks, mode)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI generation failed (%s); using offline fallback.", exc)

    if settings.groq_ready:
        try:
            return _groq_generate(question, context_chunks, mode)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq generation failed (%s); using offline fallback.", exc)

    return _offline_generate(question, context_chunks, mode)


def _build_messages(question: str, context_chunks: list[str], mode: str) -> list[dict]:
    """Assemble the chat messages shared by every hosted-model provider."""
    if mode == "rag":
        context = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(context_chunks))
        system = (
            "You are PaperTrail, a careful assistant that answers ONLY from the "
            "provided context. If the answer is not in the context, say you could "
            "not find it in the provided documents. Cite sources inline as [1], [2], "
            "etc., matching the numbered context passages."
        )
        user = f"Context:\n{context}\n\nQuestion: {question}"
    else:
        system = "You are PaperTrail, a helpful and concise assistant."
        user = question
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _openai_generate(question: str, context_chunks: list[str], mode: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=_build_messages(question, context_chunks, mode),
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def _groq_generate(question: str, context_chunks: list[str], mode: str) -> str:
    """Generate via Groq's OpenAI-compatible chat endpoint (custom base_url)."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    resp = client.chat.completions.create(
        model=settings.groq_chat_model,
        messages=_build_messages(question, context_chunks, mode),
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def complete_text(prompt: str, system: str = "You are a helpful assistant.",
                  temperature: float = 0.3) -> str:
    """Single-turn completion for auxiliary tasks (refined queries, follow-up
    questions, timeline/event extraction).

    Returns the model's text, or ``""`` in offline mode (no generative model
    configured). Callers must treat ``""`` as "feature unavailable" and degrade
    gracefully — never raise.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    if settings.openai_ready:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model=settings.openai_chat_model, messages=messages,
                temperature=temperature,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI completion failed (%s).", exc)

    if settings.groq_ready:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
            resp = client.chat.completions.create(
                model=settings.groq_chat_model, messages=messages,
                temperature=temperature,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq completion failed (%s).", exc)

    return ""


def _offline_generate(question: str, context_chunks: list[str], mode: str) -> str:
    """Extractive, clearly-labeled offline answer."""
    if mode == "direct":
        return (
            "[offline mode] No chat model is configured, so PaperTrail cannot "
            "generate a free-form direct answer. Add OPENAI_API_KEY or GROQ_API_KEY "
            "to backend/.env to enable real generation. Your question was: "
            f"“{question.strip()}”"
        )

    if not context_chunks:
        return (
            "I could not find anything relevant in the provided documents to answer "
            "that question."
        )

    # Ground the answer in the single most relevant passage (already ranked).
    top = context_chunks[0].strip()
    snippet = top if len(top) <= 600 else top[:600].rsplit(" ", 1)[0] + "…"
    return (
        "[offline mode] Based on the most relevant passage in your documents [1]:\n\n"
        f"{snippet}"
    )
