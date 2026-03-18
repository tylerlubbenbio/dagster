-- =============================================================================
-- Model: fct_{{entity_plural}}
-- Description: Fact table for {{entity}} transactions
-- Grain: One row per {{entity}}
-- Layer: Core
-- =============================================================================
-- RULES:
--   - NO date columns in the fact table — join to dim_date instead
--   - FK surrogate keys MUST match the exact name in the dim table
--   - Use incremental materialization for large tables
--   - 3-day lookback window catches late-arriving data
--   - Declare FKs pointing back to dims for query optimizer hints
-- =============================================================================

-- STEP 1: CONFIGS
{{ config(
    materialized='incremental',
    unique_key='{{entity}}_sk',
    on_schema_change='append_new_columns',
    -- # ACTIVATE: sort/clustering — sort=['date_sk', 'account_sk']  (Redshift: sort keys; Snowflake: cluster_by; Postgres: omit)
    -- # ACTIVATE: distribution/clustering — dist='account_sk'        (Redshift only; omit for Snowflake/Postgres)
    tags=['daily', 'core'],
) }}

-- STEP 2: IMPORTS
with import_{{entity_plural}} as (
    select * from {{ ref('stg_{{source}}__{{entity_plural}}') }}
    {% if is_incremental() %}
    where updated_at >= (
        select max(updated_at) from {{ this }}
    ) - interval '{{ var("lookback_days", 3) }} days'
    {% endif %}
),

import_date as (
    select * from {{ ref('dim_date') }}
),

-- STEP 3: LOGIC
-- Join to dim_date to get the date surrogate key
-- Join to other dims as needed for enrichment
joined as (
    select
        -- 1. Primary Surrogate Key
        c.{{entity}}_sk,

        -- 2. Foreign Surrogate Keys (MUST match dim table names exactly)
        d.date_sk,
        -- c.account_sk,

        -- 3. Natural Keys
        c.{{entity}}_id,

        -- 4. Metrics
        -- c.metric_count,
        -- c.duration_seconds,

        -- 5. Degenerate Dimensions (attributes that don't warrant their own dim)
        -- c.{{entity}}_type,

        -- 6. Audit / Metadata
        c.created_at,
        c.updated_at,

    from import_{{entity_plural}} as c
    left join import_date as d
        on cast(c.created_at as date) = d.date_day
),

-- STEP 4: FINAL
final as (
    select * from joined
)

select * from final
