"""Builds notebooks/01_funnel_exploration.ipynb from the cells below (so the notebook is reviewable as code).
Run:  python notebooks/build_notebook.py   then execute with:  jupyter nbconvert --to notebook --execute --inplace notebooks/01_funnel_exploration.ipynb"""
from pathlib import Path

import nbformat as nbf

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
cells = [
md("# E-commerce funnel — exploratory analysis\n**Data is synthetic** (seed 42, `src/generate_data.py`). Patterns below reflect generator assumptions; the notebook demonstrates method.\n\nUnit of analysis: **session**. Funnel is strict and chronological (see `sql/01_views.sql`)."),
code("import sys; sys.path.insert(0, '..')\nimport pandas as pd, matplotlib.pyplot as plt\nfrom src import metrics as m, validate\npd.set_option('display.width', 200)\nd = m.load_raw()\nfor k, v in d.items(): print(f'{k:12s}', v.shape)"),
md("## 1. Validate before analysing\nNothing is dropped; anomalies are counted."),
code("res = pd.DataFrame(validate.run_checks(d))\nprint(res['status'].value_counts().to_dict())\nres[res.status != 'PASS'][['status', 'check', 'count']]"),
md("## 2. Build the session-level funnel\nOne row per session, 0/1 flags per stage, first-timestamp rule prevents double counting."),
code("sf = m.build_session_funnel(d['sessions'], d['events'], d['customers'])\nsf.head()"),
code("ft = m.funnel_table(sf); ft.round(4)"),
code("# How much would naive event counting overstate the funnel?\nev = d['events']\nnaive = ev.groupby('event_type').size().reindex(m.STAGES)\npd.DataFrame({'event_rows': naive.values, 'distinct_sessions_strict': ft['sessions'].values}, index=m.STAGES)"),
md("Event rows exceed distinct sessions for product views (several per session) and payment attempts (retries). Counting rows would inflate step conversion — hence session-level flags."),
md("## 3. Segments\nPurchase rate per session with Wilson 95% CI and a one-vs-rest p-value. Segments overlap, so these are not independent effects."),
code("for dim in ['device', 'channel', 'customer_type', 'city_tier']:\n    print('\\n==', dim)\n    print(m.segment_table(sf, dim)[['segment','sessions','purchases','purchase_rate_of_sessions','ci_low','ci_high','p_vs_rest']].round(4).to_string(index=False))"),
md("### Do device and customer type confound each other?\nMobile is also the biggest device for new customers? Check the mix, and compare device within customer type."),
code("mix = pd.crosstab(sf.customer_type, sf.device, normalize='index').round(3); print(mix)\nsf.groupby(['customer_type','device']).agg(sessions=('session_id','size'), purchase_rate=('reached_purchase','mean')).round(4)"),
md("## 4. Trend and payment-stage friction"),
code("wk = m.weekly_trend(sf); wk[wk.days_in_data == 7].set_index('week_start')[['sessions','purchase_rate_of_sessions','payment_to_purchase_rate']].round(4).plot(subplots=True, figsize=(9, 6), marker='o'); plt.show()"),
code("print(m.payment_method_failures(d['events']).round(4)); print(m.retry_recovery(sf, d['events']))"),
code("m.checkout_friction(sf, d['events']).round(4)"),
md("**Caution:** this table conditions on sessions that already started checkout. Shipping fee is only recorded at `checkout_start`, so fee effects on cart→checkout cannot be observed directly (a limitation), and guest/fee groups differ in device and customer type."),
md("## 5. Customer-level vs session-level, repeat purchase"),
code("print(m.customer_level(sf)); print(m.repeat_purchase(d['orders']))"),
md("Repeat purchase is a lower bound: customers first seen late in the window have little time to buy again (right-censoring)."),
]
nb = nbf.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).parent / "01_funnel_exploration.ipynb")
