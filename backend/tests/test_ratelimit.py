"""Rate-limiting tests (Phase 4). Uses in-process storage (no Redis needed)."""
from __future__ import annotations

import app.ratelimit as ratelimit
import app.routers.documents as documents_router
import app.routers.query as query_router

from conftest import requires_db

pytestmark = requires_db


def test_query_rate_limit_returns_429_after_window(client, monkeypatch):
    # Tighten the limit so we can trip it deterministically. Direct mode still
    # calls the LLM layer, so stub it out — these assertions are about the
    # rate limiter's request counting, not real model latency (a slow/rate
    # -limited real provider retry could otherwise let the window roll over
    # between requests and make this test flaky).
    monkeypatch.setattr(query_router.llm, "generate_answer", lambda q, chunks, mode, history=None: "ok")
    monkeypatch.setattr(ratelimit.settings, "rate_limit_query", "3/minute")

    statuses = []
    for _ in range(5):
        res = client.post("/api/query", json={"question": "ping", "mode": "direct"})
        statuses.append(res.status_code)

    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses[3:]
    # The 429 uses the structured error envelope.
    last = client.post("/api/query", json={"question": "ping", "mode": "direct"})
    assert last.status_code == 429
    assert last.json()["error"]["status_code"] == 429


def test_upload_rate_limit_returns_429(client, monkeypatch):
    # Stub the summary call — a slow/rate-limited real provider retry (up to
    # ~60s of backoff) could let the 1-minute rate-limit window roll over
    # between these sequential uploads and make this test flaky.
    monkeypatch.setattr(documents_router.llm, "summarize_document", lambda title, texts: "")
    monkeypatch.setattr(ratelimit.settings, "rate_limit_upload", "2/minute")

    def _upload():
        return client.post(
            "/api/documents/upload",
            files={"file": ("d.txt", b"hello world content", "text/plain")},
        )

    assert _upload().status_code == 200
    assert _upload().status_code == 200
    assert _upload().status_code == 429


def test_rate_limit_is_per_user(anon_client, monkeypatch):
    from conftest import auth_headers

    monkeypatch.setattr(query_router.llm, "generate_answer", lambda q, chunks, mode, history=None: "ok")
    monkeypatch.setattr(ratelimit.settings, "rate_limit_query", "2/minute")
    a = auth_headers(anon_client, "rl-a@papertrail.io")
    b = auth_headers(anon_client, "rl-b@papertrail.io")

    # User A exhausts their budget.
    for _ in range(3):
        anon_client.post("/api/query", json={"question": "q", "mode": "direct"}, headers=a)
    a_blocked = anon_client.post(
        "/api/query", json={"question": "q", "mode": "direct"}, headers=a
    )
    assert a_blocked.status_code == 429

    # User B is unaffected by A's usage.
    b_ok = anon_client.post(
        "/api/query", json={"question": "q", "mode": "direct"}, headers=b
    )
    assert b_ok.status_code == 200
