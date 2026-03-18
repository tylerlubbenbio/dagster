-- =============================================================================
-- Model: dim_account
-- Description: Dimension table for accounts
-- Grain: One row per account (current state — SCD Type 1)
-- Layer: Core
-- =============================================================================
-- NOTES:
--   - If this dimension needs historical tracking (SCD Type 2), use a snapshot
--     instead and reference it from staging
--   - Declare PK so the query optimizer can use it for join planning
-- =============================================================================

-- STEP 1: CONFIGS
{{ config(
    materialized='table',
    -- # ACTIVATE: sort/clustering — sort=['{{entity}}_sk']  (Redshift: sort keys; Snowflake: cluster_by; Postgres: omit)
    -- # ACTIVATE: distribution/clustering — dist='{{entity}}_sk'  (Redshift only; omit for Snowflake/Postgres)
    tags=['daily', 'core'],
) }}

-- STEP 2: IMPORTS
with import_{{entity}} as (
    select * from {{ ref('stg_{{source}}__{{entity_plural}}') }}
),

-- STEP 3: LOGIC
-- Add any dimension-specific enrichment, deduplication, or business logic here
-- Example: join multiple staging sources for a single dimension
enriched as (
    select
        -- 1. Primary Surrogate Key
        {{entity}}_sk,

        -- 2. Natural Key
        {{entity}}_id,

        -- 3. Attributes
        -- {{entity}}_name,
        -- {{entity}}_status,
        -- {{entity}}_type,

        -- 4. Booleans
        -- is_active,

        -- 5. Audit / Metadata
        created_at,
        updated_at,

    from import_{{entity}}
),

-- STEP 4: FINAL
final as (
    select * from enriched
)

select * from final
