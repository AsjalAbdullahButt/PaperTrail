"""PaperTrail FastAPI application entry point.

Exposes GET /api/health, wires the document / query / chat-history routers,
enables env-driven CORS, threads a request ID through every request, returns
structured JSON errors, and on startup ensures the MySQL database and all
tables exist.
"""
import logging
import time
import uuid

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings, validate_production_settings
from .database import check_db, init_db, purge_soft_deleted
from .observability import (
    configure_logging,
    metrics_middleware,
    metrics_response_body,
    request_id_ctx,
)
from .ratelimit import limiter
from .routers import (
    analytics,
    auth,
    chat_history,
    collections,
    documents,
    export,
    queries,
    query,
)

configure_logging()
logger = logging.getLogger("papertrail")

REQUEST_ID_HEADER = "X-Request-ID"
VERSION = "2.0.0"
_START_TIME = time.monotonic()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup: refuse to run with production-looking config on the dev JWT
    secret, then ensure schema exists and purge documents/collections/queries
    whose soft-delete retention window (30 days) has elapsed."""
    try:
        validate_production_settings(settings)
    except RuntimeError as exc:
        # One clear, actionable line — the operator needs the fix, not a trace.
        logger.critical("Startup refused: %s", exc)
        raise
    try:
        init_db()
        logger.info("Database initialized (tables ensured).")
    except Exception as exc:  # noqa: BLE001 - keep the API up even if DB is down
        logger.warning("Database init skipped/failed: %s", exc)
    try:
        removed = purge_soft_deleted()
        if removed:
            logger.info("Cleanup: purged %d expired soft-deleted record(s).", removed)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Soft-delete cleanup skipped/failed: %s", exc)
    yield


app = FastAPI(title="PaperTrail API", version=VERSION, lifespan=lifespan)

# Rate limiting (slowapi). The limiter is attached to app.state and the
# endpoints opt in via decorators; exceeded limits return a structured 429.
app.state.limiter = limiter

# Env-driven CORS: origins come from config (not hardcoded). Methods/headers
# are scoped to what the frontend actually uses instead of "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=[REQUEST_ID_HEADER],
)


# Prometheus metrics middleware (added first so it wraps the whole stack).
app.middleware("http")(metrics_middleware)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        # The API serves JSON only — the Next.js frontend is a separate origin
        # and never receives this header, so no inline scripts or styles need
        # allowing here. (Verified: no HTMLResponse/StaticFiles anywhere; the
        # auto-generated /docs page was already non-functional under
        # script-src 'self' because its assets come from a CDN.)
        "default-src 'self'; script-src 'self'; style-src 'self'"
    ),
}


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Attach hardening headers to every response (clickjacking, MIME sniffing,
    referrer leakage, and a conservative CSP)."""
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a request ID to every request for log/error correlation."""
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    request.state.request_id = request_id
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_ctx.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Render HTTPExceptions as structured JSON while preserving status codes."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "status_code": exc.status_code,
                "request_id": _request_id(request),
            }
        },
        headers={REQUEST_ID_HEADER: _request_id(request)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Structured 422 for request-validation failures."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "message": "Request validation failed.",
                "status_code": 422,
                "request_id": _request_id(request),
                "details": jsonable_encoder(exc.errors()),
            }
        },
        headers={REQUEST_ID_HEADER: _request_id(request)},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Structured 429 when a client exceeds its rate limit."""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "message": f"Rate limit exceeded: {exc.detail}.",
                "status_code": 429,
                "request_id": _request_id(request),
            }
        },
        headers={REQUEST_ID_HEADER: _request_id(request)},
    )


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    """A dropped/unreachable database yields a 503 (retryable), never a crash."""
    request_id = _request_id(request)
    logger.error("Database unavailable (request_id=%s): %s", request_id, exc)
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "message": "Service temporarily unavailable (database).",
                "status_code": 503,
                "request_id": request_id,
            }
        },
        headers={REQUEST_ID_HEADER: request_id},
    )


@app.exception_handler(SQLAlchemyError)
async def db_error_handler(request: Request, exc: SQLAlchemyError):
    """Any other DB error is logged server-side and returned as a generic 500
    (no ORM/SQL details leak to the client)."""
    request_id = _request_id(request)
    logger.exception("Database error (request_id=%s): %s", request_id, exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error.",
                "status_code": 500,
                "request_id": request_id,
            }
        },
        headers={REQUEST_ID_HEADER: request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all: log the full stack trace server-side, return a safe 500."""
    request_id = _request_id(request)
    logger.exception("Unhandled error (request_id=%s): %s", request_id, exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error.",
                "status_code": 500,
                "request_id": request_id,
            }
        },
        headers={REQUEST_ID_HEADER: request_id},
    )


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(query.router)
app.include_router(chat_history.router)
app.include_router(collections.router)
app.include_router(queries.router)
app.include_router(analytics.router)
app.include_router(export.router)


@app.get("/api/health")
@app.get("/api/health/live")
def liveness():
    """Liveness: the process is up and serving. No external dependencies."""
    return {"status": "ok"}


@app.get("/api/health/ready")
def readiness():
    """Readiness: dependencies (DB, Redis if configured) are reachable.

    Returns 503 when a dependency is down so a load balancer stops routing
    traffic to this instance instead of us returning 200 unconditionally.
    """
    checks: dict[str, str] = {}
    ok = True

    db_ok, db_err = check_db()
    checks["database"] = "ok" if db_ok else f"error: {db_err}"
    ok = ok and db_ok

    if settings.redis_url:
        try:
            import redis

            redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {exc}"
            ok = False
    else:
        checks["redis"] = "not configured"

    status_code = 200 if ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if ok else "not_ready", "checks": checks},
    )


@app.get("/api/health/detailed")
def detailed_health():
    """Detailed status for monitoring: database, AI service, uptime, version.

    Unauthenticated (monitors need it). ``ai_service`` degradation does not take
    the whole service down — cached results and the offline fallback still work.
    """
    db_ok, _ = check_db()

    ai_status = "ok"
    if settings.openai_ready or settings.groq_ready:
        try:
            if settings.openai_ready:
                from openai import OpenAI

                OpenAI(api_key=settings.openai_api_key, timeout=5).models.list()
            # Groq/offline: treat a configured Groq key as available without a
            # blocking network probe.
        except Exception:  # noqa: BLE001
            ai_status = "degraded"
    else:
        # No hosted model configured -> offline fallback is the intended mode.
        ai_status = "degraded"

    if not db_ok:
        overall = "down"
    elif ai_status != "ok":
        overall = "degraded"
    else:
        overall = "ok"

    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "status": overall,
            "database": "ok" if db_ok else "error",
            "ai_service": ai_status,
            "uptime_seconds": int(time.monotonic() - _START_TIME),
            "version": VERSION,
        },
    )


@app.get("/metrics")
def metrics():
    """Prometheus metrics: request latency, counts, and error rate."""
    body, content_type = metrics_response_body()
    return Response(content=body, media_type=content_type)
