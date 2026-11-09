"""BBMP (Bengaluru) work orders with bill payments, 2010-2019.

Source: https://data.opencity.in/dataset/bbmp-work-orders-and-bill-payment (87 CSVs). No licence is stated, so
only this script is committed, never the data.
Used: the 84 work-order files that share one layout (contractor, work order date, total, deduction, net payment,
and a department code or ward). Left out: a 2018 bill register, a job-code list and a scheme list, which use
other layouts.
event_timestamp is the WORK ORDER date, not a payment date: the files do not give payment dates.
Contractors are pseudonymised with the same salted hash as the 2024-25 loader, so histories can be joined.
"""
import pandas as pd
import requests

from common import HEADERS, RAW, download, finish, hashed, normalise_name

PACKAGE = "https://data.opencity.in/api/3/action/package_show?id=bbmp-work-orders-and-bill-payment"


def main() -> None:
    resources = requests.get(PACKAGE, headers=HEADERS, timeout=60).json()["result"]["resources"]
    frames = []
    for resource in resources:
        frame = pd.read_csv(download(resource["url"], RAW / "bbmp_2010_2019" / f"{resource['id']}.csv"), dtype=str, encoding_errors="replace")
        frame.columns = [c.strip().lower() for c in frame.columns]
        if not {"contractor", "work order date", "net payment in rs"} <= set(frame.columns):
            print(f"  skipped, other layout: {resource['name']}")
            continue
        unit = frame["bbmp code"] if "bbmp code" in frame.columns else "WARD-" + frame["ward"].astype(str)
        frames.append(pd.DataFrame({"file": resource["id"][:8], "row": frame.index.astype(str), "contractor": frame["contractor"],
                                    "date": frame["work order date"], "net": frame["net payment in rs"], "total": frame["total amount in rs"],
                                    "unit": unit, "work_order": frame.get("work order number")}))
    raw = pd.concat(frames, ignore_index=True)
    # The same work order can appear in a department file and a zone file: one payment, listed twice.
    raw = raw.drop_duplicates(subset=["contractor", "date", "net", "work_order"])
    df = pd.DataFrame({
        "event_id": "BBMP10-" + raw["file"] + "-" + raw["row"],
        "entity_id": hashed(normalise_name(raw["contractor"]), "bbmp"),
        "counterparty_id": raw["unit"].astype("string").str.strip(),
        "amount": pd.to_numeric(raw["net"].str.replace(",", ""), errors="coerce"),
        "event_timestamp": pd.to_datetime(raw["date"], format="%d/%m/%Y", errors="coerce"),
    })
    finish(df, "bbmp_2010_2019", "INR", "contractor")


if __name__ == "__main__":
    main()
