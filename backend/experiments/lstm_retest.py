"""Steps 2e and 3d, pre-registered in lstm_retest.md: the LSTM's errors in the forest on fresh data, and an EWMA baseline.

    python experiments/lstm_retest.py
"""
import json

import numpy as np

from v2_common import MAIN_REAL, OUT, classify, early_mask, reporting_seeds, scored, spread

DATASETS = MAIN_REAL + ["afed_synthetic"]
ARMS = {"with": ("v1", None), "without": ("nolstm", {"lstm": {"in_forest": False}}),
        "lstm60": ("lstm60", {"lstm": {"fit_share": 0.6}}), "ewma": ("ewma", {"temporal_source": "ewma"})}
KEYS = ["recall", "alerts", "f1", "precision", "pr_auc"]


def measure(name: str, seed: int) -> dict:
    out = {}
    for arm, (tag, settings) in ARMS.items():
        df = scored(name, seed, tag, settings)
        late = ~early_mask(df)
        y = df["is_anomaly"].to_numpy().astype(int)[late]
        out[arm] = classify(y, (df["level"] != "Low").to_numpy()[late], df["risk"].to_numpy()[late])
    return out


def main() -> None:
    results = {}
    for name in DATASETS:
        results[name] = {seed: measure(name, seed) for seed in reporting_seeds(name)}
        print(name, {arm: round(np.mean([r[arm]["recall"] for r in results[name].values()]), 4) for arm in ARMS}, flush=True)
    verdicts = {}
    for name, runs in results.items():
        w, wo = [r["with"] for r in runs.values()], [r["without"] for r in runs.values()]
        higher = np.mean([x["recall"] for x in w]) > np.mean([x["recall"] for x in wo])
        fewer = np.mean([x["alerts"] for x in w]) <= np.mean([x["alerts"] for x in wo])
        seeds = sum(a["recall"] > b["recall"] for a, b in zip(w, wo))
        verdicts[name] = {"higher_recall": bool(higher), "no_more_alerts": bool(fewer), "seeds_higher": int(seeds),
                          "verdict": "PASS" if higher and fewer and seeds >= 2 else "FAIL"}
    (OUT / "lstm_retest_results.json").write_text(json.dumps({"verdicts": verdicts, "results": results}, indent=1, default=float))

    L = ["# LSTM errors in the forest, re-tested on fresh data: results", "",
         "Produced by `experiments/lstm_retest.py`, following `lstm_retest.md`. Reporting data: planted seeds 4-6, synthetic seeds "
         "11/12/13, latest 40% of each run. v1 fusion, default weights, cut-off 0.45. Mean ± sd over seeds. Evidence only: no default changes.", "",
         "## The pre-registered rule (with against without)", "",
         "| Dataset | Recall with | Recall without | Alerts with | Alerts without | Seeds with higher recall | Verdict |", "|---|---|---|---|---|---|---|"]
    for name, runs in results.items():
        v = verdicts[name]
        col = lambda arm, k, d=3: spread([r[arm][k] for r in runs.values()], d)  # noqa: E731
        L.append(f"| {name} | {col('with', 'recall')} | {col('without', 'recall')} | {col('with', 'alerts', 0)} | {col('without', 'alerts', 0)} | "
                 f"{v['seeds_higher']} of 3 | {v['verdict']} |")
    L += ["", "## All four arms", ""]
    for key in KEYS:
        L += [f"### {key}", "", "| Dataset | " + " | ".join(ARMS) + " |", "|---|" + "---|" * len(ARMS)]
        for name, runs in results.items():
            L.append(f"| {name} | " + " | ".join(spread([r[arm][key] for r in runs.values()], 0 if key == "alerts" else 3) for arm in ARMS) + " |")
        L.append("")
    L.append("Arms: with = LSTM trained on all events (v1); without = no temporal errors in the forest; lstm60 = LSTM trained on the "
             "earliest 60% only; ewma = EWMA forecaster errors instead of the LSTM's. A 20-invoice window was not tried.")
    (OUT / "lstm_retest_results.md").write_text("\n".join(L) + "\n")
    print(json.dumps(verdicts))


if __name__ == "__main__":
    main()
