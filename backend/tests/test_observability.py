"""Phase 5: liveness/readiness split, Prometheus metrics, JSON logging."""
from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from app.main import app
from app.observability import JsonLogFormatter, request_id_ctx

from conftest import requires_db

client = TestClient(app)


def test_liveness_is_unconditional():
    res = client.get("/api/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    # Legacy alias still works.
    assert client.get("/api/health").json() == {"status": "ok"}


@requires_db
def test_readiness_reports_dependency_checks():
    res = client.get("/api/health/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert "redis" in body["checks"]


def test_metrics_endpoint_exposes_prometheus_format():
    client.get("/api/health/live")  # generate at least one measurement
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers["content-type"]
    assert "papertrail_requests_total" in res.text
    assert "papertrail_request_latency_seconds" in res.text


def test_request_id_is_threaded_into_logs():
    formatter = JsonLogFormatter()
    token = request_id_ctx.set("corr-xyz")
    try:
        record = logging.LogRecord(
            "papertrail", logging.INFO, __file__, 1, "hello", None, None
        )
        record.request_id = request_id_ctx.get()
        line = formatter.format(record)
    finally:
        request_id_ctx.reset(token)
    parsed = json.loads(line)
    assert parsed["request_id"] == "corr-xyz"
    assert parsed["message"] == "hello"
    assert parsed["level"] == "INFO"
