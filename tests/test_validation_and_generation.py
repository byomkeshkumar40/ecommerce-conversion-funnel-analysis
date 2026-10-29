import copy

import pandas as pd

from src import generate_data, validate
from src import metrics as m


def statuses(res):
    return {r["check"]: r["status"] for r in res}


def test_real_data_has_no_failures(raw):
    res = validate.run_checks(raw)
    assert [r for r in res if r["status"] == "FAIL"] == []
    warns = [r["check"] for r in res if r["status"] == "WARN"]
    assert any("duplicate events" in w for w in warns) and any("funnel ordering" in w for w in warns)


def test_validator_detects_duplicate_ids(raw):
    bad = copy.deepcopy(raw)
    bad["sessions"] = pd.concat([bad["sessions"], bad["sessions"].iloc[[0]]])
    st = statuses(validate.run_checks(bad))
    assert st["unique primary key: sessions.session_id"] == "FAIL"


def test_validator_detects_orphans_and_bad_timestamps(raw):
    bad = copy.deepcopy(raw)
    bad["events"] = bad["events"].copy()
    bad["events"].loc[0, "session_id"] = "S_NOPE"
    bad["events"].loc[1, "event_ts"] = "not a date"
    st = statuses(validate.run_checks(bad))
    assert st["foreign key: events.session_id -> sessions.session_id"] == "FAIL"
    assert st["timestamp parses: events.event_ts"] == "FAIL"


def test_validator_detects_event_before_session_start(raw):
    bad = copy.deepcopy(raw)
    bad["events"] = bad["events"].copy()
    i = bad["events"].index[bad["events"].event_type == "product_view"][0]
    bad["events"].loc[i, "event_ts"] = "2024-12-31 00:00:00"
    assert statuses(validate.run_checks(bad))["no event earlier than its session_start"] == "FAIL"


def test_generation_is_deterministic_and_coherent():
    a, la = generate_data.generate(seed=7, n_customers=3000)
    b, lb = generate_data.generate(seed=7, n_customers=3000)
    for k in a:
        pd.testing.assert_frame_equal(a[k], b[k])
    c, _ = generate_data.generate(seed=8, n_customers=3000)
    assert not a["events"].equals(c["events"])
    res = validate.run_checks(a)
    assert [r["check"] for r in res if r["status"] == "FAIL"] == []
    assert 1 <= len(la["injected_missing_checkout_sessions"]) <= 12


def test_generated_csv_matches_fresh_regeneration(raw):
    t, _ = generate_data.generate()
    assert len(t["events"]) == len(raw["events"]) and len(t["orders"]) == len(raw["orders"])
    assert t["events"]["event_id"].equals(raw["events"]["event_id"])
