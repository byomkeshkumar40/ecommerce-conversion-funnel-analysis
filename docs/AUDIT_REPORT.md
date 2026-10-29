# Final Quality Audit (pre-publication)

Audit date: 2026-10-29. Everything marked PASS was executed in this audit; nothing is claimed beyond that.

## Results
| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Folder structure / required files | PASS | All listed files present (README, requirements, data, sql, notebooks, src, dashboard, reports, tests, screenshots, docs) |
| 2 | Regenerate data, seed 42 | PASS | Deleted `data/raw`, regenerated; all 6 CSVs byte-identical (`cmp`) to the previous run |
| 3 | Re-run SQL, analysis, validation | PASS | 13 queries ran; FK check clean; `src.validate` 0 FAIL, 3 WARN (documented injected anomalies); `src.analysis` ran |
| 4 | Automated tests | PASS | `pytest`: 36 passed in ~35 s |
| 5 | Orders / purchases / conversion reconciliation | PASS | See below |
| 6 | Dashboard = SQL = pandas | PASS | Dashboard KPIs tested equal to pandas (`AppTest`, incl. device, date, customer-type filters); pandas tested equal to SQL on every query. SQL↔dashboard is transitive, not a direct test |
| 7 | Dashboard review (3 pages) | PASS with fixes | Screenshots of pages 1–2 inspected visually. Fixed: funnel labels lacked thousands separators; one recommendation overstated ("largest pool lost"). Page 3 lower sections reviewed in code and via AppTest, not visually |
| 8 | Numerical claims in README / report | PASS with fixes | Every figure re-derived from fresh outputs (funnel, segments, CIs, categories, payment, checkout friction, repeat, weekly dip). Fixed: "largest pool of sessions lost" claim; test count updated 35→36 |
| 9 | Disclosure of synthetic data, anomalies, planted patterns | PASS | README header, report banner, DATA_DICTIONARY (anomalies and injected scenarios), dashboard sidebar |
| 10 | PROJECT_EXPLANATION beginner readability | WARNING | Reviewed by me for structure and jargon; not tested with a real beginner |
| 11 | Placeholders / broken links / unused files | PASS | No TODO/placeholder text; all README links resolve; `.pytest_cache` removed |
| 12 | requirements reproducible | PASS | Exact pins; created a brand-new venv, `pip install -r requirements.txt`, ran `pytest`: 36 passed. Optional extras are in `requirements-optional.txt`
| 13 | README has install/run/validate/dashboard steps | PASS | Present; commands were executed individually (not the README's literal copy-paste in a clean shell) |
| 14 | Credentials / local paths / junk | PASS | grep for `/Users/`, username, email, key/password/token: no hits. `.venv`, caches, SQLite DB git-ignored |
| 15 | This report | PASS | |

## Reconciliation (check 5)
- 4,986 `purchase_complete` event rows → 4,967 distinct sessions (19 rows are injected duplicates).
- **Orders = 4,967** (one per session).
- **Strict purchases = 4,955**: sessions passing the full chronological chain. The 12 missing sessions are exactly those with an injected deleted `checkout_start`.
- **5.18% = 4,955 ÷ 95,631 sessions.** Orders ÷ sessions would be 5.19%; not used because it includes the 12 anomalies.
- Customer conversion 7.89% = 4,736 customers with a strict purchase ÷ 60,000 customers.

## Changes made
Report: added reconciliation table, fixed overstated wording. Dashboard: funnel label format, recommendation wording. Tests: added date/customer-type filter test (35→36). Added `requirements-optional.txt`, `scripts/take_screenshots.py`, this report; README optional-install text and Python-version note; screenshots re-captured.

## Not tested / remaining warnings
- Python versions other than 3.14; Windows/Linux; browsers other than headless Chromium; PostgreSQL.
- Screenshots capture only the first screen of each page.
- Weekly trend week of 2024-12-30 is partial (data starts 1 Jan); hidden by default in the dashboard.
- p-values are unadjusted for multiple comparisons (disclosed).
- Resume bullets are intentionally not part of the repository; the author prepares them after independent review.
- Repository is not a git repo; nothing was committed or published. Raw CSVs are 31 MB, so decide whether to commit them.

## Publication-prep addendum
Raw CSVs and the SQLite DB are git-ignored and regenerated from the seeded generator. A fresh-clone reproduction (clone → new venv → install → generate → validate → SQL → analysis → pytest) was run before the first commit; result: PASS. From a clean `git clone` into a new directory and venv, `generate_data`, `validate` (exit 0), `run_sql`, `analysis` and `pytest` (36 passed) all ran; regenerated CSVs were byte-identical to the originals; the dashboard server responded HTTP 200; and the regenerated tracked reports left `git status` clean.
