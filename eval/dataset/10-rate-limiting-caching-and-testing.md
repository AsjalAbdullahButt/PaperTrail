# Rate Limiting, Caching, and Testing

## Redis-backed rate limiting

PaperTrail enforces per-endpoint rate limits using the `slowapi` and `limits` libraries. When `REDIS_URL` is configured, these limits are enforced against a shared Redis store, so a limit is correctly shared across every API worker process rather than each worker independently tracking (and under-enforcing) its own counter; when no Redis URL is configured, limits fall back to in-process memory, which is only correct for a single worker. Rate limiting overall is controlled by `RATE_LIMIT_ENABLED`, which defaults to `true`.

## Default per-action limits

PaperTrail's internal application defaults (distinct from the more conservative values suggested in the production deployment guidance) are: querying at 20 requests per minute (`RATE_LIMIT_QUERY`), uploading at 10 requests per hour (`RATE_LIMIT_UPLOAD`), logging in at 5 requests per minute (`RATE_LIMIT_LOGIN`), registering a new account at 3 requests per minute (`RATE_LIMIT_REGISTER`), exporting account data at 1 request per hour (`RATE_LIMIT_EXPORT`), and a general default of 100 requests per minute (`RATE_LIMIT_DEFAULT`) for any endpoint without a more specific limit.

## Query-response caching

Query responses are cached for a configurable time-to-live, `QUERY_CACHE_TTL_SECONDS`, which defaults to 300 seconds (5 minutes). Setting this value to 0 disables query-response caching entirely. This cache shares its invalidation mechanism with the retrieval index cache described elsewhere — both are invalidated together when the underlying data they depend on changes.

## Backend test suite

The backend's test suite, run with `pytest -q` from the `backend/` directory, contains 181 tests covering authentication, retrieval, ingestion, document sharing, rate limiting, and a range of other subsystems. Running it requires first installing the development dependencies listed in `backend/requirements-dev.txt`.

## Frontend testing

The frontend uses three distinct checks. Component-level tests are run with Vitest via `npm run test`. Linting is run via `npm run lint`. Type-checking (with no build output emitted) is run via `npx tsc --noEmit`. A fourth, separate check, end-to-end testing with Playwright (`npm run test:e2e`), requires both a live backend to test against and running `npx playwright install` once beforehand to fetch the browser binaries Playwright drives.

## Continuous integration

PaperTrail's continuous integration workflow, defined at `.github/workflows/ci.yml`, runs on every push and every pull request. It runs the full backend pytest suite against a real MySQL service container in the CI environment — including actually running `alembic upgrade head` against that container, not a mocked or in-memory database — alongside the frontend's lint, build, and test steps. The project's stated contribution expectation is that `pytest -q` (backend) and `npm run lint && npm run test && npm run build` (frontend) must all pass locally before a pull request is opened, since CI enforces exactly the same checks.
