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
