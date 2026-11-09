# Does the LSTM help the Isolation Forest on temporal data? Pre-registration

Written and fingerprinted on 7 Nov 2026, before any model ran on the temporal dataset. Results are
written separately, to `temporal_ablation_results.md`, so this file stays as it was when frozen.

## Why

On the original synthetic set, removing the LSTM's error columns from the forest improved the full
fusion on all three seeds tried. That set's anomalies are mostly point anomalies (large amounts,
rule breaches) that z-scores and rules already catch, so it is not a fair test of a sequence model.
This experiment asks the question on data whose structure is temporal.

## Data: `data/generate_temporal.py`, fixed before the first run

- The same 160 vendors, categories, GST and approval habits as `generate_synthetic.py`.
- Billing rhythms: 45% fixed-day monthly (30% of those with a 1.6x quarterly true-up), 15% fortnightly,
  10% weekly, 30% irregular.
- Amounts: AR(1) drift in log amount (phi 0.95, innovation sd 0.05), invoice noise sd 0.05 to 0.20,
  6% yearly inflation, a March year-end lift, and 15% of vendors growing 15% to 35% a year.
- Unlabelled look-alikes kept from the original: bulk orders (1.2%), urgent payments (1%), Saturday closes (0.3%).
- Anomalies, about 2.5% of events, split equally, at most one episode per vendor, and only temporal:
  - `slow_drift`: 6 to 8 consecutive invoices compounding 6% to 10% each, then back to normal.
  - `frequency_shift`: a monthly vendor bills every 10 to 15 days for 2 to 3 months, at normal amounts.
  - `off_cycle_invoice`: three extra mid-cycle invoices at normal amounts within about six months.
- Every PO is derived from the final amount, so no PO gives an injection away.

The only checks run before freezing were on the data itself: billing day and gap regularity,
autocorrelation, trend slopes, anomaly counts and shapes. No model was run on this data.

## Arms

Both arms run the whole AFED pipeline with default settings. The LSTM trains in both, with the same
seed, so it is identical. The only difference is the forest's input:

- **With:** the LSTM's three per-feature errors are forest inputs, as the brief specifies.
- **Without:** they are not (`lstm.in_forest = false`).

LSTM hyperparameters stay at the brief's defaults (window 10, 12 epochs, forecast mode) and are not
tuned for either arm.

## Seeds and measures

- Dataset seeds 1, 2, 3, 4, 5. Data passes through a CSV and `read_csv`, as an upload would.
- Per arm and seed, for AFED fusion at its own alert count: recall, alerts, false alarms (count and
  rate), precision, average precision, and recall for each anomaly type.
- Reported as mean and standard deviation across seeds, plus the paired difference (with minus
  without) per seed.
- Secondary, not part of the decision: the same comparison on the original dataset (`generate_synthetic.py`)
  with the same seeds, and the standalone LSTM + IF against IF + entity average precision.

## Decision rule

On the temporal dataset, the LSTM's errors **stay in the forest's input** only if all three hold:

1. Mean recall with them is higher than without (mean paired difference above zero).
2. Mean alerts with them is no higher than without (mean paired difference at or below zero).
3. Recall is higher with them on at least 3 of the 5 seeds, so one seed cannot carry the result.

If all three hold, the pipeline stays exactly as the brief requires: LSTM, then Isolation Forest, then Qwen.

If any fails, the recommendation is to keep the LSTM for the expected-vs-actual chart only and stop
feeding its errors to the forest. Because the supervisor asked for that pipeline, the default does
not change until she decides; the evidence goes to her.

## Conduct

- Time box: this working session. One data design, one run of the ablation.
- After seeing results, neither the data nor the pipeline is changed to alter the outcome. If a bug
  makes the data fail its own description above, it is fixed, everything is rerun, and both sets of
  results are reported.
- Whatever the result, the ablation goes into the paper.
