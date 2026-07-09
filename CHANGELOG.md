# Changelog

## 2026-07-09 - Security, ingestion concurrency, session UX, and retrieval scaling follow-up

- **Phase 1 (auth security):** refresh-token rotation now blacklists the presented refresh token on every exchange, detects replay as token theft, logs a warning with user/request correlation, and revokes the whole refresh-token family via `users.revoked_before`.
- **Phase 2 (upload scalability):** document ingestion keeps blocking extraction/embedding/file I/O off the event loop, records `processing_status`/`processing_error`, and exposes real failed states through document status.
- **Phase 3 (frontend session UX):** all API calls route through `apiFetch` with single-flight refresh-and-retry on 401, plus proactive access-token refresh scheduling in the auth store.
- **Phase 4 (hardening):** CSP no longer allows inline scripts on `script-src`, and startup now refuses production-like cookie settings with the default JWT secret.
- **Phase 5 (retrieval architecture):** per-user BM25 + dense ANN retrieval indexes are cached and reused, invalidated on document add/delete via the existing cache prefix invalidation hooks, and retrieval parity is covered against brute-force ranking on fixture data.
- **Phase 6 (frontend quality):** Vitest coverage expanded for auth store flows (including failure paths), middleware redirects for auth/non-auth routes, and `DocumentManager` loading/empty/populated/error states.
