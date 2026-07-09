"""Query-response cache with a pluggable backend.

Backend selection:
  * Redis (``REDIS_URL`` set) — shared across all API workers, so a horizontally
    scaled deployment gets cache hits regardless of which worker serves the
    request. Required for real multi-worker caching.
  * In-process dict with TTL (default) — correct for a single worker / local dev
    and tests. NOT shared across workers.

Keys are namespaced per user so invalidation on a user's document change never
touches another user's cache.
"""
from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from threading import RLock
from typing import Protocol

from .config import settings

_WS_RE = re.compile(r"\s+")


def make_query_key(user_id: str, question: str, mode: str) -> str:
    """Stable cache key for (user, normalized question, mode)."""
    normalized = _WS_RE.sub(" ", question.strip().lower())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"qcache:{user_id}:{mode}:{digest}"


def user_prefix(user_id: str) -> str:
    return f"qcache:{user_id}:"


def retrieval_index_key(user_id: str) -> str:
    """Stable cache key for per-user retrieval indexes (BM25 + ANN metadata)."""
    return f"{user_prefix(user_id)}retrieval:index"


class CacheBackend(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int) -> None: ...
    def invalidate_prefix(self, prefix: str) -> None: ...


class InMemoryCache:
    """Process-local TTL cache. Not shared across workers."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> str | None:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, ttl: int) -> None:
        if ttl <= 0:
            return
        self._store[key] = (time.time() + ttl, value)

    def invalidate_prefix(self, prefix: str) -> None:
        for key in [k for k in self._store if k.startswith(prefix)]:
            self._store.pop(key, None)
        invalidate_object_prefix(prefix)

    def clear(self) -> None:
        self._store.clear()
        clear_object_cache()


class RedisCache:
    """Redis-backed cache shared across workers."""

    def __init__(self, url: str) -> None:
        import redis

        self._redis = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> str | None:
        return self._redis.get(key)

    def set(self, key: str, value: str, ttl: int) -> None:
        if ttl <= 0:
            return
        self._redis.set(key, value, ex=ttl)

    def invalidate_prefix(self, prefix: str) -> None:
        # SCAN avoids blocking Redis on large keyspaces.
        for key in self._redis.scan_iter(match=f"{prefix}*"):
            self._redis.delete(key)
        invalidate_object_prefix(prefix)


def _build_cache() -> CacheBackend:
    if settings.redis_url:
        try:
            return RedisCache(settings.redis_url)
        except Exception:  # noqa: BLE001 - never let cache init break the app
            pass
    return InMemoryCache()


# Module-level singleton used by the query router.
cache: CacheBackend = _build_cache()


# Process-local object cache for heavy, non-JSON data structures (e.g. retrieval
# indexes). We keep it in this module so it is invalidated by the same
# cache.invalidate_prefix(user_prefix(...)) hooks used for query-response cache.
_object_cache: dict[str, object] = {}
_object_cache_lock = RLock()


def get_or_build_object(key: str, factory: Callable[[], object]) -> object:
    with _object_cache_lock:
        cached = _object_cache.get(key)
        if cached is not None:
            return cached
        built = factory()
        _object_cache[key] = built
        return built


def invalidate_object_prefix(prefix: str) -> None:
    with _object_cache_lock:
        for key in [k for k in _object_cache if k.startswith(prefix)]:
            _object_cache.pop(key, None)


def clear_object_cache() -> None:
    with _object_cache_lock:
        _object_cache.clear()
