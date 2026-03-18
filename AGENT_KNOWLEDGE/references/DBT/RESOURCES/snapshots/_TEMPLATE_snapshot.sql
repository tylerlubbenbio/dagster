-- =============================================================================
-- Snapshot: snap_salesforce__accounts
-- Description: SCD Type 2 capture for accounts from Salesforce
-- =============================================================================
-- WORKFLOW:
--   1. This snapshot detects changes and captures historical versions
--   2. Stored in isolated '{{project_name}}_snapshots' schema
--   3. Treat output as a raw source — reference it from staging to clean + add SKs
--   4. dbt auto-adds dbt_valid_from and dbt_valid_to timestamps
--   5. In fact tables, join using date ranges to get the historical dim version
--
-- STRATEGY OPTIONS:
--   timestamp — Use when source has a reliable updated_at column (preferred)
--   check     — Use when no reliable updated_at exists; compares specific columns
--
-- USAGE IN FACT TABLES:
--   Join fact to snapshot-based dim using date range:
--     ON fct.account_sk = dim.account_sk
--     AND fct.created_at >= dim.dbt_valid_from
--     AND fct.created_at < coalesce(dim.dbt_valid_to, '9999-12-31')
-- =============================================================================

{% snapshot snap_salesforce__accounts %}

{{ config(
    target_schema='{{project_name}}_snapshots',
    unique_key='account_id',

    -- OPTION A: Timestamp strategy (preferred — use if updated_at is reliable)
    strategy='timestamp',
    updated_at='updated_at',

    -- OPTION B: Check strategy (use if no reliable updated_at exists)
    -- strategy='check',
    -- check_cols=['column_1', 'column_2', 'column_3'],

    invalidate_hard_deletes=true,
) }}

select * from {{ source('raw_salesforce', 'accounts') }}

{% endsnapshot %}
