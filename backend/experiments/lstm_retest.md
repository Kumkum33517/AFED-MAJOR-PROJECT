# LSTM errors in the forest, re-tested on fresh data, with an EWMA baseline (steps 2e and 3d). Pre-registration

Written and committed on 11 Nov 2026 before `lstm_retest.py` first ran. Results: `lstm_retest_results.md`, `.json`.

## Context

The user decided on 10 Nov 2026 to keep the LSTM's errors in the forest, and the supervisor requires the
LSTM → Isolation Forest → Qwen pipeline. This test produces evidence only; it changes no default whatever it shows.

## Data

nspcl, mplads, chicago, delaware (planted seeds 4, 5, 6) and afed_synthetic (seeds 11, 12, 13). Measured on the
latest 40% of each run by date. v1 fusion, default weights, Medium cut-off 0.45.

## Arms

| Arm | Temporal errors fed to the forest |
|---|---|
| with | LSTM trained on all events of the run (v1 default) |
| without | none (`lstm.in_forest = false`) |
| lstm60 | LSTM trained only on the earliest 60% of events (`lstm.fit_share = 0.6`), every event scored |
| ewma | an EWMA forecaster of the same three z-scores instead of the LSTM (`temporal_source = "ewma"`) |

## Rule (the same as before)

For each dataset, the LSTM's errors pass if, comparing `with` against `without`: mean recall is higher, mean alerts
are no higher, and recall is higher on at least 2 of the 3 seeds. Each dataset gets PASS or FAIL.

`lstm60` and `ewma` are reported against `with` and `without` (recall, alerts, F1, PR-AUC) with no rule. A window of
20 invoices is not tried in this session.
