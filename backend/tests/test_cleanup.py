"""Data-lifecycle cleanup: purge, token/failed-upload cleanup, storage-key
collection, and the cross-worker retrieval-index invalidation.

These tests use a private in-memory SQLite database (foreign keys enforced) and
fake storage/Redis objects, so they never touch the configured MySQL database
and run even when none is reachable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.storage as storage_module
from app import cleanup
from app.cache import InMemoryCache, RedisCache, get_or_build_object
from app.database import (
    Base,
    document_storage_keys,
    purge_soft_deleted,
    user_storage_keys,
)
from app.models import (
    ChatHistory,
    Chunk,
    Document,
    DocumentVersion,
    PasswordResetToken,
    TokenBlacklist,
    User,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture()
def factory():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # SQLite ignores FKs unless asked
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


class FakeStorage:
    def __init__(self, failing: set[str] | None = None):
        self.deleted: list[str] = []
        self.failing = failing or set()

    def delete(self, key: str) -> None:
        if key in self.failing:
            raise RuntimeError("boom")
        self.deleted.append(key)


@pytest.fixture()
def fake_storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(storage_module, "storage", fake)
    return fake


def _user(db, email="u@x.io") -> User:
    u = User(email=email, hashed_password="x")
    db.add(u)
    db.commit()
    return u


def _doc(db, user, *, key=None, deleted_days_ago=None, status="done", age_days=0, age_minutes=0):
    d = Document(
        user_id=user.id, filename="f.txt", file_type="txt", storage_key=key,
        processing_status=status,
        created_at=_now() - timedelta(days=age_days, minutes=age_minutes),
        deleted_at=(_now() - timedelta(days=deleted_days_ago)) if deleted_days_ago else None,
    )
    db.add(d)
    db.commit()
    return d


def _count(db, model) -> int:
    return db.execute(select(func.count()).select_from(model)).scalar_one()


# ---------------------------------------------------------------- purge ----
def test_purge_removes_expired_doc_its_chunks_and_all_version_files(factory, fake_storage):
    with factory() as db:
        u = _user(db)
        d = _doc(db, u, key="uploads/u/v3.txt", deleted_days_ago=31)
        db.add_all([
            DocumentVersion(document_id=d.id, version_number=1, storage_key="uploads/u/v1.txt"),
            DocumentVersion(document_id=d.id, version_number=2, storage_key="uploads/u/v2.txt"),
            Chunk(document_id=d.id, chunk_index=0, content="c", embedding="[]"),
        ])
        db.commit()

    assert purge_soft_deleted(30, session_factory=factory) == 1

    assert sorted(fake_storage.deleted) == [
        "uploads/u/v1.txt", "uploads/u/v2.txt", "uploads/u/v3.txt",
    ]
    with factory() as db:
        assert _count(db, Document) == 0
        assert _count(db, Chunk) == 0 and _count(db, DocumentVersion) == 0


def test_purge_keeps_documents_inside_retention_window(factory, fake_storage):
    with factory() as db:
        u = _user(db)
        _doc(db, u, key="uploads/u/a.txt", deleted_days_ago=5)
        _doc(db, u, key="uploads/u/live.txt")
    assert purge_soft_deleted(30, session_factory=factory) == 0
    assert fake_storage.deleted == []
    with factory() as db:
        assert _count(db, Document) == 2


def test_purge_keeps_row_when_a_file_cannot_be_deleted_and_continues(factory, monkeypatch):
    fake = FakeStorage(failing={"uploads/u/bad.txt"})
    monkeypatch.setattr(storage_module, "storage", fake)
    with factory() as db:
        u = _user(db)
        _doc(db, u, key="uploads/u/bad.txt", deleted_days_ago=40)
        _doc(db, u, key="uploads/u/good.txt", deleted_days_ago=40)

    assert purge_soft_deleted(30, session_factory=factory) == 1

    with factory() as db:
        remaining = db.execute(select(Document.storage_key)).scalars().all()
        assert remaining == ["uploads/u/bad.txt"]  # retried on the next run


def test_purge_removes_expired_chat_rows_only(factory, fake_storage):
    with factory() as db:
        u = _user(db)
        db.add_all([
            ChatHistory(user_id=u.id, question="q", answer="a", mode="rag",
                        deleted_at=_now() - timedelta(days=40)),
            ChatHistory(user_id=u.id, question="q", answer="a", mode="rag",
                        deleted_at=_now() - timedelta(days=2)),
            ChatHistory(user_id=u.id, question="q", answer="a", mode="rag"),
        ])
        db.commit()
    purge_soft_deleted(30, session_factory=factory)
    with factory() as db:
        assert _count(db, ChatHistory) == 2


# --------------------------------------------------------- storage keys ----
def test_storage_key_collectors_include_archived_versions(factory):
    with factory() as db:
        u = _user(db)
        other = _user(db, "o@x.io")
        d = _doc(db, u, key="k-current")
        _doc(db, u, key=None)  # store_originals off -> no key
        _doc(db, other, key="k-other")
        db.add(DocumentVersion(document_id=d.id, version_number=1, storage_key="k-old"))
        db.commit()

        assert sorted(document_storage_keys(db, d.id)) == ["k-current", "k-old"]
        assert sorted(user_storage_keys(db, u.id)) == ["k-current", "k-old"]


# ------------------------------------------------------------- cleanup ----
def test_run_cleanup_removes_dead_tokens_and_keeps_live_ones(factory, fake_storage):
    with factory() as db:
        u = _user(db)
        db.add_all([
            TokenBlacklist(jti="dead", user_id=u.id, expires_at=_now() - timedelta(days=3)),
            TokenBlacklist(jti="live", user_id=u.id, expires_at=_now() + timedelta(days=3)),
            TokenBlacklist(jti="just-expired", user_id=u.id, expires_at=_now() - timedelta(hours=2)),
            PasswordResetToken(user_id=u.id, token_hash="a" * 64, expires_at=_now() - timedelta(days=60)),
            PasswordResetToken(user_id=u.id, token_hash="b" * 64, expires_at=_now() - timedelta(days=2)),
            PasswordResetToken(user_id=u.id, token_hash="c" * 64, expires_at=_now() + timedelta(hours=1)),
        ])
        db.commit()

    counts = cleanup.run_cleanup(session_factory=factory)

    assert counts["blacklist_rows_removed"] == 1
    assert counts["reset_tokens_removed"] == 1
    with factory() as db:
        assert set(db.execute(select(TokenBlacklist.jti)).scalars()) == {"live", "just-expired"}
        assert _count(db, PasswordResetToken) == 2


def test_run_cleanup_fails_stuck_then_removes_old_failed_documents(factory, fake_storage):
    with factory() as db:
        u = _user(db)
        stuck = _doc(db, u, status="processing", age_minutes=180)
        fresh = _doc(db, u, status="processing", age_minutes=2)
        old_failed = _doc(db, u, status="failed", age_days=10)
        new_failed = _doc(db, u, status="failed", age_days=1)
        done = _doc(db, u, status="done", age_days=100)
        ids = {k: v.id for k, v in dict(
            stuck=stuck, fresh=fresh, old_failed=old_failed, new_failed=new_failed, done=done,
        ).items()}

    counts = cleanup.run_cleanup(session_factory=factory)

    assert counts["stuck_documents_failed"] == 1
    assert counts["failed_documents_removed"] == 1
    with factory() as db:
        status = {d.id: d.processing_status for d in db.execute(select(Document)).scalars()}
        assert ids["old_failed"] not in status
        assert status[ids["stuck"]] == "failed"
        assert status[ids["fresh"]] == "processing"
        assert status[ids["new_failed"]] == "failed"
        assert status[ids["done"]] == "done"
        stuck_row = db.get(Document, ids["stuck"])
        assert stuck_row.processing_error == cleanup.STUCK_MESSAGE


def test_run_cleanup_is_idempotent(factory, fake_storage):
    with factory() as db:
        u = _user(db)
        _doc(db, u, key="k", deleted_days_ago=40)
    first = cleanup.run_cleanup(session_factory=factory)
    second = cleanup.run_cleanup(session_factory=factory)
    assert first["documents_purged"] == 1
    assert not any(second.values())


# --------------------------------------- cross-worker index invalidation ----
class FakeRedis:
    """Just enough of redis.Redis for RedisCache's invalidate/generation path."""

    def __init__(self):
        self.data: dict[str, str] = {}

    def get(self, k):
        return self.data.get(k)

    def set(self, k, v, nx=False, ex=None):
        if nx and k in self.data:
            return None
        self.data[k] = v
        return True

    def incr(self, k):
        self.data[k] = str(int(self.data.get(k, "0")) + 1)

    def scan_iter(self, match):
        prefix = match.rstrip("*")
        return [k for k in list(self.data) if k.startswith(prefix)]

    def delete(self, k):
        self.data.pop(k, None)


def _redis_cache(shared: FakeRedis) -> RedisCache:
    c = object.__new__(RedisCache)
    c._redis = shared
    return c


def test_generation_changes_even_if_local_object_cache_survives():
    """Directly models the bug: the entry built under the old generation must
    not be served once the shared generation moves on."""
    shared = FakeRedis()
    cache = _redis_cache(shared)
    key = "qcache:u2:retrieval:index"
    old = object()
    get_or_build_object(key, lambda: old, cache.generation("u2"))

    shared.incr("qgen:u2")  # another worker's invalidate_prefix

    new = object()
    assert get_or_build_object(key, lambda: new, cache.generation("u2")) is new


def test_in_memory_cache_generation_bumps_on_invalidate():
    c = InMemoryCache()
    g0 = c.generation("u3")
    c.invalidate_prefix("qcache:u3:")
    assert c.generation("u3") != g0
    assert c.generation("someone-else") == g0


def test_try_lock_is_exclusive_on_redis():
    shared = FakeRedis()
    a, b = _redis_cache(shared), _redis_cache(shared)
    assert a.try_lock("cleanup", 60) is True
    assert b.try_lock("cleanup", 60) is False
