-- int_customer_transactions.sql
-- Intermediate model: join customers with aggregated transaction metrics.

with customers as (

    select * from {{ ref('stg_customers') }}

),

transactions as (

    select * from {{ ref('stg_transactions') }}

),

-- Rolling transaction aggregates per customer
txn_agg as (

    select
        customer_id,

        -- Volume
        count(*)                                            as total_txn_count,
        count(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_short") }} days' then 1 end)
            as txn_count_7d,
        count(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_medium") }} days' then 1 end)
            as txn_count_30d,
        count(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_long") }} days' then 1 end)
            as txn_count_90d,

        -- Spend
        avg(amount)                                         as avg_txn_amount_all,
        avg(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_short") }} days' then amount end)
            as avg_txn_amount_7d,
        avg(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_medium") }} days' then amount end)
            as avg_txn_amount_30d,
        avg(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_long") }} days' then amount end)
            as avg_txn_amount_90d,
        sum(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_medium") }} days' then amount else 0 end)
            as total_spend_30d,
        sum(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_long") }} days' then amount else 0 end)
            as total_spend_90d,
        max(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_medium") }} days' then amount end)
            as max_single_txn_30d,
        stddev(case when transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_medium") }} days' then amount end)
            as std_txn_amount_30d,

        -- Frequency
        count(distinct date(transaction_timestamp))         as distinct_txn_days,
        min(transaction_timestamp)                          as first_txn_at,
        max(transaction_timestamp)                          as last_txn_at

    from transactions
    group by customer_id

),

-- Top spending categories per customer (last 90 days)
category_ranked as (

    select
        customer_id,
        merchant_category_code,
        sum(amount)  as category_spend,
        row_number() over (
            partition by customer_id
            order by sum(amount) desc
        ) as category_rank
    from transactions
    where transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_long") }} days'
    group by customer_id, merchant_category_code

),

top_categories as (

    select
        customer_id,
        string_agg(merchant_category_code, ',' order by category_rank)
            as top_category_codes
    from category_ranked
    where category_rank <= 5
    group by customer_id

),

-- Channel mix
channel_mix as (

    select
        customer_id,
        count(case when channel = 'mobile' then 1 end)  as mobile_txn_count,
        count(case when channel = 'web' then 1 end)     as web_txn_count,
        count(case when channel = 'branch' then 1 end)  as branch_txn_count,
        count(case when channel = 'atm' then 1 end)     as atm_txn_count
    from transactions
    where transaction_timestamp >= current_date - interval '{{ var("txn_lookback_days_medium") }} days'
    group by customer_id

)

select
    c.customer_id,
    c.first_name,
    c.last_name,
    c.age_bucket,
    c.income_bucket,
    c.life_stage,
    c.credit_score_bucket,
    c.tenure_months,
    c.region,

    -- Transaction aggregates
    coalesce(t.total_txn_count, 0)      as total_txn_count,
    coalesce(t.txn_count_7d, 0)         as txn_count_7d,
    coalesce(t.txn_count_30d, 0)        as txn_count_30d,
    coalesce(t.txn_count_90d, 0)        as txn_count_90d,
    coalesce(t.avg_txn_amount_7d, 0)    as avg_txn_amount_7d,
    coalesce(t.avg_txn_amount_30d, 0)   as avg_txn_amount_30d,
    coalesce(t.avg_txn_amount_90d, 0)   as avg_txn_amount_90d,
    coalesce(t.total_spend_30d, 0)      as total_spend_30d,
    coalesce(t.total_spend_90d, 0)      as total_spend_90d,
    coalesce(t.max_single_txn_30d, 0)   as max_single_txn_30d,
    coalesce(t.std_txn_amount_30d, 0)   as std_txn_amount_30d,
    t.first_txn_at,
    t.last_txn_at,

    -- Derived frequency
    case
        when t.distinct_txn_days > 1
        then t.total_txn_count::float / t.distinct_txn_days
        else 0
    end as avg_txns_per_active_day,

    -- Categories
    tc.top_category_codes,

    -- Channel mix
    coalesce(ch.mobile_txn_count, 0)    as mobile_txn_count,
    coalesce(ch.web_txn_count, 0)       as web_txn_count,
    coalesce(ch.branch_txn_count, 0)    as branch_txn_count,
    coalesce(ch.atm_txn_count, 0)       as atm_txn_count

from customers c
left join txn_agg t       on c.customer_id = t.customer_id
left join top_categories tc on c.customer_id = tc.customer_id
left join channel_mix ch  on c.customer_id = ch.customer_id
