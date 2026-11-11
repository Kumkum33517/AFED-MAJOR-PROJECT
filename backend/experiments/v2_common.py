"""Shared by the v2 experiments: datasets, planting, splits, cached scored runs and measures.

Splits (fixed in the v2 brief, before any v2 result):
  tuning    planted seeds 1-3, synthetic seeds 42/7/123, events before the 60th percentile of each run's dates
  reporting planted seeds 4-6, synthetic seeds 11/12/13, events from the 60th percentile on
"""
import json
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "data"), str(ROOT.parent / "data" / "scripts")]
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

import generate_synthetic  # noqa: E402
from common import PROCESSED, to_afed  # noqa: E402
from ml import pipeline  # noqa: E402
from ml.features import RULES, available_inputs, read_csv  # noqa: E402
from ml.inject import inject  # noqa: E402

OUT = Path(__file__).parent
CACHE = OUT / ".cache" / "v2"
CUT = 0.60
TUNING_PLANTED, REPORTING_PLANTED = (1, 2, 3), (4, 5, 6)
TUNING_SYNTHETIC, REPORTING_SYNTHETIC = (42, 7, 123), (11, 12, 13)
MAIN_REAL = ["nspcl", "mplads", "chicago", "delaware"]
OTHER_REAL = ["bbmp_2024", "bbmp_2010_2019", "secop", "ocds_assam"]
EXTRA_SYNTHETIC = ["icai"]  # third-party synthetic, unlabelled, so planted like the real ledgers
TYPES = ["amount_spike", "slow_drift", "frequency_shift", "off_cycle_invoice"]
KEEP = ["event_id", "vendor_id", "invoice_date", "amount", "is_anomaly", "anomaly_type", "a_score", "d_score", "f_score",
        "if_score", "rule_score", "entity_deviation", "risk", "level", "baseline_source", "history_len", "amt_z", "freq_z",
        "proc_z", "flag_count", *[f"flag_{r}" for r in RULES], *pipeline.RAW_FEATURES]
pipeline.MODELS_DIR = Path(tempfile.mkdtemp())


def as_uploaded(frame: pd.DataFrame) -> pd.DataFrame:
    path = Path(tempfile.mkdtemp()) / "data.csv"
    frame.to_csv(path, index=False)
    return read_csv(path)


def tuning_seeds(name: str) -> tuple[int, ...]:
    return TUNING_SYNTHETIC if name == "afed_synthetic" else TUNING_PLANTED


def reporting_seeds(name: str) -> tuple[int, ...]:
    return REPORTING_SYNTHETIC if name == "afed_synthetic" else REPORTING_PLANTED


def raw_frame(name: str, seed: int, plant: Callable[[pd.DataFrame, int], pd.DataFrame] = inject) -> pd.DataFrame:
    """The AFED-schema input of one run: synthetic data generated with the seed, or a ledger with anomalies planted."""
    if name == "afed_synthetic":
        return as_uploaded(generate_synthetic.generate(seed))
    return plant(to_afed(pd.read_parquet(PROCESSED / f"{name}.parquet")), seed)


def scored(name: str, seed: int, arm: str, settings: dict[str, Any] | None = None,
           plant: Callable[[pd.DataFrame, int], pd.DataFrame] = inject, plant_tag: str = "inj") -> pd.DataFrame:
    """One pipeline run, cached by dataset, seed, planting and arm. Changing an arm's meaning needs a new arm name."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}_{plant_tag}{seed}_{arm}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    raw = raw_frame(name, seed, plant)
    result = pipeline.run_pipeline(raw, settings, evaluate_labels=False)
    df = result.scored
    keep = [c for c in KEEP + [c for c in df.columns if c.startswith(("seq_", "ewma_err_", "lstm_err_"))] if c in df.columns]
    out = df[keep].copy()
    out["flags"] = df["flags"].apply(lambda f: ";".join(f)) if "flags" in df.columns else ""
    out["is_anomaly"] = out["is_anomaly"].astype(float)
    out.attrs = {}
    out.to_parquet(path)
    meta = {"inputs": available_inputs(df), "seconds": result.seconds, "events": len(df),
            "active": getattr(result, "active", None)}
    path.with_suffix(".json").write_text(json.dumps(meta, default=str))
    return out


def meta(name: str, seed: int, arm: str, plant_tag: str = "inj") -> dict[str, Any]:
    return json.loads((CACHE / f"{name}_{plant_tag}{seed}_{arm}.json").read_text())


def early_mask(df: pd.DataFrame) -> np.ndarray:
    dates = pd.to_datetime(df["invoice_date"])
    return (dates < dates.quantile(CUT)).to_numpy()


def classify(y: np.ndarray, alert: np.ndarray, score: np.ndarray) -> dict[str, float]:
    tp, fp = int((alert & (y == 1)).sum()), int((alert & (y == 0)).sum())
    fn, tn = int((~alert & (y == 1)).sum()), int((~alert & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    both = len(set(y.tolist())) == 2
    return {"f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0, "precision": precision,
            "recall": recall, "alerts": tp + fp, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "roc_auc": float(roc_auc_score(y, score)) if both else float("nan"),
            "pr_auc": float(average_precision_score(y, score)) if both else float("nan")}


def by_type(df: pd.DataFrame, alert: np.ndarray) -> dict[str, float]:
    out = {}
    for kind in sorted(df.loc[df["is_anomaly"] == 1, "anomaly_type"].dropna().unique()):
        rows = (df["is_anomaly"] == 1).to_numpy() & (df["anomaly_type"] == kind).to_numpy()
        out[kind] = float(alert[rows].mean()) if rows.any() else float("nan")
    return out


def spread(values: list[float], digits: int = 3) -> str:
    values = [v for v in values if v == v]
    if not values:
        return "n/a"
    sd = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return f"{np.mean(values):.{digits}f} ± {sd:.{digits}f}"
