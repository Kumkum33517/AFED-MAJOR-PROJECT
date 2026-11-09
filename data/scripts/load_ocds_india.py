"""Indian open-contracting (OCDS) award data: Himachal Pradesh (CC BY 4.0) and Assam (ODbL).

  ocds_hp    : https://data.open-contracting.org/en/publication/77 (full.jsonl.gz), awards 2012-2020.
  ocds_assam : https://github.com/CivicDataLab/assam-tenders-data, OCDS v3 mapping, awards 2019-2023.
Supplier names are free text with no real ids (Himachal's are all "1.0"), so supplier histories are thin. These
sets are therefore modelled from the BUYER side: entity = the buying department, counterparty = the supplier
(pseudonymised; many are individual contractors). Events are awards, not payments. Zero-value awards are dropped.
Two datasets in one loader, because both use the same OCDS shape.
"""
import gzip
import json
import zipfile

import pandas as pd

from common import RAW, download, finish, hashed, normalise_name

HP_URL = "https://data.open-contracting.org/en/publication/77/download?name=full.jsonl.gz"
ASSAM_URL = ("https://raw.githubusercontent.com/CivicDataLab/assam-tenders-data/main/data/ProcessedData/"
             "ocds-mapped-data/v3/ocds_mapped_data_fiscal_year_2016_2022_v3.json.zip")


def awards(releases: list[dict], prefix: str) -> pd.DataFrame:
    rows = []
    for release in releases:
        buyer = (release.get("buyer") or {}).get("id") or (release.get("buyer") or {}).get("name")
        fallback = (release.get("award") or {}).get("date") or ((release.get("tender") or {}).get("tenderPeriod") or {}).get("startDate")
        for n, award in enumerate(release.get("awards") or []):
            when = award.get("date") or (award.get("contractPeriod") or {}).get("startDate") or fallback
            for supplier in award.get("suppliers") or [{}]:
                rows.append({"event_id": f"{prefix}-{release.get('ocid')}-{award.get('id', n)}-{supplier.get('name', '')[:20]}",
                             "buyer": buyer, "supplier": supplier.get("name"),
                             "amount": (award.get("value") or {}).get("amount"), "when": when})
    return pd.DataFrame(rows)


def convert(frame: pd.DataFrame, name: str) -> None:
    df = pd.DataFrame({
        "event_id": frame["event_id"], "entity_id": hashed(frame["buyer"].astype("string").str.upper(), name),
        "counterparty_id": hashed(normalise_name(frame["supplier"].fillna("")).replace("", None), f"{name}-supplier"),
        "amount": frame["amount"], "event_timestamp": pd.to_datetime(frame["when"], errors="coerce", utc=True).dt.tz_localize(None),
    })
    finish(df, name, "INR", "buyer")


def main() -> None:
    with gzip.open(download(HP_URL, RAW / "ocds_hp" / "full.jsonl.gz"), "rt") as f:
        convert(awards([json.loads(line) for line in f], "HP"), "ocds_hp")
    with zipfile.ZipFile(download(ASSAM_URL, RAW / "ocds_assam" / "v3.json.zip")) as z:
        releases = json.load(z.open(z.namelist()[0]))["releases"]
    convert(awards(releases, "AS"), "ocds_assam")


if __name__ == "__main__":
    main()
