"""Step 3e, pre-registered in nspcl_case_study.md: the top 50 full-v2 alerts on real NSPCL data, for human review.

    python experiments/nspcl_case_study.py      # writes nspcl_top50_for_review.csv with empty label columns
"""
import json

import pandas as pd

from v2_common import OUT, PROCESSED, early_mask, to_afed
from ml import pipeline
from ml.explain import build_facts

CONFIG = json.loads((OUT / "v2_config.json").read_text())


def main() -> None:
    real = to_afed(pd.read_parquet(PROCESSED / "nspcl.parquet"))  # no planting: every row is a real payment
    settings = CONFIG["full_v2_settings"]
    df = pipeline.run_pipeline(real, settings, evaluate_labels=False).scored
    late = ~early_mask(df)
    alerts = df[late & (df["level"] != "Low").to_numpy()].sort_values("risk", ascending=False).head(50)
    limit = float(pipeline.merged_settings(settings)["approval_limit"])
    rows = [{"event_id": r["event_id"], "vendor_id": r["vendor_id"], "invoice_date": f"{r['invoice_date']:%Y-%m-%d}",
             "amount": round(float(r["amount"]), 2), "risk": round(float(r["risk"]), 4), "tier": r["level"],
             "facts": " | ".join(f["text"] for f in build_facts(r, limit) if f["key"] != "model_rank"),
             "reviewer1_label": "", "reviewer2_label": "", "comment": ""} for r in alerts.to_dict("records")]
    pd.DataFrame(rows).to_csv(OUT / "nspcl_top50_for_review.csv", index=False)
    print(f"{len(rows)} alerts of {int((late & (df['level'] != 'Low').to_numpy()).sum())} in the latest 40% "
          f"({int(late.sum())} events); labels left empty for reviewers")


if __name__ == "__main__":
    main()
