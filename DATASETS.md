# Datasets

The catalogue of every dataset considered for AFED, kept or rejected. Each was checked on 9 Nov 2026 by
opening its source page, API metadata or a sample file. Where a fact could not be confirmed it says
"unverified". Nothing here is from memory.

How data is used is described in [data/DATA_CARD.md](data/DATA_CARD.md). Loaders are in `data/scripts/`.

**Coverage.** Of the 9 real datasets loaded, 6 are Indian (67%). By event count the foreign ones dominate
(756k of 935k real events), because Indian public data with vendor-level histories is scarce: national
portals (data.gov.in, GeM, CPPP and the state e-procurement result pages) block bulk access with logins or
captchas.

**Labels.** No real dataset found has fraud or anomaly labels. Accuracy on real data is measured with
injected anomalies only (`backend/ml/inject.py`), tagged and never stored with the real rows.

**Evaluation coverage (11 Nov 2026).** Besides the seven real ledgers evaluated before, ocds_assam (real) and icai
(third-party synthetic) are now evaluated with planted anomalies as extra rows (`backend/experiments/`, v2). ocds_hp
is not: only 9 of its 34 buyers have 24 or more events, so planting reaches 12 anomalies (0.29% of events).
Planting reaches its 2.5% target only where enough vendors have long histories: measured with seed 1, secop 2.47%,
nspcl 1.90%, chicago 1.11%, delaware 1.01%, bbmp_2024 0.81%, ocds_assam 0.80%, bbmp_2010_2019 0.62%, mplads 0.52%.

## In use

| Dataset | Source | Country | Licence | Size used | Span | Entity | Dates | Labels | Per-entity history | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| NSPCL vendor payments | [nspcl.co.in/vendor-payment](https://www.nspcl.co.in/vendor-payment), 45 monthly PDFs | India | Free reproduction with acknowledgement (site copyright page) | 43,607 payments, 4,383 vendors | Jan 2023 – Oct 2026 (Aug 2026 missing at source) | SAP vendor number | Payment date, daily | None | 376 vendors with 24+ | Best Indian ledger. Real payments, stable ids |
| MPLADS expenditure | [Kaggle rajan1673/indias-mplads](https://www.kaggle.com/datasets/rajan1673/indias-mplads), scraped from mplads.mospi.gov.in | India | MIT on Kaggle; portal terms not stated. Script only, data not committed | 83,045 payments, 24,852 vendors | Jul 2024 – Sep 2026 | Portal vendor id; implementing agency | Disbursement date, daily | None | 438 vendors with 24+ | Strong. Short span. The dataset's `real_*.csv` files look derived and are not used |
| BBMP payments 2024-25 | [OpenCity](https://data.opencity.in/dataset/bbmp-work-orders-and-payments-2024-25) | India | Other (Public Domain) | 8,103 payments, 1,906 contractors | Apr 2024 – Mar 2025 | Contractor (hashed) | RTGS payment date; bill date too | None | 38 with 24+ | Good, short. Has real bill-to-payment times |
| BBMP work orders 2010-19 | [OpenCity](https://data.opencity.in/dataset/bbmp-work-orders-and-bill-payment), 84 of 87 files | India | None stated. Script only | 33,073 distinct work orders (412,627 rows listed) | May 2010 – Mar 2018 | Contractor (hashed, joinable with 2024-25) | Work-order date, not payment date | None | 212 with 24+ | Good, long. Dates are work orders |
| Himachal Pradesh OCDS | [OCP registry #77](https://data.open-contracting.org/en/publication/77) | India | CC BY 4.0 | 4,085 awards, 34 buyers | Oct 2012 – Aug 2020 | Buyer department | Award date | None | 9 buyers with 24+ | Secondary. Supplier ids are not real ids |
| Assam OCDS | [CivicDataLab/assam-tenders-data](https://github.com/CivicDataLab/assam-tenders-data) v3 | India | ODbL | 6,595 awards, 80 buyers (5,710 zero-value awards dropped) | Jul 2019 – Dec 2023 | Buyer department | Contract start date | None | 29 buyers with 24+ | Secondary. Thin supplier histories |
| Delaware checkbook | [data.delaware.gov 5s6n-7hpx](https://data.delaware.gov/Government-and-Finance/State-of-Delaware-Checkbook/5s6n-7hpx) | USA | Public Domain | 361,607 payments from a seeded sample of 1,843 vendors (of 18.2M rows) | Jul 2019 – Oct 2026 | Vendor (hashed) | Check date, daily | None | 1,809 with 24+ | Best foreign ledger. Payroll and giant payees left out |
| Colombia SECOP II | [datos.gov.co jbjy-vk9h](https://www.datos.gov.co/Gastos-Gubernamentales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h) | Colombia | CC BY-SA 4.0. Script only | 271,401 contracts, 4,538 companies (of 5.7M) | Jan 2022 – Nov 2026 | Company tax number (hashed) | Signature date | None | 4,538 with 24+ | Strong. Contracts, not payments. Personal columns never downloaded |
| Chicago payments | [data.cityofchicago.org s4vu-giwb](https://data.cityofchicago.org/Administration-Finance/Payments/s4vu-giwb) | USA | "See Terms of Use" (terms page returned 403). Script only | 123,463 payments, 2,327 vendors | Jan 2023 – Nov 2026 | Vendor (hashed) | Check date, daily | None | 732 with 24+ | Good. Older rows are yearly totals and are left out |
| AFED synthetic | `backend/data/generate_synthetic.py`, seed 42 | Synthetic | Ours | 10,914 invoices | Oct 2023 – Sep 2026 | Vendor | Daily | Yes, 10 point types | 140 with 24+ | Labelled. Rules match its anomaly types, so results are optimistic |
| AFED temporal | `backend/data/generate_temporal.py`, seed 1 | Synthetic | Ours | 9,155 invoices | Oct 2023 – Sep 2026 | Vendor | Daily | Yes, 3 temporal types | 148 with 24+ | Labelled. For the LSTM ablation |
| ICAI vendor payments | [Kaggle kmldas/vendor-payment-dataset-icai-book](https://www.kaggle.com/datasets/kmldas/vendor-payment-dataset-icai-book) | Synthetic (India) | CDLA-Permissive-1.0 | 10,951 payments, 598 vendors | Apr 2023 – Apr 2024 | Vendor | Daily | None (its risk cluster is K-means output) | 180 with 24+ | Tests and demo only |

**Shipped sample.** One subset is committed: `frontend/public/samples/nspcl_sample.csv`, the full histories of 80
NSPCL vendors (5,745 payments, vendor numbers only), offered on the upload page. NSPCL permits reproduction with
acknowledgement, which the page and README give. No other dataset is redistributed.

## Considered and rejected

### Indian government sources

| Dataset | Source | Reason |
|---|---|---|
| data.gov.in catalogue (incl. Assam procurement) | data.gov.in | Pages load client-side and returned 403 to scripted access; the API needs a key. Not pursued, at the project's request |
| GeM contract search | gem.gov.in/view_contracts | Captcha required; gem.gov.in/opendata returned 404 |
| GeM statistics | gem.gov.in/statistics | Aggregate totals only |
| GeM-CPPP tender notices | gem.gov.in/cppp, eprocure.gov.in/cppp | Tender notices only, no awards; CPPP home is a JavaScript app |
| NIC GePNIC "Result of Tenders" | eprocure.gov.in, assamtenders.gov.in, hptenders.gov.in | Captcha on every search, no bulk export |
| Assam OCDS tenders (registry #131) | data.open-contracting.org | Tender notices only: 0 awards, 0 suppliers |
| CivicDataLab Assam procurement 2016-21 CSVs | ndp.ckan.civicdatalab.in | Department and tender dates only, no supplier or amount paid |
| CAG Meghalaya voucher-wise expenditure | cag.gov.in | No payee named, monthly only |
| PFMS | pfms.gov.in | Per-account lookup; reports need a login |
| Open Budgets India treasury files | openbudgetsindia.org | Files return 404; the domain now redirects to an unrelated site |
| AIKosh CAG public account disbursements 2000-11 | aikosh.indiaai.gov.in | Annual aggregate; file appears empty |
| ISRO bids awarded (RTI) | isro.gov.in | About 25 rows |
| Ministry of Commerce e-payment registers | commerce.gov.in | 404 |
| CPPP awards of contract (HF rumourscape/tenders) | huggingface.co | Dropped: even trimmed to 7 columns (about 280 MB of 1.72 GB), one of seven files took over 34 minutes to fetch, so the full set would take hours. Loader kept unused in data/scripts/load_cppp.py |
| HF fireboy21/tenders_aoc | huggingface.co | Same source as the CPPP scrape in use, but raw SQLite (about 6.6 GB) and the parquet its card names does not exist |

### Indian datasets on Kaggle, Hugging Face and GitHub

| Dataset | Source | Reason |
|---|---|---|
| Indian Financial Fraud Dataset | kaggle jatinkhandelwal112 | Synthetic; labels are generator rules, so results would be circular |
| UPI (Unified Payment Interface) Transaction | kaggle santwanpathak | Synthetic consumer payments, not vendors. Possible sanity benchmark only |
| Banking Transactions 2019-2024 | kaggle belbino | Generated; median 7 transactions per customer; trivial fraud rule |
| Indian Credit Card Fraud Detection | kaggle quantumkaran | Synthetic card data; schema looks like a re-skinned card-fraud simulator (inference, unverified) |
| Pan-Indian Consumer Transaction | kaggle kumarperiya | Unclear origin; about 52% of rows labelled fraud ("augmented") |
| Bank Customer Segmentation (1M+) | kaggle shivamb | About 1.3 transactions per customer; source bank not stated |
| UPI Transactions 2024 | kaggle skullagos5246 | No sender or receiver id at all |
| UPI Payment Transactions | kaggle devildyno | 1,000 rows, every sender unique |
| UPI Transactions (two byte-identical copies) | kaggle bijitda, nitishjolly | One person's statement; the two copies carry different licences |
| Indian Bank Statement (one year) | kaggle devildyno | One account |
| UPI Digital Payment Fraud | kaggle aishricadhiman | Every row is labelled fraud |
| B2B Sales, Inventory & Finance | kaggle kirtanjogani | Synthetic; 14 suppliers |
| Credit Card Spending Habits in India | kaggle thedevastator | No customer or card id |
| Electoral Bonds 2024 | kaggle pritkc | Political donations, fixed denominations, few repeat purchasers |
| Indian-Bank-Statements | HF AgamiAI | Synthetic PDFs for document AI; counterparties only as free text |
| Accounts Payable (Power BI) | kaggle findi360 | UAE, USD, synthetic |
| india-mplads-works | GitHub Vonter | Works only, no vendor field |
| Other small or aggregate sets | various | Faker data, one row per GSTIN, fake PAN/Aadhaar records, or NPCI/RBI monthly totals with no entities |

### Foreign sources

| Dataset | Source | Reason |
|---|---|---|
| San Francisco vendor payments | data.sf.gov n9pm-xkyq (PDDL, 8.2M rows) | No payment date: `data_as_of` is a source-system update stamp. Still used by the app's demo loader, not in the evaluation |
| Ukraine Prozorro (OCDS) and State Audit monitorings | data.open-contracting.org #154; audit-api.prozorro.gov.ua | Licence not stated. The audit `violationOccurred` flags are the only real audit labels found, but they are biased (tenders were chosen by risk indicators). A possible future experiment |
| Brazil federal procurement (OCDS) | registry #157 (CC BY 4.0) | Awards only; enough award data already |
| Brazil Medicamentos Transparentes | registry #153 | Small single-sector awards |
| Italy ANAC (OCDS) | registry #117 | Data-quality warnings on its own page |
| Colombia OCDS (SECOP I history) | registry #61 | Superseded by SECOP II; dirty supplier ids |
| EU TED | data.europa.eu ted-csv | Above-threshold awards only; winners have no id before XSD 2.0.9 |
| UK HM Treasury spend over £25k | gov.uk | About 60 rows a month from one department |
| PaySim | kaggle ealaxi/paysim1 (CC BY-SA 4.0) | Mobile money, 30 simulated days, synthetic labels |
| IEEE-CIS Fraud Detection | kaggle competition | Card payments; competition rules (unverified) indicate no redistribution |
| World Bank debarred firms | worldbank.org, opensanctions.org | An entity list, not transactions; OpenSanctions copy is non-commercial |
| Labelled Italian and Mexican procurement studies | papers | Labelled data not released |

## Pre-existing downloads (not used)

`data/raw/dc_procurement` (DC government contract payments, from HF `abigailhaddad/dc-procurement-raw`) and
`data/raw/mindweave_p2p` (synthetic procure-to-pay, HF `mindweave/purchasing-procurement-us`) were downloaded by
`backend/scripts/download_datasets.py` before this catalogue. AFED does not read them.
