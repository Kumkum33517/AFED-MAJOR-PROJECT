"""AFED on real data with injected anomalies, as pre-registered in real_data_evaluation.md.

    python experiments/real_data_evaluation.py

Each (dataset, seed, arm) result is cached in experiments/.cache/, so an interrupted run resumes.
Writes experiments/real_data_evaluation_results.md.
"""
import json
import sys
import tempfile
import time
import warnings
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent / "data" / "scripts")]
warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

from common import PROCESSED, to_afed  # noqa: E402
from ml import pipeline  # noqa: E402
from ml.inject import TYPES, inject  # noqa: E402

DATASETS = ["nspcl", "mplads", "bbmp_2024", "bbmp_2010_2019", "chicago", "secop", "delaware", "cppp"]
SEEDS, ARMS = [1, 2, 3], {"with": True, "without": False}
CACHE = Path(__file__).parent / ".cache"
pipeline.MODELS_DIR = Path(tempfile.mkdtemp())


def measure(frame: pd.DataFrame, in_forest: bool) -> dict[str, Any]:
    started = time.perf_counter()
    m = pipeline.run_pipeline(frame, {"lstm": {"in_forest": in_forest}}).metrics
    a = m["variants"]["afed"]
    return {"recall": a["recall"], "alerts": m["review_budget"], "false_alarms": a["false_positives"], "precision": a["precision"],
            "f1": a["f1"], "roc_auc": a["roc_auc"], "ap": a["average_precision"], "by_type": a["recall_by_type"],
            "ms_per_event": round((time.perf_counter() - started) * 1000 / len(frame), 3), "events": len(frame),
            "reduction_vs_baseline": m["investigation"]["reduction_vs_baseline"]}


def run(name: str) -> dict[int, dict[str, Any]] | None:
    path = PROCESSED / f"{name}.parquet"
    if not path.exists():
        print(f"{name}: not loaded, skipped")
        return None
    real = to_afed(pd.read_parquet(path))
    results = {}
    for seed in SEEDS:
        frame = inject(real, seed)
        results[seed] = {}
        for arm, flag in ARMS.items():
            cached = CACHE / f"{name}_{seed}_{arm}.json"
            if not cached.exists():
                CACHE.mkdir(exist_ok=True)
                cached.write_text(json.dumps(measure(frame, flag)))
            results[seed][arm] = json.loads(cached.read_text())
        w, wo = results[seed]["with"], results[seed]["without"]
        print(f"{name} seed {seed}: recall {w['recall']:.3f} vs {wo['recall']:.3f}, alerts {w['alerts']} vs {wo['alerts']}", flush=True)
    return results


def spread(values: list[float], digits: int = 3) -> str:
    return f"{mean(values):.{digits}f} ± {stdev(values):.{digits}f}"


def report(results: dict[str, dict[int, dict[str, Any]]]) -> list[str]:
    lines = ["## Summary, AFED with the brief's default (LSTM errors in the forest)", "",
             "| Dataset | Events | Recall | Precision | F1 | ROC-AUC | Avg precision | Alerts | Fewer reviews than global IF | ms per event |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        w = [s["with"] for s in r.values()]
        reduction = [x["reduction_vs_baseline"] for x in w if x["reduction_vs_baseline"] is not None]
        lines.append(f"| {name} | {w[0]['events']:,} | {spread([x['recall'] for x in w])} | {spread([x['precision'] for x in w])} | "
                     f"{spread([x['f1'] for x in w])} | {spread([x['roc_auc'] for x in w])} | {spread([x['ap'] for x in w])} | "
                     f"{spread([x['alerts'] for x in w], 0)} | {spread(reduction) if len(reduction) > 1 else 'n/a'} | {mean(x['ms_per_event'] for x in w):.2f} |")
    lines += ["", "## Recall by injected type, with LSTM errors", "", "| Dataset | " + " | ".join(TYPES) + " |", "|---|" + "---|" * len(TYPES)]
    for name, r in results.items():
        lines.append(f"| {name} | " + " | ".join(spread([s["with"]["by_type"].get(t, 0.0) for s in r.values()]) for t in TYPES) + " |")
    lines += ["", "## LSTM errors in the forest: the pre-registered rule, per dataset", "",
              "| Dataset | Recall with | Recall without | Alerts with | Alerts without | Seeds with higher recall | Verdict |", "|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        w, wo = [s["with"] for s in r.values()], [s["without"] for s in r.values()]
        d_recall = [a["recall"] - b["recall"] for a, b in zip(w, wo)]
        d_alerts = [a["alerts"] - b["alerts"] for a, b in zip(w, wo)]
        wins = sum(d > 0 for d in d_recall)
        verdict = "PASS" if mean(d_recall) > 0 and mean(d_alerts) <= 0 and wins >= 2 else "FAIL"
        lines.append(f"| {name} | {spread([x['recall'] for x in w])} | {spread([x['recall'] for x in wo])} | "
                     f"{spread([x['alerts'] for x in w], 0)} | {spread([x['alerts'] for x in wo], 0)} | {wins} of 3 | {verdict} |")
    return lines


if __name__ == "__main__":
    done = {name: r for name in DATASETS if (r := run(name))}
    out = ["# AFED on real data with injected anomalies: results", "",
           "Produced by `experiments/real_data_evaluation.py`, following `real_data_evaluation.md`. Real rows are treated as normal, "
           "so precision is a lower bound. Anomalies are injected, not real fraud.", "", *report(done)]
    (Path(__file__).parent / "real_data_evaluation_results.md").write_text("\n".join(out) + "\n")
    print("written")
