"""Seeded anomaly injection into real, unlabelled data, for evaluation only.

Real procurement data has no ground truth. To measure detection on it, anomalies are planted into the
histories of real vendors, and everything else is treated as normal. Any real anomaly in the data then
counts as a false alarm, so precision measured this way is a lower bound.

Injected data never leaves the evaluation: it is built in memory, its events are tagged in `anomaly_type`
and in `source_dataset` ("<name>+injected"), and nothing here writes to data/processed.

Types, one episode per vendor:
  amount_spike       one invoice 5-11x its own amount
  slow_drift         6-8 consecutive invoices compounding 6-10% each
  frequency_shift    five extra invoices, one in the middle of each of five consecutive gaps
  off_cycle_invoice  three extra invoices placed mid-gap, spread over the vendor's history
"""
from typing import Any

import numpy as np
import pandas as pd

TYPES = ["amount_spike", "slow_drift", "frequency_shift", "off_cycle_invoice"]
MIN_HISTORY = 24


def _extra(row: pd.Series, when: pd.Timestamp, number: int, kind: str, rng: np.random.Generator) -> dict[str, Any]:
    """An added invoice at the vendor's ordinary amount: nothing about it is unusual on its own."""
    return {**row.to_dict(), "event_id": f"{row['event_id']}+inj{number}", "invoice_date": when,
            "amount": round(float(row["amount"]) * rng.lognormal(0, 0.1) * 1.03, 2), "is_anomaly": 1.0, "anomaly_type": kind}


def inject(frame: pd.DataFrame, seed: int, share: float = 0.025) -> pd.DataFrame:
    """Return a copy of an AFED-schema frame with about `share` of events anomalous, labelled, and the rest labelled 0."""
    rng = np.random.default_rng(seed)
    df = frame.copy()
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    df["amount"] = pd.to_numeric(df["amount"])
    df = df.sort_values(["vendor_id", "invoice_date", "event_id"], kind="stable").reset_index(drop=True)
    df["is_anomaly"], df["anomaly_type"] = 0.0, None

    sizes = df.groupby("vendor_id").size()
    candidates = list(sizes[sizes >= MIN_HISTORY].index)
    rng.shuffle(candidates)
    target = int(len(df) * share / len(TYPES))
    made = dict.fromkeys(TYPES, 0)
    added: list[dict[str, Any]] = []
    positions = df.groupby("vendor_id").indices

    for vendor in candidates:
        kind = min(made, key=made.get)  # fill the types evenly
        if made[kind] >= target:
            break
        rows = positions[vendor]
        start = int(rng.integers(12, len(rows) - 10))
        if kind == "amount_spike":
            i = rows[start]
            df.loc[i, "amount"] = round(df.at[i, "amount"] * rng.uniform(5, 11), 2)
            df.loc[i, ["is_anomaly", "anomaly_type"]] = [1.0, kind]
            made[kind] += 1
        elif kind == "slow_drift":
            length, rate = int(rng.integers(6, 9)), rng.uniform(0.06, 0.10)
            for j in range(length):
                i = rows[start + j]
                df.loc[i, "amount"] = round(df.at[i, "amount"] * (1 + rate) ** (j + 1), 2)
                df.loc[i, ["is_anomaly", "anomaly_type"]] = [1.0, kind]
            made[kind] += length
        else:
            gaps = range(start, start + 5) if kind == "frequency_shift" else (start, start + 3, start + 6)
            for n, g in enumerate(gaps):
                before, after = df.loc[rows[g]], df.loc[rows[g + 1]]
                if after["invoice_date"] - before["invoice_date"] < pd.Timedelta(days=2):
                    continue  # no room for an invoice between them
                middle = before["invoice_date"] + (after["invoice_date"] - before["invoice_date"]) / 2
                added.append(_extra(before, middle.normalize(), n, kind, rng))
                made[kind] += 1

    out = pd.concat([df, pd.DataFrame(added)], ignore_index=True) if added else df
    return out.sort_values(["invoice_date", "event_id"], kind="stable").reset_index(drop=True)


SUBTHRESHOLD_MULTIPLIERS = (2, 3, 5)


def inject_subthreshold(frame: pd.DataFrame, seed: int, share: float = 0.025, limit: float = 500_000,
                        multipliers: tuple[int, ...] = SUBTHRESHOLD_MULTIPLIERS) -> pd.DataFrame:
    """Plant amounts that a global limit cannot see: 2x, 3x or 5x the vendor's own median, kept below `limit`.

    One invoice per vendor (vendors with MIN_HISTORY or more events), chosen at a seeded random position after
    the vendor's first 12 invoices. Its amount becomes multiplier x the median of the vendor's earlier invoices,
    only if that is below the limit; otherwise the vendor is skipped. Multipliers are filled evenly, up to about
    `share` of events in all. Tagged in anomaly_type as "subthreshold_<m>x"; the input frame is not changed.
    """
    rng = np.random.default_rng(seed)
    df = frame.copy()
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    df["amount"] = pd.to_numeric(df["amount"])
    df = df.sort_values(["vendor_id", "invoice_date", "event_id"], kind="stable").reset_index(drop=True)
    df["is_anomaly"], df["anomaly_type"] = 0.0, None
    sizes = df.groupby("vendor_id").size()
    candidates = list(sizes[sizes >= MIN_HISTORY].index)
    rng.shuffle(candidates)
    target = int(len(df) * share)
    made = {m: 0 for m in multipliers}
    positions = df.groupby("vendor_id").indices
    for vendor in candidates:
        if sum(made.values()) >= target:
            break
        multiplier = min(made, key=made.get)
        rows = positions[vendor]
        start = int(rng.integers(12, len(rows) - 10))
        amount = multiplier * float(np.median(df.loc[rows[:start], "amount"]))
        if amount >= limit:
            continue
        i = rows[start]
        df.loc[i, "amount"] = round(amount, 2)
        df.loc[i, ["is_anomaly", "anomaly_type"]] = [1.0, f"subthreshold_{multiplier}x"]
        made[multiplier] += 1
    return df.sort_values(["invoice_date", "event_id"], kind="stable").reset_index(drop=True)
