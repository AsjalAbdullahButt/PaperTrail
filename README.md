# PaperTrail

A Retrieval-Augmented Generation (RAG) web app. Upload documents; PaperTrail
chunks, embeds, and stores them, then answers questions using **only** the
content of those documents, showing the exact source passages as citations.

> Full setup instructions are completed in Phase 6. This file grows as the
> project is built phase by phase.

## Stack
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind CSS
- **Backend:** Python FastAPI
- **Database:** MySQL (documents, chunks, embeddings, chat history)
- **Vector similarity:** cosine similarity in Python/NumPy over embeddings in MySQL (no separate vector DB)
- **AI:** OpenAI API, wrapped in `backend/app/llm.py` so the provider can be swapped in one place

## Project layout
```
PaperTrail/
├── backend/            FastAPI app + Python venv
│   └── app/
│       ├── main.py     app entry (GET /api/health)
│       ├── config.py   env-driven settings
│       ├── database.py SQLAlchemy engine/session
│       ├── models.py   documents / chunks / chat_history
│       ├── schemas.py  Pydantic request/response models
│       ├── llm.py      single AI service module
│       └── routers/    documents.py, query.py
├── frontend/           Next.js app
├── .gitignore
└── README.md
```
