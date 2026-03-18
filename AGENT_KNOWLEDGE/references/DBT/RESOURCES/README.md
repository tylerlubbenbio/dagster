# dbt Resources — {{project_name}}_analytics

## What's Inside

| File | Purpose |
|------|---------|
| **`DBT_AI_BIBLE.md`** | Master instruction set — feed to AI before generating any dbt code |
| **`STYLE_GUIDE.md`** | Technical structure rules (SQL formatting, trailing commas, warehouse linting) |
| **`BUSINESS_COLUMN_NAMING.md`** | Controlled column vocabulary — add project-specific entities here |
| **`dbt_project.yml`** | Project configuration with directory-level settings |
| **`profiles.yml`** | Multi-environment setup (dev + prod) with `dev_` prefix pattern |
| **`packages.yml`** | Pinned package dependencies |
| **`.sqlfluff`** | SQL dialect linting configuration |
| **`.gitignore`** | Standard dbt gitignore |

## Templates

| File | Location |
|------|----------|
| Staging model | `models/staging/_TEMPLATE_stg.sql` |
| Dimension model | `models/core/_TEMPLATE_dim.sql` |
| Fact model (incremental) | `models/core/_TEMPLATE_fct.sql` |
| Analytics OBT | `models/analytics/_TEMPLATE_obt.sql` |
| Report aggregation | `models/report/_TEMPLATE_report.sql` |
| Snapshot (SCD Type 2) | `snapshots/_TEMPLATE_snapshot.sql` |
| Source YAML | `models/raw/_TEMPLATE_source.yml` |
| Schema YAML | `models/staging/_TEMPLATE_schema.yml` |
| Docs block | `models/staging/_TEMPLATE_docs.md` |
| Exposures | `models/report/exposures.yml` |

## Pre-Built Models

| File | Purpose |
|------|---------|
| `models/core/dim_date.sql` | Calendar dimension using dbt_utils.date_spine |
| `models/core/_schema.yml` | Tests and documentation for dim_date |

## Macros

| File | Purpose |
|------|---------|
| `macros/generate_schema_name.sql` | **REQUIRED** — Routes models to correct schemas (`dev_` prefix in dev, exact schema in prod) |
| `macros/utils.sql` | Reusable utilities: clean_string, safe_cast_id, limit_dev_data, generate_md5_sk |

## How to Use

1. Feed `DBT_AI_BIBLE.md` + `STYLE_GUIDE.md` + `BUSINESS_COLUMN_NAMING.md` to your AI
2. Fill in `BUSINESS_COLUMN_NAMING.md` with new source column mappings as pipelines are added
3. Copy templates when creating new models — replace `{placeholders}` with actual values
4. Sources: configure per your project raw schemas
5. Run `dbt deps` to install packages
6. Run `dbt run --target dev` to build locally (schemas get `_dev` suffix)
7. Production runs via Dagster with `--target prod`
