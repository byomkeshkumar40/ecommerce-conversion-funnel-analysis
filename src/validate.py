"""Data-quality checks on the raw tables. Nothing is dropped or modified here: every
problem is counted and reported. Status values:
  PASS  the check found nothing
  WARN  a known/expected anomaly under its documented tolerance (reported, not hidden)
  FAIL  structural problem or tolerance exceeded -> do not trust downstream numbers

Usage: python -m src.validate [--raw data/raw] [--out reports/data_quality_report.md]
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from src import metrics as m

DUP_TOLERANCE = 0.01  # duplicate event rows allowed (as share of rows) before FAIL
KEY_COLS = ["session_id", "event_type", "event_ts", "product_id", "payment_method", "payment_status"]


def _r(name, status, detail, count=0):
    return dict(check=name, status=status, count=int(count), detail=detail)


def run_checks(t):
    c, p, s, e, o, oi = (t[k] for k in ["customers", "products", "sessions", "events", "orders", "order_items"])
    res = []

    for name, df, col in [("customers", c, "customer_id"), ("products", p, "product_id"),
                          ("sessions", s, "session_id"), ("events", e, "event_id"),
                          ("orders", o, "order_id")]:
        d = int(df[col].duplicated().sum())
        res.append(_r(f"unique primary key: {name}.{col}", "PASS" if d == 0 else "FAIL", f"{d} duplicate keys", d))
    d = int(o["session_id"].duplicated().sum())
    res.append(_r("one order per session: orders.session_id unique", "PASS" if d == 0 else "FAIL", f"{d} duplicates", d))

    for child, col, parent, pcol, df, pdf in [
        ("sessions", "customer_id", "customers", "customer_id", s, c),
        ("events", "session_id", "sessions", "session_id", e, s),
        ("events", "customer_id", "customers", "customer_id", e, c),
        ("orders", "session_id", "sessions", "session_id", o, s),
        ("orders", "customer_id", "customers", "customer_id", o, c),
        ("order_items", "order_id", "orders", "order_id", oi, o),
        ("order_items", "product_id", "products", "product_id", oi, p)]:
        bad = int((~df[col].isin(pdf[pcol])).sum())
        res.append(_r(f"foreign key: {child}.{col} -> {parent}.{pcol}", "PASS" if bad == 0 else "FAIL", f"{bad} orphans", bad))
    nn = e.loc[e["event_type"] == "product_view", "product_id"].isna().sum() + \
        e.loc[e["event_type"] == "add_to_cart", "product_id"].isna().sum()
    res.append(_r("product events carry a product_id", "PASS" if nn == 0 else "FAIL", f"{nn} missing", nn))

    miss_req = int(s[["session_id", "customer_id", "session_start", "device", "channel", "customer_type"]].isna().sum().sum()
                   + e[["event_id", "session_id", "event_ts", "event_type"]].isna().sum().sum())
    res.append(_r("no missing values in required columns", "PASS" if miss_req == 0 else "FAIL", f"{miss_req} nulls", miss_req))

    for name, df, col in [("sessions.session_start", s, "session_start"), ("events.event_ts", e, "event_ts"),
                          ("orders.order_ts", o, "order_ts")]:
        ts = pd.to_datetime(df[col], errors="coerce")
        bad = int(ts.isna().sum())
        res.append(_r(f"timestamp parses: {name}", "PASS" if bad == 0 else "FAIL", f"{bad} unparseable", bad))
        lo, hi = ts.min(), ts.max()
        res.append(_r(f"timestamp range: {name}", "PASS" if lo >= pd.Timestamp("2025-01-01") and hi < pd.Timestamp("2025-08-01") else "WARN",
                      f"{lo} .. {hi}"))
    unknown = set(e["event_type"]) - set(m.STAGES)
    res.append(_r("event_type values known", "PASS" if not unknown else "FAIL", f"unknown: {sorted(unknown)}", len(unknown)))

    # From here on, unparseable timestamps become NaT (already reported above) instead of crashing.
    e = e.assign(event_ts=pd.to_datetime(e["event_ts"], errors="coerce"))
    s = s.assign(session_start=pd.to_datetime(s["session_start"], errors="coerce"))
    o = o.assign(order_ts=pd.to_datetime(o["order_ts"], errors="coerce"))

    dups = int(e.duplicated(subset=KEY_COLS).sum())
    share = dups / len(e)
    res.append(_r("duplicate events (same session/type/ts/product/payment, different event_id)",
                  "PASS" if dups == 0 else ("WARN" if share <= DUP_TOLERANCE else "FAIL"),
                  f"{dups} rows = {share:.2%} of events; funnel uses first timestamp per session so unaffected", dups))

    ev = e.merge(s[["session_id", "session_start"]], on="session_id")
    before = int((ev["event_ts"] < ev["session_start"]).sum())
    res.append(_r("no event earlier than its session_start", "PASS" if before == 0 else "FAIL", f"{before} events", before))
    no_start = int((~s["session_id"].isin(e.loc[e["event_type"] == "session_start", "session_id"])).sum())
    res.append(_r("every session has a session_start event", "PASS" if no_start == 0 else "FAIL", f"{no_start} sessions", no_start))

    p_sess = set(e.loc[e["event_type"] == "purchase_complete", "session_id"])
    sf = m.build_session_funnel(s, e, c)
    # funnel ordering: later event present without a (chronologically valid) earlier one
    order_bad = {}
    has = e.pivot_table(index="session_id", columns="event_type", values="event_ts", aggfunc="min")
    for later, earlier in zip(m.STAGES[2:], m.STAGES[1:-1]):
        later_present = has[later].notna()
        bad = later_present & (has[earlier].isna() | (has[later] < has[earlier]))
        order_bad[f"{later} without valid {earlier}"] = int(bad.sum())
    total_bad = int(sum(order_bad.values()))
    res.append(_r("funnel ordering: stage event present without preceding stage",
                  "PASS" if total_bad == 0 else ("WARN" if total_bad <= 0.01 * max(len(p_sess), 1) else "FAIL"),
                  f"{order_bad} — these sessions are excluded from later strict-funnel stages but counted here", total_bad))
    no_flag = int(((sf["has_purchase_event"] == 1) & (sf["reached_purchase"] == 0)).sum())
    res.append(_r("purchase events excluded from strict funnel (reported, not dropped)", "PASS" if no_flag == 0 else "WARN",
                  f"{no_flag} sessions have purchase_complete but fail the strict chain", no_flag))

    o_sess = set(o["session_id"])
    res.append(_r("orders <-> purchase_complete events match by session", "PASS" if o_sess == p_sess else "FAIL",
                  f"{len(o_sess - p_sess)} orders w/o event, {len(p_sess - o_sess)} events w/o order", len(o_sess ^ p_sess)))
    ot = o.merge(ev[ev["event_type"] == "purchase_complete"].groupby("session_id")["event_ts"].min().rename("pts").reset_index(), on="session_id")
    mism = int((ot["order_ts"] != ot["pts"]).sum())
    res.append(_r("order_ts equals purchase_complete timestamp", "PASS" if mism == 0 else "FAIL", f"{mism} mismatches", mism))
    ps = e[(e["event_type"] == "payment_attempt")]
    bad_status = int((~ps["payment_status"].isin(["success", "failed"])).sum())
    res.append(_r("payment_status in {success, failed}", "PASS" if bad_status == 0 else "FAIL", f"{bad_status} bad", bad_status))
    val = int((o["order_value"] <= 0).sum() + (p["price"] <= 0).sum())
    res.append(_r("positive prices and order values", "PASS" if val == 0 else "FAIL", f"{val} non-positive", val))

    rates = [m.headline(sf)["purchase_rate"]] + list(m.funnel_table(sf)["step_conversion"])
    for dim in ["device", "channel", "customer_type", "city_tier"]:
        rates += list(m.segment_table(sf, dim)["purchase_rate_of_sessions"])
    ok = all(0.0 <= r <= 1.0 for r in rates)
    res.append(_r("all computed conversion rates within [0, 1]", "PASS" if ok else "FAIL", f"{len(rates)} rates checked"))
    mono = all(sf[a].sum() >= sf[b].sum() for a, b in zip(m.FLAGS, m.FLAGS[1:]))
    res.append(_r("funnel counts non-increasing by stage", "PASS" if mono else "FAIL", ""))
    return res


def to_markdown(res):
    lines = ["# Data Quality Report", "", "Generated by `python -m src.validate`. No records were removed or altered.", "",
             "| Status | Check | Count | Detail |", "|---|---|---:|---|"]
    lines += [f"| {r['status']} | {r['check']} | {r['count']} | {r['detail']} |" for r in res]
    n = {k: sum(r["status"] == k for r in res) for k in ["PASS", "WARN", "FAIL"]}
    lines += ["", f"**Summary:** {n['PASS']} PASS, {n['WARN']} WARN (documented injected anomalies), {n['FAIL']} FAIL."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(m.RAW))
    ap.add_argument("--out", default=str(m.ROOT / "reports" / "data_quality_report.md"))
    a = ap.parse_args()
    res = run_checks(m.load_raw(a.raw))
    Path(a.out).write_text(to_markdown(res))
    Path(a.out).with_suffix(".json").write_text(json.dumps(res, indent=2))
    for r in res:
        print(f"[{r['status']}] {r['check']}: {r['detail']}")
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
