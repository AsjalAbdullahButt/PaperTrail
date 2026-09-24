# Observability, Health Checks, and Backups

## Health endpoints

PaperTrail exposes two distinct health endpoints with different meanings. `GET /api/health/live` (also reachable at the shorter alias `GET /api/health`) is a liveness check — it answers "is this process running at all," and does not depend on any downstream service. `GET /api/health/ready` is a readiness check that only returns HTTP 200 when the backend can actually reach MySQL (and Redis, when Redis is configured); this is the endpoint that should be wired into a load balancer's health check, since a live-but-not-ready worker should not receive traffic.

## Metrics

`GET /metrics` exposes Prometheus-format metrics, including a request-latency histogram, request counts broken down by HTTP status code, and a dedicated counter for 5xx server errors, so error rates and latency percentiles can be tracked over time by any Prometheus-compatible monitoring system.

## Structured logs

PaperTrail emits structured JSON logs, one JSON object per line, which makes them straightforward to ingest into a log-aggregation system without custom parsing. Every log line is correlated to the specific request that produced it via a `request_id` field; the same request id is also returned to the client as the `X-Request-ID` response header, so a user-reported issue can be traced back to its exact log lines.

## Database backups

Backups of the production MySQL database are taken with `mysqldump`, using the `--single-transaction`, `--routines`, and `--triggers` flags, and the output is piped through `gzip` before being written to disk with a timestamped filename. The recommended backup cadence is hourly logical dumps retained for 7 days, plus daily dumps retained for 30 days, with both sets shipped off the primary box rather than kept only alongside the database itself. Restoring is the reverse operation: decompressing the dump with `gunzip`, piping it into `mysql`, and then running `alembic upgrade head` afterward to ensure the schema matches the current migration history.

## Recovery targets

PaperTrail documents two explicit disaster-recovery targets. The Recovery Point Objective (RPO), meaning the maximum acceptable amount of data loss measured in time, is one hour under the hourly-dump backup cadence, or as low as 5 minutes if binary-log point-in-time recovery is additionally configured. The Recovery Time Objective (RTO), meaning the maximum acceptable time to restore service after a failure, is one hour, covering a single restore operation followed by running the pending migrations.

## Why Redis needs no backup strategy

Unlike MySQL, Redis in PaperTrail's architecture holds only two kinds of data: the query-response cache and rate-limiting counters. Both are safe to lose entirely — a cold, freshly started Redis instance simply repopulates its cache as new queries come in and its rate-limit counters as new requests arrive — so no backup or restore procedure is defined for Redis at all.

## The production startup checklist

Before a deployment is considered production-ready, four things must be true: `JWT_SECRET` must be set to a long, randomly generated value (never the insecure development default); `DB_*` variables must point at real managed-database credentials; `CORS_ORIGINS` must be set correctly; and `REDIS_URL` must be configured so that rate limits and the query cache are shared correctly across every worker process rather than each worker tracking its own inconsistent counters. As a hard safety net beyond this checklist, the application will refuse to even start if `COOKIE_SECURE=true` is set while `JWT_SECRET` is still at its default insecure value.
