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

import hashlib
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import Document, PasswordResetToken, TokenBlacklist, User
from ..ratelimit import limiter, login_limit, register_limit
from ..storage import storage
from ..schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdate,
    ResetPasswordRequest,
    TokenOut,
    UserCreate,
    UserOut,
)
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

# Reset tokens are high-entropy random values (not user-chosen passwords), so a
# fast SHA-256 hash is appropriate here — unlike account passwords, there is no
# guessing attack to slow down with bcrypt; only the hash is ever stored.
def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

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


@router.patch("/me", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.display_name = payload.display_name
    current_user.bio = payload.bio
    current_user.avatar_url = payload.avatar_url
    db.commit()
    db.refresh(current_user)
    return current_user


AVATAR_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
AVATAR_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}


def _avatar_dir() -> str:
    path = os.path.join(settings.uploads_dir, "avatars")
    os.makedirs(path, exist_ok=True)
    return path


def _find_avatar_file(avatar_dir: str, user_id: str) -> str | None:
    prefix = f"{user_id}."
    for name in os.listdir(avatar_dir):
        if name.startswith(prefix):
            return os.path.join(avatar_dir, name)
    return None


def _remove_avatar_file(user_id: str) -> None:
    existing = _find_avatar_file(_avatar_dir(), user_id)
    if existing and os.path.exists(existing):
        try:
            os.remove(existing)
        except OSError:
            pass


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = AVATAR_CONTENT_TYPES.get(file.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=422, detail="Avatar must be a JPEG, PNG, WebP, or GIF image."
        )
    data = await file.read()
    if len(data) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=413, detail="Avatar image must be under 2 MB.")

    _remove_avatar_file(current_user.id)  # drop a previous avatar of a different extension
    path = os.path.join(_avatar_dir(), f"{current_user.id}.{ext}")
    with open(path, "wb") as fh:
        fh.write(data)

    # A fresh query string per upload busts the browser's <img> cache — the
    # path itself is stable so old links wouldn't otherwise notice a change.
    current_user.avatar_url = f"/api/auth/me/avatar/{current_user.id}?v={uuid.uuid4().hex[:8]}"
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me/avatar", response_model=UserOut)
def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _remove_avatar_file(current_user.id)
    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/avatar/{user_id}")
def get_avatar(user_id: str):
    """Serve an uploaded avatar image. Unauthenticated: avatars are meant to be
    displayable wherever the app shows a user (same trust level as any other
    public profile picture host)."""
    path = _find_avatar_file(_avatar_dir(), user_id)
    if path is None:
        raise HTTPException(status_code=404, detail="No avatar set.")
    return FileResponse(path)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    current_user.hashed_password = hash_password(payload.new_password)
    # Same revocation mechanism as refresh-token-reuse detection: every
    # outstanding refresh token predates this instant, so a password change
    # signs every other session out.
    current_user.revoked_before = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Password changed. Other sessions have been signed out."}


@router.delete("/me")
def delete_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete the account and everything owned by it.

    Related rows (documents, chunks, chat history, collections, ...) cascade
    at the database level via the ``ondelete="CASCADE"`` foreign keys already
    declared on those tables (the same mechanism TokenBlacklist uses) — no
    per-table cleanup code is needed here beyond removing on-disk files, which
    the DB cascade can't reach.
    """
    storage_keys = [
        d.storage_key
        for d in db.query(Document).filter(Document.user_id == current_user.id).all()
        if d.storage_key
    ]
    user_id = current_user.id
    db.delete(current_user)
    db.commit()
    for key in storage_keys:
        storage.delete(key)
    _remove_avatar_file(user_id)
    _clear_refresh_cookie(response)
    return {"detail": "Account deleted."}


@router.post("/forgot-password")
@limiter.limit(login_limit)
def forgot_password(
    request: Request, payload: ForgotPasswordRequest, db: Session = Depends(get_db),
):
    user = db.execute(
        select(User).where(User.email == payload.email)
    ).scalar_one_or_none()
    if user is not None:
        raw_token = secrets.token_urlsafe(32)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=_hash_reset_token(raw_token),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )
        db.commit()
        reset_link = f"{settings.frontend_base_url}/reset-password?token={raw_token}"
        # PLACEHOLDER: no email-sending infrastructure exists yet (see
        # config.py / observability.py). Log the link server-side so the
        # endpoint contract is real and testable now; swap this line for an
        # actual email send once one is wired up.
        logger.info(
            "Password reset requested for user_id=%s: %s", user.id, reset_link
        )
    # Identical response whether or not the email is registered, so this
    # endpoint can't be used to enumerate accounts.
    return {"detail": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
@limiter.limit(login_limit)
def reset_password(
    request: Request, payload: ResetPasswordRequest, db: Session = Depends(get_db),
):
    token_hash = _hash_reset_token(payload.token)
    record = db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if (
        record is None
        or record.used_at is not None
        or _as_utc(record.expires_at) < now
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user = db.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    user.hashed_password = hash_password(payload.new_password)
    user.revoked_before = now
    record.used_at = now
    db.commit()
    return {"detail": "Password has been reset. Please sign in again."}
