-- customer_features.sql
-- Mart model: final customer feature table consumed by ML models.
-- One row per customer with all features needed for offer recommendation.

with base as (

    select * from {{ ref('int_customer_transactions') }}

),

-- Product holdings (from a separate source)
product_holdings as (

    select
        customer_id,
        bool_or(product_type = 'mortgage')          as has_mortgage,
        bool_or(product_type = 'credit_card')       as has_credit_card,
        bool_or(product_type = 'savings')           as has_savings_account,
        bool_or(product_type = 'investment')        as has_investment_account,
        bool_or(product_type = 'personal_loan')     as has_personal_loan,
        count(distinct product_type)                as num_products_held,
        max(purchase_date)                          as last_product_purchase_date
    from {{ source('bank', 'customer_products') }}
    group by customer_id

),

-- Last offer interaction
offer_history as (

    select
        customer_id,
        max(sent_at)    as last_offer_sent_at,
        count(*)        as total_offers_sent,
        count(case when clicked then 1 end) as offers_clicked
    from {{ source('bank', 'offer_log') }}
    group by customer_id

),

-- Risk indicators (simplified)
risk_signals as (

    select
        customer_id,
        count(case when status = 'declined' then 1 end)    as declined_txn_count_90d,
        count(case when amount > 5000 then 1 end)          as high_value_txn_count_90d,
        bool_or(is_international)                           as has_international_txn
    from {{ source('bank', 'raw_transactions') }}
    where timestamp >= current_date - interval '90 days'
    group by customer_id

)

select
    -- Identity
    b.customer_id,

    -- Demographics
    b.life_stage,
    b.age_bucket,
    b.income_bucket,
    b.credit_score_bucket,
    b.tenure_months,
    b.region,

    -- Spending
    round(b.total_spend_30d / nullif(
        extract(month from age(current_date, current_date - interval '30 days')),
        0
    ), 2) as avg_monthly_spend,
    b.total_spend_30d,
    b.total_spend_90d,
    b.avg_txn_amount_7d,
    b.avg_txn_amount_30d,
    b.avg_txn_amount_90d,
    b.max_single_txn_30d,
    b.std_txn_amount_30d,

    -- Volume and frequency
    b.txn_count_7d,
    b.txn_count_30d,
    b.txn_count_90d,
    b.avg_txns_per_active_day,

    -- Categories
    b.top_category_codes                                    as top_categories,

    -- Channel usage
    b.mobile_txn_count,
    b.web_txn_count,
    b.branch_txn_count,
    b.atm_txn_count,

    -- Product holdings
    coalesce(p.num_products_held, 0)                        as num_products_held,
    coalesce(p.has_mortgage, false)                          as has_mortgage,
    coalesce(p.has_credit_card, false)                       as has_credit_card,
    coalesce(p.has_savings_account, false)                   as has_savings_account,
    coalesce(p.has_investment_account, false)                as has_investment_account,
    coalesce(p.has_personal_loan, false)                     as has_personal_loan,
    p.last_product_purchase_date                             as last_product_purchase,

    -- Risk indicators
    coalesce(r.declined_txn_count_90d, 0)                   as declined_txn_count_90d,
    coalesce(r.high_value_txn_count_90d, 0)                 as high_value_txn_count_90d,
    coalesce(r.has_international_txn, false)                 as has_international_txn,

    -- Composite risk score (0-100, higher = riskier)
    least(100, greatest(0,
        coalesce(r.declined_txn_count_90d, 0) * 15
        + coalesce(r.high_value_txn_count_90d, 0) * 5
        + case when b.credit_score_bucket in ('poor', 'very_poor') then 30 else 0 end
        + case when r.has_international_txn then 10 else 0 end
    ))                                                       as risk_indicators,

    -- Offer engagement
    coalesce(o.total_offers_sent, 0)                         as total_offers_sent,
    coalesce(o.offers_clicked, 0)                            as offers_clicked,
    case
        when coalesce(o.total_offers_sent, 0) > 0
        then round(o.offers_clicked::numeric / o.total_offers_sent, 4)
        else 0
    end                                                      as offer_ctr,

    -- Recency
    current_date - coalesce(o.last_offer_sent_at::date, b.first_txn_at::date)
                                                             as days_since_last_offer,
    current_date - b.last_txn_at::date                       as days_since_last_txn,

    -- Metadata
    current_timestamp                                        as feature_computed_at

from base b
left join product_holdings p  on b.customer_id = p.customer_id
left join offer_history o     on b.customer_id = o.customer_id
left join risk_signals r      on b.customer_id = r.customer_id
