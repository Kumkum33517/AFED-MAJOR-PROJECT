"""Pre-registered in threshold_calibration.md: a per-dataset alert threshold, chosen on an earlier period, tested on a later one.

    python experiments/threshold_calibration.py
"""
import hashlib
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from model_comparison import PROCESSED, as_uploaded, generate_synthetic, inject, pipeline, to_afed  # noqa: E402

DEFAULT, GRID, CUT = 0.45, np.round(np.arange(0.30, 0.951, 0.01), 2), 0.60
REAL = ["nspcl", "mplads", "chicago", "delaware"]
OUT = Path(__file__).parent


def measure(y: np.ndarray, alert: np.ndarray) -> dict[str, float]:
    tp, fp = int((alert & (y == 1)).sum()), int((alert & (y == 0)).sum())
    fn, tn = int((~alert & (y == 1)).sum()), int((~alert & (y == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0, "precision": precision,
            "recall": recall, "balanced_accuracy": (recall + tn / (tn + fp)) / 2, "alerts": tp + fp}


def run(frame: pd.DataFrame) -> dict[str, Any]:
    scored = pipeline.run_pipeline(frame).scored
    dates = pd.to_datetime(scored["invoice_date"])
    early = (dates < dates.quantile(CUT)).to_numpy()
    y, risk = scored["is_anomaly"].astype(int).to_numpy(), scored["risk"].to_numpy()
    f1s = [measure(y[early], risk[early] >= t)["f1"] for t in GRID]
    best = max(f1s)
    chosen = float(max(t for t, f in zip(GRID, f1s) if f == best))  # ties: the higher threshold
    late = ~early
    return {"threshold": chosen, "calibration_f1": best,
            "default": measure(y[late], risk[late] >= DEFAULT), "calibrated": measure(y[late], risk[late] >= chosen)}


def spread(values: list[float], digits: int = 3) -> str:
    return f"{mean(values):.{digits}f} ± {stdev(values):.{digits}f}"


def main() -> None:
    sets = [("afed_synthetic", s, as_uploaded(generate_synthetic.generate(s))) for s in (42, 7, 123)]
    sets += [(name, s, inject(to_afed(pd.read_parquet(PROCESSED / f"{name}.parquet")), s)) for name in REAL for s in (1, 2, 3)]
    results: dict[str, list[dict[str, Any]]] = {}
    for name, seed, frame in sets:
        r = run(frame)
        results.setdefault(name, []).append(r)
        print(f"{name} seed {seed}: threshold {r['threshold']:.2f}, test F1 default {r['default']['f1']:.3f}, "
              f"calibrated {r['calibrated']['f1']:.3f}", flush=True)

    plan = (OUT / "threshold_calibration.md").read_bytes()
    lines = ["# Per-dataset alert threshold on a held-out period: results", "",
             f"Produced by `experiments/threshold_calibration.py`, following `threshold_calibration.md` "
             f"(SHA-256 {hashlib.sha256(plan).hexdigest()[:16]}). Test period: the latest 40% of each dataset by date. "
             "Real rows are treated as normal, so precision on real data is a lower bound.", "",
             "| Dataset | Threshold chosen | F1 default (0.45) | F1 calibrated | Recall default | Recall calibrated | "
             "Balanced accuracy default | Balanced accuracy calibrated | Alerts default | Alerts calibrated |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    gains = {}
    for name, runs in results.items():
        d, c = [r["default"] for r in runs], [r["calibrated"] for r in runs]
        gains[name] = mean(x["f1"] for x in c) - mean(x["f1"] for x in d)
        lines.append(f"| {name} | {', '.join(f'{r['threshold']:.2f}' for r in runs)} | {spread([x['f1'] for x in d])} | "
                     f"{spread([x['f1'] for x in c])} | {spread([x['recall'] for x in d])} | {spread([x['recall'] for x in c])} | "
                     f"{spread([x['balanced_accuracy'] for x in d])} | {spread([x['balanced_accuracy'] for x in c])} | "
                     f"{mean(x['alerts'] for x in d):,.0f} | {mean(x['alerts'] for x in c):,.0f} |")
    better = [n for n in REAL if gains[n] > 0]
    worst = min(gains[n] for n in REAL)
    verdict = "PASS" if len(better) >= 3 and worst >= -0.01 else "FAIL"
    lines += ["", "## Decision rule", "",
              f"Mean test F1 higher with calibration on {len(better)} of {len(REAL)} real datasets "
              f"({', '.join(better) or 'none'}); largest loss {min(worst, 0):.3f}. "
              f"Needed: at least 3, and no loss beyond 0.01. **{verdict}.**", "",
              "F1 change per dataset (calibrated minus default): " + ", ".join(f"{n} {g:+.3f}" for n, g in gains.items()) + "."]
    (OUT / "threshold_calibration_results.md").write_text("\n".join(lines) + "\n")
    print(verdict)


if __name__ == "__main__":
    main()
