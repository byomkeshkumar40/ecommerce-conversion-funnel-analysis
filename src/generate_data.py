"""Generate the synthetic e-commerce event dataset (fixed seed, fully reproducible).

All data is SYNTHETIC. Relationships between device, channel, customer type,
shipping fee, guest checkout and payment method are *assumptions written into
this script* (see the parameter tables below). Any "finding" computed from this
data therefore demonstrates the analysis method; it is not evidence about real
shoppers. Two kinds of data-quality anomalies are injected on purpose so that
the validation layer has something real to detect (see inject_anomalies()).

Usage:  python -m src.generate_data [--seed 42] [--customers 35000] [--out data/raw]
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START = pd.Timestamp("2025-01-01")
END = pd.Timestamp("2025-07-01")  # exclusive
N_CUSTOMERS = 60_000
N_PRODUCTS = 600

DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_P = [0.62, 0.30, 0.08]
CHANNELS = ["organic_search", "paid_search", "social", "email", "direct", "referral"]
CHANNEL_P_NEW = [0.28, 0.24, 0.18, 0.02, 0.15, 0.13]
CHANNEL_P_RET = [0.22, 0.10, 0.08, 0.22, 0.30, 0.08]
TIERS = ["tier_1", "tier_2", "tier_3"]
TIER_P = [0.35, 0.40, 0.25]

# category: (popularity weight, median price INR, cart-propensity multiplier)
CATEGORIES = {
    "Fashion": (0.25, 899, 0.90),
    "Electronics": (0.20, 4500, 0.75),
    "Home & Kitchen": (0.18, 1200, 0.95),
    "Beauty": (0.15, 450, 1.00),
    "Grocery": (0.12, 300, 1.15),
    "Books": (0.10, 350, 1.10),
}

VIEW_ADJ = {"organic_search": 0.0, "paid_search": -0.06, "social": -0.12,
            "email": 0.04, "direct": 0.02, "referral": -0.02}
CART_MULT_DEVICE = {"mobile": 0.92, "desktop": 1.15, "tablet": 1.00}
CART_MULT_CHANNEL = {"organic_search": 1.0, "paid_search": 0.9, "social": 0.8,
                     "email": 1.2, "direct": 1.1, "referral": 1.0}
PAY_MULT_DEVICE = {"mobile": 0.93, "desktop": 1.05, "tablet": 1.0}

METHODS = ["upi", "card", "netbanking", "cod", "wallet"]
METHOD_P = {"mobile": [0.50, 0.15, 0.05, 0.20, 0.10],
            "desktop": [0.30, 0.35, 0.15, 0.15, 0.05],
            "tablet": [0.40, 0.25, 0.10, 0.20, 0.05]}
METHOD_SUCCESS = {"upi": 0.93, "card": 0.88, "netbanking": 0.84, "cod": 0.99, "wallet": 0.94}
FAIL_REASONS = {"upi": ["bank_timeout", "insufficient_funds", "gateway_error"],
                "card": ["otp_failed", "insufficient_funds", "bank_declined"],
                "netbanking": ["bank_timeout", "otp_failed", "gateway_error"],
                "wallet": ["insufficient_funds", "gateway_error"],
                "cod": ["address_unserviceable"]}
# Injected scenario: a UPI gateway incident (documented in docs/DATA_DICTIONARY.md).
INCIDENT_START, INCIDENT_END = pd.Timestamp("2025-04-14"), pd.Timestamp("2025-04-21")
INCIDENT_UPI_SUCCESS = 0.55
FREE_SHIPPING_THRESHOLD = 499


def make_products(rng):
    names = list(CATEGORIES)
    weights = np.array([CATEGORIES[c][0] for c in names])
    cats = rng.choice(names, N_PRODUCTS, p=weights / weights.sum())
    prices = [max(49, int(round(CATEGORIES[c][1] * np.exp(rng.normal(0, 0.5))))) for c in cats]
    return pd.DataFrame({"product_id": [f"P{i + 1:04d}" for i in range(N_PRODUCTS)],
                         "category": cats, "price": prices})


def make_customers_and_sessions(rng, n_customers):
    span = (END - START).total_seconds()
    tiers = rng.choice(TIERS, n_customers, p=TIER_P)
    dev_pref = rng.choice(DEVICES, n_customers, p=DEVICE_P)
    rows = []
    for c in range(n_customers):
        t = START + pd.Timedelta(seconds=float(rng.uniform(0, span)))
        n = int(rng.geometric(0.6))  # 1 + extra visits
        times = [t]
        for _ in range(n - 1):
            t = t + pd.Timedelta(days=float(rng.exponential(12)))
            times.append(t)
        for ts in times:
            if ts < END:
                rows.append((f"C{c + 1:06d}", ts.floor("s")))
    sess = pd.DataFrame(rows, columns=["customer_id", "session_start"])
    sess = sess.sort_values(["customer_id", "session_start"]).reset_index(drop=True)
    sess["customer_type"] = np.where(sess.groupby("customer_id").cumcount() == 0, "new", "returning")
    cidx = sess["customer_id"].str[1:].astype(int).to_numpy() - 1
    keep = rng.random(len(sess)) < 0.85
    redraw = rng.choice(DEVICES, len(sess), p=DEVICE_P)
    sess["device"] = np.where(keep, dev_pref[cidx], redraw)
    ret = (sess["customer_type"] == "returning").to_numpy()
    new_ch = rng.choice(CHANNELS, len(sess), p=CHANNEL_P_NEW)
    ret_ch = rng.choice(CHANNELS, len(sess), p=CHANNEL_P_RET)
    sess["channel"] = np.where(ret, ret_ch, new_ch)
    sess = sess.sort_values("session_start", kind="stable").reset_index(drop=True)
    sess.insert(0, "session_id", [f"S{i + 1:06d}" for i in range(len(sess))])
    sess["city_tier"] = tiers[sess["customer_id"].str[1:].astype(int).to_numpy() - 1]
    first = sess[sess["customer_type"] == "new"].set_index("customer_id")
    cust = pd.DataFrame({"customer_id": [f"C{i + 1:06d}" for i in range(n_customers)],
                         "city_tier": tiers})
    cust = cust[cust["customer_id"].isin(first.index)].copy()
    cust["first_seen_date"] = cust["customer_id"].map(first["session_start"].dt.strftime("%Y-%m-%d"))
    cust["first_touch_channel"] = cust["customer_id"].map(first["channel"])
    return cust.reset_index(drop=True), sess.drop(columns="city_tier"), \
        dict(zip(sess["customer_id"], sess["city_tier"]))


def simulate_session(s, tier, products, by_cat, rng, price_of):
    """Return (events, order|None, order_items) for one session."""
    ev, items_out, order = [], [], None
    t = s.session_start
    sid, cid, dev, ch = s.session_id, s.customer_id, s.device, s.channel
    ret = s.customer_type == "returning"
    mobile = dev == "mobile"

    def add(etype, ts, **kw):
        ev.append(dict(session_id=sid, customer_id=cid, event_ts=ts, event_type=etype, **kw))

    add("session_start", t)
    if rng.random() > 0.88 + VIEW_ADJ[ch] + (-0.02 if mobile else 0):
        return ev, order, items_out
    cats = list(CATEGORIES)
    w = np.array([CATEGORIES[c][0] for c in cats])
    cat0 = rng.choice(cats, p=w / w.sum())
    viewed = []
    for i in range(1 + int(rng.poisson(1.8))):
        cat = cat0 if (i == 0 or rng.random() < 0.7) else rng.choice(cats, p=w / w.sum())
        pid = rng.choice(by_cat[cat])
        viewed.append(pid)
        t += pd.Timedelta(seconds=int(rng.integers(15, 90)))
        add("product_view", t, product_id=pid)
    day_frac = (s.session_start - START).days / 180
    p_cart = (0.14 * CART_MULT_DEVICE[dev] * (1.35 if ret else 1.0) * CART_MULT_CHANNEL[ch]
              * CATEGORIES[cat0][2] * (1 + 0.08 * day_frac)
              * (1.05 if s.session_start.day_of_week >= 5 else 1.0))
    if rng.random() >= min(p_cart, 0.95):
        return ev, order, items_out
    n_add = min(len(set(viewed)), 1 + int(rng.random() < 0.3))
    chosen = rng.choice(sorted(set(viewed)), n_add, replace=False)
    cart_value = 0
    for pid in chosen:
        qty = 1 + int(rng.random() < 0.12)
        t += pd.Timedelta(seconds=int(rng.integers(10, 60)))
        add("add_to_cart", t, product_id=pid, quantity=qty)
        cart_value += price_of[pid] * qty
        items_out.append((pid, qty, price_of[pid]))
    fee = 0 if cart_value >= FREE_SHIPPING_THRESHOLD else (79 if tier == "tier_3" else 49)
    p_co = 0.55 * (1.10 if ret else 1.0) * (0.95 if mobile else 1.0) * (0.88 if fee > 0 else 1.0)
    if rng.random() >= p_co:
        return ev, order, []
    t += pd.Timedelta(seconds=int(rng.integers(30, 300)))
    guest = bool(rng.random() < min(0.95, (0.25 if ret else 0.55) * (1.15 if mobile else 1.0)))
    add("checkout_start", t, guest_checkout=int(guest), shipping_fee=fee)
    p_pay = 0.80 * (0.85 if guest else 1.0) * PAY_MULT_DEVICE[dev]
    if rng.random() >= min(p_pay, 0.97):
        return ev, order, []
    mp = np.array(METHOD_P[dev], dtype=float)
    if tier == "tier_3":
        mp[METHODS.index("cod")] += 0.15
        mp[METHODS.index("card")] -= 0.10
        mp[METHODS.index("netbanking")] -= 0.05
    mp = mp / mp.sum()
    method = rng.choice(METHODS, p=mp)
    for attempt in range(1, 4):
        t += pd.Timedelta(seconds=int(rng.integers(20, 180)))
        p_ok = METHOD_SUCCESS[method]
        if method == "card" and mobile:
            p_ok *= 0.97
        in_incident = INCIDENT_START <= t.floor("D") < INCIDENT_END
        if method == "upi" and in_incident:
            p_ok = INCIDENT_UPI_SUCCESS
        ok = rng.random() < p_ok
        reason = None
        if not ok:
            reason = "gateway_error" if (method == "upi" and in_incident and rng.random() < 0.7) \
                else rng.choice(FAIL_REASONS[method])
        add("payment_attempt", t, payment_method=method,
            payment_status="success" if ok else "failed", failure_reason=reason)
        if ok:
            t += pd.Timedelta(seconds=int(rng.integers(3, 10)))
            add("purchase_complete", t)
            order = dict(session_id=sid, customer_id=cid, order_ts=t,
                         order_value=cart_value + fee, shipping_fee=fee,
                         payment_method=method, payment_attempts=attempt)
            return ev, order, items_out
        if attempt < 3 and rng.random() < 0.6:
            if rng.random() < 0.4:
                method = rng.choice(["cod", "card"])
            continue
        break
    return ev, None, []


def inject_anomalies(events, orders, rng):
    """Deliberately corrupt a small share of data so validation has real work.

    1. ~0.4% of event rows are duplicated (new event_id, same content).
    2. up to 12 purchasing sessions (1 per 100 purchases if fewer) lose their checkout_start row (purchase without checkout).
    """
    log = {}
    n_dup = int(len(events) * 0.004)
    dup = events.iloc[rng.choice(len(events), n_dup, replace=False)]
    purchases = events[events["event_type"] == "purchase_complete"]["session_id"]
    victims = rng.choice(purchases.unique(), min(12, max(1, purchases.nunique() // 100)), replace=False)
    drop = events["session_id"].isin(victims) & (events["event_type"] == "checkout_start")
    events = pd.concat([events[~drop], dup], ignore_index=True)
    log["injected_duplicate_events"] = n_dup
    log["injected_missing_checkout_sessions"] = sorted(victims.tolist())
    return events, log


def generate(seed=SEED, n_customers=N_CUSTOMERS):
    rng = np.random.default_rng(seed)
    products = make_products(rng)
    by_cat = {c: products.loc[products.category == c, "product_id"].tolist() for c in CATEGORIES}
    price_of = dict(zip(products.product_id, products.price))
    cust, sess, tier_of = make_customers_and_sessions(rng, n_customers)
    all_ev, orders, order_items = [], [], []
    for s in sess.itertuples(index=False):
        ev, order, items = simulate_session(s, tier_of[s.customer_id], products, by_cat, rng, price_of)
        all_ev.extend(ev)
        if order:
            orders.append(order)
            order_items.extend((s.session_id, *i) for i in items)
    events = pd.DataFrame(all_ev)
    orders = pd.DataFrame(orders)
    orders.insert(0, "order_id", [f"O{i + 1:06d}" for i in range(len(orders))])
    oid = dict(zip(orders.session_id, orders.order_id))
    oi = pd.DataFrame(order_items, columns=["session_id", "product_id", "quantity", "unit_price"])
    oi.insert(0, "order_id", oi.session_id.map(oid))
    oi = oi.drop(columns="session_id")
    events, log = inject_anomalies(events, orders, rng)
    events = events.sort_values(["event_ts", "session_id"], kind="stable").reset_index(drop=True)
    events.insert(0, "event_id", [f"E{i + 1:07d}" for i in range(len(events))])
    for df, col in [(events, "event_ts"), (orders, "order_ts"), (sess, "session_start")]:
        df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    cols = ["event_id", "session_id", "customer_id", "event_ts", "event_type", "product_id",
            "quantity", "guest_checkout", "shipping_fee", "payment_method", "payment_status",
            "failure_reason"]
    events = events.reindex(columns=cols)
    for c in ["quantity", "guest_checkout", "shipping_fee"]:
        events[c] = events[c].astype("Int64")
    return dict(customers=cust, products=products, sessions=sess, events=events,
                orders=orders, order_items=oi), log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--customers", type=int, default=N_CUSTOMERS)
    ap.add_argument("--out", default="data/raw")
    a = ap.parse_args()
    tables, log = generate(a.seed, a.customers)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out / f"{name}.csv", index=False)
        print(f"{name:12s} {len(df):>9,d} rows")
    print("injected anomalies:", {k: (v if not isinstance(v, list) else len(v)) for k, v in log.items()})


if __name__ == "__main__":
    main()
