"""Ablation on labelled data. Every variant is judged at the same review budget: its top-k events."""
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler

K_VALUES = (50, 100, 200)


def _score_variant(scores: np.ndarray, labels: np.ndarray, types: pd.Series, budget: int) -> dict[str, Any]:
    order = np.argsort(-scores, kind="stable")
    selected = np.zeros(len(labels), dtype=bool)
    selected[order[:budget]] = True
    tp = int((selected & (labels == 1)).sum())
    fp = int((selected & (labels == 0)).sum())
    fn, tn = int(labels.sum()) - tp, int((labels == 0).sum()) - fp
    precision = tp / budget if budget else 0.0
    recall = tp / int(labels.sum())
    anomalous = labels == 1
    per_type = {kind: round(float(selected[anomalous & (types == kind).to_numpy()].mean()), 4)
                for kind in sorted(types[anomalous].unique())}
    return {
        "roc_auc": round(float(roc_auc_score(labels, scores)), 4),
        "average_precision": round(float(average_precision_score(labels, scores)), 4),
        "precision_at_k": {str(k): round(float(labels[order[:k]].mean()), 4) for k in (*K_VALUES, budget) if 0 < k <= len(labels)},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
        # Accuracy is reported because it is asked for, but with 2-3% anomalies "everything is normal" scores ~97%.
        "accuracy": round((tp + tn) / len(labels), 4),
        # The mean of the two classes' hit rates: "everything is normal" scores 0.5 however rare anomalies are.
        "balanced_accuracy": round((recall + tn / (tn + fp)) / 2, 4),
        "false_alarm_rate": round(fp / (fp + tn), 4),  # false positive rate
        "false_negative_rate": round(fn / (fn + tp), 4),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "true_positives": tp, "false_positives": fp, "recall_by_type": per_type,
    }


def _reviews_to_reach(scores: np.ndarray, labels: np.ndarray, hits: int) -> int | None:
    """How many top-ranked events a reviewer must open to find `hits` true anomalies."""
    found = np.cumsum(labels[np.argsort(-scores, kind="stable")])
    position = int(np.searchsorted(found, hits))
    return position + 1 if hits and position < len(found) else None


def _operational(df: pd.DataFrame, labels: np.ndarray, risk: np.ndarray, budget: int, baseline: np.ndarray) -> dict[str, Any]:
    """What the alerts mean for the people and the money involved."""
    selected = np.zeros(len(labels), dtype=bool)
    selected[np.argsort(-risk, kind="stable")[:budget]] = True
    amount = df["amount"].to_numpy(dtype=float)
    anomalous = labels == 1
    caught = int((selected & anomalous).sum())
    baseline_reviews = _reviews_to_reach(baseline, labels, caught)
    bins = [0.0, 0.1, 0.2, 0.3, 0.45, 0.6, 0.75, 1.0001]
    edges = np.digitize(risk, bins[1:-1])
    levels = df["level"].astype(str)
    return {
        "anomaly_detection_rate": round(caught / int(anomalous.sum()), 4),
        # No dataset AFED has carries confirmed fraud, only anomalies: a fraud rate would be a claim the data cannot back.
        "fraud_detection_rate": None,
        "amount_at_risk": {"alerted": round(float(amount[selected].sum()), 2), "anomalous_caught": round(float(amount[selected & anomalous].sum()), 2),
                           "anomalous_missed": round(float(amount[~selected & anomalous].sum()), 2), "anomalous_total": round(float(amount[anomalous].sum()), 2),
                           "all_events": round(float(amount.sum()), 2)},
        "investigation": {"events": len(labels), "reviewed": budget, "reduction_vs_all": round(1 - budget / len(labels), 4),
                          "baseline_reviews_for_same_recall": baseline_reviews,
                          "reduction_vs_baseline": round(1 - budget / baseline_reviews, 4) if baseline_reviews else None},
        "score_distribution": {"bins": bins[:-1], "normal": np.bincount(edges[~anomalous], minlength=len(bins) - 1).tolist(),
                               "anomalous": np.bincount(edges[anomalous], minlength=len(bins) - 1).tolist()},
        "level_distribution": {"all": levels.value_counts().to_dict(), "anomalous": levels[anomalous].value_counts().to_dict()},
    }


def evaluate(df: pd.DataFrame, variants: dict[str, np.ndarray], alerts: int) -> dict[str, Any] | None:
    """Compare variants at the review budget AFED itself used. None when labels are absent or one-sided."""
    labelled = df["is_anomaly"].notna().to_numpy()
    labels = df.loc[labelled, "is_anomaly"].astype(int).to_numpy()
    if labelled.sum() == 0 or len(set(labels.tolist())) < 2:
        return None
    types = df.loc[labelled, "anomaly_type"].fillna("untyped").astype(str)
    budget = min(alerts, int(labelled.sum()))  # no alerts means nothing was reviewed: a budget of 0, not 1
    results = {name: _score_variant(np.asarray(s)[labelled], labels, types, budget) for name, s in variants.items()}
    baseline_fp, afed_fp = results["global_if"]["false_positives"], results["afed"]["false_positives"]
    operational = _operational(df.loc[labelled], labels, np.asarray(variants["afed"])[labelled], budget, np.asarray(variants["global_if"])[labelled])
    return {
        **operational,
        "labelled_events": int(labelled.sum()), "anomalies": int(labels.sum()), "review_budget": budget,
        "variants": results,
        "detection_rate": results["afed"]["recall"],
        "baseline_detection_rate": results["global_if"]["recall"],
        "false_alarm_reduction": round(1 - afed_fp / baseline_fp, 4) if baseline_fp else None,
    }


COMPARISON_LABELS = {"rule_based": "Rule-based (fixed threshold)", "global_if": "Global Isolation Forest only",
                     "lof": "LOF (contextual baseline)", "afed": "AFED (proposed, IF + entity-relative fusion)"}


def _classified(labels: np.ndarray, alert: np.ndarray, score: np.ndarray) -> dict[str, Any]:
    """Every metric for one model at its own alert threshold."""
    tp, fp = int((alert & (labels == 1)).sum()), int((alert & (labels == 0)).sum())
    fn, tn = int((~alert & (labels == 1)).sum()), int((~alert & (labels == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn)
    order = np.argsort(-score, kind="stable")
    return {
        "accuracy": round((tp + tn) / len(labels), 4), "balanced_accuracy": round((recall + tn / (tn + fp)) / 2, 4),
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn}, "alerts": tp + fp,
        "roc_auc": round(float(roc_auc_score(labels, score)), 4), "pr_auc": round(float(average_precision_score(labels, score)), 4),
        "false_positive_rate": round(fp / (fp + tn), 4), "false_negative_rate": round(fn / (fn + tp), 4),
        "anomaly_detection_rate": round(recall, 4), "fraud_detection_rate": None,
        "precision_at_k": {str(k): round(float(labels[order[:k]].mean()), 4) for k in (50, 100, 200, 500) if k <= len(labels)},
    }


def compare_models(df: pd.DataFrame, raw_columns: list[str], if_alert: np.ndarray, if_score: np.ndarray, limit: float) -> dict[str, Any] | None:
    """Rule-based, Global IF, LOF and AFED, each at its OWN threshold, on the labelled rows.

    Rule-based alerts at or above the fixed approval limit, scored by amount. Global IF and LOF use their
    own contamination="auto" cut-offs on the raw features. AFED alerts at Medium and above. This is the
    classification view; `variants` is the equal-budget view.
    """
    labelled = df["is_anomaly"].notna().to_numpy()
    labels = df.loc[labelled, "is_anomaly"].astype(int).to_numpy()
    if labelled.sum() == 0 or len(set(labels.tolist())) < 2:
        return None
    amount = df.loc[labelled, "amount"].to_numpy(dtype=float)
    x = StandardScaler().fit_transform(df.loc[labelled, raw_columns].fillna(0.0).to_numpy(dtype=float))
    lof = LocalOutlierFactor(n_neighbors=20, contamination="auto", n_jobs=-1)
    lof_alert = lof.fit_predict(x) == -1
    return {
        "rule_based": _classified(labels, amount >= limit, amount),
        "global_if": _classified(labels, if_alert[labelled], if_score[labelled]),
        "lof": _classified(labels, lof_alert, -lof.negative_outlier_factor_),
        "afed": _classified(labels, (df.loc[labelled, "level"] != "Low").to_numpy(), df.loc[labelled, "risk"].to_numpy()),
    }


VARIANT_LABELS = {"global_if": "Global IF", "if_entity": "IF + entity", "lstm_if": "LSTM + IF", "afed": "AFED fusion"}


def print_report(metrics: dict[str, Any]) -> None:
    print(f"\n{metrics['labelled_events']:,} labelled events, {metrics['anomalies']} anomalies, "
          f"review budget k = {metrics['review_budget']}\n")
    print(f"{'Variant':<14}{'ROC-AUC':>9}{'Avg prec':>10}{'P@50':>7}{'P@100':>7}{'P@200':>7}{'Prec':>7}{'Recall':>8}{'FA rate':>9}")
    present = [k for k in VARIANT_LABELS if k in metrics["variants"]]
    for key in present:
        v = metrics["variants"][key]
        p = v["precision_at_k"]
        at_k = "".join(f"{p.get(k, float('nan')):>7.2f}" for k in ("50", "100", "200"))
        print(f"{VARIANT_LABELS[key]:<14}{v['roc_auc']:>9.3f}{v['average_precision']:>10.3f}{at_k}"
              f"{v['precision']:>7.2f}{v['recall']:>8.2f}{v['false_alarm_rate']:>9.4f}")
    print("\nRecall by anomaly type at the same budget")
    print(f"{'Type':<22}" + "".join(f"{VARIANT_LABELS[k]:>13}" for k in present))
    for kind in metrics["variants"]["afed"]["recall_by_type"]:
        print(f"{kind:<22}" + "".join(f"{metrics['variants'][k]['recall_by_type'][kind]:>13.2f}" for k in present))
    reduction = metrics["false_alarm_reduction"]
    print(f"\nFalse alarms vs global IF at equal budget: "
          f"{'n/a' if reduction is None else f'{reduction:.1%} fewer'}")
