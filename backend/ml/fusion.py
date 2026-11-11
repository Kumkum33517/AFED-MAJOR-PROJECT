"""Turn the three signals into one risk score and tier, and recalibrate from reviewer labels."""
from itertools import product
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

SYNERGY = 0.10  # bonus when deviation and rules agree
LEVELS = ["Low", "Medium", "High", "Critical"]
MIN_REVIEWS = 20
HOLDOUT = 0.3  # newest share of reviews kept back to check a recalibration


def signals(if_score: np.ndarray, deviation: np.ndarray, rule_score: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A = Isolation Forest percentile cubed, D = saturating entity deviation, F = rule score."""
    a = (pd.Series(if_score).rank(pct=True).to_numpy()) ** 3
    d = 1 - np.exp(-np.asarray(deviation, dtype=float) / 3)
    return a, d, np.asarray(rule_score, dtype=float)


def risk_score(a: np.ndarray, d: np.ndarray, f: np.ndarray, weights: dict[str, float], rule_share: float = 1.0) -> np.ndarray:
    """Risk = w1·A + w2·D + w3·F + 0.10·min(D, F)  (v1, and field-aware fusion when every rule's inputs exist).

    Field-aware fusion (v2) passes rule_share < 1: the share of rule severity whose inputs the dataset has. F's
    weight shrinks to w3·rule_share and the weights are renormalised over what is available, so a dataset without
    approvals or bank accounts is not scored as if those rules had looked and found nothing:
        Risk = (w1·A + w2·D + w3'·F) / (w1 + w2 + w3') + 0.10·min(D, F),  w3' = w3·rule_share,
    with the bonus only while some rule can fire (rule_share > 0).
    """
    if rule_share >= 1.0:
        risk = weights["w1"] * a + weights["w2"] * d + weights["w3"] * f + SYNERGY * np.minimum(d, f)
        return np.clip(risk, 0, 1)
    w3 = weights["w3"] * max(rule_share, 0.0)
    risk = (weights["w1"] * a + weights["w2"] * d + w3 * f) / (weights["w1"] + weights["w2"] + w3)
    if rule_share > 0:
        risk = risk + SYNERGY * np.minimum(d, f)
    return np.clip(risk, 0, 1)


CALIBRATION_GRID = np.round(np.arange(0.30, 0.951, 0.01), 2)


def calibrate_medium(risk: np.ndarray, dates: pd.Series, mode: str, target_rate: float = 0.02, fit_share: float = 0.6,
                     labels: np.ndarray | None = None) -> dict[str, Any] | None:
    """Choose the Medium cut-off on the earliest `fit_share` of events by date; the caller applies it to all of them.

    alert_budget  needs no labels: the cut-off that alerts on `target_rate` of the earlier events. Usable in a
                  real deployment, where an audit team knows how many alerts it can review.
    label         the cut-off with the best F1 on labelled earlier events (0.30 to 0.95, ties to the higher one).
                  Needs labels, so it is for evaluation only: a real deployment has none.
    Returns None when the mode cannot run (off, too few events, or no labels of both kinds).
    """
    if mode not in ("alert_budget", "label"):
        return None
    dates = pd.to_datetime(pd.Series(dates).reset_index(drop=True))
    early = (dates < dates.quantile(fit_share)).to_numpy()
    if early.sum() < 20:
        return None
    fit = np.asarray(risk, dtype=float)[early]
    if mode == "alert_budget":
        k = int(np.floor(target_rate * len(fit)))
        if k < 1:
            return None
        cut = float(np.sort(fit)[::-1][k - 1])  # the k-th highest: alerting on risk >= cut gives about k alerts
    else:
        y = None if labels is None else np.asarray(labels, dtype=float)[early]
        if y is None or np.isnan(y).any() or len(set(y.tolist())) < 2:
            return None
        scores = [float(f1_score(y.astype(int), fit >= t, zero_division=0)) for t in CALIBRATION_GRID]
        best = max(scores)
        cut = float(max(t for t, f in zip(CALIBRATION_GRID, scores) if f == best))
    return {"mode": mode, "medium": round(cut, 6), "fit_events": int(early.sum()),
            "fit_alert_rate": round(float((fit >= cut).mean()), 6), "target_rate": target_rate if mode == "alert_budget" else None}


def calibrated_thresholds(thresholds: dict[str, float], medium: float) -> dict[str, float]:
    """A new Medium cut-off, with High and Critical kept above it so the tiers stay ordered."""
    high = min(max(thresholds["high"], medium + 0.05), 0.98)
    return {"medium": medium, "high": high, "critical": min(max(thresholds["critical"], high + 0.05), 0.99)}


def rule_share(active: list[str], severities: dict[str, float]) -> float:
    """Share of total rule severity carried by the rules that can fire on this data."""
    return sum(severities[r] for r in active) / sum(severities.values())


def tier(risk: np.ndarray, thresholds: dict[str, float]) -> np.ndarray:
    cuts = [thresholds["medium"], thresholds["high"], thresholds["critical"]]
    return np.array(LEVELS, dtype=object)[np.searchsorted(cuts, risk, side="right")]


def recalibrate(a: np.ndarray, d: np.ndarray, f: np.ndarray, labels: np.ndarray,
                current: dict[str, Any]) -> dict[str, Any]:
    """Grid-search weights and the Medium cut-off for the best F1 on reviewer labels, then check them on newer ones.

    Rows must be in review order, oldest first. The search sees the older 70%; the newest 30% are held back, and
    the new settings are kept only if they do at least as well there. A fit judged on its own data always looks
    better, so only the held-back F1 says whether it learned anything.
    """
    labels = np.asarray(labels, dtype=int)
    if len(labels) < MIN_REVIEWS or len(set(labels.tolist())) < 2:
        return {"ok": False, "reviews": len(labels),
                "message": f"Needs at least {MIN_REVIEWS} reviews including both confirmed and dismissed alerts."}
    split = int(len(labels) * (1 - HOLDOUT))
    fit, check = slice(0, split), slice(split, None)
    if len(set(labels[fit].tolist())) < 2 or len(set(labels[check].tolist())) < 2:
        return {"ok": False, "reviews": len(labels),
                "message": "Both the older and the newest reviews need confirmed and dismissed alerts, to fit and then check."}

    def score(part: slice, weights: dict[str, float], medium: float) -> float:
        return float(f1_score(labels[part], risk_score(a[part], d[part], f[part], weights) >= medium, zero_division=0))

    before = score(fit, current["weights"], current["thresholds"]["medium"])
    best = (before, current["weights"], current["thresholds"]["medium"])
    steps = np.arange(0.1, 0.71, 0.05)
    for w1, w2 in product(steps, steps):
        w3 = 1 - w1 - w2
        if w3 < 0.1 - 1e-9:
            continue
        weights = {"w1": round(float(w1), 2), "w2": round(float(w2), 2), "w3": round(float(w3), 2)}
        for medium in np.arange(0.30, 0.71, 0.025):
            candidate = score(fit, weights, float(medium))
            if candidate > best[0] + 1e-9:  # strict, so ties keep the settings already in use
                best = (candidate, weights, round(float(medium), 3))

    held_before = score(check, current["weights"], current["thresholds"]["medium"])
    held_after = score(check, best[1], best[2])
    report = {"reviews": len(labels), "fit_reviews": split, "check_reviews": len(labels) - split,
              "f1_before": round(before, 4), "f1_after": round(best[0], 4),
              "heldout_before": round(held_before, 4), "heldout_after": round(held_after, 4)}
    if held_after < held_before:
        return {"ok": False, **report, "message": f"The new settings did worse on the newest {len(labels) - split} reviews "
                f"(F1 {held_before:.3f} to {held_after:.3f}), so nothing was changed."}

    thresholds = dict(current["thresholds"])
    thresholds["medium"] = best[2]
    # The higher cut-offs must stay above Medium for the tiers to mean anything.
    thresholds["high"] = min(max(thresholds["high"], round(best[2] + 0.05, 3)), 0.98)
    thresholds["critical"] = min(max(thresholds["critical"], round(thresholds["high"] + 0.05, 3)), 0.99)
    return {"ok": True, **report, "weights": best[1], "thresholds": thresholds}
