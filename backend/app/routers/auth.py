"""Authentication routes: register, login, refresh, logout, me.

Access tokens are returned in the JSON body (the frontend keeps them in memory
only). Refresh tokens are set as an httpOnly, SameSite=Strict cookie so they are
never readable by JavaScript and are sent automatically only to the auth routes.
Logout revokes the refresh token by blacklisting its ``jti``.
"""
from __future__ import annotations

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
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    if db.get(TokenBlacklist, jti) is not None:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked.")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User no longer exists.")

    # Rotate the refresh token on every use so a leaked cookie has a bounded life.
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
