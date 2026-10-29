-- Category analysis. Unit = SESSION x CATEGORY pair (distinct, so repeated views of
-- several products in one category count once). A session that touched 2 categories
-- appears in both rows => category rows are NOT additive and do not sum to the overall funnel.
-- viewed_sessions = sessions that viewed >=1 product of the category (strict view stage reached).
-- cart_rate = carted / viewed;  cart_to_purchase = purchased / carted (strict purchase stage).
WITH viewed AS (
  SELECT DISTINCT e.session_id, p.category FROM events e
  JOIN products p ON p.product_id = e.product_id WHERE e.event_type = 'product_view'),
carted AS (
  SELECT DISTINCT e.session_id, p.category FROM events e
  JOIN products p ON p.product_id = e.product_id WHERE e.event_type = 'add_to_cart')
SELECT v.category,
       COUNT(*) AS viewed_sessions,
       SUM(c.session_id IS NOT NULL AND sf.reached_cart = 1) AS carted_sessions,
       SUM(c.session_id IS NOT NULL AND sf.reached_purchase = 1) AS purchased_sessions,
       ROUND(1.0 * SUM(c.session_id IS NOT NULL AND sf.reached_cart = 1) / COUNT(*), 4) AS view_to_cart_rate,
       ROUND(1.0 * SUM(c.session_id IS NOT NULL AND sf.reached_purchase = 1)
             / SUM(c.session_id IS NOT NULL AND sf.reached_cart = 1), 4) AS cart_to_purchase_rate
FROM viewed v
JOIN session_funnel sf ON sf.session_id = v.session_id AND sf.reached_view = 1
LEFT JOIN carted c ON c.session_id = v.session_id AND c.category = v.category
GROUP BY v.category ORDER BY view_to_cart_rate DESC;
