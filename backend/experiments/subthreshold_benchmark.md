# Sub-threshold benchmark: anomalies a global limit cannot see (step 3a). Pre-registration

Written and committed on 11 Nov 2026 before `subthreshold_benchmark.py` first ran. Results:
`subthreshold_benchmark_results.md`, `.json`.

## Claim tested

AFED's central claim is entity-relative detection: an invoice can be ordinary in rupees and extraordinary for its
vendor. This benchmark plants only such invoices and asks which models find them.

## Data

nspcl, mplads, chicago, delaware, with `ml/inject.py: inject_subthreshold`, reporting seeds 4, 5, 6: one invoice
per vendor with 24+ events becomes 2x, 3x or 5x the median of the vendor's earlier invoices, only if that stays
below the Rs. 5,00,000 approval limit. Tagged `subthreshold_<m>x`, built in memory, never stored with real rows.
Measured on the latest 40% of each run by date. Planting yields far fewer than 2.5% of events (measured on seed 4:
nspcl 0.44%, mplads 0.17%, delaware 0.34%, chicago 40 events), so counts are reported, and chicago is too thin to
draw conclusions from.

## Models

| Model | Alerts | Score for PR-AUC |
|---|---|---|
| Rule-based | amount at or above Rs. 5,00,000 | amount |
| Global Isolation Forest | its own `contamination="auto"` cut-off, raw features | forest score |
| LOF | 20 neighbours, `contamination="auto"`, standardised raw features | LOF score |
| AFED v1 | Medium and above, default settings | risk |
| AFED v2 | full v2 from `v2_config.json` | risk |

Unsupervised models are fitted on all events of the run (no labels), as in the earlier comparison.

## Measures

Recall, precision, F1, PR-AUC and alerts, mean ± sd over seeds, and recall by multiplier. No decision rule: by
construction the rule-based model cannot alert on these invoices, and the question is how far each other model
gets.
