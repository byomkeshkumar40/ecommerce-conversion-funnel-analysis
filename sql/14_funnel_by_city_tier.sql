-- Funnel by city_tier. Unit = SESSION. Every rate's denominator is stated in its column name:
--   *_rate_of_sessions = / all sessions in the segment;  step_* = / previous stage.
SELECT city_tier AS segment, COUNT(*) AS sessions,
       SUM(reached_view) AS product_views, SUM(reached_cart) AS carts,
       SUM(reached_checkout) AS checkouts, SUM(reached_payment) AS payment_attempts,
       SUM(reached_purchase) AS purchases,
       ROUND(1.0 * SUM(reached_view)     / COUNT(*), 4) AS view_rate_of_sessions,
       ROUND(1.0 * SUM(reached_cart)     / SUM(reached_view), 4)     AS step_view_to_cart,
       ROUND(1.0 * SUM(reached_checkout) / SUM(reached_cart), 4)     AS step_cart_to_checkout,
       ROUND(1.0 * SUM(reached_payment)  / SUM(reached_checkout), 4) AS step_checkout_to_payment,
       ROUND(1.0 * SUM(reached_purchase) / SUM(reached_payment), 4)  AS step_payment_to_purchase,
       ROUND(1.0 * SUM(reached_purchase) / COUNT(*), 4) AS purchase_rate_of_sessions
FROM session_funnel GROUP BY city_tier ORDER BY purchase_rate_of_sessions DESC;
