import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import metrics as m  # noqa: E402


@pytest.fixture(scope="session")
def raw():
    return m.load_raw()


@pytest.fixture(scope="session")
def sf(raw):
    return m.build_session_funnel(raw["sessions"], raw["events"], raw["customers"])


def tiny_tables():
    """Hand-built dataset with known answers (see tests/test_metrics.py)."""
    customers = pd.DataFrame({"customer_id": ["C1", "C2"], "city_tier": ["tier_1", "tier_2"],
                              "first_seen_date": ["2025-01-01"] * 2, "first_touch_channel": ["direct"] * 2})
    sessions = pd.DataFrame({
        "session_id": ["S1", "S2", "S3", "S4"], "customer_id": ["C1", "C1", "C2", "C2"],
        "session_start": ["2025-01-01 10:00:00", "2025-01-02 10:00:00", "2025-01-01 11:00:00", "2025-01-03 09:00:00"],
        "customer_type": ["new", "returning", "new", "returning"], "device": ["mobile", "desktop", "mobile", "mobile"],
        "channel": ["direct"] * 4})

    def ev(i, sid, cid, ts, typ, **kw):
        return dict(event_id=f"E{i}", session_id=sid, customer_id=cid, event_ts=ts, event_type=typ, product_id=kw.get("pid"),
                    quantity=None, guest_checkout=kw.get("guest"), shipping_fee=kw.get("fee"), payment_method=kw.get("pm"),
                    payment_status=kw.get("ps"), failure_reason=None)
    rows = [
        # S1: full purchase, with 3 repeated views + a duplicated add_to_cart row + one failed then successful payment
        ev(1, "S1", "C1", "2025-01-01 10:00:00", "session_start"),
        ev(2, "S1", "C1", "2025-01-01 10:00:10", "product_view", pid="P1"),
        ev(3, "S1", "C1", "2025-01-01 10:00:20", "product_view", pid="P1"),
        ev(4, "S1", "C1", "2025-01-01 10:00:30", "product_view", pid="P2"),
        ev(5, "S1", "C1", "2025-01-01 10:01:00", "add_to_cart", pid="P1"),
        ev(6, "S1", "C1", "2025-01-01 10:01:00", "add_to_cart", pid="P1"),
        ev(7, "S1", "C1", "2025-01-01 10:02:00", "checkout_start", guest=1, fee=49),
        ev(8, "S1", "C1", "2025-01-01 10:03:00", "payment_attempt", pm="upi", ps="failed"),
        ev(9, "S1", "C1", "2025-01-01 10:04:00", "payment_attempt", pm="card", ps="success"),
        ev(10, "S1", "C1", "2025-01-01 10:04:05", "purchase_complete"),
        # S2: abandons at cart
        ev(11, "S2", "C1", "2025-01-02 10:00:00", "session_start"),
        ev(12, "S2", "C1", "2025-01-02 10:00:10", "product_view", pid="P3"),
        ev(13, "S2", "C1", "2025-01-02 10:00:50", "add_to_cart", pid="P3"),
        # S3: bounce (no product view)
        ev(14, "S3", "C2", "2025-01-01 11:00:00", "session_start"),
        # S4: purchase event WITHOUT checkout_start (anomaly) -> must be excluded from strict funnel
        ev(15, "S4", "C2", "2025-01-03 09:00:00", "session_start"),
        ev(16, "S4", "C2", "2025-01-03 09:00:10", "product_view", pid="P1"),
        ev(17, "S4", "C2", "2025-01-03 09:00:50", "add_to_cart", pid="P1"),
        ev(18, "S4", "C2", "2025-01-03 09:02:00", "payment_attempt", pm="cod", ps="success"),
        ev(19, "S4", "C2", "2025-01-03 09:02:05", "purchase_complete"),
    ]
    events = pd.DataFrame(rows)
    for c in ["quantity", "guest_checkout", "shipping_fee"]:
        events[c] = events[c].astype("Int64")
    products = pd.DataFrame({"product_id": ["P1", "P2", "P3"], "category": ["Books", "Books", "Beauty"], "price": [100, 200, 300]})
    orders = pd.DataFrame({"order_id": ["O1", "O2"], "session_id": ["S1", "S4"], "customer_id": ["C1", "C2"],
                           "order_ts": ["2025-01-01 10:04:05", "2025-01-03 09:02:05"], "order_value": [149, 100],
                           "shipping_fee": [49, 0], "payment_method": ["card", "cod"], "payment_attempts": [2, 1]})
    return dict(customers=customers, sessions=sessions, events=events, products=products, orders=orders)


@pytest.fixture()
def tiny():
    return tiny_tables()
