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


def _generation_key(user_id: str) -> str:
    # Deliberately outside the ``qcache:{user}:`` namespace so invalidate_prefix
    # never deletes the counter it is about to bump.
    return f"qgen:{user_id}"


def _user_id_from_prefix(prefix: str) -> str | None:
    """Inverse of ``user_prefix``; None for any other prefix."""
    if prefix.startswith("qcache:") and prefix.endswith(":"):
        uid = prefix[len("qcache:"):-1]
        return uid or None
    return None


class CacheBackend(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl: int) -> None: ...
    def invalidate_prefix(self, prefix: str) -> None: ...
    def generation(self, user_id: str) -> str: ...
    def try_lock(self, name: str, ttl: int) -> bool: ...


class InMemoryCache:
    """Process-local TTL cache. Not shared across workers."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, str]] = {}
        self._generations: dict[str, int] = {}

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
        uid = _user_id_from_prefix(prefix)
        if uid is not None:
            self._generations[uid] = self._generations.get(uid, 0) + 1
        invalidate_object_prefix(prefix)

    def generation(self, user_id: str) -> str:
        return str(self._generations.get(user_id, 0))

    def try_lock(self, name: str, ttl: int) -> bool:
        # Process-local cache => single process is the only contender.
        return True

    def clear(self) -> None:
        self._store.clear()
        self._generations.clear()
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
        uid = _user_id_from_prefix(prefix)
        if uid is not None:
            # The per-process object cache can't be cleared from here for the
            # *other* workers; bumping a shared counter makes each of them
            # notice and rebuild on its next lookup.
            self._redis.incr(_generation_key(uid))
        invalidate_object_prefix(prefix)

    def generation(self, user_id: str) -> str:
        try:
            return str(self._redis.get(_generation_key(user_id)) or "0")
        except Exception:  # noqa: BLE001 - degrade to "never stale-checked"
            return "0"

    def try_lock(self, name: str, ttl: int) -> bool:
        """Best-effort cross-worker mutex (SET NX EX). Fails open: if Redis is
        unreachable the caller proceeds, as every guarded task is idempotent."""
        try:
            return bool(self._redis.set(f"lock:{name}", "1", nx=True, ex=ttl))
        except Exception:  # noqa: BLE001
            return True


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
_object_cache: dict[str, tuple[str | None, object]] = {}
_object_cache_lock = RLock()


def index_generation(user_id: str) -> str:
    """Shared invalidation counter for a user's cached objects (see
    ``get_or_build_object``)."""
    return cache.generation(user_id)


def get_or_build_object(
    key: str, factory: Callable[[], object], generation: str | None = None
) -> object:
    """Return the cached object for ``key``, rebuilding it when ``generation``
    differs from the one it was built under. ``generation`` must be read
    *before* calling this, so an invalidation racing with the build leaves a
    stale tag behind and the next lookup rebuilds."""
    with _object_cache_lock:
        cached = _object_cache.get(key)
        if cached is not None and cached[0] == generation:
            return cached[1]
        built = factory()
        _object_cache[key] = (generation, built)
        return built


def invalidate_object_prefix(prefix: str) -> None:
    with _object_cache_lock:
        for key in [k for k in _object_cache if k.startswith(prefix)]:
            _object_cache.pop(key, None)


def clear_object_cache() -> None:
    with _object_cache_lock:
        _object_cache.clear()
