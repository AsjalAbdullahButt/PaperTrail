"""Phase 6: analytics overview, top queries, document usage, coverage gaps."""
from __future__ import annotations

from ._helpers import upload_text_doc

from conftest import auth_headers, requires_db

pytestmark = requires_db


def _seed(client):
    upload_text_doc(client, "alpha.txt", "Alpha content about revenue and growth. " * 20)
    upload_text_doc(client, "beta.txt", "Beta content about turbines and engines. " * 20)
    client.post("/api/query", json={"question": "revenue growth", "mode": "rag"})
    client.post("/api/query", json={"question": "revenue growth", "mode": "rag"})
    client.post("/api/query", json={"question": "turbines", "mode": "rag"})


def test_overview_counts_match(client):
    _seed(client)
    res = client.get("/api/analytics/overview")
    assert res.status_code == 200
    body = res.json()
    assert body["total_documents"] == 2
    assert body["total_queries"] == 3
    assert body["total_chunks"] >= 2
    assert 0.0 <= body["avg_confidence"] <= 1.0
    assert len(body["queries_this_week"]) == 7


def test_overview_empty_user(client):
    res = client.get("/api/analytics/overview")
    body = res.json()
    assert body["total_documents"] == 0
    assert body["total_queries"] == 0
    assert body["most_queried_document"] is None


def test_top_queries_ranks_by_frequency(client):
    _seed(client)
    res = client.get("/api/analytics/top-queries?limit=5")
    data = res.json()
    assert data
    assert data[0]["query"] == "revenue growth"
    assert data[0]["count"] == 2


def test_document_usage_reports_retrievals(client):
    _seed(client)
    res = client.get("/api/analytics/document-usage")
    data = res.json()
    assert data
    for row in data:
        assert row["total_retrievals"] >= 1
        assert 0.0 <= row["avg_similarity"] <= 1.5


def test_coverage_gaps_flags_unqueried_docs(client):
    # Upload a doc but never query it -> 100% unexplored.
    upload_text_doc(client, "lonely.txt", "Never queried content here. " * 30)
    res = client.get("/api/analytics/coverage-gaps")
    data = res.json()
    assert any(g["unexplored_pct"] > 40 for g in data)


def test_analytics_is_user_isolated(client, anon_client):
    _seed(client)
    other = auth_headers(anon_client, "analyst-b@papertrail.io")
    res = anon_client.get("/api/analytics/overview", headers=other)
    body = res.json()
    assert body["total_documents"] == 0
    assert body["total_queries"] == 0


def test_analytics_requires_auth(anon_client):
    assert anon_client.get("/api/analytics/overview").status_code == 401
