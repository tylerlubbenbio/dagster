> Run /activate to configure this document for your specific database.

# {{PROJECT_NAME}} Architecture

## System Overview

Multi-source ETL + transformation platform. Raw data extracted from APIs and internal DBs → loaded to data warehouse RAW schemas → transformed via dbt (staging → core → analytics → report). Orchestrated by Dagster with YAML-driven asset factory. Deployed to Kubernetes via container registry Docker image.

```
[APIs / DBs / Streaming Sources]
        ↓  (custom extractors → NDJSON → bulk load)
   RAW SCHEMAS  (raw_{{source_a}}, raw_{{source_b}}, raw_{{source_c}}, etc.)
        ↓  (dbt build, daily @ 6am UTC)
   STAGING VIEWS  (dev_staging_* / staging_*)
        ↓
   CORE DIMS/FACTS  (dev_core_* / core_*)
        ↓
   ANALYTICS OBTs  (dev_analytics_* / analytics_*)
        ↓
   REPORT LAYER  (dev_report_* / report_*)
```

---

## Environments

Controlled by `DAGSTER_ENV` environment variable:

| Env | Where | dbt Target | Schemas | Schedules | Data Window |
|-----|-------|------------|---------|-----------|-------------|
| `dev` | Local | `dev` | `dev_*` | OFF | 30-day window |
| `integration` | Local | `integration` | `dev_*` | OFF | Full data |
| `prod` | K8s | `prod` | prod schemas | ON | Full data |

- dbt's `generate_schema_name` macro prefixes `dev_` to all schemas unless `target.name == 'prod'`
- `env_config.py` centralizes env settings; Slack alerts route to `#dev-pipeline-alerts` (dev/integration) or `#data-pipeline-alerts` (prod)

---

## Data Sources

### API Sources

| Source | Schema | Key Tables | Schedule |
|--------|--------|------------|----------|
| `{{api_source_1}}` | `raw_{{api_source_1}}` | e.g. accounts, contacts, deals | daily |
| `{{api_source_2}}` | `raw_{{api_source_2}}` | e.g. events, sessions | daily |

### Internal DB Sources

| Source | Schema | Connection | Key Tables |
|--------|--------|------------|------------|
| `{{db_source_1}}` (Postgres) | `raw_{{db_source_1}}` | read replica | e.g. users, organizations |
| `{{db_source_2}}` (MySQL) | `raw_{{db_source_2}}` | read replica | e.g. records, settings |

Replace placeholders via `/activate` once your sources are defined.

---

## Ingestion Layer

### Asset Factory (`dagster/asset_factory.py`)
- Scans `dagster/ingestion/raw/*/config.yaml` at startup
- Generates `@asset` + `@asset_check` definitions from YAML — no source-specific code in factory
- Pipeline phases per asset: `_resolve_date_range()` → `_extract()` → `_transform()` → `_filter_by_watermark()` → `_build_run_metadata()`
- Branches on `isinstance(raw_records, str)` to handle NDJSON file-path extractors (bulk load path) vs in-memory list extractors

### Per-Source Directory Structure
```
dagster/ingestion/raw/{source}/
├── config.yaml       # Asset factory config (source, assets, field mappings, tags)
├── extractor.py      # custom_extractor=true sources only — returns NDJSON file path
├── ddl/              # CREATE TABLE statements
├── backfill/         # One-time historical load scripts
├── admin/            # Connection test / admin utilities
└── pipelines/        # (older sources) individual pipeline scripts
```

### NDJSON Streaming + Staging Table + Upsert Pattern
- All custom extractors write to `_LOCAL_FILES/{source}/{table}_{timestamp}.ndjson` and return the file path (not a list)
- IO manager (`_handle_ndjson_file`): upload NDJSON → bulk load (S3 COPY / COPY FROM / PUT+COPY INTO depending on warehouse) → `CREATE TEMP TABLE stg AS SELECT * FROM target WHERE 1=0` → load into stg → MERGE INTO target USING deduped subquery from stg (WHEN MATCHED UPDATE, WHEN NOT MATCHED INSERT)
- **Duplicate PKs are structurally impossible** — staging table + MERGE atomically upserts one row per PK with no DELETE step and no window for concurrent duplicates
- **Staging table uses `AS SELECT * FROM target WHERE 1=0`** — NOT `LIKE target` — copies column structure with no constraints (fully nullable), so bulk load never fails on missing optional columns
- full_refresh uses TRUNCATE + INSERT (not MERGE — target is empty)
- Composite PKs (`"col1, col2"` in config.yaml) are split and stripped in both load paths
- JSON columns: pass raw dict/list — never `json_dump` (causes double-encoding). Use JSONB (Postgres), VARIANT (Snowflake), or SUPER (Redshift).
- See `AGENT_KNOWLEDGE/docs/zero_memory_pipeline_pattern.md` for full details

### Watermarks
- Stored in `raw_metadata.watermarks` table
- Asset factory reads watermark → sets `from_date/to_date` → extractor pulls incremental window
- After successful load: watermark updated to `MAX(incremental_column)`

---

## Transformation Layer (dbt)

### Model Layers
```
dagster/dbt/models/
├── staging/      # Views — clean, rename, cast. One model per RAW table.
│   ├── {{source_a}}/   stg_{{source_a}}__table1, table2, ...
│   ├── {{source_b}}/   stg_{{source_b}}__table1, table2, ...
│   └── {{source_c}}/   stg_{{source_c}}__table1, table2, ...
├── core/         # Dims and facts (dim_date, dim_user, fact_events, ...)
├── analytics/    # OBTs — cross-source joined wide tables
├── analytics_adhoc/ # Ad-hoc OBTs triggered on demand
└── report/       # Report aggregations (exposures.yml)
```

Pattern: one staging model per raw table, named `stg_{source}__{table}`.

### dbt Incremental Strategy
- Models use `is_incremental()` with watermark vars (`backfill_start`, `dev_data_days`)
- **Condition order is critical:** `{% if var('backfill_start') %}` → `{% elif is_incremental() %}` → `{% else %}` (dev/full build)
- Production pods use `target.name='dev'` unless explicitly set to `prod` — schema prefix logic depends on this

### dbt Schedule
- `dbt_daily_schedule` runs `dbt build` at 6am UTC daily (after overnight raw ingestion)
- `analytics_adhoc` models triggered by sensor (on-demand)

---

## Dagster Definitions

```
dagster/definitions.py          # Entry: merges ingestion_defs + transformation_defs
dagster/ingestion/definitions.py # All raw assets from asset_factory + schedules/sensors
dagster/transformation/
├── assets.py      # dbt assets (dbt_build_assets)
├── jobs.py        # dbt_build_job
├── schedules.py   # dbt_daily_schedule (6am UTC)
├── sensors.py     # analytics_adhoc trigger sensor
└── resources.py   # dbt resource config
```

---

## Deployment

- **Docker:** `dagster/deployment/Dockerfile` — Python 3.11, built and pushed to container registry
- **K8s:** Helm chart in `dagster/deployment/` — user-code pod rolls on new image
- **Deploy flow:** `docker build → registry push → kubectl rollout restart`
- **Cloud auth:** Re-authenticate when credentials expire (see env-specific instructions)

---

## Key Infrastructure

| Component | Details |
|-----------|---------|
| Warehouse | {{DATA_WAREHOUSE}} (configure via /activate) |
| Orchestration | Dagster (Kubernetes) |
| Transformation | dbt (models in `dagster/dbt/`) |
| File staging | Local NDJSON → bulk load into warehouse |
| Secrets | K8s secrets + local `.env` |
| Alerts | Slack sensor — `#data-pipeline-alerts` (prod) |
| BI Layer | Configured separately on top of warehouse |
