# Snowflake Activation Instructions

> These instructions are read by the `/activate` command to configure this project for Snowflake.

## dbt Configuration
- **Adapter:** `dbt-snowflake`
- **profiles.yml type:** `snowflake`
- **Requirements:** Add `dbt-snowflake` and `snowflake-connector-python` to `requirements.txt`

### profiles.yml Template (Snowflake-specific)
Snowflake requires different connection params than Postgres/Redshift:

```yaml
default:
  target: "{{ env_var('DBT_TARGET', 'dev') }}"
  outputs:
    dev:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('TARGET_USERNAME') }}"
      password: "{{ env_var('TARGET_PASSWORD') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE', 'TRANSFORMER') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE', 'TRANSFORMING') }}"
      database: "{{ env_var('TARGET_DATABASE') }}"
      schema: dev_staging
      threads: 4
    integration:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('TARGET_USERNAME') }}"
      password: "{{ env_var('TARGET_PASSWORD') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE', 'TRANSFORMER') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE', 'TRANSFORMING') }}"
      database: "{{ env_var('TARGET_DATABASE') }}"
      schema: staging_dev
      threads: 4
    prod:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('TARGET_USERNAME') }}"
      password: "{{ env_var('TARGET_PASSWORD') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE', 'TRANSFORMER') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE', 'TRANSFORMING') }}"
      database: "{{ env_var('TARGET_DATABASE') }}"
      schema: staging
      threads: 4
```

## IO Manager Changes (`dagster/io_managers.py`)

### Connection: Use snowflake-connector-python
Replace psycopg2 connection with Snowflake connector:

```python
import snowflake.connector

class WarehouseResource(ConfigurableResource):
    def get_connection(self):
        target = self._get_target()
        return snowflake.connector.connect(
            account=target["account"],
            user=target["username"],
            password=target["password"],
            database=target["database"],
            warehouse=target.get("warehouse", "COMPUTE_WH"),
            role=target.get("role", "TRANSFORMER"),
        )
```

### Upsert Pattern: MERGE (with target aliases — unlike Redshift)
Snowflake MERGE is similar to Redshift but SUPPORTS target aliases:

```sql
MERGE INTO schema.table AS tgt
USING (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY pk ORDER BY updated_at DESC NULLS LAST) AS rn
    FROM stg_table
  ) WHERE rn = 1
) AS src ON tgt.pk = src.pk
WHEN MATCHED THEN UPDATE SET tgt.col2 = src.col2
WHEN NOT MATCHED THEN INSERT (col1, col2) VALUES (src.col1, src.col2);
```

Update `_build_merge_sql()` to use aliases (add `AS tgt` to target, use `tgt.col = src.col` in ON clause).

### Bulk Load: PUT + COPY INTO
Replace `_handle_s3_copy()` with Snowflake stage loading:

**Option A: Internal Stage (simplest)**
```python
def _handle_bulk_load(self, context, cur, records, meta, schema, table):
    """Snowflake bulk load via internal stage."""
    # Write NDJSON to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ndjson', delete=False) as f:
        for record in records:
            f.write(json.dumps(record, default=str) + "\n")
        tmp_path = f.name

    stage_name = f"@%{table}"  # Table stage
    cur.execute(f"PUT 'file://{tmp_path}' {stage_name} AUTO_COMPRESS=TRUE")

    col_list = ", ".join(f'"{c}"' for c in records[0].keys())
    cur.execute(f"""
        COPY INTO "{schema}"."{table}" ({col_list})
        FROM {stage_name}
        FILE_FORMAT = (TYPE = JSON)
        MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
    """)
    os.unlink(tmp_path)
```

**Option B: External S3 Stage**
If you have an S3 bucket configured, upload NDJSON to S3 then COPY INTO from the external stage.

### No stl_load_errors
Snowflake uses `COPY_HISTORY()` function or `VALIDATE()` for load error inspection:
```sql
SELECT * FROM TABLE(VALIDATE(table_name, JOB_ID => '_last'))
```

## DDL Differences
- **No DISTKEY/SORTKEY** — Snowflake uses automatic micro-partitioning
- **`VARIANT`** instead of `SUPER` for JSON columns
- **`CLUSTER BY (col)`** for clustering (optional, rarely needed)
- Snowflake is case-insensitive by default but stores identifiers as UPPERCASE — use quoted identifiers for mixed-case

Example DDL:
```sql
CREATE TABLE IF NOT EXISTS raw_example.example_table (
    id VARCHAR(255),
    name VARCHAR(500),
    metadata VARIANT,
    updated_at TIMESTAMP_NTZ,
    inserted_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
```

## resources.py Changes
- Use `snowflake-connector-python` instead of `psycopg2`
- Connection params: account, user, password, role, warehouse, database
- `psycopg2.sql` module NOT available — use f-strings with proper quoting or Snowflake's parameter binding

**IMPORTANT:** The IO manager uses `psycopg2.sql.Identifier` for SQL quoting throughout. For Snowflake, you'll need to replace these with simple string formatting using double-quoted identifiers, or create a compatibility wrapper.

## .env Additions
```
SNOWFLAKE_ACCOUNT=your_account.region
SNOWFLAKE_ROLE=TRANSFORMER
SNOWFLAKE_WAREHOUSE=TRANSFORMING
```

## config.json Changes
```json
{
  "target": {
    "type": "snowflake",
    "account": "",
    "warehouse": "TRANSFORMING",
    "role": "TRANSFORMER"
  }
}
```

## Watermark Table DDL
```sql
CREATE SCHEMA IF NOT EXISTS metadata;
CREATE TABLE IF NOT EXISTS metadata.pipeline_watermarks (
    layer VARCHAR(50),
    target_schema VARCHAR(100),
    target_table VARCHAR(100),
    watermark_value VARCHAR(255),
    rows_processed INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    last_run_at TIMESTAMP_NTZ,
    last_success_at TIMESTAMP_NTZ,
    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
-- Snowflake doesn't support composite PRIMARY KEY in CREATE TABLE — add it separately:
ALTER TABLE metadata.pipeline_watermarks ADD PRIMARY KEY (layer, target_schema, target_table);
```

## Rules to Add to RULES.md
- Snowflake MERGE supports target aliases (`MERGE INTO target AS tgt`) — unlike Redshift
- VARIANT columns: access nested fields with `:` notation (e.g., `col:field::string`)
- `QUALIFY ROW_NUMBER() OVER (...)` works in Snowflake (Redshift/Postgres need subquery)
- Snowflake `COPY INTO` requires a stage (internal via PUT, or external S3/GCS/Azure)
- `psycopg2.sql` is NOT available — replace with string formatting + proper identifier quoting
- Snowflake stores unquoted identifiers as UPPERCASE — always use double-quoted identifiers for lowercase column names
- Use `TIMESTAMP_NTZ` (no timezone) for consistency with UTC-based pipelines

## Additional Follow-Up Questions
- What is your Snowflake account identifier? (e.g., `xy12345.us-east-1`)
- What role should dbt and Dagster use? (e.g., TRANSFORMER, SYSADMIN)
- What warehouse for transformations? (e.g., TRANSFORMING, ETL_WH)
- What warehouse for loading? (same or different from transform warehouse?)
- Do you have an external stage set up for S3/GCS?
- What Snowflake edition? (Standard, Enterprise, Business Critical)
- Key pair authentication or password?
