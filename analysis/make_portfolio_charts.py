"""
make_portfolio_charts.py
------------------------
Exports presentation-ready PNG charts (assets/) from the modeled warehouse —
used in the README and on the portfolio website. Pure matplotlib, no server.

Run after the dbt build:
    python analysis/make_portfolio_charts.py
"""

from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

GREEN, DARK, MUTED, GRID = "#0e7c3a", "#1a1f24", "#8f97a3", "#e5e9ec"
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "axes.titlesize": 14, "axes.titleweight": "bold",
    "axes.labelcolor": DARK, "text.color": DARK, "xtick.color": MUTED,
    "ytick.color": MUTED,
})

con = duckdb.connect(str(ROOT / "warehouse.duckdb"), read_only=True)

# ---------------------------------------------------------- 1. market trend
m = con.execute("""SELECT trading_date, equal_weight_index FROM fct_market_summary
                   ORDER BY trading_date""").fetchdf()
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(m["trading_date"], m["equal_weight_index"], color=GREEN, lw=1.8)
ax.fill_between(m["trading_date"], m["equal_weight_index"], alpha=0.08, color=GREEN)
ax.set_title("PSX 20-stock equal-weight universe index (base = 100)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
fig.tight_layout()
fig.savefig(ASSETS / "chart_market_overview.png", dpi=160)
plt.close(fig)

# ------------------------------------------------------ 2. sector 1y returns
s = con.execute("""SELECT sector, avg_return_1y FROM agg_sector_performance
                   ORDER BY avg_return_1y""").fetchdf()
fig, ax = plt.subplots(figsize=(10, 5.4))
colors = [GREEN if v >= 0 else "#c0392b" for v in s["avg_return_1y"]]
ax.barh(s["sector"], s["avg_return_1y"] * 100, color=colors)
for i, v in enumerate(s["avg_return_1y"] * 100):
    ax.text(v + (1.5 if v >= 0 else -1.5), i, f"{v:+.0f}%",
            va="center", ha="left" if v >= 0 else "right", fontsize=10, color=DARK)
ax.set_title("Average trailing 1-year return by sector")
ax.set_xlabel("return (%)")
ax.grid(axis="y", visible=False)
fig.tight_layout()
fig.savefig(ASSETS / "chart_sector_1y.png", dpi=160)
plt.close(fig)

# ---------------------------------------------------------------- 3. macro
fx = con.execute("""SELECT trading_date, usd_pkr, sbp_policy_rate_pct
                    FROM fct_market_summary ORDER BY trading_date""").fetchdf()
fig, axes = plt.subplots(2, 1, figsize=(12, 6.4), sharex=True)
axes[0].plot(fx["trading_date"], fx["usd_pkr"], color="#8e44ad", lw=1.6)
axes[0].set_title("USD/PKR")
axes[1].step(fx["trading_date"], fx["sbp_policy_rate_pct"], where="post",
             color="#e67e22", lw=1.8)
axes[1].set_title("SBP policy rate (%)")
axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
fig.tight_layout()
fig.savefig(ASSETS / "chart_macro.png", dpi=160)
plt.close(fig)

print("Wrote:")
for p in sorted(ASSETS.glob("chart_*.png")):
    print("  ", p.relative_to(ROOT))
