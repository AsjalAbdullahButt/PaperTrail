"""Auth + row-level isolation tests (Phase 3 gate).

Covers registration, login, token expiry, unauthenticated rejection, and proof
that user A cannot list, query-retrieve, or delete user B's documents.
"""
from __future__ import annotations

import app.security as security
from app.security import create_access_token

from conftest import auth_headers, register_and_token, requires_db

pytestmark = requires_db

SECRET = "The moonstone cipher key is amber-lantern-42, unique to user A."


def _upload(client, headers, filename, text):
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, text.encode(), "text/plain")},
        headers=headers,
    )


# ------------------------------- basics -------------------------------- #
def test_register_returns_token_and_me_works(anon_client):
    token = register_and_token(anon_client, "alice@papertrail.io")
    res = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "alice@papertrail.io"


def test_duplicate_registration_rejected(anon_client):
    register_and_token(anon_client, "dupe@papertrail.io")
    res = anon_client.post(
        "/api/auth/register",
        json={"email": "dupe@papertrail.io", "password": "password123"},
    )
    assert res.status_code == 422


def test_login_success_and_failure(anon_client):
    register_and_token(anon_client, "bob@papertrail.io", "correct-horse")
    ok = anon_client.post(
        "/api/auth/login",
        json={"email": "bob@papertrail.io", "password": "correct-horse"},
    )
    assert ok.status_code == 200 and ok.json()["access_token"]

    bad = anon_client.post(
        "/api/auth/login",
        json={"email": "bob@papertrail.io", "password": "wrong-password"},
    )
    assert bad.status_code == 401

    unknown = anon_client.post(
        "/api/auth/login",
        json={"email": "nobody@papertrail.io", "password": "whatever12"},
    )
    assert unknown.status_code == 401


def test_short_password_rejected(anon_client):
    res = anon_client.post(
        "/api/auth/register", json={"email": "x@papertrail.io", "password": "short"}
    )
    assert res.status_code == 422


# --------------------------- token handling ---------------------------- #
def test_unauthenticated_requests_rejected(anon_client):
    assert anon_client.get("/api/documents").status_code == 401
    assert anon_client.post("/api/query", json={"question": "hi", "mode": "rag"}).status_code == 401
    assert anon_client.get("/api/chat-history").status_code == 401
    assert anon_client.delete("/api/documents/1").status_code == 401


def test_invalid_token_rejected(anon_client):
    res = anon_client.get("/api/documents", headers={"Authorization": "Bearer not.a.jwt"})
    assert res.status_code == 401


def test_expired_token_rejected(anon_client, monkeypatch):
    # Issue a token that is already expired.
    monkeypatch.setattr(security.settings, "jwt_expire_minutes", -1)
    token = create_access_token(123)
    res = anon_client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


# --------------------- refresh / logout / me --------------------------- #
def test_register_sets_refresh_cookie_and_refresh_issues_new_access(anon_client):
    from app.config import settings

    reg = anon_client.post(
        "/api/auth/register",
        json={"email": "refresh-me@papertrail.io", "password": "password123"},
    )
    assert reg.status_code == 201
    # httpOnly refresh cookie was set by the register response...
    assert settings.refresh_cookie_name in anon_client.cookies
    # ...and the client resends it, so /refresh mints a fresh access token.
    res = anon_client.post("/api/auth/refresh")
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_refresh_without_cookie_is_401(anon_client):
    anon_client.cookies.clear()
    res = anon_client.post("/api/auth/refresh")
    assert res.status_code == 401


def test_logout_revokes_refresh_token(anon_client):
    anon_client.post(
        "/api/auth/register",
        json={"email": "logout-me@papertrail.io", "password": "password123"},
    )
    # Refresh works before logout.
    assert anon_client.post("/api/auth/refresh").status_code == 200
    # Capture the (httpOnly) refresh token so we can present the *same* revoked
    # token after the logout response clears the cookie jar.
    from app.config import settings

    revoked = anon_client.cookies.get(settings.refresh_cookie_name)
    assert anon_client.post("/api/auth/logout").status_code == 200
    # The revoked token is rejected even if replayed directly.
    res = anon_client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {revoked}"},
    )
    assert res.status_code == 401


def test_me_requires_token(anon_client):
    assert anon_client.get("/api/auth/me").status_code == 401


def test_display_name_persisted_on_register(anon_client):
    token = anon_client.post(
        "/api/auth/register",
        json={
            "email": "named@papertrail.io",
            "password": "password123",
            "display_name": "Ada Lovelace",
        },
    ).json()["access_token"]
    me = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == "Ada Lovelace"


# ----------------------- cross-user isolation -------------------------- #
def test_user_a_documents_are_invisible_to_user_b(anon_client):
    a = auth_headers(anon_client, "a@papertrail.io")
    b = auth_headers(anon_client, "b@papertrail.io")

    up = _upload(anon_client, a, "a-secret.txt", SECRET)
    assert up.status_code == 200, up.text
    a_doc_id = up.json()["id"]

    # (1) B cannot list A's document.
    b_list = anon_client.get("/api/documents", headers=b)
    assert b_list.status_code == 200
    assert a_doc_id not in {d["id"] for d in b_list.json()}

    # A can see their own.
    a_list = anon_client.get("/api/documents", headers=a)
    assert a_doc_id in {d["id"] for d in a_list.json()}


def test_user_b_rag_query_cannot_retrieve_user_a_chunks(anon_client):
    a = auth_headers(anon_client, "a2@papertrail.io")
    b = auth_headers(anon_client, "b2@papertrail.io")
    _upload(anon_client, a, "a-secret.txt", SECRET)

    # B asks a question whose answer only exists in A's document.
    res = anon_client.post(
        "/api/query",
        json={"question": "What is the moonstone cipher key?", "mode": "rag"},
        headers=b,
    )
    assert res.status_code == 200
    assert res.json()["sources"] == []  # nothing of A's is retrievable by B


def test_user_b_cannot_delete_user_a_document(anon_client):
    a = auth_headers(anon_client, "a3@papertrail.io")
    b = auth_headers(anon_client, "b3@papertrail.io")
    up = _upload(anon_client, a, "a-secret.txt", SECRET)
    a_doc_id = up.json()["id"]

    # Cross-user delete attempt -> 403 (exists but not owned), not 404.
    forbidden = anon_client.delete(f"/api/documents/{a_doc_id}", headers=b)
    assert forbidden.status_code == 403

    # A's document is still there and still retrievable by A.
    a_list = anon_client.get("/api/documents", headers=a)
    assert a_doc_id in {d["id"] for d in a_list.json()}


def test_chat_history_is_per_user(anon_client):
    a = auth_headers(anon_client, "a4@papertrail.io")
    b = auth_headers(anon_client, "b4@papertrail.io")
    anon_client.post(
        "/api/query", json={"question": "A private question", "mode": "direct"}, headers=a
    )

    b_hist = anon_client.get("/api/chat-history", headers=b)
    assert b_hist.status_code == 200
    assert b_hist.json()["total"] == 0

    a_hist = anon_client.get("/api/chat-history", headers=a)
    assert a_hist.json()["total"] == 1
    assert a_hist.json()["items"][0]["question"] == "A private question"
