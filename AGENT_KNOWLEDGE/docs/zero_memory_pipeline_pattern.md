# Zero-Memory Pipeline Pattern + Dedup Guarantee

**MANDATORY pattern for ALL data pipelines (API and Database sources).**

## Core Principles

1. **NEVER hold data in memory** — stream to NDJSON file, then bulk load to the warehouse
2. **Duplicate PKs are structurally impossible** — every load uses a staging table with ROW_NUMBER dedup

## Why This Pattern

- Handles any table size (10 rows or 24M+ rows)
- Preserves SUPER/JSON columns (JSON stays as JSON, not double-encoded strings)
- Prevents duplicate PKs regardless of what source sends — including concurrent runs
- Fast bulk loading (S3 COPY or equivalent is 10-100x faster than row-by-row INSERT)
- Crash-safe (watermarks advance only after successful commit)

## Load Path: NDJSON → S3 → Warehouse (7 Steps)

All `s3_copy` assets flow through `dagster/io_managers.py` → `_handle_ndjson_file()`:

```
Extractor
  └─► _LOCAL_FILES/{source}/{table}_{ts}.ndjson   (stream write, never accumulates rows)
         └─► S3 upload (single file, upload_ndjson_file())
                └─► CREATE TEMP TABLE stg_{table} AS SELECT * FROM target WHERE 1=0
                       └─► COPY from S3 into stg_{table}     ← source duplicates land here
                              └─► MERGE INTO target
                                  USING (SELECT *, ROW_NUMBER() OVER
                                        (PARTITION BY pk ORDER BY incremental_col DESC NULLS LAST) rn
                                        FROM stg_{table}) WHERE rn = 1
                                  WHEN MATCHED THEN UPDATE SET ...
                                  WHEN NOT MATCHED THEN INSERT ...
```

The staging table ensures exactly one row per PK reaches the target — regardless of what the source sent.

---

## Extractor Contract

Custom extractors (`custom_extractor: true` in config.yaml) must:
- Return **file path string** (never a list)
- Write one JSON record per line to `_LOCAL_FILES/{source}/{table}_{timestamp}.ndjson`
- Never accumulate rows in memory

```python
def extract(context, from_date: str, to_date: str, asset_config: dict) -> str:
    output_file = output_dir / f"{table}_{timestamp}.ndjson"
    with open(output_file, "w", encoding="utf-8") as f:
        for batch in source.fetch_pages(from_date):        # API pages or fetchmany(1000)
            for record in batch:
                f.write(json.dumps(record, default=str) + "\n")
    return str(output_file)
```

**DB sources:** Use server-side cursors + `fetchmany(1000)` — never `fetchall()`
**API sources:** Write each page directly to file as it arrives
**Streaming sources (e.g. DynamoDB Streams, Kinesis):** Use TRIM_HORIZON + client-side timestamp filter

---

## IO Manager: `_handle_ndjson_file()` (actual 7-step implementation)

```
1. Scan NDJSON once: record column names + max(incremental_col) for watermark
   → zero memory: only 2 scalar values tracked, never accumulates rows
2. upload_ndjson_file() → S3 (single file upload, no batching)
3. CREATE TEMP TABLE stg_{table} AS SELECT * FROM {schema}.{table} WHERE 1=0
   → copies column names/types, NO constraints (fully nullable — COPY won't fail on missing cols)
   → NOTE: Some warehouses do NOT support LIKE ... EXCLUDING CONSTRAINTS — use AS SELECT instead
3b. Query information_schema.columns for target table; compute safe_columns = target_cols ∩ ndjson_cols
    → NDJSON cols not in target: silently ignored (schema drift protection)
    → target cols not in NDJSON: excluded from MERGE (prevents NOT NULL column errors)
4. COPY {stg_table} ({safe_columns}) FROM {s3_path} ... FORMAT AS JSON 'auto' TIMEFORMAT 'auto'
5. MERGE INTO {schema}.{table}
   USING (SELECT {safe_cols} FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY pk ORDER BY incremental_col DESC) rn FROM stg) WHERE rn = 1) src
   ON target.pk = src.pk
   WHEN MATCHED THEN UPDATE SET non_pk_col1 = src.non_pk_col1, ...
   WHEN NOT MATCHED THEN INSERT ({safe_cols}) VALUES (src.col1, ...)
   → Atomic upsert: UPDATE existing rows in place, INSERT new rows
   → No DELETE step — no window for concurrent runs to insert duplicates
   → For full_refresh: TRUNCATE + INSERT instead (target is empty, MERGE unnecessary)
6. Watermark updated; local NDJSON file truncated
```

Key functions: `_build_dedup_insert_sql()`, `_handle_ndjson_file()` in `dagster/io_managers.py`

---

## `_handle_direct_insert()` (small tables)

For `list[dict]` loads (non-file path assets). Same staging + column intersection + MERGE pattern:
1. CREATE TEMP TABLE stg_{table} AS SELECT * FROM target WHERE 1=0
2. Query information_schema.columns; compute safe_columns = target_cols ∩ record_cols
3. INSERT all records row-by-row into staging (safe_columns only)
4. MERGE INTO target USING deduped_subquery_from_stg (same MERGE semantics as NDJSON path)

---

## Dedup SQL: `_build_dedup_insert_sql()`

- `incremental_col` set → `ORDER BY incremental_col DESC NULLS LAST` (newest wins)
- `incremental_col` None → `ORDER BY 1` (full_refresh — arbitrary tie-break)
- Composite PKs: `PARTITION BY col1, col2`
- Composite PK config (`"col1, col2"` string) is split with `.strip()` on each part — both load paths normalize correctly

Unit tests: `dagster/tests/test_io_manager_dedup.py`

---

## Config Requirements

```yaml
assets:
  - name: table_name
    target_schema: raw_source
    target_table: table_name
    primary_key: id                    # or "col1,col2" for composite PKs
    incremental_strategy: timestamp    # timestamp | full_refresh | incremental_id
    incremental_column: updated_at     # required for timestamp strategy
    load_method: s3_copy               # triggers _handle_ndjson_file path
    s3_bucket_config: s3_source        # key in config.json
    custom_extractor: true             # uses extractor.py:extract()
```

---

## JSON/Semi-Structured Columns

- Pass raw `dict`/`list` through — **never pre-serialize to string** (causes double-encoding, breaks native JSON types)
- Use warehouse-native JSON loading (e.g. `FORMAT AS JSON 'auto'` in Redshift COPY)
- Check your warehouse's JSON column type and size limits

---

## Rules

1. **NEVER `fetchall()`** — use `fetchmany(1000)` or server-side cursor
2. **NEVER accumulate rows** in a list across pages/batches
3. **ALWAYS return file path** from extractor, not records
4. **NEVER pre-serialize JSON columns** — pass raw dict/list
5. **MERGE handles upsert atomically** — no DELETE step, no dedup logic needed in extractors
6. **ALWAYS truncate local NDJSON** after successful load

## Reference Implementations

- `dagster/ingestion/raw/api_*/extractor.py` — API source (search + list endpoints)
- `dagster/ingestion/raw/internal_*/extractor.py` — DB source (server-side cursor)
