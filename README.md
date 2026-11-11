# AFED: Automated Fraud and Event Detection

AFED finds unusual vendor and procurement transactions by comparing each event with that vendor's own
history, or its peers while the history is short. It scores risk, explains every flag in plain language,
and lets reviewers confirm or dismiss alerts. Those decisions can then recalibrate the scoring.

A Rs. 4.8 lakh invoice sits under a Rs. 5 lakh approval limit, so a global rule passes it. For a
vendor who usually bills Rs. 50,000, it is 9.6x normal. That gap is what AFED is built to catch.

AFED flags events for human review. A flag is not a finding of wrongdoing.

## Pipeline

```
 CSV ──> Validate ──> Features + red flags + entity baselines
                                  │
                                  ▼
                    LSTM (temporal error per feature)
                                  │
                                  ▼
                    Isolation Forest (all signals together)
                                  │
                                  ▼
       Risk fusion  A, D, F ──> Tiers ──> Deterministic facts ──> Qwen narration
                                                                       │
                                                                       ▼
       Recalibration <── Reviewer feedback <────────────────────── Alerts

 Evaluation and ablation run on every run that has labels.
```

`Risk = w1·A + w2·D + w3·F + 0.10·min(D, F)`, with defaults (0.40, 0.35, 0.25):

- **A** is the Isolation Forest percentile, cubed.
- **D** is `1 − exp(−deviation/3)`, the entity deviation.
- **F** is the noisy-OR rule score.

Tiers are Low < 0.45 ≤ Medium < 0.60 ≤ High < 0.75 ≤ Critical. Medium and above become alerts.

## v2 options (off by default)

v1 is the default and stays reproducible: with every option below off, output matches v1 exactly
(`tests/fixtures/v1_seed42.json`, checked by `tests/test_afed.py`). Each option is a setting, also in **Model
settings → v2 options**. Whether any of them should become the default is decided by a pre-registered rule; see
`backend/experiments/v2_evaluation_results.md` and `backend/experiments/report_numbers_v2.md`.

| Setting | What it does | Usable in a real deployment? |
|---|---|---|
| `field_aware` | Scales the rule weight by the share of rule severity whose inputs the data has, and renormalises: `Risk = (w1·A + w2·D + w3'·F)/(w1 + w2 + w3') + 0.10·min(D, F)`, `w3' = w3 × rule share`. Equal to v1 when every input exists. Each run records its inputs, active rules and weights (`active.json`, shown on the run's model version). | Yes |
| `calibration.mode = "alert_budget"` | Chooses the Medium cut-off so that `target_rate` of each run's earliest 60% of events are alerts, then applies it to all. Needs no labels. Preview with `POST /settings/calibrate` (Admin, Analyst). | Yes |
| `calibration.mode = "label"` | The cut-off with the best F1 on labelled earlier events. | **No**: it needs labels, which real data does not have. Evaluation only |
| `sequence_features` | Six change features per vendor for the forest: EWMA z-scores of amount and gap, CUSUMs of amount and of "sooner than usual", a 6-invoice amount trend, and the gap over the median earlier gap. Earlier events only (tested). | Yes |
| `narration_mode = "per_fact"` | Qwen rewords one fact at a time; every number must stay beside its own words (number-anchor check). | Yes, with a Qwen provider |
| `temporal_source = "ewma"`, `lstm.fit_share` | Evidence only: an EWMA forecaster instead of the LSTM; the LSTM trained on the earliest share of events. The LSTM stays the default. | Not intended |

## Quick start

Needs Python 3.11+ and Node 22+.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate    # or use the existing .venv
pip install -r requirements.txt
python scripts/seed.py            # users, dataset, pipeline, alerts, cases, notifications
uvicorn app.main:app --reload     # http://localhost:8000/docs

# Frontend, in a second terminal
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

With no `DATABASE_URL`, the API uses SQLite at `backend/afed.db`, so no setup is needed. In VS Code,
run the **AFED: API + frontend** launch configuration instead.

`seed.py` resets the database. It refuses to touch a non-SQLite database unless you pass `--reset-remote`.

## Demo accounts

On local SQLite the password for all of them is `afed1234`.

| Email | Role | Lands on |
|---|---|---|
| admin@afed.app | Admin | Dashboard |
| analyst@afed.app | Analyst | Data & runs |
| reviewer@afed.app | Reviewer | Alerts |
| viewer@afed.app | Viewer | Dashboard |

On a real database, seeding prints random passwords once instead. Production builds show no demo logins
unless `VITE_DEMO=1` is set, and then only the read-only Viewer.

| Page | Admin | Analyst | Reviewer | Viewer |
|---|---|---|---|---|
| Dashboard, Entities, Evaluation, Reports | ✅ | ✅ | ✅ | ✅ |
| Alerts, Alert Detail, Cases | act | view | act | read only |
| Data Upload, Model Settings | ✅ | ✅ | ❌ | ❌ |
| User & Role Management | ✅ | ❌ | ❌ | ❌ |

These are enforced by FastAPI dependencies on every router. Hiding links in the UI is only a convenience.

## Evaluation results

Real output of `python scripts/seed.py`: seed 42, 10,914 events, 276 injected anomalies. Every variant
reviews its own top 717 events, the same budget AFED used.

| Variant | ROC-AUC | Avg precision | P@50 | P@100 | P@200 | Precision | Recall | False-alarm rate |
|---|---|---|---|---|---|---|---|---|
| Global Isolation Forest | 0.614 | 0.036 | 0.02 | 0.04 | 0.03 | 0.04 | 0.09 | 6.50% |
| IF + entity features | 0.745 | 0.218 | 0.62 | 0.46 | 0.32 | 0.14 | 0.37 | 5.77% |
| LSTM + IF | 0.763 | 0.271 | 0.70 | 0.49 | 0.41 | 0.16 | 0.42 | 5.65% |
| **AFED fusion** | **0.983** | **0.575** | 0.92 | 0.67 | 0.53 | **0.35** | **0.91** | **4.39%** |

AFED raises 32.4% fewer false alarms than the global forest at the same budget.

| Recall by type | Global IF | IF + entity | LSTM + IF | AFED |
|---|---|---|---|---|
| amount_spike | 0.00 | 0.67 | 1.00 | 1.00 |
| bank_change | 0.07 | 0.07 | 0.07 | 1.00 |
| duplicate_invoice | 0.00 | 0.19 | 0.19 | 1.00 |
| frequency_burst | 0.00 | 0.84 | 0.94 | 0.90 |
| invoice_splitting | 0.10 | 0.97 | 0.97 | 1.00 |
| new_vendor_large | 0.33 | 0.48 | 0.37 | 1.00 |
| off_hours_approval | 0.30 | 0.26 | 0.37 | 0.85 |
| round_amount | 0.00 | 0.04 | 0.04 | 0.30 |
| rushed_approval | 0.11 | 0.11 | 0.15 | 1.00 |
| sod_violation | 0.04 | 0.00 | 0.00 | 1.00 |

### How to read these numbers

- **They are optimistic.** The red-flag rules target the same ten anomaly types the generator injects,
  so the rules score well almost by construction. Expect lower figures on real data. Real payment data
  has no labels, so AFED reports no accuracy for it.
- **The LSTM's value depends on the data, and the decision is open.** On the data above, removing the LSTM's
  error columns from the fusion's forest did better on all three seeds tried. A pre-registered ablation on data
  with real temporal structure (`backend/experiments/temporal_ablation.md`, results in
  `temporal_ablation_results.md`) found that the LSTM's errors raise recall on temporal anomalies on all five
  seeds, mostly billing-frequency changes, but at 13% more alerts. That failed the pre-registered criterion,
  so the recommendation is to keep the LSTM for the expected-vs-actual chart only. `lstm.in_forest` switches
  it; the default stays as the brief specifies until the supervisor decides. The same ablation found AFED
  catches only 10% to 15% of temporal anomalies either way, so sequence-level detection is the main open gap.

| Dataset seed | Mode | Alerts | Avg precision | Precision | Recall |
|---|---|---|---|---|---|
| 42 | Forecast (default) | 717 | 0.575 | 0.349 | 0.906 |
| 42 | Autoencoder | 713 | 0.579 | 0.355 | 0.917 |
| 42 | No LSTM | 680 | 0.588 | 0.387 | 0.953 |
| 7 | Forecast | 682 | 0.566 | 0.368 | 0.890 |
| 7 | No LSTM | 653 | 0.585 | 0.409 | 0.947 |
| 123 | Forecast | 654 | 0.561 | 0.361 | 0.897 |
| 123 | No LSTM | 627 | 0.585 | 0.402 | 0.958 |

- **Precision is 0.35**, so about two in three alerts are false alarms. The generator adds unlabelled
  look-alikes on purpose, such as genuine bulk orders and urgent approvals.
- **round_amount is the weak spot** at 0.30. A round amount alone rarely reaches Medium.
- **After a real recalibration, the numbers are no longer an independent test.** The weights have then been
  fitted to reviewer decisions about the same data. The Evaluation and landing pages say so when this applies.

## Four-model comparison

Every labelled run now stores Rule-based, Global Isolation Forest, LOF and AFED side by side, each at its own
alert threshold (`metrics.comparison`, shown by the API). The full study over seeds and datasets is
`backend/experiments/model_comparison.py`; results in `model_comparison_results.md`, figures in `experiments/figures/`.

Labelled synthetic data, seeds 42, 7 and 123, mean ± sd:

| Model | Accuracy | Precision | Recall | F1-Score |
|---|---|---|---|---|
| Rule-based (fixed threshold) | 0.969 ± 0.002 | 0.009 ± 0.008 | 0.002 ± 0.002 | 0.004 ± 0.003 |
| Global Isolation Forest only | 0.692 ± 0.003 | 0.038 ± 0.004 | 0.454 ± 0.052 | 0.070 ± 0.007 |
| LOF (contextual baseline) | 0.975 ± 0.000 | 0.559 ± 0.076 | 0.054 ± 0.001 | 0.098 ± 0.002 |
| **AFED (proposed)** | **0.957 ± 0.002** | **0.359 ± 0.010** | **0.898 ± 0.008** | **0.513 ± 0.009** |

Accuracy is high for doing nothing (97.5% of events are normal), so F1 and PR-AUC are the measures to read.
Balanced accuracy, the mean of recall and specificity, is fair under imbalance: Rule-based 0.498, Global IF
0.576, LOF 0.526, **AFED 0.928**. Flagging nothing scores 0.5.
No dataset has confirmed-fraud labels, so the fraud detection rate is not reported.

**On real data the picture is different.** With anomalies injected into real vendor histories (NSPCL, MPLADS,
Chicago, Delaware), every model scores F1 0.02 to 0.06. AFED is best on NSPCL and MPLADS, and Global IF on
Chicago and Delaware, where AFED's ranking is close to random (ROC-AUC 0.51 to 0.52). The real sets lack most
of the fields AFED's rules need, and AFED's thresholds were set on synthetic data. See
`experiments/real_data_evaluation_results.md`, which also re-tests the LSTM question on real data: keeping
its errors in the forest passed the pre-registered rule on 5 of 7 real datasets.

**Thresholds per dataset.** A pre-registered test (`experiments/threshold_calibration.md`, committed before it
ran) chose each real ledger's threshold on its earliest 60% of events and tested it on the latest 40%. It passed:
F1 rose on all four (MPLADS 0.023 to 0.105, Chicago 0.017 to 0.039, Delaware 0.024 to 0.058, NSPCL unchanged at
0.047), by cutting alerts 50% to 95%. Recall fell, so the gain is cheaper review, not better detection. In the app
this is what recalibration from reviewer decisions does for each deployment. The full report is `AFED.md`.

## Data

| Source | Use | Labels |
|---|---|---|
| `data/generate_synthetic.py` | Accuracy numbers: about 160 vendors, 11k invoices, 2.5% anomalies of 10 types | Yes |
| `data/generate_temporal.py` | The LSTM ablation: billing rhythms, drift, trends, 3 temporal anomaly types | Yes |
| Nine real datasets (NSPCL, MPLADS, BBMP, Delaware, SECOP, Chicago, OCDS) | `data/scripts/load_*.py`, catalogued in `DATASETS.md`, described in `data/DATA_CARD.md`. Load one into the app with `python scripts/seed.py --dataset nspcl` | No (injected anomalies for evaluation) |
| `data/download_public.py sf` | Demo: San Francisco vendor payments | No |
| `data/download_public.py chicago` | Demo: City of Chicago payments, excluding direct vouchers | No |

```bash
python data/download_public.py sf --limit 20000
python scripts/seed.py --csv data/public_sf.csv
```

The public sets have no approvals, bank accounts, vendor creation dates or invoice times, so the rules needing
those stay silent. Their amounts are US dollars, converted at the ECB reference rate of 93.92 (6 Nov 2026), the same as the dataset loaders, so the rupee limit
rules mean something. San Francisco publishes no payment date, so its source-update stamp stands in for one, and
date-based signals on that set are only indicative. `scripts/download_datasets.py` fetches the optional Hugging
Face sets into the repo-root `data/raw/`. It reads `HF_TOKEN` and asks in the terminal if a dataset needs one.
AFED itself does not use those sets.

**Upload schema.** Required: `event_id, vendor_id, amount, invoice_date`. Optional: `invoice_number, vendor_name,
category, department, approver_id, created_by, approval_date, processing_days, bank_account, vendor_created,
po_amount`. For evaluation: `is_anomaly` (0/1 or yes/no; anything else counts as unlabelled) and `anomaly_type`.
The upload page maps other column names onto these. A file can have up to 500,000 rows and 50 MB.

**Sample files.** The Data & runs page offers two files from `frontend/public/samples/`, so a demo never waits
for data. `nspcl_sample.csv` holds 5,745 real payments by 80 NSPCL vendors (2023 to 2026, unlabelled), built by
`data/scripts/make_samples.py` and shipped under NSPCL's reproduction-with-acknowledgement terms. It runs through
the same mapping and validation as any upload. `afed_template.csv` lists every column with two made-up rows.

**Automatic intake.** Another system can send invoices instead of a person uploading them. An Admin or Analyst
token posts `{"source": "SAP nightly export", "events": [{...}, ...]}` to `POST /upload/events`, with the template's
column names (up to 50,000 events and 20 MB per batch; a body that large is only read once its token checks out).
Unknown fields are refused, so a typo in an integration fails loudly. The batch is validated and run exactly like an upload; a `409` means a run is in progress and the
sender should retry. Events already stored are skipped, so resending a batch is safe. To see it working:

```bash
python scripts/send_events.py --batch 500 --every 20   # plays an accounting system, sending the NSPCL sample
```

**Dates.** ISO dates are read as they are. Numeric dates are read day first, the Indian convention, unless the
column proves it is month first; the validation report warns when a column could be either. `YYYYMMDD` is
understood. UTC offsets are dropped and the recorded clock time is kept, because off-hours rules mean local time.
Dates before 1990 or more than a year ahead count as invalid.

## Qwen narration

Facts are computed in `ml/explain.py` and never by a model. Qwen is shown only the finished fact sentences and
may only join them into two or three sentences. Its wording is refused, and the template shown instead, if it
adds a number, a word outside the facts and a short list of linking words, or an accusing term, or if it leaves
out a number from the main facts, or if the provider fails. The alert page says when Qwen's wording was refused.
Bank accounts are masked and uploaded identifiers are stripped of anything sentence-like first.

| Provider | Set up |
|---|---|
| `template` (default) | Nothing. Always works. |
| `local` | `pip install -r requirements-qwen.txt`. Downloads `Qwen/Qwen2.5-1.5B-Instruct` (about 3 GB) and runs it in half precision on the GPU if there is one. Fits on an 8 GB machine. |
| `ollama` | `ollama pull qwen2.5:3b`, then set `OLLAMA_URL` if it is not on localhost. |
| `hf_api` | `HF_TOKEN`. Model from `QWEN_HF_MODEL`, default `Qwen/Qwen2.5-7B-Instruct`. |

`QWEN_PROVIDER` sets the initial value; after that, use **Model settings**. A run narrates its top 50 alerts
with Qwen, stops trying after three failures in a row, and uses the template for the rest. Any alert can be
re-narrated on demand, in English or Hindi.

**Tested** (`experiments/narration_evaluation.md`, pre-registered): on 100 held-out alerts the local 1.5B model's
wording passed for 46 English and 61 Hindi narrations. An independent NLI judge found 43 of the 46 accepted
English ones entailed by their facts; one real error got through (a "which" attaching a percentage to the wrong
amount). Refused narrations were about six times as likely to be unsupported or contradicted. The template stays
the default; see `AFED.md`, section 10.9.

## Tests

```bash
cd backend
python tests/test_afed.py     # parsing, baselines, rules, fusion, recalibration, grounding guard
python tests/test_api.py      # access matrix, workflows, hostile input, exports, on a throwaway database
python experiments/temporal_ablation.py      # the pre-registered LSTM ablation, about 90 seconds
python experiments/real_data_evaluation.py   # AFED on real data with injected anomalies (long; resumable)
python experiments/model_comparison.py       # Rule-based vs Global IF vs LOF vs AFED, with figures
python experiments/threshold_calibration.py  # pre-registered per-dataset threshold test on a later period
TEST_DATABASE_URL=postgresql://... JWT_SECRET=<32+ characters> python tests/test_api.py    # the same on Postgres
```

The browser smoke test signs in as each role through the real form, opens every page that role may reach,
checks the refused ones, and runs the sample upload. It needs the app running on demo data:

```bash
cd frontend
pip install -r e2e/requirements.txt && playwright install chromium
python e2e/smoke.py --url http://localhost:5173
```

## Deploy

**Supabase (database).** Run `supabase/schema.sql` in the SQL editor, then use the connection string as `DATABASE_URL`.
The API connects as the table owner and enforces roles itself. RLS, keyed on `profiles.role`, is the second layer
for anything reaching the tables through the Supabase REST API. The `users` table has no policy, so password hashes
stay unreachable that way, and column grants keep labels and full bank accounts API-only. Seed once with
`python scripts/seed.py --reset-remote`, and keep the passwords it prints. Reseeding empties tables rather than
dropping them, so the policies survive.

**Render (backend).** `render.yaml` defines the service. Set `DATABASE_URL` and `CORS_ORIGINS`. torch needs more memory
than the free plan offers. The `models_store` folder is lost on redeploy unless you attach a disk; metrics stay in the database.

**Vercel (frontend).** `vercel.json` builds `frontend/`. Set `VITE_API_URL` to the backend URL and add the Vercel URL to
`CORS_ORIGINS`. Vercel cannot read environment variables in rewrites, so if you rely on the `/api` rewrite instead,
edit its domain in `vercel.json`.

**Docker.** `JWT_SECRET=$(openssl rand -hex 32) docker compose up --build`, then open http://localhost:5173. The first
start seeds a volume. Ports stay on this machine, because the demo accounts have a published password. To expose them,
set `AFED_BIND=0.0.0.0` and `PREVIEW_ALLOWED_HOSTS`, and change those passwords first.

`JWT_SECRET` must be at least 32 characters with a real database: the API refuses to start otherwise.

## Decisions made along the way

- **Runs score the full history.** Uploads add to stored events and everything is rescored, since baselines need it.
  New rows are stored in the same commit as the results, so a failed run leaves nothing behind.
- **Reviewed, assigned and closed-case alerts survive every rerun,** and are refreshed to match their event, even at
  Low. Only untouched Pending alerts are removed when they stop qualifying. The audit log lists which.
- **Entity deviation counts only risky directions** (bigger, sooner, faster) beyond 2 robust sigmas. Counting all
  deviation flagged 15% of events.
- **`rule_score` and `flag_count` also feed the forest**, because ten sparse flag columns alone are rarely drawn.
- **A case needs 2+ alerts within 30 days, or one Critical.** A case per alert would only repeat the queue. A case
  emptied by a rerun is removed, or closed if someone has worked on it.
- **Baselines are expanding**, using all earlier events. A long-lived vendor's old prices never age out.
- **No mail service.** Invites and resets show a temporary password to the admin, valid until changed, and
  "forgot password" notifies admins, at most once an hour per account. A changed password ends older sessions.
- **Seeding adds 60 simulated reviews** from the synthetic labels, so the feedback charts have data. The dashboard,
  evaluation page, activity timelines, PDFs and CSVs all disclose them. Unlabelled datasets get none.
- **Recalibration ignores simulated reviews.** They are copies of the evaluation labels, and fitting to them would
  tune the model on its own answer key. On fresh demo data it therefore asks for 20 real reviews first.
- **Recalibration is checked on reviews it did not see.** It searches on the older 70% of decisions and keeps the
  result only if F1 on the newest 30% does not fall. A separate classifier trained on reviews would need a few
  hundred real decisions to train and test honestly; until those exist, it would be guesswork.
- **Bulk decisions only touch Pending alerts,** so one person's decision is never overwritten in passing.
- **Reviewers never see labels.** `is_anomaly` is left out of the alert API, and invoice numbers carry no hint of it.
- **PDFs are English only.** The built-in fonts have no Devanagari. They list the newest 5,000 alerts and say so if
  there are more; CSV exports have no cap.
- **Recalibration applies on the next run** and can overfit a few reviews, so check its suggested weights.

## Known limits

- **Departments are not scored.** Events are compared with vendor, peer and population history. Department pages
  are reporting views, so a department spending far above its norm through normal-looking vendors raises no signal.
- **Contamination does not change scores.** It sets the forest's own cut-off, while risk uses the forest's ranking.
  It is exposed because the brief asks for it, and Settings says what it does.
- The duplicate rule, as specified, flags vendors with near-identical amounts billed within 14 days, such as a
  fixed weekly fee.
- The login lockout is per process and resets on restart. Starting a run is also guarded per process, so running
  more than one API worker would need a database-level guard.
- The JWT sits in `localStorage`. An httpOnly cookie would resist XSS better.
- Detection runs in a background thread: one at a time, and a restart marks the active run as failed.
- Dates that could be read either way are assumed day first. Convert a month-first file to `YYYY-MM-DD`.

## Layout

```
backend/   app/ (API)  ml/ (pipeline)  data/ (datasets)  scripts/ (seed)  models_store/  tests/
frontend/  React 18, Vite, TypeScript, Tailwind, Recharts
supabase/  schema.sql (tables, RLS and column grants)
data/raw/  optional Hugging Face downloads, unused by AFED
```
