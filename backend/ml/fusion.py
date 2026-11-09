"""Turn the three signals into one risk score and tier, and recalibrate from reviewer labels."""
from itertools import product
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

SYNERGY = 0.10  # bonus when deviation and rules agree
LEVELS = ["Low", "Medium", "High", "Critical"]
MIN_REVIEWS = 10


def signals(if_score: np.ndarray, deviation: np.ndarray, rule_score: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A = Isolation Forest percentile cubed, D = saturating entity deviation, F = rule score."""
    a = (pd.Series(if_score).rank(pct=True).to_numpy()) ** 3
    d = 1 - np.exp(-np.asarray(deviation, dtype=float) / 3)
    return a, d, np.asarray(rule_score, dtype=float)


def risk_score(a: np.ndarray, d: np.ndarray, f: np.ndarray, weights: dict[str, float]) -> np.ndarray:
    risk = weights["w1"] * a + weights["w2"] * d + weights["w3"] * f + SYNERGY * np.minimum(d, f)
    return np.clip(risk, 0, 1)


def tier(risk: np.ndarray, thresholds: dict[str, float]) -> np.ndarray:
    cuts = [thresholds["medium"], thresholds["high"], thresholds["critical"]]
    return np.array(LEVELS, dtype=object)[np.searchsorted(cuts, risk, side="right")]


def recalibrate(a: np.ndarray, d: np.ndarray, f: np.ndarray, labels: np.ndarray,
                current: dict[str, Any]) -> dict[str, Any]:
    """Grid-search weights and the Medium cut-off to maximise F1 on reviewer labels."""
    labels = np.asarray(labels, dtype=int)
    if len(labels) < MIN_REVIEWS or len(set(labels.tolist())) < 2:
        return {"ok": False, "reviews": len(labels),
                "message": f"Needs at least {MIN_REVIEWS} reviews including both confirmed and dismissed alerts."}

    def score(weights: dict[str, float], medium: float) -> float:
        return float(f1_score(labels, risk_score(a, d, f, weights) >= medium, zero_division=0))

    before = score(current["weights"], current["thresholds"]["medium"])
    best = (before, current["weights"], current["thresholds"]["medium"])
    steps = np.arange(0.1, 0.71, 0.05)
    for w1, w2 in product(steps, steps):
        w3 = 1 - w1 - w2
        if w3 < 0.1 - 1e-9:
            continue
        weights = {"w1": round(float(w1), 2), "w2": round(float(w2), 2), "w3": round(float(w3), 2)}
        for medium in np.arange(0.30, 0.71, 0.025):
            candidate = score(weights, float(medium))
            if candidate > best[0] + 1e-9:  # strict, so ties keep the settings already in use
                best = (candidate, weights, round(float(medium), 3))

    thresholds = dict(current["thresholds"])
    thresholds["medium"] = best[2]
    # The higher cut-offs must stay above Medium for the tiers to mean anything.
    thresholds["high"] = min(max(thresholds["high"], round(best[2] + 0.05, 3)), 0.98)
    thresholds["critical"] = min(max(thresholds["critical"], round(thresholds["high"] + 0.05, 3)), 0.99)
    return {"ok": True, "reviews": len(labels), "f1_before": round(before, 4), "f1_after": round(best[0], 4),
            "weights": best[1], "thresholds": thresholds}
