"""Evaluation metrics from the latest labelled run, plus reviewer analytics."""
import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from ml.evaluate import COMPARISON_LABELS, VARIANT_LABELS

from ..config import BACKEND_DIR
from ..deps import DB, CurrentUser
from ..models import SEEDED_COMMENT, Run
from ..services import latest_feedback

router = APIRouter(prefix="/evaluation", tags=["evaluation"])
# Written by experiments/model_comparison.py: the same four models across synthetic and real datasets.
BENCHMARKS = BACKEND_DIR / "experiments" / "model_comparison_results.json"


def _benchmarks() -> dict[str, Any] | None:
    try:
        return json.loads(BENCHMARKS.read_text())
    except (OSError, ValueError):  # not run yet, or a deployment without the experiments folder
        return None


def _latest(db: DB) -> Run | None:
    return db.scalar(select(Run).where(Run.status == "completed", Run.metrics.is_not(None)).order_by(Run.id.desc()).limit(1))


@router.get("/summary")
def public_summary(db: DB) -> dict[str, Any]:
    """Public, for the landing page: headline numbers only, null when no evaluation exists."""
    run = _latest(db)
    metrics = run.metrics if run else None
    if not metrics or "variants" not in metrics:
        return {"available": False}
    return {"available": True, "detection_rate": metrics["detection_rate"], "baseline_detection_rate": metrics["baseline_detection_rate"],
            "false_alarm_reduction": metrics["false_alarm_reduction"], "review_budget": metrics["review_budget"],
            "labelled_events": metrics["labelled_events"], "anomalies": metrics["anomalies"], "model_version": run.model_version,
            "recalibrated_on_reviews": metrics.get("recalibrated_on_reviews", 0)}


@router.get("")
def evaluation(db: DB, _: CurrentUser) -> dict[str, Any]:
    run = _latest(db)
    feedback = latest_feedback(db)  # one count per alert, however many times its decision changed
    weeks: dict[str, dict[str, int]] = defaultdict(lambda: {"Confirmed": 0, "Dismissed": 0, "Escalated": 0})
    for decision in feedback:
        weeks[decision.created_at.strftime("%G-W%V")][decision.action] += 1
    trend = []
    for week in sorted(weeks):
        counts = weeks[week]
        decided = counts["Confirmed"] + counts["Dismissed"]
        trend.append({"week": week, **counts, "false_alarm_share": round(counts["Dismissed"] / decided, 3) if decided else None})
    totals = {k: sum(w[k] for w in weeks.values()) for k in ("Confirmed", "Dismissed", "Escalated")}
    return {
        "metrics": run.metrics if run else None, "model_version": run.model_version if run else None,
        # Only variants that ran: without torch there is no LSTM + IF row to show.
        "variant_labels": {k: v for k, v in VARIANT_LABELS.items() if run and k in run.metrics.get("variants", {})},
        "comparison_labels": COMPARISON_LABELS,
        "benchmarks": _benchmarks(),
        "feedback": {"totals": totals, "trend": trend, "seeded": sum(f.comment == SEEDED_COMMENT for f in feedback)},
    }
