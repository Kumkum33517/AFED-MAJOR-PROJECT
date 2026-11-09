"""Build the sample upload files offered on the Data & runs page.

nspcl_sample.csv: whole payment histories of 80 NSPCL vendors with 24+ payments, picked with seed 42.
Real payments, unlabelled. NSPCL permits reproduction with acknowledgement, given in the app and README.
Vendors appear only as their SAP vendor numbers, as in data/processed/nspcl.parquet.

Run after load_nspcl.py:  python make_samples.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend" / "public" / "samples"
VENDORS, SEED = 80, 42


def nspcl() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data" / "processed" / "nspcl.parquet")
    sizes = df.groupby("entity_id").size()
    eligible = sorted(sizes[sizes >= 24].index)
    chosen = np.random.default_rng(SEED).choice(eligible, size=VENDORS, replace=False)
    part = df[df["entity_id"].isin(chosen)].sort_values(["event_timestamp", "event_id"])
    number = part["entity_id"].str.removeprefix("NSPCL-")
    return pd.DataFrame({
        "event_id": part["event_id"], "vendor_id": part["entity_id"], "vendor_name": "NSPCL vendor " + number,
        "amount": part["amount_inr"].round(2), "invoice_date": part["event_timestamp"].dt.strftime("%Y-%m-%d"),
        "department": "NSPCL",
    })


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    sample = nspcl()
    sample.to_csv(OUT / "nspcl_sample.csv", index=False)
    print(f"nspcl_sample.csv: {len(sample):,} payments, {sample['vendor_id'].nunique()} vendors, "
          f"{sample['invoice_date'].min()} to {sample['invoice_date'].max()}")
