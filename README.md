# PaperTrail

A Retrieval-Augmented Generation (RAG) web app. Upload documents; PaperTrail
chunks, embeds, and stores them, then answers questions using **only** the
content of those documents — showing the exact source passages as inline
citations, with a relevance score for each source.

![tech](https://img.shields.io/badge/stack-Next.js%20%2B%20FastAPI%20%2B%20MySQL-informational)

## Features
- Upload `.pdf`, `.txt`, `.md` documents → automatic text extraction, chunking, and embedding.
- **RAG mode:** answers grounded in your documents, with ranked source citations `[1] [2] [3]` and per-source relevance meters.
- **Direct mode:** ask the model directly, no retrieval.
- Faithful glassmorphism UI with dark/light themes, animated ambient background, and Plus Jakarta Sans.
- Every exchange saved to chat history.

## Stack
- **Frontend:** Next.js 16 (App Router) + TypeScript + Tailwind CSS
- **Backend:** Python FastAPI
- **Database:** MySQL 8 (documents, chunks, embeddings, chat history)
- **Vector similarity:** cosine similarity in Python/NumPy over embeddings stored in MySQL (no separate vector DB)
- **AI:** OpenAI API (`text-embedding-3-small` + a small chat model), wrapped in `backend/app/llm.py` so the provider can be swapped in one place

> **No OpenAI key? It still runs.** `llm.py` has a deterministic **offline fallback**
> (hashing embeddings + extractive answers) that activates automatically when no valid
> `OPENAI_API_KEY` is set. Retrieval, ranking, citations, and scoring are fully real
> in both modes; only the final answer wording differs. Add a real `sk-...` key to
> switch to OpenAI with zero code changes.

---

## Prerequisites
- **Python 3.11+** (tested on 3.14)
- **Node.js 20+** (tested on 24) and npm
- **MySQL 8.0+** running locally

Verify:
```bash
python --version
node --version
mysql --version
```

---

## 1. Clone & configure environment

### Backend `.env`
```bash
cd backend
cp .env.example .env
```
Edit `backend/.env`:
```ini
# OpenAI (optional — leave the placeholder to run in offline mode)
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini

# MySQL — use the dedicated app user created below (not root)
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=papertrail
DB_PASSWORD=change-me-strong-password
DB_NAME=papertrail
```

### Frontend `.env.local`
```bash
cd ../frontend
cp .env.example .env.local   # contains NEXT_PUBLIC_API_URL=http://localhost:8000
```

> `.env` files are gitignored. Never commit real secrets.

---

## 2. Create the MySQL database + a dedicated user

Connect as root once and create a least-privilege user scoped to the
`papertrail` database (recommended over using root in the app):

```sql
-- mysql -u root -p
CREATE DATABASE IF NOT EXISTS papertrail
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'papertrail'@'localhost'
  IDENTIFIED BY 'change-me-strong-password';

GRANT ALL PRIVILEGES ON papertrail.* TO 'papertrail'@'localhost';
FLUSH PRIVILEGES;
```

Use the same username/password in `backend/.env`. The app also auto-creates
the database and tables on startup if they don't exist.

---

## 3. Run the backend

```bash
cd backend
python -m venv venv

# Activate the venv:
#   Windows (PowerShell): .\venv\Scripts\Activate.ps1
#   Windows (Git Bash):   source venv/Scripts/activate
#   macOS/Linux:          source venv/bin/activate

pip install -r requirements.txt

# (Optional) create tables explicitly:
python create_tables.py

# Start the API on port 8000:
uvicorn app.main:app --reload --port 8000
```

Check it: <http://localhost:8000/api/health> → `{"status":"ok"}`
Interactive API docs: <http://localhost:8000/docs>

---

## 4. Run the frontend

In a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open <http://localhost:3000>.

---

## 5. Use it
1. Click **Upload document**, choose a `.pdf`, `.txt`, or `.md` file.
2. Type a question (or click a suggestion) and press **Ask** / Enter.
3. In **RAG mode** you get an answer with inline citation chips and a Sources
   panel (score + relevance meter). Toggle **Direct mode** for a no-retrieval answer.

---

## Tests
```bash
cd backend
source venv/Scripts/activate        # or the activation command for your OS
pip install -r requirements-dev.txt
pytest -q
```
Covers the chunking function, cosine similarity, and the `/api/health` route.
(The health test runs without a database.)

---

## Project layout
```
PaperTrail/
├── backend/
│   ├── app/
│   │   ├── main.py         FastAPI app: /api/health, routers, startup schema init
│   │   ├── config.py       env-driven settings (pydantic-settings)
│   │   ├── database.py     SQLAlchemy engine/session + schema bootstrap
│   │   ├── models.py       documents / chunks / chat_history
│   │   ├── schemas.py      Pydantic request/response models
│   │   ├── llm.py          single AI service (OpenAI + offline fallback)
│   │   ├── ingestion.py    text extraction + chunking
│   │   ├── similarity.py   cosine similarity (pure functions)
│   │   └── routers/
│   │       ├── documents.py  upload / list / delete
│   │       └── query.py       RAG + direct query
│   ├── tests/              pytest suite
│   ├── create_tables.py    standalone schema bootstrap
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── .env.example
├── frontend/
│   ├── src/app/            layout.tsx, page.tsx, globals.css
│   ├── src/lib/api.ts      backend API client
│   └── .env.example
├── .gitignore
└── README.md
```

## API reference
| Method | Path | Body | Purpose |
|---|---|---|---|
| GET | `/api/health` | — | Liveness check |
| POST | `/api/documents/upload` | multipart `file` | Ingest a document |
| GET | `/api/documents` | — | List documents + chunk counts |
| DELETE | `/api/documents/{id}` | — | Delete a document (cascades chunks) |
| POST | `/api/query` | `{ question, mode }` | RAG or direct answer |
