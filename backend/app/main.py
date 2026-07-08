"""PaperTrail FastAPI application entry point.

Exposes GET /api/health, wires the document / query / chat-history routers,
enables env-driven CORS, threads a request ID through every request, returns
structured JSON errors, and on startup ensures the MySQL database and all
tables exist.
"""
import logging
import uuid

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .database import check_db, init_db
from .observability import (
    configure_logging,
    metrics_middleware,
    metrics_response_body,
    request_id_ctx,
)
from .ratelimit import limiter
from .routers import auth, chat_history, collections, documents, queries, query

configure_logging()
logger = logging.getLogger("papertrail")

REQUEST_ID_HEADER = "X-Request-ID"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the database + tables on startup if they don't exist yet."""
    try:
        init_db()
        logger.info("Database initialized (tables ensured).")
    except Exception as exc:  # noqa: BLE001 - keep the API up even if DB is down
        logger.warning("Database init skipped/failed: %s", exc)
    yield


app = FastAPI(title="PaperTrail API", version="0.1.0", lifespan=lifespan)

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
                "details": exc.errors(),
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


@app.get("/metrics")
def metrics():
    """Prometheus metrics: request latency, counts, and error rate."""
    body, content_type = metrics_response_body()
    return Response(content=body, media_type=content_type)
