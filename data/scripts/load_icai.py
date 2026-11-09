"""Vendor payment dataset from an ICAI book, on Kaggle: a synthetic Indian manufacturer's payments. Licence: CDLA-Permissive-1.0.

Source: https://www.kaggle.com/datasets/kmldas/vendor-payment-dataset-icai-book (dataset2_vendor_payments.csv).
Synthetic, so it is tagged is_synthetic and used for tests and the demo only, never for reported accuracy.
It has no anomaly labels: `vendor_risk_cluster` is a K-means output, not ground truth, and is not used as a label.
"""
import zipfile

import pandas as pd

from common import RAW, download, finish

URL = "https://www.kaggle.com/api/v1/datasets/download/kmldas/vendor-payment-dataset-icai-book"


def main() -> None:
    archive = download(URL, RAW / "icai" / "vendor-payment-dataset-icai-book.zip")
    with zipfile.ZipFile(archive) as z:
        raw = pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith("vendor_payments.csv"))), dtype=str)
    df = pd.DataFrame({
        "event_id": "ICAI-" + raw["payment_id"], "entity_id": "ICAI-" + raw["vendor_name"].str.strip().str.upper(),
        "counterparty_id": raw["approved_by"], "amount": raw["amount_inr"],
        "event_timestamp": pd.to_datetime(raw["payment_date"], errors="coerce"), "category": raw["gl_account_name"],
    })
    finish(df, "icai", "INR", "vendor", synthetic=True)


if __name__ == "__main__":
    main()
