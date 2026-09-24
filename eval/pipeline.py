"""Standalone RAG pipeline for the eval workstream.

Every stage (load -> chunk -> embed -> retrieve -> generate) is a separately
callable function, per the assignment. This module does NOT fork the
production chunking/embedding/generation logic: it imports and calls
``backend/app/ingestion.py``, ``backend/app/llm.py``, and
``backend/app/similarity.py`` directly, so the eval measures the same code
that runs in production, not a reimplementation of it.

Nothing here touches routes, the database, storage, or auth — it only needs
the three pure/standalone modules above plus a local ``dataset/`` directory
of markdown files.
"""
from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass, field

# Make the backend's ``app`` package importable without turning it into an
# installed dependency or duplicating its code.
_BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app import ingestion, llm  # noqa: E402
from app.similarity import top_k_by_similarity  # noqa: E402

DATASET_DIR = pathlib.Path(__file__).resolve().parent / "dataset"


@dataclass
class Document:
    doc_id: str
    title: str
    path: str
    text: str


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    strategy: str
    text: str
    section_heading: str | None = None


@dataclass
class Retrieved:
    chunk: Chunk
    score: float


@dataclass
class Index:
    """A chunked, embedded corpus for one chunking strategy."""

    strategy: str
    chunks: list[Chunk]
    vectors: list[list[float]] = field(repr=False)


# --------------------------------------------------------------------------- #
# Stage 1: load
# --------------------------------------------------------------------------- #
def load_documents(dataset_dir: pathlib.Path = DATASET_DIR) -> list[Document]:
    """Read every ``.md`` file in ``dataset_dir`` into a ``Document``."""
    docs: list[Document] = []
    for path in sorted(dataset_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("#").strip() if text else path.stem
        docs.append(Document(doc_id=path.stem, title=title, path=str(path), text=text))
    return docs


# --------------------------------------------------------------------------- #
# Stage 2: chunk
# --------------------------------------------------------------------------- #
def _markdown_to_blocks(text: str) -> list[dict]:
    """Turn a markdown document into ingestion.py's provenance-block schema.

    ``chunk_blocks``/``chunk_blocks_semantic`` expect blocks tagged with
    ``is_heading``/``heading``/``page``; our source files have no real pages,
    so every block is page 1, and a line starting with ``#`` becomes a
    heading block (its heading text carries forward to the body lines that
    follow it, exactly as production does for real extracted documents).
    """
    blocks: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            blocks.append({"text": heading, "is_heading": True, "heading": heading, "page": 1})
        else:
            blocks.append({"text": line, "is_heading": False, "page": 1})
    return blocks


def chunk_character(doc: Document) -> list[Chunk]:
    """Production's character-window strategy (``ingestion.chunk_blocks``)."""
    blocks = _markdown_to_blocks(doc.text)
    raw = ingestion.chunk_blocks(blocks)  # default chunk_size=800 chars, overlap=150
    return _to_chunks(doc, raw, "character")


def chunk_sentence(doc: Document) -> list[Chunk]:
    """Production's sentence-boundary strategy (``ingestion.chunk_blocks_semantic``)."""
    blocks = _markdown_to_blocks(doc.text)
    raw = ingestion.chunk_blocks_semantic(blocks)  # default chunk_size=800 tokens, overlap=2 sentences
    return _to_chunks(doc, raw, "sentence")


def _to_chunks(doc: Document, raw: list[dict], strategy: str) -> list[Chunk]:
    return [
        Chunk(
            chunk_id=f"{doc.doc_id}::{strategy}::{i}",
            doc_id=doc.doc_id,
            strategy=strategy,
            text=c["text"],
            section_heading=c.get("section_heading"),
        )
        for i, c in enumerate(raw)
    ]


CHUNKERS = {"character": chunk_character, "sentence": chunk_sentence}


def chunk(documents: list[Document], strategy: str) -> list[Chunk]:
    """Chunk every document with the named strategy ('character' or 'sentence')."""
    fn = CHUNKERS[strategy]
    out: list[Chunk] = []
    for doc in documents:
        out.extend(fn(doc))
    return out


# --------------------------------------------------------------------------- #
# Stage 3: embed
# --------------------------------------------------------------------------- #
def embed(chunks: list[Chunk]) -> list[list[float]]:
    """Embed chunk texts via ``llm.embed_texts`` (OpenAI, or the offline
    deterministic fallback if no API key is configured). Order-preserving."""
    return llm.embed_texts([c.text for c in chunks])


def build_index(strategy: str, documents: list[Document]) -> Index:
    """Convenience wrapper: chunk + embed a whole corpus for one strategy."""
    chunks = chunk(documents, strategy)
    vectors = embed(chunks)
    return Index(strategy=strategy, chunks=chunks, vectors=vectors)


# --------------------------------------------------------------------------- #
# Stage 4: retrieve
# --------------------------------------------------------------------------- #
def retrieve(query: str, index: Index, k: int = 5) -> list[Retrieved]:
    """Embed ``query`` and return its top-``k`` chunks from ``index`` by
    cosine similarity, using the same ``top_k_by_similarity`` production uses."""
    query_vec = llm.embed_texts([query])[0]
    candidates = list(enumerate(index.vectors))
    ranked = top_k_by_similarity(query_vec, candidates, k)
    return [Retrieved(chunk=index.chunks[i], score=score) for i, score in ranked]


# --------------------------------------------------------------------------- #
# Stage 5: generate
# --------------------------------------------------------------------------- #
def generate(query: str, retrieved: list[Retrieved]) -> str:
    """Generate a RAG answer via ``llm.generate_answer`` (OpenAI -> Groq ->
    offline extractive fallback, exactly as production falls back)."""
    context_chunks = [r.chunk.text for r in retrieved]
    return llm.generate_answer(query, context_chunks, mode="rag")
