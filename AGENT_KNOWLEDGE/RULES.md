# Project Rules & Roadblocks

Rules discovered during development. Reference this to avoid repeating mistakes.

## Snowflake Rules
- Snowflake MERGE supports target aliases (`MERGE INTO target AS tgt`) — unlike Redshift
- VARIANT columns: access nested fields with `:` notation (e.g., `col:field::string`)
- `QUALIFY ROW_NUMBER() OVER (...)` works in Snowflake (Redshift/Postgres need subquery)
- Snowflake `COPY INTO` requires a stage (internal via PUT, or external S3/GCS/Azure)
- `psycopg2.sql` is NOT available — use f-strings with double-quoted identifiers via `_qi()` helper
- Snowflake stores unquoted identifiers as UPPERCASE — always use `.upper()` when querying information_schema
- Use `TIMESTAMP_NTZ` (no timezone) for consistency with UTC-based pipelines
- Target database is BIO — all schemas live under BIO
- No S3/AWS in this project — use Snowflake internal stages for bulk loading
- `MATCH_BY_COLUMN_NAME` CANNOT be combined with a column list in `COPY INTO` — remove column list when using it
- `CREATE TABLE IF NOT EXISTS` won't update existing tables — DROP first if schema changed
- Meta API returns all numbers as strings — add `to_int`/`to_float` transforms in field_mappings
- When creating DDL, use VARCHAR for ISO 8601 timestamp strings from APIs (not TIMESTAMP_NTZ) to avoid cast errors
- Always `USE SCHEMA` before creating temporary tables — Snowflake sessions may not have a default schema set, causing "Cannot perform CREATE TEMPTABLE" errors
- Snowflake PUT file paths on Windows: convert backslashes to forward slashes (`path.replace("\\", "/")`) — PUT interprets backslashes as escape chars, stripping them silently
- NDJSON record keys are lowercase but config incremental_column may be uppercase — use case-insensitive lookup for watermark scanning
- `_get_safe_columns` must return target table column names (uppercase) — not source record column names — to avoid `invalid identifier '"lowercase_col"'` errors in generated SQL
