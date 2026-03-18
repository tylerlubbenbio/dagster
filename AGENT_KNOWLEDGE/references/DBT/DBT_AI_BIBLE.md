# dbt AI Bible — {{project_name}}_analytics

> **PURPOSE:** Authoritative instruction set for AI generating dbt code in the `{{project_name}}_analytics` project. Follow every rule. Do not deviate.

---

## 1. MANDATORY REFERENCE FILES

Before generating ANY dbt code, load and apply:

1. **`STYLE_GUIDE.md`** — Technical structure: SQL formatting, layer prefixes (`stg_`, `fct_`, `dim_`, `rpt_`), column suffixes (`_id`, `_sk`, `_at`, `_date`), trailing commas, linting.
2. **`BUSINESS_COLUMN_NAMING.md`** — Semantic meaning: controlled vocabulary for DC-specific entities (organizations, documents, crunches, checklists, deals, contacts).

---

## 2. PROJECT CONFIGURATION — `dbt_project.yml`

Project name: `{{project_name}}_analytics`. Profile: `default`. **dbt Core 1.11+ required.**

### Required Settings

- **Materialization by directory:** Set `table` vs. `view` at the directory level, not per-model.
- **Schema by directory:** Each layer gets its own schema (staging, core, analytics, report).
- **Group by directory:** Each layer MUST have `+group: {layer_name}`. This maps to Dagster asset groups so `AssetSelection.groups("analytics_adhoc")` works in job definitions. Without `+group`, all models fall into Dagster's `"default"` group and layer-specific jobs cannot select them.
- **Variables (`vars`):** Define ALL global settings here. NEVER hardcode in SQL.
- **Tags:** Apply at folder level: `daily`, `pii`, `hourly`, `weekly`. **In YAML, tags go inside a `config:` block (dbt 1.11+).**
- **Hooks:** Use `pre-hook`, `post-hook`, `on-run-start`, `on-run-end` for audit logs and permissions.
- **Query Comment:** Tag every warehouse query for cost tracking and debugging.
- **Flags:** Enable strict resource naming.

### dbt 1.11 Required Configurations

These MUST be in every `dbt_project.yml`:

```yaml
# Catch duplicate resource names at parse time
flags:
  require_unique_project_resource_names: true

# Global variables — NEVER hardcode in SQL
vars:
  lookback_days: 3        # Incremental model late-arriving data window
  dev_data_days: 30       # Days of data in dev environment

# Query tagging — track dbt queries in warehouse query history
query-comment:
  comment: "dbt: {{ node.unique_id }}"
  append: true
```

- **`flags.require_unique_project_resource_names`** — Fails fast if two models share a name. Always enable.
- **`vars.lookback_days`** — Use in incremental models: `interval '{{ var("lookback_days") }} days'`. Never hardcode `3`.
- **`vars.dev_data_days`** — Use in dev data sampling: `interval '{{ var("dev_data_days") }} days'`. Never hardcode `30`.
- **`query-comment`** — Every query dbt sends to the warehouse gets tagged with the model's unique_id. Use your warehouse's query history (e.g. `STL_QUERY` on Redshift, `QUERY_HISTORY` on Snowflake, `pg_stat_statements` on Postgres) to trace slow queries back to specific models.

### Package Management — `packages.yml`

Pin versions with **list format** (required in dbt 1.11+). NEVER use unpinned versions. NEVER use comma-separated strings.

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.0.0", "<2.0.0"]
  - package: metaplane/dbt_expectations
    version: [">=0.10.0", "<1.0.0"]
  - package: dbt-labs/audit_helper
    version: [">=0.9.0", "<1.0.0"]
```

**Common mistakes:**
- `version: ">=1.0.0, <2.0.0"` — WRONG (string format, fails in dbt 1.11)
- `version: [">=1.0.0", "<2.0.0"]` — CORRECT (list format)
- `calogica/dbt_expectations` — WRONG (deprecated, renamed to `metaplane`)
- `dbt-labs/dbt_audit_helper` — WRONG (correct name is `dbt-labs/audit_helper`)

---

## 3. FOLDER STRUCTURE — MANDATORY HIERARCHY

```
dagster/dbt/
├── dbt_project.yml
├── profiles.yml
├── macros/
│   ├── generate_schema_name.sql        # REQUIRED: _dev suffix routing
│   └── {reusable_logic}.sql
│
├── models/
│   ├── staging/                        # Layer 2: Cleaned views
│   │   ├── sources.yml                 # All 11 source definitions
│   │   ├── {source_system}/
│   │   │   ├── _schema.yml
│   │   │   ├── _docs.md
│   │   │   └── stg_{source}__{table}.sql
│   │   └── ...
│   │
│   ├── core/                           # Layer 3: Star schema
│   │   ├── _schema.yml
│   │   ├── dim_{name}.sql
│   │   ├── dim_date.sql
│   │   ├── fct_{name}.sql
│   │   └── intermediate/              # Sub-domain groupings
│   │       └── {domain}/
│   │
│   ├── analytics/                      # Layer 4: Team-specific OBTs
│   │   ├── {team}/
│   │   │   ├── _schema.yml
│   │   │   └── {team}_{use_case}.sql
│   │   └── ...
│   │
│   └── report/                         # Layer 5: Aggregated reports
│       ├── _schema.yml
│       ├── exposures.yml
│       └── rpt_{use_case}.sql
│
├── snapshots/                          # SCD Type 2, target_schema: {{project_name}}_snapshots
│   └── snap_{source}__{table}.sql
│
└── tests/
```

### Directory Naming Rules

| Layer    | Table Name Format             | Example                          |
|----------|-------------------------------|----------------------------------|
| Raw      | `raw_{source_name}`           | `raw_salesforce`                 |
| Staging  | `stg_{source}__{table_name}`  | `stg_salesforce__accounts`       |
| Core     | `dim_{name}` / `fct_{name}`  | `dim_account`, `fct_crunches`    |
| Analytics| `{team}_{use_case}`           | `product_monthly_usage`          |
| Report   | `rpt_{use_case}`              | `rpt_executive_dashboard`        |

Use `__` (double underscore) to separate logical segments. Use `_` (single underscore) for words within a segment.

---

## 4. SQL MODEL STRUCTURE — THE 4-STEP CTE PATTERN

Every SQL model MUST follow this structure:

```sql
-- =============================================================================
-- Model: {model_name}
-- Description: {brief description}
-- Grain: {what one row represents}
-- =============================================================================

-- STEP 1: CONFIGS
{{ config(
    materialized='table',
    -- # ACTIVATE: sort/clustering — sort=['created_at', 'organization_id']  (Redshift: sort keys; Snowflake: cluster_by; Postgres: omit)
    -- # ACTIVATE: distribution/clustering — dist='organization_id'           (Redshift only; omit for Snowflake/Postgres)
    tags=['daily'],
) }}

-- STEP 2: IMPORTS (Always select * — bring in full sources/refs)
with import_users as (
    select * from {{ ref('stg_{{source}}__{{entity_plural}}') }}
),

import_accounts as (
    select * from {{ ref('stg_salesforce__accounts') }}
),

-- STEP 3: LOGIC CTEs (One per logical unit)
user_crunch_counts as (
    select
        user_id,
        count(crunch_id) as total_crunches,
        count(distinct document_id) as unique_documents,
    from import_crunches
    group by 1
),

-- STEP 4: FINAL CTE
final as (
    select
        -- 1. Primary Surrogate Key
        u.user_sk,

        -- 2. Foreign Surrogate Keys
        u.account_sk,
        u.organization_sk,

        -- 3. Natural Keys
        u.user_id,

        -- 4. Attributes and Metrics
        u.user_name,
        u.email,
        c.total_crunches,
        c.unique_documents,

        -- 5. Audit / Metadata
        u.created_at,
        u.updated_at,
    from import_users as u
    left join user_crunch_counts as c
        on u.user_id = c.user_id
)

-- STEP 5: FINAL SELECT (always select * from final)
select * from final
```

### CTE Rules

1. **Imports at the top.** Always `select *` from `{{ ref() }}` or `{{ source() }}`. Never filter or transform in the import CTE. Dev data sampling (`{% if target.name == 'dev' %} where ... {% endif %}`) is the only exception.
2. **ONE CTE PER LOGICAL UNIT — for multi-source models.** Each distinct transformation topic gets its own CTE when joining multiple source tables. **EXCEPTION: high-volume single-source models.** When ALL derived columns come from ONE source table (no cross-source joins), collapse all derivations inline into a single CTE instead of splitting into N CTEs and rejoining. N CTEs × 1 large source table = N full table scans + N-1 hash joins → Disk Full / 45+ min runtime. See Section 10 for the single-CTE single-scan pattern.
3. **Final CTE lists EXACT output columns** in correct column order — joins all logic CTEs together. Never use `select *` in the final CTE.
4. **Final SELECT is always `select * from final`.** Nothing else.
5. **Trailing commas** on all column lists.
6. **Comment each CTE** with a brief description of what it produces.
7. **Ask before choosing dist/sort keys.** If the primary join key is not obvious from the model's purpose, ask the user before defaulting to a guess. Wrong dist keys cause skew or missed co-location — they are hard to fix after the fact.

---

## 5. COLUMN RULES

### Naming

- **Strict `snake_case`** everywhere.
- **Boolean prefixes:** `is_` or `has_`
- **Timestamp suffixes:** `_at` for timestamps, `_date` for date-only
- **Natural Keys:** `{entity}_id` (e.g., `account_id`, `user_id`, `organization_id`)
- **Surrogate Keys:** `{entity}_sk` (e.g., `account_sk`, `user_sk`, `organization_sk`)
- **Same surrogate key name** in both Fact and Dimension tables for simple joins.

### Column Order

Every model's final CTE MUST order columns in this sequence:

1. **Primary Surrogate Key** (e.g., `account_sk`)
2. **Foreign Surrogate Keys** (e.g., `organization_sk`, `user_sk`)
3. **Natural Keys** (e.g., `account_id`)
4. **Attributes / Metrics** (e.g., `account_name`, `total_crunches`)
5. **Audit / Metadata** (e.g., `inserted_at`, `updated_at`)

---

## 6. DATA MODELING RULES BY LAYER

### Layer 1: RAW — Source Tables

- Schema: `raw_{source_name}` (configure per your project — e.g. raw_salesforce, raw_hubspot, etc.)
- Loaded by Dagster ingestion pipelines. Do NOT apply business logic here.

### Layer 2: STAGING — Cleaned Views

- **Materialization:** `view` (always)
- Generate MD5 surrogate keys: `{{ dbt_utils.generate_surrogate_key(['col1', 'col2']) }}`
- Basic cleaning ONLY. No cross-source joins.
- Explicitly list columns (strict data contract).
- Cast all data types. Apply `BUSINESS_COLUMN_NAMING.md` translations.

### Layer 3: CORE — Star Schema

- Build dimensions (`dim_`) FIRST, then facts (`fct_`).
- Always create `dim_date`. Use `dim_date` for date logic, not date columns in facts.
- Declare PKs on dims and FKs on facts (optimizer hints for warehouses that support them).
- All business logic lives here. NEVER in dashboards.

### Layer 4: ANALYTICS — Team-Specific OBTs

- **Materialization:** `table`
- No aggregations. Keep at natural grain.
- Pre-join relevant dimensions into the OBT.

### Layer 5: REPORT — Aggregated Reports

- **Materialization:** `table`
- Aggregations ONLY.
- Apply Model Contracts: `contract: true` with strict data types in YAML.
- Use `exposures.yml` to document dashboard connections.

---

## 7. SURROGATE KEYS

- Generate in the **Staging layer** using `{{ dbt_utils.generate_surrogate_key() }}`
- MD5 hashes. Name: `{entity}_sk`.
- Same name across Fact and Dimension tables for simple joins.

---

## 8. QUALITY TESTING

### dbt Native Tests
- `relationships` — FK validation
- `accepted_values` — enum/category validation

### dbt-expectations
- Complex business logic: row count thresholds, distribution checks, regex patterns.

### Source Freshness (dbt 1.11+ format)

**IMPORTANT:** In dbt 1.11+, `freshness` and `loaded_at_field` MUST be inside a `config:` block. Top-level placement is deprecated and will error in future versions.

```yaml
# CORRECT — dbt 1.11+ format
sources:
  - name: raw_salesforce
    database: "{{your_warehouse_database}}"
    schema: raw_salesforce
    description: Salesforce CRM raw data loaded by the api_salesforce pipeline.
    config:
      freshness:
        warn_after: { count: 24, period: hour }
        error_after: { count: 48, period: hour }
      loaded_at_field: inserted_at
    tables:
      - name: account
      - name: opportunity
```

```yaml
# WRONG — deprecated top-level format (will break in future dbt versions)
sources:
  - name: raw_salesforce
    freshness:                    # ← WRONG: not inside config block
      warn_after: { count: 24, period: hour }
    loaded_at_field: inserted_at  # ← WRONG: not inside config block
```

### Audit Helper
Use `dbt-labs/audit_helper` when refactoring models. Compare row counts and column values.

---

## 9. SNAPSHOTS

- **Target schema:** `{{project_name}}_snapshots`
- Use `timestamp` strategy if source has reliable `updated_at`. Use `check` strategy otherwise.
- Treat snapshots as raw sources. SELECT from the snapshot in Staging views to clean and generate `_sk` keys.
- dbt auto-adds `dbt_valid_from` and `dbt_valid_to` for historical joins.
- See `RESOURCES/snapshots/_TEMPLATE_snapshot.sql` for the template.

---

## 10. INCREMENTAL MODELS

### When to Use Incremental vs Table

The threshold depends heavily on **what the model computes**, not just row count:

| Model Type | Row Threshold for `incremental` | Why |
|---|---|---|
| Heavy computation (regex, JSON extraction, many CTEs) | **> 50k rows** | 40+ `regexp_substr` calls × 24M rows = 45+ min/run |
| Moderate joins + expressions | **> 200k rows** | Full scan + join cost adds up fast |
| Simple pass-through (select/cast) | **> 500k rows** | Cheap per row, but still scales poorly |
| Aggregations / full-scan by design | Never incremental | Must see all rows to compute correctly |
| Dimension tables | Never incremental | Always small, always `table` |

**Default rule: if it's event/log/session data → always `incremental`, no matter the size.**
Event data is append-only and grows forever. Starting as `table` is always wrong for event sources.

**CRITICAL for analytics on high-volume event sources (e.g. clickstream, event tracking):**
- High-volume event tables (20M+ rows) with heavy computation → ALWAYS `incremental`
- A `table` materialization on millions of rows with heavy computation = very long full rebuild every daily run
- `incremental` with a 3-day lookback window = fast daily run
- Use `unique_key='event_id'` and filter on `event_start`

**On batching:** Incremental handles ongoing daily runs naturally (lookback window = only new data). Batching by date range is only needed for the **initial backfill** of a large historical table.

### 🚨 CRITICAL: Condition Ordering in Incremental Models

**`is_incremental()` MUST be checked BEFORE `target.name`.**

In production Dagster pods, `target.name` is `'dev'` — this is intentional (the `generate_schema_name` macro prefixes schemas with `dev_` unless target is `prod`). If you put `{% if target.name == 'dev' %}` first, the incremental watermark filter is **never reached** in production. Every run scans the full table.

**WRONG — bypasses watermark in production (never do this):**
```sql
{% if target.name == 'dev' %}
    where event_start >= current_date - interval '30 days'
{% elif is_incremental() %}
    where event_start >= (select max(event_start) from {{ this }}) - interval '3 days'
{% endif %}
```

**CORRECT — condition order: backfill → is_incremental → else (dev/default window):**
```sql
{% if var('backfill_start', none) is not none %}
    where event_start >= '{{ var("backfill_start") }}'
      and event_start <  '{{ var("backfill_end") }}'
{% elif is_incremental() %}
    where event_start >= (select max(event_start) from {{ this }}) - interval '{{ var("lookback_days") }} days'
{% else %}
    where event_start >= current_date - interval '{{ var("dev_data_days") }} days'
{% endif %}
```

The `else` branch handles both true dev environments AND the initial full build (when `is_incremental()` is false). `target.name` should **never** be used in the WHERE clause of an incremental model filter.

### 🚨 CRITICAL: Single-CTE Single-Scan for High-Volume Single-Source Models

When a model derives ALL its columns from ONE source table (no joins to other tables), **do NOT split into multiple CTEs** — even if you have many derived columns. Multiple CTEs each scanning the same source = N redundant full table scans + N-1 hash joins → Disk Full.

**WRONG — 5 CTEs × 24M rows = 6 scans + 5 hash joins → Disk Full:**
```sql
with import_events as (select * from {{ source(...) }} where ...),

url_extractions as (
    select event_id, regexp_substr(page_url, '...') as crunch_uuid, ...
    from import_events
),
referer_enrichment as (
    select event_id, case when ... end as referer_type, ...
    from import_events
),
geo_enrichment as (
    select event_id, try_cast(...) as page_lat, ...
    from import_events
),
-- ... 2 more CTEs, each scanning import_events ...

final as (
    select e.*, u.crunch_uuid, r.referer_type, g.page_lat, ...
    from import_events e
    left join url_extractions u on e.event_id = u.event_id
    left join referer_enrichment r on e.event_id = r.event_id
    left join geo_enrichment g on e.event_id = g.event_id
    -- ... 2 more joins
)
```

**CORRECT — 1 CTE, all derived columns inline, 1 scan, 0 joins:**
```sql
with events_enriched as (
    select
        -- original columns
        event_id, session_id, page_id, ...,
        -- derived: URL extractions
        regexp_substr(page_url, '...') as crunch_uuid,
        case when page_url like '%/crunches/%' then 'crunches' ... end as url_type,
        -- derived: referer
        case when page_referer_url is null then 'direct' ... end as referer_type,
        -- derived: geo
        try_cast(trim(split_part(page_lat_long, ',', 1)) as decimal(10,6)) as page_lat,
        -- derived: flags
        date(event_start) as event_date,
        ...
    from {{ source('raw_events', 'events') }}
    {% if var('backfill_start', none) is not none %}
        where event_start >= '{{ var("backfill_start") }}'
          and event_start <  '{{ var("backfill_end") }}'
    {% elif is_incremental() %}
        where event_start >= (select max(event_start) from {{ this }}) - interval '{{ var("lookback_days") }} days'
    {% else %}
        where event_start >= current_date - interval '{{ var("dev_data_days") }} days'
    {% endif %}
)

select * from events_enriched
```

**Rule:** When ALL derived columns come from the same source table with no cross-source joins, collapse all derivations inline into one CTE. Use the multi-CTE pattern only when joining multiple distinct source tables.

### Rules for large `fct_` and high-volume analytics tables:

1. Always define `unique_key` (upsert, not blind append).
2. Set `on_schema_change='append_new_columns'`.
3. Use `var('lookback_days')` for the lookback window in the `{% if is_incremental() %}` filter. NEVER hardcode.
4. `is_incremental()` MUST come before any `target.name` check in WHERE clauses. In production Dagster pods, `target.name == 'dev'` is TRUE — so checking `target.name` first bypasses the watermark filter entirely.

**High-volume analytics_adhoc pattern (e.g. high-volume events) — single-CTE:**

```sql
{{ config(
    materialized='incremental',
    unique_key='event_id',
    on_schema_change='append_new_columns',
    -- # ACTIVATE: sort/clustering — sort=['event_start', 'entity_id']  (Redshift; Snowflake: cluster_by; Postgres: omit)
    -- # ACTIVATE: distribution/clustering — dist='entity_id'            (Redshift only; omit for Snowflake/Postgres)
    tags=['daily'],
) }}

-- Single CTE — one scan of events, all enrichments computed inline.
-- Condition order: backfill > is_incremental > dev/default window.
-- is_incremental() must come before target.name check because production
-- Dagster pods run with target.name='dev' (for schema prefixing) which
-- would otherwise bypass the watermark filter and scan 30+ days of data.
with events_enriched as (
    select
        event_id,
        -- all original columns
        session_id, page_id, ...,
        -- derived columns inline (URL, referer, geo, flags, etc.)
        regexp_substr(page_url, '...') as crunch_uuid,
        case when ... end as url_type,
        ...
    from {{ source('raw_events', 'events') }}
    {% if var('backfill_start', none) is not none %}
        where event_start >= '{{ var("backfill_start") }}'
          and event_start <  '{{ var("backfill_end") }}'
    {% elif is_incremental() %}
        where event_start >= (select max(event_start) from {{ this }}) - interval '{{ var("lookback_days") }} days'
    {% else %}
        where event_start >= current_date - interval '{{ var("dev_data_days") }} days'
    {% endif %}
)

select * from events_enriched
```

**Standard fct_ incremental pattern:**

```sql
{{ config(
    materialized='incremental',
    unique_key='crunch_sk',
    on_schema_change='append_new_columns',
    tags=['daily'],
) }}

with import_crunches as (
    select * from {{ ref('stg_crunches__checklist_assignment') }}
    {% if is_incremental() %}
    where updated_at >= (select max(updated_at) from {{ this }}) - interval '{{ var("lookback_days") }} days'
    {% endif %}
),

final as (
    select
        crunch_sk,
        organization_sk,
        user_sk,
        crunch_id,
        document_id,
        crunch_status,
        created_at,
        updated_at,
    from import_crunches
)

select * from final
```

---

## 11. ENVIRONMENT SETUP

Two environments: `dev` and `prod`.

### profiles.yml

```yaml
default:
  target: "{{ env_var('DBT_TARGET', 'dev') }}"
  outputs:
    dev:
      type: postgres    # or: redshift, snowflake
      host: "{{ env_var('TARGET_HOST') }}"
      port: "{{ env_var('TARGET_PORT', '5432') | int }}"
      user: "{{ env_var('TARGET_USERNAME') }}"
      password: "{{ env_var('TARGET_PASSWORD') }}"
      dbname: "{{ env_var('TARGET_DATABASE') }}"
      schema: dev_staging
      threads: 4
    prod:
      type: postgres    # or: redshift, snowflake
      host: "{{ env_var('TARGET_HOST') }}"
      port: "{{ env_var('TARGET_PORT', '5432') | int }}"
      user: "{{ env_var('TARGET_USERNAME') }}"
      password: "{{ env_var('TARGET_PASSWORD') }}"
      dbname: "{{ env_var('TARGET_DATABASE') }}"
      schema: staging
      threads: 4
```

### Schema Routing — `generate_schema_name` Macro

Overrides dbt default. In production, models build into their official schemas (staging, core, analytics, report). In dev, schemas get a `dev_` **prefix** so all dev schemas sort together in any schema browser (dev_staging, dev_core, dev_analytics, dev_report, dev_analytics_adhoc, etc.).

**CRITICAL: The prefix is `dev_`, NOT a `_dev` suffix.** This keeps all dev schemas grouped together alphabetically.

| Environment | Schema result |
|---|---|
| prod | `analytics_adhoc` |
| dev | `dev_analytics_adhoc` |
| prod | `staging` |
| dev | `dev_staging` |

```sql
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is not none -%}
        {%- if target.name == 'prod' -%}
            {{ custom_schema_name | trim }}
        {%- else -%}
            dev_{{ custom_schema_name | trim }}
        {%- endif -%}
    {%- else -%}
        {{ target.schema }}
    {%- endif -%}
{%- endmacro %}
```

### Dev Data Sampling

Limit dev to recent data using `var('dev_data_days')`:

```sql
{% if target.name == 'dev' %}
where created_at >= current_date - interval '{{ var("dev_data_days") }} days'
{% endif %}
```

### Deployment

1. Build and test locally against `dev`.
2. Commit to Git.
3. Dagster runs `dbt run --target prod` in production.
4. No human hands touch prod.

---

## 12. MACROS AND JINJA

- If you write the same SQL logic more than once, abstract it into a macro. No exceptions.
- NEVER hardcode column or table names inside a macro. Pass them as variables.
- Use `{% set %}` at the top of macros for changing values.
- Use `{{ target.name }}` for environment-aware logic.

---

## 13. DOCUMENTATION

### Schema YAML (`_schema.yml`) — dbt 1.11+ Format
- One per subdirectory. Includes: model descriptions, column descriptions, tests, meta properties.
- **Tags go inside `config:` block** (not top-level). Top-level `tags:` is deprecated in dbt 1.11+.
- **`accepted_values` test requires `arguments:` nesting** in dbt 1.11+.
- Contract enforcement on report-layer models.

```yaml
# CORRECT — dbt 1.11+ format
models:
  - name: dim_date
    description: "Calendar dimension table"
    config:
      tags: ['daily', 'core']          # ← tags inside config block
    columns:
      - name: quarter_number
        tests:
          - accepted_values:
              arguments:               # ← arguments wrapper required
                values: [1, 2, 3, 4]
```

```yaml
# WRONG — deprecated format (will warn/error)
models:
  - name: dim_date
    tags: ['daily', 'core']            # ← WRONG: top-level tags
    columns:
      - name: quarter_number
        tests:
          - accepted_values:
              values: [1, 2, 3, 4]    # ← WRONG: missing arguments wrapper
```

### Docs Blocks (`_docs.md`)
- Long-form explanations in Markdown. Link from `.yml`.

### Source YAML (`sources.yml`)
- All 11 sources defined with freshness thresholds (inside `config:` blocks).
- Sources: define per your project (one `_source.yml` per raw schema).
- Names MUST match Dagster asset names (lineage glue).

### Exposures (`exposures.yml`)
- Document every dashboard connected to report models.

---

## 14. DAGSTER INTEGRATION

- Dagster reads the dbt project and adds all models to lineage automatically.
- **Lineage Glue:** Dagster asset names MUST match keys in `sources.yml`.
- dbt tests appear as Asset Checks in the Dagster UI.
- Tags and meta in `_schema.yml` MUST match Dagster definitions.

---

## 15. REQUIRED dbt MACROS

| Macro | Purpose |
|-------|---------|
| `dbt_utils.generate_surrogate_key` | MD5 surrogate keys |
| `dbt_utils.date_spine` | Calendar dimension (`dim_date`) |
| `dbt_utils.unpivot` / `pivot` | Reshape wide to long |
| `generate_schema_name` | Environment-aware schema routing |

---

## 16. LINTING AND FORMATTING

- SQLFluff with `dialect` set to your warehouse (redshift, snowflake, postgres, ansi).
- All SQL keywords lowercase.
- 4-space indentation.
- Trailing commas on all column lists.
- Run linting in CI before merge.

---

## 17. DATABASE-SPECIFIC RULES

> **Note:** Sort/dist keys apply to **Redshift only**. Snowflake uses cluster keys; Postgres has no sort/dist keys — remove them from `{{ config() }}` blocks entirely. All other rules below apply across warehouses unless noted.

- **Sort Keys (Redshift only):** Always 2 per table using a list — `sort=['date_col', 'filter_col']`. 1st: most-used date/timestamp column. 2nd: highest-cardinality filter column (often the dist key). NEVER use a single string sort key — always a 2-element list. Snowflake equivalent: `cluster_by=['date_col']`. Postgres: omit entirely.
- **Dist Keys (Redshift only):** Facts: dist on most common join FK. Dims: dist on PK. Analytics/Report: `dist='even'`. Snowflake/Postgres: omit entirely.
- **Constraint Declaration:** Declare PKs on dims and FKs on facts. Redshift uses them for optimizer hints but does not enforce.
- **Skip Materialized Views:** Use dbt `table` materialization.
- **JSON Column Types:** Use `SUPER` (Redshift), `VARIANT` (Snowflake), or `JSONB` (Postgres) for JSON data. Never `VARCHAR`.
- **Bulk Load:** For 1,000+ rows, use the warehouse's native bulk load mechanism (e.g. NDJSON + COPY on Redshift, COPY INTO on Snowflake, COPY on Postgres).
- **Cast IDs in Joins:** Always cast IDs to text in joins. Silent failures from varchar/text mismatch are common.
- **Limit Full Refreshes:** Avoid frequent full refreshes on large incremental models.
- **Fast Backfills:** `TRUNCATE` first, then single `INSERT INTO ... SELECT ...`.
- **Threads:** Keep at 4. Do not overload the cluster.
- **WLM:** Separate queues for dbt transforms vs. BI reporting. Enable Auto-WLM.
- **Maintenance:** Schedule warehouse-appropriate maintenance tasks (e.g. `VACUUM`/`ANALYZE` on Redshift/Postgres) after significant loads or nightly during low-traffic. Use a Dagster system asset for this.
- **CI/CD:** Use snapshot-based clones or warehouse-provided CI features.
- **Blue/Green Warning:** Most warehouses lack atomic schema swaps. Renames can break view references — test in dev first.

---

## 18. CRITICAL RULES SUMMARY

1. All business logic in dbt, NEVER in dashboards.
2. MD5 hashes for all surrogate keys.
3. Build dims FIRST, then facts.
4. Identify snapshot candidates before building Core layer.
5. Document every model and every column.
6. Use macros for any repeated logic.
7. Use `dim_date` for all date logic.
8. No human hands touch prod.
9. Trailing commas everywhere.
10. New lines are cheap, brain power is expensive.
