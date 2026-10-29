-- session_funnel: ONE ROW PER SESSION, the base for every funnel query.
--
-- Stage rule (strict, chronological): a session "reaches" a stage only if it
--   (a) has that event type AND (b) reached the previous stage AND
--   (c) the FIRST occurrence of the stage's event is not earlier than the
--       first occurrence of the previous stage's event.
-- Using MIN(timestamp) per event type per session means repeated product views,
-- multiple add_to_cart events, payment retries and duplicated event rows can
-- never inflate the count: each session contributes at most 1 per stage.
-- Sessions with a purchase event but no checkout event (injected anomaly) drop
-- out of the strict funnel at checkout; has_purchase_event keeps them visible.
DROP VIEW IF EXISTS session_funnel;
CREATE VIEW session_funnel AS
WITH t AS (
  SELECT s.session_id, s.customer_id, s.session_start, s.device, s.channel, s.customer_type,
         c.city_tier,
         MIN(CASE WHEN e.event_type = 'product_view'     THEN e.event_ts END) AS t_view,
         MIN(CASE WHEN e.event_type = 'add_to_cart'      THEN e.event_ts END) AS t_cart,
         MIN(CASE WHEN e.event_type = 'checkout_start'   THEN e.event_ts END) AS t_checkout,
         MIN(CASE WHEN e.event_type = 'payment_attempt'  THEN e.event_ts END) AS t_payment,
         MIN(CASE WHEN e.event_type = 'purchase_complete' THEN e.event_ts END) AS t_purchase
  FROM sessions s
  JOIN customers c ON c.customer_id = s.customer_id
  LEFT JOIN events e ON e.session_id = s.session_id
  GROUP BY s.session_id),
f AS (
  SELECT *,
    CASE WHEN t_view IS NOT NULL AND t_view >= session_start THEN 1 ELSE 0 END AS reached_view
  FROM t),
g AS (
  SELECT *,
    CASE WHEN reached_view = 1 AND t_cart IS NOT NULL AND t_cart >= t_view THEN 1 ELSE 0 END AS reached_cart
  FROM f),
h AS (
  SELECT *,
    CASE WHEN reached_cart = 1 AND t_checkout IS NOT NULL AND t_checkout >= t_cart THEN 1 ELSE 0 END AS reached_checkout
  FROM g),
i AS (
  SELECT *,
    CASE WHEN reached_checkout = 1 AND t_payment IS NOT NULL AND t_payment >= t_checkout THEN 1 ELSE 0 END AS reached_payment
  FROM h)
SELECT session_id, customer_id, session_start, DATE(session_start) AS session_date,
       device, channel, customer_type, city_tier,
       reached_view, reached_cart, reached_checkout, reached_payment,
       CASE WHEN reached_payment = 1 AND t_purchase IS NOT NULL AND t_purchase >= t_payment
            THEN 1 ELSE 0 END AS reached_purchase,
       CASE WHEN t_purchase IS NOT NULL THEN 1 ELSE 0 END AS has_purchase_event
FROM i;
