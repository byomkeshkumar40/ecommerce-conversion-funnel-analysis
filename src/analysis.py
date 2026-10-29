"""Run the full pandas analysis: writes reports/key_metrics.json, reports/segment_tables/*.csv and
static figures to reports/figures/. Usage: python -m src.analysis"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src import metrics as m

OUT = m.ROOT / "reports"
BLUE, RED, GREY = "#2a6fdb", "#d1495b", "#9aa5b1"


def main():
    (OUT / "figures").mkdir(parents=True, exist_ok=True)
    (OUT / "segment_tables").mkdir(parents=True, exist_ok=True)
    d = m.load_raw()
    sf = m.build_session_funnel(d["sessions"], d["events"], d["customers"])
    ft = m.funnel_table(sf)
    km = dict(headline=m.headline(sf), funnel=ft.to_dict("records"), abandonment=m.abandonment(sf),
              customer_level=m.customer_level(sf), repeat_purchase=m.repeat_purchase(d["orders"]),
              retry_recovery=m.retry_recovery(sf, d["events"]))
    for dim in ["device", "channel", "customer_type", "city_tier"]:
        t = m.segment_table(sf, dim)
        t.to_csv(OUT / "segment_tables" / f"{dim}.csv", index=False)
        km[f"segment_{dim}"] = t.to_dict("records")
    m.category_funnel(sf, d["events"], d["products"]).to_csv(OUT / "segment_tables" / "category.csv", index=False)
    m.payment_method_failures(d["events"]).to_csv(OUT / "segment_tables" / "payment_methods.csv", index=False)
    m.checkout_friction(sf, d["events"]).to_csv(OUT / "segment_tables" / "checkout_friction.csv", index=False)
    wk = m.weekly_trend(sf)
    wk.to_csv(OUT / "segment_tables" / "weekly_trend.csv", index=False)
    (OUT / "key_metrics.json").write_text(json.dumps(km, indent=2, default=str))

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(ft["stage"][::-1], ft["sessions"][::-1], color=BLUE)
    for i, (n, r) in enumerate(zip(ft["sessions"][::-1], ft["overall_conversion"][::-1])):
        ax.text(n, i, f" {n:,} ({r:.1%})", va="center", fontsize=9)
    ax.set_xlim(0, ft["sessions"].max() * 1.25)
    ax.set_title("Sessions reaching each funnel stage (% of all sessions)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "figures" / "funnel.png", dpi=150); plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), sharey=True)
    for ax, dim in zip(axes, ["device", "channel", "customer_type"]):
        t = m.segment_table(sf, dim)
        err = [t["purchase_rate_of_sessions"] - t["ci_low"], t["ci_high"] - t["purchase_rate_of_sessions"]]
        ax.bar(t["segment"], t["purchase_rate_of_sessions"], yerr=err, color=BLUE, capsize=3)
        ax.set_title(dim.replace("_", " ")); ax.tick_params(axis="x", rotation=30)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Purchase conversion by segment (95% Wilson CI)"); fig.tight_layout()
    fig.savefig(OUT / "figures" / "segments.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(2, 1, figsize=(9, 5.5), sharex=True)
    full = wk[wk["days_in_data"] == 7]
    ax[0].plot(full["week_start"], full["purchase_rate_of_sessions"], marker="o", color=BLUE)
    ax[0].set_title("Weekly purchase conversion (complete weeks)"); ax[0].yaxis.set_major_formatter(lambda v, _: f"{v:.1%}")
    ax[1].plot(full["week_start"], full["payment_to_purchase_rate"], marker="o", color=RED)
    ax[1].set_title("Weekly payment-attempt → purchase rate"); ax[1].yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    for a in ax: a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "figures" / "weekly_trend.png", dpi=150); plt.close(fig)
    print("wrote key_metrics.json, segment_tables/, figures/")


if __name__ == "__main__":
    main()
