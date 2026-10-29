-- Repeat purchase. Unit = CUSTOMER with >=1 order (orders table).
-- ROW_NUMBER numbers each customer's orders chronologically; LAG gives the gap to the previous order.
-- Window is only ~6 months and customers first seen late have little time to repeat (right-censoring),
-- so repeat_rate is a lower bound, not a lifetime figure.
WITH ordered AS (
  SELECT customer_id, order_ts,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_ts) AS order_no,
         LAG(order_ts) OVER (PARTITION BY customer_id ORDER BY order_ts) AS prev_ts
  FROM orders),
per_customer AS (SELECT customer_id, MAX(order_no) AS n_orders FROM ordered GROUP BY customer_id)
SELECT COUNT(*) AS customers_with_order,
       SUM(n_orders >= 2) AS repeat_customers,
       ROUND(1.0 * SUM(n_orders >= 2) / COUNT(*), 4) AS repeat_purchase_rate,
       (SELECT COUNT(*) FROM orders) AS total_orders,
       (SELECT ROUND(AVG(julianday(order_ts) - julianday(prev_ts)), 2) FROM ordered WHERE order_no = 2) AS avg_days_between_1st_and_2nd_order
FROM per_customer;
