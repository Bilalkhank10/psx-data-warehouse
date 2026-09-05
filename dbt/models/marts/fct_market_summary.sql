-- mart: fct_market_summary
-- Grain: one row per trading_date (market level).
--
-- Daily breadth (advancers/decliners), total volume, average constituent
-- return, an equal-weight reconstruction of the universe index (base = 100),
-- plus macro context: USD/PKR (ASOF) and SBP policy rate (ASOF).

with prices as (
    select symbol, trading_date, close, volume, daily_return, is_return_outlier
    from {{ ref('fct_daily_prices') }}
),

breadth as (
    select
        trading_date,
        count(*)                                          as stocks_traded,
        countif(is_return_outlier)                        as outlier_count,
        -- breadth & averages exclude flagged feed anomalies so a single
        -- broken print can't smear the market-level numbers
        countif(daily_return > 0 and not is_return_outlier)  as advancers,
        countif(daily_return < 0 and not is_return_outlier)  as decliners,
        countif(daily_return = 0 and not is_return_outlier)  as unchanged,
        sum(volume)                                       as total_volume,
        avg(daily_return) filter (where not is_return_outlier) as avg_daily_return
    from prices
    group by trading_date
),

universe_index as (
    select
        breadth.*,
        round(100 * exp(sum(
            case
                -- first session (or any empty basket) contributes zero growth;
                -- guard NULL/NaN so a single gap can't poison the cumsum
                when avg_daily_return is null or isnan(avg_daily_return) then 0
                else ln(greatest(1 + avg_daily_return, 1e-9))
            end
        ) over (order by trading_date
                rows between unbounded preceding and current row)), 4)
            as equal_weight_index
    from breadth
),

fx as (select rate_date, usd_pkr from {{ ref('stg_fx_rates') }}),
policy as (select effective_date, policy_rate_pct from {{ ref('stg_policy_rates') }}),
benchmark as (select trading_date, kse100_close from {{ ref('stg_market_index') }})

select
    md5('mkt|' || cast(u.trading_date as varchar))        as market_day_id,
    u.trading_date,
    u.stocks_traded,
    u.outlier_count,
    u.advancers,
    u.decliners,
    u.unchanged,
    u.total_volume,
    round(u.avg_daily_return, 6)                          as avg_daily_return,
    u.equal_weight_index,
    b.kse100_close,       -- NULL when the official feed is stale; dashboard falls back
    round(f.usd_pkr, 2)                                    as usd_pkr,
    pl.policy_rate_pct                                     as sbp_policy_rate_pct
from universe_index u
asof left join fx f     on u.trading_date >= f.rate_date
left join benchmark b   on u.trading_date = b.trading_date
asof left join policy pl on u.trading_date >= pl.effective_date
