# v2 tuning: fusion weights, cut-offs and the alert budget (step 2d). Pre-registration

Written and committed on 11 Nov 2026 before `v2_tuning.py` first ran. Results: `v2_tuning_results.md`, and the
frozen configuration `v2_config.json`, which every reporting experiment reads and none may change.

## Data: tuning split only

- Datasets: nspcl, mplads, chicago, delaware (anomalies planted by `ml/inject.py`, seeds 1, 2, 3) and
  afed_synthetic (seeds 42, 7, 123).
- Only events before the 60th percentile of each run's dates are used to choose anything.
- The extra datasets (bbmp_2024, bbmp_2010_2019, secop, ocds_assam, icai) take no part in tuning: they test whether
  the result carries over.
- Scores come from runs with `sequence_features = true` (arm `seq`). Risk is computed with field-aware fusion
  (`ml/fusion.py: risk_score` with each run's rule share), so the search tunes the v2 fusion itself.

## Searches

- Weight grid: w1, w2, w3 in 0.05, 0.10, ..., 0.90 with w1 + w2 + w3 = 1 (153 sets).
- Cut-off grid: 0.30, 0.31, ..., 0.90. Alert-budget grid: 0.5%, 1%, 1.5%, 2%, 3%, 5% of events.
- Objective: F1 on tuning-period events, averaged over a dataset's three seeds. Across datasets: the mean of the
  five per-dataset means. Ties: the higher cut-off or lower budget, then the first weight set in grid order.

| Name | What is chosen | Can a real deployment use it? |
|---|---|---|
| P, per dataset | weights and Medium cut-off, separately for each dataset | No: needs labels on that dataset |
| G, global fixed | one weight set and one Medium cut-off for all five datasets | Yes, once fixed |
| GB, global budget | one weight set and one alert budget for all; each run's cut-off then comes from its own earliest 60% | Yes |

## Frozen output

`v2_config.json`: the P, G and GB choices with their tuning F1. **Full v2** is defined now, before any reporting
result: field-aware fusion on, sequence features on, the GB weights, and alert-budget calibration at the GB budget
(chosen on each run's earliest 60% of events). The default target of 2% in the app is not changed by this step.
