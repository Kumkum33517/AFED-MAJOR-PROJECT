"""Pipeline settings, model versions and recalibration from reviewer feedback."""
import json
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ml.features import RULE_LABELS, RULES
from ml.fusion import calibrate_medium, calibrated_thresholds, recalibrate

from ..config import MODELS_DIR
from ..deps import DB, CanOperate, audit
from ..models import SEEDED_COMMENT, Alert, Event, Setting
from ..schemas import CalibrateBody, SettingsBody
from ..services import get_settings, latest_feedback

router = APIRouter(prefix="/settings", tags=["settings"])


def _store(db: DB, data: dict[str, Any]) -> None:
    row = db.get(Setting, 1)
    row.data = data


@router.get("")
def read_settings(db: DB, _: CanOperate) -> dict[str, Any]:
    return {**get_settings(db), "rule_info": [{"name": n, "label": RULE_LABELS[n], "severity": w} for n, w in RULES.items()]}


@router.put("")
def write_settings(body: SettingsBody, db: DB, user: CanOperate) -> dict[str, Any]:
    t = body.thresholds
    if not t.medium < t.high < t.critical:
        raise HTTPException(422, "Thresholds must rise: Medium < High < Critical")
    if abs(body.weights.w1 + body.weights.w2 + body.weights.w3 - 1) > 0.011:
        raise HTTPException(422, "Weights w1, w2 and w3 must add up to 1")
    contamination: Any = body.contamination
    if contamination != "auto":
        try:
            contamination = float(contamination)
        except ValueError:
            raise HTTPException(422, 'Contamination must be "auto" or a number') from None
        if not 0 < contamination <= 0.5:
            raise HTTPException(422, "Contamination must be between 0 and 0.5")
    unknown = set(body.rules) - set(RULES)
    if unknown:
        raise HTTPException(422, f"Unknown rules: {', '.join(sorted(unknown))}")
    current = get_settings(db)  # also makes sure the row exists
    data = {**body.model_dump(), "contamination": contamination, "recalibrated_on_reviews": current.get("recalibrated_on_reviews", 0)}
    _store(db, data)
    audit(db, user, "settings_updated", "settings", 1, **data)
    db.commit()
    return read_settings(db, user)


@router.post("/calibrate")
def calibrate(body: CalibrateBody, db: DB, _: CanOperate) -> dict[str, Any]:
    """Preview a calibrated Medium cut-off on the stored events, without saving anything.

    Alert budget needs no labels. Label-based needs labelled events, so it only works on evaluation data.
    """
    rows = db.execute(select(Event.risk, Event.invoice_date, Event.is_anomaly).where(Event.risk.is_not(None))).all()
    if not rows:
        raise HTTPException(409, "No scored events yet. Run the detection first.")
    risk = np.array([r[0] for r in rows], dtype=float)
    labels = np.array([np.nan if r[2] is None else r[2] for r in rows], dtype=float)
    chosen = calibrate_medium(risk, pd.Series([r[1] for r in rows]), body.mode, body.target_rate, body.fit_share, labels)
    if chosen is None:
        raise HTTPException(422, "Label-based calibration needs labelled events of both kinds, which real data does not have. "
                                 "Use the alert budget." if body.mode == "label" else "Too few events to calibrate.")
    thresholds = calibrated_thresholds(get_settings(db)["thresholds"], chosen["medium"])
    return {**chosen, "thresholds": thresholds, "alerts_all": int((risk >= chosen["medium"]).sum()),
            "alert_rate_all": round(float((risk >= chosen["medium"]).mean()), 6), "events": len(risk)}


@router.get("/models")
def model_versions(_: CanOperate) -> list[dict[str, Any]]:
    versions = []
    for folder in sorted(MODELS_DIR.glob("v*"), reverse=True)[:30]:
        metrics_file = folder / "metrics.json"
        metrics = json.loads(metrics_file.read_text()) if metrics_file.exists() else None
        afed = (metrics or {}).get("variants", {}).get("afed", {})
        versions.append({"version": folder.name, "has_lstm": (folder / "lstm.pt").exists(),
                         "recall": afed.get("recall"), "precision": afed.get("precision"), "roc_auc": afed.get("roc_auc")})
    return versions


@router.post("/recalibrate")
def recalibrate_from_feedback(db: DB, user: CanOperate) -> dict[str, Any]:
    """Fit weights and the Medium cut-off to reviewer labels. Takes effect on the next run.

    Simulated seed reviews never count: they are copies of the evaluation labels, so fitting to
    them would tune the model on its own answer key and inflate every published metric.
    """
    decisions = [f for f in latest_feedback(db) if f.label is not None]
    real = {f.alert_id: f.label for f in sorted(decisions, key=lambda f: (f.created_at, f.id)) if f.comment != SEEDED_COMMENT}
    found = {r.id: r for r in db.execute(select(Alert.id, Alert.a_score, Alert.d_score, Alert.f_score).where(Alert.id.in_(real)))}
    rows = [found[i] for i in real if i in found]  # oldest review first: the newest are held back to check the fit
    settings = get_settings(db)
    a, d, f = (np.array([r[i] for r in rows], dtype=float) for i in (1, 2, 3))
    labels = np.array([real[r.id] for r in rows], dtype=int)
    result = recalibrate(a, d, f, labels, settings)
    result["simulated_excluded"] = len(decisions) - len(real)
    if result["ok"]:
        settings["weights"], settings["thresholds"] = result["weights"], result["thresholds"]
        settings["recalibrated_on_reviews"] = result["reviews"]
        _store(db, settings)
        audit(db, user, "recalibrated", "settings", 1, **{k: v for k, v in result.items() if k != "ok"})
        db.commit()
    return result
