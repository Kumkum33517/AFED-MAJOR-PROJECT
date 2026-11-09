"""Rule-based, Global Isolation Forest, LOF and AFED on the same data, with every requested metric.

    python experiments/model_comparison.py

Models, fixed before any result was seen:
  Rule-based   alert when the amount is at or above a fixed Rs 5,00,000 (the approval limit). Score: the amount.
  Global IF    scikit-learn IsolationForest on the raw features only, its own contamination="auto" cut-off.
  LOF          scikit-learn LocalOutlierFactor (20 neighbours) on the same raw features, standardised, contamination="auto".
  AFED         the whole pipeline at default settings; an alert is Medium risk or above. Score: the risk.
Datasets, fixed by a fitness test, not by results:
  Labelled synthetic: afed_synthetic (seeds 42, 7, 123) and afed_temporal (seeds 1, 2, 3).
  Real payments with daily dates and 300+ vendors with 24+ events, with injected anomalies (seeds 1, 2, 3):
  nspcl, mplads, chicago, delaware.
Fraud detection rate is not reported as a number: no dataset has confirmed-fraud labels.
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
sys.path[:0] = [str(ROOT), str(ROOT / "data"), str(ROOT.parent / "data" / "scripts")]
warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import IsolationForest  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402
from sklearn.neighbors import LocalOutlierFactor  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

import generate_synthetic  # noqa: E402
import generate_temporal  # noqa: E402
from common import PROCESSED, to_afed  # noqa: E402
from ml import pipeline  # noqa: E402
from ml.features import read_csv  # noqa: E402
from ml.inject import inject  # noqa: E402

LIMIT = 500_000
MODELS = ["Rule-based (fixed threshold)", "Global Isolation Forest only", "LOF (contextual baseline)", "AFED (proposed, IF + entity-relative fusion)"]
SHORT = dict(zip(MODELS, ["Rule-based", "Global IF", "LOF", "AFED"]))
OUT = Path(__file__).parent
FIGURES = OUT / "figures"
INK, MUTED, OLIVE, STONE, GRID = "#1B1A17", "#4A463F", "#4C5A33", "#8D877C", "#D8D0BC"
LEVEL_COLOURS = {"Low": "#A3B18A", "Medium": "#D9A441", "High": "#D8775F", "Critical": "#7E2F1C"}
pipeline.MODELS_DIR = Path(tempfile.mkdtemp())


def as_uploaded(frame: pd.DataFrame) -> pd.DataFrame:
    path = Path(tempfile.mkdtemp()) / "data.csv"
    frame.to_csv(path, index=False)
    return read_csv(path)


def classify(y: np.ndarray, alert: np.ndarray, score: np.ndarray, amount: np.ndarray) -> dict[str, Any]:
    tp, fp = int((alert & (y == 1)).sum()), int((alert & (y == 0)).sum())
    fn, tn = int((~alert & (y == 1)).sum()), int((~alert & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn)
    order = np.argsort(-score, kind="stable")
    return {"accuracy": (tp + tn) / len(y), "balanced_accuracy": (recall + tn / (tn + fp)) / 2, "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "roc_auc": roc_auc_score(y, score), "pr_auc": average_precision_score(y, score),
            "fpr": fp / (fp + tn), "fnr": fn / (fn + tp), "alerts": tp + fp,
            "p_at": {k: float(y[order[:k]].mean()) for k in (50, 100, 200, 500)},
            "amount_caught": float(amount[alert & (y == 1)].sum()), "amount_anomalous": float(amount[y == 1].sum())}


def evaluate(frame: pd.DataFrame) -> dict[str, Any]:
    started = time.perf_counter()
    result = pipeline.run_pipeline(frame)
    times = {MODELS[3]: time.perf_counter() - started}
    df = result.scored
    y = df["is_anomaly"].astype(int).to_numpy()
    amount = df["amount"].to_numpy(dtype=float)
    x = df[pipeline.RAW_FEATURES].fillna(0.0).to_numpy(dtype=float)

    started = time.perf_counter()
    rule_alert = amount >= LIMIT
    times[MODELS[0]] = time.perf_counter() - started

    started = time.perf_counter()
    forest = IsolationForest(n_estimators=200, contamination="auto", random_state=pipeline.SEED, n_jobs=-1).fit(x)
    if_alert, if_score = forest.predict(x) == -1, -forest.score_samples(x)
    times[MODELS[1]] = time.perf_counter() - started

    started = time.perf_counter()
    lof = LocalOutlierFactor(n_neighbors=20, contamination="auto", n_jobs=-1)
    lof_alert = lof.fit_predict(StandardScaler().fit_transform(x)) == -1
    lof_score = -lof.negative_outlier_factor_
    times[MODELS[2]] = time.perf_counter() - started

    risk = df["risk"].to_numpy()
    out = {MODELS[0]: classify(y, rule_alert, amount, amount), MODELS[1]: classify(y, if_alert, if_score, amount),
           MODELS[2]: classify(y, lof_alert, lof_score, amount), MODELS[3]: classify(y, df["level"].to_numpy() != "Low", risk, amount)}
    for model in MODELS:
        out[model]["ms_per_event"] = times[model] * 1000 / len(df)
    out["afed_extra"] = {"risk": risk[::max(1, len(risk) // 20000)].tolist(), "y": y[::max(1, len(risk) // 20000)].tolist(),
                         "levels": df["level"].value_counts().to_dict(), "levels_anomalous": df.loc[y == 1, "level"].value_counts().to_dict(),
                         "events": len(df), "amount": amount, "y_full": y, "alerts": {m: a for m, a in zip(MODELS, [rule_alert, if_alert, lof_alert, df["level"].to_numpy() != "Low"])}}
    return out


def datasets() -> list[tuple[str, int, pd.DataFrame]]:
    sets = [("afed_synthetic", s, as_uploaded(generate_synthetic.generate(s))) for s in (42, 7, 123)]
    sets += [("afed_temporal", s, as_uploaded(generate_temporal.generate(s))) for s in (1, 2, 3)]
    for name in ("nspcl", "mplads", "chicago", "delaware"):
        real = to_afed(pd.read_parquet(PROCESSED / f"{name}.parquet"))
        sets += [(name, s, inject(real, s)) for s in (1, 2, 3)]
    return sets


def spread(values: list[float], digits: int = 3) -> str:
    return f"{mean(values):.{digits}f} ± {stdev(values):.{digits}f}"


def figures(first: dict[str, Any], label: str) -> None:
    """Paper figures for one run. Thin marks, one highlighted series, text in ink, values labelled."""
    FIGURES.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                         "axes.spines.top": False, "axes.spines.right": False})
    extra = first["afed_extra"]

    fig, axes = plt.subplots(1, 4, figsize=(11, 2.8))
    for ax, key in zip(axes, ["precision", "recall", "f1", "pr_auc"]):
        values = [first[m][key] for m in MODELS]
        bars = ax.bar([SHORT[m] for m in MODELS], values, width=0.55, color=[STONE, STONE, STONE, OLIVE])
        ax.bar_label(bars, labels=[f"{v:.2f}" for v in values], color=INK, fontsize=8, padding=2)
        ax.set_ylim(0, 1.1)
        ax.set_title({"precision": "Precision", "recall": "Recall", "f1": "F1-score", "pr_auc": "PR-AUC"}[key], color=INK, fontsize=10)
        ax.tick_params(axis="x", rotation=30)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
    fig.suptitle(f"Model comparison, {label}. AFED highlighted", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "model_comparison.png", dpi=200)
    plt.close(fig)

    risk, y = np.array(extra["risk"]), np.array(extra["y"])
    fig, ax = plt.subplots(figsize=(6, 3))
    bins = np.linspace(0, 1, 41)
    ax.hist(risk[y == 0], bins=bins, color=STONE, label="Normal events")
    ax.hist(risk[y == 1], bins=bins, color=OLIVE, label="Anomalies")
    ax.set_yscale("log")
    for cut, name in ((0.45, "Medium"), (0.60, "High"), (0.75, "Critical")):
        ax.axvline(cut, color=MUTED, linewidth=0.8, linestyle=":")
        ax.text(cut + 0.005, ax.get_ylim()[1] * 0.6, name, color=MUTED, fontsize=7)
    ax.set_xlabel("AFED risk score")
    ax.set_ylabel("Events (log scale)")
    ax.legend(frameon=False)
    ax.set_title(f"Anomaly score distribution, {label}", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "score_distribution.png", dpi=200)
    plt.close(fig)

    levels = ["Low", "Medium", "High", "Critical"]
    fig, ax = plt.subplots(figsize=(5, 2.8))
    counts = [extra["levels"].get(l, 0) for l in levels]
    bars = ax.bar(levels, counts, width=0.55, color=[LEVEL_COLOURS[l] for l in levels])
    ax.bar_label(bars, labels=[f"{c:,}" for c in counts], color=INK, fontsize=8, padding=2)
    ax.set_yscale("log")
    ax.set_ylabel("Events (log scale)")
    ax.set_title(f"Risk-level distribution, {label}", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "risk_levels.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 3))
    ks = [50, 100, 200, 500]
    for model in MODELS:
        is_afed = model == MODELS[3]
        ax.plot(ks, [first[model]["p_at"][k] for k in ks], marker="o", markersize=4, linewidth=2 if is_afed else 1.2,
                color=OLIVE if is_afed else STONE, linestyle="-" if is_afed else "--", label=SHORT[model])
    ax.set_xlabel("K, events reviewed from the top")
    ax.set_ylabel("Precision@K")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=8)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_title(f"Precision@K, {label}", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "precision_at_k.png", dpi=200)
    plt.close(fig)

    amount, yy = extra["amount"], extra["y_full"]
    edges = np.quantile(amount[yy == 1], [0, 0.25, 0.5, 0.75, 1.0])
    band = np.clip(np.searchsorted(edges, amount, side="right") - 1, 0, 3)
    fig, ax = plt.subplots(figsize=(6, 3))
    width = 0.2
    for i, model in enumerate(MODELS):
        alert = extra["alerts"][model]
        recall = [float(alert[(yy == 1) & (band == b)].mean()) for b in range(4)]
        ax.bar(np.arange(4) + (i - 1.5) * width, recall, width=width * 0.9, color=OLIVE if model == MODELS[3] else STONE,
               alpha=1 if model == MODELS[3] else 0.35 + 0.2 * i, label=SHORT[model])
    ax.set_xticks(range(4), [f"Q{b + 1}\n≤ Rs {edges[b + 1]:,.0f}" for b in range(4)], fontsize=7)
    ax.set_ylabel("Recall")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, fontsize=7, ncol=4)
    ax.set_title(f"Recall by anomaly amount quartile, {label}", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(FIGURES / "amount_analysis.png", dpi=200)
    plt.close(fig)


def main() -> None:
    results: dict[str, list[dict[str, Any]]] = {}
    for name, seed, frame in datasets():
        run = evaluate(frame)
        results.setdefault(name, []).append(run)
        print(f"{name} seed {seed}: " + ", ".join(f"{SHORT[m]} F1 {run[m]['f1']:.3f}" for m in MODELS), flush=True)
        if name == "afed_synthetic" and seed == 42:
            figures(run, "AFED synthetic, seed 42")

    lines = ["# Model comparison: Rule-based, Global IF, LOF and AFED", "",
             "Produced by `experiments/model_comparison.py`; the model and dataset definitions are in its docstring, fixed before the run.",
             "Each model is judged at its own alert threshold. Values are mean ± sd over three seeds.",
             "**Fraud detection rate is not reported:** no dataset has confirmed-fraud labels. Labels are injected or generated anomalies, so the "
             "anomaly detection rate (recall) is the measurable equivalent.", ""]
    for name, runs in results.items():
        real = not name.startswith("afed_")
        lines += [f"## {name}" + (" (real data, injected anomalies: precision is a lower bound)" if real else " (synthetic, labelled)"), "",
                  "| Model | Accuracy | Precision | Recall | F1-Score |", "|---|---|---|---|---|"]
        for model in MODELS:
            row = [spread([r[model][k] for r in runs]) for k in ("accuracy", "precision", "recall", "f1")]
            text = f"**{model}**" if model == MODELS[3] else model
            lines.append(f"| {text} | " + " | ".join(f"**{v}**" if model == MODELS[3] else v for v in row) + " |")
        lines += ["", "| Model | Balanced accuracy | TP | FP | FN | TN | ROC-AUC | PR-AUC | FPR | FNR | Anomaly detection rate | Alerts | ms per event |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for model in MODELS:
            c = {k: mean(r[model][k] for r in runs) for k in ("tp", "fp", "fn", "tn", "alerts")}
            lines.append(f"| {SHORT[model]} | {spread([r[model]['balanced_accuracy'] for r in runs])} | {c['tp']:,.0f} | {c['fp']:,.0f} | {c['fn']:,.0f} | {c['tn']:,.0f} | {spread([r[model]['roc_auc'] for r in runs])} | "
                         f"{spread([r[model]['pr_auc'] for r in runs])} | {spread([r[model]['fpr'] for r in runs], 4)} | {spread([r[model]['fnr'] for r in runs])} | "
                         f"{spread([r[model]['recall'] for r in runs])} | {c['alerts']:,.0f} | {mean(r[model]['ms_per_event'] for r in runs):.3f} |")
        lines += ["", "| Precision@K | " + " | ".join(SHORT[m] for m in MODELS) + " |", "|---|" + "---|" * len(MODELS)]
        for k in (50, 100, 200, 500):
            lines.append(f"| P@{k} | " + " | ".join(spread([r[m]["p_at"][k] for r in runs], 2) for m in MODELS) + " |")
        caught = {m: mean(r[m]["amount_caught"] / r[m]["amount_anomalous"] for r in runs) for m in MODELS}
        lines += ["", "Share of anomalous amount caught: " + ", ".join(f"{SHORT[m]} {caught[m]:.1%}" for m in MODELS) + ".", ""]
        levels = runs[0]["afed_extra"]["levels"]
        lines += [f"AFED risk levels (first seed, {runs[0]['afed_extra']['events']:,} events): " +
                  ", ".join(f"{l} {levels.get(l, 0):,}" for l in ("Low", "Medium", "High", "Critical")) + ".", ""]
    lines += ["## Figures (AFED synthetic, seed 42)", "", "- `figures/model_comparison.png`", "- `figures/score_distribution.png`",
              "- `figures/risk_levels.png`", "- `figures/precision_at_k.png`", "- `figures/amount_analysis.png`"]
    (OUT / "model_comparison_results.md").write_text("\n".join(lines) + "\n")
    # The same means, for the Evaluation page.
    keys = ("accuracy", "balanced_accuracy", "precision", "recall", "f1", "roc_auc", "pr_auc")
    summary = {"models": dict(zip(["rule_based", "global_if", "lof", "afed"], MODELS)), "datasets": [
        {"name": name, "real": not name.startswith("afed_"), "seeds": len(runs), "events": round(mean(r["afed_extra"]["events"] for r in runs)),
         "results": {short: {k: round(mean(r[model][k] for r in runs), 4) for k in keys}
                     for short, model in zip(["rule_based", "global_if", "lof", "afed"], MODELS)}}
        for name, runs in results.items()]}
    (OUT / "model_comparison_results.json").write_text(json.dumps(summary, indent=1) + "\n")
    print("written")


if __name__ == "__main__":
    main()
