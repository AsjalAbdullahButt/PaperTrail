# Production Environment Variables

## Where these values are set

Every environment variable described in this document is set directly on the Render backend service, under Dashboard → the service → Environment. Their names match `backend/.env.example` exactly, so nothing about them is invented or renamed for production specifically.

## OpenAI configuration

`OPENAI_API_KEY` is required — without it, RAG-mode answers will not use a real hosted model. `OPENAI_EMBEDDING_MODEL` is optional; its default value, `text-embedding-3-small`, is fine for most deployments. `OPENAI_CHAT_MODEL` is likewise optional, defaulting to `gpt-4o-mini`.

## Database and TLS configuration (Aiven for MySQL)

`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and `DB_NAME` are all required and come from the Aiven console's Service Overview page. `DB_SSL_MODE` is required and must be set to `true`, because Aiven rejects any connection attempt that is not encrypted with TLS. `DB_SSL_CA` is optional but recommended: it should point at the path of a downloaded CA certificate file (mounted as a Render secret file, for example at `/etc/secrets/aiven-ca.pem`); without it, the TLS connection still negotiates successfully, but the server's certificate is not verified against a known certificate authority.

## Upload limits

`MAX_UPLOAD_MB` (default 25 in the documented production guidance, though the application's own internal default is 50) and `MAX_QUERY_CHUNKS` (default 5000) are both optional and can be set to whatever ceiling the operator prefers.

## Storage (Cloudflare R2)

`STORAGE_BACKEND` is required and must be set to `s3`, since R2 is accessed through the S3-compatible API. `S3_BUCKET` is required and comes from the bucket name created in the Cloudflare dashboard's R2 section. `S3_REGION` is required and must be set to `auto` specifically for R2. `S3_ENDPOINT_URL` is required and takes the form `https://<account_id>.r2.cloudflarestorage.com`, found in the Cloudflare dashboard. `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` are both required and are generated from Cloudflare's R2 "Manage API Tokens" page.

## CORS and frontend URL

`CORS_ORIGINS` and `FRONTEND_BASE_URL` are both required, and both must be set to the same final deployed Vercel URL (for example, `https://papertrail-yourname.vercel.app`). If either variable is left stale — still pointing at `localhost`, for instance — the practical failure differs: a stale `CORS_ORIGINS` causes the browser to silently reject the backend's responses, while a stale `FRONTEND_BASE_URL` causes generated password-reset links to point at the wrong host.

## JWT and cookies

`JWT_SECRET` is required and must be freshly generated (for example with `openssl rand -hex 32`) — the application deliberately refuses to start with `COOKIE_SECURE=true` while still using the default development secret. `JWT_ALGORITHM` (default `HS256`), `JWT_EXPIRE_MINUTES` (default 30), `REFRESH_EXPIRE_DAYS` (default 7), and `REFRESH_COOKIE_NAME` (default `papertrail_refresh`) are all optional. `COOKIE_SECURE` is required and must be set to `true` in production, since production traffic runs over HTTPS.

## Redis and rate limiting

`REDIS_URL` is required in production, since it is what makes rate limiting and the query-response cache consistent across multiple API workers rather than each worker keeping its own independent, incorrect counters. `RATE_LIMIT_ENABLED` defaults to `true`. `RATE_LIMIT_QUERY` defaults to `60/minute`, `RATE_LIMIT_UPLOAD` defaults to `20/minute`, and `QUERY_CACHE_TTL_SECONDS` defaults to 300 seconds — all three are optional and can be tuned per deployment.

## SQLAlchemy connection pool

`DB_POOL_SIZE` (default 10) and `DB_MAX_OVERFLOW` (default 20) are optional, but the operator must keep the product `WEB_CONCURRENCY * (DB_POOL_SIZE + DB_MAX_OVERFLOW)` under Aiven's configured `max_connections` limit, or the database will start rejecting new connections under load. `DB_POOL_TIMEOUT` (default 30 seconds) and `DB_POOL_RECYCLE` (default 1800 seconds, i.e. 30 minutes) are also optional.

## Variables Render sets automatically

`PORT` is set automatically by Render and should never be set manually — `backend/Dockerfile` is written to bind to whatever value `$PORT` holds. `WEB_CONCURRENCY`, the number of gunicorn worker processes, is optional and defaults to 4 in the Dockerfile's `CMD` instruction.
