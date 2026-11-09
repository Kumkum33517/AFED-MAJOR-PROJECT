"""State of Delaware Checkbook: every state payment to vendors (Socrata 5s6n-7hpx). Licence: Public Domain.

Source: https://data.delaware.gov/Government-and-Finance/State-of-Delaware-Checkbook/5s6n-7hpx (18.2M rows).
Subset, so it stays workable: payments from 1 Jul 2019 (FY2020), payroll excluded, from a seeded random sample
of the vendors with 24 to 5,000 such payments, until about TARGET_ROWS. The cap leaves out a few giant payees
(benefit and pension funds with hundreds of thousands of payments), which would otherwise fill the whole budget. Whole vendor histories are kept: a random
sample of rows would break the sequences the LSTM needs.
Vendors are pseudonymised (some payees are individuals); department is the counterparty, category kept.
"""
import json

import numpy as np
import pandas as pd
from common import RAW, finish, get, hashed, socrata

BASE, DATASET = "https://data.delaware.gov", "5s6n-7hpx"
SINCE, MIN_PAYMENTS, MAX_PAYMENTS, TARGET_ROWS, SEED = "2019-07-01", 24, 5_000, 400_000, 42
WHERE = f"check_date >= '{SINCE}' AND check_number != 'PAYROLL'"


def sampled_vendors() -> list[str]:
    path = RAW / "delaware" / "vendor_sample.json"
    if path.exists():
        return json.loads(path.read_text())
    counts = get(f"{BASE}/resource/{DATASET}.json", timeout=900, params={
        "$select": "vendor, count(*) as n", "$where": WHERE, "$group": "vendor", "$having": f"count(*) >= {MIN_PAYMENTS}", "$limit": 500_000}).json()
    frame = pd.DataFrame(counts).assign(n=lambda d: d["n"].astype(int))
    eligible = frame[frame["n"] <= MAX_PAYMENTS].sample(frac=1, random_state=SEED)
    chosen = eligible[eligible["n"].cumsum() <= TARGET_ROWS]["vendor"].tolist()
    print(f"{len(frame):,} vendors have {MIN_PAYMENTS}+ payments, {len(frame) - len(eligible):,} above {MAX_PAYMENTS:,} left out; sampled {len(chosen):,}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chosen))
    return chosen


def main() -> None:
    vendors = sampled_vendors()
    frames = []
    for start in range(0, len(vendors), 40):  # an IN list per request, short enough for a URL
        names = ", ".join("'" + v.replace("'", "''") + "'" for v in vendors[start:start + 40])
        frames.append(socrata(BASE, DATASET, {"$where": f"{WHERE} AND vendor IN ({names})", "$order": ":id"},
                              RAW / "delaware" / f"payments_{start // 40:04d}.csv"))
    raw = pd.concat(frames, ignore_index=True)
    raw = raw.drop_duplicates()  # a fully identical row is the same payment fetched twice
    df = pd.DataFrame({
        "event_id": "DE-" + raw.index.astype(str) + "-" + raw["check_number"].fillna("na"),
        "entity_id": hashed(raw["vendor"].str.strip().str.upper(), "delaware"),
        "counterparty_id": raw["department"], "amount": raw["amount"],
        "event_timestamp": pd.to_datetime(raw["check_date"], errors="coerce"), "category": raw["category"],
    })
    finish(df, "delaware", "USD", "vendor")


if __name__ == "__main__":
    main()
