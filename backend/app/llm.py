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
from typing import Iterator

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
    # Batch to stay well within request limits for large documents.
    batch_size = 100
    batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]

    def _embed_batch(batch: list[str]) -> list[list[float]]:
        resp = client.embeddings.create(model=settings.openai_embedding_model, input=batch)
        # Order by `index` so chunk<->embedding alignment never depends on the
        # order the API returns items in; a misalignment would silently corrupt
        # retrieval (wrong snippets cited) with no error.
        return [item.embedding for item in sorted(resp.data, key=lambda d: d.index)]

    if len(batches) == 1:
        return _embed_batch(batches[0])

    # Independent requests (large documents only — most uploads fit in one
    # batch and never hit this path): fire them concurrently instead of
    # waiting on each round trip in turn. Order is preserved via `results`
    # regardless of which batch's request finishes first.
    from concurrent.futures import ThreadPoolExecutor

    results: list[list[list[float]]] = [[] for _ in batches]
    with ThreadPoolExecutor(max_workers=min(8, len(batches))) as pool:
        futures = {pool.submit(_embed_batch, batch): i for i, batch in enumerate(batches)}
        for future in futures:
            results[futures[future]] = future.result()

    out: list[list[float]] = []
    for batch_result in results:
        out.extend(batch_result)
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



# Shared formatting instructions so multi-part answers render as structure
# (headings/bold/lists), not a wall of text — the frontend now parses this
# markdown subset back into real elements (see Citations.tsx).
_FORMATTING_INSTRUCTIONS = (
    "Format the answer for readability: if it covers more than one distinct "
    "point, break it into labeled sections using markdown headings (## "
    "Section Name). Use **bold** only around key terms, never whole "
    "sentences. Prefer short paragraphs; only use a \"- \" bullet list when "
    "the content is genuinely a list (steps, enumerated items), not as a "
    "default structure."
)


def _build_messages(question: str, context_chunks: list[str], mode: str) -> list[dict]:
    """Assemble the chat messages shared by every hosted-model provider."""
    if mode == "rag":
        context = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(context_chunks))
        system = (
            "You are PaperTrail, a careful assistant that answers ONLY from the "
            "provided context. If the answer is not in the context, say you could "
            "not find it in the provided documents. Cite sources inline as [1], [2], "
            "etc., matching the numbered context passages. " + _FORMATTING_INSTRUCTIONS
        )
        user = f"Context:\n{context}\n\nQuestion: {question}"
    else:
        system = (
            "You are PaperTrail, a helpful and concise assistant. "
            + _FORMATTING_INSTRUCTIONS
        )
        user = question
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


# --------------------------------------------------------------------------- #
# Streaming generation (RAG mode only — see routers/query.py's /query/stream)
# --------------------------------------------------------------------------- #
def stream_rag_answer(question: str, context_chunks: list[str]) -> Iterator[str]:
    """Yield successive answer-text chunks for a RAG-mode question.

    Tries OpenAI streaming, then Groq streaming, then falls back to yielding
    the full offline extractive answer as a single chunk — the same provider
    fallback order as ``generate_answer``, just token-by-token instead of a
    single blocking call.
    """
    if settings.openai_ready:
        try:
            yield from _stream_openai(question, context_chunks)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI streaming failed (%s); trying next fallback.", exc)

    if settings.groq_ready:
        try:
            yield from stream_rag_answer_groq(question, context_chunks)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq streaming failed (%s); using offline fallback.", exc)

    yield _offline_generate(question, context_chunks, "rag")


def _stream_openai(question: str, context_chunks: list[str]) -> Iterator[str]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    stream = client.chat.completions.create(
        model=settings.openai_chat_model,
        messages=_build_messages(question, context_chunks, "rag"),
        temperature=0.2,
        stream=True,
    )
    for event in stream:
        delta = event.choices[0].delta.content
        if delta:
            yield delta


def stream_rag_answer_groq(question: str, context_chunks: list[str]) -> Iterator[str]:
    """Groq's chat endpoint is OpenAI-compatible, including ``stream=True``."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    stream = client.chat.completions.create(
        model=settings.groq_chat_model,
        messages=_build_messages(question, context_chunks, "rag"),
        temperature=0.2,
        stream=True,
    )
    for event in stream:
        delta = event.choices[0].delta.content
        if delta:
            yield delta


# Marker the model is asked to emit between the answer and the follow-up
# questions in the combined RAG call below — arbitrary but distinctive enough
# to never collide with real answer text.
_FOLLOWUP_MARKER = "===FOLLOWUPS==="


def _build_rag_messages_with_followups(question: str, context_chunks: list[str]) -> list[dict]:
    context = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(context_chunks))
    system = (
        "You are PaperTrail, a careful assistant that answers ONLY from the "
        "provided context. If the answer is not in the context, say you could "
        "not find it in the provided documents. Cite sources inline as [1], [2], "
        "etc., matching the numbered context passages. " + _FORMATTING_INSTRUCTIONS
        + " After the complete answer, on its own new line write exactly "
        f"{_FOLLOWUP_MARKER} followed by a JSON array of exactly 4 short "
        "follow-up questions the user might ask next — no prose, no markdown, "
        "nothing else after it."
    )
    user = f"Context:\n{context}\n\nQuestion: {question}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def generate_rag_answer_with_followups(question: str, context_chunks: list[str]) -> tuple[str, str]:
    """RAG answer + a raw follow-up-questions blob from a *single* model call.

    Generating the answer and its follow-up questions used to be two separate
    sequential completions (see ``generate_answer`` + the old two-call flow in
    services/followup.py) — every hosted-model round trip costs roughly the
    same regardless of what's asked for, so combining them into one prompt
    with a delimited trailing block cuts a full network round trip off every
    RAG/multi-hop query without changing what either output contains.

    Returns ``(answer, raw_followups_blob)``; the blob is ``""`` when the
    model didn't include the marker (or no provider is configured) — callers
    already treat that as "no follow-ups", the same graceful-degradation
    contract the old two-call flow had.
    """
    if not (settings.openai_ready or settings.groq_ready):
        return _offline_generate(question, context_chunks, "rag"), ""

    messages = _build_rag_messages_with_followups(question, context_chunks)
    raw: str | None = None

    if settings.openai_ready:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model=settings.openai_chat_model, messages=messages, temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI generation failed (%s); trying next fallback.", exc)

    if raw is None and settings.groq_ready:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
            resp = client.chat.completions.create(
                model=settings.groq_chat_model, messages=messages, temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq generation failed (%s); using offline fallback.", exc)

    if raw is None:
        return _offline_generate(question, context_chunks, "rag"), ""

    if _FOLLOWUP_MARKER in raw:
        answer_part, _, followups_part = raw.partition(_FOLLOWUP_MARKER)
        return answer_part.strip(), followups_part.strip()
    return raw, ""


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
