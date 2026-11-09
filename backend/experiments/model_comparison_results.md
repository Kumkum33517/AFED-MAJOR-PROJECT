# Model comparison: Rule-based, Global IF, LOF and AFED

Produced by `experiments/model_comparison.py`; the model and dataset definitions are in its docstring, fixed before the run.
Each model is judged at its own alert threshold. Values are mean ± sd over three seeds.
**Fraud detection rate is not reported:** no dataset has confirmed-fraud labels. Labels are injected or generated anomalies, so the anomaly detection rate (recall) is the measurable equivalent.

## afed_synthetic (synthetic, labelled)

| Model | Accuracy | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Rule-based (fixed threshold) | 0.969 ± 0.002 | 0.009 ± 0.008 | 0.002 ± 0.002 | 0.004 ± 0.003 |
| Global Isolation Forest only | 0.692 ± 0.003 | 0.038 ± 0.004 | 0.454 ± 0.052 | 0.070 ± 0.007 |
| LOF (contextual baseline) | 0.975 ± 0.000 | 0.559 ± 0.076 | 0.054 ± 0.001 | 0.098 ± 0.002 |
| **AFED (proposed, IF + entity-relative fusion)** | **0.957 ± 0.002** | **0.359 ± 0.010** | **0.898 ± 0.008** | **0.513 ± 0.009** |

| Model | Balanced accuracy | TP | FP | FN | TN | ROC-AUC | PR-AUC | FPR | FNR | Anomaly detection rate | Alerts | ms per event |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rule-based | 0.498 ± 0.000 | 1 | 64 | 273 | 10,423 | 0.657 ± 0.025 | 0.080 ± 0.016 | 0.0061 ± 0.0019 | 0.998 ± 0.002 | 0.002 ± 0.002 | 64 | 0.000 |
| Global IF | 0.576 ± 0.025 | 124 | 3,161 | 150 | 7,326 | 0.608 ± 0.012 | 0.035 ± 0.004 | 0.3015 ± 0.0036 | 0.546 ± 0.052 | 0.454 ± 0.052 | 3,285 | 0.028 |
| LOF | 0.526 ± 0.000 | 15 | 12 | 259 | 10,475 | 0.710 ± 0.015 | 0.154 ± 0.011 | 0.0011 ± 0.0003 | 0.946 ± 0.001 | 0.054 ± 0.001 | 27 | 0.012 |
| AFED | 0.928 ± 0.003 | 246 | 439 | 28 | 10,048 | 0.982 ± 0.001 | 0.567 ± 0.007 | 0.0418 ± 0.0021 | 0.102 ± 0.008 | 0.898 ± 0.008 | 684 | 0.469 |

| Precision@K | Rule-based | Global IF | LOF | AFED |
|---|---|---|---|---|
| P@50 | 0.05 ± 0.05 | 0.01 ± 0.01 | 0.41 ± 0.05 | 0.88 ± 0.04 |
| P@100 | 0.16 ± 0.11 | 0.01 ± 0.02 | 0.31 ± 0.03 | 0.65 ± 0.02 |
| P@200 | 0.20 ± 0.05 | 0.03 ± 0.00 | 0.24 ± 0.03 | 0.54 ± 0.01 |
| P@500 | 0.14 ± 0.01 | 0.03 ± 0.01 | 0.16 ± 0.01 | 0.42 ± 0.02 |

Share of anomalous amount caught: Rule-based 1.0%, Global IF 61.9%, LOF 3.6%, AFED 94.2%.

AFED risk levels (first seed, 10,914 events): Low 10,197, Medium 512, High 129, Critical 76.

## afed_temporal (synthetic, labelled)

| Model | Accuracy | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Rule-based (fixed threshold) | 0.966 ± 0.003 | 0.068 ± 0.050 | 0.023 ± 0.013 | 0.034 ± 0.021 |
| Global Isolation Forest only | 0.566 ± 0.028 | 0.024 ± 0.005 | 0.404 ± 0.124 | 0.046 ± 0.010 |
| LOF (contextual baseline) | 0.971 ± 0.001 | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 |
| **AFED (proposed, IF + entity-relative fusion)** | **0.929 ± 0.002** | **0.071 ± 0.013** | **0.142 ± 0.026** | **0.094 ± 0.017** |

| Model | Balanced accuracy | TP | FP | FN | TN | ROC-AUC | PR-AUC | FPR | FNR | Anomaly detection rate | Alerts | ms per event |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rule-based | 0.507 ± 0.007 | 6 | 88 | 249 | 9,473 | 0.552 ± 0.023 | 0.036 ± 0.004 | 0.0094 ± 0.0030 | 0.977 ± 0.013 | 0.023 ± 0.013 | 94 | 0.000 |
| Global IF | 0.487 ± 0.046 | 103 | 4,114 | 151 | 5,448 | 0.480 ± 0.048 | 0.024 ± 0.003 | 0.4299 ± 0.0325 | 0.596 ± 0.124 | 0.404 ± 0.124 | 4,217 | 0.030 |
| LOF | 0.499 ± 0.000 | 0 | 26 | 255 | 9,535 | 0.603 ± 0.007 | 0.036 ± 0.002 | 0.0027 ± 0.0009 | 1.000 ± 0.000 | 0.000 ± 0.000 | 26 | 0.010 |
| AFED | 0.546 ± 0.014 | 36 | 475 | 218 | 9,087 | 0.744 ± 0.025 | 0.068 ± 0.006 | 0.0497 ± 0.0015 | 0.858 ± 0.026 | 0.142 ± 0.026 | 511 | 0.420 |

| Precision@K | Rule-based | Global IF | LOF | AFED |
|---|---|---|---|---|
| P@50 | 0.07 ± 0.06 | 0.01 ± 0.01 | 0.01 ± 0.02 | 0.04 ± 0.00 |
| P@100 | 0.07 ± 0.05 | 0.01 ± 0.02 | 0.02 ± 0.02 | 0.04 ± 0.02 |
| P@200 | 0.07 ± 0.03 | 0.01 ± 0.01 | 0.03 ± 0.01 | 0.04 ± 0.02 |
| P@500 | 0.05 ± 0.01 | 0.01 ± 0.01 | 0.04 ± 0.01 | 0.07 ± 0.01 |

Share of anomalous amount caught: Rule-based 11.0%, Global IF 51.4%, LOF 0.0%, AFED 19.1%.

AFED risk levels (first seed, 9,155 events): Low 8,679, Medium 355, High 107, Critical 14.

## nspcl (real data, injected anomalies: precision is a lower bound)

| Model | Accuracy | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Rule-based (fixed threshold) | 0.743 ± 0.001 | 0.030 ± 0.003 | 0.398 ± 0.039 | 0.056 ± 0.006 |
| Global Isolation Forest only | 0.825 ± 0.005 | 0.013 ± 0.001 | 0.112 ± 0.010 | 0.024 ± 0.002 |
| LOF (contextual baseline) | 0.934 ± 0.000 | 0.023 ± 0.002 | 0.058 ± 0.006 | 0.032 ± 0.003 |
| **AFED (proposed, IF + entity-relative fusion)** | **0.915 ± 0.000** | **0.037 ± 0.002** | **0.136 ± 0.009** | **0.058 ± 0.004** |

| Model | Balanced accuracy | TP | FP | FN | TN | ROC-AUC | PR-AUC | FPR | FNR | Anomaly detection rate | Alerts | ms per event |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rule-based | 0.574 ± 0.019 | 336 | 10,791 | 507 | 32,394 | 0.607 ± 0.019 | 0.030 ± 0.002 | 0.2499 ± 0.0003 | 0.602 ± 0.039 | 0.398 ± 0.039 | 11,127 | 0.000 |
| Global IF | 0.475 ± 0.005 | 94 | 6,972 | 749 | 36,213 | 0.467 ± 0.011 | 0.017 ± 0.000 | 0.1614 ± 0.0050 | 0.888 ± 0.010 | 0.112 ± 0.010 | 7,066 | 0.015 |
| LOF | 0.504 ± 0.003 | 49 | 2,106 | 795 | 41,079 | 0.547 ± 0.004 | 0.022 ± 0.001 | 0.0488 ± 0.0006 | 0.942 ± 0.006 | 0.058 ± 0.006 | 2,154 | 0.002 |
| AFED | 0.533 ± 0.005 | 115 | 3,019 | 729 | 40,166 | 0.582 ± 0.002 | 0.028 ± 0.000 | 0.0699 ± 0.0004 | 0.864 ± 0.009 | 0.136 ± 0.009 | 3,133 | 0.415 |

| Precision@K | Rule-based | Global IF | LOF | AFED |
|---|---|---|---|---|
| P@50 | 0.07 ± 0.01 | 0.00 ± 0.00 | 0.03 ± 0.02 | 0.01 ± 0.01 |
| P@100 | 0.07 ± 0.01 | 0.00 ± 0.00 | 0.02 ± 0.02 | 0.03 ± 0.01 |
| P@200 | 0.04 ± 0.00 | 0.00 ± 0.00 | 0.01 ± 0.01 | 0.04 ± 0.01 |
| P@500 | 0.04 ± 0.01 | 0.00 ± 0.00 | 0.01 ± 0.01 | 0.06 ± 0.01 |

Share of anomalous amount caught: Rule-based 98.4%, Global IF 86.2%, LOF 44.0%, AFED 43.3%.

AFED risk levels (first seed, 44,024 events): Low 40,915, Medium 2,166, High 811, Critical 132.

## mplads (real data, injected anomalies: precision is a lower bound)

| Model | Accuracy | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Rule-based (fixed threshold) | 0.817 ± 0.000 | 0.012 ± 0.001 | 0.404 ± 0.024 | 0.023 ± 0.002 |
| Global Isolation Forest only | 0.849 ± 0.006 | 0.009 ± 0.000 | 0.263 ± 0.013 | 0.018 ± 0.000 |
| LOF (contextual baseline) | 0.830 ± 0.000 | 0.011 ± 0.002 | 0.348 ± 0.043 | 0.021 ± 0.003 |
| **AFED (proposed, IF + entity-relative fusion)** | **0.885 ± 0.001** | **0.013 ± 0.001** | **0.262 ± 0.003** | **0.024 ± 0.001** |

| Model | Balanced accuracy | TP | FP | FN | TN | ROC-AUC | PR-AUC | FPR | FNR | Anomaly detection rate | Alerts | ms per event |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rule-based | 0.612 ± 0.012 | 180 | 14,974 | 265 | 67,847 | 0.668 ± 0.015 | 0.026 ± 0.002 | 0.1808 ± 0.0002 | 0.596 ± 0.024 | 0.404 ± 0.024 | 15,154 | 0.000 |
| Global IF | 0.558 ± 0.004 | 117 | 12,228 | 328 | 70,593 | 0.631 ± 0.018 | 0.008 ± 0.000 | 0.1476 ± 0.0064 | 0.737 ± 0.013 | 0.263 ± 0.013 | 12,345 | 0.012 |
| LOF | 0.590 ± 0.021 | 155 | 13,852 | 290 | 68,969 | 0.705 ± 0.011 | 0.011 ± 0.001 | 0.1673 ± 0.0006 | 0.652 ± 0.043 | 0.348 ± 0.043 | 14,007 | 0.003 |
| AFED | 0.576 ± 0.002 | 117 | 9,210 | 328 | 73,612 | 0.633 ± 0.005 | 0.020 ± 0.002 | 0.1112 ± 0.0013 | 0.738 ± 0.003 | 0.262 ± 0.003 | 9,326 | 0.549 |

| Precision@K | Rule-based | Global IF | LOF | AFED |
|---|---|---|---|---|
| P@50 | 0.17 ± 0.01 | 0.00 ± 0.00 | 0.01 ± 0.02 | 0.00 ± 0.00 |
| P@100 | 0.12 ± 0.01 | 0.00 ± 0.00 | 0.02 ± 0.02 | 0.02 ± 0.02 |
| P@200 | 0.07 ± 0.01 | 0.00 ± 0.00 | 0.02 ± 0.01 | 0.09 ± 0.01 |
| P@500 | 0.06 ± 0.00 | 0.00 ± 0.00 | 0.02 ± 0.01 | 0.06 ± 0.01 |

Share of anomalous amount caught: Rule-based 87.7%, Global IF 60.4%, LOF 36.3%, AFED 58.7%.

AFED risk levels (first seed, 83,259 events): Low 74,061, Medium 6,726, High 2,030, Critical 442.

## chicago (real data, injected anomalies: precision is a lower bound)

| Model | Accuracy | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Rule-based (fixed threshold) | 0.435 ± 0.000 | 0.015 ± 0.000 | 0.774 ± 0.002 | 0.029 ± 0.001 |
| Global Isolation Forest only | 0.822 ± 0.006 | 0.020 ± 0.001 | 0.330 ± 0.023 | 0.039 ± 0.002 |
| LOF (contextual baseline) | 0.929 ± 0.000 | 0.012 ± 0.001 | 0.065 ± 0.004 | 0.020 ± 0.001 |
| **AFED (proposed, IF + entity-relative fusion)** | **0.900 ± 0.001** | **0.011 ± 0.000** | **0.095 ± 0.002** | **0.020 ± 0.001** |

| Model | Balanced accuracy | TP | FP | FN | TN | ROC-AUC | PR-AUC | FPR | FNR | Anomaly detection rate | Alerts | ms per event |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rule-based | 0.602 ± 0.001 | 1,041 | 69,888 | 305 | 52,902 | 0.655 ± 0.006 | 0.022 ± 0.001 | 0.5692 ± 0.0001 | 0.226 ± 0.002 | 0.774 ± 0.002 | 70,928 | 0.000 |
| Global IF | 0.578 ± 0.008 | 444 | 21,236 | 901 | 101,553 | 0.643 ± 0.010 | 0.018 ± 0.001 | 0.1729 ± 0.0063 | 0.670 ± 0.023 | 0.330 ± 0.023 | 21,680 | 0.013 |
| LOF | 0.502 ± 0.002 | 88 | 7,535 | 1,258 | 115,255 | 0.559 ± 0.011 | 0.012 ± 0.000 | 0.0614 ± 0.0001 | 0.935 ± 0.004 | 0.065 ± 0.004 | 7,623 | 0.003 |
| AFED | 0.502 ± 0.001 | 128 | 11,146 | 1,217 | 111,643 | 0.509 ± 0.007 | 0.015 ± 0.001 | 0.0908 ± 0.0006 | 0.905 ± 0.002 | 0.095 ± 0.002 | 11,275 | 0.391 |

| Precision@K | Rule-based | Global IF | LOF | AFED |
|---|---|---|---|---|
| P@50 | 0.07 ± 0.02 | 0.00 ± 0.00 | 0.02 ± 0.00 | 0.15 ± 0.03 |
| P@100 | 0.09 ± 0.02 | 0.00 ± 0.00 | 0.02 ± 0.01 | 0.13 ± 0.03 |
| P@200 | 0.06 ± 0.01 | 0.00 ± 0.00 | 0.01 ± 0.01 | 0.10 ± 0.01 |
| P@500 | 0.05 ± 0.01 | 0.01 ± 0.00 | 0.01 ± 0.00 | 0.08 ± 0.01 |

Share of anomalous amount caught: Rule-based 99.8%, Global IF 91.0%, LOF 26.2%, AFED 24.3%.

AFED risk levels (first seed, 124,151 events): Low 112,906, Medium 8,881, High 2,215, Critical 149.

## delaware (real data, injected anomalies: precision is a lower bound)

| Model | Accuracy | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Rule-based (fixed threshold) | 0.817 ± 0.000 | 0.015 ± 0.000 | 0.272 ± 0.007 | 0.029 ± 0.001 |
| Global Isolation Forest only | 0.835 ± 0.004 | 0.022 ± 0.000 | 0.353 ± 0.006 | 0.041 ± 0.000 |
| LOF (contextual baseline) | 0.909 ± 0.000 | 0.010 ± 0.001 | 0.084 ± 0.009 | 0.018 ± 0.002 |
| **AFED (proposed, IF + entity-relative fusion)** | **0.905 ± 0.001** | **0.014 ± 0.000** | **0.120 ± 0.002** | **0.025 ± 0.000** |

| Model | Balanced accuracy | TP | FP | FN | TN | ROC-AUC | PR-AUC | FPR | FNR | Anomaly detection rate | Alerts | ms per event |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rule-based | 0.547 ± 0.004 | 997 | 63,961 | 2,675 | 295,809 | 0.571 ± 0.006 | 0.015 ± 0.000 | 0.1778 ± 0.0000 | 0.728 ± 0.007 | 0.272 ± 0.007 | 64,958 | 0.000 |
| Global IF | 0.596 ± 0.002 | 1,295 | 57,535 | 2,377 | 302,235 | 0.686 ± 0.003 | 0.020 ± 0.000 | 0.1599 ± 0.0038 | 0.647 ± 0.006 | 0.353 ± 0.006 | 58,830 | 0.011 |
| LOF | 0.501 ± 0.004 | 308 | 29,687 | 3,363 | 330,083 | 0.568 ± 0.008 | 0.014 ± 0.000 | 0.0825 ± 0.0003 | 0.916 ± 0.009 | 0.084 ± 0.009 | 29,996 | 0.004 |
| AFED | 0.517 ± 0.001 | 440 | 31,182 | 3,231 | 328,588 | 0.516 ± 0.007 | 0.015 ± 0.000 | 0.0867 ± 0.0008 | 0.880 ± 0.002 | 0.120 ± 0.002 | 31,622 | 0.373 |

| Precision@K | Rule-based | Global IF | LOF | AFED |
|---|---|---|---|---|
| P@50 | 0.07 ± 0.03 | 0.03 ± 0.01 | 0.20 ± 0.07 | 0.01 ± 0.01 |
| P@100 | 0.04 ± 0.01 | 0.03 ± 0.01 | 0.20 ± 0.03 | 0.03 ± 0.01 |
| P@200 | 0.05 ± 0.01 | 0.02 ± 0.01 | 0.14 ± 0.02 | 0.04 ± 0.01 |
| P@500 | 0.04 ± 0.01 | 0.02 ± 0.01 | 0.09 ± 0.01 | 0.03 ± 0.00 |

Share of anomalous amount caught: Rule-based 98.4%, Global IF 93.7%, LOF 44.9%, AFED 24.9%.

AFED risk levels (first seed, 363,435 events): Low 332,112, Medium 25,881, High 4,698, Critical 744.

## Figures (AFED synthetic, seed 42)

- `figures/model_comparison.png`
- `figures/score_distribution.png`
- `figures/risk_levels.png`
- `figures/precision_at_k.png`
- `figures/amount_analysis.png`
