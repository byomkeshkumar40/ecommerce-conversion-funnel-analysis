-- Cart & checkout abandonment. Unit = SESSION.
-- cart abandonment     = sessions that added to cart but did not purchase / sessions with a cart
-- checkout abandonment = sessions that started checkout but did not purchase / sessions that started checkout
-- payment abandonment  = sessions that attempted payment but did not purchase / sessions that attempted payment
SELECT 'overall' AS segment_type, 'all' AS segment,
       SUM(reached_cart) AS carts, SUM(reached_cart) - SUM(reached_purchase) AS carts_abandoned,
       ROUND(1.0 - 1.0 * SUM(reached_purchase) / SUM(reached_cart), 4) AS cart_abandonment_rate,
       SUM(reached_checkout) AS checkouts,
       ROUND(1.0 - 1.0 * SUM(reached_purchase) / SUM(reached_checkout), 4) AS checkout_abandonment_rate,
       SUM(reached_payment) AS payment_attempts,
       ROUND(1.0 - 1.0 * SUM(reached_purchase) / SUM(reached_payment), 4) AS payment_abandonment_rate
FROM session_funnel
UNION ALL
SELECT 'device', device, SUM(reached_cart), SUM(reached_cart) - SUM(reached_purchase),
       ROUND(1.0 - 1.0 * SUM(reached_purchase) / SUM(reached_cart), 4), SUM(reached_checkout),
       ROUND(1.0 - 1.0 * SUM(reached_purchase) / SUM(reached_checkout), 4), SUM(reached_payment),
       ROUND(1.0 - 1.0 * SUM(reached_purchase) / SUM(reached_payment), 4)
FROM session_funnel GROUP BY device
UNION ALL
SELECT 'customer_type', customer_type, SUM(reached_cart), SUM(reached_cart) - SUM(reached_purchase),
       ROUND(1.0 - 1.0 * SUM(reached_purchase) / SUM(reached_cart), 4), SUM(reached_checkout),
       ROUND(1.0 - 1.0 * SUM(reached_purchase) / SUM(reached_checkout), 4), SUM(reached_payment),
       ROUND(1.0 - 1.0 * SUM(reached_purchase) / SUM(reached_payment), 4)
FROM session_funnel GROUP BY customer_type;
