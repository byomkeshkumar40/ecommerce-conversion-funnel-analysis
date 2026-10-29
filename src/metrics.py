"""Independent pandas implementation of the funnel metrics.

The SQL in sql/ and this module compute the same numbers by different routes;
tests/test_reconciliation.py asserts they agree. The Streamlit dashboard imports
THIS module, so dashboard numbers come from the same functions the tests check.

Unit of analysis is the SESSION unless a function says otherwise.
"""
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

STAGES = ["session_start", "product_view", "add_to_cart", "checkout_start",
          "payment_attempt", "purchase_complete"]
FLAGS = ["in_session", "reached_view", "reached_cart", "reached_checkout",
         "reached_payment", "reached_purchase"]
STAGE_LABELS = ["Sessions", "Product view", "Add to cart", "Checkout start",
                "Payment attempt", "Purchase"]
STEP_NAMES = ["Session → Product view", "Product view → Add to cart",
              "Add to cart → Checkout", "Checkout → Payment attempt",
              "Payment attempt → Purchase"]


def load_raw(raw_dir=RAW):
    raw_dir = Path(raw_dir)
    names = ["customers", "products", "sessions", "events", "orders", "order_items"]
    return {n: pd.read_csv(raw_dir / f"{n}.csv") for n in names}


def build_session_funnel(sessions, events, customers):
    """One row per session with 0/1 stage flags (strict chronological funnel).

    A stage is reached only if the event exists, the previous stage was reached and
    the FIRST timestamp of the event is >= the first timestamp of the previous stage.
    Taking the first timestamp per (session, event_type) means repeated views, carts,
    payment retries and duplicated rows cannot double count.
    """
    ev = events.assign(event_ts=pd.to_datetime(events["event_ts"]))
    first = (ev.pivot_table(index="session_id", columns="event_type", values="event_ts", aggfunc="min")
             .reindex(columns=STAGES))
    sf = sessions.merge(customers[["customer_id", "city_tier"]], on="customer_id", how="left")
    sf["session_start"] = pd.to_datetime(sf["session_start"])
    sf = sf.merge(first.drop(columns="session_start"), left_on="session_id", right_index=True, how="left")
    sf["in_session"] = 1
    view = sf["product_view"].notna() & (sf["product_view"] >= sf["session_start"])
    cart = view & sf["add_to_cart"].notna() & (sf["add_to_cart"] >= sf["product_view"])
    chk = cart & sf["checkout_start"].notna() & (sf["checkout_start"] >= sf["add_to_cart"])
    pay = chk & sf["payment_attempt"].notna() & (sf["payment_attempt"] >= sf["checkout_start"])
    pur = pay & sf["purchase_complete"].notna() & (sf["purchase_complete"] >= sf["payment_attempt"])
    for col, m in zip(FLAGS[1:], [view, cart, chk, pay, pur]):
        sf[col] = m.astype(int)
    sf["has_purchase_event"] = sf["purchase_complete"].notna().astype(int)
    sf["session_date"] = sf["session_start"].dt.normalize()
    return sf.drop(columns=STAGES[1:])


def safe_div(a, b):
    return float(a) / float(b) if b else float("nan")


def wilson_ci(successes, n, z=1.96):
    """95% Wilson score interval for a proportion; (nan, nan) if n == 0."""
    if n == 0:
        return float("nan"), float("nan")
    p = successes / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def two_prop_p_value(x1, n1, x2, n2):
    """Two-sided p-value of the pooled two-proportion z-test (nan if undefined)."""
    if n1 == 0 or n2 == 0:
        return float("nan")
    pool = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return float("nan")
    z = (x1 / n1 - x2 / n2) / se
    return math.erfc(abs(z) / math.sqrt(2))


def funnel_table(sf):
    """Stage counts, step conversion (/previous stage), overall conversion (/all sessions)."""
    n = [int(sf[f].sum()) for f in FLAGS]
    total = n[0]
    rows = []
    for i, (label, c) in enumerate(zip(STAGE_LABELS, n)):
        prev = n[i - 1] if i else c
        rows.append(dict(stage_no=i + 1, stage=label, sessions=c,
                         step_conversion=safe_div(c, prev),
                         overall_conversion=safe_div(c, total),
                         dropoff_from_previous=1 - safe_div(c, prev) if prev else float("nan"),
                         sessions_lost=prev - c))
    return pd.DataFrame(rows)


def headline(sf):
    return dict(sessions=len(sf), visitors=int(sf["customer_id"].nunique()),
                purchases=int(sf["reached_purchase"].sum()),
                purchase_rate=safe_div(sf["reached_purchase"].sum(), len(sf)))


def segment_table(sf, dim):
    """Funnel by segment with Wilson CI and a one-vs-rest p-value on purchase rate."""
    if sf.empty:
        return pd.DataFrame(columns=["segment", "sessions", "purchases", "view_rate_of_sessions", "step_view_to_cart",
                                     "step_cart_to_checkout", "step_checkout_to_payment", "step_payment_to_purchase",
                                     "purchase_rate_of_sessions", "ci_low", "ci_high", "p_vs_rest"])
    rows = []
    tot_n, tot_x = len(sf), int(sf["reached_purchase"].sum())
    for seg, g in sf.groupby(dim):
        n, x = len(g), int(g["reached_purchase"].sum())
        lo, hi = wilson_ci(x, n)
        s = {f: int(g[f].sum()) for f in FLAGS}
        rows.append(dict(
            segment=seg, sessions=n, purchases=x,
            view_rate_of_sessions=safe_div(s["reached_view"], n),
            step_view_to_cart=safe_div(s["reached_cart"], s["reached_view"]),
            step_cart_to_checkout=safe_div(s["reached_checkout"], s["reached_cart"]),
            step_checkout_to_payment=safe_div(s["reached_payment"], s["reached_checkout"]),
            step_payment_to_purchase=safe_div(s["reached_purchase"], s["reached_payment"]),
            purchase_rate_of_sessions=safe_div(x, n), ci_low=lo, ci_high=hi,
            p_vs_rest=two_prop_p_value(x, n, tot_x - x, tot_n - n)))
    return pd.DataFrame(rows).sort_values("purchase_rate_of_sessions", ascending=False).reset_index(drop=True)


def weekly_trend(sf):
    d = sf.assign(week_start=sf["session_date"] - pd.to_timedelta(sf["session_date"].dt.dayofweek, unit="D"))
    g = d.groupby("week_start").agg(sessions=("session_id", "size"), purchases=("reached_purchase", "sum"),
                                    payment_attempts=("reached_payment", "sum"),
                                    days_in_data=("session_date", "nunique")).reset_index()
    g["purchase_rate_of_sessions"] = g["purchases"] / g["sessions"]
    g["payment_to_purchase_rate"] = g["purchases"] / g["payment_attempts"].replace(0, np.nan)
    g["wow_change_pp"] = g["purchase_rate_of_sessions"].diff() * 100
    return g


def abandonment(sf):
    c, k, p, u = (sf[f].sum() for f in ["reached_cart", "reached_checkout", "reached_payment", "reached_purchase"])
    return dict(carts=int(c), cart_abandonment_rate=1 - safe_div(u, c) if c else float("nan"),
                checkouts=int(k), checkout_abandonment_rate=1 - safe_div(u, k) if k else float("nan"),
                payment_attempts=int(p), payment_abandonment_rate=1 - safe_div(u, p) if p else float("nan"))


def customer_level(sf):
    per = sf.groupby("customer_id").agg(sessions=("session_id", "size"), purchased=("reached_purchase", "max"))
    first = sf[sf["customer_type"] == "new"].groupby("customer_id")["reached_purchase"].max()
    n = len(per)
    return dict(customers=n, purchasing_customers=int(per["purchased"].sum()),
                customer_conversion_rate=safe_div(per["purchased"].sum(), n),
                first_session_conversion_rate=safe_div(first.sum(), n),
                avg_sessions_per_customer=safe_div(per["sessions"].sum(), n),
                session_conversion_rate=safe_div(sf["reached_purchase"].sum(), len(sf)))


def repeat_purchase(orders):
    o = orders.assign(order_ts=pd.to_datetime(orders["order_ts"])).sort_values(["customer_id", "order_ts"])
    o["order_no"] = o.groupby("customer_id").cumcount() + 1
    n_orders = o.groupby("customer_id")["order_no"].max()
    second = o[o["order_no"] == 2]
    first = o[o["order_no"] == 1].set_index("customer_id")["order_ts"]
    gap = (second.set_index("customer_id")["order_ts"] - first.reindex(second["customer_id"]).values).dt.total_seconds() / 86400
    return dict(customers_with_order=len(n_orders), repeat_customers=int((n_orders >= 2).sum()),
                repeat_purchase_rate=safe_div((n_orders >= 2).sum(), len(n_orders)),
                total_orders=len(o), avg_days_between_1st_and_2nd_order=float(gap.mean()) if len(gap) else float("nan"))


def category_funnel(sf, events, products):
    """Session x category pairs (distinct). Rows overlap: a session may touch several categories."""
    ev = events.merge(products[["product_id", "category"]], on="product_id")
    viewed = ev[ev["event_type"] == "product_view"][["session_id", "category"]].drop_duplicates()
    carted = ev[ev["event_type"] == "add_to_cart"][["session_id", "category"]].drop_duplicates().assign(carted_cat=1)
    v = viewed.merge(sf[["session_id", "reached_view", "reached_cart", "reached_purchase"]], on="session_id")
    v = v[v["reached_view"] == 1].merge(carted, on=["session_id", "category"], how="left")
    v["carted_cat"] = v["carted_cat"].fillna(0).astype(int) & v["reached_cart"]
    v["purchased_cat"] = v["carted_cat"] & v["reached_purchase"]
    g = v.groupby("category").agg(viewed_sessions=("session_id", "size"), carted_sessions=("carted_cat", "sum"),
                                  purchased_sessions=("purchased_cat", "sum")).reset_index()
    g["view_to_cart_rate"] = g["carted_sessions"] / g["viewed_sessions"]
    g["cart_to_purchase_rate"] = g["purchased_sessions"] / g["carted_sessions"].replace(0, np.nan)
    return g.sort_values("view_to_cart_rate", ascending=False).reset_index(drop=True)


def payment_method_failures(events):
    a = events[events["event_type"] == "payment_attempt"][["session_id", "event_ts", "payment_method", "payment_status"]].drop_duplicates()
    g = a.groupby("payment_method").agg(attempts=("payment_status", "size"),
                                         failed_attempts=("payment_status", lambda s: int((s == "failed").sum()))).reset_index()
    g["attempt_failure_rate"] = g["failed_attempts"] / g["attempts"]
    return g.sort_values("attempts", ascending=False).reset_index(drop=True)


def retry_recovery(sf, events):
    a = events[events["event_type"] == "payment_attempt"][["session_id", "event_ts", "payment_status"]].drop_duplicates()
    had = a.groupby("session_id")["payment_status"].apply(lambda s: int((s == "failed").any())).rename("had_failure").reset_index()
    m = had.merge(sf[["session_id", "reached_payment", "reached_purchase"]], on="session_id")
    m = m[m["reached_payment"] == 1]
    f = m[m["had_failure"] == 1]
    return dict(sessions_with_attempt=len(m), sessions_with_failure=len(f), recovered=int(f["reached_purchase"].sum()),
                recovery_rate=safe_div(f["reached_purchase"].sum(), len(f)))


def checkout_friction(sf, events):
    co = (events[events["event_type"] == "checkout_start"].groupby("session_id")
          .agg(guest_checkout=("guest_checkout", "min"), shipping_fee=("shipping_fee", "min")).reset_index())
    m = sf[sf["reached_checkout"] == 1].merge(co, on="session_id")
    m["checkout_type"] = np.where(m["guest_checkout"] == 1, "guest", "account")
    m["shipping"] = np.where(m["shipping_fee"] > 0, "fee_charged", "free_shipping")
    g = m.groupby(["checkout_type", "shipping"]).agg(checkout_sessions=("session_id", "size"),
                                                      payment_attempts=("reached_payment", "sum"),
                                                      purchases=("reached_purchase", "sum")).reset_index()
    g["checkout_to_payment_rate"] = g["payment_attempts"] / g["checkout_sessions"]
    g["checkout_to_purchase_rate"] = g["purchases"] / g["checkout_sessions"]
    return g


def derive_findings(sf):
    """Plain-language findings computed from the (possibly filtered) sessions. Observed facts only."""
    out = []
    if len(sf) == 0:
        return ["No sessions match the current filters."]
    ft = funnel_table(sf).iloc[1:]
    ft = ft[ft["sessions_lost"] > 0]
    if len(ft):
        top = ft.loc[ft["sessions_lost"].idxmax()]
        out.append(f"Largest absolute loss: **{top['stage']}** step — {int(top['sessions_lost']):,} sessions "
                   f"lost ({top['dropoff_from_previous']:.1%} of those that reached the previous stage).")
        worst = ft.loc[ft["dropoff_from_previous"].idxmax()]
        out.append(f"Highest step-level drop-off rate: **{worst['stage']}** at {worst['dropoff_from_previous']:.1%}.")
    for dim, label in [("device", "device"), ("channel", "channel"), ("customer_type", "customer type")]:
        seg = segment_table(sf, dim)
        seg = seg[seg["sessions"] >= 500]
        if len(seg) >= 2:
            hi, lo = seg.iloc[0], seg.iloc[-1]
            p = two_prop_p_value(hi["purchases"], hi["sessions"], lo["purchases"], lo["sessions"])
            sig = "difference unlikely to be chance alone (p<0.05)" if p < 0.05 else "difference not statistically distinguishable (p≥0.05)"
            out.append(f"By {label}: **{hi['segment']}** converts {hi['purchase_rate_of_sessions']:.2%} "
                       f"(n={int(hi['sessions']):,}) vs **{lo['segment']}** {lo['purchase_rate_of_sessions']:.2%} "
                       f"(n={int(lo['sessions']):,}); {sig}.")
    ab = abandonment(sf)
    if ab["carts"]:
        out.append(f"Cart abandonment {ab['cart_abandonment_rate']:.1%} of {ab['carts']:,} cart sessions; "
                   f"checkout abandonment {ab['checkout_abandonment_rate']:.1%} of {ab['checkouts']:,} checkout sessions.")
    return out


def apply_filters(sf, start=None, end=None, devices=None, channels=None, customer_types=None, city_tiers=None):
    """Filter the session table. None / empty list means 'no restriction' for that field is NOT assumed:
    an explicitly empty list selects nothing (callers pass None for 'all')."""
    m_ = pd.Series(True, index=sf.index)
    if start is not None:
        m_ &= sf["session_date"] >= pd.Timestamp(start)
    if end is not None:
        m_ &= sf["session_date"] <= pd.Timestamp(end)
    for col, vals in [("device", devices), ("channel", channels), ("customer_type", customer_types), ("city_tier", city_tiers)]:
        if vals is not None:
            m_ &= sf[col].isin(vals)
    return sf[m_]
