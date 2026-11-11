# NSPCL case study: top 50 v2 alerts for human review (step 3e). Pre-registration

Written and committed on 11 Nov 2026 before `nspcl_case_study.py` first ran. Output:
`nspcl_top50_for_review.csv`.

## What is exported

The real NSPCL ledger with **no planted anomalies**, scored with full v2 (`v2_config.json`). From the latest 40% of
events by date, the 50 alerts with the highest risk, with: event id, vendor, date, amount, risk, tier, the fact
sentences, and empty columns `reviewer1_label`, `reviewer2_label` (reasonable / doubtful / benign) and `comment`.

## What is not done

The labels are left empty. They are for people to fill in. No result is claimed from this file until two reviewers
have labelled it.
