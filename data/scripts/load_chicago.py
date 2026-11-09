"""City of Chicago payments (Socrata s4vu-giwb). Licence: "See Terms of Use", which could not be read (HTTP 403),
so only this script is committed.

Source: https://data.cityofchicago.org/Administration-Finance/Payments/s4vu-giwb (480,237 rows).
Used: rows with a full MM/DD/YYYY check date. Payments older than two years are published as one yearly total per
vendor and contract, with no day, so they cannot form a sequence and are left out. Direct vouchers (contract "DV")
often pay private individuals and are left out too. Vendors are pseudonymised; department is the category.
"""
import pandas as pd

from common import RAW, finish, hashed, socrata

BASE, DATASET = "https://data.cityofchicago.org", "s4vu-giwb"


def main() -> None:
    raw = socrata(BASE, DATASET, {"$where": "contract_number != 'DV' AND check_date like '%/%/%'", "$order": ":id"},
                  RAW / "chicago" / "payments.csv")
    # The feed lists some payments twice, with and without a department: keep the one with it.
    raw = raw.sort_values("department_name", na_position="last")
    raw = raw.drop_duplicates(subset=["voucher_number", "amount", "check_date", "contract_number", "vendor_name"])
    df = pd.DataFrame({
        "event_id": "CHI-" + raw["voucher_number"].astype(str) + "-" + raw.groupby("voucher_number").cumcount().astype(str),
        "entity_id": hashed(raw["vendor_name"].str.strip().str.upper(), "chicago"),
        "counterparty_id": hashed(raw["contract_number"].astype(str), "chicago-contract"),
        "amount": raw["amount"], "event_timestamp": pd.to_datetime(raw["check_date"], format="%m/%d/%Y", errors="coerce"),
        "category": raw["department_name"],
    })
    finish(df, "chicago", "USD", "vendor")


if __name__ == "__main__":
    main()
