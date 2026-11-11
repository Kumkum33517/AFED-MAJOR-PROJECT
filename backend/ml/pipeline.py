"""Ingest -> Validate -> Features -> LSTM -> Isolation Forest -> Fusion -> Tiers -> Facts -> Evaluate.

    python -m ml.pipeline data/afed_transactions.csv

Narration, alerts and reviewer feedback happen in the API layer, on top of this module's output.
"""
import json
import secrets
import sys
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from .evaluate import compare_models, evaluate, print_report
from .features import RULES, active_rules, available_inputs, compute_features, entity_baselines, read_csv, validate
from .fusion import calibrate_medium, calibrated_thresholds, rule_share, risk_score, signals, tier
from .lstm_seq import CLIP, SEQ_FEATURES, run_lstm
from .sequence import SEQUENCE_FEATURES, add_sequence_features, ewma_forecast_errors

MODELS_DIR = Path(__file__).resolve().parents[1] / "models_store"
SEED = 42
NORMAL_BAND = 2.0

DEFAULT_SETTINGS: dict[str, Any] = {
    "approval_limit": 500_000,
    "weights": {"w1": 0.40, "w2": 0.35, "w3": 0.25},
    "thresholds": {"medium": 0.45, "high": 0.60, "critical": 0.75},
    "contamination": "auto",
    # in_forest: whether the LSTM's errors feed the Isolation Forest. The LSTM trains either way, for the chart.
    "lstm": {"window": 10, "mode": "forecast", "epochs": 12, "in_forest": True, "fit_share": 1.0},
    "rules": {name: True for name in RULES},
    "qwen_provider": "template",
    # v2 options. All off reproduces v1 exactly (tests/fixtures/v1_seed42.json).
    "field_aware": False,        # renormalise fusion over the rule inputs the data has
    # Medium cut-off chosen per run on its earliest events: "alert_budget" (no labels) or "label" (evaluation only).
    "calibration": {"mode": "off", "target_rate": 0.02, "fit_share": 0.6},
    "sequence_features": False,  # CUSUM, EWMA, trend and gap-ratio features for the forest (ml/sequence.py)
    # Evidence only: "ewma" replaces the LSTM's errors with an EWMA forecaster's (and skips the LSTM).
    "temporal_source": "lstm",
    "narration_mode": "paragraph",   # "per_fact": Qwen rewords one fact at a time, with the number-anchor check
}

RAW_FEATURES = ["log_amount", "proc_days_f", "gap_days_f", "approval_hour", "approval_dow", "category_code",
                "vendor_age_f", "po_ratio"]
ENTITY_FEATURES = ["amt_z", "log_amt_ratio", "freq_z", "proc_z", "count_7d", "burst_ratio", "history_len"]
LSTM_FEATURES = [f"lstm_err_{name}" for name in SEQ_FEATURES]
# rule_score and flag_count are summaries: ten sparse flag columns alone are rarely drawn by a random forest.
FLAG_FEATURES = [f"flag_{name}" for name in RULES] + ["rule_score", "flag_count"]

Progress = Callable[[int, str], None]


@dataclass
class PipelineResult:
    scored: pd.DataFrame
    baselines: pd.DataFrame
    version: str
    metrics: dict[str, Any] | None
    lstm_available: bool
    seconds: float  # scoring time, excluding saving and narration
    active: dict[str, Any] | None = None  # which inputs, rules and fusion weights this run used


def merged_settings(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Defaults under the stored settings, so a rule added later still has a value."""
    merged = deepcopy(DEFAULT_SETTINGS)
    for key, value in (overrides or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def fit_forest(df: pd.DataFrame, columns: list[str], contamination: Any) -> tuple[IsolationForest, np.ndarray]:
    forest = IsolationForest(n_estimators=200, contamination=contamination, random_state=SEED, n_jobs=-1)
    x = df[columns].fillna(0.0).to_numpy(dtype=float)
    forest.fit(x)
    return forest, -forest.score_samples(x)


def entity_deviation(df: pd.DataFrame) -> np.ndarray:
    """How far past its own normal band (2 robust sigmas) an event sits, in the risky direction only.

    Bigger, sooner and faster count; a small invoice or a slow approval is unusual but not a risk.
    Measuring all z-scores, or from zero, scores ordinary noise and floods reviewers with alerts.
    """
    bigger = (df["amt_z"] - NORMAL_BAND).clip(lower=0)
    sooner = (df["freq_z"] - NORMAL_BAND).clip(lower=0)
    faster = (-df["proc_z"] - NORMAL_BAND).clip(lower=0)
    return np.sqrt(bigger ** 2 + sooner ** 2 + faster ** 2).to_numpy()


def run_pipeline(raw: pd.DataFrame, settings: dict[str, Any] | None = None, progress: Progress | None = None,
                 evaluate_labels: bool = True) -> PipelineResult:
    """Score a batch. evaluate_labels=False skips the built-in evaluation (three extra forests and an LOF), which
    experiments do themselves; scores and tiers are the same either way."""
    settings = merged_settings(settings)
    report = progress or (lambda _pct, _stage: None)
    started = time.perf_counter()

    report(5, "Validating")
    check = validate(raw)
    if not check["ok"]:
        raise ValueError("; ".join(check["errors"]))

    report(10, "Building features and baselines")
    df = compute_features(raw, settings)

    if settings.get("sequence_features"):
        df = add_sequence_features(df)

    report(25, "Training LSTM")
    lstm = settings["lstm"]
    fit_share = float(lstm.get("fit_share", 1.0))
    train_rows = None if fit_share >= 1.0 else (df["invoice_date"] < df["invoice_date"].quantile(fit_share)).to_numpy()
    if settings.get("temporal_source", "lstm") == "ewma":
        sequence = {"available": False, "pred": np.zeros((len(df), len(SEQ_FEATURES))), "state": None,
                    "errors": ewma_forecast_errors(df, SEQ_FEATURES, CLIP)}
    else:
        sequence = run_lstm(df, lstm["window"], lstm["mode"], lstm["epochs"], SEED, train_rows)
    for k, column in enumerate(LSTM_FEATURES):
        df[column] = sequence["errors"][:, k]
    # Without torch these stay empty: a neutral-looking score would claim a model ran when none did.
    has_lstm = sequence["available"]
    df["lstm_err"] = sequence["errors"].sum(axis=1)
    df["lstm_percentile"] = df["lstm_err"].rank(pct=True) if has_lstm else np.nan
    df["expected_amount"] = np.exp(df["base_log_amount"] + sequence["pred"][:, 0] * df["base_log_scale"]) if has_lstm else np.nan

    report(65, "Scoring with Isolation Forest")
    contamination = settings["contamination"]
    use_ewma = settings.get("temporal_source", "lstm") == "ewma"
    sequence_columns = LSTM_FEATURES if (has_lstm or use_ewma) and lstm.get("in_forest", True) else []
    columns = RAW_FEATURES + ENTITY_FEATURES + sequence_columns + FLAG_FEATURES
    if settings.get("sequence_features"):
        columns = columns + SEQUENCE_FEATURES
    forest, if_score = fit_forest(df, columns, contamination)
    df["if_score"] = if_score
    df["if_percentile"] = (df["if_score"].rank() - 1) / len(df)  # the share of events below this one

    report(75, "Fusing risk and assigning tiers")
    df["entity_deviation"] = entity_deviation(df)
    a, d, f = signals(if_score, df["entity_deviation"].to_numpy(), df["rule_score"].to_numpy())
    df["a_score"], df["d_score"], df["f_score"] = a, d, f
    inputs = available_inputs(df)
    rules_on = [r for r in active_rules(inputs) if settings["rules"].get(r, True)]
    share = rule_share(rules_on, RULES)
    used_share = share if settings.get("field_aware") else 1.0
    df["risk"] = risk_score(a, d, f, settings["weights"], used_share)
    w = settings["weights"]
    w3 = w["w3"] * used_share
    active = {"inputs": inputs, "rules": rules_on, "rule_share": round(share, 4), "field_aware": bool(settings.get("field_aware")),
              "weights_effective": {k: round(v / (w["w1"] + w["w2"] + w3), 4) for k, v in (("w1", w["w1"]), ("w2", w["w2"]), ("w3", w3))}
              if used_share < 1 else dict(w)}
    calibration = settings.get("calibration") or {}
    chosen = calibrate_medium(df["risk"].to_numpy(), df["invoice_date"], calibration.get("mode", "off"),
                              calibration.get("target_rate", 0.02), calibration.get("fit_share", 0.6),
                              df["is_anomaly"].to_numpy(dtype=float))
    thresholds = calibrated_thresholds(settings["thresholds"], chosen["medium"]) if chosen else settings["thresholds"]
    df["level"] = tier(df["risk"].to_numpy(), thresholds)
    active["calibration"] = {**chosen, "thresholds": thresholds} if chosen else {"mode": calibration.get("mode", "off"), "applied": False}

    report(82, "Evaluating against labels")
    metrics = None
    if evaluate_labels and df["is_anomaly"].notna().any():
        global_forest, global_score = fit_forest(df, RAW_FEATURES, contamination)
        variants = {
            "global_if": global_score,
            "if_entity": fit_forest(df, RAW_FEATURES + ENTITY_FEATURES, contamination)[1],
        }
        if has_lstm:
            variants["lstm_if"] = fit_forest(df, RAW_FEATURES + ENTITY_FEATURES + LSTM_FEATURES, contamination)[1]
        variants["afed"] = df["risk"].to_numpy()
        # Only labelled alerts count: alerts on unlabelled events must not buy the labelled set extra review budget.
        metrics = evaluate(df, variants, int(((df["level"] != "Low") & df["is_anomaly"].notna()).sum()))
        if metrics:  # recalibrated weights were tuned on decisions about this same data, so readers must be told
            metrics["recalibrated_on_reviews"] = settings.get("recalibrated_on_reviews", 0)
            global_alert = global_forest.predict(df[RAW_FEATURES].fillna(0.0).to_numpy(dtype=float)) == -1
            metrics["comparison"] = compare_models(df, RAW_FEATURES, global_alert, global_score, float(settings["approval_limit"]))

    seconds = round(time.perf_counter() - started, 2)
    if metrics:
        metrics["processing_seconds"] = seconds
        metrics["ms_per_event"] = round(seconds * 1000 / len(df), 3)
    report(88, "Saving model version")
    version = f"{datetime.now():v%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"  # two runs can share a second
    folder = MODELS_DIR / version
    folder.mkdir(parents=True, exist_ok=True)
    joblib.dump({"forest": forest, "columns": columns}, folder / "isolation_forest.joblib")
    if sequence["available"]:
        import torch
        torch.save(sequence["state"], folder / "lstm.pt")
    (folder / "settings.json").write_text(json.dumps(settings, indent=2))
    (folder / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (folder / "active.json").write_text(json.dumps(active, indent=2))
    if metrics:
        metrics["active"] = active

    return PipelineResult(df, entity_baselines(df), version, metrics, sequence["available"], seconds, active)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/afed_transactions.csv"
    started = time.time()
    result = run_pipeline(read_csv(path), progress=lambda pct, stage: print(f"[{pct:3d}%] {stage}  ({time.time() - started:.1f}s)"))
    print(f"\nModel {result.version}, LSTM {'on' if result.lstm_available else 'skipped'}, {time.time() - started:.1f}s total")
    print(result.scored["level"].value_counts().reindex(["Low", "Medium", "High", "Critical"]).fillna(0).astype(int).to_string())
    if result.metrics:
        print_report(result.metrics)
