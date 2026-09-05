-- Staging: USD/PKR daily closes.
-- Grain: one row per rate_date.
select
    cast(rate_date as date)           as rate_date,
    cast(usd_pkr as double)           as usd_pkr,
    cast(is_synthetic as boolean)     as is_synthetic,
    loaded_at
from {{ source('raw', 'raw_fx_rates') }}
