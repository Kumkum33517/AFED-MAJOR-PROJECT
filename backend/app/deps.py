"""Request dependencies: the current user, role checks, and small shared helpers."""
from collections.abc import Callable
from datetime import datetime, time, timedelta
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .auth import decode_token, password_version
from .db import get_db
from .models import AuditLog, Notification, User

oauth2 = OAuth2PasswordBearer(tokenUrl="auth/login")
DB = Annotated[Session, Depends(get_db)]
MAX_ID = 2**31 - 1
Id = Annotated[int, Path(ge=1, le=MAX_ID)]  # larger values would overflow the integer column and return a 500


def current_user(db: DB, token: Annotated[str, Depends(oauth2)]) -> User:
    # The user is loaded on every request, so deactivating or re-roling takes effect immediately.
    claims = decode_token(token)
    user = db.get(User, claims[0]) if claims and claims[0] <= MAX_ID else None
    if user is None or not user.is_active or claims[1] != password_version(user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require(*roles: str) -> Callable[[User], User]:
    """Dependency factory: `Depends(require("Admin", "Reviewer"))`."""
    def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires role: {', '.join(roles)}")
        return user
    return check


# The access matrix from the brief, in one place.
CanAct = Annotated[User, Depends(require("Admin", "Reviewer"))]
CanOperate = Annotated[User, Depends(require("Admin", "Analyst"))]
AdminOnly = Annotated[User, Depends(require("Admin"))]


def audit(db: Session, user: User | None, action: str, entity_type: str = "", entity_id: Any = "",
          **detail: Any) -> None:
    # The actor is written down now: a name looked up later would change if the user renamed themself.
    actor = f"{user.name} ({user.email})" if user else "System"
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity_type=entity_type,
                    entity_id=str(entity_id), detail={**detail, "actor": actor}))


def through(value: datetime | None) -> datetime | None:
    """An end date covers that whole day, including invoices that carry a time."""
    return datetime.combine(value.date() + timedelta(days=1), time.min) - timedelta(microseconds=1) if value and value.time() == time.min else value


def notify(db: Session, user_ids: list[int], kind: str, title: str, body: str = "", link: str = "") -> None:
    db.add_all(Notification(user_id=u, kind=kind, title=title, body=body, link=link) for u in user_ids)
