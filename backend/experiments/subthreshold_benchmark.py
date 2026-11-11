"""Step 3a, pre-registered in subthreshold_benchmark.md: anomalies below the approval limit. Reporting data only.

    python experiments/subthreshold_benchmark.py
"""
import json

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

from v2_common import MAIN_REAL, OUT, REPORTING_PLANTED, classify, early_mask, meta, scored, spread
from ml import pipeline
from ml.features import RULES, active_rules
from ml.fusion import calibrate_medium, risk_score, rule_share
from ml.inject import SUBTHRESHOLD_MULTIPLIERS, inject_subthreshold

CONFIG = json.loads((OUT / "v2_config.json").read_text())
LIMIT = 500_000
MODELS = ["Rule-based", "Global IF", "LOF", "AFED v1", "AFED v2"]
TYPES = [f"subthreshold_{m}x" for m in SUBTHRESHOLD_MULTIPLIERS]


def run(name: str, seed: int) -> dict:
    v1 = scored(name, seed, "v1", None, plant=inject_subthreshold, plant_tag="sub")
    seq = scored(name, seed, "seq", {"sequence_features": True}, plant=inject_subthreshold, plant_tag="sub")
    late = ~early_mask(v1)
    y = v1["is_anomaly"].to_numpy().astype(int)
    amount = v1["amount"].to_numpy(dtype=float)
    x = v1[pipeline.RAW_FEATURES].fillna(0.0).to_numpy(dtype=float)
    forest = IsolationForest(n_estimators=200, contamination="auto", random_state=pipeline.SEED, n_jobs=-1).fit(x)
    lof = LocalOutlierFactor(n_neighbors=20, contamination="auto", n_jobs=-1)
    lof_alert = lof.fit_predict(StandardScaler().fit_transform(x)) == -1
    gb = CONFIG["global_budget"]
    share = rule_share(active_rules(meta(name, seed, "v1", "sub")["inputs"]), RULES)
    r5 = risk_score(seq["a_score"].to_numpy(), v1["d_score"].to_numpy(), v1["f_score"].to_numpy(), gb["weights"], share)
    cut = calibrate_medium(r5, v1["invoice_date"], "alert_budget", gb["target_rate"], 0.6)["medium"]
    models = {"Rule-based": (amount >= LIMIT, amount), "Global IF": (forest.predict(x) == -1, -forest.score_samples(x)),
              "LOF": (lof_alert, -lof.negative_outlier_factor_), "AFED v1": ((v1["level"] != "Low").to_numpy(), v1["risk"].to_numpy()),
              "AFED v2": (r5 >= cut, r5)}
    kinds = v1["anomaly_type"].to_numpy()
    out = {"planted_late": int(y[late].sum()), "events_late": int(late.sum())}
    for model, (alert, score) in models.items():
        out[model] = classify(y[late], alert[late], score[late])
        out[model]["by_type"] = {t: float(alert[late & (kinds == t)].mean()) if (late & (kinds == t)).any() else float("nan") for t in TYPES}
    return out


def main() -> None:
    results = {}
    for name in MAIN_REAL:
        results[name] = {seed: run(name, seed) for seed in REPORTING_PLANTED}
        print(name, {m: round(np.mean([r[m]["recall"] for r in results[name].values()]), 4) for m in MODELS}, flush=True)
    (OUT / "subthreshold_benchmark_results.json").write_text(json.dumps(results, indent=1, default=float))
    L = ["# Sub-threshold benchmark: results", "",
         "Produced by `experiments/subthreshold_benchmark.py`, following `subthreshold_benchmark.md`. Planted seeds 4-6 (reporting), latest 40% "
         "of each run. Every planted invoice is 2x, 3x or 5x its vendor's earlier median and below Rs. 5,00,000. Mean ± sd over seeds. "
         "Real rows count as normal, so precision is a lower bound.", ""]
    for name, runs in results.items():
        planted = [r["planted_late"] for r in runs.values()]
        L += [f"## {name}", "", f"Planted invoices in the measured period: {spread(planted, 1)} per seed, of {np.mean([r['events_late'] for r in runs.values()]):,.0f} events."
              + (" Too few to draw conclusions from." if np.mean(planted) < 30 else ""), "",
              "| Model | Recall | Precision | F1 | PR-AUC | Alerts | " + " | ".join(f"Recall {t.split('_')[1]}" for t in TYPES) + " |",
              "|---|---|---|---|---|---|" + "---|" * len(TYPES)]
        for model in MODELS:
            col = lambda k, d=3: spread([r[model][k] for r in runs.values()], d)  # noqa: E731
            L.append(f"| {model} | {col('recall')} | {col('precision')} | {col('f1')} | {col('pr_auc')} | {col('alerts', 0)} | "
                     + " | ".join(spread([r[model]["by_type"][t] for r in runs.values()]) for t in TYPES) + " |")
        L.append("")
    (OUT / "subthreshold_benchmark_results.md").write_text("\n".join(L) + "\n")
    print("written")


if __name__ == "__main__":
    main()
