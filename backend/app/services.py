"""Detection runs: load events, score them, and persist alerts, cases and notifications.

A run always scores the full event history, because baselines need it. Uploads add to that
history, and reviewer decisions survive every rerun.
"""
import logging
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from ml.explain import build_facts, narrate, template_explanation
from ml.features import LABELS, OPTIONAL, REQUIRED, RULES, prepare, read_csv
from ml.pipeline import PipelineResult, merged_settings, run_pipeline

from .config import QWEN_PROVIDER
from .db import SessionLocal
from .deps import audit, notify
from .models import Alert, Case, EntityBaseline, Event, Feedback, Run, Setting, User, utcnow

log = logging.getLogger("afed.services")

INPUT_COLUMNS = REQUIRED + OPTIONAL + LABELS
CASE_WINDOW = timedelta(days=30)
NARRATED_PER_RUN = 50  # A remote model on every alert is slow and costly; the rest use the template until /explain
MAX_NARRATOR_FAILURES = 3  # in a row: a hung provider must not cost a 30 second timeout per alert


def get_settings(db: Session) -> dict[str, Any]:
    row = db.get(Setting, 1)
    if row is None:
        row = Setting(id=1, data=merged_settings({"qwen_provider": QWEN_PROVIDER}))
        db.add(row)
        db.commit()
    return merged_settings(row.data)


def apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Build AFED's columns from the mapped sources.

    Selecting rather than renaming: one source can feed two fields, a source can share a name
    with another target, and a field set to "Not in file" stays out even if the name exists.
    """
    return pd.DataFrame({target: df[source] for target, source in mapping.items() if target in INPUT_COLUMNS and source in df.columns})


def _clean(value: Any) -> Any:
    """Convert pandas and numpy scalars into what the database driver accepts."""
    if value is None or value is pd.NaT or value is pd.NA:
        return None
    if isinstance(value, (float, np.floating)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def new_events(db: Session, df: pd.DataFrame) -> pd.DataFrame:
    """Rows whose event_id is not stored yet."""
    clean = prepare(df)
    return clean[~clean["event_id"].isin(set(db.scalars(select(Event.event_id))))]


def _insert_events(db: Session, fresh: pd.DataFrame) -> None:
    rows = [{c: _clean(v) for c, v in zip(INPUT_COLUMNS, values)} for values in fresh[INPUT_COLUMNS].itertuples(index=False)]
    if rows:
        db.execute(Event.__table__.insert(), rows)


def ingest(db: Session, df: pd.DataFrame) -> int:
    """Store rows whose event_id is new and return how many were added."""
    fresh = new_events(db, df)
    _insert_events(db, fresh)
    db.commit()
    return len(fresh)


def load_events(db: Session) -> pd.DataFrame:
    columns = [getattr(Event, c) for c in INPUT_COLUMNS]
    return pd.DataFrame(db.execute(select(*columns)).all(), columns=INPUT_COLUMNS)


def latest_feedback(db: Session) -> list[Feedback]:
    """Each alert's current decision. Earlier decisions on the same alert were overruled."""
    newest = select(func.max(Feedback.id)).group_by(Feedback.alert_id)
    return list(db.scalars(select(Feedback).where(Feedback.id.in_(newest))))


def _fired(row: dict[str, Any]) -> list[str]:
    return [name for name in RULES if row.get(f"flag_{name}")]


def _draft_alerts(result: PipelineResult, settings: dict[str, Any], keep: set[str]) -> list[dict[str, Any]]:
    """Facts and narration, worked out before any write. A slow provider must never hold the database.

    `keep` is events that already have an alert: those stay in step with their event even at Low.
    """
    limit, provider = float(settings["approval_limit"]), settings["qwen_provider"]
    scored = result.scored
    rows = scored[(scored["level"] != "Low") | scored["event_id"].isin(keep)].sort_values("risk", ascending=False)
    failures = 0
    drafts = []
    for rank, row in enumerate(rows.to_dict("records")):
        facts = build_facts(row, limit)
        risk, level = float(row["risk"]), str(row["level"])
        if rank < NARRATED_PER_RUN and failures < MAX_NARRATOR_FAILURES and provider != "template":
            text, used = narrate(facts, level, risk, "en", provider)
            failures = failures + 1 if used == "template" else 0
        else:
            text, used = template_explanation(facts, level, risk), "template"
        drafts.append({"event_id": row["event_id"], "vendor_id": row["vendor_id"], "risk": risk, "level": level, "a_score": float(row["a_score"]),
                       "d_score": float(row["d_score"]), "f_score": float(row["f_score"]), "lstm_score": _clean(row["lstm_percentile"]),
                       "flags": _fired(row), "facts": facts, "explanation": text, "explanation_provider": used})
    return drafts


def _save_events(db: Session, scored: pd.DataFrame, ids: dict[str, int]) -> None:
    columns = ["baseline_source", "baseline_amount", "expected_amount", "amt_z", "amt_ratio", "freq_z", "proc_z", "risk", "level"]
    frame = scored[["event_id", *columns, *[f"flag_{name}" for name in RULES]]]
    rows = []
    for record in frame.to_dict("records"):
        row = {c: _clean(record[c]) for c in columns}
        row.update(id=ids[record["event_id"]], flags=_fired(record))
        rows.append(row)
    db.execute(update(Event), rows)


def _save_baselines(db: Session, baselines: pd.DataFrame) -> None:
    db.execute(delete(EntityBaseline))
    rows = [{k: _clean(v) for k, v in r.items()} for r in baselines.to_dict("records")]
    db.execute(EntityBaseline.__table__.insert(), [{**r, "entity_type": "vendor", "updated_at": utcnow()} for r in rows])


def _save_alerts(db: Session, run: Run, version: str, drafts: list[dict[str, Any]], ids: dict[str, int]) -> tuple[list[Alert], int]:
    """Upsert alerts and return (new alerts, existing alerts that became Critical).

    An alert that no longer qualifies goes only if nobody has touched it. Reviewed, assigned and
    closed-case alerts stay, and are refreshed so they never contradict their event.
    """
    existing = {a.event_pk: a for a in db.scalars(select(Alert).options(joinedload(Alert.case)))}
    created: list[Alert] = []
    upgraded = 0
    stale: list[int] = []
    for draft in drafts:
        alert = existing.get(ids[draft["event_id"]])
        if draft["level"] == "Low" and alert is not None and alert.status == "Pending" and alert.assignee_id is None \
                and not (alert.case and alert.case.status == "Closed"):
            stale.append(alert.id)
            continue
        if alert is None:
            alert = Alert(event_pk=ids[draft["event_id"]], vendor_id=draft["vendor_id"], status="Pending")
            db.add(alert)
            created.append(alert)
        elif draft["level"] == "Critical" and alert.level != "Critical":
            upgraded += 1
        for field in ("risk", "level", "a_score", "d_score", "f_score", "lstm_score", "flags", "facts", "explanation", "explanation_provider"):
            setattr(alert, field, draft[field])
        alert.run_id, alert.model_version = run.id, version
    db.flush()
    if stale:
        # The condition is repeated in SQL, so a review committed while this run worked is safe from it.
        removed = db.execute(delete(Alert).where(Alert.id.in_(stale), Alert.status == "Pending", Alert.assignee_id.is_(None))
                             .returning(Alert.id).execution_options(synchronize_session=False)).scalars().all()
        audit(db, None, "alerts_removed", "run", run.id, count=len(removed), alert_ids=removed[:500])
    return created, upgraded


def _fits(case: Case, date: Any) -> bool:
    return max(case.window_end, date) - min(case.window_start, date) <= CASE_WINDOW


def assign_cases(db: Session) -> int:
    """Group alerts per vendor into cases spanning at most 30 days. A case needs 2+ alerts or one Critical.

    Single non-critical alerts stay uncased: a case per alert would just repeat the queue.
    """
    open_cases: dict[str, list[Case]] = defaultdict(list)
    for case in db.scalars(select(Case).where(Case.status != "Closed")):
        open_cases[case.vendor_id].append(case)

    loose = db.scalars(select(Alert).join(Event).where(Alert.case_id.is_(None), Alert.status != "Dismissed", Alert.level != "Low")
                       .order_by(Alert.vendor_id, Event.invoice_date)).all()
    by_vendor: dict[str, list[Alert]] = defaultdict(list)
    for alert in loose:
        by_vendor[alert.vendor_id].append(alert)

    made = 0
    for vendor, alerts in by_vendor.items():
        left: list[Alert] = []
        for alert in alerts:
            date = alert.event.invoice_date
            case = next((c for c in open_cases[vendor] if _fits(c, date)), None)
            if case is None:
                left.append(alert)
            else:
                alert.case = case
                case.window_start, case.window_end = min(case.window_start, date), max(case.window_end, date)
        while left:
            start = left[0].event.invoice_date
            bucket = [a for a in left if a.event.invoice_date <= start + CASE_WINDOW]
            left = left[len(bucket):]
            if len(bucket) >= 2 or any(a.level == "Critical" for a in bucket):
                case = Case(vendor_id=vendor, vendor_name=bucket[0].event.vendor_name, window_start=start,
                            window_end=bucket[-1].event.invoice_date)
                db.add(case)
                open_cases[vendor].append(case)
                made += 1
                for alert in bucket:
                    alert.case = case
    db.flush()
    _tidy_cases(db)
    return made


def _tidy_cases(db: Session) -> None:
    """Reruns can take alerts out of a case. An emptied case goes, or closes if someone worked on it."""
    db.expire_all()
    for case in db.scalars(select(Case).where(Case.status != "Closed").options(selectinload(Case.alerts).joinedload(Alert.event))):
        dates = [a.event.invoice_date for a in case.alerts]
        if dates:
            case.window_start, case.window_end = min(dates), max(dates)
        elif case.notes or case.assignee_id:
            case.status = "Closed"
        else:
            db.delete(case)
    db.flush()


def _notify_run(db: Session, run: Run, created: list[Alert], upgraded: int) -> None:
    staff = list(db.scalars(select(User.id).where(User.role.in_(("Admin", "Reviewer")), User.is_active)))
    critical = sum(a.level == "Critical" for a in created) + upgraded
    if critical:
        notify(db, staff, "critical_alert", f"{critical} new critical alerts", "Review them first in the queue.", "/alerts?level=Critical")
    people = set(db.scalars(select(User.id).where(User.role.in_(("Admin", "Analyst")), User.is_active)))
    if run.created_by:
        people.add(run.created_by)
    notify(db, sorted(people), "run_completed", f"Run {run.id} completed",
           f"{run.rows:,} events scored, {len(created):,} new alerts, model {run.model_version}.", "/upload")


def execute_run(run_id: int, upload_path: str | None = None, mapping: dict[str, str] | None = None) -> None:
    """The whole detection job. Runs in a background thread with its own session.

    New rows are only stored with the results, in one commit: a failed run leaves nothing behind.
    """
    with SessionLocal() as db:
        run = db.get(Run, run_id)

        def progress(pct: int, stage: str) -> None:
            run.status, run.progress, run.stage = "running", pct, stage
            db.commit()

        try:
            progress(2, "Loading data")
            fresh = new_events(db, apply_mapping(read_csv(upload_path), mapping or {})) if upload_path else pd.DataFrame(columns=INPUT_COLUMNS)
            stored = load_events(db)
            frame = pd.concat([f[INPUT_COLUMNS] for f in (stored, fresh) if len(f)], ignore_index=True) if len(stored) or len(fresh) else stored
            if frame.empty:
                raise ValueError("There are no events to score. Upload a CSV first.")
            settings = get_settings(db)
            result = run_pipeline(frame, settings, progress)

            progress(90, "Writing explanations")
            keep = set(db.scalars(select(Event.event_id).join(Alert, Alert.event_pk == Event.id)))
            drafts = _draft_alerts(result, settings, keep)

            progress(94, "Saving alerts and cases")
            _insert_events(db, fresh)
            run.new_rows = len(fresh)
            ids = dict(db.execute(select(Event.event_id, Event.id)).all())
            _save_events(db, result.scored, ids)
            _save_baselines(db, result.baselines)
            created, upgraded = _save_alerts(db, run, result.version, drafts, ids)
            assign_cases(db)

            run.rows, run.model_version, run.metrics = len(result.scored), result.version, result.metrics
            run.alerts_count = int((result.scored["level"] != "Low").sum())
            run.status, run.progress, run.stage, run.finished_at = "completed", 100, "Completed", utcnow()
            _notify_run(db, run, created, upgraded)
            audit(db, None, "run_completed", "run", run.id, model_version=result.version, alerts=run.alerts_count)
            db.commit()
        except Exception as error:
            log.exception("Run %s failed", run_id)
            db.rollback()
            run = db.get(Run, run_id)
            run.status, run.stage, run.error, run.finished_at = "failed", "Failed", str(error)[:1000], utcnow()
            db.commit()
        finally:
            if upload_path:
                Path(upload_path).unlink(missing_ok=True)


def mark_interrupted_runs(db: Session) -> None:
    """A restart kills background threads, so anything still marked active never finishes."""
    db.execute(update(Run).where(Run.status.in_(("queued", "running")))
               .values(status="failed", stage="Failed", error="Interrupted by a server restart", finished_at=utcnow()))
    db.commit()
