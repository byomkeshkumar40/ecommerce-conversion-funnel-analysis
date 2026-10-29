-- Overall funnel. Unit = SESSION. Denominators: step conversion = previous stage;
-- overall conversion = all sessions; drop-off = 1 - step conversion.
-- Also returns unique visitors (distinct customer_id with >=1 session) on the first row.
WITH totals AS (
  SELECT COUNT(*) AS sessions, COUNT(DISTINCT customer_id) AS visitors,
         SUM(reached_view) AS product_view, SUM(reached_cart) AS add_to_cart,
         SUM(reached_checkout) AS checkout_start, SUM(reached_payment) AS payment_attempt,
         SUM(reached_purchase) AS purchase
  FROM session_funnel),
stages AS (
  SELECT 1 AS stage_no, 'session_start'    AS stage, sessions       AS n, sessions       AS prev_n, sessions AS all_n, visitors FROM totals UNION ALL
  SELECT 2, 'product_view',     product_view,    sessions,       sessions, visitors FROM totals UNION ALL
  SELECT 3, 'add_to_cart',      add_to_cart,     product_view,   sessions, visitors FROM totals UNION ALL
  SELECT 4, 'checkout_start',   checkout_start,  add_to_cart,    sessions, visitors FROM totals UNION ALL
  SELECT 5, 'payment_attempt',  payment_attempt, checkout_start, sessions, visitors FROM totals UNION ALL
  SELECT 6, 'purchase_complete', purchase,       payment_attempt, sessions, visitors FROM totals)
SELECT stage_no, stage, n AS sessions_reaching_stage,
       ROUND(1.0 * n / prev_n, 4)       AS step_conversion,
       ROUND(1.0 * n / all_n, 4)        AS overall_conversion,
       ROUND(1.0 - 1.0 * n / prev_n, 4) AS dropoff_from_previous,
       prev_n - n                       AS sessions_lost,
       CASE WHEN stage_no = 1 THEN visitors END AS unique_visitors
FROM stages ORDER BY stage_no;
