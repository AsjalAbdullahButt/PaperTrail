"""Structured JSON logging + Prometheus metrics.

- A request-scoped ``request_id`` is stored in a contextvar and injected into
  every log record via a logging filter, so all logs emitted while handling a
  request share the same correlation id.
- Logs are emitted as one JSON object per line (machine-parseable).
- Prometheus metrics track request latency, counts, and errors.
"""
from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.requests import Request

# Correlation id for the in-flight request (set by middleware).
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Install a JSON stream handler with the request-id filter on the root."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


# --------------------------------------------------------------------------- #
# Prometheus metrics
# --------------------------------------------------------------------------- #
REQUEST_COUNT = Counter(
    "papertrail_requests_total",
    "Total HTTP requests.",
    ["method", "endpoint", "status"],
)
REQUEST_LATENCY = Histogram(
    "papertrail_request_latency_seconds",
    "HTTP request latency in seconds.",
    ["method", "endpoint"],
)
ERROR_COUNT = Counter(
    "papertrail_errors_total",
    "Total HTTP responses with a 5xx status.",
    ["method", "endpoint"],
)


def _endpoint_label(request: Request) -> str:
    """Stable, low-cardinality label: the route template, not the raw path."""
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        endpoint = _endpoint_label(request)
        elapsed = time.perf_counter() - start
        REQUEST_LATENCY.labels(request.method, endpoint).observe(elapsed)
        REQUEST_COUNT.labels(request.method, endpoint, str(status)).inc()
        if status >= 500:
            ERROR_COUNT.labels(request.method, endpoint).inc()


def metrics_response_body() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
