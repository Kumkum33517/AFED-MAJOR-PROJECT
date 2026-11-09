"""BBMP (Bengaluru) contractor work-order payments, 2024-25.

Source: https://data.opencity.in/dataset/bbmp-work-orders-and-payments-2024-25 (three CSVs for the
198, 225 and 243 ward regimes). Licence: "Other (Public Domain)".
Kept: payment (RTGS) date, bill-register date, net amount, ward.
Derived: processing_time_days = RTGS date minus bill-register date, both parsed from `brnumber`.
Dropped: contractor names and the phone numbers glued onto them; contractors are pseudonymised by a salted hash
of the normalised name with the phone number removed first.
"""
import re

import pandas as pd

from common import RAW, download, finish, hashed, normalise_name

BASE = "https://data.opencity.in/dataset/4e539082-aca3-4df0-b676-dc1655cf17d2/resource"
FILES = {"198": "67637545-30aa-4a6c-80fa-b46bc22bdc24/download/5cfd015d-cc0b-4526-b6e2-e547e740345a.csv",
         "225": "f0606cb1-51f7-48f8-8c38-8995f790a958/download/c57cb808-16cc-4dc7-87e1-4ec55ae58dd3.csv",
         "243": "83d27234-f87c-4a0b-a668-a58bd57b5034/download/7b43174d-fa07-46f5-b27b-e7b6ccb1a4bd.csv"}
BILL = re.compile(r"BR\s*-\s*\S*\s*/\s*(\d{2}-[A-Za-z]{3}-\d{4})")
RTGS = re.compile(r"Rtgs\s*-\s*\S*\s*/\s*(\d{2}-[A-Za-z]{3}-\d{4})")


def main() -> None:
    frames = []
    for regime, path in FILES.items():
        frame = pd.read_csv(download(f"{BASE}/{path}", RAW / "bbmp_2024" / f"wards_{regime}.csv"), dtype=str)
        frames.append(frame.assign(regime=regime))
    raw = pd.concat(frames, ignore_index=True)
    raw.columns = [c.strip().lower() for c in raw.columns]
    raw = raw.drop_duplicates(subset=[c for c in raw.columns if c not in ("slno", "regime")])
    bill = pd.to_datetime(raw["brnumber"].str.extract(BILL)[0], format="%d-%b-%Y", errors="coerce")
    paid = pd.to_datetime(raw["brnumber"].str.extract(RTGS)[0], format="%d-%b-%Y", errors="coerce")
    # A leading contractor code, where present, is the stable key; otherwise the cleaned name is.
    contractor = raw["contractor"].str.replace(r"\d{10}\s*$", "", regex=True)  # the phone number glued on the end
    amount = raw["nett"] if "nett" in raw.columns else raw["amount"]
    df = pd.DataFrame({
        "event_id": "BBMP24-" + raw["regime"] + "-" + raw.index.astype(str),
        "entity_id": hashed(normalise_name(contractor), "bbmp"),  # same salt as the 2010-19 loader, so histories can join
        "counterparty_id": "WARD-" + raw["ward"].astype(str).str.strip() if "ward" in raw.columns else pd.NA,
        "amount": amount.fillna(raw["amount"]), "event_timestamp": paid,
        "processing_time_days": (paid - bill).dt.days.where((paid - bill).dt.days >= 0),
    })
    finish(df, "bbmp_2024", "INR", "contractor")


if __name__ == "__main__":
    main()
