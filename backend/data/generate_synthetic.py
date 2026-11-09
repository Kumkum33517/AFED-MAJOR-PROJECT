"""Generate a labelled procure-to-pay log: ~160 vendors, ~10k invoices, ~2.5% injected anomalies.

    python data/generate_synthetic.py [--seed 42] [--out data/afed_transactions.csv]

Normal behaviour differs per vendor on purpose, so a single global threshold cannot work.
Unlabelled look-alikes (seasonal bulk orders, genuine same-day approvals, month-end weekend
approvals, real bank changes) are included so that precision is not trivially perfect.
"""
import argparse
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

LIMIT = 500_000  # default approval limit, Rs.
START, END = pd.Timestamp("2023-10-02"), pd.Timestamp("2026-09-30")
N_VENDORS = 160
ANOMALY_SHARE = 0.025

# category: (median amount Rs., median days between invoices, median processing days)
CATEGORIES = {
    "IT Services": (150_000, 26, 5), "Office Supplies": (18_000, 13, 3), "Logistics": (65_000, 9, 2),
    "Facilities": (45_000, 28, 4), "Consulting": (210_000, 32, 7), "Raw Materials": (120_000, 10, 4),
    "Marketing": (90_000, 20, 5), "Travel": (25_000, 12, 2), "Utilities": (40_000, 29, 3),
    "Maintenance": (30_000, 17, 3),
}
DEPARTMENTS = ["Operations", "Finance", "Administration", "Engineering", "Sales", "Supply Chain", "HR", "Projects"]
NAME_A = ["Sharma", "Mehta", "Iyer", "Kulkarni", "Reddy", "Banerjee", "Nair", "Gupta", "Patel", "Rao", "Desai", "Joshi",
          "Malhotra", "Chawla", "Menon", "Saxena", "Pillai", "Bhatt", "Sethi", "Verma"]
NAME_B = {"IT Services": "Infotech", "Office Supplies": "Stationers", "Logistics": "Carriers", "Facilities": "Facility Services",
          "Consulting": "Advisors", "Raw Materials": "Industries", "Marketing": "Media", "Travel": "Travels",
          "Utilities": "Power & Water", "Maintenance": "Engineering Works"}
ANOMALY_TYPES = ["amount_spike", "invoice_splitting", "duplicate_invoice", "round_amount", "off_hours_approval",
                 "rushed_approval", "frequency_burst", "new_vendor_large", "bank_change", "sod_violation"]


def bank_account(rng: np.random.Generator) -> str:
    return "".join(rng.choice(list("0123456789"), 12))


def working_day(day: pd.Timestamp) -> pd.Timestamp:
    """Next Monday if the date falls on a weekend."""
    return day + timedelta(days=(7 - day.weekday()) if day.weekday() >= 5 else 0)


def office_time(day: pd.Timestamp, rng: np.random.Generator) -> pd.Timestamp:
    return day.normalize() + timedelta(hours=int(rng.integers(9, 18)), minutes=int(rng.integers(0, 60)))


def with_gst(pre_tax: float, rate: float) -> float:
    """Invoices carry GST and paise, which is why honest amounts are almost never round."""
    return round(pre_tax * (1 + rate) + 0.01, 2)


def purchase_order(amount: float, gst: float, rng: np.random.Generator) -> float:
    """PO value for an invoice, or NaN for the 20% raised without one.

    Freight and rounding keep real POs a few percent off. Every row goes through here, injected
    ones too: a PO left over from before an injection would give the labels away to the models.
    """
    return round(amount / (1 + gst) * rng.uniform(0.97, 1.03), 2) if rng.random() < 0.8 else np.nan


def make_vendors(rng: np.random.Generator) -> list[dict]:
    vendors = []
    categories = list(CATEGORIES)
    for i in range(N_VENDORS):
        category = categories[i % len(categories)]
        amount, gap, proc = CATEGORIES[category]
        onboarded_mid_period = rng.random() < 0.28
        created = (START + timedelta(days=int(rng.integers(30, 900))) if onboarded_mid_period
                   else START - timedelta(days=int(rng.integers(60, 1800))))
        department = str(rng.choice(DEPARTMENTS))
        dept_no = DEPARTMENTS.index(department)
        vendors.append({
            "vendor_id": f"V{i + 1:04d}",
            "vendor_name": f"{NAME_A[int(rng.integers(len(NAME_A)))]} {NAME_B[category]} {'Pvt Ltd' if i % 3 else 'LLP'}",
            "category": category, "department": department, "created": created,
            "scale": min(amount * rng.lognormal(0, 0.6), 230_000),
            "sigma": rng.uniform(0.14, 0.38), "gap": gap * rng.lognormal(0, 0.35), "proc": proc * rng.lognormal(0, 0.3),
            "gst": float(rng.choice([0.05, 0.12, 0.18, 0.18, 0.18])), "bank": bank_account(rng),
            # A few vendors really do move banks. These stay unlabelled and act as honest false alarms.
            "legit_bank_move": bank_account(rng) if rng.random() < 0.03 else None,
            "approvers": [f"APR{dept_no * 3 + k + 1:02d}" for k in range(3)],
            "clerks": [f"CLK{dept_no * 2 + k + 1:02d}" for k in range(2)],
        })
    return vendors


def make_normal_events(vendors: list[dict], rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for v in vendors:
        day = max(START, v["created"] + timedelta(days=int(rng.integers(3, 20))))
        day += timedelta(days=int(rng.uniform(0, v["gap"])))
        level, seq = 0.0, 0
        total_days = (END - START).days
        move_at = rng.uniform(0.4, 0.8)
        while day <= END:
            invoice_day = working_day(day)
            seq += 1
            years = (invoice_day - START).days / 365
            # Slow contract drift, yearly price rises and March year-end spending give the
            # sequence real temporal structure for the LSTM to learn.
            level = 0.9 * level + rng.normal(0, 0.07)
            season = 0.18 if invoice_day.month == 3 else 0.0
            pre_tax = v["scale"] * np.exp(level + 0.06 * years + season + rng.normal(0, v["sigma"]))
            if rng.random() < 0.012:  # genuine bulk order, unlabelled
                pre_tax *= rng.uniform(2.0, 3.5)
            amount = with_gst(pre_tax, v["gst"])

            proc_days = max(1, int(round(rng.lognormal(np.log(v["proc"]), 0.35))))
            if rng.random() < 0.01:  # genuine urgent payment, unlabelled
                proc_days = 0
            approval = office_time(working_day(invoice_day + timedelta(days=proc_days)), rng)
            if rng.random() < 0.003:  # month-end close on a Saturday, unlabelled
                approval = office_time(invoice_day + timedelta(days=(5 - invoice_day.weekday()) % 7), rng)

            moved = v["legit_bank_move"] and (invoice_day - START).days / total_days > move_at
            rows.append({
                "vendor_id": v["vendor_id"], "vendor_name": v["vendor_name"], "category": v["category"],
                "department": v["department"], "invoice_number": f"{v['vendor_id']}-{seq:04d}", "amount": amount,
                "invoice_date": invoice_day, "approval_date": approval,
                "approver_id": str(rng.choice(v["approvers"])), "created_by": str(rng.choice(v["clerks"])),
                "bank_account": v["legit_bank_move"] if moved else v["bank"],
                "vendor_created": v["created"], "po_amount": purchase_order(amount, v["gst"], rng),
                "is_anomaly": 0, "anomaly_type": "",
            })
            day = invoice_day + timedelta(days=max(1, int(rng.gamma(4, v["gap"] / 4))))
    return pd.DataFrame(rows)


def inject(df: pd.DataFrame, vendors: list[dict], rng: np.random.Generator) -> pd.DataFrame:
    """Inject labelled anomalies. In-place types edit a normal row; the rest append new rows."""
    by_id = {v["vendor_id"]: v for v in vendors}
    per_type = int(len(df) * ANOMALY_SHARE / (1 - ANOMALY_SHARE) / len(ANOMALY_TYPES))
    history = df.sort_values("invoice_date").groupby("vendor_id").cumcount()
    used: set[int] = set()
    new_rows: list[dict] = []

    def pick(n: int, mask: pd.Series) -> list[int]:
        """Normal rows with enough vendor history, each used at most once."""
        pool = df.index[mask & (history >= 12) & ~df.index.isin(used)]
        chosen = [int(i) for i in rng.choice(pool, size=min(n, len(pool)), replace=False)]
        used.update(chosen)
        return chosen

    def label(i: int, kind: str) -> None:
        df.loc[i, ["is_anomaly", "anomaly_type"]] = [1, kind]

    def set_amount(i: int, amount: float) -> None:
        df.loc[i, "amount"] = amount
        df.loc[i, "po_amount"] = purchase_order(amount, by_id[df.at[i, "vendor_id"]]["gst"], rng)

    def add(base: pd.Series, kind: str, day: pd.Timestamp, amount: float) -> None:
        v = by_id[base["vendor_id"]]
        approval = office_time(working_day(day + timedelta(days=max(1, int(round(v["proc"]))))), rng)
        new_rows.append({**base.to_dict(), "amount": amount, "invoice_date": day, "approval_date": approval,
                         "po_amount": purchase_order(amount, v["gst"], rng), "is_anomaly": 1, "anomaly_type": kind})

    # amount_spike: 5-11x this vendor's normal, yet under the global limit, so a global view sees nothing odd.
    normal = df.groupby("vendor_id")["amount"].transform("median")
    ceiling = 0.88 * LIMIT
    for i in pick(per_type, normal < ceiling / 5):
        set_amount(i, round(normal[i] * rng.uniform(5, min(11, ceiling / normal[i])), 2))
        label(i, "amount_spike")

    # round_amount: the amount is rounded to an exact multiple of Rs. 10,000.
    for i in pick(per_type, df["amount"] > 15_000):
        set_amount(i, float(round(df.at[i, "amount"] / 10_000) * 10_000))
        label(i, "round_amount")

    # off_hours_approval: approved on a weekend or late at night.
    for i in pick(per_type, df["amount"] > 0):
        approval = df.at[i, "approval_date"].normalize()
        if rng.random() < 0.5:
            approval += timedelta(days=(5 - approval.weekday()) % 7 + int(rng.integers(0, 2)))
            approval += timedelta(hours=int(rng.integers(10, 17)))
        else:
            approval += timedelta(hours=int(rng.choice([22, 23, 5, 6])), minutes=int(rng.integers(0, 60)))
        df.loc[i, "approval_date"] = approval
        label(i, "off_hours_approval")

    # rushed_approval: approved the same day for a vendor who usually takes 3+ days.
    slow = df["vendor_id"].map(lambda v: by_id[v]["proc"] >= 3)
    for i in pick(per_type, slow):
        df.loc[i, "approval_date"] = office_time(df.at[i, "invoice_date"], rng)
        label(i, "rushed_approval")

    # bank_change: one payment routed to an unfamiliar account.
    for i in pick(per_type, df["amount"] > 0):
        df.loc[i, "bank_account"] = bank_account(rng)
        label(i, "bank_change")

    # sod_violation: the same person created and approved the invoice.
    for i in pick(per_type, df["amount"] > 0):
        df.loc[i, "created_by"] = df.at[i, "approver_id"]
        label(i, "sod_violation")

    # duplicate_invoice: the same invoice raised again within two weeks, amount equal or within 0.1%.
    for i in pick(per_type, df["amount"] > 0):
        base = df.loc[i]
        amount = base["amount"] if rng.random() < 0.6 else round(base["amount"] * (1 + rng.uniform(-0.001, 0.001)), 2)
        add(base, "duplicate_invoice", working_day(base["invoice_date"] + timedelta(days=int(rng.integers(1, 13)))), amount)

    # invoice_splitting: 3-4 invoices at 90-100% of the limit inside 3 days, each dodging one higher approval.
    made = 0
    for i in pick(per_type, df["amount"] > 0):
        if made >= per_type:
            break
        base, n = df.loc[i], int(rng.integers(3, 5))
        # Start early in the week: a weekend inside the group would stretch it past 3 days.
        first = base["invoice_date"]
        first += timedelta(days=(7 - first.weekday()) if first.weekday() > 2 else 0)
        for _ in range(n):
            amount = round(LIMIT * rng.uniform(0.905, 0.995) + 0.37, 2)
            add(base, "invoice_splitting", first + timedelta(days=int(rng.integers(0, 3))), amount)
            made += 1

    # frequency_burst: 4-6 ordinary-looking invoices in under a week from a normally slow vendor.
    made = 0
    slow_billers = df["vendor_id"].map(lambda v: by_id[v]["gap"] >= 15)
    for i in pick(per_type, slow_billers):
        if made >= per_type:
            break
        base, n = df.loc[i], int(rng.integers(4, 7))
        for _ in range(n):
            day = working_day(base["invoice_date"] + timedelta(days=int(rng.integers(1, 6))))
            add(base, "frequency_burst", day, with_gst(by_id[base["vendor_id"]]["scale"] * rng.lognormal(0, 0.2),
                                                       by_id[base["vendor_id"]]["gst"]))
            made += 1

    # new_vendor_large: a large payment to a vendor onboarded under 45 days ago.
    newcomers = [v for v in vendors if v["created"] > START + timedelta(days=30)]
    for v in [newcomers[int(k)] for k in rng.choice(len(newcomers), size=min(per_type, len(newcomers)), replace=False)]:
        rows = df[df["vendor_id"] == v["vendor_id"]]
        if rows.empty:
            continue
        day = working_day(v["created"] + timedelta(days=int(rng.integers(6, 40))))
        add(rows.iloc[0], "new_vendor_large", day, round(LIMIT * rng.uniform(0.6, 0.86) + 0.13, 2))

    return pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)


def generate(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    vendors = make_vendors(rng)
    df = inject(make_normal_events(vendors, rng), vendors, rng)
    df = df.sort_values(["invoice_date", "vendor_id", "invoice_number"], kind="stable").reset_index(drop=True)
    df.insert(0, "event_id", [f"EV-{i + 1:06d}" for i in range(len(df))])
    # Numbered last, so that nothing a reviewer can read marks a row as injected.
    sequence = df.groupby("vendor_id").cumcount() + 1
    df["invoice_number"] = df["vendor_id"] + "-" + sequence.astype(str).str.zfill(4)
    df["processing_days"] = (df["approval_date"].dt.normalize() - df["invoice_date"]).dt.days
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "afed_transactions.csv")
    args = parser.parse_args()
    data = generate(args.seed)
    data.to_csv(args.out, index=False)
    print(f"{len(data):,} events, {data['vendor_id'].nunique()} vendors, "
          f"{data['is_anomaly'].mean():.2%} anomalous -> {args.out}")
    print(data.loc[data["is_anomaly"] == 1, "anomaly_type"].value_counts().to_string())
