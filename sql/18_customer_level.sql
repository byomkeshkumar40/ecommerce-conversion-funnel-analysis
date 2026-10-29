-- Customer-level conversion. Unit = CUSTOMER (visitor id), NOT session.
-- customer conversion = customers with >=1 (strict) purchase session / customers with >=1 session.
-- Compare with session conversion: customers have several sessions, so the two rates differ.
-- first_session_conversion uses only each customer's first session (customer_type = 'new').
WITH per_customer AS (
  SELECT customer_id, COUNT(*) AS sessions, MAX(reached_purchase) AS purchased,
         MAX(CASE WHEN customer_type = 'new' THEN reached_purchase END) AS purchased_first_session
  FROM session_funnel GROUP BY customer_id)
SELECT COUNT(*) AS customers, SUM(purchased) AS purchasing_customers,
       ROUND(1.0 * SUM(purchased) / COUNT(*), 4) AS customer_conversion_rate,
       ROUND(1.0 * SUM(purchased_first_session) / COUNT(*), 4) AS first_session_conversion_rate,
       ROUND(1.0 * SUM(sessions) / COUNT(*), 3) AS avg_sessions_per_customer,
       ROUND((SELECT 1.0 * SUM(reached_purchase) / COUNT(*) FROM session_funnel), 4) AS session_conversion_rate
FROM per_customer;
