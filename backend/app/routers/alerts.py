"""Alert queue, detail, reviewer actions and on-demand narration."""
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session, joinedload

from ml.explain import narrate, template_explanation

from ..deps import DB, CanAct, CurrentUser, Id, audit, notify, through
from ..models import Alert, AuditLog, Event, Feedback, User
from ..schemas import AssignBody, BulkAction, Language, ReviewAction
from ..services import get_settings

router = APIRouter(prefix="/alerts", tags=["alerts"])

SORTS = {"risk": Alert.risk, "date": Event.invoice_date, "amount": Event.amount, "vendor": Event.vendor_name,
         "status": Alert.status, "id": Alert.id}
LABEL = {"Confirmed": 1, "Dismissed": 0, "Escalated": None}
SEQUENCE_LENGTH = 24


def alert_row(alert: Alert) -> dict[str, Any]:
    """The compact shape used in tables."""
    event = alert.event
    return {
        "id": alert.id, "event_id": event.event_id, "vendor_id": alert.vendor_id, "vendor_name": event.vendor_name,
        "amount": event.amount, "invoice_date": event.invoice_date, "risk": round(alert.risk, 3), "level": alert.level,
        "flags": alert.flags, "status": alert.status, "case_id": alert.case_id,
        "assignee": alert.assignee and {"id": alert.assignee.id, "name": alert.assignee.name},
    }


def _get(db: Session, alert_id: int) -> Alert:
    alert = db.get(Alert, alert_id, options=[joinedload(Alert.event), joinedload(Alert.assignee)])
    if alert is None:
        raise HTTPException(404, "Alert not found")
    return alert


def _review(db: Session, alert: Alert, status: str, user: User, reason: str, comment: str) -> None:
    if alert.status == status:  # a double submit is not a second decision
        return
    alert.status = status
    db.add(Feedback(alert_id=alert.id, user_id=user.id, action=status, label=LABEL[status], reason=reason, comment=comment))
    audit(db, user, f"alert_{status.lower()}", "alert", alert.id, reason=reason, comment=comment)


def _assign(db: Session, alert: Alert, assignee_id: int | None, user: User) -> None:
    if assignee_id is not None:
        assignee = db.get(User, assignee_id)
        if assignee is None or not assignee.is_active or assignee.role not in ("Admin", "Reviewer"):
            raise HTTPException(400, "Assignee must be an active Admin or Reviewer")
        if assignee_id != user.id:
            notify(db, [assignee_id], "assignment", f"Alert {alert.id} assigned to you",
                   f"{alert.level} risk, assigned by {user.name}.", f"/alerts/{alert.id}")
    alert.assignee_id = assignee_id
    audit(db, user, "alert_assigned", "alert", alert.id, assignee_id=assignee_id)


@router.get("")
def list_alerts(
    db: DB, _: CurrentUser,
    level: list[str] = Query(default=[]), status: list[str] = Query(default=[]),
    entity: str | None = None, rule: str | None = None, search: str | None = None,
    date_from: datetime | None = None, date_to: datetime | None = None, assignee_id: int | None = None,
    sort: str = "risk", order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1, le=1_000_000), page_size: int = Query(25, ge=1, le=200),
) -> dict[str, Any]:
    query = select(Alert).join(Event, Alert.event_pk == Event.id)
    if level:
        query = query.where(Alert.level.in_(level))
    if status:
        query = query.where(Alert.status.in_(status))
    if entity:
        query = query.where(or_(Alert.vendor_id == entity, Event.department == entity, Event.vendor_name.icontains(entity, autoescape=True)))
    if rule:
        query = query.where(cast(Alert.flags, String).contains(f'"{rule}"', autoescape=True))
    if date_from:
        query = query.where(Event.invoice_date >= date_from)
    if date_to:
        query = query.where(Event.invoice_date <= through(date_to))
    if assignee_id:
        query = query.where(Alert.assignee_id == assignee_id)
    if search:
        query = query.where(or_(Event.vendor_name.icontains(search, autoescape=True),
                                Event.event_id.icontains(search, autoescape=True),
                                Event.invoice_number.icontains(search, autoescape=True),
                                Alert.vendor_id.icontains(search, autoescape=True)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = SORTS.get(sort, Alert.risk)
    query = query.order_by(column.asc() if order == "asc" else column.desc(), Alert.id.desc())
    query = query.options(joinedload(Alert.event), joinedload(Alert.assignee))
    rows = db.scalars(query.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [alert_row(a) for a in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/bulk")
def bulk(body: BulkAction, db: DB, user: CanAct) -> dict[str, int]:
    alerts = db.scalars(select(Alert).where(Alert.id.in_(body.ids))).all()
    status = {"confirm": "Confirmed", "dismiss": "Dismissed", "escalate": "Escalated"}.get(body.action)
    # A bulk decision only clears undecided alerts: one person's decision is not overwritten in passing.
    targets = [a for a in alerts if a.status == "Pending"] if status else alerts
    for alert in targets:
        if status:
            _review(db, alert, status, user, body.reason, body.comment)
        else:
            _assign(db, alert, body.assignee_id, user)
    db.commit()
    return {"updated": len(targets), "skipped": len(alerts) - len(targets)}


@router.get("/{alert_id}")
def detail(alert_id: Id, db: DB, _: CurrentUser) -> dict[str, Any]:
    alert = _get(db, alert_id)
    event = alert.event
    past = db.scalars(select(Event).where(Event.vendor_id == event.vendor_id, Event.invoice_date <= event.invoice_date)
                      .order_by(Event.invoice_date.desc(), Event.id.desc()).limit(SEQUENCE_LENGTH)).all()
    related = db.scalars(select(Alert).join(Event, Alert.event_pk == Event.id)
                         .where(Alert.vendor_id == alert.vendor_id, Alert.id != alert.id)
                         .options(joinedload(Alert.event), joinedload(Alert.assignee))
                         .order_by(Event.invoice_date.desc()).limit(8)).all()
    amounts = sorted(e.amount for e in past if e.id != event.id)

    def quantile(p: float) -> float | None:
        return amounts[int(p * (len(amounts) - 1))] if amounts else None

    timeline = db.execute(select(AuditLog, User.name).outerjoin(User, AuditLog.user_id == User.id)
                          .where(AuditLog.entity_type == "alert", AuditLog.entity_id == str(alert.id))
                          .order_by(AuditLog.created_at.desc())).all()
    return {
        **alert_row(alert),
        "event": {c.name: getattr(event, c.name) for c in Event.__table__.columns
                  if c.name not in ("is_anomaly", "anomaly_type", "bank_account")},
        "scores": {"lstm": None if alert.lstm_score is None else round(alert.lstm_score, 3), "isolation_forest": round(alert.a_score, 3),
                   "entity_deviation": round(alert.d_score, 3), "rules": round(alert.f_score, 3)},
        "thresholds": get_settings(db)["thresholds"],
        "facts": alert.facts, "explanation": alert.explanation, "explanation_provider": alert.explanation_provider,
        "model_version": alert.model_version,
        "normal_range": {"p10": quantile(0.1), "p50": quantile(0.5), "p90": quantile(0.9), "count": len(amounts)},
        "sequence": [{"event_id": e.event_id, "date": e.invoice_date, "actual": e.amount, "expected": e.expected_amount,
                      "level": e.level, "current": e.id == event.id} for e in reversed(past)],
        "related": [alert_row(a) for a in related],
        "timeline": [{"action": log.action, "user": log.detail.get("actor") or name or "System", "at": log.created_at, "detail": log.detail}
                     for log, name in timeline],
    }


@router.get("/{alert_id}/explain")
def explain(alert_id: Id, db: DB, _: CurrentUser, language: Language = "en") -> dict[str, Any]:
    """Re-narrate on demand. Facts are never recomputed, so the reasons cannot change."""
    alert = _get(db, alert_id)
    wanted = get_settings(db)["qwen_provider"]
    text, used = narrate(alert.facts, alert.level, alert.risk, language, wanted)
    # The reviewer should know when the model was asked and its wording refused, not just see a template.
    return {"explanation": text, "provider": used, "language": language, "fell_back": wanted != "template" and used == "template"}


@router.get("/{alert_id}/similar")
def similar(alert_id: Id, db: DB, _: CurrentUser, limit: int = Query(5, ge=1, le=20)) -> list[dict[str, Any]]:
    """Other vendors' alerts sharing the most red flags, then closest in risk, so past outcomes can inform this one."""
    alert = _get(db, alert_id)
    mine = set(alert.flags)
    others = db.execute(select(Alert.id, Alert.flags, Alert.risk).where(Alert.vendor_id != alert.vendor_id)).all()
    alike = [o for o in others if mine & set(o.flags)] if mine else [o for o in others if not o.flags]
    ranked = sorted(alike, key=lambda o: (-len(mine & set(o.flags)), abs(o.risk - alert.risk)))[:limit]
    rows = {a.id: a for a in db.scalars(select(Alert).where(Alert.id.in_([o.id for o in ranked]))
                                        .options(joinedload(Alert.event), joinedload(Alert.assignee)))}
    return [{**alert_row(rows[o.id]), "shared_flags": sorted(mine & set(o.flags))} for o in ranked]


def _action(status: str):
    def handler(alert_id: Id, body: ReviewAction, db: DB, user: CanAct) -> dict[str, str]:
        alert = _get(db, alert_id)
        _review(db, alert, status, user, body.reason, body.comment)
        db.commit()
        return {"status": alert.status}
    return handler


router.post("/{alert_id}/confirm", summary="Confirm alert")(_action("Confirmed"))
router.post("/{alert_id}/dismiss", summary="Dismiss alert")(_action("Dismissed"))
router.post("/{alert_id}/escalate", summary="Escalate alert")(_action("Escalated"))


@router.post("/{alert_id}/assign")
def assign(alert_id: Id, body: AssignBody, db: DB, user: CanAct) -> dict[str, Any]:
    alert = _get(db, alert_id)
    _assign(db, alert, body.assignee_id, user)
    db.commit()
    return {"assignee_id": alert.assignee_id}
