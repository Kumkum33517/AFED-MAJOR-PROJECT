# Data card

AFED's datasets in one schema, for training and evaluating per-entity anomaly detection. The catalogue of
sources, including rejected ones, is [DATASETS.md](../DATASETS.md).

## Layout

```
data/
  raw/<dataset>/         original downloads, never edited (not committed)
  processed/<dataset>.parquet, processed/unified.parquet   (not committed)
  scripts/               one loader per source, common.py, build_unified.py
  checksums.sha256       SHA-256 of every raw file, so a re-download can be checked
```

Run a loader, then `python build_unified.py`, with the backend's Python environment.

## Schema

| Column | Meaning | Derived? |
|---|---|---|
| event_id | Unique; prefixed with the dataset | From source ids, or the row position where the source has none |
| entity_id | The vendor, supplier, contractor, or for OCDS the buying department | Source code where one exists (NSPCL, MPLADS, AFED); otherwise a salted SHA-256 of the normalised name |
| entity_type | vendor, supplier, contractor or buyer | Set per dataset |
| counterparty_id | The other side: agency, department, ward, contract or supplier | Hashed when it is a name |
| amount, currency | Amount in the source's own currency | No |
| amount_inr | Amount in rupees | USD × 93.92 (ECB reference rate, 6 Nov 2026); COP × 0.028995 (open.er-api.com, 9 Nov 2026). One rate for all years: a simplification |
| event_timestamp | The date the source records; what it means differs per dataset (below) | Parsed |
| payment_gap_days | Days since this entity's previous event in the same dataset | Derived |
| processing_time_days | BBMP 2024-25: bill-register to RTGS payment. SECOP: signature to contract start. AFED synthetic: invoice to approval | Derived where the source has two dates; otherwise empty |
| category | The source's own grouping | No |
| source_dataset | Dataset name. Injected anomalies would be "<name>+injected", but never appear in these files | Set |
| is_synthetic | True only for generated data | Set |
| label, anomaly_type | Only where the source itself is labelled (AFED synthetic and temporal) | No |

## Rows per source (unified.parquet, 9 Nov 2026)

| Source | Real? | Events | Entities | Entities with 24+ events | Span | What the date is |
|---|---|---|---|---|---|---|
| nspcl | Real, India | 43,607 | 4,383 | 376 | 2023-01 – 2026-10 | Payment date |
| mplads | Real, India | 83,045 | 24,852 | 438 | 2024-07 – 2026-09 | Disbursement date |
| bbmp_2024 | Real, India | 8,103 | 1,906 | 38 | 2024-04 – 2025-03 | RTGS payment date |
| bbmp_2010_2019 | Real, India | 33,071 | 4,414 | 212 | 2010-05 – 2018-03 | Work-order date |
| ocds_hp | Real, India | 4,085 | 34 | 9 | 2012-10 – 2020-08 | Award date |
| ocds_assam | Real, India | 6,595 | 80 | 29 | 2019-07 – 2023-12 | Contract start |
| delaware | Real, USA | 361,607 | 1,843 | 1,809 | 2019-07 – 2026-10 | Check date |
| secop | Real, Colombia | 271,401 | 4,538 | 4,538 | 2022-01 – 2026-11 | Contract signature |
| chicago | Real, USA | 123,463 | 2,327 | 732 | 2023-01 – 2026-11 | Check date |
| afed_synthetic | Synthetic | 10,914 | 160 | 140 | 2023-10 – 2026-09 | Invoice date |
| afed_temporal | Synthetic | 9,155 | 160 | 148 | 2023-10 – 2026-09 | Invoice date |
| icai | Synthetic | 10,951 | 598 | 180 | 2023-04 – 2024-04 | Payment date |
| **Total** | | **965,997** | | | | |

CPPP was dropped: even trimmed to the needed columns (about 280 MB of 1.72 GB), one of its seven files took
over 34 minutes to fetch from Hugging Face, so the full set would take hours. Its loader is kept, unused.

## Cleaning rules

- **Personal data.** No person's name is stored. Names are dropped or replaced by salted hashes, after phone
  numbers, PAN and long digit runs are stripped (`common.strip_personal`). BBMP 2024-25 had phone numbers joined
  onto contractor names in 7,238 rows. SECOP's personal columns (individual ID numbers, legal representatives,
  bank account numbers) are never requested from the API. Chicago direct vouchers, which pay individuals, are
  excluded.
- **Duplicates.** Decided per source, because the same amount on the same day is often real:
  - NSPCL: the same vendor, date, payment document, amount and invoice reference.
  - MPLADS: identical in every field but the serial number (1,129 rows).
  - BBMP 2010-19: the same contractor, date, net amount and work order. 412,627 listed rows are 33,073 work
    orders, repeated across department, zone and ward files.
  - Chicago: the same voucher, amount, date and contract, keeping the row with a department.
- **Dropped rows.** Missing entity, amount or date; amounts that are zero, negative or not finite.
- **Subsets.** Delaware and SECOP are sampled by entity with a fixed seed (42), keeping whole histories, to stay
  under 400k rows each. The loaders' docstrings give the exact filters.

## Known limitations

- **No real labels.** Real-data accuracy comes only from injected anomalies, and real rows are treated as normal,
  so precision on real data is a lower bound.
- **Mixed event kinds.** The events are not all payments: CPPP, OCDS and SECOP are awards or contracts, and
  BBMP 2010-19 dates are work orders.
- **Short Indian histories.** The Indian sources have far fewer long entity histories than Delaware or SECOP.
- **Currency.** One conversion rate per currency for all years. Original amounts are kept.
- **Name matching.** Matching by normalised name (BBMP, CPPP, Chicago, Delaware) can merge two firms with the same
  name, or split one firm whose name is spelled two ways.
- **Synthetic sets.** The ICAI set is synthetic and unlabelled. AFED's own synthetic sets were designed together
  with AFED's rules, so results on them are optimistic.
