"""CSV upload: preview, column mapping, validation, background run and history."""
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from sqlalchemy import select

from ml.features import LABELS, OPTIONAL, REQUIRED, read_csv, validate

from ..config import MAX_UPLOAD_BYTES, UPLOAD_DIR, UPLOAD_MAX_AGE_HOURS
from ..deps import DB, CanOperate, Id, audit
from ..models import Run, User
from ..schemas import EventBatch, MappingBody
from ..services import apply_mapping, execute_run

router = APIRouter(prefix="/upload", tags=["upload"])

MAX_COLUMNS = 500
_start_lock = threading.Lock()  # One API process; a second worker would need a database-level guard

# Common names in real exports, used to pre-fill the mapping form.
SYNONYMS = {"event_id": ["id", "transaction_id", "voucher", "voucher_number"], "vendor_id": ["vendor", "supplier_id", "supplier"],
            "amount": ["total_amount", "invoice_amount", "total", "vouchers_paid"], "invoice_date": ["date", "check_date", "transaction_date"],
            "vendor_name": ["supplier_name", "payee"], "department": ["dept", "agency"], "category": ["type", "commodity"]}


def _suggest(columns: list[str]) -> dict[str, str]:
    lowered = {c.lower().strip(): c for c in columns}
    mapping = {}
    for target in REQUIRED + OPTIONAL + LABELS:
        for name in [target, *SYNONYMS.get(target, [])]:
            if name in lowered:
                mapping[target] = lowered[name]
                break
    return mapping


def _path(upload_id: str) -> Path:
    path = UPLOAD_DIR / f"{upload_id}.csv"  # upload_id is 32 hex characters, enforced by the schema
    if not path.exists():
        raise HTTPException(404, "Upload not found. Please upload the file again.")
    return path


def _mapped(path: Path, mapping: dict[str, str]) -> pd.DataFrame:
    try:
        return apply_mapping(read_csv(path), mapping)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


def _discard_abandoned_uploads() -> None:
    """Uploads hold raw bank accounts, so ones nobody ran must not sit on disk."""
    cutoff = time.time() - UPLOAD_MAX_AGE_HOURS * 3600
    for path in UPLOAD_DIR.glob("*.csv"):
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)


@router.post("/preview")
def preview(user: CanOperate, file: UploadFile = File(...)) -> dict[str, Any]:
    # A plain def, so parsing a large file runs in the threadpool, not on the event loop.
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"The file is larger than {MAX_UPLOAD_BYTES // 1024 // 1024} MB")
    try:
        frame = read_csv(BytesIO(content))  # the whole file, so a bad line 2,500 is reported now, not after mapping
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    if len(frame.columns) > MAX_COLUMNS:
        raise HTTPException(400, f"The file has {len(frame.columns):,} columns, above the limit of {MAX_COLUMNS}")
    upload_id = uuid4().hex
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _discard_abandoned_uploads()
    (UPLOAD_DIR / f"{upload_id}.csv").write_bytes(content)
    return {"upload_id": upload_id, "filename": file.filename, "columns": list(frame.columns),
            "sample": frame.head(5).fillna("").to_dict("records"), "suggested": _suggest(list(frame.columns)),
            "required": REQUIRED, "optional": OPTIONAL, "labels": LABELS}


@router.post("/validate")
def validate_upload(body: MappingBody, user: CanOperate) -> dict[str, Any]:
    return validate(_mapped(_path(body.upload_id), body.mapping))


def _start(db: DB, user: User, background: BackgroundTasks, source: str, path: str | None, mapping: dict[str, str] | None) -> Run:
    with _start_lock:  # a double click must not start two runs: the check and the insert have to be one step
        if db.scalar(select(Run.id).where(Run.status.in_(("queued", "running"))).limit(1)):
            raise HTTPException(409, "A run is already in progress. Wait for it to finish.")
        run = Run(source=source, created_by=user.id)
        db.add(run)
        db.flush()
        audit(db, user, "run_started", "run", run.id, source=source)
        db.commit()
    background.add_task(execute_run, run.id, path, mapping)
    return run


@router.post("/run", status_code=202)
def run_upload(body: MappingBody, background: BackgroundTasks, db: DB, user: CanOperate) -> dict[str, int]:
    path = _path(body.upload_id)
    report = validate(_mapped(path, body.mapping))
    if not report["ok"]:
        raise HTTPException(422, "; ".join(report["errors"]))
    return {"run_id": _start(db, user, background, "CSV upload", str(path), body.mapping).id}


@router.post("/events", status_code=202)
def ingest_events(body: EventBatch, background: BackgroundTasks, db: DB, user: CanOperate) -> dict[str, int]:
    """Automatic intake: another system posts a batch of invoices and a run starts on them.

    The batch takes the same path as an upload (validation, then a run), so nothing about it is special.
    A 409 means a run is in progress: the sender should retry later.
    """
    rows = [event.model_dump(exclude_unset=True) for event in body.events]  # unknown keys were refused while parsing
    columns = [c for c in REQUIRED + OPTIONAL + LABELS if any(c in row for row in rows)]
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _discard_abandoned_uploads()
    path = UPLOAD_DIR / f"{uuid4().hex}.csv"
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False)
    mapping = {c: c for c in columns}
    report = validate(_mapped(path, mapping))
    if not report["ok"]:
        path.unlink(missing_ok=True)
        raise HTTPException(422, "; ".join(report["errors"]))
    try:
        run = _start(db, user, background, f"API: {body.source}", str(path), mapping)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    return {"run_id": run.id, "rows": report["rows"]}


@router.post("/rerun", status_code=202)
def rerun(background: BackgroundTasks, db: DB, user: CanOperate) -> dict[str, int]:
    """Rescore existing events, for example after changing settings."""
    return {"run_id": _start(db, user, background, "Rerun on stored events", None, None).id}


def run_row(run: Run) -> dict[str, Any]:
    return {"id": run.id, "status": run.status, "stage": run.stage, "progress": run.progress, "source": run.source,
            "rows": run.rows, "new_rows": run.new_rows, "alerts": run.alerts_count, "model_version": run.model_version,
            "error": run.error, "started_at": run.started_at, "finished_at": run.finished_at,
            "duration_seconds": round((run.finished_at - run.started_at).total_seconds(), 1) if run.finished_at else None}


@router.get("/runs")
def runs(db: DB, _: CanOperate) -> list[dict[str, Any]]:
    return [run_row(r) for r in db.scalars(select(Run).order_by(Run.id.desc()).limit(50))]


@router.get("/runs/{run_id}")
def run_status(run_id: Id, db: DB, _: CanOperate) -> dict[str, Any]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run_row(run)
