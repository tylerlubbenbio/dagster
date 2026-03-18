> **Note:** This document uses generic warehouse terminology. Run /activate to get database-specific instructions in _RESOURCES/{db}.md.

# 2. Universal Pipeline Architecture

**Step 2 of 3.** Sequence: **1 (API) → 2 (this doc) → 3 (Dagster).** Handoff is strict: finish Step 1 before Step 2; finish Step 2 before Step 3.

**Purpose:** Finish the pipeline from source to data warehouse — DDL, load, watermarks, validation, full sync, and higher layers. **Step 1** ([1. Universal API Architecture](1_universal_api_architecture.md)) is required for API sources: connect, get a sample to local JSON, and document primary key and incremental strategy. **Step 3** ([3. Universal Dagster Architecture](3_universal_dagster_architecture.md)) adds assets and schedules.

**Prerequisites:**
- **API sources:** Complete Step 1. You must have `data/temp/{table}.json`, documented primary key, and incremental strategy per endpoint.
- **DB sources:** Connection details and knowledge of source table(s); no separate "test run" doc.

**Scope (no overlap):** This doc covers directory structure, schema/table/column rules, watermark table, load to data warehouse, validation (including NULL checks), full sync, and SILVER/GOLD/PLATINUM. It does **not** cover: API authentication, connect.py, or "first sample" extraction — those are Step 1 only. It does **not** cover: asset definitions, schedules, or Dagster resources — those are Step 3 only.

---

## Table of Contents

1. [Rules & Conventions](#rules--conventions)
2. [System Overview](#system-overview)
3. [4-Layer Architecture](#4-layer-architecture)
4. [Universal Incremental Strategy](#universal-incremental-strategy)
5. [Metadata-Driven Configuration](#metadata-driven-configuration)
6. [Watermark Table Design](#watermark-table-design)
7. [Auto-Detection Logic](#auto-detection-logic)
8. [File Handling Strategy](#file-handling-strategy)
9. [Complete Workflow](#complete-workflow)
10. [Implementation Phases](#implementation-phases)

---

## Rules & Conventions

**Critical rules that apply across ALL pipelines and layers**

---

## 🚨 CRITICAL RULES: JSON Columns & Large Datasets

**RULE 1: ALWAYS use JSON column type (JSONB/VARIANT/SUPER) for JSON data**

When creating DDL, identify ANY column containing JSON arrays or objects:
- Examples: `["role1", "role2"]`, `{"key": "value"}`, nested objects, PostgreSQL ARRAY/JSONB types
- **DDL:** Create column as JSON column type (JSONB/VARIANT/SUPER) in your data warehouse (not VARCHAR)
- **Extraction:** Pass raw Python dicts/lists through - do NOT serialize to JSON strings
- **Load:** Use the appropriate JSON format option in bulk load commands (preserves native structure)

**Why:**
- JSON column types let the warehouse query JSON fields: `WHERE column.field = 'value'`
- VARCHAR forces string parsing: `WHERE column LIKE '%"field":"value"%'`
- JSON column types support large values (16MB+ depending on warehouse); VARCHAR limited to 65,535 bytes

**RULE 2: ALWAYS use bulk load + NDJSON for large tables (1000+ rows)**

For any table with 1000+ rows:
- **Extraction:** Stream to NDJSON file using `cur.fetchmany(1000)` - return file path, not records
- **Load:** Upload NDJSON to staging → bulk load (10-100x faster than INSERT)
- **Pattern:** See [Zero-Memory Pipeline Pattern](../docs/zero_memory_pipeline_pattern.md)

**Why:**
- Memory: 1M rows in memory = 1GB RAM; streaming = 1MB max
- Speed: bulk load loads in seconds; row-by-row INSERT takes minutes
- Reliability: Crashes? Resume from watermark + file

**Decision Matrix:**

| Column Type | DDL Type | Transform | Load Pattern |
|-------------|----------|-----------|--------------|
| Plain text/numbers | VARCHAR/BIGINT | standard | bulk load (if large) or direct_insert (if small) |
| JSON array/object | **JSON column type (JSONB/VARIANT/SUPER)** | pass raw list/dict | **bulk load with JSON format** |
| Small table (<100 rows) | any | any | **direct_insert** (bulk load overhead not worth it) |
| Large table (1000+ rows) | any | any | **bulk load + NDJSON** (mandatory for memory safety) |

---

### Schema Naming

**Rule:** All RAW layer schemas MUST use `raw_` prefix

**Examples:**
- Source: internal chat DB → Target schema: `raw_chat`
- Source: CRM API → Target schema: `raw_salesforce`
- Source: application DB → Target schema: `raw_{{source}}`

**Why:** Clear separation between raw ingestion and transformed data

---

### Table Naming

**Rule:** Strip source schema prefix, use only table name in target

**Pattern:**
```
Source: {source_schema}.{prefix}_{table_name}
Target: raw_{source}.{table_name}
```

**Examples:**
- `app_db.chat_history` → `raw_app.history` ✅
- `app_db.user` → `raw_{{source}}.user` ✅

**Why:** Avoid redundant prefixes (schema already indicates source)

---

### Column Standards

**Rule 1: Always add audit timestamp columns at the END of every table**

**Required columns:**
```sql
inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

**Placement:** LAST two columns in table definition (after all data columns)

**Behavior:**
- `inserted_at`: Set once on first insert, NEVER updated
- `updated_at`: Set on insert, updated on every upsert

**Rule 2: Remove ALL Airbyte columns**

Columns to REMOVE when replicating from Airbyte-managed tables: `_airbyte_raw_id`, `_airbyte_extracted_at`, `_airbyte_generation_id`, `_airbyte_meta`, any other `_airbyte_*` columns.

**Rule 3: Preserve source table structure exactly (except Airbyte columns)**

Keep ALL columns — even if entirely NULL. NULL columns might become critical in the future. Schema cleanup happens in SILVER/GOLD layers, not RAW.

---

### DDL Scripts

**Rule 1: DDL scripts go in the existing pipeline directory**

Place scripts in the **existing** directory for that source (`api_{source}` or `internal_{source}`). Do not create new source directories.

**Standard layout:**
```
api_{source}/   or   internal_{source}/
    ├── ddl/                    ← Schema/table DDL scripts
    ├── backfill/               ← One-time historical backfills
    ├── admin/                  ← Diagnostics & utilities
    ├── pipelines/              ← Regular extraction/insertion scripts
    └── data/temp/              ← Temporary JSON files
```

**Rule 2: Always use `data_agent` credentials for DDL — load from `config.json`, never hardcode.**

---

### Upsert Logic

**Rule: Use primary key from source for conflict resolution. NEVER use auto-increment.**

```sql
INSERT INTO {target_schema}.{target_table} (col1, col2, ..., inserted_at, updated_at)
VALUES (%s, %s, ..., CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
ON CONFLICT ({primary_key})
DO UPDATE SET
    col1 = EXCLUDED.col1, ...,
    updated_at = CURRENT_TIMESTAMP
    -- NOTE: inserted_at is NOT updated
```

---

### Data Type Mapping

**Source → warehouse type conversions:**

| Source (Postgres/MySQL) | Warehouse | Notes |
|-------------------------|----------|-------|
| `integer`, `int` | `BIGINT` | |
| `varchar(n)`, `text` | `VARCHAR(65535)` | Adjust max for your warehouse |
| `timestamp`, `datetime` | `TIMESTAMP` | |
| `date` | `DATE` | |
| `boolean`, `tinyint(1)` | `BIGINT` (0/1) | |
| **`json`, `jsonb`, `ARRAY[]`** | **JSON column type (JSONB/VARIANT/SUPER)** | **🚨 ALWAYS use JSON column type** |

---

### 🚨 CRITICAL: MySQL Date Column Empty-String Handling

MySQL DATE/DATETIME/TIMESTAMP columns can return empty string `""` — causes bulk load to fail.

**Root cause:** `EMPTYASNULL`/`BLANKSASNULL` bulk load options apply only to `CHAR`/`VARCHAR` — **NOT to DATE or TIMESTAMP columns**.

**MANDATORY pattern for all MySQL extractors:**

```python
_MYSQL_ZERO_DATES = {"0000-00-00 00:00:00", "0000-00-00", b"0000-00-00 00:00:00", b"0000-00-00"}

def _get_date_columns(mysql_conn, source_table: str, safe_cols: list[str]) -> set[str]:
    cur = mysql_conn.cursor()
    cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
          AND DATA_TYPE IN ('date', 'datetime', 'timestamp', 'time', 'year')
    """, (source_table,))
    date_type_cols = {row[0] for row in cur.fetchall()}
    cur.close()
    return date_type_cols & set(safe_cols)

# In per-row loop:
date_cols = _get_date_columns(conn, source_table, safe_cols)
for row in rows:
    record = dict(zip(columns, row))
    for col, val in record.items():
        if val in _MYSQL_ZERO_DATES:
            record[col] = None
        elif col in date_cols and isinstance(val, (str, bytes)) and not val:
            record[col] = None
    f.write(json.dumps(record, default=json_serializer) + "\n")
```

---

### Directory Structure (STANDARD)

**Folder naming (no `raw` in folder name):**
- **Never** put `raw` in the folder name. `raw` is the **schema prefix** only.
- **API sources:** Folder is `api_{source}` only. Not `api_raw_*`.
- **Internal DB sources:** Folder is `internal_{source}` only. Not `internal_raw_*`.

**Backfill strategy (warehouse-to-warehouse):**
- Use a **single INSERT SELECT** (no batching).
- **TRUNCATE the target table first.**
- Completes in 5–10 minutes for millions of rows.

---

### File Naming

**File format:**
- **NDJSON** (newline-delimited JSON) for ALL sources — both database and API sources
- File pattern: `_LOCAL_FILES/{source}/{table}_{timestamp}.ndjson`

**Pipeline scripts:** `{schema}_{table}.py` in `pipelines/` directory
**Backfill scripts:** `backfill_{schema}_{table}.py` in `backfill/` directory

---

## System Overview

A universal, metadata-driven data pipeline that:
- Ingests from **any source** (databases, APIs) without custom code per source
- Auto-detects the **best incremental strategy** based on available columns
- Tracks progress with **unified watermark table** across all layers
- Processes data through **4-layer medallion architecture**
- Uses **config-driven** approach for easy addition of new sources

---

## 4-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ RAW Layer (Bronze)                                          │
│ - Direct extraction from sources                            │
│ - Minimal transformation (data type conversion only)        │
│ - Schema: raw_{source_name}                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ SILVER Layer                                                │
│ - Cleaned, deduplicated, validated data                     │
│ - Business logic applied                                    │
│ - Schema: silver_{domain}                                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ GOLD Layer                                                  │
│ - Aggregated, business-ready datasets                       │
│ - Metrics, KPIs, dimensional models                         │
│ - Schema: gold_{domain}                                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ PLATINUM Layer (Marts/Production)                           │
│ - Final consumption layer, department-specific views        │
│ - Schema: platinum_{department}                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Universal Incremental Strategy

### 1️⃣ Updated Timestamp (BEST)
**Columns:** `updated_at`, `modified_at`, `last_modified`, `LastModifiedDate`

```sql
SELECT * FROM source_table WHERE updated_at > {watermark_value} LIMIT {batch_size}
```

### 2️⃣ Created Timestamp
**Columns:** `created_at`, `inserted_at`, `created_date`

```sql
SELECT * FROM source_table WHERE created_at > {watermark_value} LIMIT {batch_size}
```

### 3️⃣ Incremental ID (Numeric)
**Columns:** `id`, `record_id` (must be auto-incrementing numeric)

```sql
SELECT * FROM source_table WHERE id > {watermark_value} LIMIT {batch_size}
```

### 4️⃣ Full Refresh (Small Tables)
```sql
TRUNCATE target_table;
INSERT INTO target_table SELECT * FROM source_table;
```
**Use when:** Table has < 10,000 rows

### 5️⃣ Brainstorm with User (EDGE CASES)
When none of the above work → pause and collaborate with user.

---

## Metadata-Driven Configuration

### Config Structure (config.json)

```json
{
  "watermark_table": "metadata.pipeline_watermarks",
  "sources": {
    "chat_history": {
      "layer": "raw",
      "source_type": "database",
      "source_connection": "{{source_db}}",
      "source_table": "chat_history",
      "target_schema": "raw_chat",
      "target_table": "history",
      "primary_key": "id",
      "incremental_strategy": "auto",
      "batch_size": 1000,
      "file_format": "ndjson",
      "enabled": true
    },
    "api_accounts": {
      "layer": "raw",
      "source_type": "api",
      "source_connection": "{{api_source}}",
      "target_schema": "raw_{{source}}",
      "target_table": "accounts",
      "primary_key": "id",
      "incremental_strategy": "auto",
      "incremental_column": "updated_at",
      "batch_size": 500,
      "file_format": "ndjson",
      "enabled": true
    }
  }
}
```

---

## Watermark Table Design

**Single unified table tracks progress across ALL 4 layers**

### DDL

```sql
CREATE TABLE metadata.pipeline_watermarks (
    -- Identity
    layer VARCHAR(50) NOT NULL,
    target_schema VARCHAR(100) NOT NULL,
    target_table VARCHAR(100) NOT NULL,

    -- Source tracking
    source_system VARCHAR(100),
    source_object VARCHAR(100),

    -- Watermark details
    watermark_column VARCHAR(100),
    watermark_value VARCHAR(500),
    watermark_type VARCHAR(50),    -- 'timestamp', 'incremental_id', 'full_refresh'

    -- Run metadata
    last_run_at TIMESTAMP,
    last_success_at TIMESTAMP,
    rows_processed BIGINT,

    -- Status tracking
    status VARCHAR(50),            -- 'success', 'failed', 'in_progress'
    error_message TEXT,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (layer, target_schema, target_table)
    -- # ACTIVATE: distribution/clustering key for your warehouse
);
```

### 🚨 CRITICAL: Watermark Value Must Be From SOURCE SYSTEM

**Rule:** `watermark_value` MUST be the high-water mark from the SOURCE data, NOT the script run time.

```python
# ✅ CORRECT
max_source_value = df['updated_at'].max()  # From the actual data pulled
# UPDATE watermark_value = max_source_value

# ❌ WRONG
# UPDATE watermark_value = CURRENT_TIMESTAMP  # Script time, not source data time!
```

---

## Auto-Detection Logic

```python
def auto_detect_strategy(source_connection, source_table, source_schema=None):
    """Inspect source table and determine best incremental strategy."""
    columns = get_table_columns(source_connection, source_table, source_schema)
    row_count = get_table_row_count(source_connection, source_table, source_schema)
    primary_key = get_primary_key(source_connection, source_table, source_schema)

    # Priority 1: Updated timestamp (HIGH CONFIDENCE)
    for col in ['updated_at', 'modified_at', 'last_modified', 'LastModifiedDate']:
        if col in columns and columns[col]['type'] in ['timestamp', 'datetime', 'date']:
            return {'strategy': 'timestamp', 'column': col, 'type': 'updated', 'confidence': 'high'}

    # Priority 2: Created timestamp (MEDIUM CONFIDENCE — misses updates)
    for col in ['created_at', 'inserted_at', 'created_date', 'CreatedDate']:
        if col in columns and columns[col]['type'] in ['timestamp', 'datetime', 'date']:
            return {'strategy': 'timestamp', 'column': col, 'type': 'created', 'confidence': 'medium'}

    # Priority 3: Numeric auto-increment ID (MEDIUM CONFIDENCE — misses updates)
    if primary_key:
        pk_col = columns.get(primary_key)
        if pk_col and pk_col['type'] in ['int', 'bigint', 'integer', 'serial', 'bigserial']:
            return {'strategy': 'incremental_id', 'column': primary_key, 'type': 'id', 'confidence': 'medium'}

    # Priority 4: Full refresh for small tables
    if row_count < 10000:
        return {'strategy': 'full_refresh', 'column': None, 'type': 'full', 'confidence': 'high'}

    # Priority 5: NEEDS DISCUSSION
    return {'strategy': 'needs_discussion', 'column': None, 'type': 'custom', 'confidence': 'low',
            'reason': 'Large table without usable timestamps or auto-increment ID'}
```

---

## File Handling Strategy

### RAW Layer (Extraction from Sources)

**MANDATORY: Zero-Memory Streaming Pattern**

```
1. Read watermark from metadata.pipeline_watermarks
2. Execute query (NO LIMIT - stream everything)
3. Fetch 1000 rows from DB → Write to NDJSON immediately
4. Repeat until no more rows
5. Return NDJSON file path (NOT records)
6. IO Manager: Upload NDJSON to staging
7. IO Manager: Bulk load into warehouse via staging table + MERGE
8. IO Manager: Update watermark to max value
9. IO Manager: TRUNCATE local NDJSON file
```

**Key Implementation Points:**
1. **Extractor returns `str` (file path)**, not `list[dict]` (records)
2. **Use `cur.fetchmany(1000)`**, never `cur.fetchall()`
3. **Write to NDJSON immediately**, don't accumulate in list

### SILVER/GOLD/PLATINUM Layers (Transformations)

**Strategy: SQL transforms (no files) OR dbt models — data stays in warehouse**

---

## Complete Workflow

### RAW Layer Workflow

```
1. INITIALIZE
   - Read watermark from metadata.pipeline_watermarks
   - Update status to 'in_progress'

2. EXTRACT BATCH
   - Connect to source (database/API)
   - Query: WHERE {incremental_column} > {watermark_value}
   - Stream to NDJSON file

3. VALIDATE DATA INTEGRITY
   - Check row count > 0
   - Identify all-NULL columns in TARGET table
   - For each all-NULL column: verify source also NULL (pipeline integrity check)
     * PASS: Source also NULL (unused column, correctly replicated)
     * FAIL: Source has data but target NULL (PIPELINE BUG — fix extraction logic)

4. LOAD TO WAREHOUSE
   - Upload NDJSON to staging area
   - Bulk load into staging temp table
   - MERGE INTO target (WHEN MATCHED UPDATE / WHEN NOT MATCHED INSERT)
   - Atomic upsert — no DELETE step, no window for concurrent duplicates

5. UPDATE WATERMARK
   - Set watermark_value = MAX({incremental_column}) from extracted data
   - Update status = 'success', last_success_at = NOW()

6. CLEANUP
   - TRUNCATE local NDJSON file
   - Log batch completion
```

**Dedup guarantee:** Use staging table + MERGE pattern:
1. `CREATE TEMP TABLE stg_{table} AS SELECT * FROM target WHERE 1=0` (no constraints)
2. Bulk load source data into staging
3. `MERGE INTO target USING (SELECT ... ROW_NUMBER() OVER (PARTITION BY pk ORDER BY incremental_col DESC NULLS LAST) WHERE rn = 1) ON pk WHEN MATCHED UPDATE / WHEN NOT MATCHED INSERT`

### Error Handling

```
ANY STEP FAILS:
    - UPDATE metadata.pipeline_watermarks SET status = 'failed', error_message = {error_details}
    - Log full stack trace
    - Re-raise exception (Dagster marks run as failed, triggers retry)

NEXT RUN:
    - Starts from last successful watermark
    - No duplicate data (watermark + upsert logic)
```

---

## Implementation Phases

### Phase 1: Watermark Infrastructure
- [ ] Create `metadata` schema in warehouse
- [ ] Create `metadata.pipeline_watermarks` table
- [ ] Create helper functions: `get_watermark()`, `update_watermark()`, `set_status()`

### Phase 2: Auto-Detection Engine
- [ ] Build metadata inspection functions
- [ ] Implement `auto_detect_strategy()` function

### Phase 3: Universal Extraction Framework (Pattern Library)
- [ ] Database connector factory (Postgres, MySQL, etc.)
- [ ] API client helpers (REST, pagination, auth)
- [ ] NDJSON file writers, data type conversion utilities

### Phase 4: Universal Load Utilities
- [ ] Staging table + MERGE upsert logic
- [ ] Handle `inserted_at` / `updated_at` timestamps correctly

### Phase 5: Per-Source Pipeline Scripts
- [ ] For each source, adapt extraction patterns
- [ ] Add scripts to the **existing** source directory

### Phase 6: Initial Validation (Small Sample)
- [ ] Run with LIMIT 100 or use Step 1 sample for APIs
- [ ] Verify NULL column integrity against source

### Phase 7: Full Sync
- [ ] Remove LIMIT, run full extraction
- [ ] Monitor watermark progression, verify row counts

### Phase 8: SILVER/GOLD/PLATINUM Layers
- [ ] Design SQL / dbt transformations at each layer
- [ ] Use same watermark system for each layer

---

## Handoff to Step 3 (Dagster)

When the pipeline is complete (DDL, load, watermarks, validation, full sync), use **[3. Universal Dagster Architecture](3_universal_dagster_architecture.md)** (Step 3) to register assets, configure resources and IO managers, set schedules, and set up asset checks.

---

## Key Principles

1. **Pattern-based, not rigid:** Extraction is a framework of patterns AI adapts
2. **Source-system watermarks:** Track high-water mark from SOURCE data, not script run time
3. **Unified watermarking:** Single table tracks all 4 layers
4. **Idempotent:** Staging table + MERGE + watermark = safe reruns, no duplicates
5. **Auditable:** Timestamps (`inserted_at`/`updated_at`) and status tracking built-in
6. **4-layer separation:** RAW → SILVER → GOLD → PLATINUM

---

**Last Updated:** 2026-02-09
**Document 2 of 3.** No overlap with 1 or 3: this doc = pipeline only (DDL, load, watermarks, validation, full sync, layers). Connection/first sample = Step 1. Assets/schedules = Step 3.
