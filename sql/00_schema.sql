-- Schema for the e-commerce funnel database (SQLite). Timestamps are TEXT
-- 'YYYY-MM-DD HH:MM:SS' (IST, no offset), which sort correctly as strings.
-- Note: events.event_id is unique but NOT a business key for deduplication:
-- injected duplicate events carry new event_ids with otherwise identical content.
PRAGMA foreign_keys = ON;
CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY, city_tier TEXT NOT NULL,
  first_seen_date TEXT NOT NULL, first_touch_channel TEXT NOT NULL);
CREATE TABLE products (
  product_id TEXT PRIMARY KEY, category TEXT NOT NULL, price INTEGER NOT NULL);
CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  session_start TEXT NOT NULL, customer_type TEXT NOT NULL CHECK (customer_type IN ('new','returning')),
  device TEXT NOT NULL, channel TEXT NOT NULL);
CREATE TABLE events (
  event_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(session_id),
  customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  event_ts TEXT NOT NULL, event_type TEXT NOT NULL,
  product_id TEXT REFERENCES products(product_id),
  quantity INTEGER, guest_checkout INTEGER, shipping_fee INTEGER,
  payment_method TEXT, payment_status TEXT, failure_reason TEXT);
CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL UNIQUE REFERENCES sessions(session_id),
  customer_id TEXT NOT NULL REFERENCES customers(customer_id),
  order_ts TEXT NOT NULL, order_value INTEGER NOT NULL, shipping_fee INTEGER NOT NULL,
  payment_method TEXT NOT NULL, payment_attempts INTEGER NOT NULL);
CREATE TABLE order_items (
  order_id TEXT NOT NULL REFERENCES orders(order_id),
  product_id TEXT NOT NULL REFERENCES products(product_id),
  quantity INTEGER NOT NULL, unit_price INTEGER NOT NULL);
CREATE INDEX idx_events_session ON events(session_id);
CREATE INDEX idx_sessions_customer ON sessions(customer_id);
