-- =============================================================================
-- Model: rpt_executive_dashboard_monthly
-- Description: Aggregated monthly report for the executive dashboard
-- Grain: One row per year_month
-- Layer: Report (aggregations ONLY)
-- =============================================================================
-- RULES:
--   - Aggregations ONLY — this is where you roll up data
--   - Apply Model Contracts (contract: true in YAML) for schema stability
--   - Document connected dashboards in exposures.yml
-- =============================================================================

{{ config(
    materialized='table',
    -- # ACTIVATE: distribution/clustering — dist='even'  (Redshift only; omit for Snowflake/Postgres)
    tags=['daily', 'report'],
) }}

with source_obt as (
    select * from {{ ref('{analytic_source_model}') }}
),

-- Aggregation logic
aggregated as (
    select
        -- Group by dimensions
        year_month,
        -- account_type,

        -- Aggregate metrics
        count(*) as total_records,
        -- sum(page_count) as total_pages,
        -- count(distinct account_id) as unique_account_count,

        -- Min/Max for ranges
        min(date_day) as period_start,
        max(date_day) as period_end,

    from source_obt
    group by 1
        -- , 2
),

final as (
    select * from aggregated
)

select * from final
