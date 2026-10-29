# E-commerce Conversion Funnel & Drop-off Analysis — Business Report

> **Synthetic data.** Every number below comes from a generated dataset (seed 42, 95,631 sessions, 1 Jan – 30 Jun 2025). The generator encodes assumptions about devices, channels, etc., so the segment gaps below are *what the method finds in data built with those gaps*; they are not evidence about real shoppers. No experiment has been run and no business impact is claimed. Figures are reproducible via `python -m src.analysis` and the SQL in `sql/`; both paths were reconciled by automated tests.

## 1. Executive summary
- 95,631 sessions from 60,000 visitors produced 4,955 strictly-ordered purchase sessions: **5.18%** session-level conversion (95% CI 5.04%–5.32%). Customer-level conversion is higher (**7.89%** of customers bought at least once) because customers have 1.59 sessions on average.
- The biggest absolute loss is **product view → add-to-cart** (67,907 sessions, 84.1% of viewers). Among purchase-intent stages, **cart → checkout** loses 45.5% and **checkout → payment attempt** loses 26.8%; **payment attempt → purchase** loses only 3.4%.
- **Mobile** (62% of sessions) converts 4.28% vs desktop 6.80%; the gap is widest at checkout → payment (68.5% vs 80.1%).
- Returning customers convert 7.17% vs 4.00% for new; email (7.48%) and direct (6.54%) lead, social (3.34%) and paid search (4.00%) trail.
- Payment friction is visible but secondary: 417 sessions had a failed attempt, 58.5% of them still bought. One week (14 Apr) shows payment→purchase of 86.9% vs a 96.8% weekly median (see §5 caveat: this was a planted scenario).

## 2. Business problem
The business sees heavy drop-off before purchase and needs to know where it happens, whether it varies by segment, and what to investigate first.

## 3. Dataset and methodology
Synthetic event-level data: 60,000 customers, 95,631 sessions, 356,321 events, 4,967 orders, 600 products, 6 categories (`docs/DATA_DICTIONARY.md`). Unit of analysis is the **session** unless stated. 12 purchasing sessions with a deleted `checkout_start` and 1,419 duplicate events were injected deliberately and are reported, not hidden (`reports/data_quality_report.md`).
Methods: SQL (SQLite) and independent pandas code compute the same metrics; 36 automated tests include SQL↔pandas reconciliation. Segment gaps carry Wilson 95% CIs and two-proportion z-tests. Tests are descriptive and unadjusted for multiple comparisons.

### Reconciling orders, purchases and conversion
| Quantity | Value | Numerator | Denominator |
|---|---:|---|---|
| Purchase-complete event rows | 4,986 | rows | – (19 are injected duplicates) |
| Orders | 4,967 | distinct sessions with an order | – (one order per session) |
| Strict purchases | 4,955 | sessions that passed the full chronological chain | – |
| Orders − strict purchases | 12 | the 12 injected sessions missing `checkout_start` | – |
| **Session conversion** | **5.18%** | 4,955 strict purchase sessions | 95,631 sessions |
| Naive orders ÷ sessions | 5.19% | 4,967 orders | 95,631 sessions (not used; includes the 12 anomalies) |
| Customer conversion | 7.89% | 4,736 customers with a strict purchase | 60,000 customers |

## 4. Funnel metric definitions
| Metric | Formula | Denominator |
|---|---|---|
| Stage reached | event exists, previous stage reached, first timestamp ≥ previous stage's | – |
| Step conversion | sessions at stage ÷ sessions at previous stage | previous stage |
| Overall conversion | sessions at stage ÷ all sessions | all sessions |
| Drop-off | 1 − step conversion | previous stage |
| Cart abandonment | carted sessions without purchase ÷ carted sessions | sessions with cart |
| Checkout abandonment | checkout sessions without purchase ÷ checkout sessions | sessions at checkout |
| Customer conversion | customers with ≥1 purchase session ÷ customers with ≥1 session | customers |

## 5. Verified findings (observed)
| Stage | Sessions | Step conv. | Overall |
|---|---:|---:|---:|
| Session start | 95,631 | – | 100% |
| Product view | 80,758 | 84.45% | 84.45% |
| Add to cart | 12,851 | 15.91% | 13.44% |
| Checkout start | 7,008 | 54.53% | 7.33% |
| Payment attempt | 5,128 | 73.17% | 5.36% |
| Purchase | 4,955 | 96.63% | 5.18% |

- Cart abandonment **61.4%** (of 12,851); checkout abandonment **29.3%** (of 7,008); payment-stage abandonment 3.4% (of 5,128).
- Repeat purchase: 209 of 4,748 purchasing customers (4.4%) bought again, on average 16.7 days after the first order. This is a **lower bound** (6-month window, right-censoring).
- Payment methods (attempt-level failure): card 14.0%, netbanking 12.5%, UPI 8.4%, wallet 4.3%, COD 1.1%.
- Checkout friction indicators (sessions that started checkout): guest checkout reaches payment 65.6–66.0% vs account 75.2–79.3%. Among account users, fee-charged checkouts reach payment 75.2% vs 79.3% free-shipping; among guests there is no gap.
- Weekly payment→purchase was 86.9% in the week of 14 Apr 2025 (214 attempting sessions) vs a 96.8% median. **Caveat:** the generator deliberately lowers UPI success that week, so this is a check that the analysis can surface a planted incident, not a discovery.
- Category view→cart ranges from 14.0% (Grocery) to 10.4% (Electronics); cart→purchase is similar across categories (36–40%). Category rows overlap and are not additive.

## 6. Segment insights (observed associations)
| Segment | Sessions | Purchase rate (95% CI) |
|---|---:|---|
| Desktop | 28,572 | 6.80% (6.52–7.10) |
| Tablet | 7,718 | 6.10% (5.59–6.66) |
| Mobile | 59,341 | 4.28% (4.12–4.45) |
| Returning | 35,631 | 7.17% (6.90–7.44) |
| New | 60,000 | 4.00% (3.85–4.16) |
| Email / Direct | 8,971 / 19,897 | 7.48% / 6.54% |
| Referral / Organic | 10,587 / 24,472 | 5.21% / 5.12% |
| Paid search / Social | 18,155 / 13,549 | 4.00% / 3.34% |
| City tier 1 / 2 / 3 | 33,237 / 38,479 / 23,915 | 5.25% / 5.21% / 5.04% |

Device mix is almost identical for new and returning customers, and the desktop > mobile gap holds within each customer type (new 5.28% vs 3.28%; returning 9.32% vs 5.98%), so device is not simply proxying for customer type here. Channel, device and customer type were not modelled jointly; interactions are untested.

## 7. Recommendations (prioritised; hypotheses, not proven causes)
1. **Investigate mobile checkout → payment** (68.5% vs 80.1% desktop) with session recordings and form analytics. This is the widest device gap at any single funnel step.
2. **Add daily payment-method success monitoring** with alerting; method gaps and one anomalous week are visible, and the effort is low.
3. **Review guest-checkout flow**; guest sessions progress to payment ~10–13 points less often than account sessions.
4. **Review traffic quality for social and paid search** before changing the site; lower conversion may reflect intent, not friction.

## 8. Experiment proposals (none executed)
| | A. Free-shipping progress bar | B. Streamlined mobile guest checkout | C. Alternate-method prompt after failure |
|---|---|---|---|
| Hypothesis | Showing progress to free shipping raises cart→checkout | Fewer fields on mobile raises checkout→payment | Suggesting another method recovers failed payments |
| Target population | Carts below the free-shipping threshold | Mobile sessions at checkout, guest | Sessions with ≥1 failed payment attempt |
| Primary metric | Cart→checkout rate | Checkout→payment rate | Recovery rate (purchase after a failure; 58.5% today) |
| Guardrails | AOV, returns, page latency | Payment failure rate, support contacts | Duplicate-charge reports, COD share |
| Expected mechanism | Lower perceived fee, nudge to threshold | Lower effort and drop-off at form | Removes dead end after decline |
| Measurement | User-level randomised A/B, two-proportion test, pre-computed sample size | Same | Session-level randomisation among failed sessions |

## 9. Limitations
Synthetic data and coded assumptions; associations only (no causal identification); segment overlap/confounding untested beyond one cross-check; shipping fee unobserved for non-checkout carts; `customer_type` left-censored; no session end times; no prices/discounts/inventory; repeat purchase right-censored; p-values unadjusted for multiple comparisons.

## 10. Next steps
Apply the pipeline to a real public dataset; add a joint (logistic-regression) model of device × customer type × channel; add time-to-purchase and funnel-by-cohort analysis; size experiments with a power calculation; add an optional Power BI view only if a real `.pbix` can be built and tested.
