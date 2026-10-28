"""Standalone RAG pipeline for the eval workstream.

Every stage (load -> chunk -> embed -> retrieve -> generate) is a separately
callable function. This module does NOT fork production logic: it imports and
calls the same modules the live app uses —

* ``app.ingestion``            chunking (``chunk_blocks`` / ``chunk_blocks_semantic``)
* ``app.llm``                  embeddings and answer generation
* ``app.similarity``           dense cosine ranking
* ``app.services.bm25_index``  sparse BM25
* ``app.services.importance``  per-document chunk importance
* ``app.services.retriever``   the fusion weights and min-max normaliser

The one place we cannot call production directly is ``hybrid_retrieve`` itself:
it is bound to SQLAlchemy sessions, per-user caches and ANN indexes, so
``retrieve_hybrid`` below re-implements its *scoring* (candidate union, min-max
normalisation, 0.6/0.4 fusion, importance boost) on in-memory arrays, taking
the weights and ``_minmax`` straight from the production module. Documented
deviation: production uses an approximate (USearch/KD-tree) dense candidate
search, the eval uses exact brute-force cosine for the dense candidates.

Nothing here touches routes, the database, storage or auth.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re
import sys
import time
from dataclasses import dataclass, field

_BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app import ingestion, llm  # noqa: E402
from app.config import settings  # noqa: E402
from app.services import query_expansion, reranker  # noqa: E402
from app.services import retriever as prod_retriever  # noqa: E402
from app.services.bm25_index import BM25Index  # noqa: E402
from app.services.importance import score_chunks  # noqa: E402
from app.similarity import top_k_by_similarity  # noqa: E402

# ``Settings`` reads ``.env`` relative to the current directory, so running from
# ``eval/`` would silently ignore ``backend/.env`` (and its API keys). Reload the
# shared settings object from the backend's .env regardless of the cwd.
_env_file = _BACKEND_DIR / ".env"
if _env_file.exists():
    for _name, _value in type(settings)(_env_file=_env_file).model_dump().items():
        setattr(settings, _name, _value)

EVAL_DIR = pathlib.Path(__file__).resolve().parent
DATASET_DIR = EVAL_DIR / "dataset"
CACHE_DIR = EVAL_DIR / ".cache"

# Expected embedding dimensions, used to detect a silent fall-back to the
# 512-d offline hashing embedder (``llm.embed_texts`` degrades quietly).
EXPECTED_DIM = {"openai": 1536, "hf": 384, "bge": 384}

# Eval embedder name -> (llm.embed_texts provider, Hugging Face model or None).
# "hf" is the project's default HF model; "bge" is a second local model so the
# embedding comparison needs no paid API key.
EMBEDDERS = {
    "openai": ("openai", None),
    "hf": ("hf", "sentence-transformers/all-MiniLM-L6-v2"),
    "bge": ("hf", "BAAI/bge-small-en-v1.5"),
}

_PAGE_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")


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
    page_number: int = 1
    section_heading: str | None = None
    importance: float = 0.0
    embed_text: str = ""  # text that is embedded (contextual-header variants); "" = same as ``text``


@dataclass
class Retrieved:
    chunk: Chunk
    score: float
    dense: float = 0.0
    sparse: float = 0.0
    rerank: float | None = None  # cross-encoder logit when re-ranking ran


@dataclass
class Index:
    """A chunked, embedded corpus for one (chunker, embedder) pair."""

    strategy: str
    embedder: str
    chunks: list[Chunk]
    vectors: list[list[float]] = field(repr=False)
    bm25: BM25Index | None = field(default=None, repr=False)


# --------------------------------------------------------------------------- #
# Stage 1: load
# --------------------------------------------------------------------------- #
def load_documents(dataset_dir: pathlib.Path = DATASET_DIR) -> list[Document]:
    """Read the corpus listed in ``manifest.csv`` (falls back to every ``.md``)."""
    manifest = dataset_dir / "manifest.csv"
    if manifest.exists():
        with manifest.open(encoding="utf-8", newline="") as f:
            ids = [row["doc_id"] for row in csv.DictReader(f)]
        paths = [dataset_dir / f"{i}.md" for i in ids]
    else:
        paths = sorted(dataset_dir.glob("*.md"))
    docs: list[Document] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("#").strip() if text else path.stem
        docs.append(Document(doc_id=path.stem, title=title, path=str(path), text=text))
    return docs


# --------------------------------------------------------------------------- #
# Stage 2: chunk
# --------------------------------------------------------------------------- #
def _markdown_to_blocks(text: str) -> list[dict]:
    """Turn a corpus markdown file into ingestion.py's provenance-block schema.

    ``<!-- page: N -->`` markers set the page of the blocks that follow, and
    ``## heading`` lines become heading blocks whose text carries forward to the
    body blocks after them — the same shape ``extractor.extract_blocks``
    produces for real uploads.
    """
    blocks: list[dict] = []
    page = 1
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _PAGE_RE.match(line)
        if m:
            page = int(m.group(1))
            continue
        if line.startswith("# "):  # document title line
            continue
        if line.startswith("## "):
            heading = line[3:].strip()
            blocks.append({"text": heading, "is_heading": True, "heading": heading, "page": page})
        else:
            blocks.append({"text": line, "is_heading": False, "page": page})
    return blocks


def _chunk_character(blocks: list[dict]) -> list[dict]:
    """Legacy fixed-window strategy (800 chars, 150 overlap)."""
    return ingestion.chunk_blocks(blocks)


def _chunk_sentence(blocks: list[dict]) -> list[dict]:
    """Production default: sentence-aware, up to 800 'tokens' (~3,200 chars)."""
    return ingestion.chunk_blocks_semantic(blocks)


def _chunk_sentence800(blocks: list[dict]) -> list[dict]:
    """Size-controlled variant: same sentence-boundary logic, capped so chunks
    are ~800 chars (200 'tokens' x CHARS_PER_TOKEN) like the character windows."""
    return ingestion.chunk_blocks_semantic(blocks, chunk_size=ingestion.CHUNK_SIZE // ingestion.CHARS_PER_TOKEN)


CHUNKERS = {
    "character": _chunk_character,
    "sentence": _chunk_sentence,
    "sentence800": _chunk_sentence800,
}
# ``<chunker>_ctx``: identical chunks, but the text that is *embedded* is prefixed
# with "<paper title> | <section>" (ingestion.contextualize_chunk). Display, BM25
# and citation text stay the raw chunk.
CONTEXTUAL_SUFFIX = "_ctx"


def chunk(documents: list[Document], strategy: str) -> list[Chunk]:
    """Chunk every document; importance is scored per document, as at upload."""
    contextual = strategy.endswith(CONTEXTUAL_SUFFIX)
    fn = CHUNKERS[strategy.removesuffix(CONTEXTUAL_SUFFIX)]
    out: list[Chunk] = []
    for doc in documents:
        raw = fn(_markdown_to_blocks(doc.text))
        importance = score_chunks([c["text"] for c in raw])
        for i, (c, imp) in enumerate(zip(raw, importance)):
            section = c.get("section_heading")
            out.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}::{strategy}::{i}",
                    doc_id=doc.doc_id,
                    strategy=strategy,
                    text=c["text"],
                    page_number=int(c.get("page_number") or 1),
                    section_heading=section,
                    importance=imp,
                    embed_text=ingestion.contextualize_chunk(c["text"], doc.title, section) if contextual else "",
                )
            )
    return out


# --------------------------------------------------------------------------- #
# Stage 3: embed
# --------------------------------------------------------------------------- #
def embedder_label(embedder: str) -> str:
    provider, model = EMBEDDERS[embedder]
    return settings.openai_embedding_model if provider == "openai" else model


def _cache_path(embedder: str) -> pathlib.Path:
    CACHE_DIR.mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{embedder}-{embedder_label(embedder)}")
    return CACHE_DIR / f"emb_{safe}.json"


def embed_texts(texts: list[str], embedder: str) -> list[list[float]]:
    """Embed through ``llm.embed_texts`` with ``embedding_provider`` set to
    ``embedder``, caching vectors on disk (keyed by model + text hash) so reruns
    don't re-pay for unchanged text. Raises if production's silent offline
    fallback kicked in (wrong vector dimension)."""
    provider, model = EMBEDDERS[embedder]
    settings.embedding_provider = provider
    if model:
        settings.hf_embedding_model = model
    path = _cache_path(embedder)
    cache: dict[str, list[float]] = json.loads(path.read_text()) if path.exists() else {}
    keys = [hashlib.sha1(t.encode("utf-8")).hexdigest() for t in texts]
    missing = [(k, t) for k, t in dict.fromkeys(zip(keys, texts)) if k not in cache]
    if missing:
        vectors = llm.embed_texts([t for _, t in missing])
        if any(len(v) != EXPECTED_DIM[embedder] for v in vectors):
            raise RuntimeError(
                f"{embedder!r} embeddings came back with dimension {len(vectors[0])}, expected "
                f"{EXPECTED_DIM[embedder]}: llm.embed_texts fell back to the offline hasher. "
                "Fix credentials / dependencies; refusing to evaluate on offline embeddings."
            )
        for (k, _), v in zip(missing, vectors):
            cache[k] = v
        path.write_text(json.dumps(cache))
    return [cache[k] for k in keys]


def build_index(strategy: str, documents: list[Document], embedder: str) -> Index:
    """Chunk + embed + BM25-index a whole corpus."""
    chunks = chunk(documents, strategy)
    vectors = embed_texts([c.embed_text or c.text for c in chunks], embedder)
    bm25 = BM25Index().build([c.text for c in chunks])
    return Index(strategy=strategy, embedder=embedder, chunks=chunks, vectors=vectors, bm25=bm25)


# --------------------------------------------------------------------------- #
# Stage 4: retrieve
# --------------------------------------------------------------------------- #
def retrieve_dense(query: str, index: Index, k: int = 5) -> list[Retrieved]:
    """Top-``k`` chunks by cosine similarity (production's ``top_k_by_similarity``)."""
    query_vec = embed_texts([query], index.embedder)[0]
    ranked = top_k_by_similarity(query_vec, list(enumerate(index.vectors)), k)
    return [Retrieved(chunk=index.chunks[i], score=score, dense=score) for i, score in ranked]


def _hybrid_scored(query: str, index: Index, k: int, expanded: str | None = None) -> list[Retrieved]:
    """All fused candidates, best first, mirroring ``services.retriever.hybrid_retrieve``.

    Candidates = top ``k * 20`` by dense cosine  U  top ``k * 20`` by BM25; dense
    cosine and normalised BM25 are each min-max normalised over the candidates,
    fused as ``0.6 * dense + 0.4 * sparse`` and multiplied by
    ``1 + 0.2 * importance``. Weights, multiplier and ``_minmax`` come from the
    production module. With ``expanded`` (a HyDE passage) the dense side embeds
    the passage and BM25 sees question + passage, as in production.
    """
    assert index.bm25 is not None
    query_vec = embed_texts([expanded or query], index.embedder)[0]
    sparse_query = f"{query}\n{expanded}" if expanded else query
    n = len(index.chunks)
    limit = max(k * prod_retriever._ANN_CANDIDATE_MULTIPLIER, k)

    dense_all = [prod_retriever._cosine(query_vec, v) for v in index.vectors]
    dense_top = sorted(range(n), key=lambda i: dense_all[i], reverse=True)[:limit]
    sparse_map = dict(index.bm25.search(sparse_query, top_k=n))
    sparse_top = [i for i, _ in index.bm25.search(sparse_query, top_k=limit)]

    candidates = sorted(set(dense_top) | set(sparse_top))
    dense_raw = [dense_all[i] for i in candidates]
    sparse_raw = [float(sparse_map.get(i, 0.0)) for i in candidates]
    dense_norm = prod_retriever._minmax(dense_raw)
    sparse_norm = prod_retriever._minmax(sparse_raw)

    scored: list[Retrieved] = []
    for pos, i in enumerate(candidates):
        fused = prod_retriever.DENSE_WEIGHT * dense_norm[pos] + prod_retriever.SPARSE_WEIGHT * sparse_norm[pos]
        ranked = fused * (1 + prod_retriever.IMPORTANCE_BOOST * index.chunks[i].importance)
        scored.append(Retrieved(chunk=index.chunks[i], score=ranked, dense=dense_raw[pos], sparse=sparse_raw[pos]))
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored


def retrieve_hybrid(query: str, index: Index, k: int = 5, expanded: str | None = None) -> list[Retrieved]:
    return _hybrid_scored(query, index, k, expanded)[:k]


def retrieve_hybrid_rerank(query: str, index: Index, k: int = 5, expanded: str | None = None) -> list[Retrieved]:
    """Hybrid top-``rerank_candidates`` re-scored by a cross-encoder (production's
    ``hybrid_retrieve(rerank=True)``: candidates = max(k, settings.rerank_candidates))."""
    scored = _hybrid_scored(query, index, k, expanded)
    candidates = scored[: max(k, settings.rerank_candidates)]
    items = [{"text": r.chunk.text, "i": pos} for pos, r in enumerate(candidates)]
    out: list[Retrieved] = []
    for it in reranker.rerank(query, items, k):
        base = candidates[it["i"]]
        out.append(Retrieved(chunk=base.chunk, score=base.score, dense=base.dense, sparse=base.sparse,
                             rerank=it["rerank_score"]))
    return out


_HYDE_CACHE = CACHE_DIR / "hyde.json"
HYDE_MODEL = ""  # Groq model that writes HyDE passages ("" = settings.groq_chat_model)


def hyde_passage(query: str) -> str:
    """HyDE hypothetical passage (``services.query_expansion``), cached on disk.
    Raises if no LLM answers, rather than silently falling back to the raw query."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache: dict[str, str] = json.loads(_HYDE_CACHE.read_text(encoding="utf-8")) if _HYDE_CACHE.exists() else {}
    model = HYDE_MODEL or settings.groq_chat_model
    key = hashlib.sha1(f"{model}|{query}".encode("utf-8")).hexdigest()
    if key not in cache:
        text = ""
        for attempt in range(4):
            time.sleep(1.5)  # stay under per-minute token limits on the free tier
            previous = settings.groq_chat_model
            settings.groq_chat_model = model
            try:
                text = query_expansion.hyde_passage(query)
            finally:
                settings.groq_chat_model = previous
            if text:
                break
            time.sleep(5 * (attempt + 1))
        if not text:
            raise RuntimeError("HyDE expansion returned nothing (no LLM / rate limit); refusing to fake it.")
        cache[key] = text
        _HYDE_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return cache[key]


def retrieve(query: str, index: Index, mode: str = "dense", k: int = 5) -> list[Retrieved]:
    """Modes: ``dense``, ``hybrid``, ``hybrid_rerank``, ``hybrid_hyde``."""
    if mode == "dense":
        return retrieve_dense(query, index, k)
    if mode == "hybrid":
        return retrieve_hybrid(query, index, k)
    if mode == "hybrid_rerank":
        return retrieve_hybrid_rerank(query, index, k)
    if mode == "hybrid_hyde":
        return retrieve_hybrid(query, index, k, expanded=hyde_passage(query))
    raise ValueError(f"unknown retrieval mode {mode!r}")


# --------------------------------------------------------------------------- #
# Stage 5: generate
# --------------------------------------------------------------------------- #
def generate(query: str, retrieved: list[Retrieved]) -> str:
    """Generate a RAG answer via ``llm.generate_answer`` (OpenAI -> Groq ->
    offline extractive fallback, exactly as production). Callers must reject
    answers beginning ``[offline mode]``."""
    return llm.generate_answer(query, [r.chunk.text for r in retrieved], mode="rag")
