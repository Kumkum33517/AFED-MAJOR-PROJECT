# LSTM errors in the forest, re-tested on fresh data: results

Produced by `experiments/lstm_retest.py`, following `lstm_retest.md`. Reporting data: planted seeds 4-6, synthetic seeds 11/12/13, latest 40% of each run. v1 fusion, default weights, cut-off 0.45. Mean ± sd over seeds. Evidence only: no default changes.

## The pre-registered rule (with against without)

| Dataset | Recall with | Recall without | Alerts with | Alerts without | Seeds with higher recall | Verdict |
|---|---|---|---|---|---|---|
| nspcl | 0.121 ± 0.011 | 0.100 ± 0.004 | 1554 ± 28 | 1548 ± 9 | 3 of 3 | FAIL |
| mplads | 0.285 ± 0.059 | 0.303 ± 0.037 | 3973 ± 92 | 4370 ± 50 | 0 of 3 | FAIL |
| chicago | 0.080 ± 0.013 | 0.066 ± 0.013 | 5456 ± 93 | 5923 ± 32 | 3 of 3 | PASS |
| delaware | 0.099 ± 0.009 | 0.078 ± 0.009 | 14150 ± 187 | 16394 ± 409 | 3 of 3 | PASS |
| afed_synthetic | 0.894 ± 0.012 | 0.949 ± 0.024 | 286 ± 20 | 280 ± 19 | 0 of 3 | FAIL |

## All four arms

### recall

| Dataset | with | without | lstm60 | ewma |
|---|---|---|---|---|
| nspcl | 0.121 ± 0.011 | 0.100 ± 0.004 | 0.126 ± 0.005 | 0.119 ± 0.012 |
| mplads | 0.285 ± 0.059 | 0.303 ± 0.037 | 0.293 ± 0.062 | 0.290 ± 0.057 |
| chicago | 0.080 ± 0.013 | 0.066 ± 0.013 | 0.084 ± 0.013 | 0.078 ± 0.013 |
| delaware | 0.099 ± 0.009 | 0.078 ± 0.009 | 0.103 ± 0.011 | 0.102 ± 0.009 |
| afed_synthetic | 0.894 ± 0.012 | 0.949 ± 0.024 | 0.897 ± 0.003 | 0.892 ± 0.015 |

### alerts

| Dataset | with | without | lstm60 | ewma |
|---|---|---|---|---|
| nspcl | 1554 ± 28 | 1548 ± 9 | 1585 ± 41 | 1552 ± 35 |
| mplads | 3973 ± 92 | 4370 ± 50 | 3981 ± 76 | 3900 ± 59 |
| chicago | 5456 ± 93 | 5923 ± 32 | 5434 ± 101 | 5570 ± 65 |
| delaware | 14150 ± 187 | 16394 ± 409 | 13876 ± 138 | 14286 ± 296 |
| afed_synthetic | 286 ± 20 | 280 ± 19 | 286 ± 18 | 283 ± 19 |

### f1

| Dataset | with | without | lstm60 | ewma |
|---|---|---|---|---|
| nspcl | 0.044 ± 0.003 | 0.037 ± 0.001 | 0.045 ± 0.001 | 0.043 ± 0.004 |
| mplads | 0.026 ± 0.005 | 0.025 ± 0.002 | 0.027 ± 0.005 | 0.027 ± 0.004 |
| chicago | 0.015 ± 0.004 | 0.011 ± 0.003 | 0.016 ± 0.004 | 0.014 ± 0.004 |
| delaware | 0.020 ± 0.002 | 0.013 ± 0.001 | 0.021 ± 0.002 | 0.020 ± 0.002 |
| afed_synthetic | 0.536 ± 0.032 | 0.579 ± 0.046 | 0.539 ± 0.036 | 0.540 ± 0.026 |

### precision

| Dataset | with | without | lstm60 | ewma |
|---|---|---|---|---|
| nspcl | 0.027 ± 0.002 | 0.022 ± 0.001 | 0.027 ± 0.001 | 0.026 ± 0.003 |
| mplads | 0.014 ± 0.002 | 0.013 ± 0.001 | 0.014 ± 0.002 | 0.014 ± 0.002 |
| chicago | 0.008 ± 0.002 | 0.006 ± 0.002 | 0.009 ± 0.002 | 0.008 ± 0.002 |
| delaware | 0.011 ± 0.001 | 0.007 ± 0.001 | 0.012 ± 0.001 | 0.011 ± 0.001 |
| afed_synthetic | 0.384 ± 0.035 | 0.418 ± 0.047 | 0.386 ± 0.036 | 0.388 ± 0.030 |

### pr_auc

| Dataset | with | without | lstm60 | ewma |
|---|---|---|---|---|
| nspcl | 0.024 ± 0.002 | 0.022 ± 0.001 | 0.024 ± 0.002 | 0.024 ± 0.002 |
| mplads | 0.026 ± 0.007 | 0.020 ± 0.005 | 0.027 ± 0.008 | 0.029 ± 0.008 |
| chicago | 0.013 ± 0.003 | 0.011 ± 0.002 | 0.013 ± 0.003 | 0.013 ± 0.003 |
| delaware | 0.013 ± 0.002 | 0.010 ± 0.000 | 0.013 ± 0.001 | 0.013 ± 0.001 |
| afed_synthetic | 0.638 ± 0.055 | 0.655 ± 0.063 | 0.638 ± 0.054 | 0.639 ± 0.056 |

Arms: with = LSTM trained on all events (v1); without = no temporal errors in the forest; lstm60 = LSTM trained on the earliest 60% only; ewma = EWMA forecaster errors instead of the LSTM's. A 20-invoice window was not tried.
