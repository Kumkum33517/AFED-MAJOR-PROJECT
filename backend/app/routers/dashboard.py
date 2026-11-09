"""KPIs and charts for the dashboard."""
from collections import Counter
from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from ..deps import DB, CurrentUser
from ..models import SEEDED_COMMENT, Alert, Case, Event, Feedback, Run
from .alerts import alert_row

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(db: DB, _: CurrentUser) -> dict[str, Any]:
    levels = dict(db.execute(select(Event.level, func.count()).where(Event.level.is_not(None)).group_by(Event.level)).all())
    months: Counter[str] = Counter()
    # Months are bucketed in Python so one query works on SQLite and Postgres. Use date_trunc past ~100k alerts.
    for (date,) in db.execute(select(Event.invoice_date).join(Alert, Alert.event_pk == Event.id).where(Alert.level != "Low")):
        months[date.strftime("%Y-%m")] += 1

    top = db.execute(
        select(Alert.vendor_id, func.max(Event.vendor_name), func.count(), func.avg(Alert.risk), func.max(Alert.risk))
        .join(Event, Alert.event_pk == Event.id).group_by(Alert.vendor_id)
        .order_by(func.sum(Alert.risk).desc()).limit(5)).all()
    recent = db.scalars(select(Alert).join(Event).where(Alert.level != "Low").order_by(Event.invoice_date.desc(), Alert.risk.desc()).limit(6)).all()
    last_run = db.scalar(select(Run).order_by(Run.id.desc()).limit(1))
    return {
        "kpis": {
            "total_events": db.scalar(select(func.count()).select_from(Event)) or 0,
            "flagged": sum(count for level, count in levels.items() if level != "Low"),
            "critical": levels.get("Critical", 0),
            "pending": db.scalar(select(func.count()).select_from(Alert).where(Alert.status == "Pending")) or 0,
            "open_cases": db.scalar(select(func.count()).select_from(Case).where(Case.status != "Closed")) or 0,
        },
        "levels": [{"level": k, "count": levels.get(k, 0)} for k in ("Low", "Medium", "High", "Critical")],
        "simulated_reviews": db.scalar(select(func.count()).select_from(Feedback).where(Feedback.comment == SEEDED_COMMENT)) or 0,
        "over_time": [{"month": m, "alerts": months[m]} for m in sorted(months)],
        "top_vendors": [{"vendor_id": v, "vendor_name": n, "alerts": c, "avg_risk": round(a, 3), "max_risk": round(m, 3)}
                        for v, n, c, a, m in top],
        "recent_alerts": [alert_row(a) for a in recent],
        "last_run": last_run and {
            "id": last_run.id, "status": last_run.status, "rows": last_run.rows, "alerts": last_run.alerts_count,
            "model_version": last_run.model_version, "finished_at": last_run.finished_at, "source": last_run.source},
    }
