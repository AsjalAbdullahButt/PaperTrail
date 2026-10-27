"""Coverage for GET /api/chat-history (persisted on every query)."""
from __future__ import annotations

from conftest import requires_db

pytestmark = requires_db


def test_chat_history_records_and_paginates_newest_first(client):
    # Each query persists a ChatHistory row.
    client.post("/api/query", json={"question": "first question", "mode": "direct"})
    client.post("/api/query", json={"question": "second question", "mode": "direct"})

    res = client.get("/api/chat-history")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 2
    assert body["items"][0]["question"] == "second question"  # newest first
    assert body["items"][0]["mode"] == "direct"


def test_chat_history_pagination_params(client):
    for i in range(3):
        client.post("/api/query", json={"question": f"q{i}", "mode": "direct"})

    page = client.get("/api/chat-history?limit=1&offset=0")
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["limit"] == 1

    assert client.get("/api/chat-history?limit=0").status_code == 422
    assert client.get("/api/chat-history?limit=1000").status_code == 422


def test_chat_history_excludes_soft_deleted_queries(client):
    keep = client.post("/api/query", json={"question": "keep me", "mode": "direct"})
    drop = client.post("/api/query", json={"question": "delete me", "mode": "direct"})
    assert keep.status_code == drop.status_code == 200

    # Locate the row to delete via the query-history listing, then soft-delete it.
    items = client.get("/api/queries").json()["items"]
    target = next(i for i in items if i["question"] == "delete me")
    assert client.delete(f"/api/queries/{target['id']}").status_code == 200

    body = client.get("/api/chat-history").json()
    questions = [i["question"] for i in body["items"]]
    assert "delete me" not in questions
    assert "keep me" in questions
    assert body["total"] == len(questions)
