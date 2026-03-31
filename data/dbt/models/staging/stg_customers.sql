-- stg_customers.sql
-- Staging model: clean and standardise raw customer data.

with source as (

    select * from {{ source('bank', 'raw_customers') }}

),

deduplicated as (

    select
        *,
        row_number() over (
            partition by customer_id
            order by updated_at desc
        ) as _row_num
    from source

),

cleaned as (

    select
        cast(customer_id as varchar(64))                as customer_id,
        trim(first_name)                                as first_name,
        trim(last_name)                                 as last_name,
        cast(date_of_birth as date)                     as date_of_birth,
        lower(trim(gender))                             as gender,
        trim(region)                                    as region,
        cast(annual_income as numeric(18, 2))           as annual_income,
        lower(trim(employment_status))                  as employment_status,
        lower(trim(marital_status))                     as marital_status,
        cast(credit_score as integer)                   as credit_score,
        cast(onboarding_date as date)                   as onboarding_date,
        cast(updated_at as timestamp)                   as updated_at,

        -- Derived: tenure in months
        extract(year from age(current_date, onboarding_date)) * 12
            + extract(month from age(current_date, onboarding_date))
            as tenure_months,

        -- Derived: age bucket
        case
            when extract(year from age(current_date, date_of_birth)) < 25
                then 'young_adult'
            when extract(year from age(current_date, date_of_birth)) < 35
                then 'adult'
            when extract(year from age(current_date, date_of_birth)) < 50
                then 'middle_aged'
            when extract(year from age(current_date, date_of_birth)) < 65
                then 'senior'
            else 'retiree'
        end as age_bucket,

        -- Derived: income bucket
        case
            when annual_income < 30000  then 'low'
            when annual_income < 60000  then 'lower_middle'
            when annual_income < 100000 then 'upper_middle'
            when annual_income < 200000 then 'high'
            else 'affluent'
        end as income_bucket,

        -- Derived: life stage (simplified heuristic)
        case
            when extract(year from age(current_date, date_of_birth)) < 25
                then 'starting_out'
            when extract(year from age(current_date, date_of_birth)) < 35
                 and lower(trim(marital_status)) = 'single'
                then 'young_professional'
            when extract(year from age(current_date, date_of_birth)) < 35
                then 'young_family'
            when extract(year from age(current_date, date_of_birth)) < 50
                then 'established'
            when extract(year from age(current_date, date_of_birth)) < 65
                then 'pre_retirement'
            else 'retired'
        end as life_stage,

        -- Derived: credit score bucket
        case
            when credit_score >= 750 then 'excellent'
            when credit_score >= 700 then 'good'
            when credit_score >= 650 then 'fair'
            when credit_score >= 600 then 'poor'
            else 'very_poor'
        end as credit_score_bucket

    from deduplicated
    where _row_num = 1
      and customer_id is not null

)

select * from cleaned
