"""Vendors and departments: list, and a profile with baseline, peers, time series and alerts."""
from datetime import timedelta
from statistics import median
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import joinedload

from ..deps import DB, CurrentUser
from ..models import Alert, EntityBaseline, Event
from .alerts import alert_row

router = APIRouter(prefix="/entities", tags=["entities"])

EntityType = Literal["vendor", "department"]
TREND_DAYS = 90


def _key(kind: EntityType) -> Any:
    return Event.vendor_id if kind == "vendor" else Event.department


@router.get("")
def list_entities(db: DB, _: CurrentUser, type: EntityType = "vendor", search: str | None = None,
                  sort: Literal["alerts", "transactions", "avg_risk", "name"] = "alerts", order: Literal["asc", "desc"] = "desc",
                  page: int = Query(1, ge=1, le=1_000_000), page_size: int = Query(25, ge=1, le=200)) -> dict[str, Any]:
    key = _key(type)
    latest = db.scalar(select(func.max(Event.invoice_date)))
    if latest is None:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}
    recent_from, previous_from = latest - timedelta(days=TREND_DAYS), latest - timedelta(days=2 * TREND_DAYS)
    is_alert = Alert.id.is_not(None)
    alerts = func.count(Alert.id).label("alerts")
    avg_risk = func.avg(Event.risk).label("avg_risk")
    transactions = func.count(Event.id).label("transactions")
    name = func.max(Event.vendor_name if type == "vendor" else Event.department).label("name")
    query = (select(key.label("id"), name, func.max(Event.category).label("category"), transactions, alerts, avg_risk,
                    func.sum(case((is_alert & (Event.invoice_date > recent_from), 1), else_=0)).label("recent"),
                    func.sum(case((is_alert & (Event.invoice_date > previous_from) & (Event.invoice_date <= recent_from), 1), else_=0)).label("previous"))
             .outerjoin(Alert, Alert.event_pk == Event.id).where(key.is_not(None)).group_by(key))
    if search:
        query = query.having(name.icontains(search, autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    column = {"alerts": alerts, "transactions": transactions, "avg_risk": avg_risk, "name": name}[sort]
    # nulls_last: Postgres otherwise puts unscored vendors above the riskiest ones.
    rows = db.execute(query.order_by((column.asc() if order == "asc" else column.desc()).nulls_last(), key)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    items = [{"id": r.id, "name": r.name, "category": r.category if type == "vendor" else None, "transactions": r.transactions,
              "alerts": r.alerts, "avg_risk": round(r.avg_risk or 0, 3), "recent_alerts": int(r.recent or 0),
              "trend": "up" if (r.recent or 0) > (r.previous or 0) else "down" if (r.recent or 0) < (r.previous or 0) else "flat"}
             for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _quantile(values: list[float], p: float) -> float | None:
    ordered = sorted(values)
    return ordered[int(p * (len(ordered) - 1))] if ordered else None


@router.get("/{entity_id:path}")  # :path, because a department such as Legal/Compliance contains a slash
def profile(entity_id: str, db: DB, _: CurrentUser, type: EntityType = "vendor") -> dict[str, Any]:
    events = db.scalars(select(Event).where(_key(type) == entity_id).order_by(Event.invoice_date)).all()
    if not events:
        raise HTTPException(404, "Entity not found")
    amounts = [e.amount for e in events]
    gaps = [(b.invoice_date - a.invoice_date).days for a, b in zip(events, events[1:])]
    days = [e.processing_days for e in events if e.processing_days is not None]
    stored = db.scalar(select(EntityBaseline).where(EntityBaseline.entity_id == entity_id)) if type == "vendor" else None
    baseline = {
        "median_amount": median(amounts), "p25_amount": _quantile(amounts, 0.25), "p75_amount": _quantile(amounts, 0.75),
        "median_gap_days": median(gaps) if gaps else None, "median_processing_days": median(days) if days else None,
        "history_len": len(events),
    }

    category = events[-1].category
    peers = None
    if type == "vendor" and category:
        # One median per vendor, so a prolific vendor cannot stand in for the whole category.
        rows = db.execute(select(Event.vendor_id, Event.amount, Event.processing_days).where(Event.category == category)).all()
        grouped: dict[str, list[float]] = {}
        for vendor, amount, _days in rows:
            grouped.setdefault(vendor, []).append(amount)
        medians = sorted(median(v) for v in grouped.values())
        peer_days = [d for _v, _a, d in rows if d is not None]
        peers = {"category": category, "vendors": len(medians), "median_amount": median(medians),
                 "median_processing_days": median(peer_days) if peer_days else None,
                 "amount_percentile": round(sum(m <= baseline["median_amount"] for m in medians) / len(medians), 3)}

    alerts = db.scalars(select(Alert).join(Event, Alert.event_pk == Event.id).where(_key(type) == entity_id)
                        .options(joinedload(Alert.event), joinedload(Alert.assignee)).order_by(Event.invoice_date.desc())).all()
    latest = events[-1]
    return {
        "id": entity_id, "type": type, "name": latest.vendor_name if type == "vendor" else entity_id,
        "category": category if type == "vendor" else None, "department": latest.department,
        "vendor_created": latest.vendor_created if type == "vendor" else None,
        # The source the latest event really used, and the reason for it.
        "fallback_baseline": latest.baseline_source if type == "vendor" and latest.baseline_source != "vendor" else None,
        "baseline": baseline, "peers": peers, "updated_at": stored.updated_at if stored else None,
        "series": [{"event_id": e.event_id, "date": e.invoice_date, "amount": e.amount, "risk": e.risk,
                    "level": e.level, "flagged": e.level not in (None, "Low")} for e in events],
        "alerts": [alert_row(a) for a in alerts],
    }
