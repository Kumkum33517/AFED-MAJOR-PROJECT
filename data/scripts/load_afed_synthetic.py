"""AFED's own generated data, both labelled, both synthetic. Committed? Not needed: the generators are, and are seeded.

  afed_synthetic : backend/data/generate_synthetic.py, seed 42. Point anomalies of 10 types, 2.5%.
  afed_temporal  : backend/data/generate_temporal.py, seed 1. Temporal anomalies of 3 types, 2.5%.
Labels and anomaly types come from the generators. is_synthetic is true on every row.
"""
import sys
from pathlib import Path

import pandas as pd

from common import finish

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "data"))
import generate_synthetic  # noqa: E402
import generate_temporal  # noqa: E402


def convert(raw: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "event_id": raw["event_id"], "entity_id": raw["vendor_id"], "counterparty_id": raw["department"],
        "amount": raw["amount"], "event_timestamp": raw["invoice_date"], "processing_time_days": raw["processing_days"],
        "category": raw["category"], "label": raw["is_anomaly"], "anomaly_type": raw["anomaly_type"].replace("", None),
    })


def main() -> None:
    finish(convert(generate_synthetic.generate(42)), "afed_synthetic", "INR", "vendor", synthetic=True)
    finish(convert(generate_temporal.generate(1)), "afed_temporal", "INR", "vendor", synthetic=True)


if __name__ == "__main__":
    main()
