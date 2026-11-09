"""Play the part of an accounting system: post invoices to AFED in batches, on a timer.

    python scripts/send_events.py --file ../frontend/public/samples/nspcl_sample.csv --batch 500 --every 20

Each batch goes to POST /upload/events, which validates it and starts a run, exactly as an ERP export job
would. Alerts and notifications then appear in the app without anyone uploading a file. The account must be
an Admin or Analyst; the password is read from AFED_PASSWORD or asked for in the terminal.
"""
import argparse
import getpass
import math
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

FIELDS = ["event_id", "vendor_id", "amount", "invoice_date", "invoice_number", "vendor_name", "category", "department",
          "approver_id", "created_by", "approval_date", "processing_days", "bank_account", "vendor_created", "po_amount",
          "is_anomaly", "anomaly_type"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--email", default="analyst@afed.app")
    parser.add_argument("--file", type=Path, default=Path(__file__).resolve().parents[2] / "frontend/public/samples/nspcl_sample.csv")
    parser.add_argument("--batch", type=int, default=500, help="invoices per batch")
    parser.add_argument("--every", type=float, default=20, help="seconds between batches")
    parser.add_argument("--source", default="Accounting system feed")
    args = parser.parse_args()

    password = os.getenv("AFED_PASSWORD") or getpass.getpass(f"Password for {args.email}: ")
    login = requests.post(f"{args.api}/auth/login", data={"username": args.email, "password": password}, timeout=30)
    if login.status_code != 200:
        sys.exit(f"Login failed: {login.status_code} {login.text[:200]}")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    frame = pd.read_csv(args.file, dtype=str, keep_default_na=False)
    frame = frame[[c for c in frame.columns if c in FIELDS]].sort_values("invoice_date", kind="stable")
    batches = math.ceil(len(frame) / args.batch)
    print(f"{len(frame):,} invoices from {args.file.name}, in {batches} batches of {args.batch}, every {args.every:g} s")
    for number in range(batches):
        part = frame.iloc[number * args.batch:(number + 1) * args.batch]
        events = [{k: (v if v != "" else None) for k, v in row.items()} for row in part.to_dict("records")]
        while True:
            reply = requests.post(f"{args.api}/upload/events", json={"source": args.source, "events": events}, headers=headers, timeout=120)
            if reply.status_code != 409:  # 409: a run is still going, so wait and send again
                break
            time.sleep(5)
        if reply.status_code != 202:
            sys.exit(f"Batch {number + 1} rejected: {reply.status_code} {reply.text[:300]}")
        print(f"batch {number + 1}/{batches}: {len(events)} invoices, run {reply.json()['run_id']} started", flush=True)
        if number + 1 < batches:
            time.sleep(args.every)
    print("done")


if __name__ == "__main__":
    main()
