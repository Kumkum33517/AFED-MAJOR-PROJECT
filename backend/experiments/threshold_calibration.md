# Per-dataset alert threshold on a held-out period: pre-registration

Written on 9 Nov 2026 and committed to git before the script first ran, so the commit dates the plan. Results go
to `threshold_calibration_results.md`; this file is not edited after the run.

## Question

AFED alerts at a fixed risk of 0.45 (Medium) on every dataset. On real data it does worse than a global
Isolation Forest on Chicago and Delaware. Does choosing the threshold separately for each dataset, on an
earlier period, give a better F1 on a later period it has not seen?

## Data

The datasets of `model_comparison.py`, chosen there by a fitness test and not by results:

- Real, with anomalies injected by `ml/inject.py` (seeds 1, 2, 3): nspcl, mplads, chicago, delaware.
- Synthetic, labelled (seeds 42, 7, 123): afed_synthetic, reported for reference only.

## Method

1. Run the whole AFED pipeline once per dataset and seed, at default settings. The pipeline never reads labels.
2. Split the scored events by date: calibration is every event before the 60th percentile of event dates;
   test is the rest. A date split, because a deployment can only calibrate on its past.
3. Default arm: alert when risk >= 0.45.
4. Calibrated arm: on the calibration period only, try thresholds 0.30, 0.31, ..., 0.95 and keep the one with
   the highest F1. On a tie, the higher threshold (fewer alerts).
5. On the test period, measure both arms: F1, precision, recall, balanced accuracy, alerts. Report mean ± sd
   over the three seeds, and the chosen thresholds.

## Decision rule

Per-dataset calibration is called helpful if, on the test period, its mean F1 is higher than the default's on
at least 3 of the 4 real datasets, and no real dataset loses more than 0.01 of mean F1. Synthetic results do not
count towards the rule. All results are reported whatever they show, and nothing is changed after seeing them.

If the rule passes, the app may offer a threshold calibrated from labelled data as an option in Model settings,
with the default unchanged. That change would be made only after this result, and described as such.
