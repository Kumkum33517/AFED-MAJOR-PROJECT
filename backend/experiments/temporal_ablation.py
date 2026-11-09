"""LSTM ablation on temporal data, as pre-registered in temporal_ablation.md. Run once:

    python experiments/temporal_ablation.py

Writes experiments/temporal_ablation_results.md.
"""
import sys
import tempfile
import warnings
from pathlib import Path
from statistics import mean, stdev
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "data")]
warnings.filterwarnings("ignore")

import generate_synthetic  # noqa: E402
import generate_temporal  # noqa: E402
from ml import pipeline  # noqa: E402
from ml.features import read_csv  # noqa: E402

SEEDS = [1, 2, 3, 4, 5]
ARMS = {"with": True, "without": False}
pipeline.MODELS_DIR = Path(tempfile.mkdtemp())  # experiment runs must not fill the app's model store


def as_uploaded(frame: Any) -> Any:
    path = Path(tempfile.mkdtemp()) / "data.csv"
    frame.to_csv(path, index=False)
    return read_csv(path)


def measure(frame: Any, in_forest: bool) -> dict[str, Any]:
    metrics = pipeline.run_pipeline(frame, {"lstm": {"in_forest": in_forest}}).metrics
    afed = metrics["variants"]["afed"]
    return {"recall": afed["recall"], "alerts": metrics["review_budget"], "false_alarms": afed["false_positives"],
            "fa_rate": afed["false_alarm_rate"], "precision": afed["precision"], "ap": afed["average_precision"],
            "by_type": afed["recall_by_type"], "lstm_if_ap": metrics["variants"]["lstm_if"]["average_precision"],
            "if_entity_ap": metrics["variants"]["if_entity"]["average_precision"]}


def spread(values: list[float], digits: int = 3) -> str:
    return f"{mean(values):.{digits}f} ± {stdev(values):.{digits}f}"


def run(name: str, generate: Any) -> dict[int, dict[str, dict[str, Any]]]:
    results = {}
    for seed in SEEDS:
        frame = as_uploaded(generate(seed))
        results[seed] = {arm: measure(frame, flag) for arm, flag in ARMS.items()}
        w, wo = results[seed]["with"], results[seed]["without"]
        print(f"{name} seed {seed}: recall {w['recall']:.3f} vs {wo['recall']:.3f}, alerts {w['alerts']} vs {wo['alerts']}", flush=True)
    return results


def table(name: str, results: dict[int, dict[str, dict[str, Any]]]) -> list[str]:
    lines = [f"### {name}", "", "| Seed | Recall with | Recall without | Alerts with | Alerts without | False alarms with | False alarms without |",
             "|---|---|---|---|---|---|---|"]
    for seed, r in results.items():
        w, wo = r["with"], r["without"]
        lines.append(f"| {seed} | {w['recall']:.3f} | {wo['recall']:.3f} | {w['alerts']} | {wo['alerts']} | {w['false_alarms']} | {wo['false_alarms']} |")
    lines += ["", "| Measure, mean ± sd over seeds | With LSTM errors | Without | Paired difference (with − without) |", "|---|---|---|---|"]
    for key, label, digits in [("recall", "Recall", 3), ("alerts", "Alerts", 1), ("false_alarms", "False alarms", 1),
                               ("fa_rate", "False-alarm rate", 4), ("precision", "Precision", 3), ("ap", "Average precision", 3)]:
        w = [r["with"][key] for r in results.values()]
        wo = [r["without"][key] for r in results.values()]
        lines.append(f"| {label} | {spread(w, digits)} | {spread(wo, digits)} | {spread([a - b for a, b in zip(w, wo)], digits)} |")
    kinds = sorted(next(iter(results.values()))["with"]["by_type"])
    lines += ["", "| Recall by type, mean ± sd | With | Without |", "|---|---|---|"]
    for kind in kinds:
        lines.append(f"| {kind} | {spread([r['with']['by_type'][kind] for r in results.values()])} | {spread([r['without']['by_type'][kind] for r in results.values()])} |")
    standalone = [r["with"]["lstm_if_ap"] - r["with"]["if_entity_ap"] for r in results.values()]
    lines += ["", f"Standalone forest, LSTM + IF minus IF + entity, average precision: {spread(standalone)}.", ""]
    return lines


def decide(results: dict[int, dict[str, dict[str, Any]]]) -> tuple[bool, list[str]]:
    d_recall = [r["with"]["recall"] - r["without"]["recall"] for r in results.values()]
    d_alerts = [r["with"]["alerts"] - r["without"]["alerts"] for r in results.values()]
    checks = [("Mean recall higher with the LSTM errors", mean(d_recall) > 0, f"mean difference {mean(d_recall):+.4f}"),
              ("Mean alerts no higher with them", mean(d_alerts) <= 0, f"mean difference {mean(d_alerts):+.1f}"),
              ("Recall higher with them on at least 3 of 5 seeds", sum(d > 0 for d in d_recall) >= 3, f"{sum(d > 0 for d in d_recall)} of 5")]
    lines = ["| Pre-registered condition | Met | Value |", "|---|---|---|"] + [f"| {c} | {'yes' if ok else 'no'} | {v} |" for c, ok, v in checks]
    return all(ok for _, ok, _ in checks), lines


if __name__ == "__main__":
    temporal = run("temporal", generate_temporal.generate)
    original = run("original", generate_synthetic.generate)
    passed, conditions = decide(temporal)
    verdict = ("PASS: the LSTM's errors stay in the forest's input, and the pipeline stays as the brief requires." if passed else
               "FAIL: recommend keeping the LSTM for the expected-vs-actual chart only and removing its errors from the forest. "
               "The default does not change until the supervisor decides.")
    out = ["# LSTM ablation results", "", "Produced by `experiments/temporal_ablation.py`, following `temporal_ablation.md`.", "",
           "## Decision, on the temporal dataset", "", *conditions, "", f"**{verdict}**", "",
           "## Results", "", *table("Temporal dataset (decides)", temporal), *table("Original dataset (secondary)", original)]
    (Path(__file__).parent / "temporal_ablation_results.md").write_text("\n".join(out) + "\n")
    print("\n" + verdict)
