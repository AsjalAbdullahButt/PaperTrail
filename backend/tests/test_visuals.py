"""Phase 5: mind map data, timeline extraction, timeline caching."""
from __future__ import annotations

import app.services.visuals as visuals
from app.services.visuals import _parse_events, build_mindmap
from ._helpers import upload_text_doc

from conftest import requires_db

pytestmark = requires_db


# ------------------------------ unit ------------------------------------ #
def test_parse_events_valid():
    raw = '[{"date":"2020","event":"Founded","chunk_index":1}]'
    events = _parse_events(raw)
    assert events == [{"date": "2020", "event": "Founded", "chunk_index": 1}]


def test_parse_events_empty_and_garbage():
    assert _parse_events("") == []
    assert _parse_events("no json here") == []
    assert _parse_events("[]") == []


# --------------------------- mind map (DB) ------------------------------ #
def test_mindmap_returns_nodes_and_edges(client):
    upload_text_doc(
        client,
        "space.txt",
        "Neptune is the eighth planet from the sun and orbits every 165 years. " * 20,
    )
    q = client.post("/api/query", json={"question": "Tell me about Neptune", "mode": "rag"})
    qid = q.json()["query_id"]

    res = client.get(f"/api/queries/{qid}/mindmap")
    assert res.status_code == 200
    data = res.json()
    # A query node plus at least one chunk node.
    assert any(n["type"] == "query" for n in data["nodes"])
    assert any(n["type"] == "chunk" for n in data["nodes"])
    # Every query->chunk edge starts at the query node.
    q_edges = [e for e in data["edges"] if e["source"] == "q"]
    assert q_edges


def test_mindmap_cross_user_forbidden(client, anon_client):
    from conftest import auth_headers

    upload_text_doc(client, "x.txt", "content about turbines and engines " * 20)
    qid = client.post("/api/query", json={"question": "turbines", "mode": "rag"}).json()["query_id"]
    other = auth_headers(anon_client, "peeker@papertrail.io")
    assert anon_client.get(f"/api/queries/{qid}/mindmap", headers=other).status_code == 403


# --------------------------- timeline (DB) ------------------------------ #
def test_timeline_empty_when_no_dates_offline(client):
    upload_text_doc(client, "nodate.txt", "A general note with no dates whatsoever. " * 10)
    doc_id = client.get("/api/documents").json()[0]["id"]
    res = client.get(f"/api/documents/{doc_id}/timeline")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_timeline_is_cached(client, monkeypatch):
    upload_text_doc(client, "dated.txt", "In 1969 humans landed on the moon. " * 10)
    doc_id = client.get("/api/documents").json()[0]["id"]

    calls = {"n": 0}

    def fake_complete(*args, **kwargs):
        calls["n"] += 1
        return '[{"date":"1969","event":"Moon landing","chunk_index":0}]'

    monkeypatch.setattr(visuals.llm, "complete_text", fake_complete)

    first = client.get(f"/api/documents/{doc_id}/timeline")
    second = client.get(f"/api/documents/{doc_id}/timeline")
    assert first.status_code == 200 and second.status_code == 200
    assert first.json() == second.json()
    # The model was called at most once; the second request hit the cache.
    assert calls["n"] <= 1
