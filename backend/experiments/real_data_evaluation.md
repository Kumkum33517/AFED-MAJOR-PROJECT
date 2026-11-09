# AFED on real procurement data with injected anomalies: pre-registration

Written and fingerprinted on 9 Nov 2026, before any model ran on these datasets. Results go to
`real_data_evaluation_results.md`, so this file stays as it was when frozen.

## Question

How well does AFED detect anomalies planted in real vendor histories, and does feeding the LSTM's errors
to the Isolation Forest help on real data? This adds evidence to the temporal ablation in
`temporal_ablation.md`; the decision about the LSTM remains the supervisor's.

## Data

Real, unlabelled datasets from `data/processed/`, each loaded by its script in `data/scripts/`:
nspcl, mplads, bbmp_2024, bbmp_2010_2019, delaware, secop, chicago, and cppp if its download completes.
The open-contracting sets (ocds_hp, ocds_assam) are left out: too few entities with long histories.
Synthetic sets are left out: they are reported elsewhere.

## Injection (`backend/ml/inject.py`)

About 2.5% of events, split evenly across four types, at most one episode per vendor, only in vendors with
24 or more events: amount_spike (5-11x), slow_drift (6-8 invoices compounding 6-10%), frequency_shift (five
extra mid-gap invoices in a row), off_cycle_invoice (three extra mid-gap invoices spread out). Seeds 1, 2, 3.
Every real row is treated as normal, so any real anomaly counts as a false alarm and precision is a lower bound.

## Arms and measures

Whole AFED pipeline, default settings, as in the temporal ablation: with the LSTM's errors in the forest, and
without. Per dataset, arm and seed: recall, alerts, false alarms, precision, F1, ROC-AUC, average precision,
recall by type, time per event. Reported as mean ± sd over the three seeds.

## Decision rule, applied per dataset as evidence

The same three conditions as before: mean recall higher with the LSTM errors, mean alerts no higher, and recall
higher on at least 2 of the 3 seeds (a majority, as 3 of 5 was before). Each dataset gets PASS or FAIL. All
results are reported, whatever they show, and nothing is tuned after seeing them.
