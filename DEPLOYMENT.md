# PaperTrail — Deployment & Operations

## Architecture at a glance

```
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

## Horizontal scaling

The API tier is **stateless** and scales horizontally: run N workers
(`gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w <cores*2+1>`), or N
containers behind a load balancer. All shared state lives in MySQL and Redis:

- **Auth** is stateless JWT — any worker can validate any request; no sticky
  sessions required.
- **Rate limiting** and the **query cache** use Redis when `REDIS_URL` is set,
  so limits and cache hits are shared across all workers. Without Redis they
  fall back to per-process memory, which is only correct for a single worker.
- **Uploads/queries** persist to MySQL; no local disk state.

### ⚠️ The similarity search does NOT scale by itself

RAG retrieval currently computes cosine similarity in NumPy over **every chunk**
belonging to the user, on **every query** (`app/routers/query.py`). Adding API
workers does not help — each worker still scans every chunk. This is bounded by
`MAX_QUERY_CHUNKS` to avoid OOM, but it is O(chunks) per query and will not go
beyond a small corpus (a few thousand chunks). **To scale the corpus, replace
the in-memory scan with a real ANN/vector index** (pgvector, Qdrant, Weaviate,
Pinecone). That is the single biggest architectural limitation.

### Connection pool sizing

Each worker keeps its own SQLAlchemy pool (`DB_POOL_SIZE` persistent +
`DB_MAX_OVERFLOW` burst). Keep:

```
workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW)  <  MySQL max_connections
```

Defaults (10 + 20) × 4 workers = 120 connections/instance — tune both sides for
your instance count and MySQL `max_connections`.

## Observability

- **Liveness:** `GET /api/health/live` (also `/api/health`) — process up.
- **Readiness:** `GET /api/health/ready` — 200 only when MySQL (and Redis, if
  configured) answer; 503 otherwise. Wire this to the load balancer so a broken
  instance is drained.
- **Metrics:** `GET /metrics` (Prometheus) — request latency histogram, request
  counts by status, and 5xx error counter.
- **Logs:** structured JSON, one object per line, each carrying the
  `request_id` also returned in the `X-Request-ID` response header for
  end-to-end correlation.

## Backups, RPO & RTO

**Backup strategy (MySQL):**

- Automated logical backup on a schedule (cron / managed-DB snapshot):
  ```
  mysqldump --single-transaction --routines --triggers papertrail \
    | gzip > papertrail-$(date +%F-%H%M).sql.gz
  ```
  `--single-transaction` gives a consistent snapshot without locking (InnoDB).
- Recommended cadence: **hourly** incremental/logical dumps retained 7 days +
  **daily** dumps retained 30 days, shipped off-box (e.g. object storage).
- For lower RPO, enable **binlog** and use point-in-time recovery, or use a
  managed MySQL with continuous backup.

**Restore (tested procedure):**
```
gunzip < papertrail-YYYY-MM-DD-HHMM.sql.gz | mysql papertrail
alembic upgrade head   # ensure schema is at the latest migration
```
Restores must be **tested** on a scratch instance regularly — an untested
backup is not a backup.

**Targets (modest, appropriate for this project's scale):**

| Metric | Target | Basis |
|--------|--------|-------|
| RPO (max data loss) | ≤ 1 hour | hourly automated dumps (≤ 5 min with binlog PITR) |
| RTO (time to restore) | ≤ 1 hour | single `mysqldump` restore + `alembic upgrade` |

Redis holds only cache + rate-limit counters (regenerable), so it has **no RPO
requirement** — a cold Redis simply repopulates.

## Configuration

All settings are environment-driven (see `backend/.env.example`). Production
**must** set: `JWT_SECRET` (long random), `DB_*`, `CORS_ORIGINS`, and
`REDIS_URL` (for multi-worker correctness).
