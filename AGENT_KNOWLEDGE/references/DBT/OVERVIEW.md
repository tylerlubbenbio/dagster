# dbt Reference — {{project_name}}_analytics

> **Note:** This document uses generic warehouse terminology. Run /activate to get database-specific instructions in _RESOURCES/{db}.md.

**Core instruction files:** `DBT_AI_BIBLE.md` (master AI instruction set), `STYLE_GUIDE.md` (SQL formatting, SQLFluff config, trailing comma standard), `BUSINESS_COLUMN_NAMING.md` (controlled column vocabulary with source-to-official mapping).

**RESOURCES directory contents:**
- `README.md` — Index of all templates and macros
- `dbt_project.yml`, `profiles.yml`, `packages.yml`, `.sqlfluff`, `.gitignore` — Config files
- `macros/generate_schema_name.sql` — Environment-aware schema routing (`dev_` prefix pattern)
- `macros/utils.sql` — Reusable utilities: clean_string, safe_cast_id, limit_dev_data, generate_md5_sk
- `models/staging/` — Templates: `_TEMPLATE_stg.sql`, `_TEMPLATE_schema.yml`, `_TEMPLATE_docs.md`
- `models/core/` — Templates: `_TEMPLATE_dim.sql`, `_TEMPLATE_fct.sql`, `dim_date.sql`, `_schema.yml`
- `models/analytics/` — Template: `_TEMPLATE_obt.sql`
- `models/report/` — Templates: `_TEMPLATE_report.sql`, `exposures.yml`
- `models/raw/` — Template: `_TEMPLATE_source.yml`
- `snapshots/` — Template: `_TEMPLATE_snapshot.sql`

**Sources:** Configure your own raw source schemas. Layer flow: raw -> staging -> core -> analytics -> report. Database-agnostic (Redshift/Snowflake/Postgres). **dbt Core 1.11+ required.**
