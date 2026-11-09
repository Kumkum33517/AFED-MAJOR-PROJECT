"""Shared pieces for the dataset loaders: the common schema, personal-data rules, currency, and output.

Every loader downloads its source into data/raw/<dataset>/ (never edited), maps it to the common
schema below, and writes data/processed/<dataset>.parquet. build_unified.py then stacks them.

Common schema
  event_id              unique within the dataset, prefixed with the dataset name
  entity_id             the vendor, supplier or contractor the event belongs to. A source's own code where it
                        has one; otherwise a salted hash of the normalised name, so no names are stored
  entity_type           vendor | supplier | contractor | merchant
  counterparty_id       the buyer or department side, hashed the same way when it is a name; may be empty
  amount                in the source's own currency, never converted
  currency              ISO code of `amount`
  amount_inr            converted with the documented rates below; equal to `amount` for INR
  event_timestamp       the payment, check, award or contract date, as named per dataset in DATASETS.md
  payment_gap_days      derived: days since this entity's previous event in the same dataset
  processing_time_days  from the source where it has two dates (for example bill and payment); else empty
  category              the source's own grouping (department, object of expenditure, sector); may be empty
  source_dataset        the dataset name; injected anomalies get "<name>+injected" and never live in these files
  is_synthetic          true only for generated data
  label                 1 or 0 only where the source itself is labelled; empty for real data
  anomaly_type          the source's anomaly type where labelled
"""
import hashlib
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

DATA = Path(__file__).resolve().parents[1]
RAW, PROCESSED = DATA / "raw", DATA / "processed"
# An honest client name. Some hosts (Kaggle) refuse the generic python-requests agent.
HEADERS = {"User-Agent": "AFED-dataset-loader/1.0"}
COLUMNS = ["event_id", "entity_id", "entity_type", "counterparty_id", "amount", "currency", "amount_inr", "event_timestamp",
           "payment_gap_days", "processing_time_days", "category", "source_dataset", "is_synthetic", "label", "anomaly_type"]

# One fixed rate per currency, for all years: a stated simplification, so amounts stay comparable within a dataset.
RATES_TO_INR = {
    "INR": 1.0,
    "USD": 93.92,      # ECB reference rate, 2026-11-06, via api.frankfurter.dev
    "COP": 0.028995,   # ECB publishes no COP: open.er-api.com, 2026-11-09 (1 USD = 94.047485 INR = 3243.549 COP)
}

# Personal data the brief rules out: phone numbers, Aadhaar (12 digits), PAN, and long digit runs such as accounts.
_PHONE = re.compile(r"(?:\+?91[\s-]?)?\b[6-9]\d{9}\b")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_LONG_DIGITS = re.compile(r"\b\d{11,18}\b")


def strip_personal(text: pd.Series) -> pd.Series:
    """Remove phone numbers, PAN and long digit runs (Aadhaar, account numbers) from free text."""
    cleaned = text.astype("string")
    for pattern in (_PHONE, _PAN, _LONG_DIGITS):
        cleaned = cleaned.str.replace(pattern, " ", regex=True)
    return cleaned.str.replace(r"\s+", " ", regex=True).str.strip()


def normalise_name(name: pd.Series) -> pd.Series:
    """For matching one firm across spellings: case, M/s prefixes, punctuation and spacing."""
    text = strip_personal(name).str.upper()
    text = text.str.replace(r"^\s*M\s*/?\s*S\.?\s+", "", regex=True).str.replace(r"[^A-Z0-9 ]", " ", regex=True)
    return text.str.split().str.join(" ")


def hashed(values: pd.Series, salt: str) -> pd.Series:
    """A stable pseudonym. Salted per dataset, so the same name in two datasets is not linkable by default."""
    return values.map(lambda v: None if pd.isna(v) or v == "" else f"{salt}-" + hashlib.sha256(f"{salt}|{v}".encode()).hexdigest()[:12])


def download(url: str, path: Path, **params) -> Path:
    """Fetch once into data/raw; later runs reuse the file. Writes to .part first, so a broken download never looks complete."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    with requests.get(url, params=params or None, headers=HEADERS, stream=True, timeout=300) as response:
        response.raise_for_status()
        with open(partial, "wb") as out:
            for chunk in response.iter_content(1 << 20):
                out.write(chunk)
    partial.replace(path)
    return path


def get(url: str, attempts: int = 4, headers: dict | None = None, **kwargs) -> requests.Response:
    """GET with retries: public portals reset connections and time out under load."""
    for attempt in range(attempts):
        try:
            response = requests.get(url, headers={**HEADERS, **(headers or {})}, **kwargs)
            if response.status_code < 500 or attempt == attempts - 1:  # a 5xx is often a busy server: try again
                response.raise_for_status()
                return response
            error: Exception = requests.HTTPError(f"HTTP {response.status_code}")
        except (requests.ConnectionError, requests.Timeout) as caught:
            error = caught
            if attempt == attempts - 1:
                raise
        print(f"  retrying after {error}", flush=True)
        time.sleep(5 * 2 ** attempt)
    raise AssertionError("unreachable")


def socrata(base: str, dataset: str, params: dict, path: Path, page: int = 50_000) -> pd.DataFrame:
    """Page through a Socrata query into one CSV in data/raw, fetched once."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        frames, offset = [], 0
        while True:
            rows = get(f"{base}/resource/{dataset}.json", params={**params, "$limit": page, "$offset": offset}, timeout=600).json()
            if not rows:
                break
            frames.append(pd.DataFrame(rows))
            offset += len(rows)
            print(f"  {offset:,} rows", flush=True)
            if len(rows) < page:
                break
        pd.concat(frames, ignore_index=True).to_csv(path, index=False)
    return pd.read_csv(path, dtype=str)


def finish(df: pd.DataFrame, name: str, currency: str, entity_type: str, synthetic: bool = False) -> pd.DataFrame:
    """Fill the derived columns, drop unusable rows and duplicates, and write data/processed/<name>.parquet."""
    df = df.copy()
    df["source_dataset"], df["currency"], df["entity_type"], df["is_synthetic"] = name, currency, entity_type, synthetic
    for column in COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], errors="coerce")
    before = len(df)
    df = df.dropna(subset=["entity_id", "amount", "event_timestamp"])
    df = df[np.isfinite(df["amount"]) & (df["amount"] > 0)]
    # Only exact event repeats go here. What else counts as a duplicate depends on the source, so each loader
    # decides and documents it: identical works paid on the same day are real activity, not duplicates.
    df = df.drop_duplicates(subset=["event_id"])
    df["amount_inr"] = (df["amount"] * RATES_TO_INR[currency]).round(2)
    df = df.sort_values(["entity_id", "event_timestamp", "event_id"], kind="stable")
    df["payment_gap_days"] = df.groupby("entity_id")["event_timestamp"].diff().dt.total_seconds() / 86400
    df["label"] = pd.to_numeric(df["label"], errors="coerce").astype("Float64")
    df = df[COLUMNS].sort_values(["event_timestamp", "event_id"], kind="stable").reset_index(drop=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED / f"{name}.parquet", index=False)
    per_entity = df.groupby("entity_id").size()
    print(f"{name}: {len(df):,} events kept of {before:,}, {per_entity.size:,} entities, {int((per_entity >= 24).sum()):,} with 24+ events, "
          f"{df['event_timestamp'].min():%Y-%m-%d} to {df['event_timestamp'].max():%Y-%m-%d}")
    return df


def to_afed(df: pd.DataFrame) -> pd.DataFrame:
    """Adapter: the common schema to AFED's upload schema, so the pipeline runs on any processed dataset."""
    return pd.DataFrame({
        "event_id": df["event_id"], "vendor_id": df["entity_id"], "vendor_name": df["entity_id"], "amount": df["amount_inr"],
        "invoice_date": df["event_timestamp"], "category": df["category"], "department": df["counterparty_id"],
        "processing_days": df["processing_time_days"], "is_anomaly": df["label"], "anomaly_type": df["anomaly_type"],
    })


if __name__ == "__main__":
    sys.exit("Run a load_<dataset>.py script, or build_unified.py.")
