-- mart: dim_stocks  (SCD Type 2)
-- Full version history of company metadata, sourced from the dbt snapshot over
-- the `stocks` seed. Edit the seed (e.g. a company rebrands or changes sector)
-- and `dbt snapshot` will close the old validity window and open a new row.

select
    symbol,
    company_name,
    sector,
    industry,
    listed_year,
    updated_at,
    dbt_valid_from,
    dbt_valid_to,
    dbt_scd_id,
    case when dbt_valid_to is null then true else false end as is_current
from {{ ref('stocks_snapshot') }}
