-- Staging: State Bank of Pakistan policy rate change events (seeded).
-- Grain: one row per rate-change effective date.
select
    cast(effective_date as date)          as effective_date,
    cast(policy_rate_pct as double)       as policy_rate_pct,
    note
from {{ ref('sbp_policy_rates') }}
