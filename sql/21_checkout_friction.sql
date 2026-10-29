-- Checkout friction indicators. Unit = SESSION that started checkout (strict stage).
-- guest_checkout and shipping_fee are recorded on the checkout_start event. These are
-- ASSOCIATIONS: guest vs account users and fee vs no-fee carts also differ in other ways
-- (device, customer type, cart value), so no causal claim can be made from this table.
WITH co AS (
  SELECT sf.session_id, sf.reached_payment, sf.reached_purchase,
         MIN(e.guest_checkout) AS guest_checkout, MIN(e.shipping_fee) AS shipping_fee
  FROM session_funnel sf JOIN events e ON e.session_id = sf.session_id AND e.event_type = 'checkout_start'
  WHERE sf.reached_checkout = 1 GROUP BY sf.session_id)
SELECT CASE guest_checkout WHEN 1 THEN 'guest' ELSE 'account' END AS checkout_type,
       CASE WHEN shipping_fee > 0 THEN 'fee_charged' ELSE 'free_shipping' END AS shipping,
       COUNT(*) AS checkout_sessions, SUM(reached_payment) AS payment_attempts, SUM(reached_purchase) AS purchases,
       ROUND(1.0 * SUM(reached_payment) / COUNT(*), 4) AS checkout_to_payment_rate,
       ROUND(1.0 * SUM(reached_purchase) / COUNT(*), 4) AS checkout_to_purchase_rate
FROM co GROUP BY 1, 2 ORDER BY 1, 2;
