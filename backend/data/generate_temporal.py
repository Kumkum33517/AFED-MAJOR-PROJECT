"""A procure-to-pay log with real temporal structure, for the LSTM ablation.

    python data/generate_temporal.py [--seed 1] [--out data/afed_temporal.csv]

Same vendors, categories and approval habits as generate_synthetic.py. What differs:
  * Billing rhythms: fixed-day monthly (some with a larger quarterly true-up), fortnightly,
    weekly, or irregular.
  * Amounts carry persistent drift (AR(1), phi 0.95), and some vendors grow steadily all year.
  * Anomalies are only temporal, each ordinary-looking one invoice at a time:
      slow_drift         6-8 consecutive invoices compounding 6-10% each, then back to normal
      frequency_shift    a monthly vendor bills every 10-15 days for 2-3 months
      off_cycle_invoice  three extra mid-cycle invoices at normal amounts, within six months
The design was fixed before the ablation ran: see experiments/temporal_ablation.md.
"""
import argparse
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from generate_synthetic import END, START, make_vendors, office_time, purchase_order, with_gst, working_day

PATTERNS = {"monthly": 0.45, "fortnightly": 0.15, "weekly": 0.10, "irregular": 0.30}
TREND_SHARE = 0.15           # vendors growing steadily, 15-35% a year: normal business, not an anomaly
QUARTERLY_SHARE = 0.30       # of monthly vendors, a 1.6x true-up every third month
ANOMALY_SHARE = 0.025
TEMPORAL_TYPES = ["slow_drift", "frequency_shift", "off_cycle_invoice"]


def plan_vendors(rng: np.random.Generator) -> list[dict]:
    vendors = make_vendors(rng)
    for v in vendors:
        v["pattern"] = str(rng.choice(list(PATTERNS), p=list(PATTERNS.values())))
        v["day"] = int(rng.integers(1, 29))
        # Recurring contracts vary little from one invoice to the next, so the rhythm is visible.
        v["sigma"] = rng.uniform(0.05, 0.20)
        v["trend"] = rng.uniform(0.15, 0.35) if rng.random() < TREND_SHARE else 0.0
        v["quarterly"] = v["pattern"] == "monthly" and rng.random() < QUARTERLY_SHARE
    return vendors


def schedule(v: dict, rng: np.random.Generator) -> list[pd.Timestamp]:
    first = max(START, v["created"] + timedelta(days=int(rng.integers(3, 20))))
    days: list[pd.Timestamp] = []
    if v["pattern"] == "monthly":
        month = pd.Timestamp(first.year, first.month, 1)
        while month <= END:
            day = month + timedelta(days=v["day"] - 1 + int(rng.integers(-1, 2)))
            if first <= day <= END:
                days.append(working_day(day))
            month += pd.DateOffset(months=1)
    elif v["pattern"] in ("fortnightly", "weekly"):
        step = 14 if v["pattern"] == "fortnightly" else 7
        day = first
        while day <= END:
            days.append(working_day(day + timedelta(days=int(rng.integers(-1, 2)))))
            day += timedelta(days=step)
    else:
        day = first + timedelta(days=int(rng.uniform(0, v["gap"])))
        while day <= END:
            days.append(working_day(day))
            day += timedelta(days=max(1, int(rng.gamma(4, v["gap"] / 4))))
    return sorted(set(d for d in days if d <= END))


def approve(v: dict, invoice_day: pd.Timestamp, rng: np.random.Generator) -> pd.Timestamp:
    proc_days = max(1, int(round(rng.lognormal(np.log(v["proc"]), 0.35))))
    if rng.random() < 0.01:  # genuine urgent payment, unlabelled
        proc_days = 0
    approval = office_time(working_day(invoice_day + timedelta(days=proc_days)), rng)
    if rng.random() < 0.003:  # month-end close on a Saturday, unlabelled
        approval = office_time(invoice_day + timedelta(days=(5 - invoice_day.weekday()) % 7), rng)
    return approval


def vendor_rows(v: dict, rng: np.random.Generator) -> list[dict]:
    rows, level = [], 0.0
    for seq, day in enumerate(schedule(v, rng)):
        years = (day - START).days / 365
        level = 0.95 * level + rng.normal(0, 0.05)  # persistent drift, so the recent past predicts the next amount
        log_amount = np.log(v["scale"]) + level + (0.06 + v["trend"]) * years + rng.normal(0, v["sigma"])
        log_amount += 0.18 if day.month == 3 else 0.0
        log_amount += np.log(1.6) if v["quarterly"] and day.month % 3 == 0 else 0.0
        pre_tax = np.exp(log_amount)
        if rng.random() < 0.012:  # genuine bulk order, unlabelled
            pre_tax *= rng.uniform(2.0, 3.5)
        rows.append({
            "vendor_id": v["vendor_id"], "vendor_name": v["vendor_name"], "category": v["category"], "department": v["department"],
            "amount": with_gst(pre_tax, v["gst"]), "invoice_date": day, "approval_date": approve(v, day, rng),
            "approver_id": str(rng.choice(v["approvers"])), "created_by": str(rng.choice(v["clerks"])), "bank_account": v["bank"],
            "vendor_created": v["created"], "is_anomaly": 0, "anomaly_type": "",
        })
    return rows


def _like(row: dict, v: dict, day: pd.Timestamp, rng: np.random.Generator, kind: str) -> dict:
    """An extra invoice at the vendor's normal amount: nothing about it is unusual on its own."""
    amount = round(row["amount"] * rng.lognormal(0, v["sigma"]), 2)
    if abs(amount - row["amount"]) / row["amount"] < 0.01:  # keep clear of the duplicate rule
        amount = round(amount * 1.03, 2)
    return {**row, "amount": amount, "invoice_date": day, "approval_date": approve(v, day, rng), "is_anomaly": 1, "anomaly_type": kind}


def slow_drift(rows: list[dict], v: dict, rng: np.random.Generator) -> int:
    start, length, rate = int(rng.integers(12, len(rows) - 8)), int(rng.integers(6, 9)), rng.uniform(0.06, 0.10)
    for j in range(length):
        row = rows[start + j]
        row["amount"] = round(row["amount"] * (1 + rate) ** (j + 1), 2)
        row["is_anomaly"], row["anomaly_type"] = 1, "slow_drift"
    return length


def frequency_shift(rows: list[dict], v: dict, rng: np.random.Generator) -> int:
    start = int(rng.integers(12, len(rows) - 4))
    begin = rows[start]["invoice_date"]
    end = begin + pd.DateOffset(months=int(rng.integers(2, 4)))
    template = rows[start]
    kept = [r for r in rows if not begin <= r["invoice_date"] < end]
    gap, day, added = int(rng.integers(10, 16)), begin, []
    while day < end:
        added.append(_like(template, v, working_day(day), rng, "frequency_shift"))
        day += timedelta(days=gap)
    rows[:] = sorted(kept + added, key=lambda r: r["invoice_date"])
    return len(added)


def off_cycle(rows: list[dict], v: dict, rng: np.random.Generator) -> int:
    step = 2 if v["pattern"] == "monthly" else 4  # three insertions spread over about six months
    start = int(rng.integers(12, len(rows) - 2 * step - 2))
    added = []
    for k in range(3):
        before, after = rows[start + k * step], rows[start + k * step + 1]
        middle = before["invoice_date"] + (after["invoice_date"] - before["invoice_date"]) / 2
        day = working_day((middle + timedelta(days=int(rng.integers(-2, 3)))).normalize())
        added.append(_like(before, v, day, rng, "off_cycle_invoice"))
    rows[:] = sorted(rows + added, key=lambda r: r["invoice_date"])
    return len(added)


INJECTORS = {"slow_drift": (slow_drift, ("monthly", "fortnightly", "weekly", "irregular")),
             "frequency_shift": (frequency_shift, ("monthly",)),
             "off_cycle_invoice": (off_cycle, ("monthly", "fortnightly"))}


def generate(seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    vendors = plan_vendors(rng)
    per_vendor = {v["vendor_id"]: vendor_rows(v, rng) for v in vendors}
    total = sum(len(r) for r in per_vendor.values())
    target = int(total * ANOMALY_SHARE / (1 - ANOMALY_SHARE) / len(TEMPORAL_TYPES))

    # One anomaly episode per vendor at most, so episodes never overlap or interact.
    order = [vendors[int(i)] for i in rng.permutation(len(vendors))]
    used: set[str] = set()
    for kind in TEMPORAL_TYPES:
        inject, patterns = INJECTORS[kind]
        made = 0
        for v in order:
            if made >= target:
                break
            rows = per_vendor[v["vendor_id"]]
            if v["vendor_id"] in used or v["pattern"] not in patterns or len(rows) < 24:
                continue
            made += inject(rows, v, rng)
            used.add(v["vendor_id"])

    by_id = {v["vendor_id"]: v for v in vendors}
    rows = [r for vendor_rows_ in per_vendor.values() for r in vendor_rows_]
    for r in rows:  # every PO from the final amount, so no PO gives an injection away
        r["po_amount"] = purchase_order(r["amount"], by_id[r["vendor_id"]]["gst"], rng)
    df = pd.DataFrame(rows).sort_values(["invoice_date", "vendor_id"], kind="stable").reset_index(drop=True)
    df.insert(0, "event_id", [f"TV-{i + 1:06d}" for i in range(len(df))])
    df.insert(4, "invoice_number", df["vendor_id"] + "-" + (df.groupby("vendor_id").cumcount() + 1).astype(str).str.zfill(4))
    df["processing_days"] = (df["approval_date"].dt.normalize() - df["invoice_date"]).dt.days
    df.attrs["patterns"] = {v["vendor_id"]: v["pattern"] for v in vendors}
    df.attrs["trend"] = {v["vendor_id"]: v["trend"] for v in vendors}
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "afed_temporal.csv")
    args = parser.parse_args()
    data = generate(args.seed)
    data.to_csv(args.out, index=False)
    print(f"{len(data):,} events, {data['vendor_id'].nunique()} vendors, {data['is_anomaly'].mean():.2%} anomalous -> {args.out}")
    print(data.loc[data["is_anomaly"] == 1, "anomaly_type"].value_counts().to_string())
