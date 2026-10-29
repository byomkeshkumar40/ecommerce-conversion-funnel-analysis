-- Payment-stage friction by payment method. Unit = PAYMENT ATTEMPT (event).
-- attempt_failure_rate = failed attempts / all attempts for that method.
-- Injected duplicate event rows are excluded via SELECT DISTINCT on (session, ts, method, status),
-- so they cannot inflate attempt counts. Failure rates are observed associations; they do not
-- say WHY an attempt failed.
WITH attempts AS (
  SELECT DISTINCT session_id, event_ts, payment_method, payment_status FROM events
  WHERE event_type = 'payment_attempt')
SELECT payment_method, COUNT(*) AS attempts, SUM(payment_status = 'failed') AS failed_attempts,
       ROUND(1.0 * SUM(payment_status = 'failed') / COUNT(*), 4) AS attempt_failure_rate
FROM attempts GROUP BY payment_method ORDER BY attempts DESC;
