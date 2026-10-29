"""Capture dashboard screenshots (needs playwright; run from repo root with the app on port 8501)."""
from playwright.sync_api import sync_playwright
out = "screenshots/"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 1000})
    pg.goto("http://localhost:8501"); pg.wait_for_selector("text=Executive overview", timeout=60000); pg.wait_for_timeout(4000)
    pg.screenshot(path=out + "01_executive_overview.png", full_page=True)
    pg.get_by_text("2 · Funnel & segments").click(); pg.wait_for_selector("h1:has-text('Funnel & segment')", timeout=30000); pg.wait_for_timeout(4000)
    pg.screenshot(path=out + "02_funnel_segments.png", full_page=True)
    pg.get_by_text("3 · Business insights").click(); pg.wait_for_selector("h1:has-text('Business insights')", timeout=30000); pg.wait_for_timeout(3000)
    pg.screenshot(path=out + "03_business_insights.png", full_page=True)
    b.close()
