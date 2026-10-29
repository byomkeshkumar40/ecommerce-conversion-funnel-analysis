"""SQL vs pandas: the two implementations must agree on every critical metric."""
import sqlite3

import pandas as pd
import pytest

from src import metrics as m
from src import run_sql


@pytest.fixture(scope="module")
def sql(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "t.db"
    con = run_sql.build_db(m.RAW, db)
    out = run_sql.run_queries(con, tmp_path_factory.mktemp("out"))
    return out


def approx(a, b):
    assert a == pytest.approx(b, abs=1e-4), (a, b)


def test_overall_funnel(sql, sf):
    s, p = sql["10_funnel_overall"], m.funnel_table(sf)
    assert s["sessions_reaching_stage"].tolist() == p["sessions"].tolist()
    for a, b in zip(s["step_conversion"], p["step_conversion"]):
        approx(a, b)
    assert int(s["unique_visitors"].iloc[0]) == sf["customer_id"].nunique()


@pytest.mark.parametrize("name,dim", [("11_funnel_by_device", "device"), ("12_funnel_by_channel", "channel"),
                                      ("13_funnel_by_customer_type", "customer_type"), ("14_funnel_by_city_tier", "city_tier")])
def test_segments(sql, sf, name, dim):
    s = sql[name].set_index("segment").sort_index()
    p = m.segment_table(sf, dim).set_index("segment").sort_index()
    assert s["sessions"].tolist() == p["sessions"].tolist()
    assert s["purchases"].tolist() == p["purchases"].tolist()
    for col in ["step_view_to_cart", "step_cart_to_checkout", "step_checkout_to_payment", "step_payment_to_purchase", "purchase_rate_of_sessions"]:
        for a, b in zip(s[col], p[col]):
            approx(a, b)


def test_category(sql, sf, raw):
    s = sql["15_category_funnel"].set_index("category").sort_index()
    p = m.category_funnel(sf, raw["events"], raw["products"]).set_index("category").sort_index()
    for col in ["viewed_sessions", "carted_sessions", "purchased_sessions"]:
        assert s[col].tolist() == p[col].tolist()


def test_weekly(sql, sf):
    s = sql["16_weekly_trend"]
    p = m.weekly_trend(sf)
    assert s["sessions"].tolist() == p["sessions"].tolist()
    assert s["purchases"].tolist() == p["purchases"].tolist()
    assert s["week_start"].tolist() == p["week_start"].dt.strftime("%Y-%m-%d").tolist()


def test_abandonment(sql, sf):
    s = sql["17_abandonment"].set_index(["segment_type", "segment"])
    ab = m.abandonment(sf)
    approx(s.loc[("overall", "all"), "cart_abandonment_rate"], ab["cart_abandonment_rate"])
    approx(s.loc[("overall", "all"), "checkout_abandonment_rate"], ab["checkout_abandonment_rate"])
    for dev in sf["device"].unique():
        approx(s.loc[("device", dev), "checkout_abandonment_rate"], m.abandonment(sf[sf.device == dev])["checkout_abandonment_rate"])


def test_customer_and_repeat(sql, sf, raw):
    s, p = sql["18_customer_level"].iloc[0], m.customer_level(sf)
    assert s["customers"] == p["customers"] and s["purchasing_customers"] == p["purchasing_customers"]
    approx(s["first_session_conversion_rate"], p["first_session_conversion_rate"])
    r, q = sql["19_repeat_purchase"].iloc[0], m.repeat_purchase(raw["orders"])
    assert r["repeat_customers"] == q["repeat_customers"] and r["total_orders"] == q["total_orders"]
    assert r["avg_days_between_1st_and_2nd_order"] == pytest.approx(q["avg_days_between_1st_and_2nd_order"], abs=0.01)  # SQL rounds to 2 dp


def test_payment_and_checkout(sql, sf, raw):
    s = sql["20_payment_friction"].set_index("payment_method").sort_index()
    p = m.payment_method_failures(raw["events"]).set_index("payment_method").sort_index()
    assert s["attempts"].tolist() == p["attempts"].tolist() and s["failed_attempts"].tolist() == p["failed_attempts"].tolist()
    r, q = sql["22_payment_retry_recovery"].iloc[0], m.retry_recovery(sf, raw["events"])
    assert r["sessions_with_failure"] == q["sessions_with_failure"] and r["recovered"] == q["recovered"]
    c = sql["21_checkout_friction"].sort_values(["checkout_type", "shipping"]).reset_index(drop=True)
    d = m.checkout_friction(sf, raw["events"]).sort_values(["checkout_type", "shipping"]).reset_index(drop=True)
    assert c["checkout_sessions"].tolist() == d["checkout_sessions"].tolist() and c["purchases"].tolist() == d["purchases"].tolist()


def test_orders_vs_strict_purchases_gap_is_the_documented_anomaly(sf, raw):
    gap = len(raw["orders"]) - int(sf["reached_purchase"].sum())
    assert gap == int(((sf.has_purchase_event == 1) & (sf.reached_purchase == 0)).sum()) == 12
