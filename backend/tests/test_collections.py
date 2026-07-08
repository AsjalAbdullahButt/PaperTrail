"""Phase 4: collections, tags, versions, coverage, duplicate detection,
query history + bookmarks."""
from __future__ import annotations

import io

from ._helpers import upload_bytes, upload_text_doc

from conftest import auth_headers, requires_db

pytestmark = requires_db


def _create_collection(client, name="Research"):
    res = client.post("/api/collections", json={"name": name, "description": "d"})
    assert res.status_code == 201, res.text
    return res.json()


# ------------------------------ collections ----------------------------- #
def test_collection_crud_and_membership(client):
    coll = _create_collection(client)
    doc = upload_text_doc(client, "d1.txt", "content about turbines and engines " * 10)

    add = client.post(f"/api/collections/{coll['id']}/documents", json={"document_ids": [doc["id"]]})
    assert add.status_code == 200
    assert add.json()["document_count"] == 1

    docs = client.get(f"/api/collections/{coll['id']}/documents")
    assert docs.status_code == 200 and len(docs.json()) == 1

    # Rename.
    upd = client.put(f"/api/collections/{coll['id']}", json={"name": "Renamed"})
    assert upd.json()["name"] == "Renamed"


def test_collection_scoped_query_only_returns_member_docs(client):
    coll = _create_collection(client)
    inside = upload_text_doc(client, "inside.txt", "The passphrase is orangutan. " * 20)
    upload_text_doc(client, "outside.txt", "Nothing relevant about fruit here. " * 20)
    client.post(f"/api/collections/{coll['id']}/documents", json={"document_ids": [inside["id"]]})

    res = client.post(
        "/api/query",
        json={"question": "what is the passphrase", "mode": "rag", "collection_id": coll["id"]},
    )
    body = res.json()
    assert body["sources"]
    assert all(s["document_id"] == inside["id"] for s in body["sources"])


def test_delete_collection_keeps_documents(client):
    coll = _create_collection(client)
    doc = upload_text_doc(client, "keep.txt", "keep me around " * 10)
    client.post(f"/api/collections/{coll['id']}/documents", json={"document_ids": [doc["id"]]})

    assert client.delete(f"/api/collections/{coll['id']}").status_code == 200
    # Collection gone...
    assert client.get(f"/api/collections/{coll['id']}/documents").status_code == 404
    # ...but the document still exists.
    docs = {d["id"] for d in client.get("/api/documents").json()}
    assert doc["id"] in docs


def test_collection_cross_user_forbidden(client, anon_client):
    coll = _create_collection(client)
    other = auth_headers(anon_client, "outsider@papertrail.io")
    res = anon_client.put(f"/api/collections/{coll['id']}", json={"name": "hax"}, headers=other)
    assert res.status_code == 403


def test_update_missing_collection_returns_404(client):
    assert client.put("/api/collections/nope", json={"name": "x"}).status_code == 404


def test_list_collections_reports_counts(client):
    coll = _create_collection(client, "Counted")
    doc = upload_text_doc(client, "c.txt", "counted content " * 10)
    client.post(f"/api/collections/{coll['id']}/documents", json={"document_ids": [doc["id"]]})
    listing = client.get("/api/collections").json()
    match = next(c for c in listing if c["id"] == coll["id"])
    assert match["document_count"] == 1


def test_remove_document_from_collection(client):
    coll = _create_collection(client)
    doc = upload_text_doc(client, "rm.txt", "removable content " * 10)
    client.post(f"/api/collections/{coll['id']}/documents", json={"document_ids": [doc["id"]]})
    res = client.delete(f"/api/collections/{coll['id']}/documents/{doc['id']}")
    assert res.status_code == 200
    assert client.get(f"/api/collections/{coll['id']}/documents").json() == []
    # Removing again -> 404 (not a member).
    assert client.delete(f"/api/collections/{coll['id']}/documents/{doc['id']}").status_code == 404


# --------------------------------- tags --------------------------------- #
def test_add_and_remove_tags(client):
    doc = upload_text_doc(client, "tagged.txt", "some content " * 10)
    res = client.post(f"/api/documents/{doc['id']}/tags", json={"tags": ["finance", "q3"]})
    assert res.status_code == 200
    assert set(res.json()["tags"]) == {"finance", "q3"}

    rm = client.delete(f"/api/documents/{doc['id']}/tags/finance")
    assert rm.json()["tags"] == ["q3"]


def test_tag_filter_lists_only_matching(client):
    d1 = upload_text_doc(client, "a.txt", "alpha " * 10)
    upload_text_doc(client, "b.txt", "beta " * 10)
    client.post(f"/api/documents/{d1['id']}/tags", json={"tags": ["special"]})
    res = client.get("/api/documents?tag=special")
    ids = {d["id"] for d in res.json()}
    assert ids == {d1["id"]}


def test_invalid_tag_rejected(client):
    doc = upload_text_doc(client, "t.txt", "x " * 10)
    res = client.post(f"/api/documents/{doc['id']}/tags", json={"tags": ["not valid!"]})
    assert res.status_code == 422


# ------------------------------- versions ------------------------------- #
def test_upload_version_bumps_number(client):
    doc = upload_text_doc(client, "v.txt", "version one content " * 10)
    res = client.post(
        f"/api/documents/{doc['id']}/upload-version",
        files={"file": ("v2.txt", b"version two content", "text/plain")},
    )
    assert res.status_code == 200
    assert res.json()["version_number"] == 2
    versions = client.get(f"/api/documents/{doc['id']}/versions")
    assert len(versions.json()) == 1  # the archived v1


# --------------------------- duplicate detection ------------------------ #
def test_duplicate_detection_flags_near_identical(client):
    body_text = "The mitochondria is the powerhouse of the cell in biology. " * 30
    upload_text_doc(client, "orig.txt", body_text)
    dup = upload_bytes(client, "copy.txt", body_text.encode(), "text/plain")
    assert dup.status_code == 200
    payload = dup.json()
    assert payload["is_duplicate"] is True
    assert payload["duplicate_of_name"] == "orig.txt"


# -------------------------------- coverage ------------------------------ #
def test_coverage_reports_retrieval_counts(client):
    doc = upload_text_doc(client, "cov.txt", "quantum entanglement spooky action " * 20)
    client.post("/api/query", json={"question": "quantum entanglement", "mode": "rag"})
    res = client.get(f"/api/documents/{doc['id']}/coverage")
    assert res.status_code == 200
    cells = res.json()
    assert len(cells) >= 1
    assert any(c["retrieved_count"] >= 1 for c in cells)


# --------------------------- query history / bookmarks ------------------ #
def test_query_history_and_bookmark_persist(client):
    upload_text_doc(client, "h.txt", "the sky is blue during the day " * 10)
    q = client.post("/api/query", json={"question": "why is the sky blue", "mode": "rag"})
    qid = q.json()["query_id"]
    assert qid

    hist = client.get("/api/queries")
    assert hist.json()["total"] >= 1

    bm = client.post(f"/api/queries/{qid}/bookmark", json={"note": "interesting"})
    assert bm.json()["bookmarked"] is True
    assert bm.json()["bookmark_note"] == "interesting"

    marks = client.get("/api/queries/bookmarks")
    assert any(m["id"] == qid for m in marks.json())

    # Toggle off.
    off = client.post(f"/api/queries/{qid}/bookmark")
    assert off.json()["bookmarked"] is False


def test_delete_query_removes_from_history(client):
    upload_text_doc(client, "d.txt", "content to query " * 10)
    qid = client.post("/api/query", json={"question": "content", "mode": "rag"}).json()["query_id"]
    assert client.delete(f"/api/queries/{qid}").status_code == 200
    remaining = client.get("/api/queries").json()
    assert all(item["id"] != qid for item in remaining["items"])
