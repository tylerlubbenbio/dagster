# dbt Model Builder

The user will provide a SQL file path. Build a complete, tested dbt model from it.

---

## Step 0: Read All Reference Docs First

Before writing a single line, read these in order:

1. **`AGENT_KNOWLEDGE/references/DBT/DBT_AI_BIBLE.md`** — the law. Every rule applies.
2. **`AGENT_KNOWLEDGE/references/DBT/STYLE_GUIDE.md`** — SQL formatting, layer prefixes, column suffixes, linting rules.
3. **`AGENT_KNOWLEDGE/references/DBT/BUSINESS_COLUMN_NAMING.md`** — DC-specific vocabulary (orgs, crunches, checklists, deals, contacts). Use these names exactly.
4. **`dagster/dbt/dbt_project.yml`** — understand the layer configs, schema names, vars.
5. **`dagster/dbt/models/staging/sources.yml`** — check if the source table is already registered. Add it if not.
6. **`dagster/transformation/assets.py`** — confirm dbt auto-discovery is active (no changes needed if `dbt_project.prepare_if_dev()` is present).

---

## Step 1: Ask Clarifying Questions Before Writing Any Code

**Do NOT guess. Ask the user:**

1. **Which dbt layer?** (staging / core / analytics / analytics_adhoc / report)
   - `analytics_adhoc` = one-off enriched model, no strict upstream dependency required
   - `analytics` = team OBT, joins core dims/facts
   - `staging` = 1:1 cleaned view of a raw source table

2. **What is the primary join key?** (the column other models will join TO this one on)
   - This becomes the `dist` key in data warehouse for join co-location.

3. **What are the 2 sort columns?** (data warehouse always uses 2 — never 1)
   - Sort 1: most-used date/timestamp column (e.g., `event_start`, `created_at`)
   - Sort 2: highest-cardinality filter column (usually the same as the dist key)
   - Config syntax: `sort=['event_start', 'crunch_uuid']` — always a list, never a single string.

4. **Is this high-volume?** (>1M rows expected)
   - If yes AND the source data is append-only (events, logs, sessions): use `materialized='incremental'` with `unique_key`, NOT `table`.
   - A `table` on 24M rows = 30-60 min full rebuild every daily run. `incremental` = only processes new rows (seconds to minutes).
   - Rule: if the user says "this is event data" or the source is event-logs/activity → default to `incremental`.
   - `dev_data_days: 3` keeps dev fast. For incremental: dev filter uses `target.name == 'dev'`, prod uses `is_incremental()` — these are separate conditions.

5. **Does the source table already exist in `sources.yml`?**
   - If not, add it before building the model.

**Do not proceed past Step 1 until these are answered.**

---

## Step 2: Read the SQL File

Read the file path the user provided. Understand:
- What source table it reads from
- What transformations it applies
- What the output grain is (one row per what?)
- What derived/computed columns are produced

---

## Step 3: Determine File Location and Model Name

| Layer | Directory | Naming |
|---|---|---|
| Staging | `dagster/dbt/models/staging/{source}/` | `stg_{source}__{table}.sql` |
| Core dim | `dagster/dbt/models/core/` | `dim_{name}.sql` |
| Core fact | `dagster/dbt/models/core/` | `fct_{name}.sql` |
| Analytics | `dagster/dbt/models/analytics/{team}/` | `{team}_{use_case}.sql` |
| Analytics Ad-Hoc | `dagster/dbt/models/analytics_adhoc/` | `{source}_{description}.sql` |
| Report | `dagster/dbt/models/report/` | `rpt_{use_case}.sql` |

---

## Step 4: Build the dbt Model

Follow the **4-step CTE pattern** from the Bible — NO EXCEPTIONS:

```sql
-- =============================================================================
-- Model: {model_name}
-- Description: {what this model contains}
-- Grain: {what one row represents}
-- Joins on: {primary join key} — {what it joins to}
-- =============================================================================

-- For small/medium tables (<1M rows) or models requiring full rebuild:
{{ config(
    materialized='table',                          -- or 'view' for staging
    sort=['{sort_col_1}', '{sort_col_2}'],         -- ALWAYS a 2-element list: [date_col, filter_col]
    dist='{dist_column}',                          -- asked in Step 1 — the primary join key
    tags=['{layer}', '{source_tag}'],
) }}

-- For HIGH-VOLUME append-only sources (>1M rows — events, logs, sessions):
{{ config(
    materialized='incremental',                    -- NOT 'table' — full rebuild on 24M rows = 60 min/day
    unique_key='{primary_key}',                    -- required for upsert (e.g. 'event_id')
    on_schema_change='append_new_columns',
    sort=['{sort_col_1}', '{sort_col_2}'],
    dist='{dist_column}',
    tags=['{layer}', '{source_tag}'],
) }}

-- STEP 2: IMPORTS (select * only — no transforms here)
-- Three conditions — order matters, all mutually exclusive:
--   1. dev: small sample for fast iteration
--   2. backfill_start var: manual date-range chunk (for initial prod backfill)
--   3. is_incremental: normal daily lookback window
with import_{name} as (
    select * from {{ source('{source}', '{table}') }}
    {% if target.name == 'dev' %}
        where {timestamp_col} >= current_date - interval '{{ var("dev_data_days") }} days'
    {% elif var('backfill_start', none) is not none %}
        where {timestamp_col} >= '{{ var("backfill_start") }}'
          and {timestamp_col} <  '{{ var("backfill_end") }}'
    {% elif is_incremental() %}
        where {timestamp_col} >= (select max({timestamp_col}) from {{ this }}) - interval '{{ var("lookback_days") }} days'
    {% endif %}
),

-- STEP 3: LOGIC CTEs — ONE PER LOGICAL UNIT, NO EXCEPTIONS
-- Each CTE: select event_id + only its own derived columns
-- Examples of separate CTEs: url_extractions, referer_enrichment,
--   geo_enrichment, user_enrichment, event_flags, engagement_metrics

{cte_name} as (
    select
        {key_col},
        {derived columns only},
    from import_{name}
),

-- STEP 4: FINAL — joins all CTEs, lists EXACT columns in correct order
final as (
    select
        -- 1. Natural/Surrogate Key
        -- 2. Foreign Keys
        -- 3. Attributes
        -- 4. Derived columns (from logic CTEs)
        -- 5. Audit (inserted_at, updated_at last)
    from import_{name} as e
    left join {cte_name} as x on e.{key} = x.{key}
    ...
)

select * from final
```

### CRITICAL CTE RULES (learned the hard way):

- ❌ **NEVER put all transformations in one big CTE.** This is the most common mistake.
- ✅ Each logical grouping of derivations gets its own CTE: URL parsing, geo splits, flag calculations, referer classification, time helpers — all separate.
- ✅ Each logic CTE selects: `{join_key}` + its own derived columns only.
- ✅ `final` CTE does the joining and lists every output column explicitly. Never `select *` in final.
- ✅ `select * from final` is the only thing after the final CTE.

---

## Step 5: Create `_schema.yml`

If one doesn't exist for this directory, create it. Include:
- Model name and description
- `config.tags`
- `unique` + `not_null` test on the primary key column
- Descriptions for all key columns (especially the dist key / join key)

---

## Step 6: Register Source (if needed)

If the source table isn't in `dagster/dbt/models/staging/sources.yml`, add it:

```yaml
- name: {table_name}
  description: {description}
```

Under the correct source block. Sources use `config:` block for freshness (dbt 1.11+ format).

---

## Step 7: Update `dbt_project.yml` and `groups.yml` (if new layer)

If this is the first model in a new directory/layer, add the config block to `dbt_project.yml`:

```yaml
{layer_dir}:
  +materialized: table
  +schema: {schema_name}     # prod schema — dev gets dev_ prefix automatically
  +group: {layer_name}       # REQUIRED — maps to Dagster asset group for job selection
  +tags: ['daily']
```

**AND** add the group to `dagster/dbt/models/groups.yml`:

```yaml
  - name: {layer_name}
    owner:
      name: "Data Team"
```

Groups must be declared in `groups.yml` before they can be referenced. Without this, dbt parse will error: `Invalid group '{name}', expected one of []`.

**Why `+group` matters:**
- Each layer group maps directly to a Dagster asset group
- Enables `AssetSelection.groups("analytics_adhoc")` in `dagster/transformation/jobs.py`
- Without `+group`, all models fall into Dagster's `"default"` group — layer-specific jobs won't select anything

**Schema naming:**
- Prod: `analytics_adhoc`, `analytics`, `core`, `staging`, etc.
- Dev: automatically becomes `dev_analytics_adhoc`, `dev_analytics`, `dev_core`, etc.
- The `generate_schema_name` macro handles this — `dev_` prefix, NOT `_dev` suffix.

---

## Step 8: Run in Dev and Verify

```bash
cd dagster/dbt && \
  set -a && source ../../.env 2>/dev/null; set +a; \
  ../../.venv/bin/dbt run --select {model_name} --target dev 2>&1
```

**Confirm in output:**
- Schema shows `dev_{schema}` (e.g. `dev_analytics_adhoc`) — NOT `{schema}_dev`
- `SUCCESS` status
- Run time is reasonable (3-day window = fast; flag if >2 min)

---

## Step 8b: Initial Prod Backfill (High-Volume Incremental Models Only)

**Skip this step if:** the model is `table` materialized, or the table is small enough to build in one go.

**Use this when:** `incremental` model with large historical data (e.g. 24M rows). One giant `dbt run` without a backfill var would try to CREATE TABLE AS SELECT on all history — same 60-min problem. Instead, loop monthly so each chunk is a fast incremental INSERT.

**How it works:**
- First iteration: table doesn't exist → dbt creates it with just that month's data
- Each subsequent iteration: table exists → dbt does incremental INSERT for that month only
- Each month takes 1-3 minutes instead of 60 minutes total

**Create `_TESTING/backfill_{model_name}.sh`:**

```bash
#!/bin/bash
# Initial prod backfill for {model_name} — run ONCE after first deploy.
# Loops monthly. Each chunk = fast incremental INSERT, not a full rebuild.
# Resume from any month if it fails — just update START_YEAR/START_MONTH.

MODEL="{model_name}"
TARGET="prod"
TIMESTAMP_COL="{timestamp_col}"

# Set to earliest date in source table:
# SELECT MIN({timestamp_col}) FROM {raw_schema}.{raw_table}
START_YEAR={yyyy}
START_MONTH={m}

year=$START_YEAR
month=$START_MONTH
current_year=$(date +%Y)
current_month=$(date +%-m)

cd "$(dirname "$0")/../dagster/dbt"
set -a && source ../../.env 2>/dev/null; set +a

while [ "$year" -lt "$current_year" ] || ([ "$year" -eq "$current_year" ] && [ "$month" -le "$current_month" ]); do
    month_fmt=$(printf "%02d" $month)

    if [ "$month" -eq 12 ]; then
        next_year=$((year + 1)); next_month=1
    else
        next_year=$year; next_month=$((month + 1))
    fi
    next_month_fmt=$(printf "%02d" $next_month)

    echo "=== Backfilling $year-$month_fmt ==="
    ../../.venv/bin/dbt run \
        --select $MODEL \
        --target $TARGET \
        --vars "{backfill_start: '$year-$month_fmt-01', backfill_end: '$next_year-$next_month_fmt-01'}" \
        2>&1

    if [ $? -ne 0 ]; then
        echo "ERROR on $year-$month_fmt — fix the issue, update START_YEAR/START_MONTH, and rerun."
        exit 1
    fi

    month=$next_month
    year=$next_year
done

echo "=== Backfill complete! ==="
```

**Run it:**
```bash
chmod +x _TESTING/backfill_{model_name}.sh && ./_TESTING/backfill_{model_name}.sh
```

**After backfill completes:** normal daily `dbt run` (no vars) will use the `is_incremental()` lookback filter automatically.

---

## Step 9: Verify in Dagster

Reload Dagster to pick up the new model:

```bash
curl -s -X POST http://localhost:3000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { reloadRepositoryLocation(repositoryLocationName: \"definitions.py\") { __typename } }"}'
```

Then confirm the asset exists:

```bash
curl -s http://localhost:3000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query":"{ assetNodes { assetKey { path } groupName } }"}' \
  | python3 -c "import sys,json; nodes=[n for n in json.load(sys.stdin)['data']['assetNodes'] if '{model_name}' in str(n)]; print(nodes)"
```

Tell the user the asset path and the direct Dagster URL:
`http://localhost:3000/assets/{layer}%2F{model_name}`

---

## Step 10: Final Checklist

- [ ] All reference docs read before writing any code
- [ ] Dist key confirmed with user (not assumed)
- [ ] Both sort keys confirmed with user — `sort=[date_col, filter_col]` (always a 2-element list)
- [ ] Logic CTEs are split — one per logical unit (url_extractions, geo, referer, flags — never one big CTE)
- [ ] Final CTE lists all columns explicitly (no `select *` in final)
- [ ] Dev data filter applied in import CTE (`{% if target.name == 'dev' %}`)
- [ ] Schema prefix is `dev_` in run output (not `_dev` suffix)
- [ ] `_schema.yml` created with PK uniqueness test
- [ ] Source registered in `sources.yml` if new
- [ ] `dbt_project.yml` updated if new layer (with `+group: {layer_name}`)
- [ ] `models/groups.yml` updated if new group added
- [ ] `dbt run --target dev` passed with SUCCESS
- [ ] Asset visible in Dagster UI
