"""
fetch_market_data.py
--------------------
Extracts raw market data into pandas DataFrames:

  1. Daily OHLCV prices for PSX-listed companies (via Yahoo Finance, `.KA` suffix)
  2. USD/PKR daily FX rate (`PKR=X`)
  3. KSE-100 benchmark index (`^KSE`)

Every frame is tagged with `loaded_at` (UTC) so dbt can run source-freshness
tests, and `is_synthetic` so downstream consumers can flag demo data.

The extractor is deliberately fault-tolerant: a single failed ticker is logged
and skipped instead of killing the whole batch — this is the behaviour you want
in a scheduled pipeline.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
import pandas as pd

import pandas as pd
import yfinance as yf

log = logging.getLogger("ingestion")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

FX_TICKER = "PKR=X"        # USD -> PKR
INDEX_TICKER = "^KSE"      # KSE-100 benchmark
HISTORY_PERIOD = "5y"      # trailing window of history to pull
REQUEST_PAUSE_S = 0.4      # be polite to the API


@dataclass
class ExtractResult:
    prices: pd.DataFrame = field(default_factory=pd.DataFrame)
    fx: pd.DataFrame = field(default_factory=pd.DataFrame)
    index: pd.DataFrame = field(default_factory=pd.DataFrame)
    tickers_ok: list[str] = field(default_factory=list)
    tickers_failed: list[str] = field(default_factory=list)


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """snake_case every column including the reset index (yfinance names vary)."""
    df = df.reset_index()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def _standardise_ohlcv(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Normalise a yfinance history frame to our raw schema."""
    df = _normalise_columns(df)
    df = df.rename(columns={"date": "trading_date", "datetime": "trading_date",
                            "index": "trading_date"})
    keep = ["trading_date", "open", "high", "low", "close", "adj_close", "volume"]
    df = df[keep].copy()
    df["trading_date"] = pd.to_datetime(df["trading_date"]).dt.date
    df["symbol"] = symbol
    df["loaded_at"] = datetime.now(timezone.utc)
    df["is_synthetic"] = False
    return df.dropna(subset=["close"])


def fetch_stock_prices(symbols: list[str]) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Download 5 years of daily OHLCV for each PSX symbol. Fault-tolerant."""
    frames, ok, failed = [], [], []
    for sym in symbols:
        yahoo_ticker = f"{sym}.KA"
        try:
            hist = yf.Ticker(yahoo_ticker).history(period=HISTORY_PERIOD, auto_adjust=False)
            if hist.empty:
                raise ValueError("empty history")
            frames.append(_standardise_ohlcv(hist, sym))
            ok.append(sym)
            log.info("  ✓ %-8s %5d rows", sym, len(hist))
        except Exception as exc:  # noqa: BLE001 - we want to survive any single failure
            failed.append(sym)
            log.warning("  ✗ %-8s skipped (%s)", sym, str(exc)[:80])
        time.sleep(REQUEST_PAUSE_S)
    prices = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return prices, ok, failed


def fetch_fx_rates() -> pd.DataFrame:
    """Daily USD/PKR exchange rate."""
    hist = yf.Ticker(FX_TICKER).history(period=HISTORY_PERIOD, auto_adjust=False)
    if hist.empty:
        raise RuntimeError(f"No FX data returned for {FX_TICKER}")
    df = _normalise_columns(hist).rename(columns={"date": "rate_date",
                                                  "datetime": "rate_date"})
    df["rate_date"] = pd.to_datetime(df["rate_date"]).dt.date
    df = df[["rate_date", "close"]].rename(columns={"close": "usd_pkr"}).dropna()
    df["loaded_at"] = datetime.now(timezone.utc)
    df["is_synthetic"] = False
    return df


def fetch_market_index() -> pd.DataFrame:
    """Daily KSE-100 index levels (benchmark).

    Yahoo serves this index sparsely under `period=` windows but exposes full
    history under `max` — so we pull max and trim client-side.
    """
    hist = yf.Ticker(INDEX_TICKER).history(period="max", auto_adjust=False)
    if hist.empty:
        raise RuntimeError(f"No index data returned for {INDEX_TICKER}")
    hist = hist[hist.index >= (pd.Timestamp.today(tz=hist.index.tz)
                               - pd.Timedelta(days=5 * 366))]
    df = _normalise_columns(hist).rename(columns={"date": "trading_date",
                                                  "datetime": "trading_date"})
    df["trading_date"] = pd.to_datetime(df["trading_date"]).dt.date
    df = df[["trading_date", "close", "volume"]].rename(columns={"close": "kse100_close"})
    df["loaded_at"] = datetime.now(timezone.utc)
    df["is_synthetic"] = False
    return df.dropna(subset=["kse100_close"])


def extract_all(symbols: list[str]) -> ExtractResult:
    """Full extraction run for every source."""
    result = ExtractResult()
    log.info("Extracting %d PSX symbols from Yahoo Finance…", len(symbols))
    result.prices, result.tickers_ok, result.tickers_failed = fetch_stock_prices(symbols)

    for name, fn, attr in [("USD/PKR FX", fetch_fx_rates, "fx"),
                           ("KSE-100 index", fetch_market_index, "index")]:
        try:
            df = fn()
            setattr(result, attr, df)
            log.info("  ✓ %-14s %5d rows", name, len(df))
        except Exception as exc:  # noqa: BLE001
            log.warning("  ✗ %-14s failed (%s)", name, str(exc)[:100])

    return result


if __name__ == "__main__":
    # smoke test
    res = extract_all(["HBL", "OGDC", "LUCK"])
    print(res.prices.tail())
