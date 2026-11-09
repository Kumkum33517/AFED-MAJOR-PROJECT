"""Cases: alerts grouped per vendor per 30 days."""
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from ..deps import DB, CanAct, CurrentUser, Id, audit, notify
from ..models import Alert, Case, User, utcnow
from ..schemas import CaseNote, CaseUpdate
from .alerts import alert_row

router = APIRouter(prefix="/cases", tags=["cases"])


def case_row(case: Case) -> dict[str, Any]:
    risks = [a.risk for a in case.alerts]
    return {
        "id": case.id, "vendor_id": case.vendor_id, "vendor_name": case.vendor_name, "status": case.status,
        "window_start": case.window_start, "window_end": case.window_end,
        "assignee": case.assignee and {"id": case.assignee.id, "name": case.assignee.name},
        "alert_count": len(risks), "max_risk": round(max(risks), 3) if risks else 0.0,
        "total_amount": sum(a.event.amount for a in case.alerts), "updated_at": case.updated_at,
    }


LOAD_ALERTS = selectinload(Case.alerts).joinedload(Alert.event)


@router.get("")
def list_cases(db: DB, _: CurrentUser, status: list[str] = Query(default=[]), search: str | None = None,
               page: int = Query(1, ge=1, le=1_000_000), page_size: int = Query(25, ge=1, le=200)) -> dict[str, Any]:
    query = select(Case)
    if status:
        query = query.where(Case.status.in_(status))
    if search:
        query = query.where(Case.vendor_name.icontains(search, autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.options(LOAD_ALERTS, joinedload(Case.assignee)).order_by(Case.window_end.desc(), Case.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [case_row(c) for c in rows], "total": total, "page": page, "page_size": page_size}


def _get(db: DB, case_id: int) -> Case:
    case = db.get(Case, case_id, options=[LOAD_ALERTS, joinedload(Case.assignee)])
    if case is None:
        raise HTTPException(404, "Case not found")
    return case


@router.get("/{case_id}")
def detail(case_id: Id, db: DB, _: CurrentUser) -> dict[str, Any]:
    case = _get(db, case_id)
    return {**case_row(case), "notes": case.notes,
            "alerts": [{**alert_row(a), "explanation": a.explanation}
                       for a in sorted(case.alerts, key=lambda a: a.event.invoice_date)]}


@router.patch("/{case_id}")
def update_case(case_id: Id, body: CaseUpdate, db: DB, user: CanAct) -> dict[str, Any]:
    case = _get(db, case_id)
    changed = body.model_dump(exclude_unset=True)
    if changed.get("status"):
        case.status = changed["status"]
    if "assignee_id" in changed:
        target = changed["assignee_id"]
        if target is not None:
            assignee = db.get(User, target)
            if assignee is None or not assignee.is_active or assignee.role not in ("Admin", "Reviewer"):
                raise HTTPException(400, "Assignee must be an active Admin or Reviewer")
            if target != user.id:
                notify(db, [target], "assignment", f"Case {case.id} assigned to you", f"{case.vendor_name}, by {user.name}.", f"/cases/{case.id}")
        case.assignee_id = target
    audit(db, user, "case_updated", "case", case.id, **changed)
    db.commit()
    db.refresh(case)  # otherwise the relationship still holds the previous assignee
    return detail(case_id, db, user)


@router.post("/{case_id}/notes")
def add_note(case_id: Id, body: CaseNote, db: DB, user: CanAct) -> list[dict[str, Any]]:
    # The row lock keeps two people's notes from overwriting each other, since they share one JSON value.
    case = db.get(Case, case_id, with_for_update=True)
    if case is None:
        raise HTTPException(404, "Case not found")
    # Reassigned, not appended: SQLAlchemy does not see in-place changes to a JSON list.
    case.notes = [*case.notes, {"author": user.name, "at": utcnow().isoformat(), "text": body.text}]
    audit(db, user, "case_note_added", "case", case.id)
    db.commit()
    return case.notes
