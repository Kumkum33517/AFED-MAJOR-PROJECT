# AFED on real data with injected anomalies: results

Produced by `experiments/real_data_evaluation.py`, following `real_data_evaluation.md`. Real rows are treated as normal, so precision is a lower bound. Anomalies are injected, not real fraud.

## Summary, AFED with the brief's default (LSTM errors in the forest)

| Dataset | Events | Recall | Precision | F1 | ROC-AUC | Avg precision | Alerts | Fewer reviews than global IF | ms per event |
|---|---|---|---|---|---|---|---|---|---|
| nspcl | 44,024 | 0.136 ± 0.009 | 0.037 ± 0.002 | 0.058 ± 0.004 | 0.582 ± 0.002 | 0.028 ± 0.000 | 3133 ± 26 | 0.616 ± 0.046 | 0.38 |
| mplads | 83,259 | 0.262 ± 0.003 | 0.013 ± 0.001 | 0.024 ± 0.001 | 0.633 ± 0.005 | 0.020 ± 0.002 | 9326 ± 114 | 0.243 ± 0.017 | 0.49 |
| bbmp_2024 | 8,136 | 0.295 ± 0.033 | 0.026 ± 0.006 | 0.048 ± 0.010 | 0.794 ± 0.016 | 0.031 ± 0.013 | 644 ± 18 | 0.641 ± 0.058 | 0.48 |
| bbmp_2010_2019 | 33,174 | 0.190 ± 0.008 | 0.013 ± 0.001 | 0.025 ± 0.001 | 0.555 ± 0.007 | 0.022 ± 0.003 | 3142 ± 51 | 0.210 ± 0.081 | 0.37 |
| chicago | 124,151 | 0.095 ± 0.001 | 0.011 ± 0.000 | 0.020 ± 0.001 | 0.509 ± 0.007 | 0.015 ± 0.001 | 11275 ± 69 | -1.022 ± 0.182 | 0.30 |
| secop | 274,794 | 0.088 ± 0.002 | 0.028 ± 0.001 | 0.043 ± 0.001 | 0.498 ± 0.004 | 0.026 ± 0.000 | 21159 ± 61 | 0.047 ± 0.032 | 0.31 |
| delaware | 363,435 | 0.120 ± 0.002 | 0.014 ± 0.000 | 0.025 ± 0.000 | 0.516 ± 0.007 | 0.015 ± 0.000 | 31622 ± 266 | -1.187 ± 0.034 | 0.33 |

## Recall by injected type, with LSTM errors

| Dataset | amount_spike | slow_drift | frequency_shift | off_cycle_invoice |
|---|---|---|---|---|
| nspcl | 0.358 ± 0.020 | 0.089 ± 0.024 | 0.039 ± 0.015 | 0.059 ± 0.029 |
| mplads | 0.794 ± 0.056 | 0.115 ± 0.014 | 0.070 ± 0.045 | 0.073 ± 0.026 |
| bbmp_2024 | 0.644 ± 0.134 | 0.235 ± 0.157 | 0.116 ± 0.115 | 0.183 ± 0.104 |
| bbmp_2010_2019 | 0.637 ± 0.030 | 0.040 ± 0.014 | 0.048 ± 0.053 | 0.050 ± 0.014 |
| chicago | 0.247 ± 0.007 | 0.047 ± 0.010 | 0.043 ± 0.012 | 0.045 ± 0.010 |
| secop | 0.209 ± 0.014 | 0.057 ± 0.008 | 0.045 ± 0.003 | 0.041 ± 0.002 |
| delaware | 0.338 ± 0.011 | 0.062 ± 0.006 | 0.038 ± 0.011 | 0.042 ± 0.003 |

## LSTM errors in the forest: the pre-registered rule, per dataset

| Dataset | Recall with | Recall without | Alerts with | Alerts without | Seeds with higher recall | Verdict |
|---|---|---|---|---|---|---|
| nspcl | 0.136 ± 0.009 | 0.115 ± 0.004 | 3133 ± 26 | 3179 ± 133 | 3 of 3 | PASS |
| mplads | 0.262 ± 0.003 | 0.270 ± 0.020 | 9326 ± 114 | 9955 ± 26 | 1 of 3 | FAIL |
| bbmp_2024 | 0.295 ± 0.033 | 0.274 ± 0.017 | 644 ± 18 | 740 ± 6 | 2 of 3 | PASS |
| bbmp_2010_2019 | 0.190 ± 0.008 | 0.156 ± 0.013 | 3142 ± 51 | 3684 ± 36 | 3 of 3 | PASS |
| chicago | 0.095 ± 0.001 | 0.081 ± 0.005 | 11275 ± 69 | 12616 ± 348 | 3 of 3 | PASS |
| secop | 0.088 ± 0.002 | 0.069 ± 0.002 | 21159 ± 61 | 19366 ± 355 | 3 of 3 | FAIL |
| delaware | 0.120 ± 0.002 | 0.096 ± 0.005 | 31622 ± 266 | 37865 ± 451 | 3 of 3 | PASS |
