-- =============================================================================
-- Model: stg_{{source}}__{{table}}
-- Description: Cleaned and typed staging view of raw_{{source}}.{{table}}
-- Grain: One row per {{entity}}
-- Layer: Staging (no joins, no aggregations)
-- =============================================================================

-- STEP 1: CONFIGS
{{ config(
    materialized='view',
    tags=['daily', 'staging'],
) }}

-- STEP 2: IMPORTS
with source_data as (
    select * from {{ source('raw_{{source}}', '{{table}}') }}
),

-- STEP 3: LOGIC — Cleaning, casting, renaming, filtering
cleaned as (
    select
        -- Surrogate Key (MD5 hash — generate here in staging)
        {{ dbt_utils.generate_surrogate_key(['user_id']) }} as user_sk,

        -- Natural Key (cast to text for safe joins)
        cast(user_id as text) as user_id,

        -- Foreign Keys (cast to text)
        -- cast(account_id as text) as account_id,

        -- Attributes (clean, rename, cast)
        -- {{ clean_string('name') }} as user_name,
        -- cast(status as text) as user_status,

        -- Booleans
        -- case when is_active = 'Y' then true else false end as is_active,

        -- Timestamps (cast to proper types)
        -- cast(created_at as timestamp) as created_at,
        -- cast(updated_at as timestamp) as updated_at,

    from source_data

    -- Filter out test/invalid rows
    where 1 = 1
        -- and user_id is not null
)

-- STEP 4: FINAL
select * from cleaned
