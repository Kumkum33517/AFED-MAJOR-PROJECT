"""MPLADS fund disbursements to vendors, as published on the MPLADS portal and scraped to Kaggle.

Source: https://www.kaggle.com/datasets/rajan1673/indias-mplads (file
Expenditure_on_Completed_and_On-going_Works_as_on_Date.csv). Kaggle lists MIT; the government portal's own
terms are not stated, so only this script is committed, never the data.
Kept: vendor id (the portal's numeric code), disbursement date and amount, implementing agency (hashed), activity.
Dropped: vendor and MP names. Not used: the dataset's real_*.csv files, whose payment types and references look derived.
"""
import zipfile

import pandas as pd

from common import RAW, download, finish, hashed

URL = "https://www.kaggle.com/api/v1/datasets/download/rajan1673/indias-mplads"
FILE = "Expenditure_on_Completed_and_On-going_Works_as_on_Date.csv"


def main() -> None:
    archive = download(URL, RAW / "mplads" / "indias-mplads.zip")
    with zipfile.ZipFile(archive) as z:
        raw = pd.read_csv(z.open(FILE), dtype=str)
    # A duplicate is a row identical in every field but the running serial number.
    raw = raw.drop_duplicates(subset=[c for c in raw.columns if c != "Sno"])
    df = pd.DataFrame({
        # The work's id plus the row's position within it: one work is paid in several instalments.
        "event_id": "MPLADS-" + raw["WORK_RECOMMENDATION_DTL_ID"] + "-" + raw.groupby("WORK_RECOMMENDATION_DTL_ID").cumcount().astype(str),
        "entity_id": "MPLADS-V" + raw["VENDOR_ID"],
        "counterparty_id": hashed(raw["IA_NAME"].str.strip().str.upper(), "mplads-ia"),
        "amount": raw["FUND_DISBURSED_AMT"], "event_timestamp": pd.to_datetime(raw["EXPENDITURE_DATE"], format="%d-%b-%Y", errors="coerce"),
        "category": raw["ACTIVITY_NAME"],
    })
    finish(df, "mplads", "INR", "vendor")


if __name__ == "__main__":
    main()
