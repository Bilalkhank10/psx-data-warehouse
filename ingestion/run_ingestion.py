"""
run_ingestion.py
----------------
Entry point for the extract-and-load stage.

    python ingestion/run_ingestion.py            # live Yahoo Finance data
    python ingestion/run_ingestion.py --offline  # synthetic demo data
    python ingestion/run_ingestion.py --offline-if-fail   # live, w/ fallback

Behaviour:
  * reads the stock universe from dbt/seeds/stocks.csv (single source of truth)
  * extracts prices + FX + index
  * lands raw Parquet snapshots under data/raw/ (partitioned by load date)
  * loads typed tables into warehouse.duckdb  ->  raw_psx_prices, raw_fx_rates,
    raw_market_index  (idempotent full refresh)

The load layer is intentionally dumb (CREATE OR REPLACE) — all modelling logic
lives in dbt, which is the separation of concerns an analytics engineer wants.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from fetch_market_data import extract_all  # noqa: E402
from synthetic import generate  # noqa: E402

log = logging.getLogger("ingestion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = PROJECT_ROOT / "warehouse.duckdb"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SEEDS = PROJECT_ROOT / "dbt" / "seeds" / "stocks.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PSX data ingestion")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--offline", action="store_true", help="force synthetic data")
    g.add_argument("--offline-if-fail", action="store_true",
                   help="try live fetch first, fall back to synthetic")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    stocks = pd.read_csv(SEEDS)
    symbols = stocks["symbol"].tolist()
    log.info("Universe loaded from seeds/stocks.csv: %d symbols", len(symbols))

    synthetic = args.offline
    if not args.offline:
        try:
            res = extract_all(symbols)
            if res.prices.empty or res.fx.empty:
                raise RuntimeError("live extraction returned empty frames")
            tables = {"prices": res.prices, "fx": res.fx, "index": res.index}
            log.info("Live extraction OK (%d/%d symbols)", len(res.tickers_ok), len(symbols))
        except Exception as exc:  # noqa: BLE001
            if not args.offline_if_fail:
                log.error("Live extraction failed: %s", exc)
                return 1
            log.warning("Live extraction failed (%s) — falling back to synthetic data", exc)
            synthetic = True

    if args.offline or synthetic:
        tables = generate(stocks)
        log.warning("Using SYNTHETIC data (is_synthetic = true in every raw table)")

    # ---------- land raw parquet snapshots ----------
    load_date = pd.Timestamp.utcnow().date()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        out = RAW_DIR / f"{name}" / f"load_date={load_date}"
        out.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out / "data.parquet", index=False)

    # ---------- load into duckdb (idempotent full refresh) ----------
    # An empty optional source (e.g. ^KSE index feed dead upstream) must NOT
    # crash the load: we still create the table with the expected schema so
    # dbt sources resolve, downstream joins degrade to NULLs, and the docs
    # already describe the fallback behaviour. Blocking load: prices/fx empty.
    expected_cols = {
        "prices": ["trading_date", "open", "high", "low", "close", "adj_close",
                   "volume", "symbol", "loaded_at", "is_synthetic"],
        "fx": ["rate_date", "usd_pkr", "loaded_at", "is_synthetic"],
        "index": ["trading_date", "kse100_close", "volume", "loaded_at",
                  "is_synthetic"],
    }
    con = duckdb.connect(str(WAREHOUSE))
    for df_name, table_name in [("prices", "raw_psx_prices"),
                                ("fx", "raw_fx_rates"),
                                ("index", "raw_market_index")]:
        df = tables[df_name]
        if df.empty:
            log.warning("%s: extract empty — creating schema-only table",
                        table_name)
            df = pd.DataFrame(columns=expected_cols[df_name])
        con.register("_stage", df)
        con.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM _stage")
        con.unregister("_stage")

    counts = con.execute("""
        SELECT 'raw_psx_prices' tbl, count(*) n FROM raw_psx_prices UNION ALL
        SELECT 'raw_fx_rates', count(*) FROM raw_fx_rates UNION ALL
        SELECT 'raw_market_index', count(*) FROM raw_market_index
    """).fetchall()
    con.close()

    log.info("Loaded into %s:", WAREHOUSE.name)
    for tbl, n in counts:
        log.info("  %-18s %7d rows", tbl, n)
    log.info("Ingestion finished ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
