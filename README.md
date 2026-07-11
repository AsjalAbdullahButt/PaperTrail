<div align="center">

# 📄 PaperTrail

**Ask your documents anything — get answers you can trace back to the source.**

Upload PDFs, Word docs, spreadsheets, or text files. PaperTrail chunks, embeds, and indexes them, then answers your questions using **only** the content of those documents — with inline citations, per-source relevance scores, and a confidence rating on every answer.

[![CI](https://github.com/AsjalAbdullahButt/PaperTrail/actions/workflows/ci.yml/badge.svg)](https://github.com/AsjalAbdullahButt/PaperTrail/actions/workflows/ci.yml)
![stack](https://img.shields.io/badge/frontend-Next.js%2016%20%2B%20TypeScript-000000?logo=nextdotjs&logoColor=white)
![stack](https://img.shields.io/badge/backend-FastAPI%20%2B%20Python-009688?logo=fastapi&logoColor=white)
![stack](https://img.shields.io/badge/database-MySQL%208-4479A1?logo=mysql&logoColor=white)
![stack](https://img.shields.io/badge/cache-Redis-DC382D?logo=redis&logoColor=white)

</div>

---

## ✨ What it does

- 🔍 **Retrieval-Augmented Generation (RAG)** — answers are grounded in the exact passages retrieved from your documents, cited inline as `[1] [2] [3]`.
- 🧩 **Multi-hop mode** — chains two retrieval rounds together (refining the search from what it finds) to answer questions that need connecting facts across documents.
- 💬 **Direct mode** — skip retrieval entirely and ask the model directly.
- 🛡️ **Hallucination guard** — every answer is checked sentence-by-sentence against the retrieved evidence; unsupported claims are flagged.
- 🎯 **Hybrid search** — dense (embedding/ANN) similarity fused with BM25 keyword search and a learned importance boost, so both "meaning" and exact-keyword queries work well.
- 🗂️ **Document management** — collections, tags, duplicate detection, per-document coverage heatmaps, and an auto-extracted event timeline.
- 🧠 **Concept mind maps** — every answer can be visualized as a graph of the question and the chunks that informed it.
- 📊 **Analytics dashboard** — query volume, top questions, per-document usage, and coverage gaps (which parts of your library never get retrieved).
- 🔗 **Share & export** — download a grounded answer as a PDF, generate a public read-only share link, or export your full account data as a ZIP.
- 🔐 **Real auth** — JWT access tokens + rotating httpOnly refresh tokens with theft detection, password reset, avatar upload, and account deletion.
- 🌓 **Polished UI** — glassmorphism design system with dark/light themes, a command palette (`Ctrl+K`), and full keyboard shortcuts.
- 🧪 **Offline-friendly** — no API key? PaperTrail falls back to a deterministic offline embedder + extractive answers automatically, so the whole pipeline still runs end-to-end for local development and testing.

---

## 🏗️ Architecture

| Layer | Technology |
| --- | --- |
| **Frontend** | Next.js 16 (App Router) + TypeScript, hand-authored CSS-variable theme system |
| **Backend** | Python + FastAPI |
| **Database** | MySQL 8 (documents, chunks, embeddings, chat history, collections, users) via SQLAlchemy + Alembic migrations |
| **Cache / rate limiting** | Redis (shared across workers); falls back to in-process memory for single-worker/local dev |
| **Retrieval** | Dense ANN (usearch, with a KD-tree fallback) + BM25 sparse index, fused and importance-boosted, cached per user |
| **AI** | OpenAI (`text-embedding-3-small` + a chat model) or Groq, wrapped in a single-module provider layer (`backend/app/llm.py`) so the provider can be swapped without touching the rest of the app |

```text
                    ┌──────────────┐
            users → │ Load balancer│
                    └──────┬───────┘
                  ┌────────┼─────────┐
                  ▼        ▼         ▼
             ┌────────┐┌────────┐┌────────┐   stateless API workers
             │uvicorn ││uvicorn ││uvicorn │   (gunicorn -k UvicornWorker)
             └───┬────┘└───┬────┘└───┬────┘
                 └─────────┼─────────┘
                  ┌────────┴────────┐
                  ▼                 ▼
             ┌─────────┐       ┌─────────┐
             │  MySQL  │       │  Redis  │   shared state
             └─────────┘       └─────────┘
```

The API tier is stateless — auth is JWT (no sticky sessions), and rate limits / query cache live in Redis when configured, so it scales horizontally by adding workers.

> ⚠️ **Known scaling limit:** retrieval currently does an in-memory cosine/BM25 scan over each user's chunks, bounded by `MAX_QUERY_CHUNKS`. This is fine up to a few thousand chunks per user; a larger corpus needs a real vector database (pgvector, Qdrant, Weaviate, Pinecone) in front of it. This is the single biggest architectural item on the roadmap.

---

## 🚀 Quick start

### Option A — Docker Compose (fastest)

```bash
docker compose up --build
```

Spins up MySQL, Redis, the backend (`:8000`), and the frontend (`:3000`) together. Override secrets via a `.env` file at the repo root (`DB_PASSWORD`, `JWT_SECRET`, `MYSQL_ROOT_PASSWORD`) — see `docker-compose.yml`.

### Option B — Run locally

**Prerequisites:** Python 3.11+, Node.js 20+, MySQL 8.0+.

```bash
python --version
node --version
mysql --version
```

#### 1. Configure environment

```bash
cd backend && cp .env.example .env      # edit DB_*, JWT_SECRET, and (optionally) OPENAI_API_KEY
cd ../frontend && cp .env.example .env.local
```

> `.env*` files are gitignored — never commit real secrets. No `OPENAI_API_KEY`? PaperTrail runs fine in offline mode (see [What it does](#-what-it-does)).

#### 2. Create the database

```sql
CREATE DATABASE IF NOT EXISTS papertrail CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'papertrail'@'localhost' IDENTIFIED BY 'change-me-strong-password';
GRANT ALL PRIVILEGES ON papertrail.* TO 'papertrail'@'localhost';
FLUSH PRIVILEGES;
```

#### 3. Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate      # Windows Git Bash — see below for other shells
pip install -r requirements.txt
alembic upgrade head              # or: python create_tables.py
uvicorn app.main:app --reload --port 8000
```

<details>
<summary>Venv activation on other shells</summary>

- Windows PowerShell: `.\venv\Scripts\Activate.ps1`
- macOS/Linux: `source venv/bin/activate`

</details>

Check it: <http://localhost:8000/api/health> → `{"status":"ok"}` · Interactive API docs: <http://localhost:8000/docs>

#### 4. Frontend (second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>, register an account, upload a document, and ask it something.

**Or, on Windows, just double-click / run `start-dev.ps1`** — it launches both servers in their own terminal windows.

---

## ⚙️ Configuration

All settings are environment-driven — see `backend/.env.example` and `frontend/.env.example` for the full list with descriptions. The essentials:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` / `GROQ_API_KEY` | Enable hosted embeddings/generation (optional — offline fallback works without either) |
| `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | MySQL connection |
| `JWT_SECRET` | **Must** be a long random value in production (`openssl rand -hex 32`) |
| `REDIS_URL` | Set for multi-worker correctness (shared cache + rate limits); omit for single-worker/local dev |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |
| `NEXT_PUBLIC_API_URL` | Frontend → backend base URL (baked in at build time) |

---

## 🧪 Testing

```bash
# Backend — 181 tests covering auth, retrieval, ingestion, sharing, rate limits, and more
cd backend
pip install -r requirements-dev.txt
pytest -q

# Frontend — component tests (Vitest) + lint + type-check
cd frontend
npm run test
npm run lint
npx tsc --noEmit

# Frontend — end-to-end (needs a live backend + `npx playwright install`)
npm run test:e2e
```

CI (`.github/workflows/ci.yml`) runs the backend suite against a real MySQL service container (including `alembic upgrade head`) and the frontend lint/build/test steps on every push and pull request.

---

## 📦 Deployment & operations

<details>
<summary><strong>Expand for horizontal scaling, backups, and observability notes</strong></summary>

### Horizontal scaling

Run N workers (`gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w <cores*2+1>`) or N containers behind a load balancer — the API tier holds no local state. Keep:

```text
workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW) < MySQL max_connections
```

### Observability

- **Liveness:** `GET /api/health/live` (also `/api/health`)
- **Readiness:** `GET /api/health/ready` — 200 only when MySQL (and Redis, if configured) answer; wire this to your load balancer
- **Metrics:** `GET /metrics` (Prometheus) — request latency histogram, counts by status, 5xx counter
- **Logs:** structured JSON, one object per line, correlated by `request_id` (also returned as the `X-Request-ID` response header)

### Backups (MySQL)

```bash
mysqldump --single-transaction --routines --triggers papertrail | gzip > papertrail-$(date +%F-%H%M).sql.gz
```

Recommended cadence: hourly logical dumps retained 7 days + daily dumps retained 30 days, shipped off-box. Restore:

```bash
gunzip < papertrail-YYYY-MM-DD-HHMM.sql.gz | mysql papertrail
alembic upgrade head
```

| Metric | Target |
| --- | --- |
| RPO (max data loss) | ≤ 1 hour (hourly dumps; ≤ 5 min with binlog PITR) |
| RTO (time to restore) | ≤ 1 hour (single restore + migration) |

Redis holds only cache + rate-limit counters — no backup needed, a cold Redis simply repopulates.

### Production checklist

Set `JWT_SECRET` (long random), real `DB_*` credentials, `CORS_ORIGINS`, and `REDIS_URL`. The app refuses to start if `COOKIE_SECURE=true` is set alongside the default insecure `JWT_SECRET`.

</details>

---

## 📁 Project layout

```text
PaperTrail/
├── backend/
│   ├── app/
│   │   ├── main.py           FastAPI app, middleware, router registration
│   │   ├── config.py         env-driven settings (pydantic-settings)
│   │   ├── database.py       SQLAlchemy engine/session + schema bootstrap
│   │   ├── models.py         users, documents, chunks, chat history, collections…
│   │   ├── schemas.py        Pydantic request/response models
│   │   ├── llm.py            single AI provider layer (OpenAI/Groq + offline fallback)
│   │   ├── auth.py           JWT auth dependency
│   │   ├── ingestion.py      text extraction + chunking helpers
│   │   ├── services/         retrieval, multi-hop, follow-ups, hallucination guard,
│   │   │                     importance scoring, outline/timeline extraction
│   │   └── routers/          auth, documents, query, queries, collections,
│   │                         chat_history, analytics, export, share
│   ├── tests/                pytest suite (181 tests)
│   ├── migrations/           Alembic schema migrations
│   └── create_tables.py      standalone schema bootstrap
├── frontend/
│   ├── src/app/               pages (App Router)
│   ├── src/components/        UI components
│   ├── src/lib/api.ts         typed backend API client
│   ├── src/hooks/, src/stores/
│   └── e2e/                   Playwright end-to-end tests
├── docker-compose.yml         MySQL + Redis + backend + frontend, prod-parity
├── start-dev.ps1              one-click local dev launcher (Windows)
└── .github/workflows/ci.yml   backend + frontend CI
```

---

## 🤝 Contributing

Issues and pull requests are welcome. Please make sure `pytest -q` (backend) and `npm run lint && npm run test && npm run build` (frontend) all pass before opening a PR — CI enforces the same.
