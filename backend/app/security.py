"""Password hashing and JWT issuance/verification.

Passwords are hashed with bcrypt (via passlib). Two token types are issued:

* **access**  — short-lived (``jwt_expire_minutes``), sent as a Bearer header,
  used to authorize API calls. Stateless: never stored server-side.
* **refresh** — long-lived (``refresh_expire_days``), delivered in an httpOnly
  cookie, exchanged for new access tokens. Carries a unique ``jti`` so it can
  be revoked on logout by blacklisting that id.

Both are signed JWTs (HS256), chosen over server-side sessions so the API tier
stays stateless and scales horizontally without shared session storage. Only
refresh revocation needs a tiny bit of state (the blacklist table).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from passlib.context import CryptContext

from .config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _pwd_context.verify(password, hashed)
    except ValueError:
        return False


def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    """Issue a signed access JWT whose ``sub`` claim is the user id."""
    now = datetime.now(timezone.utc)
    return _encode(
        {
            "sub": str(subject),
            "type": ACCESS_TOKEN_TYPE,
            "iat": int(now.timestamp()),
            "exp": int(
                (now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()
            ),
        }
    )


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """Issue a refresh JWT. Returns ``(token, jti, expires_at)``.

    The ``jti`` and ``expires_at`` are surfaced so the caller can record the
    token in the blacklist table on logout (and a cleanup job can purge it once
    expired).
    """
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    expires_at = now + timedelta(days=settings.refresh_expire_days)
    token = _encode(
        {
            "sub": str(subject),
            "type": REFRESH_TOKEN_TYPE,
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
    )
    return token, jti, expires_at


def decode_token(token: str) -> dict:
    """Decode and verify any PaperTrail JWT. Raises ``jwt.PyJWTError``."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def decode_access_token(token: str) -> dict:
    """Decode a token and require it to be an access token.

    A refresh token presented as a Bearer credential is rejected (wrong type),
    so a long-lived refresh token can't be used to call protected routes.
    """
    payload = decode_token(token)
    # Tokens minted before typed claims (or of the wrong type) are not accepted
    # as access tokens.
    if payload.get("type", ACCESS_TOKEN_TYPE) != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Not an access token.")
    return payload


def decode_refresh_token(token: str) -> dict:
    """Decode a token and require it to be a refresh token."""
    payload = decode_token(token)
    if payload.get("type") != REFRESH_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Not a refresh token.")
    return payload
