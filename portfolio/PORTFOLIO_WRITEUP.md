# Portfolio website copy — PSX Analytics Data Warehouse

Use this text on your portfolio page. Adjust the links at the bottom.

---

## Project title
**PSX Analytics — an end-to-end data warehouse for the Pakistan Stock Exchange**

**Author:** Umer Iqbal — Data Analyst & Analytics Engineer ·
[github.com/Bilalkhank10](https://github.com/Bilalkhank10)

### One-liner
Live market data → modeled analytics warehouse → tested, monitored, and served
through an interactive dashboard — built solo with dbt, DuckDB, Python and
Streamlit.

### Short description (hero card)
Built a production-grade analytics pipeline for Pakistan's stock market: a
fault-tolerant Python extractor pulls 24,600+ daily price records for 20 PSX
large-caps plus USD/PKR and the SBP policy rate; a dbt layer models them into
facts and dimensions (including a Type-2 slowly-changing dimension); 41
automated data tests and freshness monitors guard quality; a five-tab Streamlit
dashboard serves the insights. CI refreshes everything daily via GitHub Actions.

### Why it's interesting (recruiter-facing bullets)
- **Real data, real problems:** survived Yahoo Finance throttling, a stale
  upstream benchmark feed, and 14 corporate-action anomalies — each handled
  with an explicit engineering decision, not a workaround.
- **Finance-grade modeling:** ASOF joins for currency conversion, window
  functions for returns/volatility/drawdowns, breadth analytics, and a
  reconstruction of the market index.
- **Quality as a feature:** uniqueness/null/relationship tests, a custom
  business-rule test, source freshness SLAs, and flagged-not-deleted outliers.
- **Operational maturity:** scheduled CI with hermetic offline test mode,
  build artifacts, documented runbook and roadmap.

### Tech stack
Python · SQL · dbt Core · DuckDB · Streamlit · Plotly · yfinance ·
GitHub Actions · Parquet

### Skills tags
#dbt #DataModeling #SCD2 #DataQuality #ELT #DuckDB #Python #Streamlit
#AnalyticsEngineering #CI/CD #DataPipelines

### Metrics strip
20 tickers · 9 sectors · ~24,600 price rows · 8 dbt models · 41 tests ·
5 dashboard tabs · 100% local & free to run

### Links
- 🔗 Repository: https://github.com/Bilalkhank10/psx-data-warehouse
- 📊 Live dashboard: `https://<your-app>.streamlit.app` *(deploy in ~5 min — see below; this is the last remaining placeholder)*
- 🗺 Architecture diagram: `assets/architecture.svg`
- 🖼 Screenshots: `assets/chart_market_overview.png` · `assets/chart_sector_1y.png` · `assets/chart_macro.png`
- 🧩 Website card: `portfolio/project-card.html` *(self-contained, paste into your site)*

---

## Deploying the live dashboard link (Streamlit Community Cloud)
1. Push this repo to GitHub.
2. On share.streamlit.io → New app → pick the repo, entry point
   `dashboard/app.py`.
3. Add a step to CI that commits the refreshed `warehouse.duckdb` (or run
   ingestion on app boot) so the hosted app has data.
4. Paste the public URL above.
