"""Rate limiting via slowapi.

Keyed per authenticated user when a valid Bearer token is present, falling back
to per-IP for anonymous requests — so one user's traffic can't exhaust another
user's budget, and unauthenticated abuse is still bounded by source IP.

Storage is Redis when ``REDIS_URL`` is set (shared across workers) and in-memory
otherwise. Limits are read from settings via callables so they can be tuned
(and overridden in tests) without re-importing the module.
"""
from __future__ import annotations

import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from .config import settings
from .security import decode_access_token


def _user_or_ip_key(request: Request) -> str:
    """Prefer the authenticated user id; fall back to client IP."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        try:
            sub = decode_access_token(token).get("sub")
            if sub:
                return f"user:{sub}"
        except jwt.PyJWTError:
            pass
    return f"ip:{get_remote_address(request)}"


def _storage_uri() -> str | None:
    return settings.redis_url or None


limiter = Limiter(
    key_func=_user_or_ip_key,
    storage_uri=_storage_uri(),
    enabled=settings.rate_limit_enabled,
)


# Callables so a test can monkeypatch settings.* and have it take effect live.
def query_limit() -> str:
    return settings.rate_limit_query


def upload_limit() -> str:
    return settings.rate_limit_upload


def login_limit() -> str:
    return settings.rate_limit_login


def register_limit() -> str:
    return settings.rate_limit_register


def export_limit() -> str:
    return settings.rate_limit_export
