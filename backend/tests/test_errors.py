"""The global exception handlers return structured JSON with a request ID."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

# These do not need the database.
client = TestClient(app)


def test_http_exception_is_structured_json():
    # A 404 route yields the structured error envelope, not FastAPI's default.
    res = client.get("/api/does-not-exist")
    assert res.status_code == 404
    body = res.json()
    assert "error" in body
    assert body["error"]["status_code"] == 404
    assert "request_id" in body["error"]
    assert res.headers.get("X-Request-ID")


def test_request_id_is_echoed_and_honored():
    res = client.get("/api/health", headers={"X-Request-ID": "test-correlation-123"})
    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == "test-correlation-123"


def test_validation_error_is_structured():
    # /api/auth/register needs no auth, so body validation (short password)
    # is what fails here — proving the structured 422 handler.
    res = client.post(
        "/api/auth/register", json={"email": "x@y.io", "password": "short"}
    )
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["status_code"] == 422
    assert "details" in body["error"]
