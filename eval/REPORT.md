# PaperTrail RAG Evaluation — Course Report

## 1. Problem statement and chosen domain

This report evaluates the retrieval-augmented generation (RAG) pipeline that
underlies PaperTrail, an existing production document-QA application, on a
**fixed, domain-specific document set** rather than the open-ended "any
document a user might upload" framing the live product supports. The chosen
domain is PaperTrail's own technical documentation: its architecture,
ingestion and chunking pipeline, hybrid retrieval, LLM provider layer,
multi-hop retrieval, hallucination guard, authentication, deployment
topology, and operations. This domain was chosen deliberately over sourcing
external documents: it lets every fact in the corpus be independently
verified against the actual source code (`backend/app/`) rather than trusted
at face value, and it avoids any copyright or web-scraping question entirely
around dataset sourcing. The system being evaluated (PaperTrail's chunking,
embedding, retrieval, and generation code) is now, in this specific
assignment, also the *subject* of the documents it is asked to answer
questions about — a coincidence of scope, not the point of the exercise.

## 2. Dataset description

`eval/dataset/` contains 10 original Markdown documents (roughly 1,200-2,000
words / 7,000-12,000 characters each), authored specifically for this
assignment and organized under clear `#`/`##` headings:

1. Architecture Overview
2. Document Ingestion and Chunking
3. Hybrid Retrieval and Ranking
4. The LLM Provider Layer and Generation Modes
5. Multi-Hop Retrieval and the Hallucination Guard
6. Authentication and Session Management
7. Deployment Topology
8. Production Environment Variables
9. Observability, Health Checks, and Backups
10. Rate Limiting, Caching, and Testing

Every factual claim in these documents was checked directly against the
current state of `backend/app/` (specifically `llm.py`, `ingestion.py`,
`similarity.py`, `config.py`, `services/retriever.py`,
`services/multihop.py`, `services/hallucination_guard.py`,
`services/importance.py`) and against `README.md`, `DEPLOY_BLUEPRINT.md`, and
`backend/DEPLOYMENT.md`. No cleaning was required (no scanned pages, no
broken PDF text layers) because the documents were authored as clean
Markdown rather than converted from another format.

One intentional feature of the corpus: documents 08 and 10 state two
genuinely different numbers for the same setting (`RATE_LIMIT_QUERY` — the
production deployment guidance suggests `60/minute`; the application's actual
internal default is `20/minute`). This mirrors a real discrepancy between
`backend/DEPLOYMENT.md` and `backend/app/config.py`, and is used as a
deliberately hard, cross-document test question (`q20`).

## 3. Pipeline architecture

`eval/pipeline.py` exposes each RAG stage as a separately callable function,
built on top of production code rather than a fork of it:

- `load_documents()` — reads every `.md` file in `eval/dataset/`.
- `chunk(documents, strategy)` — dispatches to `chunk_character` or
  `chunk_sentence`, which call `backend/app/ingestion.py`'s real
  `chunk_blocks` (character-window) and `chunk_blocks_semantic`
  (sentence-boundary) functions directly, at their real production defaults.
  A lightweight Markdown-to-"blocks" adapter (`_markdown_to_blocks`) is the
  only new code — it exists because production's blocks carry page/heading
  provenance that a raw `.md` file doesn't have out of the box.
- `embed(chunks)` — calls `backend/app/llm.py`'s `embed_texts` (OpenAI
  `text-embedding-3-small`, or the offline deterministic hashing fallback).
- `retrieve(query, index, k)` — embeds the query and ranks chunks with
  `backend/app/similarity.py`'s real `top_k_by_similarity` (cosine
  similarity), the same function production's retriever uses for its dense
  score.
- `generate(query, retrieved)` — calls `llm.py`'s `generate_answer` in RAG
  mode (OpenAI -> Groq -> offline extractive fallback).

**Gap, explicitly noted:** retrieval here is dense-only cosine similarity,
not production's full hybrid fusion (dense + BM25 + importance boost,
`services/retriever.py`). The assignment's Task 2 asks for a `retrieve(query,
k)` stage function reusing `llm.py`, which this does; reproducing the full
hybrid fusion would additionally require standing up production's BM25 index
and importance scorer outside the database-backed retriever they're wired
into. Documented here as a scope cut, not an oversight — see Limitations.

**Gap, explicitly noted:** Task 2's optional LangChain `RetrievalQA`-style
wrap was skipped due to time. The five stages above are documented explicitly
as a linear pipeline instead (`load -> chunk -> embed -> retrieve ->
generate`), per the assignment's own fallback instruction for this step.

## 4. Evaluation methodology

`eval/testset.json` contains 20 hand-written question/answer pairs, each
naming its exact source document and source section, written directly from
the dataset documents in section 2 (not generated by the LLM being
evaluated, to avoid a circular evaluation). `eval/run_eval.py` runs the full
pipeline for both chunking strategies against all 20 questions and records,
per question: the retrieved chunk IDs and their source documents, a
doc-level retrieval hit (correct source document in the top-5), a
section-level hit (correct document *and* matching section heading — a
stricter measure), the generated answer, an LLM-as-judge faithfulness score
(1-5), an LLM-as-judge relevance score (1-5), and a blank `manual_score`
column for a human grader to fill in with correct/partially
correct/incorrect. Results are written to `results/raw_character.csv`,
`results/raw_sentence.csv`, and aggregated into `results/summary.md`.

## 5. Results

See `chunking_comparison.md` for the full ablation with worked failure
examples. Headline numbers from the run committed alongside this report:

| Strategy | Doc-level hit rate | Section-level hit rate | Avg faithfulness | Avg relevance |
|---|---|---|---|---|
| character | 95% (19/20) | 65% (13/20) | n/a (offline) | n/a (offline) |
| sentence | 90% (18/20) | 25% (5/20) | n/a (offline) | n/a (offline) |

Character chunking matched sentence chunking on document-level retrieval and
substantially outperformed it on section-level precision, because
production's sentence-boundary strategy uses a ~4x larger default chunk
budget (~3,200 characters vs. 800), which bundles more of each document's
headings into a single chunk and coarsens the section label attached to it.

## 6. Failure analysis

Worked examples (full detail in `chunking_comparison.md`):

- **q05** (doc-level miss under sentence chunking): the correct document's
  content was compressed into just 2 large sentence-based chunks, diluting
  the specific "usearch/cKDTree fallback" signal enough for smaller,
  more topically concentrated chunks from unrelated documents to outrank it.
- **q01, q04, q06** and five more (section-level misses under sentence
  chunking despite a correct document hit): a single oversized chunk spans
  multiple original headings, so the section label attached to it (taken
  from wherever the chunk *starts*) doesn't match the specific section a
  fine-grained question is asking about, even though the retrieved text
  itself contains the answer.

## 7. Embedding model note (Task 6)

PaperTrail uses OpenAI's `text-embedding-3-small` in production rather than a
self-hosted Hugging Face model (e.g. `sentence-transformers/all-MiniLM-L6-v2`).
Trade-offs:

- **Cost.** `text-embedding-3-small` is priced per token with no
  infrastructure to run or maintain; a self-hosted HF model has zero
  per-call cost but requires either a GPU/CPU host running continuously or a
  serverless inference endpoint, which shifts cost from "per query" to
  "per hour of uptime" — cheaper at high, steady volume, more expensive at
  PaperTrail's bursty, per-user query pattern (and the offline fallback in
  `llm.py` needs no model or inference cost at all).
- **Quality.** OpenAI's embedding models are trained on a broader and more
  recent corpus than most freely available small HF sentence-embedding
  models, and empirically rank well on retrieval benchmarks (e.g. MTEB)
  relative to models of comparable dimensionality. `all-MiniLM-L6-v2`, by
  contrast, is a much smaller (22M-parameter) model — fast and
  cheap to self-host, but generally lower recall on out-of-domain text than
  a larger hosted model.
- **Latency.** Self-hosting removes a network round trip to a third-party
  API, which can be faster for high-throughput batch embedding on adequate
  local hardware — but adds cold-start latency if the serving infrastructure
  scales to zero, which a hosted API never does.
- **Why OpenAI won for PaperTrail specifically:** the product already
  isolates every AI call in one module (`llm.py`) specifically so the
  provider is swappable, and it already has a working offline fallback for
  when no API key is configured at all — so the marginal cost of *not*
  self-hosting is low (an operator without an API key still gets a fully
  functional, if lower-quality, pipeline for free), while the marginal
  complexity of adding and maintaining a self-hosted inference service for
  every deployment would be a meaningful new operational burden for what is,
  at PaperTrail's current scale, a bursty low-to-moderate query volume.

**Gap, explicitly noted:** running `all-MiniLM-L6-v2` through this same
harness as a bonus comparison row was skipped due to time — see Limitations.

## 8. Limitations and what a larger eval would change

- **No hosted API key configured in this environment.** `OPENAI_API_KEY`/
  `GROQ_API_KEY` are both unset, so this run used PaperTrail's own offline
  fallback path end to end: deterministic hashing embeddings (not real
  semantic embeddings) and extractive (not generative) answers. This is the
  same code path production falls back to, so the pipeline mechanics are
  faithfully tested, but the *retrieval quality* and *answer quality*
  numbers above should be read as a lower bound, not a representative
  result for the hosted configuration. Re-running `python run_eval.py` with
  a real key in `backend/.env` requires no code changes and would produce
  real embedding-based retrieval, real generated answers, and real
  LLM-as-judge faithfulness/relevance scores in place of the `n/a` values
  currently in `results/summary.md`.
- **Dense-only retrieval, not full hybrid.** As noted in section 3, this
  harness reuses `llm.py`'s embeddings and `similarity.py`'s cosine ranking
  but does not reproduce production's BM25 fusion or importance boost. A
  fuller evaluation would stand up `services/bm25_index.py` and
  `services/importance.py` outside their current database-backed retriever
  to measure the fused hybrid score's effect on hit rate directly.
- **No LangChain `RetrievalQA` wrap** (Task 2's optional step) — skipped for
  time; the five pipeline stages are documented explicitly instead.
- **No Hugging Face embedding comparison row** (Task 6's bonus) — skipped
  for time; section 7 gives a qualitative justification only.
- **Chunk-size confound in the ablation.** As detailed in
  `chunking_comparison.md`, the two chunking strategies differ in default
  chunk size by roughly 4x, which confounds "sentence-boundary alignment"
  with "chunk size" as explanations for the section-level hit-rate gap. A
  fine-tuned or larger eval set — and a controlled re-run holding chunk size
  constant between strategies — would be needed to attribute the effect
  correctly.
- **Small test set (20 questions, 10 documents).** Large enough to surface a
  real, explainable pattern (the section-level attribution gap) but too
  small to produce statistically stable hit-rate percentages; a production
  evaluation would want at least 100+ questions and a held-out document set
  the question-writer didn't also help author, to reduce authoring bias
  toward passages that are "easy" to write a clean question about.

## Supporting engineering context

PaperTrail is deployed in production (Next.js frontend on Vercel, FastAPI
backend on Render, MySQL on Aiven, Cloudflare R2 storage) and this
evaluation runs entirely independently of that deployment — see `eval/README.md`
for how to run it standalone. That context is included here only because the
pipeline code under test (`llm.py`, `ingestion.py`, `similarity.py`) is the
same code the live app runs, not because this report is about the product.
