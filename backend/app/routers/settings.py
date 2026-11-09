"""Pipeline settings, model versions and recalibration from reviewer feedback."""
import json
from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ml.features import RULE_LABELS, RULES
from ml.fusion import recalibrate

from ..config import MODELS_DIR
from ..deps import DB, CanOperate, audit
from ..models import SEEDED_COMMENT, Alert, Setting
from ..schemas import SettingsBody
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
    real = {f.alert_id: f.label for f in decisions if f.comment != SEEDED_COMMENT}
    rows = db.execute(select(Alert.id, Alert.a_score, Alert.d_score, Alert.f_score).where(Alert.id.in_(real))).all()
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
