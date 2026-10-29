-- Weekly conversion trend. Unit = SESSION, bucketed by session_start week (Monday start).
-- LAG() gives week-over-week change in percentage points.
-- days_in_data < 7 flags partial weeks (first/last week of the window).
WITH weekly AS (
  SELECT DATE(session_date, 'weekday 0', '-6 days') AS week_start,
         COUNT(*) AS sessions, SUM(reached_purchase) AS purchases,
         SUM(reached_checkout) AS checkouts, SUM(reached_payment) AS payment_attempts,
         COUNT(DISTINCT session_date) AS days_in_data
  FROM session_funnel GROUP BY week_start)
SELECT week_start, sessions, purchases, days_in_data,
       ROUND(1.0 * purchases / sessions, 4) AS purchase_rate_of_sessions,
       ROUND(1.0 * purchases / payment_attempts, 4) AS payment_to_purchase_rate,
       ROUND(100.0 * (1.0 * purchases / sessions
             - LAG(1.0 * purchases / sessions) OVER (ORDER BY week_start)), 2) AS wow_change_pp
FROM weekly ORDER BY week_start;
