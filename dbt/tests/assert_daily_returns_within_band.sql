{{ config(severity = 'warn') }}

-- Singular test (WARN): PSX circuit breakers cap daily moves (±7.5% normally).
-- Anything beyond 35% in a day is a feed artifact — Yahoo's corporate-action
-- adjustment flapping around split/bonus dates (verified 2026-09: 14 rows in
-- LUCK/SYS/UBL in 2025). Such rows carry is_return_outlier = true downstream
-- and are excluded from market aggregates; this test monitors for *new*
-- anomalies appearing in future loads.
select
    trading_date,
    symbol,
    daily_return
from {{ ref('fct_daily_prices') }}
where is_return_outlier

