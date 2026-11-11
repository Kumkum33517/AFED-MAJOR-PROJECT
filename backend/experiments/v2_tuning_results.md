# v2 tuning: results

Produced by `experiments/v2_tuning.py`, following `v2_tuning.md`. Tuning data only: planted seeds 1-3, synthetic seeds 42/7/123, earliest 60% of each run. F1 is the mean over a dataset's three seeds. Field-aware fusion, sequence features on. These are tuning scores, not results: they are optimistic by construction.

## P: per dataset

| Dataset | w1 | w2 | w3 | Medium | Tuning F1 | Default weights, 0.45 | Default weights, 2% budget |
|---|---|---|---|---|---|---|---|
| nspcl | 0.05 | 0.90 | 0.05 | 0.30 | 0.1495 | 0.0760 | 0.1059 |
| mplads | 0.45 | 0.50 | 0.05 | 0.86 | 0.1562 | 0.0353 | 0.0908 |
| chicago | 0.05 | 0.85 | 0.10 | 0.36 | 0.1025 | 0.0352 | 0.0544 |
| delaware | 0.05 | 0.90 | 0.05 | 0.37 | 0.1003 | 0.0324 | 0.0674 |
| afed_synthetic | 0.05 | 0.05 | 0.90 | 0.61 | 0.6314 | 0.4842 | 0.4613 |

## G and GB: one setting for all five datasets

| Setting | w1 | w2 | w3 | Cut-off or budget | Tuning mean F1 |
|---|---|---|---|---|---|
| G, fixed cut-off | 0.05 | 0.45 | 0.50 | Medium 0.40 | 0.1980 |
| GB, alert budget | 0.05 | 0.45 | 0.50 | 3.0% of events | 0.1751 |

GB tuning F1 per dataset: nspcl 0.1143, mplads 0.0663, chicago 0.0447, delaware 0.0545, afed_synthetic 0.5957.

**Full v2**, frozen in `v2_config.json`: field-aware fusion, sequence features, weights 0.05 / 0.45 / 0.50, alert budget 3.0% chosen on each run's earliest 60%.

Note: the plan states 153 weight sets. The grid it defines (each weight 0.05 to 0.90 in steps of 0.05, summing to 1) has 171, and all 171 were searched. The miscount was in the plan, not the search.
