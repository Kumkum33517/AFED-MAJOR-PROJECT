"""Step 1, pre-registered in diagnostics.md: why AFED ranks weakly on real ledgers. Tuning split only.

    python experiments/diagnostics.py
"""
import json
from statistics import mean

import numpy as np
import pandas as pd

from v2_common import (OUT, TUNING_PLANTED, TYPES, by_type, classify, early_mask, meta, scored, spread)
from ml.features import RULE_INPUTS, RULE_LABELS, RULES

DATASETS = ["nspcl", "mplads", "bbmp_2024", "bbmp_2010_2019", "chicago", "secop", "delaware", "ocds_assam", "icai"]
W = {"a": 0.40, "d": 0.35, "f": 0.25}


def one(name: str, seed: int) -> dict:
    df = scored(name, seed, "v1")
    m = df[early_mask(df)].reset_index(drop=True)
    y = m["is_anomaly"].astype(int).to_numpy()
    alert = (m["level"] != "Low").to_numpy()
    overall = classify(y, alert, m["risk"].to_numpy())
    tp = alert & (y == 1)
    inputs = meta(name, seed, "v1")["inputs"]
    hist = m["history_len"].to_numpy()
    mass = {k: float((W[k] * m[f"{k}_score"]).sum()) for k in "adf"}
    mass["bonus"] = float((0.10 * np.minimum(m["d_score"], m["f_score"])).sum())
    total = sum(mass.values())
    return {
        "events": len(m), "anomalies": int(y.sum()), "overall": overall, "recall_by_type": by_type(m, alert),
        "tp_share_by_type": {t: float((tp & (m["anomaly_type"] == t).to_numpy()).sum() / max(tp.sum(), 1)) for t in TYPES},
        "history": {"median": float(np.median(hist)), "q1": float(np.quantile(hist, 0.25)), "q3": float(np.quantile(hist, 0.75)),
                    "under_8": float((hist < 8).mean()), "under_24": float((hist < 24).mean())},
        "baseline": m["baseline_source"].value_counts(normalize=True).to_dict(),
        "inputs": inputs,
        "rules": {r: {"can_fire": all(inputs.get(n, False) for n in RULE_INPUTS[r]), "fires": float(m[f"flag_{r}"].mean())} for r in RULES},
        "component_auc": {c: {"roc_auc": classify(y, alert, m[col].to_numpy())["roc_auc"], "pr_auc": classify(y, alert, m[col].to_numpy())["pr_auc"]}
                          for c, col in (("A", "a_score"), ("D", "d_score"), ("F", "f_score"), ("fusion", "risk"))},
        "zeros": {"f_zero": float((m["f_score"] == 0).mean()), "d_zero": float((m["d_score"] == 0).mean()),
                  "mass_share": {k: v / total for k, v in mass.items()}},
    }


def main() -> None:
    results = {name: [one(name, s) for s in TUNING_PLANTED] for name in DATASETS}
    for name, runs in results.items():
        print(name, "fusion ROC-AUC", spread([r["component_auc"]["fusion"]["roc_auc"] for r in runs]), flush=True)
    (OUT / "diagnostics_results.json").write_text(json.dumps(results, indent=1, default=float))

    L = ["# Why is AFED's ranking weak on real ledgers? Results", "",
         "Produced by `experiments/diagnostics.py`, following `diagnostics.md`. AFED v1, default settings. Planted seeds 1-3; "
         "only events before the 60th percentile of each run's dates (the tuning period). Mean ± sd over seeds.", "",
         "## 1. Detection at the default cut-off (0.45)", "",
         "| Dataset | Events | Planted | Precision | Recall | " + " | ".join(f"Recall {t}" for t in TYPES) + " |",
         "|---|---|---|---|---|" + "---|" * len(TYPES)]
    for n, r in results.items():
        L.append(f"| {n} | {mean(x['events'] for x in r):,.0f} | {mean(x['anomalies'] for x in r):,.0f} | "
                 f"{spread([x['overall']['precision'] for x in r])} | {spread([x['overall']['recall'] for x in r])} | "
                 + " | ".join(spread([x['recall_by_type'].get(t, float('nan')) for x in r]) for t in TYPES) + " |")
    L += ["", "Share of true positives by planted type (a false alarm has no type, so precision is overall only):", "",
          "| Dataset | " + " | ".join(TYPES) + " |", "|---|" + "---|" * len(TYPES)]
    for n, r in results.items():
        L.append(f"| {n} | " + " | ".join(spread([x['tp_share_by_type'][t] for x in r], 2) for t in TYPES) + " |")

    L += ["", "## 2. Vendor history and baselines", "",
          "| Dataset | Prior events: median (Q1-Q3) | Under 8 prior | Under 24 prior | Vendor baseline | Peer | Population |",
          "|---|---|---|---|---|---|---|"]
    for n, r in results.items():
        b = lambda k: spread([x["baseline"].get(k, 0.0) for x in r], 3)  # noqa: E731
        L.append(f"| {n} | {mean(x['history']['median'] for x in r):.0f} ({mean(x['history']['q1'] for x in r):.0f}-"
                 f"{mean(x['history']['q3'] for x in r):.0f}) | {spread([x['history']['under_8'] for x in r])} | "
                 f"{spread([x['history']['under_24'] for x in r])} | {b('vendor')} | {b('peer')} | {b('global')} |")

    L += ["", "## 3. Which rules can fire, and how often they fire", "",
          "`can fire` means the dataset has every input the rule needs. Values are the share of tuning-period events flagged.", "",
          "| Dataset | " + " | ".join(RULE_LABELS[r] for r in RULES) + " |", "|---|" + "---|" * len(RULES)]
    for n, r in results.items():
        cells = []
        for rule in RULES:
            can = r[0]["rules"][rule]["can_fire"]
            cells.append(f"{mean(x['rules'][rule]['fires'] for x in r):.4f}" if can else "no input")
        L.append(f"| {n} | " + " | ".join(cells) + " |")

    L += ["", "## 4. Each component alone", "", "| Dataset | ROC-AUC A | ROC-AUC D | ROC-AUC F | ROC-AUC fusion | PR-AUC A | PR-AUC D | PR-AUC F | PR-AUC fusion |",
          "|---|---|---|---|---|---|---|---|---|"]
    for n, r in results.items():
        L.append(f"| {n} | " + " | ".join(spread([x['component_auc'][c]['roc_auc'] for x in r]) for c in ("A", "D", "F", "fusion")) + " | "
                 + " | ".join(spread([x['component_auc'][c]['pr_auc'] for x in r]) for c in ("A", "D", "F", "fusion")) + " |")

    L += ["", "## 5. Structural zeros", "",
          "With F = 0 the highest reachable risk is 0.40 + 0.35 = 0.75 (A = D = 1); the Medium cut-off is 0.45.", "",
          "| Dataset | Events with F = 0 | Events with D = 0 | Risk mass from A | from D | from F | from bonus |", "|---|---|---|---|---|---|---|"]
    for n, r in results.items():
        L.append(f"| {n} | {spread([x['zeros']['f_zero'] for x in r])} | {spread([x['zeros']['d_zero'] for x in r])} | "
                 + " | ".join(spread([x['zeros']['mass_share'][k] for x in r]) for k in ("a", "d", "f", "bonus")) + " |")
    L += ["", "## Most likely causes", "", "CAUSES_PLACEHOLDER", ""]
    (OUT / "diagnostics_results.md").write_text("\n".join(L) + "\n")
    print("written")


if __name__ == "__main__":
    main()
