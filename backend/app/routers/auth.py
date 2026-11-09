"""Login, current user, profile and password. `/auth/login` takes a form so the /docs Authorize button works."""
import secrets
import threading
import time
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from ..auth import create_token, hash_password, verify_password
from ..deps import DB, CurrentUser, audit, notify
from ..models import Notification, User, utcnow
from ..schemas import ForgotPassword, PasswordChange, ProfileUpdate, Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILURES, LOCKOUT_SECONDS, MAX_TRACKED = 5, 300, 10_000
# Per-process memory, so the limit is per worker and resets on restart. Move to Redis if scaled out.
_attempts: dict[str, list[float]] = {}
_attempts_lock = threading.Lock()
# Checked when an account does not exist, so response time cannot reveal which emails do.
_NO_SUCH_USER = hash_password(secrets.token_hex(16))


def _reserve_attempt(key: str) -> bool:
    """Count the attempt before the password is checked, so a parallel burst cannot slip under the limit."""
    now = time.time()
    with _attempts_lock:
        if len(_attempts) > MAX_TRACKED:
            for stale in [k for k, times in _attempts.items() if now - times[-1] >= LOCKOUT_SECONDS]:
                del _attempts[stale]
        recent = [t for t in _attempts.get(key, []) if now - t < LOCKOUT_SECONDS]
        allowed = len(recent) < MAX_FAILURES
        _attempts[key] = [*recent, now] if allowed else recent
        return allowed


@router.post("/login", response_model=Token)
def login(request: Request, form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB) -> Token:
    email = form.username.strip().lower()
    if len(email) > 255 or "\x00" in email:
        raise HTTPException(401, "Incorrect email or password")
    # Keyed on the address as well, so a stranger's bad guesses cannot lock an account's real owner out.
    key = f"{email}|{request.client.host if request.client else ''}"
    if not _reserve_attempt(key):
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")

    user = db.scalar(select(User).where(User.email == email))
    password_ok = verify_password(form.password, user.password_hash if user else _NO_SUCH_USER)
    if user is None or not password_ok:
        if user is not None:
            audit(db, None, "login_failed", "user", user.id)
            db.commit()
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated")

    with _attempts_lock:
        _attempts.pop(key, None)
    user.last_login = utcnow()
    audit(db, user, "login", "user", user.id)
    db.commit()
    return Token(access_token=create_token(user.id, user.password_hash), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: CurrentUser, db: DB) -> User:
    if body.name is not None and body.name != user.name:
        audit(db, user, "name_changed", "user", user.id, new_name=body.name)
        user.name = body.name
    if body.preferences is not None:
        user.preferences = {**user.preferences, **body.preferences.model_dump(exclude_none=True)}
    db.commit()
    return user


@router.post("/change-password")
def change_password(body: PasswordChange, user: CurrentUser, db: DB) -> dict[str, str]:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "password_changed", "user", user.id)
    db.commit()
    # Older tokens stop working now, this session's included, so it gets a new one.
    return {"message": "Password changed", "access_token": create_token(user.id, user.password_hash)}


@router.post("/forgot")
def forgot(body: ForgotPassword, db: DB) -> dict[str, str]:
    # No mail service, so an admin is notified and resets it from User Management.
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is not None:
        recent = utcnow() - timedelta(hours=1)
        already = db.scalar(select(Notification.id).where(Notification.kind == "password_reset", Notification.body.contains(user.email, autoescape=True),
                                                          Notification.created_at >= recent).limit(1))
        if already is None:  # this endpoint is anonymous, so it must not be a way to flood admins
            admins = list(db.scalars(select(User.id).where(User.role == "Admin", User.is_active)))
            notify(db, admins, "password_reset", "Password reset requested", f"{user.email} asked for a reset. Use User Management.", "/users")
            audit(db, None, "password_reset_requested", "user", user.id)  # System: the requester is unverified
            db.commit()
    # Same answer either way, so this endpoint cannot be used to discover accounts.
    return {"message": "If that account exists, an administrator has been asked to reset the password."}
