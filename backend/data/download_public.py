"""Download real, unlabelled vendor-payment data and map it to the AFED schema.

    python data/download_public.py sf --limit 20000
    python data/download_public.py chicago --limit 20000

These sets are for demos only: they have no labels, so they produce no accuracy numbers.
Neither has approvals, bank accounts, vendor creation dates or invoice times, so the rules needing those stay silent.
Chicago's direct vouchers (contract "DV") often pay private individuals, so they are excluded.

Amounts are US dollars, converted at the fixed illustrative rate below so that the rupee limit rules mean something.
San Francisco publishes no payment date: `data_as_of` is a source-system update stamp, used here as a stand-in,
so date-based signals on that set are only indicative.
"""
import argparse
import hashlib
from datetime import date
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).parent
PAGE = 5000
USD_TO_INR = 84.0  # illustrative, for demo data only


def fetch(url: str, params: dict, limit: int) -> pd.DataFrame:
    """Page through a Socrata endpoint."""
    frames = []
    for offset in range(0, limit, PAGE):
        response = requests.get(url, params={**params, "$limit": min(PAGE, limit - offset), "$offset": offset}, timeout=180)
        response.raise_for_status()
        page = response.json()
        if not page:
            break
        frames.append(pd.DataFrame(page))
        print(f"  fetched {offset + len(page):,}")
    if not frames:
        raise SystemExit("The endpoint returned no rows.")
    return pd.concat(frames, ignore_index=True)


def vendor_key(name: pd.Series) -> pd.Series:
    """A stable id from the vendor's name, since neither source publishes a vendor id."""
    return name.map(lambda n: "V-" + hashlib.sha1(str(n).encode()).hexdigest()[:10])


def tidy(out: pd.DataFrame) -> pd.DataFrame:
    out["amount"] = (pd.to_numeric(out["amount"], errors="coerce") * USD_TO_INR).round(2)
    out["invoice_date"] = pd.to_datetime(out["invoice_date"], errors="coerce", format="mixed", utc=True).dt.tz_localize(None)
    out = out.dropna(subset=["amount", "invoice_date", "vendor_name"])
    out = out[out["amount"] > 0].drop_duplicates("event_id").sort_values("invoice_date")
    out["invoice_date"] = out["invoice_date"].dt.date
    return out


def san_francisco(limit: int) -> pd.DataFrame:
    # Summed by the server: one voucher spans many budget lines, including reversals that net it to zero,
    # so grouping a capped sample here would give wrong amounts.
    raw = fetch("https://data.sf.gov/resource/n9pm-xkyq.json", {
        "$select": "vendor, voucher, sum(vouchers_paid) as vouchers_paid, max(data_as_of) as data_as_of, "
                   "max(character) as character, max(department) as department",
        "$where": f"voucher IS NOT NULL AND fiscal_year >= '{date.today().year}'", "$group": "vendor, voucher",  # older years time out
        "$having": "sum(vouchers_paid) > 0", "$order": "voucher DESC"}, limit)
    return tidy(pd.DataFrame({
        "event_id": "SF-" + raw["voucher"].astype(str) + "-" + vendor_key(raw["vendor"]),
        "vendor_id": vendor_key(raw["vendor"]), "vendor_name": raw["vendor"], "amount": raw["vouchers_paid"],
        "invoice_date": raw["data_as_of"], "invoice_number": raw["voucher"], "category": raw["character"],
        "department": raw["department"],
    }))


def chicago(limit: int) -> pd.DataFrame:
    # :id order is an arbitrary but stable shuffle: ordered by voucher, a capped sample never reaches most voucher classes.
    raw = fetch("https://data.cityofchicago.org/resource/s4vu-giwb.json",
                {"$where": "contract_number != 'DV' AND check_date like '%/%/%'", "$order": ":id"}, limit)
    if "department_name" not in raw:
        raw["department_name"] = pd.NA
    raw["amount"] = pd.to_numeric(raw["amount"], errors="coerce")
    # The feed lists some payments twice, with and without a department.
    raw = raw.sort_values("department_name", na_position="last")
    raw = raw.drop_duplicates(["voucher_number", "amount", "check_date", "contract_number"])
    raw = raw.groupby(["vendor_name", "voucher_number"], as_index=False).agg(
        amount=("amount", "sum"), check_date=("check_date", "first"), department_name=("department_name", "first"))
    return tidy(pd.DataFrame({
        "event_id": "CHI-" + raw["voucher_number"].astype(str) + "-" + vendor_key(raw["vendor_name"]),
        "vendor_id": vendor_key(raw["vendor_name"]), "vendor_name": raw["vendor_name"], "amount": raw["amount"],
        "invoice_date": raw["check_date"], "invoice_number": raw["voucher_number"],
        "category": raw["department_name"], "department": raw["department_name"],
    }))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", choices=["sf", "chicago"])
    parser.add_argument("--limit", type=int, default=20_000)
    args = parser.parse_args()
    mapped = san_francisco(args.limit) if args.source == "sf" else chicago(args.limit)
    path = HERE / f"public_{args.source}.csv"
    mapped.to_csv(path, index=False)
    print(f"{len(mapped):,} rows, {mapped['vendor_id'].nunique():,} vendors, "
          f"{mapped['invoice_date'].min()} to {mapped['invoice_date'].max()} -> {path}")
