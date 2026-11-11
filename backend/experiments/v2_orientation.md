# v2 orientation: the state of AFED before any v2 change

Written on 11 Nov 2026, before any code change for v2, from the code at commit `a3384a0` and the result files in
this folder. Planted shares were measured on 11 Nov 2026 with `ml/inject.py`, seed 1.

## Current defaults (v1)

| Part | Setting | Value | Where |
|---|---|---|---|
| Baselines | Vendor window / peer window | 500 / 5,000 invoices | `ml/features.py` |
| | Minimum vendor history before peer fallback | 8 invoices | `ml/features.py` (`MIN_HISTORY`) |
| | Normal band for the entity deviation | 2 robust sigmas, one-sided | `ml/pipeline.py` (`NORMAL_BAND`) |
| LSTM | Mode, window | forecast, 10 invoices | `DEFAULT_SETTINGS["lstm"]` |
| | Layers, hidden size | 2, 32 | `ml/lstm_seq.py` |
| | Epochs, optimiser, learning rate | 12, Adam, 0.003 | `ml/lstm_seq.py` |
| | Training data | every event of the run (no labels) | `ml/lstm_seq.py` |
| | Errors fed to the forest | yes (`in_forest = true`), kept by the user's decision of 10 Nov 2026 | `DEFAULT_SETTINGS["lstm"]` |
| Isolation Forest | Trees, contamination, seed | 200, `"auto"`, 42 | `ml/pipeline.py` |
| Fusion | Weights w1 (A), w2 (D), w3 (F) | 0.40, 0.35, 0.25 | `DEFAULT_SETTINGS["weights"]` |
| | Synergy bonus | 0.10 · min(D, F) | `ml/fusion.py` |
| | A, D, F | percentile³; 1 − exp(−deviation/3); noisy-OR of rule severities | `ml/fusion.py` |
| Tiers | Medium, High, Critical cut-offs | 0.45, 0.60, 0.75 | `DEFAULT_SETTINGS["thresholds"]` |
| Rules | Approval limit; all 10 rules on | Rs. 5,00,000 | `DEFAULT_SETTINGS` |
| Narration | Provider | template | `DEFAULT_SETTINGS` |

## Experiments and the data each used

| Experiment | Datasets | Seeds |
|---|---|---|
| `temporal_ablation` | afed_temporal (decides), afed_synthetic (reference) | temporal 1-5; synthetic 42, 7, 123 |
| `real_data_evaluation` | nspcl, mplads, bbmp_2024, bbmp_2010_2019, chicago, secop, delaware (cppp listed but dropped) | planted 1, 2, 3 |
| `model_comparison` | afed_synthetic; afed_temporal; nspcl, mplads, chicago, delaware | 42, 7, 123; 1, 2, 3; planted 1, 2, 3 |
| `threshold_calibration` | afed_synthetic; nspcl, mplads, chicago, delaware | 42, 7, 123; planted 1, 2, 3 |
| `narration_evaluation` | the 717 demo alerts (synthetic seed 42) | alerts shuffled with seed 1: 30 development, next 100 test |

So every seed used so far is 1-5 (planted and temporal) or 42, 7, 123 (synthetic). Under the v2 protocol these are
tuning seeds; the reporting seeds 4-6 (planted) and 11, 12, 13 (synthetic) are new. Planted seeds 4 and 5 were used
before only for the *temporal* generator, not for planting, so planted seeds 4-6 are unused.

## Which of the 12 datasets were evaluated

Evaluated: nspcl, mplads, bbmp_2024, bbmp_2010_2019, chicago, secop, delaware (real); afed_synthetic,
afed_temporal (ours). **Confirmed never evaluated: ocds_hp, ocds_assam, icai.** Whether they can take the planting
protocol (one episode per entity with 24+ events, target 2.5% of events):

| Dataset | Events | Entities | With 24+ events | Planted (seed 1) | Decision |
|---|---|---|---|---|---|
| ocds_hp | 4,085 | 34 | 9 | 12 (0.29%) | **Skip**: too few entities to plant a usable number of anomalies |
| ocds_assam | 6,595 | 80 | 29 | 53 (0.80%) | **Add as an extra row.** Entities are buying departments, not vendors |
| icai | 10,951 | 598 | 180 | 273 (2.46%) | **Add as an extra row**, labelled third-party synthetic |

## A correction found while orienting

Earlier documents say planting reaches "about 2.5% of events". It does only where enough vendors have 24+ events,
because each vendor gets one episode. Measured with seed 1: secop 2.47%, nspcl 1.90%, chicago 1.11%, delaware 1.01%,
bbmp_2024 0.81%, bbmp_2010_2019 0.62%, mplads 0.52%. Results stay valid (precision and recall are measured on what
was planted), but the share should be stated per dataset, and the lower shares make precision harder to reach.

## Protocol for v2 (from the brief)

- Tune only on planted seeds 1-3, synthetic seeds 42/7/123, and the earliest 60% of each dataset by date.
- Report only on planted seeds 4-6, synthetic seeds 11/12/13, and the latest 40% of each dataset by date.
- Every new behaviour sits behind a setting that is off by default; with all of them off, output equals v1.
