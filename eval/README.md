# PaperTrail evaluation workstream

**PaperTrail — Evidence-Grounded Research-Paper Question Answering over an NLP Corpus using Hybrid RAG.**
Course category: *RAG Bot for a Niche Domain* (domain: research papers on NLP techniques).

This directory evaluates PaperTrail's RAG pipeline on a corpus of 14 NLP research papers. It is built on top of
the production modules (`backend/app/ingestion.py`, `llm.py`, `similarity.py`, `services/bm25_index.py`,
`services/importance.py`, `services/retriever.py`) — it imports them, it does not fork them — and it never touches
routes, the database, storage or auth.

## Layout

| Path | What it is |
|---|---|
| `dataset/sources.csv` | Curated list of the 14 papers (arXiv id, short name, title, authors, year). |
| `dataset/raw/` | Source PDFs, named `<arxiv_id>.pdf` (git-ignored; re-fetchable). |
| `dataset/*.md` | The cleaned paper texts. Generated and git-ignored: not in the repo until you run `build_dataset.py`. |
| `build_dataset.py` | PDFs → cleaned markdown in `dataset/` + `dataset/manifest.csv` (provenance), using the production extractor. |
| `dataset/manifest.csv` | `doc_id, title, authors, year, arxiv_id_or_url, n_words, n_pages, source_pdf`. |
| `testset.json` | 46 questions (factual / multi-hop / unanswerable) with verbatim evidence quotes. |
| `verify_testset.py` | Checks every evidence quote exists in the corpus and every unanswerable question's key terms are absent. |
| `pipeline.py` | `load → chunk → embed → retrieve (dense / hybrid) → generate`, each a callable stage. |
| `run_eval.py` | Runs the experiment grid, computes all metrics, writes `results/`. |
| `ask.py` | Ask the corpus a question from the CLI (live-demo helper). |
| `results/` | `raw_<config>.csv` per configuration and `run_meta.json`. `run_eval.py` also (re)generates `summary.md` and `tables/*.md` (every metric table) on each run; they are not committed. |

## Setup

```bash
cd backend
python -m venv venv && source venv/Scripts/activate      # Windows Git Bash; see the repo README for other shells
pip install -r requirements-dev.txt                       # includes sentence-transformers (eval-only)
```

### Environment (`backend/.env`)

A submission-grade run needs **real embeddings and a real LLM**:

| Variable | Needed for | Example |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI embeddings (`text-embedding-3-small`), answer generation, LLM judge | `sk-...` (a real key; placeholders are rejected) |
| `GROQ_API_KEY` | *Alternative* generation + judge (no embeddings endpoint) | `gsk_...` |
| `OPENAI_CHAT_MODEL` / `GROQ_CHAT_MODEL` | Optional model override | `gpt-4o-mini` (default) |

Hugging Face embeddings (`sentence-transformers/all-MiniLM-L6-v2`) run locally and need no key. The eval switches
embedder per configuration; `EMBEDDING_PROVIDER` in `.env` only affects the live app and defaults to `openai`.

`--require-online` is **on by default**: `run_eval.py` aborts with a clear message if an OpenAI-embedding configuration
has no valid OpenAI key, if HF embeddings are requested without `sentence-transformers`, if answer generation is requested
with neither an OpenAI nor a Groq key, or if production's silent offline fallback ever produced a wrong-dimension vector or an
`[offline mode]` answer. Pass `--no-require-online` only for debugging; never report those numbers.

## Running

```bash
cd eval
python build_dataset.py --download     # fetch PDFs by arXiv id (skip --download if dataset/raw/ already has them) and build the corpus .md files + manifest
python verify_testset.py               # sanity-check the test set against the corpus
python run_eval.py                     # full grid: 10 configurations, retrieval + generation + judge
```

Useful variations:

```bash
python run_eval.py --no-generate                                  # retrieval metrics only (HF configs need no API key)
python run_eval.py --configs character__hybrid__hf --limit 5      # quick smoke test
python ask.py --embedder hf --retrieval-only "What is MaxSim?"    # interactive query
```

Embeddings and LLM outputs are cached in `eval/.cache/` (git-ignored), so interrupted runs resume and re-runs are cheap.
Delete the folder to force fresh calls.

## Experiment grid

A configuration is `chunker__retrieval__embedder`:

* chunker: `character` (legacy 800-char windows), `sentence` (production default sentence chunker, ~3,000 chars),
  `sentence800` (the same sentence chunker capped at ~800 chars — the size-controlled variant);
* retrieval: `dense` (cosine only) or `hybrid` (production fusion: 0.6 dense + 0.4 BM25, × (1 + 0.2 · importance));
* embedder: `openai` or `hf`. HF MiniLM truncates input at 256 word-pieces, so it is only paired with the ~800-char chunkers.

## Metrics

* **Doc Recall@5** — fraction of the gold source papers that appear among the top-5 chunks (answerable questions).
* **Evidence Recall@5 / MRR** — whether a retrieved chunk actually contains the supporting passage (the verbatim quote, or an
  `any_of` phrase for facts the paper states in more than one place). This is stricter and more honest than Doc Recall.
* **Section hit** — a retrieved chunk carries the gold section heading (best-effort: headings are heuristically detected in PDFs).
* **Correctness / Faithfulness / Relevance** — LLM-as-judge, 1–5, one structured call per answer (`manual_score` column left blank for the human grader).
* **Citation accuracy** — of the `[n]` passages an answer cites, the fraction that contain gold evidence; *coverage* — fraction of answers that cite at all.
* **Unanswerable handling** — fraction of unanswerable questions on which the system abstains (judge verdict, cross-checked with a regex).
* **Guard rate** — fraction of answer sentences the lexical hallucination heuristic flags; correlated against judged faithfulness.

All intervals are bootstrap 95% CIs over questions; comparisons use paired bootstrap on per-question differences.

## Documented deviations from production

1. `retrieve_hybrid` re-implements `services/retriever.hybrid_retrieve`'s *scoring* on in-memory arrays because the production function is bound to SQLAlchemy sessions and per-user caches. Weights, the importance multiplier and `_minmax` are imported from the production module so they cannot drift. Dense candidates use exact cosine instead of production's approximate USearch/KD-tree index.
2. Sections: production PDF extraction yields one block per page and no headings; `build_dataset.py` adds heading detection and page markers when writing the markdown corpus.
3. References sections are stripped from the corpus (bibliographic noise for lexical matching).
4. Generator and judge are the same model family by default, so LLM-judge scores can be biased towards the generator's own style; treat them as relative, not absolute.
