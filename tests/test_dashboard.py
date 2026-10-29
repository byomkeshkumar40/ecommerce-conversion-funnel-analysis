"""Smoke + consistency tests for the Streamlit app using Streamlit's AppTest runner."""
import pytest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src import metrics as m

APP = str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py")
PAGES = ["1 · Executive overview", "2 · Funnel & segments", "3 · Business insights"]


@pytest.mark.parametrize("page", PAGES)
def test_pages_render_without_exception(page):
    at = AppTest.from_file(APP, default_timeout=180).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception


def metric_values(at):
    return {x.label: x.value for x in at.metric}


def test_overview_kpis_match_pipeline(sf):
    at = AppTest.from_file(APP, default_timeout=180).run()
    h = m.headline(sf)
    v = metric_values(at)
    assert v["Sessions"] == f"{h['sessions']:,}"
    assert v["Unique visitors"] == f"{h['visitors']:,}"
    assert v["Purchase conversion"] == f"{h['purchase_rate']:.2%}"


def test_device_filter_changes_kpis_consistently(sf):
    at = AppTest.from_file(APP, default_timeout=180).run()
    ms = next(w for w in at.sidebar.multiselect if w.label == "Device")
    ms.set_value(["desktop"]).run()
    h = m.headline(m.apply_filters(sf, devices=["desktop"]))
    v = metric_values(at)
    assert v["Sessions"] == f"{h['sessions']:,}" and v["Purchase conversion"] == f"{h['purchase_rate']:.2%}"


def test_empty_filter_shows_warning_not_crash():
    at = AppTest.from_file(APP, default_timeout=180).run()
    next(w for w in at.sidebar.multiselect if w.label == "Channel").set_value([]).run()
    assert not at.exception and len(at.warning) >= 1


def test_date_and_customer_type_filters_match_pipeline(sf):
    import datetime as dt
    at = AppTest.from_file(APP, default_timeout=180).run()
    next(w for w in at.sidebar.multiselect if w.label == "Customer type").set_value(["returning"])
    at.sidebar.date_input[0].set_value((dt.date(2025, 3, 1), dt.date(2025, 3, 31))).run()
    assert not at.exception
    h = m.headline(m.apply_filters(sf, "2025-03-01", "2025-03-31", customer_types=["returning"]))
    v = metric_values(at)
    assert v["Sessions"] == f"{h['sessions']:,}" and v["Purchase conversion"] == f"{h['purchase_rate']:.2%}"
