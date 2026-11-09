"""A user's own notifications."""
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select, update

from ..deps import DB, CurrentUser, Id
from ..models import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(db: DB, user: CurrentUser) -> dict[str, Any]:
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(100)).all()
    unread = db.scalar(select(func.count()).select_from(Notification)
                       .where(Notification.user_id == user.id, Notification.read.is_(False))) or 0
    return {"unread": unread, "items": [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link,
                                         "read": n.read, "created_at": n.created_at} for n in rows]}


@router.post("/read-all")
def read_all(db: DB, user: CurrentUser) -> dict[str, str]:
    db.execute(update(Notification).where(Notification.user_id == user.id).values(read=True))
    db.commit()
    return {"status": "ok"}


@router.post("/{notification_id}/read")
def read_one(notification_id: Id, db: DB, user: CurrentUser) -> dict[str, str]:
    row = db.get(Notification, notification_id)
    if row is None or row.user_id != user.id:  # someone else's row reads as absent
        raise HTTPException(404, "Notification not found")
    row.read = True
    db.commit()
    return {"status": "ok"}
