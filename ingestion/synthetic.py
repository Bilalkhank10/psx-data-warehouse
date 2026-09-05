"""
synthetic.py
------------
Deterministic, realistic synthetic PSX data used when the live API is
unreachable (sandboxed CI runners, IP throttling, etc.).

The generator deliberately encodes realistic structure so the dbt models and
dashboard still demonstrate something meaningful:

  * geometric Brownian motion per stock with a shared market factor
  * sector betas (banking/energy/cement co-move, tech is idiosyncratic)
  * USD/PKR as a drifting random walk (100 -> ~280 over five years)
  * an equal-weight-implied KSE-100 proxy with market shocks

Everything is driven by a fixed seed => identical data on every CI run,
which keeps the dbt test suite deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

SEED = 42
TRADING_DAYS = 5 * 247  # ~5 years of business days

SECTOR_BETA = {
    "Commercial Banks": 1.00, "Oil & Gas Exploration": 0.95, "Oil Marketing": 1.05,
    "Power Generation": 0.90, "Cement": 1.15, "Fertilizer": 0.85,
    "Technology": 1.35, "Textile": 1.10, "Automobile": 1.10,
}


def _trading_calendar() -> pd.DatetimeIndex:
    end = pd.Timestamp.today().normalize()
    start = end - pd.Timedelta(days=int(TRADING_DAYS * 1.55))
    days = pd.bdate_range(start=start, end=end)  # Mon–Fri
    return days[-TRADING_DAYS:]


def generate(stocks: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Returns {'prices', 'fx', 'index'} DataFrames matching the raw schema."""
    rng = np.random.default_rng(SEED)
    days = _trading_calendar()
    n = len(days)
    now = datetime.now(timezone.utc)

    # --- shared market factor with occasional shocks (crises, rallies) ---
    market_ret = rng.normal(0.0006, 0.009, n)
    shock_days = rng.choice(n, size=6, replace=False)
    market_ret[shock_days] += rng.normal(0, 0.035, 6)

    frames = []
    for _, row in stocks.iterrows():
        beta = SECTOR_BETA.get(row["sector"], 1.0)
        sigma = 0.018 if "Technology" in row["sector"] else 0.014
        alpha = rng.uniform(-0.0002, 0.0006)
        ret = alpha + beta * market_ret + rng.normal(0, sigma, n)
        ret = np.clip(ret, -0.075, 0.075)  # PSX circuit breakers
        close = rng.uniform(15, 450) * np.exp(np.cumsum(ret))
        open_ = close * (1 + rng.normal(0, 0.004, n))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, n)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, n)))
        volume = (rng.lognormal(13, 0.8, n) * (1 + 4 * np.abs(ret))).astype(int)
        frames.append(pd.DataFrame({
            "trading_date": days.date, "open": open_.round(2), "high": high.round(2),
            "low": low.round(2), "close": close.round(2), "adj_close": close.round(2),
            "volume": volume, "symbol": row["symbol"], "loaded_at": now,
            "is_synthetic": True,
        }))
    prices = pd.concat(frames, ignore_index=True)

    # --- USD/PKR: depreciation drift ~ 22%/yr ---
    fx_ret = rng.normal(0.0007, 0.0015, n)
    usd_pkr = 105.0 * np.exp(np.cumsum(fx_ret))
    fx = pd.DataFrame({"rate_date": days.date, "usd_pkr": usd_pkr.round(2),
                       "loaded_at": now, "is_synthetic": True})

    # --- KSE-100 proxy: 45_000 * exp(cumsum(market + drift)) ---
    idx_ret = market_ret + 0.0003 + rng.normal(0, 0.002, n)
    kse = 45_000 * np.exp(np.cumsum(idx_ret))
    index = pd.DataFrame({"trading_date": days.date, "kse100_close": kse.round(2),
                          "volume": (rng.lognormal(18, 0.6, n)).astype(int),
                          "loaded_at": now, "is_synthetic": True})

    return {"prices": prices, "fx": fx, "index": index}
