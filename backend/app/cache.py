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
from typing import Protocol

from .config import settings

_WS_RE = re.compile(r"\s+")


def make_query_key(user_id: int, question: str, mode: str) -> str:
    """Stable cache key for (user, normalized question, mode)."""
    normalized = _WS_RE.sub(" ", question.strip().lower())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"qcache:{user_id}:{mode}:{digest}"


def user_prefix(user_id: int) -> str:
    return f"qcache:{user_id}:"


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

    def clear(self) -> None:
        self._store.clear()


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


def _build_cache() -> CacheBackend:
    if settings.redis_url:
        try:
            return RedisCache(settings.redis_url)
        except Exception:  # noqa: BLE001 - never let cache init break the app
            pass
    return InMemoryCache()


# Module-level singleton used by the query router.
cache: CacheBackend = _build_cache()
