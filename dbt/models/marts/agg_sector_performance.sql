-- mart: agg_sector_performance
-- Grain: one row per sector.
--
-- Trailing total returns (7 / 30 / 90 / 365 calendar days) and average
-- realised volatility, using arg_max(close, trading_date) filtered at each
-- lookback boundary — a clean way to get "price N days ago" without self-joins.

with fct as (
    select * from {{ ref('fct_daily_prices') }}
),

dim as (
    select symbol, sector
    from {{ ref('dim_stocks') }}
    where is_current
),

bounds as (
    select
        max(trading_date)                                   as max_date,
        cast(max(trading_date) as date) - interval 7 day    as d7,
        cast(max(trading_date) as date) - interval 30 day   as d30,
        cast(max(trading_date) as date) - interval 90 day   as d90,
        cast(max(trading_date) as date) - interval 365 day  as d365
    from fct
),

symbol_returns as (
    select
        f.symbol,
        round(arg_max(f.close, f.trading_date)
            / nullif(arg_max(f.close, f.trading_date)
                filter (f.trading_date <= (select d7 from bounds)), 0) - 1, 4)  as ret_7d,
        round(arg_max(f.close, f.trading_date)
            / nullif(arg_max(f.close, f.trading_date)
                filter (f.trading_date <= (select d30 from bounds)), 0) - 1, 4) as ret_30d,
        round(arg_max(f.close, f.trading_date)
            / nullif(arg_max(f.close, f.trading_date)
                filter (f.trading_date <= (select d90 from bounds)), 0) - 1, 4) as ret_90d,
        round(arg_max(f.close, f.trading_date)
            / nullif(arg_max(f.close, f.trading_date)
                filter (f.trading_date <= (select d365 from bounds)), 0) - 1, 4) as ret_1y,
        round(avg(f.volatility_30d_ann)
            filter (f.trading_date > (select d90 from bounds)), 4)             as avg_volatility_90d
    from fct f
    group by f.symbol
)

select
    d.sector,
    count(*)                                as n_stocks,
    round(avg(s.ret_7d), 4)                 as avg_return_7d,
    round(avg(s.ret_30d), 4)                as avg_return_30d,
    round(avg(s.ret_90d), 4)                as avg_return_90d,
    round(avg(s.ret_1y), 4)                 as avg_return_1y,
    round(avg(s.avg_volatility_90d), 4)     as avg_volatility_90d_ann
from symbol_returns s
join dim d using (symbol)
group by d.sector
order by avg_return_1y desc nulls last
