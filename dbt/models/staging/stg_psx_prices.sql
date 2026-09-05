-- Staging: clean + type the raw PSX price feed.
-- Grain: one row per (symbol, trading_date).
with source as (
    select * from {{ source('raw', 'raw_psx_prices') }}
),

renamed as (
    select
        symbol,
        cast(trading_date as date)                          as trading_date,
        cast(open        as double)                          as open,
        cast(high        as double)                          as high,
        cast(low         as double)                          as low,
        cast(close       as double)                          as close,
        cast(coalesce(adj_close, close) as double)           as adj_close,
        cast(volume      as bigint)                          as volume,
        cast(is_synthetic as boolean)                        as is_synthetic,
        loaded_at,
        -- deterministic surrogate key for uniqueness tests & joins
        md5(symbol || '|' || cast(trading_date as varchar))  as price_id
    from source
)

select * from renamed
