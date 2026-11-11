# Why is AFED's ranking weak on real ledgers? Results

Produced by `experiments/diagnostics.py`, following `diagnostics.md`. AFED v1, default settings. Planted seeds 1-3; only events before the 60th percentile of each run's dates (the tuning period). Mean ± sd over seeds.

## 1. Detection at the default cut-off (0.45)

| Dataset | Events | Planted | Precision | Recall | Recall amount_spike | Recall slow_drift | Recall frequency_shift | Recall off_cycle_invoice |
|---|---|---|---|---|---|---|---|---|
| nspcl | 26,390 | 492 | 0.044 ± 0.005 | 0.144 ± 0.017 | 0.368 ± 0.037 | 0.079 ± 0.011 | 0.034 ± 0.030 | 0.071 ± 0.030 |
| mplads | 49,792 | 244 | 0.013 ± 0.001 | 0.280 ± 0.018 | 0.798 ± 0.072 | 0.122 ± 0.084 | 0.059 ± 0.050 | 0.072 ± 0.054 |
| bbmp_2024 | 4,728 | 18 | 0.023 ± 0.013 | 0.427 ± 0.258 | 0.657 ± 0.249 | 0.000 ± 0.000 | 0.278 ± 0.255 | 0.367 ± 0.153 |
| bbmp_2010_2019 | 19,901 | 119 | 0.013 ± 0.001 | 0.196 ± 0.039 | 0.621 ± 0.048 | 0.017 ± 0.029 | 0.068 ± 0.069 | 0.039 ± 0.040 |
| chicago | 74,185 | 758 | 0.013 ± 0.001 | 0.101 ± 0.007 | 0.246 ± 0.031 | 0.044 ± 0.012 | 0.042 ± 0.011 | 0.042 ± 0.020 |
| secop | 164,769 | 3,621 | 0.028 ± 0.002 | 0.097 ± 0.005 | 0.214 ± 0.017 | 0.063 ± 0.007 | 0.038 ± 0.002 | 0.043 ± 0.006 |
| delaware | 218,011 | 2,030 | 0.014 ± 0.000 | 0.127 ± 0.001 | 0.347 ± 0.009 | 0.049 ± 0.011 | 0.038 ± 0.007 | 0.039 ± 0.002 |
| ocds_assam | 3,969 | 20 | 0.008 ± 0.005 | 0.136 ± 0.052 | 0.270 ± 0.200 | 0.000 ± 0.000 | 0.067 ± 0.115 | 0.125 ± 0.177 |
| icai | 6,636 | 139 | 0.083 ± 0.003 | 0.303 ± 0.015 | 0.731 ± 0.056 | 0.120 ± 0.072 | 0.098 ± 0.056 | 0.047 ± 0.044 |

Share of true positives by planted type (a false alarm has no type, so precision is overall only):

| Dataset | amount_spike | slow_drift | frequency_shift | off_cycle_invoice |
|---|---|---|---|---|
| nspcl | 0.69 ± 0.05 | 0.15 ± 0.04 | 0.05 ± 0.04 | 0.11 ± 0.05 |
| mplads | 0.78 ± 0.04 | 0.10 ± 0.07 | 0.05 ± 0.04 | 0.07 ± 0.06 |
| bbmp_2024 | 0.70 ± 0.18 | 0.00 ± 0.00 | 0.08 ± 0.08 | 0.22 ± 0.13 |
| bbmp_2010_2019 | 0.84 ± 0.09 | 0.03 ± 0.05 | 0.08 ± 0.07 | 0.04 ± 0.04 |
| chicago | 0.70 ± 0.02 | 0.10 ± 0.04 | 0.11 ± 0.03 | 0.09 ± 0.04 |
| secop | 0.65 ± 0.02 | 0.15 ± 0.01 | 0.10 ± 0.01 | 0.10 ± 0.01 |
| delaware | 0.76 ± 0.03 | 0.10 ± 0.02 | 0.07 ± 0.01 | 0.07 ± 0.01 |
| ocds_assam | 0.71 ± 0.34 | 0.00 ± 0.00 | 0.22 ± 0.38 | 0.07 ± 0.12 |
| icai | 0.81 ± 0.06 | 0.07 ± 0.04 | 0.08 ± 0.05 | 0.04 ± 0.04 |

## 2. Vendor history and baselines

| Dataset | Prior events: median (Q1-Q3) | Under 8 prior | Under 24 prior | Vendor baseline | Peer | Population |
|---|---|---|---|---|---|---|
| nspcl | 9 (2-31) | 0.460 ± 0.000 | 0.696 ± 0.000 | 0.540 ± 0.000 | 0.000 ± 0.000 | 0.460 ± 0.000 |
| mplads | 3 (0-23) | 0.608 ± 0.000 | 0.750 ± 0.000 | 0.392 ± 0.000 | 0.595 ± 0.000 | 0.013 ± 0.000 |
| bbmp_2024 | 2 (0-6) | 0.801 ± 0.000 | 0.935 ± 0.000 | 0.199 ± 0.000 | 0.000 ± 0.000 | 0.801 ± 0.000 |
| bbmp_2010_2019 | 10 (2-80) | 0.454 ± 0.000 | 0.616 ± 0.000 | 0.546 ± 0.000 | 0.000 ± 0.000 | 0.454 ± 0.000 |
| chicago | 64 (19-192) | 0.130 ± 0.000 | 0.284 ± 0.000 | 0.870 ± 0.000 | 0.096 ± 0.000 | 0.034 ± 0.000 |
| secop | 20 (9-45) | 0.215 ± 0.000 | 0.557 ± 0.000 | 0.785 ± 0.000 | 0.214 ± 0.000 | 0.001 ± 0.000 |
| delaware | 149 (40-475) | 0.062 ± 0.000 | 0.170 ± 0.000 | 0.938 ± 0.000 | 0.056 ± 0.000 | 0.006 ± 0.000 |
| ocds_assam | 90 (31-224) | 0.096 ± 0.000 | 0.208 ± 0.000 | 0.904 ± 0.000 | 0.000 ± 0.000 | 0.096 ± 0.000 |
| icai | 6 (3-12) | 0.571 ± 0.000 | 0.981 ± 0.000 | 0.429 ± 0.000 | 0.561 ± 0.000 | 0.010 ± 0.000 |

## 3. Which rules can fire, and how often they fire

`can fire` means the dataset has every input the rule needs. Values are the share of tuning-period events flagged.

| Dataset | Duplicate invoice | Invoice splitting | Segregation of duties | Bank account change | New vendor, large payment | Invoice burst | Off-hours approval | Rushed approval | Round amount | Near approval limit |
|---|---|---|---|---|---|---|---|---|---|---|
| nspcl | 0.0214 | 0.0002 | no input | no input | no input | 0.0734 | no input | no input | 0.0172 | 0.0206 |
| mplads | 0.3765 | 0.0168 | no input | no input | no input | 0.1697 | no input | no input | 0.2163 | 0.0641 |
| bbmp_2024 | 0.0493 | 0.0042 | no input | no input | no input | 0.0831 | no input | 0.0008 | 0.0061 | 0.0192 |
| bbmp_2010_2019 | 0.2998 | 0.0134 | no input | no input | no input | 0.3458 | no input | no input | 0.0076 | 0.0340 |
| chicago | 0.0959 | 0.0031 | no input | no input | no input | 0.1892 | no input | no input | 0.0016 | 0.0230 |
| secop | 0.0172 | 0.0000 | no input | no input | no input | 0.1481 | no input | 0.1626 | 0.0014 | 0.0164 |
| delaware | 0.1276 | 0.0005 | no input | no input | no input | 0.2033 | no input | no input | 0.0003 | 0.0127 |
| ocds_assam | 0.1439 | 0.0000 | no input | no input | no input | 0.4121 | no input | no input | 0.0593 | 0.0043 |
| icai | 0.0311 | 0.0000 | no input | no input | no input | 0.0728 | no input | no input | 0.0115 | 0.0011 |

## 4. Each component alone

| Dataset | ROC-AUC A | ROC-AUC D | ROC-AUC F | ROC-AUC fusion | PR-AUC A | PR-AUC D | PR-AUC F | PR-AUC fusion |
|---|---|---|---|---|---|---|---|---|
| nspcl | 0.598 ± 0.007 | 0.640 ± 0.005 | 0.501 ± 0.004 | 0.618 ± 0.006 | 0.024 ± 0.000 | 0.066 ± 0.004 | 0.019 ± 0.000 | 0.033 ± 0.001 |
| mplads | 0.728 ± 0.011 | 0.648 ± 0.015 | 0.316 ± 0.015 | 0.634 ± 0.013 | 0.014 ± 0.001 | 0.058 ± 0.005 | 0.004 ± 0.000 | 0.019 ± 0.002 |
| bbmp_2024 | 0.862 ± 0.015 | 0.730 ± 0.125 | 0.605 ± 0.032 | 0.871 ± 0.035 | 0.018 ± 0.005 | 0.041 ± 0.039 | 0.006 ± 0.003 | 0.027 ± 0.018 |
| bbmp_2010_2019 | 0.598 ± 0.024 | 0.623 ± 0.006 | 0.409 ± 0.008 | 0.568 ± 0.021 | 0.011 ± 0.002 | 0.034 ± 0.006 | 0.006 ± 0.001 | 0.030 ± 0.003 |
| chicago | 0.525 ± 0.009 | 0.576 ± 0.003 | 0.477 ± 0.009 | 0.532 ± 0.010 | 0.011 ± 0.000 | 0.035 ± 0.004 | 0.010 ± 0.000 | 0.018 ± 0.002 |
| secop | 0.500 ± 0.003 | 0.573 ± 0.002 | 0.468 ± 0.001 | 0.507 ± 0.003 | 0.022 ± 0.000 | 0.034 ± 0.001 | 0.021 ± 0.000 | 0.025 ± 0.001 |
| delaware | 0.534 ± 0.009 | 0.611 ± 0.006 | 0.410 ± 0.003 | 0.529 ± 0.007 | 0.011 ± 0.001 | 0.034 ± 0.001 | 0.009 ± 0.000 | 0.015 ± 0.001 |
| ocds_assam | 0.491 ± 0.043 | 0.602 ± 0.022 | 0.470 ± 0.059 | 0.524 ± 0.033 | 0.006 ± 0.003 | 0.012 ± 0.007 | 0.005 ± 0.002 | 0.007 ± 0.004 |
| icai | 0.645 ± 0.012 | 0.650 ± 0.004 | 0.551 ± 0.003 | 0.654 ± 0.010 | 0.050 ± 0.002 | 0.131 ± 0.012 | 0.025 ± 0.001 | 0.068 ± 0.002 |

## 5. Structural zeros

With F = 0 the highest reachable risk is 0.40 + 0.35 = 0.75 (A = D = 1); the Medium cut-off is 0.45.

| Dataset | Events with F = 0 | Events with D = 0 | Risk mass from A | from D | from F | from bonus |
|---|---|---|---|---|---|---|
| nspcl | 0.878 ± 0.000 | 0.923 ± 0.000 | 0.771 ± 0.001 | 0.078 ± 0.000 | 0.148 ± 0.001 | 0.003 ± 0.000 |
| mplads | 0.419 ± 0.000 | 0.956 ± 0.000 | 0.465 ± 0.001 | 0.028 ± 0.000 | 0.503 ± 0.001 | 0.004 ± 0.000 |
| bbmp_2024 | 0.856 ± 0.000 | 0.953 ± 0.001 | 0.740 ± 0.000 | 0.053 ± 0.001 | 0.202 ± 0.001 | 0.004 ± 0.000 |
| bbmp_2010_2019 | 0.515 ± 0.000 | 0.956 ± 0.000 | 0.489 ± 0.001 | 0.028 ± 0.000 | 0.479 ± 0.001 | 0.003 ± 0.000 |
| chicago | 0.732 ± 0.000 | 0.958 ± 0.000 | 0.668 ± 0.001 | 0.025 ± 0.000 | 0.306 ± 0.001 | 0.001 ± 0.000 |
| secop | 0.690 ± 0.000 | 0.899 ± 0.000 | 0.662 ± 0.000 | 0.060 ± 0.000 | 0.273 ± 0.000 | 0.005 ± 0.000 |
| delaware | 0.688 ± 0.000 | 0.948 ± 0.000 | 0.626 ± 0.001 | 0.035 ± 0.000 | 0.337 ± 0.001 | 0.002 ± 0.000 |
| ocds_assam | 0.503 ± 0.001 | 0.892 ± 0.000 | 0.498 ± 0.001 | 0.069 ± 0.001 | 0.425 ± 0.000 | 0.008 ± 0.000 |
| icai | 0.889 ± 0.001 | 0.886 ± 0.000 | 0.740 ± 0.002 | 0.113 ± 0.001 | 0.142 ± 0.001 | 0.006 ± 0.000 |

## Most likely causes

Each cause is tied to the tables above; none of it has been tested by changing AFED yet (that is step 3).

1. **The rule score F works against detection on real ledgers.** F alone ranks below chance on 6 of the 8 real
   ledgers (ROC-AUC 0.316 mplads, 0.409 bbmp_2010_2019, 0.410 delaware, 0.468 secop, 0.470 ocds_assam, 0.477
   chicago; 0.501 nspcl). The rules that need only amount and date fire on large shares of ordinary payments: a
   "duplicate" (same vendor, amount within 0.2%, within 14 days) on 37.7% of mplads and 30.0% of bbmp_2010_2019
   events, an "invoice burst" on 7.3% to 41.2% of events, a round amount on 21.6% of mplads. Yet F carries 14% to
   50% of all risk mass (50.3% mplads, 47.9% bbmp_2010_2019, 33.7% delaware). The other five rules can never fire
   on any real ledger (no approvals, creators, bank accounts or vendor dates), except rushed approval on secop and
   bbmp_2024.
2. **The forest component A carries most of the score but is close to random on the large ledgers.** A's ROC-AUC
   is 0.500 secop, 0.525 chicago, 0.534 delaware and 0.491 ocds_assam, while A supplies 47% to 77% of all risk mass.
   On these ledgers the forest has amount, date and category to work with; its other raw features are constant.
3. **The best signal is diluted.** The entity deviation D is the best single component on 7 of 9 datasets (for
   example delaware 0.611 alone against 0.529 for the fusion; chicago 0.576 against 0.532; secop 0.573 against
   0.507), but it is zero for 89% to 96% of events and contributes only 2.5% to 11% of risk mass. Fusion ranks
   below D alone on every dataset except mplads, bbmp_2024 and icai, where A is stronger.

Also seen: planted slow drift, frequency shifts and off-cycle invoices are caught at 0% to 12% at the default
cut-off on every real ledger (frequency shifts 3.4% to 9.8%, bbmp_2024 aside), and even amount spikes only 21% to
37% on chicago, secop, delaware and nspcl. Short histories are common on nspcl, mplads, bbmp_2024 and icai (46% to
80% of events have fewer than 8 earlier invoices) but are not the main cause on chicago, secop and delaware, where
histories are long (medians of 64, 20 and 149 earlier invoices) and ranking is still near chance.

