"""Test the /api/health route.

Uses TestClient WITHOUT the lifespan context manager so the test does not
require a live database connection.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
