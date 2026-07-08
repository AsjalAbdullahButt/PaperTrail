# Presence of this file puts the backend/ directory on sys.path so tests can
# `import app...` regardless of where pytest is invoked from.
#
# It also provides DB-backed fixtures. Integration tests run against the real
# configured database (MySQL in dev/CI) using transactional rollback isolation:
# each test runs inside an outer transaction that is rolled back on teardown,
# so tests share the real schema (including MySQL-only LONGTEXT) without
# persisting any rows and without needing a separate database.
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, get_db
from app.main import app


def _db_available() -> bool:
    try:
        conn = engine.connect()
        conn.close()
        return True
    except Exception:  # noqa: BLE001
        return False


DB_AVAILABLE = _db_available()

# Integration tests that need a database are skipped (not failed) when no DB is
# reachable, so unit tests (chunking, similarity, health, llm, ingestion) still
# run in a bare environment.
requires_db = pytest.mark.skipif(
    not DB_AVAILABLE, reason="No database reachable for integration tests."
)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    if not DB_AVAILABLE:
        yield
        return
    from app import models  # noqa: F401  (register tables on Base.metadata)

    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def db_session():
    """A session bound to an outer transaction that is rolled back on teardown.

    ``join_transaction_mode="create_savepoint"`` makes the ORM emit SAVEPOINTs,
    so application-level ``commit()`` calls are preserved within the test but
    everything is discarded when the outer transaction rolls back.
    """
    connection = engine.connect()
    trans = connection.begin()
    session = SessionLocal(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _no_disk_writes(monkeypatch):
    """Tests exercise the upload pipeline but must not leave files on disk, and
    default rate limits are relaxed so ordinary tests don't trip them. Tests
    that specifically exercise a limit set their own (later, so it wins)."""
    from app.config import settings

    monkeypatch.setattr(settings, "store_originals", False, raising=False)
    for attr in (
        "rate_limit_query", "rate_limit_upload", "rate_limit_login",
        "rate_limit_register", "rate_limit_export", "rate_limit_default",
    ):
        monkeypatch.setattr(settings, attr, "10000/minute", raising=False)
    yield


@pytest.fixture(autouse=True)
def _reset_cache_and_limiter():
    """Keep the in-process cache and rate-limiter storage isolated per test."""
    from app.cache import cache
    from app.ratelimit import limiter

    if hasattr(cache, "clear"):
        cache.clear()
    try:
        limiter.reset()
    except Exception:  # noqa: BLE001
        pass
    yield
    if hasattr(cache, "clear"):
        cache.clear()
    try:
        limiter.reset()
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture()
def anon_client(db_session):
    """Unauthenticated TestClient bound to the rolled-back test session."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        # No `with` block: we intentionally skip the lifespan (init_db) so tests
        # never trigger CREATE DATABASE against the server.
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def register_and_token(client, email: str, password: str = "password123") -> str:
    """Register a user via the API and return their access token."""
    res = client.post(
        "/api/auth/register", json={"email": email, "password": password}
    )
    assert res.status_code == 201, res.text
    return res.json()["access_token"]


def auth_headers(client, email: str, password: str = "password123") -> dict:
    return {"Authorization": f"Bearer {register_and_token(client, email, password)}"}


@pytest.fixture()
def client(anon_client):
    """Authenticated TestClient (default user). Most routes require auth."""
    token = register_and_token(anon_client, "default-user@papertrail.io")
    anon_client.headers.update({"Authorization": f"Bearer {token}"})
    return anon_client
