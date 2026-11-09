"""NSPCL (NTPC-SAIL Power Company) monthly vendor payment reports, Jan 2023 onward.

Source: https://www.nspcl.co.in/vendor-payment (monthly PDF reports). Terms: the site's copyright page
allows reproduction free of charge with acknowledgement, if accurate and not misleading.
Kept: vendor number (the company's SAP code, not personal), payment date, payment document, amount.
The invoice reference is read only to tell duplicates apart and is not stored.
Dropped: vendor name and city (some vendors are individuals) and cheque/bank references.
"""
import re

import pandas as pd
import pdfplumber
import requests

from common import RAW, download, finish

PAGE = "https://www.nspcl.co.in/vendor-payment"
# One payment: vendor no., DD.MM.YYYY, payment document, optional cheque/reference, amount with paise.
ROW = re.compile(r"\b(1[0-9]\d{8}) (\d{2}\.\d{2}\.\d{4}) (\d{10})(?: (\S+))? ([\d,]+\.\d{2})\b([^\n]*)")


def main() -> None:
    html = requests.get(PAGE, timeout=60).text
    links = sorted(set(re.findall(r'href="(https?://[^"]*/srpt/monthly/[^"]+\.pdf)"', html)))
    print(f"{len(links)} monthly reports listed")
    rows = []
    for link in links:
        path = download(link, RAW / "nspcl" / link.rsplit("/", 1)[1])
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        found = ROW.findall(text)
        rows += [{"vendor_no": v, "date": d, "doc": doc, "amount": a.replace(",", ""), "invoice_ref": rest.strip(), "file": path.name}
                 for v, d, doc, _cheque, a, rest in found]
        print(f"  {path.name}: {len(found)} payments", flush=True)
    raw = pd.DataFrame(rows)
    # A duplicate repeats vendor, date, payment document, amount AND invoice reference. One payment document can
    # settle two invoices of the same value; those differ in the reference and are kept.
    raw = raw.drop_duplicates(subset=["vendor_no", "date", "doc", "amount", "invoice_ref"])
    df = pd.DataFrame({
        "event_id": "NSPCL-" + raw["doc"] + "-" + raw["vendor_no"] + "-" + raw.groupby(["doc", "vendor_no"]).cumcount().astype(str),
        "entity_id": "NSPCL-" + raw["vendor_no"],
        "amount": raw["amount"], "event_timestamp": pd.to_datetime(raw["date"], format="%d.%m.%Y", errors="coerce"),
    })
    finish(df, "nspcl", "INR", "vendor")


if __name__ == "__main__":
    main()
