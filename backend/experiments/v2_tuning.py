"""Step 2d, pre-registered in v2_tuning.md: choose v2's fusion weights, cut-offs and alert budget on tuning data only.

    python experiments/v2_tuning.py      # writes v2_config.json (frozen) and v2_tuning_results.md
"""
import json
from itertools import product

import numpy as np

from v2_common import MAIN_REAL, OUT, early_mask, meta, scored, tuning_seeds
from ml.features import RULES, active_rules
from ml.fusion import risk_score, rule_share

DATASETS = MAIN_REAL + ["afed_synthetic"]
SEQ = {"sequence_features": True}
STEPS = np.round(np.arange(0.05, 0.901, 0.05), 2)
WEIGHTS = [{"w1": float(a), "w2": float(b), "w3": round(1 - a - b, 2)} for a, b in product(STEPS, STEPS) if 1 - a - b >= 0.05 - 1e-9]
CUTS = np.round(np.arange(0.30, 0.901, 0.01), 2)
RATES = [0.005, 0.01, 0.015, 0.02, 0.03, 0.05]
DEFAULT = {"w1": 0.40, "w2": 0.35, "w3": 0.25}


def runs() -> dict[str, list[dict]]:
    """Tuning-period arrays per dataset and seed, from the `seq` arm."""
    out = {}
    for name in DATASETS:
        out[name] = []
        for seed in tuning_seeds(name):
            df = scored(name, seed, "seq", SEQ)
            early = early_mask(df)
            share = rule_share(active_rules(meta(name, seed, "seq")["inputs"]), RULES)
            out[name].append({"a": df["a_score"].to_numpy()[early], "d": df["d_score"].to_numpy()[early],
                              "f": df["f_score"].to_numpy()[early], "y": df["is_anomaly"].to_numpy()[early].astype(int), "share": share})
            print(f"tuning data {name} seed {seed}: {early.sum():,} events, rule share {share:.3f}", flush=True)
    return out


def f1_at_cuts(risk: np.ndarray, y: np.ndarray, cuts: np.ndarray) -> np.ndarray:
    """F1 for alerting on risk >= c, for every c at once."""
    order = np.argsort(risk)
    sorted_risk, positives = risk[order], y[order]
    above = len(risk) - np.searchsorted(sorted_risk, cuts, side="left")       # alerts at each cut
    tp_from_top = np.concatenate([[0], np.cumsum(positives[::-1])])           # true positives among the top k
    tp = tp_from_top[above]
    total = y.sum()
    precision = np.divide(tp, above, out=np.zeros(len(cuts)), where=above > 0)
    recall = tp / total if total else np.zeros(len(cuts))
    return np.divide(2 * precision * recall, precision + recall, out=np.zeros(len(cuts)), where=(precision + recall) > 0)


def f1_at_budget(risk: np.ndarray, y: np.ndarray, rate: float) -> float:
    """Alert-budget mode on the tuning events themselves: the cut-off is the k-th highest risk, k = rate x events."""
    k = int(np.floor(rate * len(risk)))
    if k < 1:
        return 0.0
    cut = np.sort(risk)[::-1][k - 1]
    return float(f1_at_cuts(risk, y, np.array([cut]))[0])


def main() -> None:
    data = runs()
    per_cut = {}      # (weights index) -> {dataset: mean F1 over seeds at every cut}
    per_budget = {}   # (weights index) -> {dataset: mean F1 over seeds at every rate}
    for i, w in enumerate(WEIGHTS):
        per_cut[i], per_budget[i] = {}, {}
        for name, seeds in data.items():
            risks = [risk_score(r["a"], r["d"], r["f"], w, r["share"]) for r in seeds]
            per_cut[i][name] = np.mean([f1_at_cuts(risk, r["y"], CUTS) for risk, r in zip(risks, seeds)], axis=0)
            per_budget[i][name] = np.array([np.mean([f1_at_budget(risk, r["y"], rate) for risk, r in zip(risks, seeds)]) for rate in RATES])

    def better(score: float, best: float) -> bool:
        return score > best + 1e-12

    per_dataset = {}
    for name in DATASETS:  # P: ties go to the higher cut, then the earlier weight set
        best = (-1.0, None, None)
        for i in range(len(WEIGHTS)):
            scores = per_cut[i][name]
            j = max(range(len(CUTS)), key=lambda k: (round(scores[k], 12), CUTS[k]))
            if better(scores[j], best[0]):
                best = (float(scores[j]), i, float(CUTS[j]))
        per_dataset[name] = {"weights": WEIGHTS[best[1]], "medium": best[2], "tuning_f1": round(best[0], 4)}

    best_g = (-1.0, None, None)
    for i in range(len(WEIGHTS)):
        mean_over = np.mean([per_cut[i][n] for n in DATASETS], axis=0)
        j = max(range(len(CUTS)), key=lambda k: (round(mean_over[k], 12), CUTS[k]))
        if better(mean_over[j], best_g[0]):
            best_g = (float(mean_over[j]), i, float(CUTS[j]))
    best_b = (-1.0, None, None)
    for i in range(len(WEIGHTS)):
        mean_over = np.mean([per_budget[i][n] for n in DATASETS], axis=0)
        j = max(range(len(RATES)), key=lambda k: (round(mean_over[k], 12), -RATES[k]))
        if better(mean_over[j], best_b[0]):
            best_b = (float(mean_over[j]), i, RATES[j])

    default_i = next(i for i, w in enumerate(WEIGHTS) if all(abs(w[k] - DEFAULT[k]) < 1e-9 for k in w))
    reference = {n: {"default_weights_cut_045": round(float(per_cut[default_i][n][list(CUTS).index(0.45)]), 4),
                     "default_weights_budget_2pct": round(float(per_budget[default_i][n][RATES.index(0.02)]), 4)} for n in DATASETS}
    config = {
        "frozen": "chosen on tuning data only by v2_tuning.py; read, never changed, by the reporting experiments",
        "per_dataset": per_dataset,
        "global_fixed": {"weights": WEIGHTS[best_g[1]], "medium": best_g[2], "tuning_mean_f1": round(best_g[0], 4)},
        "global_budget": {"weights": WEIGHTS[best_b[1]], "target_rate": best_b[2], "tuning_mean_f1": round(best_b[0], 4),
                          "per_dataset_tuning_f1": {n: round(float(per_budget[best_b[1]][n][RATES.index(best_b[2])]), 4) for n in DATASETS}},
        "full_v2_settings": {"field_aware": True, "sequence_features": True, "weights": WEIGHTS[best_b[1]],
                             "calibration": {"mode": "alert_budget", "target_rate": best_b[2], "fit_share": 0.6}},
        "reference_tuning_f1": reference,
    }
    (OUT / "v2_config.json").write_text(json.dumps(config, indent=1))

    L = ["# v2 tuning: results", "",
         "Produced by `experiments/v2_tuning.py`, following `v2_tuning.md`. Tuning data only: planted seeds 1-3, synthetic seeds 42/7/123, "
         "earliest 60% of each run. F1 is the mean over a dataset's three seeds. Field-aware fusion, sequence features on. "
         "These are tuning scores, not results: they are optimistic by construction.", "",
         "## P: per dataset", "", "| Dataset | w1 | w2 | w3 | Medium | Tuning F1 | Default weights, 0.45 | Default weights, 2% budget |",
         "|---|---|---|---|---|---|---|---|"]
    for n, p in per_dataset.items():
        w = p["weights"]
        L.append(f"| {n} | {w['w1']:.2f} | {w['w2']:.2f} | {w['w3']:.2f} | {p['medium']:.2f} | {p['tuning_f1']:.4f} | "
                 f"{reference[n]['default_weights_cut_045']:.4f} | {reference[n]['default_weights_budget_2pct']:.4f} |")
    g, b = config["global_fixed"], config["global_budget"]
    L += ["", "## G and GB: one setting for all five datasets", "", "| Setting | w1 | w2 | w3 | Cut-off or budget | Tuning mean F1 |", "|---|---|---|---|---|---|",
          f"| G, fixed cut-off | {g['weights']['w1']:.2f} | {g['weights']['w2']:.2f} | {g['weights']['w3']:.2f} | Medium {g['medium']:.2f} | {g['tuning_mean_f1']:.4f} |",
          f"| GB, alert budget | {b['weights']['w1']:.2f} | {b['weights']['w2']:.2f} | {b['weights']['w3']:.2f} | {b['target_rate']:.1%} of events | {b['tuning_mean_f1']:.4f} |",
          "", "GB tuning F1 per dataset: " + ", ".join(f"{n} {v:.4f}" for n, v in b["per_dataset_tuning_f1"].items()) + ".", "",
          f"**Full v2**, frozen in `v2_config.json`: field-aware fusion, sequence features, weights {b['weights']['w1']:.2f} / "
          f"{b['weights']['w2']:.2f} / {b['weights']['w3']:.2f}, alert budget {b['target_rate']:.1%} chosen on each run's earliest 60%."]
    (OUT / "v2_tuning_results.md").write_text("\n".join(L) + "\n")
    print(json.dumps({k: config[k] for k in ("global_fixed", "global_budget")}, indent=1))


if __name__ == "__main__":
    main()
