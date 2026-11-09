# LSTM ablation results

Produced by `experiments/temporal_ablation.py`, following `temporal_ablation.md`.

## Decision, on the temporal dataset

| Pre-registered condition | Met | Value |
|---|---|---|
| Mean recall higher with the LSTM errors | yes | mean difference +0.0475 |
| Mean alerts no higher with them | no | mean difference +59.2 |
| Recall higher with them on at least 3 of 5 seeds | yes | 5 of 5 |

**FAIL: recommend keeping the LSTM for the expected-vs-actual chart only and removing its errors from the forest. The default does not change until the supervisor decides.**

## Results

### Temporal dataset (decides)

| Seed | Recall with | Recall without | Alerts with | Alerts without | False alarms with | False alarms without |
|---|---|---|---|---|---|---|
| 1 | 0.120 | 0.062 | 476 | 402 | 447 | 387 |
| 2 | 0.171 | 0.117 | 524 | 464 | 479 | 433 |
| 3 | 0.135 | 0.070 | 533 | 469 | 498 | 451 |
| 4 | 0.167 | 0.137 | 411 | 374 | 372 | 342 |
| 5 | 0.165 | 0.134 | 549 | 488 | 506 | 453 |

| Measure, mean ± sd over seeds | With LSTM errors | Without | Paired difference (with − without) |
|---|---|---|---|
| Recall | 0.151 ± 0.022 | 0.104 ± 0.036 | 0.047 ± 0.016 |
| Alerts | 498.6 ± 56.0 | 439.4 ± 48.8 | 59.2 ± 13.6 |
| False alarms | 460.4 ± 54.4 | 413.2 ± 47.9 | 47.2 ± 11.1 |
| False-alarm rate | 0.0486 ± 0.0037 | 0.0436 ± 0.0029 | 0.0050 ± 0.0012 |
| Precision | 0.077 ± 0.014 | 0.060 ± 0.021 | 0.017 ± 0.009 |
| Average precision | 0.074 ± 0.009 | 0.057 ± 0.008 | 0.017 ± 0.005 |

| Recall by type, mean ± sd | With | Without |
|---|---|---|
| frequency_shift | 0.277 ± 0.092 | 0.146 ± 0.103 |
| off_cycle_invoice | 0.072 ± 0.036 | 0.053 ± 0.037 |
| slow_drift | 0.103 ± 0.048 | 0.112 ± 0.062 |

Standalone forest, LSTM + IF minus IF + entity, average precision: 0.022 ± 0.003.

### Original dataset (secondary)

| Seed | Recall with | Recall without | Alerts with | Alerts without | False alarms with | False alarms without |
|---|---|---|---|---|---|---|
| 1 | 0.905 | 0.945 | 630 | 587 | 400 | 347 |
| 2 | 0.885 | 0.944 | 656 | 630 | 433 | 392 |
| 3 | 0.942 | 0.971 | 614 | 583 | 387 | 349 |
| 4 | 0.898 | 0.902 | 661 | 626 | 433 | 397 |
| 5 | 0.917 | 0.976 | 670 | 647 | 437 | 399 |

| Measure, mean ± sd over seeds | With LSTM errors | Without | Paired difference (with − without) |
|---|---|---|---|
| Recall | 0.909 ± 0.022 | 0.948 ± 0.030 | -0.038 ± 0.023 |
| Alerts | 646.2 ± 23.3 | 614.6 ± 28.2 | 31.6 ± 7.9 |
| False alarms | 418.0 ± 22.9 | 376.8 ± 26.4 | 41.2 ± 6.8 |
| False-alarm rate | 0.0432 ± 0.0022 | 0.0390 ± 0.0027 | 0.0043 ± 0.0007 |
| Precision | 0.353 ± 0.013 | 0.387 ± 0.018 | -0.034 ± 0.009 |
| Average precision | 0.586 ± 0.010 | 0.610 ± 0.009 | -0.024 ± 0.005 |

| Recall by type, mean ± sd | With | Without |
|---|---|---|
| amount_spike | 0.992 ± 0.018 | 0.959 ± 0.041 |
| bank_change | 1.000 ± 0.000 | 1.000 ± 0.000 |
| duplicate_invoice | 1.000 ± 0.000 | 1.000 ± 0.000 |
| frequency_burst | 0.954 ± 0.050 | 0.947 ± 0.044 |
| invoice_splitting | 1.000 ± 0.000 | 1.000 ± 0.000 |
| new_vendor_large | 1.000 ± 0.000 | 1.000 ± 0.000 |
| off_hours_approval | 0.872 ± 0.107 | 0.984 ± 0.022 |
| round_amount | 0.268 ± 0.129 | 0.582 ± 0.257 |
| rushed_approval | 1.000 ± 0.000 | 1.000 ± 0.000 |
| sod_violation | 1.000 ± 0.000 | 1.000 ± 0.000 |

Standalone forest, LSTM + IF minus IF + entity, average precision: 0.003 ± 0.026.


## Interpretation

Written after the results were in. It is not part of the pre-registration, and it does not change the decision above.

**The decision is FAIL.** Recall was higher with the LSTM's errors in the forest on average and on all 5 seeds,
but mean alerts were higher too, so condition 2 was not met. The rule is applied as written.

**On temporal data, the LSTM adds information the other signals lack.** With its errors in the forest:

- Recall rose by 0.047 ± 0.016.
- Precision rose by 0.017 ± 0.009.
- Average precision rose by 0.017 ± 0.005. Average precision does not depend on how many alerts are raised,
  so the gain is not only the effect of raising more of them.
- The gain is almost all in frequency shifts, where recall went from 0.15 to 0.28. Off-cycle invoices barely
  moved, from 0.05 to 0.07, and slow drift not at all, from 0.11 to 0.10.
- The cost was 59 ± 14 more alerts (13%), 47 of them false alarms.

**On point anomalies it costs.** On the original data, the forest with the LSTM's errors did worse on every
measure: recall −0.038 ± 0.023, 32 more alerts, average precision −0.024 ± 0.005. Most of the loss is
`round_amount`, from 0.58 to 0.27, and `off_hours_approval`, from 0.98 to 0.87. Those are flag-only anomalies.
A likely reason, not tested here, is that three extra columns make the forest draw the sparse flag columns less often.

**The larger finding is that AFED catches few temporal anomalies either way.** Recall is 0.10 to 0.15 on
temporal anomalies, against 0.91 to 0.95 on point anomalies, with 5% to 6% of events alerted in both. AFED's entity
deviation and rules look at one invoice against a baseline. A likely reason, not tested here, is that a slow
drift raises the vendor's own baseline as it goes, and an extra invoice at a normal amount barely registers.
The LSTM narrows this gap a little. It does not close it.

**For the paper:**

> In a pre-registered ablation over five seeds, feeding the LSTM's forecast errors to the Isolation Forest
> improved ranking on temporally structured anomalies (average precision +0.017 ± 0.005, recall +0.047 ± 0.016,
> higher on all five seeds), mainly for changes in billing frequency, but raised 13% more alerts and so failed
> the pre-registered criterion. On point anomalies the same change lowered recall (−0.038 ± 0.023) and average
> precision. The LSTM therefore adds value only where temporal patterns exist, and then at an alert cost. Both
> configurations detected few temporal anomalies (recall 0.10 to 0.15), which identifies sequence-level
> detection as the main open problem for this design.

**For the supervisor's decision:** removing the LSTM's errors from the forest is what the rule recommends,
and it is better on point anomalies. Keeping them buys more temporal coverage, mainly frequency shifts, for
about 13% more alerts. Either way the LSTM still trains and drives the expected-vs-actual chart. Changing
`lstm.in_forest` to `false` is one setting, and the default stays as the brief specifies until she decides.
