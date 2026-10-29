"""Streamlit dashboard. All numbers come from src/metrics.py (the same functions the tests
reconcile against SQL). Run:  streamlit run dashboard/app.py
Data: SYNTHETIC (see README / docs/DATA_DICTIONARY.md)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import metrics as m

PRIMARY, MUTED, ALERT = "#2a6fdb", "#9aa5b1", "#d1495b"
MIN_N = 500  # segments below this are flagged as low-sample

st.set_page_config(page_title="E-commerce Funnel Analysis", layout="wide")


@st.cache_data(show_spinner="Loading data…")
def load():
    d = m.load_raw()
    sf = m.build_session_funnel(d["sessions"], d["events"], d["customers"])
    return sf, d["events"], d["products"], d["orders"]


def pct(x, d=1):
    return "–" if pd.isna(x) else f"{x:.{d}%}"


def style(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), font=dict(size=13),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    return fig


if not (m.RAW / "events.csv").exists():
    st.error("Data not found. Generate it first: `python -m src.generate_data` (see README).")
    st.stop()
sf_all, events, products, orders = load()

st.sidebar.title("Funnel analysis")
page = st.sidebar.radio("Page", ["1 · Executive overview", "2 · Funnel & segments", "3 · Business insights"])
st.sidebar.markdown("**Filters** (apply to every page)")
dmin, dmax = sf_all["session_date"].min().date(), sf_all["session_date"].max().date()
dr = st.sidebar.date_input("Session date range", (dmin, dmax), min_value=dmin, max_value=dmax)
start, end = (dr[0], dr[1]) if isinstance(dr, tuple) and len(dr) == 2 else (dmin, dmax)
sel = {}
for key, col in [("Device", "device"), ("Channel", "channel"), ("Customer type", "customer_type"), ("City tier", "city_tier")]:
    opts = sorted(sf_all[col].unique())
    sel[col] = st.sidebar.multiselect(key, opts, default=opts)
sf = m.apply_filters(sf_all, start, end, sel["device"], sel["channel"], sel["customer_type"], sel["city_tier"])
st.sidebar.caption(f"{len(sf):,} of {len(sf_all):,} sessions selected")
st.sidebar.info("Data is **synthetic** (seed 42). Patterns reflect generator assumptions, not real shoppers.")

if len(sf) == 0:
    st.title("E-commerce Conversion Funnel")
    st.warning("No sessions match the current filters. Widen the filters in the sidebar.")
    st.stop()

h = m.headline(sf)
ft = m.funnel_table(sf)

# ------------------------------------------------------------------ page 1
if page.startswith("1"):
    st.title("Executive overview")
    st.caption("Unit of analysis: **session**. Purchase conversion = sessions with a (strictly ordered) purchase ÷ all sessions.")
    lo, hi = m.wilson_ci(h["purchases"], h["sessions"])
    c = st.columns(4)
    c[0].metric("Unique visitors", f"{h['visitors']:,}", help="Distinct customer_id with ≥1 session in the filtered range")
    c[1].metric("Sessions", f"{h['sessions']:,}")
    c[2].metric("Purchases (sessions)", f"{h['purchases']:,}")
    c[3].metric("Purchase conversion", pct(h["purchase_rate"], 2), help=f"95% CI {pct(lo, 2)} – {pct(hi, 2)}; denominator = {h['sessions']:,} sessions")

    left, right = st.columns([3, 2])
    with left:
        fig = go.Figure(go.Funnel(y=ft["stage"], x=ft["sessions"], texttemplate="%{value:,}<br>%{percentInitial:.1%}",
                                  marker=dict(color=PRIMARY)))
        fig.update_layout(title="Sessions reaching each stage (% of all sessions)")
        st.plotly_chart(style(fig, 420), width="stretch")
    with right:
        steps = ft.iloc[1:].copy()
        steps["step"] = m.STEP_NAMES
        steps = steps.sort_values("dropoff_from_previous")
        fig = px.bar(steps, x="dropoff_from_previous", y="step", orientation="h", text=steps["dropoff_from_previous"].map(pct),
                     title="Drop-off rate by step (% lost of previous stage)", color_discrete_sequence=[ALERT])
        fig.update_xaxes(tickformat=".0%", title=None)
        fig.update_yaxes(title=None)
        st.plotly_chart(style(fig, 420), width="stretch")
    top = steps.loc[steps["sessions_lost"].idxmax()]
    st.info(f"Largest observed loss in absolute sessions: **{top['step']}** — {int(top['sessions_lost']):,} sessions "
            f"({pct(top['dropoff_from_previous'])} of the previous stage). Steep view→cart steps are common in "
            "retail because many sessions are browsing; that is context, not a finding about why these sessions left.")

    wk = m.weekly_trend(sf)
    full_only = st.checkbox("Hide partial weeks (< 7 days of data in range)", value=True)
    if full_only:
        wk = wk[wk["days_in_data"] == 7]
    if len(wk):
        fig = px.line(wk, x="week_start", y="purchase_rate_of_sessions", markers=True, title="Weekly purchase conversion (by session week, Monday start)",
                      hover_data={"sessions": True, "purchases": True}, color_discrete_sequence=[PRIMARY])
        fig.update_yaxes(tickformat=".1%", title=None, rangemode="tozero")
        fig.update_xaxes(title=None)
        st.plotly_chart(style(fig, 340), width="stretch")
        st.caption("Weekly values with few sessions are noisy; hover to see session counts.")
    else:
        st.caption("No complete weeks in the selected range.")
    with st.expander("Funnel table and definitions"):
        t = ft.copy()
        for col in ["step_conversion", "overall_conversion", "dropoff_from_previous"]:
            t[col] = t[col].map(pct)
        st.dataframe(t, hide_index=True, width="stretch")
        st.markdown("- **step_conversion** = sessions at stage ÷ sessions at previous stage\n- **overall_conversion** = sessions at stage ÷ all sessions\n"
                    "- **dropoff_from_previous** = 1 − step_conversion")

# ------------------------------------------------------------------ page 2
elif page.startswith("2"):
    st.title("Funnel & segment analysis")
    dims = {"Device": "device", "Acquisition channel": "channel", "New vs returning": "customer_type", "City tier": "city_tier"}
    tabs = st.tabs(list(dims) + ["Product category"])
    for tab, (label, col) in zip(tabs[:-1], dims.items()):
        with tab:
            seg = m.segment_table(sf, col)
            low = seg[seg["sessions"] < MIN_N]
            if len(low):
                st.warning(f"Low sample (< {MIN_N} sessions): {', '.join(low['segment'])}. Treat rates as unreliable.")
            fig = go.Figure(go.Bar(x=seg["segment"], y=seg["purchase_rate_of_sessions"], marker_color=PRIMARY,
                                   error_y=dict(type="data", symmetric=False, array=seg["ci_high"] - seg["purchase_rate_of_sessions"],
                                                arrayminus=seg["purchase_rate_of_sessions"] - seg["ci_low"]),
                                   text=seg["purchase_rate_of_sessions"].map(lambda v: pct(v, 2)), textposition="inside", insidetextanchor="middle",
                                   textfont=dict(color="white", size=14)))
            fig.update_layout(title=f"Purchase conversion by {label.lower()} (bars = 95% Wilson CI)")
            fig.update_yaxes(tickformat=".0%", title=None, rangemode="tozero")
            st.plotly_chart(style(fig, 360), width="stretch")
            step_cols = ["step_view_to_cart", "step_cart_to_checkout", "step_checkout_to_payment", "step_payment_to_purchase"]
            heat = seg.set_index("segment")[step_cols]
            heat.columns = ["View→Cart", "Cart→Checkout", "Checkout→Payment", "Payment→Purchase"]
            fig = px.imshow(heat, text_auto=".1%", aspect="auto", color_continuous_scale="Blues",
                            title="Step-to-step conversion (denominator = sessions at the previous stage)")
            fig.update_coloraxes(showscale=False)
            st.plotly_chart(style(fig, 80 + 55 * len(heat)), width="stretch")
            show = seg[["segment", "sessions", "purchases", "purchase_rate_of_sessions", "ci_low", "ci_high", "p_vs_rest"]].copy()
            for k in ["purchase_rate_of_sessions", "ci_low", "ci_high"]:
                show[k] = show[k].map(lambda v: pct(v, 2))
            show["p_vs_rest"] = show["p_vs_rest"].map(lambda v: "–" if pd.isna(v) else ("<0.001" if v < 0.001 else f"{v:.3f}"))
            st.dataframe(show.rename(columns={"p_vs_rest": "p-value vs rest*"}), hide_index=True, width="stretch")
            st.caption("*Two-proportion z-test, segment vs all other selected sessions. A small p-value shows the gap is unlikely to be sampling noise; "
                       "it does not show why the gap exists. Segments overlap (e.g. mobile users skew toward new customers), so differences are not independent effects.")
    with tabs[-1]:
        cat = m.category_funnel(sf, events, products)
        if cat.empty:
            st.info("No product-view sessions in the selected range.")
        else:
            c1, c2 = st.columns(2)
            f1 = px.bar(cat, x="category", y="view_to_cart_rate", text=cat["view_to_cart_rate"].map(pct), title="View → cart rate by category",
                        color_discrete_sequence=[PRIMARY])
            f1.update_yaxes(tickformat=".0%", title=None)
            c1.plotly_chart(style(f1, 340), width="stretch")
            f2 = px.bar(cat, x="category", y="cart_to_purchase_rate", text=cat["cart_to_purchase_rate"].map(pct), title="Cart → purchase rate by category",
                        color_discrete_sequence=[MUTED])
            f2.update_yaxes(tickformat=".0%", title=None)
            c2.plotly_chart(style(f2, 340), width="stretch")
            st.dataframe(cat.assign(view_to_cart_rate=cat["view_to_cart_rate"].map(pct), cart_to_purchase_rate=cat["cart_to_purchase_rate"].map(pct)),
                         hide_index=True, width="stretch")
            st.caption("Unit = distinct session × category pair. A session that touched two categories appears in both rows, so rows are **not additive** and do not sum to the overall funnel. "
                       "Cart→purchase is session-level (the whole cart is bought or not), so it is not a category-specific purchase intent.")

# ------------------------------------------------------------------ page 3
else:
    st.title("Business insights")
    st.caption("Section A is computed live from the filtered data. Sections B–D are analyst judgement: hypotheses to test, not established causes.")
    st.subheader("A. Observed findings (current filters)")
    for f in m.derive_findings(sf):
        st.markdown(f"- {f}")
    pay = m.payment_method_failures(events[events["session_id"].isin(sf["session_id"])])
    rec = m.retry_recovery(sf, events)
    chk = m.checkout_friction(sf, events)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Payment attempts by method** (unit = attempt)")
        if len(pay):
            st.dataframe(pay.assign(attempt_failure_rate=pay["attempt_failure_rate"].map(pct)), hide_index=True, width="stretch")
        st.caption(f"Sessions with ≥1 failed attempt: {rec['sessions_with_failure']:,}; of these {pct(rec['recovery_rate'])} still purchased.")
    with c2:
        st.markdown("**Checkout sessions: guest vs account × shipping fee** (unit = session)")
        if len(chk):
            st.dataframe(chk.assign(checkout_to_payment_rate=chk["checkout_to_payment_rate"].map(pct),
                                    checkout_to_purchase_rate=chk["checkout_to_purchase_rate"].map(pct)), hide_index=True, width="stretch")
        st.caption("Association only: guest and account users also differ by device and customer type.")
    wk = m.weekly_trend(sf)
    wk = wk[wk["days_in_data"] == 7]
    if len(wk) >= 4:
        w = wk.loc[wk["payment_to_purchase_rate"].idxmin()]
        med = wk["payment_to_purchase_rate"].median()
        st.markdown(f"- Lowest weekly payment→purchase rate: week of **{w['week_start']:%Y-%m-%d}** at {pct(w['payment_to_purchase_rate'])} "
                    f"(median week {pct(med)}; {int(w['payment_attempts'])} attempting sessions that week). Worth a look in payment-gateway logs.")
    st.subheader("B. Hypotheses requiring further investigation")
    st.markdown("""
- **Mobile checkout friction** — mobile lags desktop at checkout→payment; could be form length, wallet/UPI hand-off or page speed. *Not tested.*
- **Guest checkout** — guest sessions progress less often than account sessions; account creation friction or lower intent are both plausible.
- **Shipping fees** — in the full data, fee-charged checkouts convert to payment less often only among account users (≈75% vs ≈79%) and not among guests; fee is unobserved for carts that never reach checkout, and cart value is a confounder.
- **Payment gateway incidents** — a dip in payment→purchase in one week suggests a method-specific outage; confirm with gateway logs.
- **Social/paid-search traffic quality** — lower conversion may reflect lower purchase intent rather than site problems.""")
    st.subheader("C. Prioritised recommendations")
    st.table(pd.DataFrame([
        ["1", "Investigate mobile checkout→payment step (session recordings, form analytics)", "Widest device gap at a single step (checkout→payment)", "Medium"],
        ["2", "Monitor payment-method success rates by day with alerting", "Method-level failure gaps and a weekly dip are visible", "Low"],
        ["3", "Test guest-checkout simplification / post-purchase account creation", "Guest vs account gap observed", "Medium"],
        ["4", "Review traffic quality for social and paid-search campaigns", "Lowest-converting channels", "Low"]],
        columns=["Priority", "Action", "Evidence (observed)", "Effort"]))
    st.subheader("D. Proposed experiments (none have been run)")
    st.table(pd.DataFrame([
        ["Show free-shipping progress bar in cart", "Carts below the free-shipping threshold", "Cart→checkout rate", "Average order value, return rate", "Reduces perceived fee friction / nudges larger carts", "A/B, randomise by user; 2-prop test; size via baseline rate"],
        ["Offer 'continue as guest' with one-page checkout on mobile", "Mobile new customers at checkout", "Checkout→payment rate", "Payment failure rate, support contacts", "Fewer form fields lower effort", "A/B by user; sequential monitoring off, fixed horizon"],
        ["Auto-suggest alternate payment method after a failed attempt", "Sessions with ≥1 failed payment", "Recovery rate (purchase after failure)", "Duplicate-charge reports, COD share", "Retry path removes dead end", "A/B by session; compare recovery rate"]],
        columns=["Experiment", "Target population", "Primary metric", "Guardrails", "Mechanism (hypothesis)", "Measurement"]))
    st.subheader("E. Limitations")
    st.markdown("""
- Synthetic data: patterns come from the generator's assumptions, so these findings demonstrate method, not real customer behaviour.
- Observational association only; confounding (device × customer type × channel) is not controlled.
- Customer type is defined by the first observed session in a 6-month window (left-censored).
- No price/discount, inventory or page-level data; ~12 injected anomalies and duplicate events are documented in the data-quality report.""")
