# Why is AFED's ranking weak on real ledgers? Pre-registration

Written and committed on 11 Nov 2026 before the diagnostic script first ran. Results: `diagnostics_results.md` and
`diagnostics_results.json`.

## Question

On Chicago, SECOP II and Delaware, AFED's ROC-AUC is about 0.50. This step looks for the causes. It changes
nothing in AFED and decides nothing: it only describes.

## Data (tuning split only)

- Real ledgers evaluated before: nspcl, mplads, bbmp_2024, bbmp_2010_2019, chicago, secop, delaware.
- Added in step 0: ocds_assam (real, entities are buying departments) and icai (third-party synthetic).
- Anomalies planted with `ml/inject.py`, seeds 1, 2, 3 (tuning seeds).
- Only events dated before the 60th percentile of each run's dates are measured (the tuning period). The pipeline
  scores the whole run, as in production; nothing from the later 40% is reported or looked at.
- AFED v1, default settings.

## Measures, per dataset, mean ± sd over the three seeds

1. Recall per planted type at the default Medium cut-off (0.45), and overall precision. A false alarm has no
   planted type, so precision is reported overall only; per type, the share of true positives is given.
2. Vendor history length at each event (median, quartiles, share under 8 and under 24 prior events), and the share
   of events scored against the vendor's own baseline, a peer group, or the whole population.
3. For each of the ten rules: whether its input fields exist in the dataset, and how often it fires.
4. ROC-AUC and PR-AUC of each component alone, A (forest percentile cubed), D (entity deviation) and F (rule score),
   and of the fused risk.
5. Structural zeros: the share of events where F = 0 and where D = 0, the share of the total risk mass each
   component contributes, and the highest risk an event can reach when F = 0.

## Output

The tables above, then a plain-language list of the three most likely causes of weak ranking, each tied to numbers
in the tables. No threshold, weight or setting is changed by this step.
