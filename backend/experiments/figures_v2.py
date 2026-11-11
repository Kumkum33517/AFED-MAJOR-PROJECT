"""Step 4: report figures for v2, 300 dpi, drawn only from the result JSON files of this folder.

    python experiments/figures_v2.py
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path(__file__).parent
FIG = OUT / "figures_v2"
INK, MUTED, GRID = "#1B1A17", "#4A463F", "#D8D0BC"
COLOURS = {"v1": "#D9A441", "v2": "#4C5A33", "Rule-based": "#8D877C", "Global IF": "#B2432A", "LOF": "#C98B78",
           "AFED v1": "#D9A441", "AFED v2": "#4C5A33", "A": "#B2432A", "D": "#4C5A33", "F": "#D9A441", "fusion": "#4E6A85"}
ABLATION = ["#8D877C", "#C98B78", "#D9A441", "#B2432A", "#6F7D45", "#2F3A22"]
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "font.size": 9,
                     "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 300})


def load(name: str) -> dict | None:
    path = OUT / name
    return json.loads(path.read_text()) if path.exists() else None


def tidy(ax: plt.Axes, title: str, ylabel: str = "") -> None:
    ax.set_title(title, color=INK, fontsize=10)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def grouped(ax: plt.Axes, labels: list[str], series: dict[str, tuple[list[float], list[float]]], digits: int = 3) -> None:
    """Bars per label, one colour per series, with sd error bars and value labels."""
    width = 0.8 / len(series)
    for k, (name, (means, sds)) in enumerate(series.items()):
        x = np.arange(len(labels)) + (k - (len(series) - 1) / 2) * width
        bars = ax.bar(x, means, width * 0.92, yerr=sds, color=COLOURS.get(name, ABLATION[k % len(ABLATION)]), label=name,
                      error_kw={"elinewidth": 0.6, "ecolor": MUTED, "capsize": 1.5})
        ax.bar_label(bars, labels=[f"{m:.{digits}f}" for m in means], fontsize=6, padding=1.5, color=INK)
    ax.set_xticks(np.arange(len(labels)), labels, rotation=20, ha="right")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.22)  # headroom so the legend never covers a bar
    ax.legend(frameon=False, fontsize=7, ncol=min(len(series), 6), loc="upper center")


def ms(values: list[float]) -> tuple[float, float]:
    values = [v for v in values if v == v]
    return (float(np.mean(values)), float(np.std(values, ddof=1)) if len(values) > 1 else 0.0) if values else (0.0, 0.0)


def evaluation_figures(ev: dict) -> list[str]:
    made = []
    results = ev["results"]
    real = [n for n in results if n not in ("afed_synthetic", "icai")]
    m = lambda n, row, k: [r["rows"][row]["measures"][k] for r in results[n] if row in r["rows"]]  # noqa: E731

    fig, ax = plt.subplots(figsize=(8, 3.2))
    grouped(ax, real, {"v1": tuple(zip(*[ms(m(n, "R0 v1", "f1")) for n in real])), "v2": tuple(zip(*[ms(m(n, "R5 full v2", "f1")) for n in real]))})
    tidy(ax, "F1 on real ledgers, v1 against full v2 (reporting seeds 4-6, latest 40%)", "F1")
    fig.tight_layout(); fig.savefig(FIG / "f1_v1_v2_real.png"); plt.close(fig); made.append("f1_v1_v2_real.png")

    rows = ["R0 v1", "R1 + field-aware fusion", "R2 + alert budget (2%)", "R3 + sequence features", "R4 + weight search (P)", "R5 full v2"]
    sets = [n for n in ["nspcl", "mplads", "chicago", "delaware", "afed_synthetic"] if n in results]
    fig, ax = plt.subplots(figsize=(9, 3.4))
    grouped(ax, sets, {row: tuple(zip(*[ms(m(n, row, "f1")) for n in sets])) for row in rows}, 2)
    tidy(ax, "Cumulative ablation, F1 (reporting data)", "F1")
    fig.tight_layout(); fig.savefig(FIG / "cumulative_ablation.png"); plt.close(fig); made.append("cumulative_ablation.png")

    types = ["amount_spike", "slow_drift", "frequency_shift", "off_cycle_invoice"]
    main = [n for n in ["nspcl", "mplads", "chicago", "delaware"] if n in results]
    fig, axes = plt.subplots(1, len(main), figsize=(10, 2.8), sharey=True)
    for ax, n in zip(np.atleast_1d(axes), main):
        series = {v: tuple(zip(*[ms([r["rows"][row]["by_type"].get(t, float("nan")) for r in results[n]]) for t in types]))
                  for v, row in (("v1", "R0 v1"), ("v2", "R5 full v2"))}
        grouped(ax, [t.replace("_", " ") for t in types], series, 2)
        tidy(ax, n, "Recall" if ax is np.atleast_1d(axes)[0] else "")
    fig.suptitle("Recall by planted type, v1 against full v2 (reporting data)", color=INK, fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / "recall_by_type_v1_v2.png"); plt.close(fig); made.append("recall_by_type_v1_v2.png")
    return made


def subthreshold_figure(sub: dict) -> list[str]:
    models = ["Rule-based", "Global IF", "LOF", "AFED v1", "AFED v2"]
    names = list(sub)
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.2))
    for ax, key, title, digits in zip(axes, ("recall", "pr_auc"), ("Recall", "PR-AUC"), (2, 3)):
        grouped(ax, names, {mo: tuple(zip(*[ms([r[mo][key] for r in sub[n].values()]) for n in names])) for mo in models}, digits)
        tidy(ax, title)
    fig.suptitle("Sub-threshold benchmark: 2x to 5x the vendor's median, below Rs. 5 lakh (reporting data)", color=INK, fontsize=10)
    fig.tight_layout(); fig.savefig(FIG / "subthreshold_benchmark.png"); plt.close(fig)
    return ["subthreshold_benchmark.png"]


def diagnostics_figure(diag: dict) -> list[str]:
    names = list(diag)
    fig, ax = plt.subplots(figsize=(10, 3.2))
    grouped(ax, names, {c: tuple(zip(*[ms([r["component_auc"][c]["roc_auc"] for r in diag[n]]) for n in names])) for c in ("A", "D", "F", "fusion")}, 2)
    ax.axhline(0.5, color=MUTED, linewidth=0.8, linestyle="--")
    tidy(ax, "Each component alone, ROC-AUC (tuning data; dashed line = chance)", "ROC-AUC")
    fig.tight_layout(); fig.savefig(FIG / "component_roc_auc.png"); plt.close(fig)
    return ["component_roc_auc.png"]


def narration_figure(nar: dict) -> list[str]:
    detail = nar["detail"]
    outcomes = ["accepted", "new word", "new number", "misplaced number", "main fact left out"]
    labels = [f"{'English' if l == 'en' else 'Hindi'}, {arm} {'paragraph' if arm == 'v1' else 'per fact'}" for l in detail for arm in ("v1", "v2")]
    counts = {o: [detail[l][arm].get(o, 0) for l in detail for arm in ("v1", "v2")] for o in outcomes}
    fig, ax = plt.subplots(figsize=(8, 3.2))
    grouped(ax, labels, {o: (c, [0] * len(c)) for o, c in counts.items()}, 0)
    tidy(ax, "Qwen narration on 100 new alerts: v1 paragraph against v2 per fact", "Narrations of 100")
    fig.tight_layout(); fig.savefig(FIG / "qwen_v2_outcomes.png"); plt.close(fig)
    return ["qwen_v2_outcomes.png"]


def main() -> None:
    FIG.mkdir(exist_ok=True)
    made = []
    for name, draw in (("v2_evaluation_results.json", evaluation_figures), ("subthreshold_benchmark_results.json", subthreshold_figure),
                       ("diagnostics_results.json", diagnostics_figure), ("narration_v2_results.json", narration_figure)):
        data = load(name)
        if data:
            made += draw(data)
    print("figures:", made)


if __name__ == "__main__":
    main()
