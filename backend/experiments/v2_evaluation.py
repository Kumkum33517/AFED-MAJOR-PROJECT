"""Steps 3b, 3c and 2d's reporting, pre-registered in v2_evaluation.md. Reporting data only; settings from v2_config.json.

    python experiments/v2_evaluation.py
"""
import json

import numpy as np
import pandas as pd

from v2_common import (EXTRA_SYNTHETIC, MAIN_REAL, OTHER_REAL, OUT, TYPES, by_type, classify, early_mask, meta, raw_frame,
                       reporting_seeds, scored, spread)
from ml import pipeline
from ml.features import RULES, active_rules
from ml.fusion import calibrate_medium, risk_score, rule_share

CONFIG = json.loads((OUT / "v2_config.json").read_text())
DEFAULT = {"w1": 0.40, "w2": 0.35, "w3": 0.25}
SEQ = {"sequence_features": True}
DATASETS = MAIN_REAL + ["afed_synthetic"] + OTHER_REAL + EXTRA_SYNTHETIC
ROWS = ["R0 v1", "R1 + field-aware fusion", "R2 + alert budget (2%)", "R3 + sequence features", "R4 + weight search (P)", "R5 full v2"]
MEASURES = ["f1", "recall", "precision", "pr_auc", "roc_auc", "alerts"]


def budget_cut(risk: np.ndarray, dates: pd.Series, rate: float) -> float:
    return calibrate_medium(risk, dates, "alert_budget", rate, 0.6)["medium"]


def evaluate_run(name: str, seed: int) -> dict:
    v1, seq = scored(name, seed, "v1"), scored(name, seed, "seq", SEQ)
    assert (v1["event_id"].to_numpy() == seq["event_id"].to_numpy()).all()
    late = ~early_mask(v1)
    share = rule_share(active_rules(meta(name, seed, "v1")["inputs"]), RULES)
    dates, y = v1["invoice_date"], v1["is_anomaly"].to_numpy().astype(int)
    d, f = v1["d_score"].to_numpy(), v1["f_score"].to_numpy()
    a1, a2 = v1["a_score"].to_numpy(), seq["a_score"].to_numpy()
    gb = CONFIG["global_budget"]
    rows = {}

    def add(row: str, risk: np.ndarray, alert: np.ndarray) -> None:
        rows[row] = {"measures": classify(y[late], alert[late], risk[late]), "by_type": by_type(v1[late].reset_index(drop=True), alert[late])}

    add("R0 v1", v1["risk"].to_numpy(), (v1["level"] != "Low").to_numpy())
    r1 = risk_score(a1, d, f, DEFAULT, share)
    add("R1 + field-aware fusion", r1, r1 >= 0.45)
    add("R2 + alert budget (2%)", r1, r1 >= budget_cut(r1, dates, 0.02))
    r3 = risk_score(a2, d, f, DEFAULT, share)
    add("R3 + sequence features", r3, r3 >= budget_cut(r3, dates, 0.02))
    if name in CONFIG["per_dataset"]:
        p = CONFIG["per_dataset"][name]
        r4 = risk_score(a2, d, f, p["weights"], share)
        add("R4 + weight search (P)", r4, r4 >= p["medium"])
    r5 = risk_score(a2, d, f, gb["weights"], share)
    add("R5 full v2", r5, r5 >= budget_cut(r5, dates, gb["target_rate"]))
    g = CONFIG["global_fixed"]
    rg = risk_score(a2, d, f, g["weights"], share)
    add("G global fixed cut-off", rg, rg >= g["medium"])
    return {"rows": rows, "rule_share": share, "late_events": int(late.sum()), "late_anomalies": int(y[late].sum())}


def consistency_check() -> dict:
    """R5 computed from cached components must equal a pipeline run with the full v2 settings."""
    name, seed = "nspcl", 4
    v1, seq = scored(name, seed, "v1"), scored(name, seed, "seq", SEQ)
    share = rule_share(active_rules(meta(name, seed, "v1")["inputs"]), RULES)
    gb = CONFIG["global_budget"]
    r5 = risk_score(seq["a_score"].to_numpy(), v1["d_score"].to_numpy(), v1["f_score"].to_numpy(), gb["weights"], share)
    alert = r5 >= budget_cut(r5, v1["invoice_date"], gb["target_rate"])
    live = pipeline.run_pipeline(raw_frame(name, seed), CONFIG["full_v2_settings"], evaluate_labels=False).scored
    live = live.set_index("event_id").loc[v1["event_id"]]
    return {"dataset": name, "seed": seed, "max_risk_difference": float(np.abs(live["risk"].to_numpy() - r5).max()),
            "alerts_equal": bool(((live["level"] != "Low").to_numpy() == alert).all())}


def main() -> None:
    results = {}
    for name in DATASETS:
        results[name] = [evaluate_run(name, s) for s in reporting_seeds(name)]
        print(name, "R0 F1", spread([r["rows"]["R0 v1"]["measures"]["f1"] for r in results[name]]),
              "R5 F1", spread([r["rows"]["R5 full v2"]["measures"]["f1"] for r in results[name]]), flush=True)
    check = consistency_check()
    print("consistency", check, flush=True)

    def m(name: str, row: str, key: str) -> list[float]:
        return [r["rows"][row]["measures"][key] for r in results[name] if row in r["rows"]]

    main_better = [n for n in MAIN_REAL if np.mean(m(n, "R5 full v2", "f1")) > np.mean(m(n, "R0 v1", "f1"))]
    recall_drop = float(np.mean(m("afed_synthetic", "R0 v1", "recall")) - np.mean(m("afed_synthetic", "R5 full v2", "recall")))
    verdict = "PASS" if len(main_better) >= 3 and recall_drop <= 0.03 else "FAIL"
    summary = {"decision": {"verdict": verdict, "main_ledgers_with_higher_f1": main_better, "synthetic_recall_drop": recall_drop},
               "consistency_check": check, "config": CONFIG, "results": results}
    (OUT / "v2_evaluation_results.json").write_text(json.dumps(summary, indent=1, default=float))

    gb = CONFIG["global_budget"]
    L = ["# v2 evaluation: results", "",
         "Produced by `experiments/v2_evaluation.py`, following `v2_evaluation.md`. **Reporting data only**: planted seeds 4-6, synthetic "
         "seeds 11/12/13, latest 40% of each run by date. Settings from `v2_config.json`, frozen by `v2_tuning.py` on tuning data. "
         "Mean ± sd over three seeds. Real rows count as normal, so precision on real ledgers is a lower bound.", "",
         f"Full v2 = field-aware fusion + sequence features + weights {gb['weights']['w1']:.2f} / {gb['weights']['w2']:.2f} / "
         f"{gb['weights']['w3']:.2f} + alert budget {gb['target_rate']:.1%} chosen on each run's earliest 60%.", "",
         "## Decision rule for the default", "",
         f"Mean F1 of full v2 above v1 on {len(main_better)} of 4 main ledgers ({', '.join(main_better) or 'none'}); "
         f"synthetic recall change {-recall_drop:+.4f} (allowed: no worse than −0.03). **{verdict}**: "
         + ("v2 meets the rule." if verdict == "PASS" else "v1 stays the default; v2 stays available as an option."), "",
         f"Consistency: full v2 computed from cached components against a live pipeline run ({check['dataset']}, seed {check['seed']}): "
         f"largest risk difference {check['max_risk_difference']:.2e}, alerts identical: {check['alerts_equal']}.", "",
         "## Headline: v1 against full v2 (3c)", "",
         "| Dataset | Late events | Planted | F1 v1 | F1 v2 | Recall v1 | Recall v2 | Precision v1 | Precision v2 | ROC-AUC v1 | ROC-AUC v2 | Alerts v1 | Alerts v2 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, runs in results.items():
        L.append(f"| {n} | {np.mean([r['late_events'] for r in runs]):,.0f} | {np.mean([r['late_anomalies'] for r in runs]):,.0f} | "
                 + " | ".join(f"{spread(m(n, 'R0 v1', k), 0 if k == 'alerts' else 3)} | {spread(m(n, 'R5 full v2', k), 0 if k == 'alerts' else 3)}"
                              for k in ("f1", "recall", "precision", "roc_auc", "alerts")) + " |")
    L += ["", "Recall by planted type, v1 → v2:", "", "| Dataset | " + " | ".join(TYPES) + " |", "|---|" + "---|" * len(TYPES)]
    for n, runs in results.items():
        if n == "afed_synthetic":
            continue
        cells = []
        for t in TYPES:
            a = [r["rows"]["R0 v1"]["by_type"].get(t, float("nan")) for r in runs]
            b = [r["rows"]["R5 full v2"]["by_type"].get(t, float("nan")) for r in runs]
            cells.append(f"{spread(a)} → {spread(b)}")
        L.append(f"| {n} | " + " | ".join(cells) + " |")

    L += ["", "## Cumulative ablation (3b)", ""]
    for key in MEASURES:
        L += [f"### {key}", "", "| Row | " + " | ".join(DATASETS) + " |", "|---|" + "---|" * len(DATASETS)]
        for row in ROWS:
            L.append(f"| {row} | " + " | ".join(spread(m(n, row, key), 0 if key == "alerts" else 3) if m(n, row, key) else "n/a" for n in DATASETS) + " |")
        L.append("")
    L += ["## Does per-dataset tuning carry over? (2d)", "", "| Dataset | F1 P (per dataset) | F1 G (global, fixed cut) | F1 GB (full v2) | F1 v1 |", "|---|---|---|---|---|"]
    for n in MAIN_REAL + ["afed_synthetic"]:
        L.append(f"| {n} | {spread(m(n, 'R4 + weight search (P)', 'f1'))} | {spread(m(n, 'G global fixed cut-off', 'f1'))} | "
                 f"{spread(m(n, 'R5 full v2', 'f1'))} | {spread(m(n, 'R0 v1', 'f1'))} |")
    (OUT / "v2_evaluation_results.md").write_text("\n".join(L) + "\n")
    print(verdict, main_better, recall_drop)


if __name__ == "__main__":
    main()
