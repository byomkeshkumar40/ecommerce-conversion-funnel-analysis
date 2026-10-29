"""Known-answer tests on a hand-built dataset, plus edge cases."""
import math

import pandas as pd

from src import metrics as m


def test_strict_funnel_known_answer(tiny):
    sf = m.build_session_funnel(tiny["sessions"], tiny["events"], tiny["customers"])
    ft = m.funnel_table(sf)
    # S1 full; S2 cart; S3 bounce; S4 has purchase event but no checkout_start -> stops at cart
    assert ft["sessions"].tolist() == [4, 3, 3, 1, 1, 1]


def test_no_double_counting_of_repeated_events(tiny):
    sf = m.build_session_funnel(tiny["sessions"], tiny["events"], tiny["customers"])
    assert sf["reached_view"].sum() == 3  # S1 had 3 view rows but counts once
    assert sf.loc[sf.session_id == "S1", ["reached_cart", "reached_payment", "reached_purchase"]].iloc[0].tolist() == [1, 1, 1]


def test_out_of_order_events_are_not_counted(tiny):
    ev = tiny["events"].copy()
    ev.loc[ev.event_id == "E7", "event_ts"] = "2025-01-01 09:00:00"  # checkout before cart
    sf = m.build_session_funnel(tiny["sessions"], ev, tiny["customers"])
    s1 = sf[sf.session_id == "S1"].iloc[0]
    assert (s1.reached_cart, s1.reached_checkout, s1.reached_purchase) == (1, 0, 0)


def test_anomalous_purchase_is_flagged_not_dropped(tiny):
    sf = m.build_session_funnel(tiny["sessions"], tiny["events"], tiny["customers"])
    s4 = sf[sf.session_id == "S4"].iloc[0]
    assert s4.has_purchase_event == 1 and s4.reached_purchase == 0
    assert len(sf) == 4  # nothing silently removed


def test_headline_and_denominators(tiny):
    sf = m.build_session_funnel(tiny["sessions"], tiny["events"], tiny["customers"])
    h = m.headline(sf)
    assert h == dict(sessions=4, visitors=2, purchases=1, purchase_rate=0.25)
    ab = m.abandonment(sf)
    assert ab["carts"] == 3 and math.isclose(ab["cart_abandonment_rate"], 2 / 3)
    assert ab["checkouts"] == 1 and ab["checkout_abandonment_rate"] == 0


def test_customer_level_differs_from_session_level(tiny):
    sf = m.build_session_funnel(tiny["sessions"], tiny["events"], tiny["customers"])
    cl = m.customer_level(sf)
    assert cl["customers"] == 2 and cl["purchasing_customers"] == 1
    assert cl["customer_conversion_rate"] == 0.5 and cl["session_conversion_rate"] == 0.25
    assert cl["first_session_conversion_rate"] == 0.5


def test_payment_helpers_ignore_duplicates(tiny):
    dup = pd.concat([tiny["events"], tiny["events"][tiny["events"].event_id == "E8"].assign(event_id="E99")])
    pm = m.payment_method_failures(dup).set_index("payment_method")
    assert pm.loc["upi", "attempts"] == 1 and pm.loc["upi", "failed_attempts"] == 1
    sf = m.build_session_funnel(tiny["sessions"], tiny["events"], tiny["customers"])
    assert m.retry_recovery(sf, dup)["recovery_rate"] == 1.0


def test_category_funnel_known(tiny):
    sf = m.build_session_funnel(tiny["sessions"], tiny["events"], tiny["customers"])
    cat = m.category_funnel(sf, tiny["events"], tiny["products"]).set_index("category")
    assert cat.loc["Books", "viewed_sessions"] == 2 and cat.loc["Books", "carted_sessions"] == 2
    assert cat.loc["Books", "purchased_sessions"] == 1
    assert cat.loc["Beauty", "viewed_sessions"] == 1 and cat.loc["Beauty", "purchased_sessions"] == 0


def test_empty_dataset_edge_cases(tiny):
    sf = m.build_session_funnel(tiny["sessions"], tiny["events"], tiny["customers"]).iloc[0:0]
    ft = m.funnel_table(sf)
    assert ft["sessions"].sum() == 0 and ft["step_conversion"].isna().all()
    assert math.isnan(m.headline(sf)["purchase_rate"])
    assert m.segment_table(sf, "device").empty
    assert m.derive_findings(sf) == ["No sessions match the current filters."]
    assert all(math.isnan(x) for x in m.wilson_ci(0, 0))


def test_zero_denominator_returns_nan_not_error(tiny):
    sf = m.build_session_funnel(tiny["sessions"], tiny["events"], tiny["customers"])
    only_bounce = sf[sf.session_id == "S3"]
    ab = m.abandonment(only_bounce)
    assert ab["carts"] == 0 and math.isnan(ab["cart_abandonment_rate"])


def test_wilson_and_ztest_sanity():
    lo, hi = m.wilson_ci(50, 1000)
    assert 0 <= lo < 0.05 < hi <= 1
    assert m.wilson_ci(0, 10)[0] == 0.0
    assert m.two_prop_p_value(50, 1000, 50, 1000) > 0.99
    assert m.two_prop_p_value(100, 1000, 50, 1000) < 0.001


def test_filters(sf):
    only = m.apply_filters(sf, devices=["desktop"])
    assert set(only.device) == {"desktop"}
    assert len(m.apply_filters(sf, devices=[])) == 0
    assert len(m.apply_filters(sf)) == len(sf)
    d = m.apply_filters(sf, start="2025-03-01", end="2025-03-31")
    assert d.session_date.min() >= pd.Timestamp("2025-03-01") and d.session_date.max() <= pd.Timestamp("2025-03-31")
