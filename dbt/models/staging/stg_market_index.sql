-- Staging: official KSE-100 closes (may be sparse/stale — see sources.yml note).
-- Grain: one row per trading_date.
select
    cast(trading_date as date)        as trading_date,
    cast(kse100_close as double)      as kse100_close,
    cast(volume as bigint)            as volume,
    cast(is_synthetic as boolean)     as is_synthetic
from {{ source('raw', 'raw_market_index') }}
