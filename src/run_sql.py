"""Build the SQLite database from data/raw CSVs and execute every analysis query.

Usage: python -m src.run_sql [--raw data/raw] [--db data/processed/ecommerce.db] [--out reports/sql_outputs]
Each sql/NN_name.sql (NN >= 10) is a single SELECT; its result is written to <out>/NN_name.csv.
"""
import argparse
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TABLES = ["customers", "products", "sessions", "events", "orders", "order_items"]


def build_db(raw, db):
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)
    con.executescript((ROOT / "sql" / "00_schema.sql").read_text())
    for t in TABLES:
        df = pd.read_csv(Path(raw) / f"{t}.csv")
        df.to_sql(t, con, if_exists="append", index=False)
    con.executescript((ROOT / "sql" / "01_views.sql").read_text())
    con.commit()
    return con


def run_queries(con, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    results = {}
    for f in sorted((ROOT / "sql").glob("[1-9][0-9]_*.sql")):
        df = pd.read_sql_query(f.read_text(), con)
        df.to_csv(out / f"{f.stem}.csv", index=False)
        results[f.stem] = df
        print(f"{f.stem:32s} {len(df):>3d} rows")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "data/raw"))
    ap.add_argument("--db", default=str(ROOT / "data/processed/ecommerce.db"))
    ap.add_argument("--out", default=str(ROOT / "reports/sql_outputs"))
    a = ap.parse_args()
    con = build_db(a.raw, a.db)
    print("PRAGMA foreign_key_check ->", con.execute("PRAGMA foreign_key_check").fetchall()[:5] or "no violations")
    run_queries(con, a.out)


if __name__ == "__main__":
    main()
