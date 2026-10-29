# Project Explanation (for a beginner)

## 1. The business problem
Shoppers browse, add items to a cart, start checkout, try to pay, and sometimes complete the purchase. At each step some leave. The project measures **how many leave at each step and who they are**, so a team can decide what to investigate. It does *not* know *why* they leave.

## 2. The dataset (synthetic!)
Made by `src/generate_data.py` with a random seed so you get identical data each time. Because the data is simulated, the patterns (e.g. mobile converts worse) were put there by the generator's rules — treat results as a demonstration of method.
- `customers` — who. `sessions` — one visit (device, channel, new/returning). `events` — what happened in a visit (6 event types). `orders` — completed purchases. `products` — category and price.
- **Unit of analysis = session**. One customer can have several sessions, so "customer conversion" (7.89%) differs from "session conversion" (5.18%).
- Two deliberate flaws were injected: duplicate event rows and 12 purchases lacking a checkout event, to practise data-quality handling.

## 3. Funnel formulas
- **Stage reached**: a session counts at stage *k* only if it reached stage *k−1* and the event's first timestamp is not earlier. Using *first* timestamp and one row per session stops repeated views/retries from inflating counts.
- **Step conversion** = sessions at stage ÷ sessions at previous stage (e.g. checkout → payment = 5,128 ÷ 7,008 = 73.2%).
- **Overall conversion** = sessions at stage ÷ all sessions (purchase: 4,955 ÷ 95,631 = 5.18%).
- **Drop-off** = 1 − step conversion. **Cart abandonment** = carted sessions that never purchased ÷ carted sessions (61.4%).
Always ask: *what is the denominator?*

## 4. What each SQL file does (`sql/`)
| File | Purpose |
|---|---|
| 00_schema | tables, primary/foreign keys, CHECK constraints |
| 01_views | `session_funnel` view: one row per session, 0/1 stage flags (CTE chain, `MIN(CASE…)` conditional aggregation) |
| 10_funnel_overall | stage counts, step & overall conversion, drop-off, unique visitors |
| 11–14 | same funnel by device, channel, customer type, city tier |
| 15_category_funnel | distinct session×category view→cart→purchase (rows overlap) |
| 16_weekly_trend | weekly conversion, `LAG()` for week-over-week change |
| 17_abandonment | cart / checkout / payment abandonment, overall and by segment |
| 18_customer_level | customer vs session conversion |
| 19_repeat_purchase | `ROW_NUMBER()` + `LAG()` for 2nd-order gap |
| 20–22 | payment failure by method, guest × shipping-fee checkout table, retry recovery |
Window functions appear only where they are the natural tool (trend, order sequence).

## 5. Important Python functions (`src/metrics.py`)
- `build_session_funnel` — the pandas twin of the SQL view (first timestamp per event type, boolean chain).
- `funnel_table`, `segment_table` — counts, rates, Wilson CI, p-value vs rest.
- `wilson_ci`, `two_prop_p_value` — uncertainty for a proportion; test for a difference between two.
- `category_funnel`, `payment_method_failures`, `retry_recovery`, `checkout_friction`, `weekly_trend`, `customer_level`, `repeat_purchase`.
- `apply_filters` — what the dashboard sidebar calls. `src/validate.py::run_checks` — all data-quality checks.

## 6. Dashboard logic (`dashboard/app.py`)
Sidebar filters (date, device, channel, customer type, city tier) → `apply_filters` → every chart/table recomputed from `src/metrics.py`. Because tests compare those functions to SQL and compare dashboard KPIs to them, the three agree. Page 3's findings text is generated from the filtered data; recommendations and experiments are labelled analyst judgement.

## 7. Findings and their denominators
See `reports/business_report.md`. Example: "mobile converts 4.28%" = 2,540 purchase sessions ÷ 59,341 mobile sessions, 95% CI 4.12–4.45%.

## 8. Limitations
Synthetic data; association ≠ cause; segments overlap (device × customer type × channel); shipping fee only known after checkout starts; "new" means first seen in the window; repeat purchase is a lower bound; planted UPI incident means that finding validates the method rather than discovering anything.

## 9. How to learn it (suggested order)
1. Read `docs/DATA_DICTIONARY.md`. 2. Run `python -m src.generate_data` and open `events.csv` for one session. 3. Read `sql/01_views.sql` line by line, then `10_funnel_overall.sql`. 4. Read `build_session_funnel` and find the SQL equivalent line by line. 5. Run `pytest -v` and read `tests/test_metrics.py` (tiny dataset, answers checkable by hand). 6. Break something on purpose (e.g. change `>=` to `>` in the view) and watch which tests fail. 7. Explore the dashboard.

## 10. Interview questions (answers deliberately not provided)
1. Why is the session, not the event, the unit of the funnel, and how does the SQL avoid double counting?
2. What is the difference between step conversion and overall conversion, and which denominator does each use?
3. Why can customer-level conversion exceed session-level conversion?
4. A session has a purchase event but no checkout event. How does your funnel treat it, and why not just delete it?
5. How did you prove your SQL and Python give the same answers?
6. Mobile converts less than desktop. What can and can't you conclude, and what would you check next?
7. Why is the category table not additive?
8. How would you design an A/B test for a mobile guest-checkout change — metric, guardrails, unit of randomisation?
9. Why is the repeat-purchase rate a lower bound?
10. The data is synthetic. What does this project still demonstrate, and what would change with real data?
