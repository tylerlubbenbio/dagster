> **Note:** This document uses generic warehouse terminology. Run /activate to get database-specific instructions in _RESOURCES/{db}.md.

# 3. Universal Dagster Architecture

**Orchestration and asset design for multi-source, multi-layer pipelines**

---

## Table of Contents

1. [Rules & Conventions](#rules--conventions)
2. [System Overview](#system-overview)
3. [Definitions Structure (Layer Separation)](#definitions-structure-layer-separation)
4. [Asset Factory Pattern (YAML to Python)](#asset-factory-pattern-yaml-to-python)
5. [Resources](#resources)
6. [Assets](#assets)
7. [IO Managers](#io-managers)
8. [Watermark Table & Partitions](#watermark-table--partitions)
9. [Metadata](#metadata)
10. [Asset Checks](#asset-checks)
11. [Concurrency & Retries](#concurrency--retries)
12. [Scheduling, Auto-Materialization & Freshness](#scheduling-auto-materialization--freshness)
13. [Sensors vs Automation Conditions](#sensors-vs-automation-conditions)
14. [Organization & Lineage](#organization--lineage)
15. [DBT Integration](#dbt-integration)
16. [Data Quality & Alerts](#data-quality--alerts)
17. [Slack Failure Notifications (Sensor-Based)](#slack-failure-notifications-sensor-based)
18. [Development Environment](#development-environment)
19. [Config vs Resources](#config-vs-resources)
20. [Quick Reference](#quick-reference)

---

## Rules & Conventions

**Critical rules that apply across ALL Dagster assets and jobs**

---

## 🚨 CRITICAL RULES: JSON Columns & Bulk Load

**RULE 1: ALWAYS identify JSON columns and use JSON column type (JSONB/VARIANT/SUPER) from the start**

When creating config.yaml for a new source:
1. Inspect source schema - look for: Postgres ARRAY/JSONB, MySQL JSON, API fields with arrays/objects
2. In DDL: Create these columns as JSON column type (JSONB/VARIANT/SUPER) (Step 2)
3. In config.yaml field_mappings: **DO NOT add any transform** - pass raw dicts/lists through
4. In IO Manager: bulk load with JSON format preserves native structure

**Examples:**
```yaml
# ✅ CORRECT - Postgres ARRAY column
- source: inherited_roles  # ARRAY['admin', 'editor']
  column: inherited_roles
  # NO TRANSFORM - pass raw list through

# ✅ CORRECT - Postgres JSONB column
- source: metadata  # {"key": "value"}
  column: metadata
  # NO TRANSFORM - pass raw dict through

# ❌ WRONG - json_dump transform
- source: inherited_roles
  column: inherited_roles
  transform: json_dump  # ← BREAKS JSON column type! Creates VARCHAR(65535) limit
```

**RULE 2: Bulk load is the DEFAULT load method**

**Factory default: `s3_copy`** - Consistent, fast, memory-safe for all table sizes.

| Table Size | load_method | Notes |
|------------|-------------|-------|
| **ALL tables** | `s3_copy` (default) | No need to specify - factory default |
| < 10 rows (rare) | `direct_insert` | Only override for micro config tables |

**RULE 3: NEVER use `SELECT *` from source — always select explicit columns**

Use `_get_safe_columns()` in every `extractor.py` — intersects source columns with warehouse target columns. New source columns are silently skipped until you add them to the DDL.

---

### Asset Naming

**Rule:** Name assets after their **OUTPUT** (target table or data product), not after scripts or processes.

**Examples:**
- Asset `history` produces table `raw_chat.history`
- Asset `accounts` produces table `raw_{{source}}.accounts`

**Why:** Lineage is self-documenting; UI and code stay aligned with target tables.

---

### Schema and Table Naming

- RAW schemas: `raw_{source}` (e.g. `raw_salesforce`, `raw_chat`)
- Core schemas: `core_{domain}` (e.g. `core_crm`, `core_product`)
- OBT schemas: `obt_{domain}` (e.g. `obt_analytics`)
- Report schemas: `report_{domain}` (e.g. `report_exec`)

---

### Credentials and Paths

**Rule:** No hardcoded credentials or absolute paths in asset code.

- Load connection details from **Dagster resources** (or from config that resources provide).
- Secrets live in `.env`; resources read env and expose clients/connections.

---

### One Group Per Asset

**Rule:** Dagster assets belong to exactly **one group**. Use **layer + source** as the group (e.g. `raw_hubspot`, `raw_chat`, `core_crm`). Use **tags** for every other dimension (schedule tier, source type, etc.).

---

### Structured Logging

**Rule:** Every asset MUST log at every pipeline phase using `context.log.info()`. Never use `print()`.

**Required log points:** `[START]`, watermark value, date range + extraction method, record count, transform stats, `[END]` with duration, `[FAILED]` on exception.

---

### Error Handling

**Rule:** Asset functions MUST wrap all logic in `try/except`. On failure:
1. Log `[FAILED]` with error details
2. Set watermark status to `"failed"` with the error message
3. Re-raise the exception so Dagster marks the run as failed

---

### Pitfalls to Avoid

| Don't | Do |
|-------|-----|
| Name assets after scripts (e.g. `ingest_contacts`) | Name after tables (e.g. `contacts` for `raw_{{source}}.contacts`) |
| Use `json_dump` transform on JSON column type columns | Pass raw dicts/lists through — JSON column type accepts native JSON via bulk load |
| Use `print()` for logging | Use `context.log.info()` / `.warning()` / `.error()` |
| Let exceptions bubble uncaught | Wrap in `try/except`, set watermark to `"failed"`, re-raise |
| Generate a new timestamp for bulk load prefix | Derive COPY prefix from actual uploaded keys (avoids path mismatch) |
| Use shared prefix for all assets in a source | Include `{schema}_{table}` in prefix to avoid key collision on parallel runs |
| Use `AssetCheckSeverity.WARNING` | Use `AssetCheckSeverity.WARN` (Dagster 1.x enum value is `WARN`) |
| Use param injection in `@asset_check` (e.g. `def check(warehouse):`) | Use `def check(context):` + `context.resources.warehouse` + `required_resource_keys={"warehouse"}` |
| Omit `ORDER BY` note | **Never ORDER BY in incremental extraction queries** — causes sort memory errors on large tables |

---

## System Overview

Dagster orchestrates the 4-layer pipeline (Raw, Core, OBT, Report): assets represent tables (or views); resources provide connections to sources and targets; the **watermark table** (`metadata.pipeline_watermarks`) tracks incremental progress across all layers.

**Core responsibilities (Dagster layer):**
1. **Create assets** for all pipeline outputs (one asset per target table where appropriate).
2. **Set dependencies** (`deps=` or `ins=`) so ordering matches layer and upstream/downstream.
3. **Add metadata** (row counts, execution time, hours_since_last_run, etc.) to every asset.
4. **Organize with groups** (layer+source) for UI filtering and lineage.
5. **Create jobs and schedules** (or automation conditions) for regular runs.

---

## Definitions Structure (Layer Separation)

**Rule:** Split definitions by layer (ingestion, transformation) for clarity and maintainability.

### File Structure

```
dagster/
├── definitions.py                    # Main entry point - merges all layers
├── ingestion/
│   ├── definitions.py                # Ingestion layer definitions
│   ├── jobs.py, schedules.py, sensors.py
│   └── raw/{source}/config.yaml
└── transformation/
    └── definitions.py                # Transformation layer definitions
```

### Main Entry Point (`dagster/definitions.py`)

```python
from dagster import Definitions
from ingestion.definitions import ingestion_defs
from transformation.definitions import transformation_defs

defs = Definitions.merge(
    ingestion_defs,
    transformation_defs,
)
```

### Ingestion Layer (`dagster/ingestion/definitions.py`)

```python
from dagster import Definitions
from asset_factory import build_assets_from_yaml

factory_assets, factory_checks = build_assets_from_yaml()

ingestion_defs = Definitions(
    assets=factory_assets,
    asset_checks=factory_checks,
    jobs=[...],
    schedules=ingestion_schedules,
    sensors=[slack_run_failure_sensor],
    resources=_resources,
)
```

---

## Asset Factory Pattern (YAML to Python)

**Rule:** Every source gets a YAML file. The factory generates all Dagster asset definitions from YAML — no exceptions. New source = new YAML entry + reload.

**Workflow:**
1. Define `dagster/asset_factory.py` that scans `dagster/ingestion/raw/*/config.yaml`.
2. Each config.yaml contains: source key, connection_resource, field_mappings, primary keys, incremental columns, group, tags.
3. Factory loops over YAML and builds `@asset` definitions.
4. Factory auto-generates asset checks from YAML `primary_key` (zero_rows, duplicate_pk, null_pk).
5. Factory attaches validation stats and run metadata to every asset.

**CRITICAL: Zero-Memory Pattern (Mandatory for tables with 1000+ rows)**

All extractors MUST:
- Return `str` (file path), not `list[dict]` (records)
- Stream data to `_LOCAL_FILES/{source}/{table}_{timestamp}.ndjson`
- IO Manager detects file path → `_handle_ndjson_file()` → staging upload → bulk load → MERGE

**CRITICAL: JSON Column Type Handling**

When config.yaml has JSON column type columns:
1. **NO transform in field_mappings** - pass raw dicts/lists through
2. **Extractor streams to NDJSON** (not CSV) - JSON structure preserved
3. **IO Manager uploads to staging** → bulk load with JSON format
4. **DO NOT use `json_dump` transform** - breaks JSON column type, creates VARCHAR(65535) limit

### YAML Schema (one file per source)

```yaml
# dagster/ingestion/raw/api_{{source}}/config.yaml
source: {{source}}
source_type: api                     # api | internal_db | s3
connection_resource: {{source}}      # Dagster resource key
default_group: raw_{{source}}
default_tags:
  layer: raw
  source_type: api
  source_system: {{source}}

assets:
  - name: contacts                   # Asset name = target table name
    description: >                   # REQUIRED: 2-3 sentences explaining what this data is.
      {{source}} contacts with       # If unsure about downstream usage, ask the user.
      email, lifecycle stage, etc.
    target_schema: raw_{{source}}
    target_table: contacts
    primary_key: id
    incremental_strategy: timestamp  # timestamp | cursor | id | full_refresh
    incremental_column: updated_at
    compute_kind: {{source}}
    schedule_tier: daily
    load_method: s3_copy             # s3_copy | direct_insert

    field_mappings:
      - source: id
        column: id
        transform: to_str
      - source: email
        column: email
      - source: updated_at
        column: updated_at
        transform: warehouse_ts
      # ... one entry per column
```

```yaml
# dagster/ingestion/raw/internal_raw_chat/config.yaml
source: chat
source_type: internal_db
connection_resource: svc_db
custom_extractor: true               # uses extractor.py for complex DB queries
default_group: raw_chat
default_tags:
  layer: raw
  source_type: internal_db
  source_system: svc_db
  database: postgres

assets:
  - name: history
    target_schema: raw_chat
    target_table: history
    primary_key: id
    incremental_strategy: id
    incremental_column: id
    compute_kind: python
    schedule_tier: daily
    load_method: s3_copy
```

**Description (REQUIRED for every asset):**
Every asset MUST have a `description` field. Write 2-3 sentences: what the data is, what it links to, what it's used for downstream. If unsure, ask the user. Generic "extracts data from source" is NOT acceptable.

---

## Resources

**Rule:** Use Dagster **resources** for connections, credentials, and shared clients.

### Resource Skeleton Classes

```python
# dagster/resources.py
import os
import boto3
import psycopg2
import requests
import time
from dagster import ConfigurableResource


class WarehouseResource(ConfigurableResource):
    """Warehouse connection factory. Reads from .env."""

    def get_connection(self):
        return psycopg2.connect(
            host=os.environ["TARGET_HOST"],
            port=int(os.environ.get("TARGET_PORT", 5439)),
            database=os.environ["TARGET_DATABASE"],
            user=os.environ["TARGET_USERNAME"],
            password=os.environ["TARGET_PASSWORD"],
            sslmode="require",
        )

    def execute(self, sql, params=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                if cur.description:
                    return cur.fetchall()
            conn.commit()
        finally:
            conn.close()

    def get_row_count(self, schema, table):
        result = self.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
        return result[0][0] if result else 0


class WatermarkResource(ConfigurableResource):
    """Read/update metadata.pipeline_watermarks via warehouse."""
    warehouse: WarehouseResource

    def get_watermark(self, layer, schema, table):
        rows = self.warehouse.execute(
            """SELECT watermark_value FROM metadata.pipeline_watermarks
               WHERE layer = %s AND target_schema = %s AND target_table = %s""",
            (layer, schema, table),
        )
        return rows[0][0] if rows else None

    def update_watermark(self, layer, schema, table, value, rows_processed, status="success"):
        self.warehouse.execute(
            """UPDATE metadata.pipeline_watermarks
               SET watermark_value = %s, rows_processed = %s, status = %s,
                   last_run_at = CURRENT_TIMESTAMP, last_success_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP
               WHERE layer = %s AND target_schema = %s AND target_table = %s""",
            (str(value), rows_processed, status, layer, schema, table),
        )


class S3Resource(ConfigurableResource):
    """Object storage client for uploading NDJSON and issuing bulk load commands."""
    bucket: str = ""
    region: str = "us-east-1"

    def get_client(self):
        return boto3.client("s3", region_name=self.region)


class ExampleApiResource(ConfigurableResource):
    """Example API client with rate limiting."""

    def _get_headers(self):
        return {"X-API-Key": os.environ["EXAMPLE_API_KEY"]}

    def fetch_records(self, from_date: str, to_date: str, page: int = 1, per_page: int = 100):
        url = "https://api.example.com/v1/records"
        params = {"from": from_date, "to": to_date, "page": page, "per_page": per_page}
        for attempt in range(5):
            resp = requests.get(url, headers=self._get_headers(), params=params)
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("API rate limit exceeded after 5 retries")


def get_all_resources():
    """Build the resources dict for Definitions."""
    warehouse = WarehouseResource()
    return {
        "warehouse": warehouse,
        "watermark": WatermarkResource(warehouse=warehouse),
        "s3": S3Resource(),
        # "api_source": ExampleApiResource(),
        # "slack": get_slack_resource(),
    }
```

---

## Assets

### Asset Types

| Type | Decorator / pattern | Use when |
|------|---------------------|----------|
| **Materializing** | `@asset` | Asset creates/updates the table. |
| **Observable source** | `@observable_source_asset` | External table we observe but do not create. |
| **Non-materializing** | `@asset` returning `None` | Tracks a view or metadata-only output. |

### Watermark Usage

- **Read** the watermark from `metadata.pipeline_watermarks` before running the pipeline logic.
- **Request** only data above that watermark from the source (API or DB).
- **Update** the watermark after a successful run with the **source-system** high-water value (max value from the data pulled), not script run time.

### How Assets Work (Factory-Generated)

**All raw assets are generated by the factory from YAML.** There is no hand-written `@asset` code for raw ingestion.

What the factory-generated asset does internally:
1. Logs `[START]` with schema, table, source, and strategy
2. Reads watermark + computes `hours_since_last_run`
3. Calls `_extract()` → custom extractor streams to NDJSON, returns file path
4. Calls `_transform()` with `field_mappings` → logs raw→mapped counts
5. Calls `_filter_by_watermark()` for incremental dedup
6. Attaches all standard + custom metadata + sample_data markdown table
7. Logs `[END]` with record count and duration
8. Returns records — IO Manager handles persistence and watermark update

**Error handling:** Entire asset function is wrapped in `try/except`. On failure:
- Logs `[FAILED]` with schema, table, duration, and error message
- Sets watermark status to `"failed"`
- Re-raises the exception

---

## IO Managers

`WarehouseIOManager` handles the full write pipeline. Asset functions return data (list of dicts or file path); the IO Manager handles all persistence.

### Two Load Modes

**`s3_copy`:** Asset returns records (or a file path from zero-memory extractors). IO manager serializes to NDJSON, uploads to object storage, then bulk loads into a staging temp table and MERGEs into the target. Staging table + MERGE pattern: `CREATE TEMP TABLE stg_{table}`, bulk load, then `MERGE INTO target USING (deduped subquery via ROW_NUMBER) WHEN MATCHED UPDATE / WHEN NOT MATCHED INSERT`. Atomic upsert — no DELETE step. Duplicate PKs structurally impossible. Always include timestamp format handling in bulk load commands.

**JSON column type columns:** Do NOT use `json_dump` transform. JSON column type columns accept raw JSON objects via bulk load. The `json_dump` transform double-encodes data → warehouse treats it as VARCHAR with 65535-byte limit.

**Bulk load path:** Always derive the COPY prefix from actual uploaded keys, not a separately generated timestamp. Timing mismatch causes "prefix does not exist" errors.

**Prefix per table (STANDARD):** Always include `{schema}_{table}` in the object storage prefix to prevent key collision when assets run in parallel.

**`direct_insert`:** Asset returns records. IO manager routes through a temp staging table — INSERT into staging, then MERGE INTO target.

### IO Manager Skeleton

```python
# dagster/io_managers.py
import json
import uuid
from dagster import IOManager, OutputContext, InputContext


class WarehouseIOManager(IOManager):
    """Handles persistence of asset outputs to the warehouse.

    Two modes based on asset metadata 'load_method':
      - s3_copy: Upload NDJSON to object storage, COPY into staging, MERGE into target
      - direct_insert: INSERT into staging, MERGE into target
    """

    def __init__(self, warehouse, s3, watermark):
        self.warehouse = warehouse
        self.s3 = s3
        self.watermark = watermark

    def handle_output(self, context: OutputContext, records):
        if not records:
            context.log.info("No records to write.")
            return

        metadata = context.metadata or {}
        schema = metadata.get("target_schema", "public")
        table = metadata.get("target_table", context.name)
        pk = metadata.get("primary_key", "id")
        load_method = metadata.get("load_method", "direct_insert")
        layer = metadata.get("layer", "raw")

        if load_method == "s3_copy":
            self._load_via_object_storage(context, records, schema, table, pk)
        else:
            self._load_direct(context, records, schema, table, pk)

        # Update watermark after successful write
        watermark_value = metadata.get("watermark_after")
        if watermark_value and watermark_value != "none":
            self.watermark.update_watermark(layer, schema, table, watermark_value, len(records) if isinstance(records, list) else 0)

    def _load_via_object_storage(self, context, records, schema, table, pk):
        """Upload NDJSON to object storage, COPY into staging temp table, MERGE into target."""
        # Upload records to object storage
        # Issue COPY command into staging temp table
        # MERGE INTO target — atomic upsert
        pass

    def _load_direct(self, context, records, schema, table, pk):
        """INSERT into staging temp table, then MERGE into target."""
        pass

    def load_input(self, context: InputContext):
        metadata = context.upstream_output.metadata or {}
        schema = metadata.get("target_schema", "public")
        table = metadata.get("target_table", context.name)
        rows = self.warehouse.execute(f"SELECT * FROM {schema}.{table}")
        return rows
```

---

## Watermark Table & Partitions

### Watermark Table

- **Table:** `metadata.pipeline_watermarks` as defined in [Universal Pipeline Architecture](2_universal_pipeline_architecture.md#watermark-table-design).
- **Unified across layers:** One table tracks raw, core, obt, report. Watermark value must be the **source-system** high-water value.

### Partitions

- **Default:** Use **watermark-based incremental** sync only; no Dagster partitions required for most pipelines.
- **Add partitions** when: you need time-window backfills, or rate-limit-friendly runs.
- **Recommendation:** Start without partitions; introduce per asset where backfill justifies it.

---

## Metadata

**Rule:** Every materializing asset must attach **mandatory metadata**.

**Mandatory fields (auto-computed by factory):**
- `row_count`: Total rows in the output table (after run).
- `row_count_delta`: Change in row count.
- `last_updated`: ISO timestamp of last update.
- `processing_duration_seconds`: Time taken for the run.
- `records_processed`: Rows processed in this run.
- `errors`: Total error count for the run.
- `dagster_run_id`: Ties metadata back to the specific Dagster run.
- `watermark_before` / `watermark_after`: Shows how far the watermark moved.
- `raw_records_fetched`: Total records returned by source before filtering.
- `records_missing_pk`: Records skipped because primary key was null/missing.
- `hours_since_last_run`: Freshness indicator.
- `date_range_min` / `date_range_max`: Min/max of incremental column.
- `sample_data`: Markdown table of the first 5 records (via `MetadataValue.md()`).

### Custom metadata (YAML-driven, per-asset)

```yaml
custom_metadata:
  - column: transcript
    type: null_count       # -> transcript_null: 120, transcript_present: 3856
  - column: status
    type: value_counts     # -> status_distribution: "active: 45, inactive: 32, ..."
```

**Before writing config.yaml — ALWAYS recommend custom_metadata to the user:**
1. Analyze source schema for columns worth tracking (NULL tracking, value distribution)
2. Present recommendations with explanations
3. Wait for user approval before finalizing config.yaml

---

## Asset Checks

**Rule:** Every asset MUST have asset checks. The factory auto-generates all 5 checks from config.yaml.

| Check | What it does | Severity | Blocks downstream? |
|-------|-------------|----------|-------------------|
| **zero_rows** | Table must have at least 1 row. | ERROR | Yes |
| **duplicate_pk** | No duplicate values in primary key column. | ERROR | Yes |
| **null_pk** | Primary key column must never be NULL. | ERROR | Yes |
| **freshness** | Data updated within expected window. Threshold from `schedule_tier`: hourly=6h, daily=48h, weekly=192h. | WARN | No |
| **schema** | All columns from `field_mappings` must exist in target table. | WARN | No |

**Implementation pattern (critical):**
```python
# CORRECT: use context + required_resource_keys
@asset_check(asset="contacts", name="contacts_zero_rows",
             required_resource_keys={"warehouse"})
def check_zero_rows(context):
    warehouse = context.resources.warehouse
    ...

# WRONG: param injection gives you the asset's OUTPUT, not the resource
@asset_check(asset="contacts", name="contacts_zero_rows")
def check_zero_rows(warehouse):  # ← receives list[dict] from IO manager, NOT WarehouseResource
    ...
```

**Severity enum:** Use `AssetCheckSeverity.WARN` (not `.WARNING`) and `AssetCheckSeverity.ERROR`.

---

## Concurrency & Retries

### Retry Policy

| source_type | Default max_retries | Default delay (s) |
|-------------|--------------------|--------------------|
| `api` | 2 | 30 |
| `internal_db` | 1 | 15 |
| `s3` | 2 | 30 |
| dbt / SQL transforms | 0 | -- |

### Concurrency

- **Per-job concurrency (STANDARD):** ALL ETL jobs MUST include `executor_def=in_process_executor` AND `tags={"dagster/max_concurrent_runs": "1"}`:

```python
from dagster import define_asset_job, in_process_executor

raw_source_job = define_asset_job(
    name="raw_{{source}}_sync",
    selection=AssetSelection.groups("raw_{{source}}"),
    executor_def=in_process_executor,            # REQUIRED - prevents OOMKill from subprocess forks
    tags={"dagster/max_concurrent_runs": "1"},   # REQUIRED - prevents race conditions
)
```

**Why `in_process_executor`:** Default multiprocess executor spawns a subprocess per step/check. On K8s, each fork copies the full Python process (~1Gi). With 5+ asset checks running simultaneously, this causes OOMKill. `in_process_executor` runs all steps sequentially in a single process.

### Idempotency

**Watermark + upsert = safe rerun.** If a run fails mid-batch:
1. Watermark was NOT updated (it's updated after success).
2. Next run reads the same watermark and re-processes the same data.
3. MERGE upsert prevents duplicates atomically.

---

## Scheduling, Auto-Materialization & Freshness

**Rule:** Use **schedules** for regular runs. Use **freshness policies** for downstream layers.

### Simple schedule strategy

- **Nightly:** Data that doesn't need to be fresh. One job/schedule, e.g. 2am.
- **Every 1-2 hours:** Data that should be reasonably fresh. One job/schedule, e.g. every 2 hours.
- **One schedule per tier** is enough (assign assets to groups/tags like `schedule_tier: daily` vs `hourly`).
- **Stagger within a tier** if you hit rate limits or warehouse contention.

### When to use schedule vs freshness policy

| Use case | Use schedule | Use freshness policy |
|----------|--------------|----------------------|
| **Raw ingestion** (API/DB pull) | **Yes.** Fixed cadence with stagger. | Optional in addition. |
| **Core transforms** (dbt or SQL) | Optional. | **Preferred.** Materialize when downstream needs it. |
| **Reporting / marts** | Either. | Same as above. |

**Rule of thumb:** **Schedules** for raw. **Freshness policies + lazy auto-materialization** for downstream layers.

---

## Sensors vs Automation Conditions

| Use | When |
|-----|------|
| **Schedules** | Regular cadence (daily, hourly). |
| **Automation conditions** | Trigger downstream assets when upstream asset completes. |
| **Sensors** | External events (file landed, webhook); or cursor-based conditions. |

---

## Organization & Lineage

**Directory structure:**
- One directory per source. `api_{source}` for API sources, `internal_{source}` for internal DB.
- **Never** put `raw` in the folder name — `raw` is the **schema prefix** only.

```
{{project_name}}/
├── config.json, load_config.py, .env
├── dagster/
│   ├── definitions.py
│   ├── resources.py, io_managers.py, asset_factory.py
│   ├── ingestion/                     (raw layer)
│   │   ├── assets.py, jobs.py, schedules.py
│   │   └── raw/
│   │       ├── api_*/                 (external API sources)
│   │       └── internal_*/            (internal DB sources)
│   ├── dbt/                           (core → report layers)
│   │   ├── dbt_project.yml, profiles.yml
│   │   ├── macros/
│   │   ├── models/
│   │   │   ├── staging/
│   │   │   ├── core/
│   │   │   ├── obt/
│   │   │   └── report/
│   │   └── snapshots/
│   └── deployment/
├── AGENT_KNOWLEDGE/
└── _TESTING/, _LOCAL_FILES/, _LOGS/, prompts/
```

### Groups (one per asset)

Format: `{layer}_{source}`. Examples: `raw_hubspot`, `raw_chat`, `core_crm`, `obt_analytics`, `report_exec`.

### Tags (use for everything else)

| Tag | Values |
|-----|--------|
| `layer` | raw, core, obt, report |
| `source_type` | api, internal_db, s3 |
| `source_system` | salesforce, stripe, etc. |
| `schedule_tier` | hourly, daily, weekly |
| `rate_limit_tier` | high, medium, low |
| `pii` | true, false |
| `incremental_strategy` | timestamp, cursor, id, full_refresh |

---

## DBT Integration

**Rule:** dbt project lives in the same repo at `dagster/dbt/`. Load dbt models as Dagster assets via `@dbt_assets`.

### Layer Mapping

| dbt prefix | Layer | Schema | Example |
|------------|-------|--------|---------|
| `stg_` | Staging (views) | `staging` | `staging.stg_hubspot__contacts` |
| `int_`, `dim_`, `fct_` | Core | `core` | `core.dim_accounts` |
| `fct_` (wide) | OBT | `obt` | `obt.fct_executive_dashboard` |
| `rpt_` | Report | `report` | `report.rpt_executive_dashboard_monthly` |

### How Raw Assets Connect to dbt

1. **Raw Python assets** produce tables like `raw_{{source}}.contacts`.
2. **dbt sources** reference those tables in `dbt/models/staging/sources.yml`.
3. **dbt staging models** SELECT from `{{ source('raw_{{source}}', 'contacts') }}`.
4. **Dagster sees the dependency** via `@dbt_assets` and the manifest.

### ⚠️ MANDATORY: Register Every New Pipeline in sources.yml

Every time a new ingestion pipeline is built, you MUST register it in `dagster/dbt/models/staging/sources.yml`. Without this, dbt models cannot reference the raw table via `{{ source(...) }}`.

**Completion checklist:**
- [ ] Table exists in warehouse and has data
- [ ] Source block added to `dagster/dbt/models/staging/sources.yml`
- [ ] `dbt ls --select source:{source_name}` returns the table without error

### 🚨 CRITICAL: `target.name` in Production Dagster Pods

**Production Dagster pods may run with `target.name = 'dev'`** (intentional — the `generate_schema_name` macro uses it for schema prefix selection). This breaks dbt incremental models if they check `target.name == 'dev'` before `is_incremental()`:

```sql
-- ❌ BROKEN — target.name is 'dev' in prod pods
{% if target.name == 'dev' %}
    where event_start >= current_date - interval '30 days'  -- fires in PROD too!
{% elif is_incremental() %}
    where event_start >= (select max(event_start) from {{ this }}) - interval '3 days'  -- never reached
{% endif %}

-- ✅ CORRECT — is_incremental() checked first
{% if var('backfill_start', none) is not none %}
    where event_start >= '{{ var("backfill_start") }}'
      and event_start <  '{{ var("backfill_end") }}'
{% elif is_incremental() %}
    where event_start >= (select max(event_start) from {{ this }}) - interval '{{ var("lookback_days") }} days'
{% else %}
    where event_start >= current_date - interval '{{ var("dev_data_days") }} days'
{% endif %}
```

### Dagster Registration

```python
# dagster/transformation/dbt_assets.py
from pathlib import Path
from dagster_dbt import DbtCliResource, dbt_assets, DbtProject

DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent / "dbt"
dbt_project = DbtProject(project_dir=DBT_PROJECT_DIR)

@dbt_assets(manifest=dbt_project.manifest_path)
def all_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()
```

---

## Data Quality & Alerts

### Slack Failure Notifications (Sensor-Based)

**Rule:** Use a **sensor-based polling pattern** for Slack failure notifications across ALL jobs.

**Why sensors instead of hooks:**
- `define_asset_job()` does NOT support `.with_hooks()`
- Sensors are centralized — one sensor handles all failures across all jobs

```python
# dagster/ingestion/sensors.py
import os
from datetime import datetime, timedelta
from dagster import DagsterRunStatus, sensor, DefaultSensorStatus, RunsFilter

@sensor(
    name="slack_run_failure_sensor",
    minimum_interval_seconds=30,
    default_status=DefaultSensorStatus.RUNNING,
)
def slack_run_failure_sensor(context):
    """Poll for failed runs and post to Slack."""
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token:
        context.update_cursor(str(datetime.now().timestamp()))
        return

    cursor = context.cursor
    try:
        cursor_timestamp = float(cursor) if cursor else (datetime.now() - timedelta(minutes=2)).timestamp()
        cursor_dt = datetime.fromtimestamp(cursor_timestamp)
    except (ValueError, TypeError):
        cursor_timestamp = (datetime.now() - timedelta(minutes=2)).timestamp()
        cursor_dt = datetime.fromtimestamp(cursor_timestamp)

    runs_list = list(context.instance.get_runs(
        filters=RunsFilter(statuses=[DagsterRunStatus.FAILURE]),
        limit=50,
    ))

    failed_runs = []
    for run in runs_list:
        run_stats = context.instance.get_run_stats(run.run_id)
        if run_stats.end_time and run_stats.end_time > cursor_timestamp:
            failed_runs.append(run)

    if not failed_runs:
        context.update_cursor(str(datetime.now().timestamp()))
        return

    from slack_sdk import WebClient
    client = WebClient(token=slack_token)
    channel = os.environ.get("SLACK_ALERT_CHANNEL", "#data-pipeline-alerts")
    ui_base = os.environ.get("DAGSTER_UI_BASE_URL", "http://127.0.0.1:3000")

    for run in failed_runs:
        client.chat_postMessage(
            channel=channel,
            text=(
                f":x: *Dagster Run Failed*\n"
                f"*Job:* `{run.job_name}`\n"
                f"*Run ID:* `{run.run_id}`\n"
                f"View details at {ui_base}/runs/{run.run_id}"
            ),
        )

    context.update_cursor(str(datetime.now().timestamp()))
```

---

## Development Environment

**Dev server:**
```bash
DAGSTER_HOME=/absolute/path/to/.dagster_home .venv/bin/python -m dagster dev -f dagster/definitions.py
```

**Key notes:**
- Use **UI "Deployment → Reload"** for asset/job/schedule code changes (preserves run history)
- Only RESTART for: daemon errors persisting after reload, environment variable changes
- **CRITICAL:** Multiple Dagster instances cause daemon conflicts. Always kill ALL before restarting.

**Restart procedure (when necessary):**
```bash
pkill -9 -f dagster && sleep 3
DAGSTER_HOME=/absolute/path .venv/bin/python -m dagster dev -f dagster/definitions.py > _LOGS/dagster.log 2>&1 &
```

---

## Config vs Resources

| What | Where | Example |
|------|-------|---------|
| API base URLs (non-sensitive), endpoint/table lists, feature flags, batch sizes | `config.json` | `{"batch_size": 1000, "endpoints": [...]}` |
| API keys, passwords, host/port | `.env` (read by resources) | `WAREHOUSE_PASSWORD=...` |
| Client classes, auth refresh, rate limiting | Dagster `resources.py` | `class ApiResource` |

---

## Quick Reference

| Item | Value |
|------|-------|
| Main entry point | `dagster/definitions.py` |
| Asset factory | `dagster/asset_factory.py` |
| IO manager | `dagster/io_managers.py` |
| Resources | `dagster/resources.py` |
| Source configs | `dagster/ingestion/raw/*/config.yaml` |
| Dev server | `.venv/bin/python -m dagster dev -f dagster/definitions.py` |
| Watermark table | `metadata.pipeline_watermarks` |
| Group format | `{layer}_{source}` |

**References:** [1. Universal API Architecture](1_universal_api_architecture.md), [2. Universal Pipeline Architecture](2_universal_pipeline_architecture.md).
