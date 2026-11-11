# v2 evaluation: cumulative ablation and v1 against v2 (steps 3b and 3c, and 2d's reporting). Pre-registration

Written and committed on 11 Nov 2026 before `v2_evaluation.py` first ran, and before `v2_tuning.py` produced
`v2_config.json`. Results: `v2_evaluation_results.md` and `.json`.

## Data: reporting split only

- Main real ledgers: nspcl, mplads, chicago, delaware, anomalies planted with `ml/inject.py`, **seeds 4, 5, 6**.
- Synthetic: afed_synthetic, **seeds 11, 12, 13**.
- Extra rows, not used in tuning: bbmp_2024, bbmp_2010_2019, secop, ocds_assam (real, planted seeds 4-6) and
  icai (third-party synthetic, planted seeds 4-6).
- Only events from the 60th percentile of each run's dates onward are measured (the latest 40%). Calibration
  modes may look at the earliest 60% of the same run without labels (alert budget), as a deployment would.
- Settings come from `v2_config.json`, frozen by `v2_tuning.py`. Nothing is chosen on reporting data.

## Rows of the cumulative ablation (3b)

| Row | Forest features | Fusion | Weights | Medium cut-off |
|---|---|---|---|---|
| R0 v1 | v1 | v1 | 0.40 / 0.35 / 0.25 | 0.45 |
| R1 + field-aware fusion | v1 | field-aware | default | 0.45 |
| R2 + alert budget | v1 | field-aware | default | alert budget 2% (the app default), earliest 60% |
| R3 + sequence features | + sequence | field-aware | default | alert budget 2% |
| R4 + weight search (P) | + sequence | field-aware | P, per dataset | P, per dataset (main datasets only; needs labels) |
| R5 full v2 | + sequence | field-aware | GB | alert budget at the GB rate |

Measures per row and dataset, mean ± sd over seeds: F1, recall, precision, PR-AUC, ROC-AUC, alerts. ROC-AUC and
PR-AUC depend on the ranking only, so a cut-off change alone does not move them.

2d's reporting: P, G and GB side by side on the main datasets and synthetic, to see whether per-dataset tuning
carries over to new seeds and the later period better than one global setting.

## Headline (3c)

R0 against R5 for every dataset: F1, recall, precision, ROC-AUC and alerts with seed sd, and recall by planted
type. A check that R5 computed here matches a pipeline run with the same settings is reported (one dataset, one
seed, exact match of risk and levels).

## Decision rule for making v2 the default

v2 (R5) becomes the default **only if**, on the reporting data, its mean F1 is higher than v1's (R0) on at least 3
of the 4 main real ledgers (nspcl, mplads, chicago, delaware) **and** its mean recall on afed_synthetic is no more
than 0.03 below v1's. Otherwise v1 stays the default and v2 stays available as an option, and the results say so.
