"""Authentication routes: register, login, refresh, logout, me.

Access tokens are returned in the JSON body (the frontend keeps them in memory
only). Refresh tokens are set as an httpOnly, SameSite=Strict cookie so they are
never readable by JavaScript and are sent automatically only to the auth routes.
Logout revokes the refresh token by blacklisting its ``jti``.

Refresh tokens are single-use: /refresh blacklists the presented token's
``jti`` before minting a replacement. A blacklisted jti coming back therefore
means two parties hold the same token (theft), so every outstanding refresh
token for that account is revoked via ``users.revoked_before``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import TokenBlacklist, User
from ..ratelimit import limiter, login_limit, register_limit
from ..schemas import LoginRequest, TokenOut, UserCreate, UserOut
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

logger = logging.getLogger("papertrail.auth")


def _as_utc(dt: datetime) -> datetime:
    """Timestamps read back from MySQL DATETIME columns are naive; they were
    written as UTC wall-clock, so attach UTC for comparisons."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.refresh_expire_days * 24 * 3600,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api/auth",
    )


def _issue_tokens(response: Response, db: Session, user: User) -> TokenOut:
    """Mint an access token (body) + refresh token (httpOnly cookie)."""
    refresh, _jti, _exp = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/register", response_model=TokenOut, status_code=201)
@limiter.limit(register_limit)
def register(
    request: Request, payload: UserCreate, response: Response,
    db: Session = Depends(get_db),
):
    existing = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if existing is not None:
        # 422: the submitted email cannot be processed because it is taken.
        raise HTTPException(status_code=422, detail="Email is already registered.")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=(payload.display_name or None),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_tokens(response, db, user)


@router.post("/login", response_model=TokenOut)
@limiter.limit(login_limit)
def login(
    request: Request, payload: LoginRequest, response: Response,
    db: Session = Depends(get_db),
):
    user = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    # Same 401 whether the email is unknown or the password is wrong, so we
    # don't leak which emails exist.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    return _issue_tokens(response, db, user)


def _refresh_token_from_request(request: Request) -> str:
    """Pull the refresh token from the httpOnly cookie, falling back to a
    Bearer header for non-browser API clients / tests."""
    cookie = request.cookies.get(settings.refresh_cookie_name)
    if cookie:
        return cookie
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    raise HTTPException(status_code=401, detail="Missing refresh token.")


@router.post("/refresh", response_model=TokenOut)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = _refresh_token_from_request(request)
    try:
        payload = decode_refresh_token(token)
        user_id = str(payload["sub"])
        jti = str(payload["jti"])
        issued_at = datetime.fromtimestamp(int(payload["iat"]), tz=timezone.utc)
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    if db.get(TokenBlacklist, jti) is not None:
        # Rotation blacklists every used token, so a blacklisted jti coming
        # back is not a stale client — someone else holds a copy. Revoke every
        # outstanding refresh token for the account, not just this one.
        user = db.get(User, user_id)
        if user is not None:
            user.revoked_before = datetime.now(timezone.utc)
            db.commit()
        logger.warning(
            "Refresh-token reuse detected; all refresh tokens revoked "
            "(user_id=%s, request_id=%s)",
            user_id,
            getattr(request.state, "request_id", "-"),
        )
        raise HTTPException(status_code=401, detail="Refresh token has been revoked.")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User no longer exists.")

    # ``iat`` has whole-second precision, so a token minted within the same
    # second as a theft-response revocation is also rejected — fail closed.
    if user.revoked_before is not None and issued_at < _as_utc(user.revoked_before):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked.")

    # Rotate: blacklist the token being exchanged so it is single-use. A later
    # replay of it lands in the reuse-detection branch above.
    db.add(TokenBlacklist(jti=jti, user_id=user_id, expires_at=expires_at))
    db.commit()
    return _issue_tokens(response, db, user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Revoke the current refresh token (idempotent) and clear the cookie."""
    token = request.cookies.get(settings.refresh_cookie_name)
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()

    if token:
        try:
            payload = decode_refresh_token(token)
            jti = str(payload["jti"])
            exp = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
            if db.get(TokenBlacklist, jti) is None:
                db.add(
                    TokenBlacklist(
                        jti=jti, user_id=str(payload["sub"]), expires_at=exp
                    )
                )
                db.commit()
        except (jwt.PyJWTError, KeyError, ValueError):
            # An unparseable/expired token needs no revoking; still clear cookie.
            pass

    _clear_refresh_cookie(response)
    return {"detail": "Logged out."}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
