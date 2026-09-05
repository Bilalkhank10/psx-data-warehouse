"""
PSX Analytics Dashboard
-----------------------
Streamlit front-end over the dbt-modeled DuckDB warehouse.

Run:
    streamlit run dashboard/app.py
"""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

WAREHOUSE = Path(__file__).resolve().parent.parent / "warehouse.duckdb"
GREEN, RED, MUTED = "#0e7c3a", "#c0392b", "#8f97a3"
TEMPLATE = "plotly_white"

st.set_page_config(page_title="PSX Analytics", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")


# ---------------------------------------------------------------- data layer
@st.cache_resource
def get_con():
    return duckdb.connect(str(WAREHOUSE), read_only=True)


@st.cache_data(ttl=3600)
def q(sql: str) -> pd.DataFrame:
    return get_con().execute(sql).fetchdf()


def is_synthetic() -> bool:
    return bool(q("SELECT bool_or(is_synthetic) AS s FROM raw_psx_prices")["s"].iloc[0])


# ------------------------------------------------------------------- header
st.title("📈 PSX Analytics")
st.caption(
    "Pakistan Stock Exchange data warehouse · yfinance ➜ DuckDB ➜ dbt ➜ "
    "Streamlit · 20 large-caps across 9 sectors · USD/PKR + SBP policy-rate context"
)
if is_synthetic():
    st.warning("⚠️ Serving **synthetic demo data** — the live extractor will "
               "replace this automatically on the next successful run.", icon="⚠️")

market = q("SELECT * FROM fct_market_summary ORDER BY trading_date")
fct = q("SELECT * FROM fct_daily_prices")
dim = q("SELECT symbol, company_name, sector, industry FROM dim_stocks WHERE is_current")
sectors = q("SELECT * FROM agg_sector_performance ORDER BY avg_return_1y DESC NULLS LAST")

last_day = market["trading_date"].max()
fct["trading_date"] = pd.to_datetime(fct["trading_date"])
market["trading_date"] = pd.to_datetime(market["trading_date"])

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Controls")
    symbol = st.selectbox(
        "Stock",
        dim["symbol"],
        format_func=lambda s: f"{s} — {dim.set_index('symbol').loc[s, 'company_name']}",
    )
    min_d, max_d = market["trading_date"].min(), market["trading_date"].max()
    rng = st.date_input("Window", value=(max_d - pd.Timedelta(days=365), max_d),
                        min_value=min_d, max_value=max_d)
    start_d = pd.to_datetime(rng[0]) if isinstance(rng, tuple) else max_d - pd.Timedelta(days=365)
    st.divider()
    st.caption(f"Warehouse: `{WAREHOUSE.name}` · data through **{last_day:%d %b %Y}**")
    st.caption("Built as a portfolio project — dbt models, SCD2 dimension, "
               "40+ data tests, daily CI refresh.")

# ------------------------------------------------------------------ KPI row
last = market.iloc[-1]
prev = market.iloc[-2]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Equal-weight universe index", f"{last['equal_weight_index']:,.0f}",
          f"{(last['equal_weight_index']/prev['equal_weight_index']-1)*100:+.1f}% d/d")
c2.metric("Breadth (adv/dec)", f"{int(last['advancers'])} / {int(last['decliners'])}")
c3.metric("USD/PKR", f"{last['usd_pkr']:,.1f}")
c4.metric("SBP policy rate", f"{last['sbp_policy_rate_pct']:.2f} %")

tab_mkt, tab_stock, tab_sector, tab_macro, tab_dq = st.tabs(
    ["🏠 Market", "🎯 Stock explorer", "🏭 Sectors", "💱 Macro", "🧪 Data quality"])

# ---------------------------------------------------------------- Market tab
with tab_mkt:
    win = market[market["trading_date"] >= start_d].copy()
    win["rebased"] = win["equal_weight_index"] / win["equal_weight_index"].iloc[0] * 100

    fig = go.Figure()
    fig.add_scatter(x=win["trading_date"], y=win["rebased"],
                    name="Equal-weight universe (rebased=100)",
                    line=dict(color=GREEN, width=2))
    if win["kse100_close"].notna().sum() > 5:
        kse = win.dropna(subset=["kse100_close"])
        fig.add_scatter(x=kse["trading_date"], y=kse["kse100_close"] / kse["kse100_close"].iloc[0] * 100,
                        name="KSE-100 (official)", line=dict(color=MUTED, dash="dot"))
    fig.update_layout(template=TEMPLATE, height=380, margin=dict(l=10, r=10, t=30, b=10),
                      legend=dict(orientation="h"), yaxis_title=None, xaxis_title=None)
    st.plotly_chart(fig, width="stretch")

    a, b = st.columns([3, 2])
    with a:
        recent = win.tail(90)
        fig_b = go.Figure()
        fig_b.add_bar(x=recent["trading_date"], y=recent["advancers"], name="Advancers",
                      marker_color=GREEN)
        fig_b.add_bar(x=recent["trading_date"], y=-recent["decliners"], name="Decliners",
                      marker_color=RED)
        fig_b.update_layout(template=TEMPLATE, barmode="relative", height=280,
                            title="Market breadth — last 90 sessions",
                            margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h"))
        st.plotly_chart(fig_b, width="stretch")
    with b:
        latest_fct = fct[(fct["trading_date"] == fct["trading_date"].max())
                         & (~fct["is_return_outlier"])]
        movers = pd.concat([latest_fct.nlargest(5, "daily_return"),
                            latest_fct.nsmallest(5, "daily_return")])
        movers = movers.merge(dim, on="symbol")
        movers["daily_return"] = (movers["daily_return"] * 100).round(2)
        st.subheader("Top movers — latest session")
        st.dataframe(
            movers[["symbol", "company_name", "close", "daily_return"]]
            .rename(columns={"daily_return": "return %", "company_name": "company"}),
            hide_index=True, width="stretch",
            column_config={"return %": st.column_config.NumberColumn(format="%.2f %%")})

# ------------------------------------------------------------ Stock explorer
with tab_stock:
    s = fct[(fct["symbol"] == symbol) & (fct["trading_date"] >= start_d)].copy()
    meta = dim.set_index("symbol").loc[symbol]

    k1, k2, k3, k4, k5 = st.columns(5)
    close_s = s["close"]
    k1.metric("Last close", f"PKR {close_s.iloc[-1]:,.2f}")
    k2.metric("30d return", f"{(close_s.iloc[-1]/close_s.iloc[-22]-1)*100:+.1f} %" if len(s) > 22 else "—")
    k3.metric("1y return", f"{(close_s.iloc[-1]/close_s.iloc[0]-1)*100:+.1f} %")
    k4.metric("Volatility (30d, ann.)", f"{s['volatility_30d_ann'].iloc[-1]*100:.1f} %"
              if pd.notna(s["volatility_30d_ann"].iloc[-1]) else "—")
    k5.metric("Drawdown vs 52w high", f"{s['drawdown_from_52w_high'].iloc[-1]*100:+.1f} %")
    st.caption(f"**{meta['company_name']}** · {meta['sector']} — {meta['industry']}")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28],
                        vertical_spacing=0.03)
    fig.add_candlestick(x=s["trading_date"], open=s["open"], high=s["high"],
                        low=s["low"], close=s["close"], name=symbol,
                        increasing_line_color=GREEN, decreasing_line_color=RED, row=1, col=1)
    fig.add_scatter(x=s["trading_date"], y=s["ma_7"], name="MA-7",
                    line=dict(color="#1f77b4", width=1.2), row=1, col=1)
    fig.add_scatter(x=s["trading_date"], y=s["ma_30"], name="MA-30",
                    line=dict(color="#e67e22", width=1.2), row=1, col=1)
    fig.add_bar(x=s["trading_date"], y=s["volume"], name="Volume",
                marker_color="#c7d2cc", row=2, col=1)
    fig.update_layout(template=TEMPLATE, height=520, showlegend=True,
                      legend=dict(orientation="h"), margin=dict(l=10, r=10, t=20, b=10),
                      xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, width="stretch")

# --------------------------------------------------------------- Sectors tab
with tab_sector:
    horizon = st.radio("Horizon", ["1y", "90d", "30d", "7d"], horizontal=True, index=0)
    col = f"avg_return_{horizon}"
    fig_s = px.bar(sectors.sort_values(col), x=col, y="sector", orientation="h",
                   color=col, color_continuous_scale=["#c0392b", "#f5f5f5", "#0e7c3a"],
                   labels={col: f"Average {horizon} return", "sector": ""})
    fig_s.update_layout(template=TEMPLATE, height=420, coloraxis_showscale=False,
                        margin=dict(l=10, r=10, t=20, b=10),
                        xaxis_tickformat=".1%")
    st.plotly_chart(fig_s, width="stretch")

    st.subheader("Return correlations — last 12 months")
    yr = fct[(fct["trading_date"] >= fct["trading_date"].max() - pd.Timedelta(days=365))
             & (~fct["is_return_outlier"])]
    piv = yr.pivot_table(index="trading_date", columns="symbol", values="daily_return")
    corr = piv.corr().round(2)
    fig_c = px.imshow(corr, color_continuous_scale="RdYlGn", zmin=-1, zmax=1,
                      text_auto=".2f", aspect="auto")
    fig_c.update_layout(template=TEMPLATE, height=560, margin=dict(l=10, r=10, t=20, b=10))
    st.plotly_chart(fig_c, width="stretch")

# ----------------------------------------------------------------- Macro tab
with tab_macro:
    a, b = st.columns(2)
    with a:
        fig_fx = px.line(win, x="trading_date", y="usd_pkr",
                         title="USD/PKR exchange rate")
        fig_fx.update_traces(line_color="#8e44ad")
        fig_fx.update_layout(template=TEMPLATE, height=320,
                             margin=dict(l=10, r=10, t=40, b=10), yaxis_title=None)
        st.plotly_chart(fig_fx, width="stretch")
    with b:
        fig_pr = px.line(win, x="trading_date", y="sbp_policy_rate_pct",
                         title="SBP policy rate (%)")
        fig_pr.update_traces(line_color="#e67e22", line_shape="hv")
        fig_pr.update_layout(template=TEMPLATE, height=320,
                             margin=dict(l=10, r=10, t=40, b=10), yaxis_title=None)
        st.plotly_chart(fig_pr, width="stretch")

    st.markdown(
        "**Why this matters:** PKR-denominated equity returns look very different "
        "to a USD-based investor. Every stock in this warehouse carries both a "
        "`close` (PKR) and `close_usd` column, joined ASOF against the FX table — "
        "so currency devaluation is adjustable in every analysis."
    )
    usd_toggle = st.multiselect("Compare price series (USD-adjusted)", dim["symbol"].tolist(),
                                default=[symbol])
    if usd_toggle:
        cmp_df = fct[(fct["symbol"].isin(usd_toggle)) & (fct["trading_date"] >= start_d)].copy()
        cmp_df["rebased_usd"] = cmp_df.groupby("symbol")["close_usd"].transform(lambda x: x / x.iloc[0] * 100)
        fig_u = px.line(cmp_df, x="trading_date", y="rebased_usd", color="symbol",
                        title="USD-adjusted price, rebased = 100")
        fig_u.update_layout(template=TEMPLATE, height=360, margin=dict(l=10, r=10, t=40, b=10),
                            yaxis_title=None)
        st.plotly_chart(fig_u, width="stretch")

# ---------------------------------------------------------- Data quality tab
with tab_dq:
    st.subheader("Engineering grade data-quality guardrails")
    st.markdown(
        "- **40+ dbt tests** run on every build: uniqueness, non-null keys, "
        "referential integrity (fact → dimension), and a custom business-rule test "
        "(`assert_daily_returns_within_band`).\n"
        "- **Source freshness** monitored with `dbt source freshness` (36h warn / 96h error).\n"
        "- **Feed anomalies are flagged, never deleted** — Yahoo's corporate-action "
        "adjustment glitches around split dates are carried as `is_return_outlier` "
        "and excluded from market aggregates.\n"
        "- **SCD2 dimension**: company metadata edits create versioned rows "
        "(`dbt snapshot`), preserving as-was analysis."
    )
    outliers = fct[fct["is_return_outlier"]][
        ["trading_date", "symbol", "close", "daily_return"]].sort_values("trading_date")
    outliers["daily_return %"] = (outliers["daily_return"] * 100).round(1)
    st.markdown(f"**Flagged anomalies in current data: {len(outliers)}**")
    st.dataframe(outliers.drop(columns="daily_return"), hide_index=True,
                 width="stretch")
    fresh = q("""SELECT 'prices' AS t, max(loaded_at) AS last_load FROM raw_psx_prices
                 UNION ALL SELECT 'fx', max(loaded_at) FROM raw_fx_rates""")
    st.caption("Last raw loads (UTC): " + " · ".join(
        f"{r.t}: {r.last_load:%Y-%m-%d %H:%M}" for r in fresh.itertuples()))

st.divider()
st.caption("Built by **[Umer Iqbal](https://github.com/Bilalkhank10)** — Data Analyst & "
           "Analytics Engineer · Stack: yfinance → Python extractor → DuckDB → dbt "
           "(staging/marts/tests/snapshots) → Streamlit · "
           "[Repo & docs](https://github.com/Bilalkhank10/psx-data-warehouse)")
