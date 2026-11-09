# Per-dataset alert threshold on a held-out period: results

Produced by `experiments/threshold_calibration.py`, following `threshold_calibration.md` (SHA-256 b848a5a5b9010011). Test period: the latest 40% of each dataset by date. Real rows are treated as normal, so precision on real data is a lower bound.

| Dataset | Threshold chosen | F1 default (0.45) | F1 calibrated | Recall default | Recall calibrated | Balanced accuracy default | Balanced accuracy calibrated | Alerts default | Alerts calibrated |
|---|---|---|---|---|---|---|---|---|---|
| afed_synthetic | 0.51, 0.52, 0.50 | 0.548 ± 0.007 | 0.578 ± 0.023 | 0.889 ± 0.019 | 0.757 ± 0.058 | 0.923 ± 0.009 | 0.865 ± 0.027 | 293 | 210 |
| nspcl | 0.60, 0.60, 0.48 | 0.047 ± 0.001 | 0.047 ± 0.003 | 0.125 ± 0.003 | 0.076 ± 0.033 | 0.519 ± 0.002 | 0.517 ± 0.005 | 1,536 | 764 |
| mplads | 0.68, 0.66, 0.65 | 0.023 ± 0.003 | 0.105 ± 0.012 | 0.241 ± 0.029 | 0.131 ± 0.025 | 0.563 ± 0.015 | 0.561 ± 0.012 | 3,915 | 294 |
| chicago | 0.65, 0.63, 0.65 | 0.017 ± 0.002 | 0.039 ± 0.005 | 0.088 ± 0.011 | 0.029 ± 0.006 | 0.489 ± 0.005 | 0.512 ± 0.002 | 5,443 | 273 |
| delaware | 0.63, 0.63, 0.63 | 0.024 ± 0.001 | 0.058 ± 0.001 | 0.111 ± 0.005 | 0.046 ± 0.002 | 0.509 ± 0.003 | 0.520 ± 0.001 | 13,563 | 953 |

## Decision rule

Mean test F1 higher with calibration on 4 of 4 real datasets (nspcl, mplads, chicago, delaware); largest loss 0.000. Needed: at least 3, and no loss beyond 0.01. **PASS.**

F1 change per dataset (calibrated minus default): afed_synthetic +0.031, nspcl +0.000, mplads +0.081, chicago +0.022, delaware +0.034.
