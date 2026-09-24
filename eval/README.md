# PaperTrail Eval Workstream

A standalone course-assignment evaluation of PaperTrail's RAG pipeline,
built on top of (not forked from) the production `backend/app/llm.py`,
`ingestion.py`, and `similarity.py` modules. This directory does not touch
any live route, the database, storage, or auth — it only needs Python and
the backend's existing dependencies.

## Layout

- `dataset/` — 10 original Markdown documents (the fixed domain corpus:
  PaperTrail's own architecture/ingestion/retrieval/deployment docs).
- `pipeline.py` — `load_documents` / `chunk` / `embed` / `retrieve` /
  `generate`, each a standalone function reusing production code.
- `testset.json` — 20 hand-written question/answer pairs with source
  document + section provenance.
- `run_eval.py` — runs the full pipeline for both chunking strategies
  ("character" vs "sentence") against every test question, scores answers
  with an LLM-as-judge pass, and writes results to `results/`.
- `results/` — `raw_character.csv`, `raw_sentence.csv` (per-question detail,
  including a blank `manual_score` column for hand-grading), `summary.md`
  (aggregate hit rates + disagreement examples).
- `chunking_comparison.md` — the Task 5 ablation writeup.
- `REPORT.md` — the full course report (Tasks 1, 3-8).

## Running it

```bash
cd backend
python -m venv venv            # if not already created
source venv/Scripts/activate   # Windows Git Bash; see repo README for other shells
pip install -r requirements.txt

cd ../eval
python run_eval.py
```

No `OPENAI_API_KEY` required — without one, `run_eval.py` runs entirely
through PaperTrail's own offline fallback path (deterministic hashing
embeddings + extractive answers, and the LLM-judge columns come back as
`n/a (offline)`). Add a real `OPENAI_API_KEY` (or `GROQ_API_KEY` for
generation only) to `backend/.env` to get real embeddings, real generated
answers, and real judge scores — no code changes needed, since this harness
calls the exact same `llm.py` functions production does.
