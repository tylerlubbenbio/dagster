-- =============================================================================
-- Model: {team}_{source}__{use_case}
-- Description: One Big Table (OBT) for {team} team — {use_case}
-- Grain: One row per {grain_entity} (NO aggregations)
-- Layer: Analytics
-- =============================================================================
-- RULES:
--   - NO aggregations — keep at natural grain
--   - Pre-join all relevant dimensions
--   - Slow-changing strategy:
--     * Rarely changing dims (categories, segments): denormalize fully, refresh daily
--     * Frequently changing dims (address, status): keep separate OR accept day-lag
-- =============================================================================

{{ config(
    materialized='table',
    -- # ACTIVATE: sort/clustering — sort=['date_day']  (Redshift: sort keys; Snowflake: cluster_by; Postgres: omit)
    -- # ACTIVATE: distribution/clustering — dist='even'  (Redshift only; omit for Snowflake/Postgres)
    tags=['daily', 'analytics'],
) }}

-- STEP 2: IMPORTS
with import_facts as (
    select * from {{ ref('fct_{{entity_plural}}') }}
),

import_date as (
    select * from {{ ref('dim_date') }}
),

import_dim_account as (
    select * from {{ ref('dim_account') }}
),

-- import_dim_user as (
--     select * from {{ ref('dim_user') }}
-- ),

-- STEP 3: LOGIC — Pre-join everything
joined as (
    select
        -- Date attributes (from dim_date)
        d.date_day,
        d.year_month,
        d.quarter_number,
        d.year_number,
        d.is_weekend,

        -- Account attributes (denormalized)
        acct.account_id,
        acct.account_name,
        -- acct.account_type,

        -- User attributes (denormalized)
        -- u.user_id,
        -- u.user_name,

        -- Fact metrics (at grain — NO aggregation)
        f.{{entity}}_id,
        -- f.metric_count,
        -- f.duration_seconds,

        -- Audit
        f.created_at,
        f.updated_at,

    from import_facts as f
    left join import_date as d
        on f.date_sk = d.date_sk
    left join import_dim_account as acct
        on f.account_sk = acct.account_sk
    -- left join import_dim_user as u
    --     on f.user_sk = u.user_sk
),

-- STEP 4: FINAL
final as (
    select * from joined
    where {{ limit_dev_data('date_day') }}
)

select * from final
