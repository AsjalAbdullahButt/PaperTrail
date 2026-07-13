"""Router coverage for POST /api/query/stream (SSE)."""
from __future__ import annotations

import json

import app.routers.query as query_router
from ._helpers import upload_text_doc

from conftest import requires_db

pytestmark = requires_db


def _parse_sse(text: str) -> list[tuple[str | None, dict]]:
    """Parse ``event: X\\ndata: Y\\n\\n`` blocks into ``[(event, data), ...]``."""
    events: list[tuple[str | None, dict]] = []
    for block in text.strip().split("\n\n"):
        if not block.strip():
            continue
        event = None
        data: dict = {}
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:"):].strip())
        events.append((event, data))
    return events


def _fake_stream(*tokens: str):
    def _stream(question, context_chunks, history=None):
        yield from tokens

    return _stream


def test_query_stream_returns_valid_sse_with_sources_before_tokens(client, monkeypatch):
    upload_text_doc(
        client,
        "facts.txt",
        "The capital of the fictional country Zubrowka is Lutz. "
        "Lutz is home to the grand budapest hotel.",
    )
    monkeypatch.setattr(
        query_router.llm, "stream_rag_answer", _fake_stream("Lutz ", "is the capital.")
    )

    res = client.post(
        "/api/query/stream",
        json={"question": "What is the capital of Zubrowka?", "mode": "rag"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(res.text)
    names = [e for e, _ in events]

    assert names[0] == "sources"
    assert names[-1] == "done"
    assert "token" in names
    assert names.index("sources") < names.index("token")

    sources_data = events[names.index("sources")][1]
    assert sources_data["sources"][0]["title"] == "facts.txt"

    token_events = [d for e, d in events if e == "token"]
    assert "".join(t["token"] for t in token_events) == "Lutz is the capital."

    done_data = events[-1][1]
    assert "query_id" in done_data and done_data["query_id"]
    assert "followups" in names
    assert "hallucination" in names


def test_query_stream_empty_corpus_emits_done_last_with_empty_sources(client, monkeypatch):
    monkeypatch.setattr(query_router.llm, "stream_rag_answer", _fake_stream("should not be called"))

    res = client.post(
        "/api/query/stream", json={"question": "anything?", "mode": "rag"}
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    names = [e for e, _ in events]

    assert names[0] == "sources"
    assert events[names.index("sources")][1]["sources"] == []
    assert names[-1] == "done"

    token_events = [d for e, d in events if e == "token"]
    assert len(token_events) == 1
    assert "no documents" in token_events[0]["token"].lower()


def test_query_stream_persists_chat_history(client, db_session, monkeypatch):
    from sqlalchemy import select

    from app.models import ChatHistory

    upload_text_doc(client, "notes.txt", "Quarterly revenue grew significantly this year overall.")
    monkeypatch.setattr(query_router.llm, "stream_rag_answer", _fake_stream("Revenue grew."))

    res = client.post(
        "/api/query/stream", json={"question": "How did revenue change?", "mode": "rag"}
    )
    assert res.status_code == 200
    events = _parse_sse(res.text)
    done_data = dict(events)["done"]

    row = db_session.get(ChatHistory, done_data["query_id"])
    assert row is not None
    assert row.answer == "Revenue grew."


def test_query_stream_direct_mode_skips_retrieval(client, monkeypatch):
    monkeypatch.setattr(
        query_router.llm,
        "generate_answer",
        lambda q, chunks, mode, history=None: "A direct answer.",
    )
    res = client.post("/api/query/stream", json={"question": "hi", "mode": "direct"})
    assert res.status_code == 200
    events = _parse_sse(res.text)
    names = [e for e, _ in events]
    assert names[0] == "sources"
    assert dict(events)["sources"]["sources"] == []
    assert names[-1] == "done"
    token_events = [d for e, d in events if e == "token"]
    assert token_events[0]["token"] == "A direct answer."
