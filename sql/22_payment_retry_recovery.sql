-- Retry recovery. Unit = SESSION with >=1 payment attempt.
-- sessions_with_failure   = sessions with >=1 failed attempt
-- recovery_rate           = those sessions that still purchased (strict) / sessions_with_failure
WITH attempts AS (
  SELECT DISTINCT session_id, event_ts, payment_status FROM events WHERE event_type = 'payment_attempt'),
sess AS (
  SELECT a.session_id, MAX(a.payment_status = 'failed') AS had_failure, sf.reached_purchase
  FROM attempts a JOIN session_funnel sf ON sf.session_id = a.session_id
  WHERE sf.reached_payment = 1 GROUP BY a.session_id)
SELECT COUNT(*) AS sessions_with_attempt, SUM(had_failure) AS sessions_with_failure,
       SUM(had_failure AND reached_purchase) AS recovered,
       ROUND(1.0 * SUM(had_failure AND reached_purchase) / SUM(had_failure), 4) AS recovery_rate
FROM sess;
