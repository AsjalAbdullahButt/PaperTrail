# PaperTrail Architecture Overview

## What PaperTrail is

PaperTrail is a retrieval-augmented generation (RAG) document question-answering system. A user uploads documents, the system extracts and chunks their text, embeds the chunks, and indexes them. When the user asks a question, PaperTrail retrieves the most relevant chunks and asks a language model to answer strictly from that retrieved evidence, citing which passage each claim came from.

## Technology stack

The frontend is built with Next.js 16 using the App Router and TypeScript, styled with a hand-authored CSS-variable theme system rather than a component library. The backend is written in Python using the FastAPI framework. Persistent data — documents, chunks, embeddings, chat history, collections, and user accounts — is stored in a MySQL 8 database, accessed through SQLAlchemy with Alembic managing schema migrations. Redis provides a shared cache and rate-limiting store across multiple API workers; when no Redis URL is configured, the application falls back to in-process memory, which is only correct for a single worker.

Retrieval combines a dense approximate-nearest-neighbor index (backed by the `usearch` library, with a KD-tree fallback when `usearch` is unavailable) with a sparse BM25 keyword index, fused together and boosted by a learned importance score. All embedding and text-generation calls are isolated in a single module, `backend/app/llm.py`, so the underlying AI provider can be swapped by editing only that one file.

## Layered request flow

Client requests reach a load balancer, which distributes them across several stateless `uvicorn` worker processes managed by `gunicorn`. Because no worker holds session state locally — authentication uses JSON Web Tokens rather than server-side sessions — any worker can serve any request. Workers share two backing stores: the MySQL database for durable state, and Redis for the query-response cache and rate-limit counters. This design lets the API tier scale horizontally by adding more worker processes or containers, since there is no sticky-session requirement.

## The single biggest architectural limitation

Retrieval currently performs an in-memory cosine-similarity and BM25 scan over each user's own chunks, bounded by a configuration ceiling called `MAX_QUERY_CHUNKS` (default 5000). This approach is fine for up to a few thousand chunks per user, but it does not scale to a very large corpus. The documented plan for scaling further is to introduce a dedicated vector database such as pgvector, Qdrant, Weaviate, or Pinecone in front of retrieval. This is called out explicitly as the single biggest item on PaperTrail's architectural roadmap.

## Project layout

The backend's application code lives under `backend/app/`. Its `main.py` wires up the FastAPI app and registers routers; `config.py` loads all environment-driven settings through `pydantic-settings`; `database.py` sets up the SQLAlchemy engine and session; `models.py` defines the ORM models for users, documents, chunks, chat history, and collections; `llm.py` is the single AI provider layer; `auth.py` implements the JWT auth dependency; and `ingestion.py` holds the text-extraction and chunking helpers. Two subdirectories hold more specialized logic: `services/` (retrieval, multi-hop search, follow-up question generation, the hallucination guard, importance scoring, and outline/timeline extraction) and `routers/` (auth, documents, query, queries, collections, chat history, analytics, export, and share).

The backend's test suite lives in `backend/tests/` and covers 181 tests spanning authentication, retrieval, ingestion, sharing, and rate limiting, among other areas. The frontend lives under `frontend/src/`, with pages under `src/app/`, UI components under `src/components/`, a typed API client at `src/lib/api.ts`, and Playwright end-to-end tests under `frontend/e2e/`.

## Offline-friendly design

When no OpenAI (or Groq) API key is configured, PaperTrail does not fail — it transparently falls back to a deterministic offline embedder (a hashing-based bag-of-words vectorizer) and an extractive offline answer generator. This means the full RAG pipeline — ingestion, chunking, embedding, retrieval, and answer generation — runs end to end, and is fully testable, without requiring a paid API key. Dropping a real API key into the backend's `.env` file switches the system over to the hosted provider transparently, with no code changes required.
