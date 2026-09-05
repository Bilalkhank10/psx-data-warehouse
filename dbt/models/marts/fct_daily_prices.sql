-- mart: fct_daily_prices
-- Grain: one row per (symbol, trading_date) — the analytical spine of the project.
--
-- Enrichments:
--   * PKR prices translated to USD via an ASOF join (each trading date takes the
--     most recent FX print at or before it — weekends/holidays handled correctly)
--   * daily simple return, 7/30-day moving averages
--   * 30-day realised volatility, annualised (x sqrt(252))
--   * rolling 52-week high + % drawdown from it

with prices as (
    select * from {{ ref('stg_psx_prices') }}
),

fx as (
    select rate_date, usd_pkr from {{ ref('stg_fx_rates') }}
),

fx_enriched as (
    select
        p.*,
        f.usd_pkr,
        round(p.close / nullif(f.usd_pkr, 0), 4) as close_usd
    from prices p
    asof left join fx f
        on p.trading_date >= f.rate_date
),

returns as (
    select
        fx_enriched.*,
        close / nullif(lag(close) over w, 0) - 1 as daily_return
    from fx_enriched
    window w as (partition by symbol order by trading_date)
)

select
    price_id,
    symbol,
    trading_date,
    open, high, low, close, adj_close, volume,
    usd_pkr,
    close_usd,
    round(daily_return, 6)                                            as daily_return,
    round(avg(close) over (
        partition by symbol order by trading_date
        rows between 6 preceding and current row), 4)                 as ma_7,
    round(avg(close) over (
        partition by symbol order by trading_date
        rows between 29 preceding and current row), 4)                as ma_30,
    round(stddev_samp(daily_return) over (
        partition by symbol order by trading_date
        rows between 29 preceding and current row) * power(252, 0.5), 4) as volatility_30d_ann,
    round(max(close) over (
        partition by symbol order by trading_date
        rows between 251 preceding and current row), 4)               as high_52w,
    round(close / nullif(max(close) over (
        partition by symbol order by trading_date
        rows between 251 preceding and current row), 0) - 1, 4)       as drawdown_from_52w_high,
    -- Feed-quality flag: Yahoo's corporate-action adjustment can flap around
    -- split/bonus dates, printing impossible single-day moves. Flagged here,
    -- monitored by assert_daily_returns_within_band, excluded from aggregates.
    case
        when daily_return is not null and abs(daily_return) > 0.35
        then true else false
    end                                                               as is_return_outlier,
    is_synthetic,
    loaded_at
from returns
