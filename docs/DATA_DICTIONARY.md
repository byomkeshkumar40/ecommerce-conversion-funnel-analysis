# Data Dictionary

> **All data is synthetic.** It is produced by `src/generate_data.py` with a fixed seed (42). No real customer, company or platform is represented. Relationships between device, channel, customer type, guest checkout, shipping fee and payment method are *assumptions coded into the generator*, so findings show analytical method, not real-world behaviour.

## Units of analysis
| Unit | Definition | Used for |
|---|---|---|
| **Event** | one row in `events` | payment-attempt failure rates |
| **Session** | one visit (`sessions.session_id`) | **all funnel and conversion metrics (default)** |
| **Customer** | persistent visitor id (`customer_id`) | unique visitors, customer-level conversion, repeat purchase |
| **Order** | one row in `orders` (max one per session) | order value, repeat purchase |

## Timestamps
`YYYY-MM-DD HH:MM:SS`, text, treated as one local time zone (IST) with no offset; compare lexicographically in SQL. Window: 2025-01-01 to 2025-06-30 (sessions starting on 30 June can have events just after midnight).

## Tables, keys
**customers** — PK `customer_id`. `city_tier` (tier_1/2/3), `first_seen_date` (date of first session in the dataset), `first_touch_channel`.
**products** — PK `product_id`. `category` (6), `price` (INR).
**sessions** — PK `session_id`; FK `customer_id → customers`. `session_start`; `customer_type` = `new` if this is the customer's first session *in the dataset*, else `returning`; `device` (mobile/desktop/tablet); `channel` (organic_search, paid_search, social, email, direct, referral).
**events** — PK `event_id`; FK `session_id → sessions`, `customer_id → customers`, `product_id → products` (nullable). `event_type` ∈ session_start, product_view, add_to_cart, checkout_start, payment_attempt, purchase_complete. Type-specific nullable columns: `quantity` (add_to_cart); `guest_checkout` (0/1), `shipping_fee` (INR) on checkout_start; `payment_method`, `payment_status` (success/failed), `failure_reason` on payment_attempt.
**orders** — PK `order_id`; `session_id` UNIQUE FK; FK `customer_id`. `order_ts`, `order_value` (items + shipping), `shipping_fee`, `payment_method`, `payment_attempts`.
**order_items** — (`order_id`, `product_id`) FKs; `quantity`, `unit_price`.

## Funnel stage definitions (strict)
A session *reaches* a stage only if the event exists, the previous stage was reached, and the **first** timestamp of the event is ≥ the first timestamp of the previous stage. Stages: session → product_view → add_to_cart → checkout_start → payment_attempt → purchase_complete.

## Deliberately injected anomalies (so validation has something to find)
1. **Duplicate events** — 0.4% of event rows are copied with a new `event_id` (1,419 rows).
2. **Purchase without checkout** — 12 purchasing sessions had their `checkout_start` row removed. They stay in `orders` and as `purchase_complete` events but fail the strict chain, so orders (4,967) − strict purchases (4,955) = 12.

## Injected scenarios (disclosed so nobody mistakes them for discoveries)
- UPI success rate drops to 55% between 2025-04-14 and 2025-04-20 (gateway incident).
- Conversion multipliers: desktop > tablet > mobile; returning > new; email/direct > social/paid; guest checkout and shipping fees lower progression; electronics add-to-cart is lowest, grocery highest; slight upward trend and weekend lift.

## Limitations
- Synthetic: no real seasonality, bots, ad spend, price changes, stock-outs or page-performance data.
- `customer_id` is a persistent id; cross-device identity, cookie churn and anonymous visitors are not modelled.
- `customer_type` is left-censored: customers existing before 2025-01-01 appear as `new` at their first observed session.
- Shipping fee is only recorded at `checkout_start`, so it is unobserved for carts that never reached checkout.
- Repeat-purchase metrics are lower bounds (6-month window, right-censoring).
- Sessions have no explicit end time; "abandonment" means the last observed funnel stage, not a confirmed exit.
