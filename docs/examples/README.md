# Example AFED results

Three files exported from the app's Reports page, unedited. Open them in Excel or Google Sheets.

| File | What it is | Rows |
|---|---|---|
| `1-all-alerts-demo.csv` | Every alert from the labelled demo data (synthetic, 10,914 invoices), with reviewer decisions | 717 |
| `2-all-results-nspcl-real.csv` | Every scored payment from the real NSPCL sample, Low risk included, highest risk first | 5,745 |
| `3-one-case-alerts.csv` | The alerts of one case: Patel Infotech LLP, 7 alerts in 30 days | 7 |

## Columns

| Column | Meaning |
|---|---|
| `amount` | The invoice or payment, in rupees |
| `vendor_usual_amount` | The vendor's typical amount before this event (median of its own history, or of its peers while the history is short) |
| `times_usual` | `amount` divided by `vendor_usual_amount` |
| `usual_from` | Where the usual amount came from: `vendor`, `peer` or `global` |
| `risk`, `level` | Risk from 0 to 1, and Low, Medium, High or Critical. Medium and above are alerts |
| `forest_signal`, `deviation_signal`, `rule_signal` | The three parts of the risk score: Isolation Forest, distance from the vendor's own normal, and red-flag rules |
| `red_flags` | The rules that fired, in words |
| `why_flagged` | The explanation shown to reviewers, written only from computed facts |
| `alerted`, `alert_id` | In the results file: whether the payment became an alert |
| `status`, `decision`, `decided_by`, `decided_at`, `decision_reason`, `decision_comment` | What the reviewer decided |
| `simulated_review` | `True` for the demo's simulated decisions, which were made from the synthetic labels, not by a person |
| `assignee`, `case_id`, `model_version` | Who it is assigned to, its case, and the model run that scored it |

Labels used for evaluation and bank account numbers are never exported.

Example 2 is real data: NSPCL vendor payments (nspcl.co.in), reproduced with acknowledgement. The NSPCL payments
carry no labels, so its alerts are leads for review, not findings. AFED flags events for human review; a flag is not
a finding of wrongdoing.
