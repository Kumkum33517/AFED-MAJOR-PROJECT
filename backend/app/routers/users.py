"""User and role management (Admin), plus the assignee list reviewers need."""
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from ..auth import hash_password
from ..deps import DB, AdminOnly, CanAct, Id, audit
from ..models import AuditLog, User
from ..schemas import Invite, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DB, _: AdminOnly) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)))


@router.get("/assignees")
def assignees(db: DB, _: CanAct) -> list[dict[str, Any]]:
    rows = db.execute(select(User.id, User.name).where(User.is_active, User.role.in_(("Admin", "Reviewer"))).order_by(User.name)).all()
    return [{"id": i, "name": n} for i, n in rows]


@router.get("/audit-log")
def audit_log(db: DB, _: AdminOnly, page: int = Query(1, ge=1, le=1_000_000), page_size: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    total = db.scalar(select(func.count()).select_from(AuditLog)) or 0
    rows = db.execute(select(AuditLog, User.name).outerjoin(User, AuditLog.user_id == User.id)
                      .order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [{"id": log.id, "user": log.detail.get("actor") or name or "System", "action": log.action, "entity_type": log.entity_type,
                       "entity_id": log.entity_id, "detail": {k: v for k, v in log.detail.items() if k != "actor"}, "created_at": log.created_at}
                      for log, name in rows]}


@router.post("", status_code=201)
def invite(body: Invite, db: DB, admin: AdminOnly) -> dict[str, Any]:
    # No mail service, so the admin passes on this temporary password by hand.
    email = body.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "A user with that email already exists")
    password = secrets.token_urlsafe(9)
    user = User(email=email, name=body.name, role=body.role, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    audit(db, admin, "user_invited", "user", user.id, email=email, role=body.role)
    db.commit()
    return {"user": UserOut.model_validate(user).model_dump(), "temporary_password": password}


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: Id, body: UserUpdate, db: DB, admin: AdminOnly) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:  # an admin cannot lock everyone out by demoting themself
        raise HTTPException(400, "You cannot change your own role or status")
    changes = body.model_dump(exclude_none=True)  # role and is_active are NOT NULL, so null means "leave alone"
    for key, value in changes.items():
        setattr(user, key, value)
    audit(db, admin, "user_updated", "user", user.id, **changes)
    db.commit()
    return user


@router.post("/{user_id}/reset-password")
def reset_password(user_id: Id, db: DB, admin: AdminOnly) -> dict[str, str]:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    password = secrets.token_urlsafe(9)
    user.password_hash = hash_password(password)
    audit(db, admin, "password_reset", "user", user.id)
    db.commit()
    return {"temporary_password": password}
