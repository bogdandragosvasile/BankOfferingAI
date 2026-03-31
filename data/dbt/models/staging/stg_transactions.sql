-- stg_transactions.sql
-- Staging model: clean and type-cast raw transactions.
-- Filters out non-completed transactions and deduplicates by transaction_id.

with source as (

    select * from {{ source('bank', 'raw_transactions') }}

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by transaction_id
            order by _loaded_at desc
        ) as _row_num
    from source

),

cleaned as (

    select
        cast(transaction_id as varchar(64))              as transaction_id,
        cast(customer_id as varchar(64))                 as customer_id,
        cast(amount as numeric(18, 2))                   as amount,
        upper(trim(currency))                            as currency,
        trim(merchant_name)                              as merchant_name,
        cast(merchant_category_code as varchar(10))      as merchant_category_code,
        lower(trim(transaction_type))                    as transaction_type,
        cast(timestamp as timestamp)                     as transaction_timestamp,
        lower(trim(channel))                             as channel,
        lower(trim(status))                              as status,
        cast(_loaded_at as timestamp)                    as loaded_at

    from deduplicated
    where _row_num = 1
      and lower(trim(status)) = 'completed'
      and amount > 0
      and transaction_id is not null
      and customer_id is not null

)

select * from cleaned
