-- customer_features.sql
-- Mart model: final customer feature table consumed by ML models.
-- One row per customer with all features needed for offer recommendation.
-- Includes profiler-required fields: monthly_savings, avg_expenses, idle_cash,
-- balance_trend, debt_to_income, savings_rate, dominant_spend_category,
-- investment_gap_flag.

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

),

-- Financial balance snapshot (savings vs. expenses)
financial_snapshot as (

    select
        customer_id,
        -- Monthly savings: inflow credited to savings accounts last 30 days
        sum(case
            when transaction_type = 'credit'
             and merchant_category_code = 'savings_transfer'
             and transaction_timestamp >= current_date - interval '30 days'
            then amount else 0
        end)                                                as monthly_savings,

        -- Average monthly expenses: debits over the last 90 days averaged
        round(
            sum(case
                when transaction_type = 'debit'
                 and transaction_timestamp >= current_date - interval '90 days'
                then amount else 0
            end) / 3.0
        , 2)                                                as avg_expenses,

        -- Idle cash heuristic: large credits with no corresponding investment
        -- or savings activity in the same month (proxy for uninvested cash)
        greatest(0, sum(case
            when transaction_type = 'credit'
             and transaction_timestamp >= current_date - interval '30 days'
            then amount else 0
        end) - sum(case
            when transaction_type = 'debit'
             and merchant_category_code not in ('housing', 'groceries', 'utilities')
             and transaction_timestamp >= current_date - interval '30 days'
            then amount else 0
        end))                                               as idle_cash,

        -- Balance trend: difference between avg spend 30d vs 90d (positive = spending up)
        round(
            avg(case
                when transaction_timestamp >= current_date - interval '30 days'
                 and transaction_type = 'debit'
                then amount end)
            -
            avg(case
                when transaction_timestamp >= current_date - interval '90 days'
                 and transaction_type = 'debit'
                then amount end)
        , 2)                                                as balance_trend,

        -- Dominant spend category by total amount in last 30 days
        first_value(merchant_category_code) over (
            partition by customer_id
            order by sum(case
                when transaction_timestamp >= current_date - interval '30 days'
                 and transaction_type = 'debit'
                then amount else 0
            end) desc
        )                                                   as dominant_spend_category

    from {{ ref('stg_transactions') }}
    group by customer_id, merchant_category_code

),

-- Deduplicate financial_snapshot to one row per customer
financial_deduped as (

    select distinct on (customer_id)
        customer_id,
        monthly_savings,
        avg_expenses,
        idle_cash,
        balance_trend,
        dominant_spend_category
    from financial_snapshot
    order by customer_id, monthly_savings desc

),

-- Debt and income signals from customer profile
debt_income_signals as (

    select
        c.customer_id,
        c.annual_income,
        -- Approximate total debt from loan/credit product balances
        -- (In production, join to a balance table; here we use a heuristic.)
        coalesce(
            sum(case when cp.product_type in ('mortgage', 'personal_loan', 'credit_card')
                then cp.outstanding_balance else 0 end),
            0
        )                                                   as total_debt
    from {{ source('bank', 'raw_customers') }} c
    left join {{ source('bank', 'customer_products') }} cp
        on c.customer_id = cp.customer_id
    group by c.customer_id, c.annual_income

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
    ), 2)                                                   as avg_monthly_spend,
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

    -- -----------------------------------------------------------------------
    -- Profiler-required financial features
    -- -----------------------------------------------------------------------

    -- Monthly savings: net amount moved into savings accounts last 30 days
    coalesce(f.monthly_savings, 0)                           as monthly_savings,

    -- Average monthly expenses over last 90 days
    coalesce(f.avg_expenses, 0)                              as avg_expenses,

    -- Idle cash: uninvested liquid balance proxy
    coalesce(f.idle_cash, 0)                                 as idle_cash,

    -- Balance trend: positive = spending accelerating, negative = decelerating
    coalesce(f.balance_trend, 0)                             as balance_trend,

    -- Debt-to-income ratio (annual debt burden / annual income)
    case
        when coalesce(di.annual_income, 0) > 0
        then round(coalesce(di.total_debt, 0)::numeric / di.annual_income, 4)
        else null
    end                                                      as debt_to_income,

    -- Savings rate: monthly_savings / (monthly_income proxy)
    case
        when coalesce(di.annual_income, 0) > 0
        then round(
            coalesce(f.monthly_savings, 0)::numeric
            / (di.annual_income / 12.0),
        4)
        else null
    end                                                      as savings_rate,

    -- Dominant spend category last 30 days
    coalesce(f.dominant_spend_category, 'unknown')           as dominant_spend_category,

    -- Investment gap flag: customer has income suggesting investment capacity
    -- but no investment product and meaningful idle cash
    case
        when coalesce(p.has_investment_account, false) = false
         and coalesce(di.annual_income, 0) >= 50000
         and coalesce(f.idle_cash, 0) >= 1000
        then true
        else false
    end                                                      as investment_gap_flag,

    -- Metadata
    current_timestamp                                        as feature_computed_at

from base b
left join product_holdings p   on b.customer_id = p.customer_id
left join offer_history o      on b.customer_id = o.customer_id
left join risk_signals r       on b.customer_id = r.customer_id
left join financial_deduped f  on b.customer_id = f.customer_id
left join debt_income_signals di on b.customer_id = di.customer_id
