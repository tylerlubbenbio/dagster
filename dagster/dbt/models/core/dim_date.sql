-- =============================================================================
-- Model: dim_date
-- Description: Calendar dimension table — the ONLY place dates live
-- Grain: One row per calendar day
-- Layer: Core
-- =============================================================================
-- RULES:
--   - NEVER put date columns directly in fact tables
--   - ALL date-based analysis joins through this table
--   - Supports: business week, monthly, fiscal year, quarter, etc.
--   - Extend with custom fiscal calendars as needed
-- =============================================================================

{{ config(
    materialized='table',
    tags=['daily', 'core']
) }}

with import_dates as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('" ~ var('default_start_date') ~ "' as date)",
        end_date="current_date + interval '365 days'"
    ) }}
),

final as (
    select
        -- Surrogate Key
        {{ dbt_utils.generate_surrogate_key(['date_day']) }} as date_sk,

        -- Core Date
        cast(date_day as date) as date_day,

        -- Year
        extract(year from date_day) as year_number,
        cast(extract(year from date_day) as text) as year_text,

        -- Quarter
        extract(quarter from date_day) as quarter_number,
        cast(extract(year from date_day) as text) || '-Q' || cast(extract(quarter from date_day) as text) as year_quarter,

        -- Month
        extract(month from date_day) as month_number,
        to_char(date_day, 'Month') as month_name,
        to_char(date_day, 'Mon') as month_short,
        cast(extract(year from date_day) as text) || '-' || lpad(cast(extract(month from date_day) as text), 2, '0') as year_month,

        -- Week
        extract(week from date_day) as week_number,
        extract(dow from date_day) as day_of_week_number,
        to_char(date_day, 'Day') as day_of_week_name,
        to_char(date_day, 'Dy') as day_of_week_short,

        -- Day
        extract(day from date_day) as day_of_month,
        extract(doy from date_day) as day_of_year,

        -- Booleans
        case
            when extract(dow from date_day) in (0, 6) then true
            else false
        end as is_weekend,

        case
            when extract(dow from date_day) between 1 and 5 then true
            else false
        end as is_weekday,

        -- Relative Flags (useful for dashboards)
        case when cast(date_day as date) = current_date then true else false end as is_today,
        case when cast(date_day as date) = current_date - 1 then true else false end as is_yesterday,

        -- Period Start/End
        -- ACTIVATE: ::date cast syntax works in Redshift/Postgres. For Snowflake use cast(... as date).
        date_trunc('week', date_day)::date as week_start_date,
        (date_trunc('week', date_day) + interval '6 days')::date as week_end_date,
        date_trunc('month', date_day)::date as month_start_date,
        (date_trunc('month', date_day) + interval '1 month' - interval '1 day')::date as month_end_date,
        date_trunc('quarter', date_day)::date as quarter_start_date,
        (date_trunc('quarter', date_day) + interval '3 months' - interval '1 day')::date as quarter_end_date,
        date_trunc('year', date_day)::date as year_start_date,
        (date_trunc('year', date_day) + interval '1 year' - interval '1 day')::date as year_end_date

        -- =====================================================================
        -- FISCAL CALENDAR (Uncomment and customize for your fiscal year)
        -- =====================================================================
        -- Example: Fiscal year starts February 1
        -- , case
        --     when extract(month from date_day) >= 2
        --     then extract(year from date_day)
        --     else extract(year from date_day) - 1
        --   end as fiscal_year
        --
        -- , case
        --     when extract(month from date_day) >= 2
        --     then extract(month from date_day) - 1
        --     else extract(month from date_day) + 11
        --   end as fiscal_month_number

    from import_dates
)

select * from final
