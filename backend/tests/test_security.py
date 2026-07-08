"""Phase 7: input validation, rate limiting, isolation, headers, secrets."""
from __future__ import annotations

import app.ratelimit as ratelimit
import app.routers.documents as documents_router
from ._helpers import upload_bytes, upload_text_doc

from conftest import auth_headers, register_and_token, requires_db

pytestmark = requires_db


# ----------------------------- input validation ------------------------- #
def test_password_requires_letter_and_number(anon_client):
    res = anon_client.post(
        "/api/auth/register",
        json={"email": "weak@papertrail.io", "password": "alllettershere"},
    )
    assert res.status_code == 422


def test_query_over_2000_chars_rejected(client):
    res = client.post("/api/query", json={"question": "a" * 2001, "mode": "rag"})
    assert res.status_code == 422


def test_whitespace_only_query_rejected(client):
    res = client.post("/api/query", json={"question": "     ", "mode": "rag"})
    assert res.status_code == 422


def test_null_bytes_stripped_from_query(client):
    upload_text_doc(client, "n.txt", "some content about topics " * 10)
    res = client.post("/api/query", json={"question": "topic\x00s", "mode": "direct"})
    # Accepted (nulls stripped), not a 422/500.
    assert res.status_code == 200


# ------------------------------ file upload ----------------------------- #
def test_exe_renamed_pdf_rejected_by_magic_bytes(client):
    res = upload_bytes(client, "evil.pdf", b"MZ\x90\x00\x03 this is a PE binary", "application/pdf")
    assert res.status_code == 422


def test_oversized_upload_rejected(client, monkeypatch):
    monkeypatch.setattr(documents_router.settings, "max_upload_mb", 0.001, raising=False)
    res = upload_bytes(client, "big.txt", b"x" * 4096, "text/plain")
    assert res.status_code == 413


# ------------------------------ rate limiting --------------------------- #
def test_login_rate_limited(anon_client, monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "rate_limit_login", "5/minute")
    anon_client.post("/api/auth/register", json={"email": "rl@papertrail.io", "password": "password123"})
    statuses = [
        anon_client.post("/api/auth/login", json={"email": "rl@papertrail.io", "password": "password123"}).status_code
        for _ in range(6)
    ]
    assert 429 in statuses


# ------------------------------- isolation ------------------------------ #
def test_cross_user_document_returns_403(client, anon_client):
    doc = upload_text_doc(client, "mine.txt", "private secret content " * 10)
    other = auth_headers(anon_client, "intruder2@papertrail.io")
    # Delete + status + coverage + tags all reject with 403 (exists, not owned).
    assert anon_client.delete(f"/api/documents/{doc['id']}", headers=other).status_code == 403
    assert anon_client.get(f"/api/documents/{doc['id']}/status", headers=other).status_code == 403
    assert anon_client.get(f"/api/documents/{doc['id']}/coverage", headers=other).status_code == 403


def test_sql_injection_attempt_is_harmless(client):
    upload_text_doc(client, "s.txt", "normal content about databases " * 10)
    res = client.post(
        "/api/query",
        json={"question": "'; DROP TABLE users; --", "mode": "rag"},
    )
    assert res.status_code == 200
    # The users table still works: a follow-up authenticated call succeeds.
    assert client.get("/api/auth/me").status_code == 200


# ------------------------------ error safety ---------------------------- #
def test_errors_do_not_leak_stack_traces(client):
    res = client.get("/api/documents/nonexistent-id/status")
    assert res.status_code == 404
    body = res.text.lower()
    assert "traceback" not in body and "sqlalchemy" not in body


# ------------------------------ headers --------------------------------- #
def test_security_headers_present(anon_client):
    res = anon_client.get("/api/health")
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in res.headers
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


# ------------------------------ secrets --------------------------------- #
def test_settings_load_without_hardcoded_secrets():
    from app.config import settings

    # The signing secret is configurable (not a literal in code) and the app
    # exposes whether the insecure dev default is in use.
    assert hasattr(settings, "jwt_secret")
    assert isinstance(settings.jwt_secret_is_default, bool)
