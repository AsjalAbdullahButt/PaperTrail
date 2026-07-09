"""Profile update, password change, account deletion, and password-reset flow.

Covers the endpoints added alongside the /profile frontend page: PATCH
/api/auth/me, POST /api/auth/change-password, DELETE /api/auth/me, and the
forgot/reset-password pair.
"""
from __future__ import annotations

from conftest import auth_headers, register_and_token, requires_db

pytestmark = requires_db


# ------------------------------- profile -------------------------------- #
def test_update_profile_persists_fields(anon_client):
    headers = auth_headers(anon_client, "profile@papertrail.io")
    res = anon_client.patch(
        "/api/auth/me",
        json={"display_name": "Grace Hopper", "bio": "Compiler pioneer.", "avatar_url": "https://example.com/a.png"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["display_name"] == "Grace Hopper"
    assert body["bio"] == "Compiler pioneer."
    assert body["avatar_url"] == "https://example.com/a.png"

    me = anon_client.get("/api/auth/me", headers=headers).json()
    assert me["display_name"] == "Grace Hopper"


def test_update_profile_clears_fields_with_null(anon_client):
    headers = auth_headers(anon_client, "clear@papertrail.io")
    anon_client.patch("/api/auth/me", json={"bio": "temp"}, headers=headers)
    res = anon_client.patch("/api/auth/me", json={}, headers=headers)
    assert res.status_code == 200
    assert res.json()["bio"] is None


def test_update_profile_requires_auth(anon_client):
    assert anon_client.patch("/api/auth/me", json={"display_name": "x"}).status_code == 401


# --------------------------- change password ----------------------------- #
def test_change_password_requires_current_password(anon_client):
    headers = auth_headers(anon_client, "pw1@papertrail.io", "original-pw1")
    res = anon_client.post(
        "/api/auth/change-password",
        json={"current_password": "wrong-pw", "new_password": "newpassword1"},
        headers=headers,
    )
    assert res.status_code == 401


def test_change_password_rejects_weak_new_password(anon_client):
    headers = auth_headers(anon_client, "pw2@papertrail.io", "original-pw1")
    res = anon_client.post(
        "/api/auth/change-password",
        json={"current_password": "original-pw1", "new_password": "allletters"},
        headers=headers,
    )
    assert res.status_code == 422


def test_change_password_updates_and_revokes_other_sessions(anon_client):
    headers = auth_headers(anon_client, "pw3@papertrail.io", "original-pw1")
    # Grab a refresh token for the still-live session before the change.
    from app.config import settings

    old_refresh = anon_client.cookies.get(settings.refresh_cookie_name)

    res = anon_client.post(
        "/api/auth/change-password",
        json={"current_password": "original-pw1", "new_password": "new-password-2"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    # Old refresh token (issued before the change) is now rejected.
    anon_client.cookies.clear()
    stale = anon_client.post(
        "/api/auth/refresh", headers={"Authorization": f"Bearer {old_refresh}"}
    )
    assert stale.status_code == 401

    # New password logs in; old password no longer works.
    ok = anon_client.post(
        "/api/auth/login",
        json={"email": "pw3@papertrail.io", "password": "new-password-2"},
    )
    assert ok.status_code == 200
    bad = anon_client.post(
        "/api/auth/login",
        json={"email": "pw3@papertrail.io", "password": "original-pw1"},
    )
    assert bad.status_code == 401


# ------------------------------ deletion --------------------------------- #
def test_delete_account_removes_user_and_owned_documents(anon_client, db_session):
    from app.models import Document, User

    headers = auth_headers(anon_client, "delete-me@papertrail.io")
    up = anon_client.post(
        "/api/documents/upload",
        files={"file": ("note.txt", b"hello world", "text/plain")},
        headers=headers,
    )
    assert up.status_code == 200, up.text
    doc_id = up.json()["id"]

    res = anon_client.delete("/api/auth/me", headers=headers)
    assert res.status_code == 200, res.text

    # The account and its documents are gone; the token is now orphaned.
    assert anon_client.get("/api/auth/me", headers=headers).status_code == 401
    assert db_session.get(User, doc_id) is None
    assert db_session.get(Document, doc_id) is None


def test_delete_account_requires_auth(anon_client):
    assert anon_client.delete("/api/auth/me").status_code == 401


# --------------------------- forgot / reset ------------------------------- #
def test_forgot_password_is_silent_for_unknown_email(anon_client):
    res = anon_client.post(
        "/api/auth/forgot-password", json={"email": "nobody-here@papertrail.io"}
    )
    assert res.status_code == 200
    assert "If that email is registered" in res.json()["detail"]


def test_forgot_password_then_reset_password_flow(anon_client, db_session, caplog):
    import logging
    import re

    register_and_token(anon_client, "reset-me@papertrail.io", "original-pw1")

    with caplog.at_level(logging.INFO, logger="papertrail.auth"):
        res = anon_client.post(
            "/api/auth/forgot-password", json={"email": "reset-me@papertrail.io"}
        )
    assert res.status_code == 200

    match = re.search(r"reset-password\?token=(\S+)", caplog.text)
    assert match, caplog.text
    raw_token = match.group(1)

    reset = anon_client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "new_password": "brand-new-pw2"},
    )
    assert reset.status_code == 200, reset.text

    # New password works; old one doesn't.
    ok = anon_client.post(
        "/api/auth/login",
        json={"email": "reset-me@papertrail.io", "password": "brand-new-pw2"},
    )
    assert ok.status_code == 200
    bad = anon_client.post(
        "/api/auth/login",
        json={"email": "reset-me@papertrail.io", "password": "original-pw1"},
    )
    assert bad.status_code == 401

    # The token is single-use.
    replay = anon_client.post(
        "/api/auth/reset-password",
        json={"token": raw_token, "new_password": "another-pw3"},
    )
    assert replay.status_code == 400


def test_reset_password_rejects_invalid_token(anon_client):
    res = anon_client.post(
        "/api/auth/reset-password",
        json={"token": "not-a-real-token", "new_password": "whatever12"},
    )
    assert res.status_code == 400
