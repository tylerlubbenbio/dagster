# Snowflake Activation Design — bio-dagster-dbt

**Date:** 2026-03-18
**Status:** Approved

---

## Overview

Activate the `dagster_template/` framework for Snowflake, merge it into `dagster/`, wire all 14 existing connections as Dagster pipelines, and configure everything to target a new `BIO` database in Snowflake.

## Snowflake Target

- **Account:** vab13150
- **User:** TYLERLUBBEN
- **Role:** ACCOUNTADMIN
- **Warehouse:** COMPUTE_WH
- **Database:** BIO (new — to be created)
- **Auth:** Password
- **Case sensitivity:** Snowflake stores unquoted identifiers as UPPERCASE. All schema/table names in YAML configs, Python code, and DDL will use unquoted identifiers (resolves to uppercase internally). When querying `information_schema`, use `.upper()` on schema/table names.

## Database Structure

```
BIO (database)
├── METADATA                        — pipeline_watermarks table
├── RAW_KLAVIYO                     — Klaviyo API
├── RAW_META                        — Meta Ads
├── RAW_GOOGLE_ADS_GALLANT_SETO     — Google Ads (Gallant Seto account)
├── RAW_GOOGLE_ADS_NOOT             — Google Ads (Noot account)
├── RAW_GA4                         — Google Analytics 4 (both properties)
├── RAW_GTM                         — Google Tag Manager
├── RAW_AMAZON_ADS                  — Amazon Ads
├── RAW_AMAZON_SELLING_PARTNER      — Amazon Selling Partner
├── RAW_TIKTOK_ADS                  — TikTok Ads
├── RAW_PACVUEDSP                   — PacvueDSP
├── RAW_REFERSION                   — Refersion
├── RAW_TRIPLE_WHALE                — Triple Whale
├── RAW_MYSQL_DOCK                  — MySQL Dock (prod)
├── RAW_MONGO_GOLDLANTERN           — MongoDB Goldlantern (prod)
├── STAGING_DEV                     — dbt staging (dev target)
├── STAGING                         — dbt staging (prod target)
├── CORE                            — dbt dims/facts
├── ANALYTICS                       — dbt OBTs
└── REPORT                          — dbt aggregations
```

(Snowflake stores these as uppercase internally; YAML configs may use lowercase — both work since Snowflake is case-insensitive for unquoted identifiers.)

## Dagster Directory (Post-Merge)

```
dagster/
├── definitions.py                  — Entry point (merges ingestion + transformation + systems)
├── definitions_ingestion_only.py   — Ingestion-only mode (no dbt)
├── asset_factory.py                — YAML-driven asset generator (default load_method → stage_copy)
├── resources.py                    — Snowflake WarehouseResource, WatermarkResource (no S3/boto3)
├── io_managers.py                  — Snowflake IO: MERGE, PUT + COPY INTO (internal stages, no S3)
├── env_config.py                   — dev/integration/prod environment config
├── field_transforms.py             — Field mapping transforms
├── dbt_jobs.py                     — dbt source freshness job
│
├── ingestion/
│   ├── definitions.py              — Ingestion layer definition builder
│   ├── assets.py, jobs.py, schedules.py, sensors.py, resources.py
│   └── raw/
│       ├── metadata/DDL/           — Watermark schema DDL (Snowflake)
│       ├── api_klaviyo/            — config.yaml + extractor.py + ddl/
│       ├── api_meta/
│       ├── api_google_ads_gallant_seto/
│       ├── api_google_ads_noot/
│       ├── api_ga4/
│       ├── api_gtm/
│       ├── api_amazon_ads/
│       ├── api_amazon_selling_partner/
│       ├── api_tiktok_ads/
│       ├── api_pacvuedsp/
│       ├── api_refersion/
│       ├── api_triple_whale/
│       ├── internal_mysql_dock/
│       └── internal_mongo_goldlantern/
│
├── transformation/
│   ├── definitions.py, assets.py, jobs.py, schedules.py, sensors.py, resources.py
│
├── systems/
│   ├── definitions.py, assets.py, jobs.py, schedules.py
│
├── dbt/
│   ├── dbt_project.yml             — project: bio_dagster_dbt_analytics
│   ├── profiles.yml                — Snowflake targets (dev/integration/prod)
│   ├── packages.yml
│   ├── .gitignore
│   ├── macros/
│   │   └── generate_schema_name.sql — Appends _dev in non-prod targets
│   └── models/
│       ├── sources.yml             — Raw source definitions for all 14 sources
│       └── core/
│           └── dim_date.sql        — Remove DISTKEY/SORTKEY, use Snowflake date functions
│
└── deployment/
    ├── dagster.yaml                — (moved from existing dagster/)
    ├── workspace.yaml              — (moved from existing dagster/)
    ├── Dockerfile_dagster          — (moved from existing dagster/)
    ├── Dockerfile_user_code        — (moved, remove libpq-dev, uncomment dbt-snowflake)
    ├── nginx-dagster.example.conf  — (moved from existing dagster/)
    ├── nginx-dagster-bootstrap.conf
    └── values.yaml                 — Helm chart (remove AWS/S3/ECR references)
```

## File Changes

### .env

```
# Snowflake target warehouse
SNOWFLAKE_ACCOUNT=vab13150
TARGET_DATABASE=BIO
TARGET_USERNAME=TYLERLUBBEN
TARGET_PASSWORD=<from_user_credentials>
SNOWFLAKE_ROLE=ACCOUNTADMIN
SNOWFLAKE_WAREHOUSE=COMPUTE_WH

# dbt
DBT_TARGET=dev

# Slack (placeholder)
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token

# === API CREDENTIALS (placeholders — fill in per source) ===
KLAVIYO_API_KEY=
META_ACCESS_TOKEN=
META_AD_ACCOUNT_ID=
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_GALLANT_SETO_CUSTOMER_ID=
GOOGLE_ADS_GALLANT_SETO_REFRESH_TOKEN=
GOOGLE_ADS_NOOT_CUSTOMER_ID=
GOOGLE_ADS_NOOT_REFRESH_TOKEN=
GA4_CREDENTIALS_JSON=
GA4_PROPERTY_ID_1=270052061
GA4_PROPERTY_ID_2=345174638
GTM_CREDENTIALS_JSON=
AMAZON_ADS_CLIENT_ID=
AMAZON_ADS_CLIENT_SECRET=
AMAZON_ADS_REFRESH_TOKEN=
AMAZON_SP_CLIENT_ID=
AMAZON_SP_CLIENT_SECRET=
AMAZON_SP_REFRESH_TOKEN=
TIKTOK_ADS_ACCESS_TOKEN=
TIKTOK_ADS_ADVERTISER_ID=
PACVUEDSP_API_KEY=
REFERSION_API_KEY=
REFERSION_API_SECRET=
TRIPLE_WHALE_API_KEY=

# === SOURCE DATABASE CREDENTIALS ===
MYSQL_DOCK_HOST=
MYSQL_DOCK_PORT=3306
MYSQL_DOCK_USERNAME=
MYSQL_DOCK_PASSWORD=
MYSQL_DOCK_DATABASE=dock_prod
MYSQL_DOCK_SSL=true
MYSQL_DOCK_SSL_VERIFY=true
MONGO_GOLDLANTERN_URI=
MONGO_GOLDLANTERN_DATABASE=goldlantern
```

### config.json

Remove: `s3_default` block, `databases` block, `target.port`.
Add: `target.type: snowflake`, `target.account`, `target.database`, `target.warehouse`, `target.role`, `sources` block.

```json
{
  "_doc": "Structure and non-secret values only. Secrets injected from .env via load_config().",
  "dagster": {
    "env": "dev",
    "ui_base_url": "http://localhost:3000"
  },
  "target": {
    "type": "snowflake",
    "account": "vab13150",
    "database": "BIO",
    "warehouse": "COMPUTE_WH",
    "role": "ACCOUNTADMIN"
  },
  "sources": {
    "klaviyo": {
      "type": "api",
      "base_url": "https://a.klaviyo.com/api"
    },
    "meta": {
      "type": "api"
    },
    "google_ads_gallant_seto": {
      "type": "api"
    },
    "google_ads_noot": {
      "type": "api"
    },
    "ga4": {
      "type": "api",
      "properties": ["270052061", "345174638"]
    },
    "gtm": {
      "type": "api"
    },
    "amazon_ads": {
      "type": "api"
    },
    "amazon_selling_partner": {
      "type": "api"
    },
    "tiktok_ads": {
      "type": "api"
    },
    "pacvuedsp": {
      "type": "api"
    },
    "refersion": {
      "type": "api"
    },
    "triple_whale": {
      "type": "api"
    },
    "mysql_dock": {
      "type": "mysql",
      "host": "",
      "port": 3306,
      "database": "dock_prod"
    },
    "mongo_goldlantern": {
      "type": "mongodb",
      "database": "goldlantern"
    }
  }
}
```

### load_config.py

Full _SECRETS mapping:

```python
_SECRETS = [
    # Snowflake target warehouse
    (("target", "account"), "SNOWFLAKE_ACCOUNT"),
    (("target", "database"), "TARGET_DATABASE"),
    (("target", "username"), "TARGET_USERNAME"),
    (("target", "password"), "TARGET_PASSWORD"),
    (("target", "role"), "SNOWFLAKE_ROLE"),
    (("target", "warehouse"), "SNOWFLAKE_WAREHOUSE"),
    # MySQL Dock source
    (("sources", "mysql_dock", "host"), "MYSQL_DOCK_HOST"),
    (("sources", "mysql_dock", "username"), "MYSQL_DOCK_USERNAME"),
    (("sources", "mysql_dock", "password"), "MYSQL_DOCK_PASSWORD"),
    # MongoDB Goldlantern source
    (("sources", "mongo_goldlantern", "uri"), "MONGO_GOLDLANTERN_URI"),
    # API sources
    (("sources", "klaviyo", "api_key"), "KLAVIYO_API_KEY"),
    (("sources", "meta", "access_token"), "META_ACCESS_TOKEN"),
    (("sources", "meta", "ad_account_id"), "META_AD_ACCOUNT_ID"),
    (("sources", "google_ads_gallant_seto", "developer_token"), "GOOGLE_ADS_DEVELOPER_TOKEN"),
    (("sources", "google_ads_gallant_seto", "customer_id"), "GOOGLE_ADS_GALLANT_SETO_CUSTOMER_ID"),
    (("sources", "google_ads_gallant_seto", "refresh_token"), "GOOGLE_ADS_GALLANT_SETO_REFRESH_TOKEN"),
    (("sources", "google_ads_noot", "developer_token"), "GOOGLE_ADS_DEVELOPER_TOKEN"),
    (("sources", "google_ads_noot", "customer_id"), "GOOGLE_ADS_NOOT_CUSTOMER_ID"),
    (("sources", "google_ads_noot", "refresh_token"), "GOOGLE_ADS_NOOT_REFRESH_TOKEN"),
    (("sources", "ga4", "credentials_json"), "GA4_CREDENTIALS_JSON"),
    (("sources", "gtm", "credentials_json"), "GTM_CREDENTIALS_JSON"),
    (("sources", "amazon_ads", "client_id"), "AMAZON_ADS_CLIENT_ID"),
    (("sources", "amazon_ads", "client_secret"), "AMAZON_ADS_CLIENT_SECRET"),
    (("sources", "amazon_ads", "refresh_token"), "AMAZON_ADS_REFRESH_TOKEN"),
    (("sources", "amazon_selling_partner", "client_id"), "AMAZON_SP_CLIENT_ID"),
    (("sources", "amazon_selling_partner", "client_secret"), "AMAZON_SP_CLIENT_SECRET"),
    (("sources", "amazon_selling_partner", "refresh_token"), "AMAZON_SP_REFRESH_TOKEN"),
    (("sources", "tiktok_ads", "access_token"), "TIKTOK_ADS_ACCESS_TOKEN"),
    (("sources", "tiktok_ads", "advertiser_id"), "TIKTOK_ADS_ADVERTISER_ID"),
    (("sources", "pacvuedsp", "api_key"), "PACVUEDSP_API_KEY"),
    (("sources", "refersion", "api_key"), "REFERSION_API_KEY"),
    (("sources", "refersion", "api_secret"), "REFERSION_API_SECRET"),
    (("sources", "triple_whale", "api_key"), "TRIPLE_WHALE_API_KEY"),
]
```

Remove: `TARGET_HOST` mapping (Snowflake uses account identifier, not host).

### requirements.txt

Add:
- `dbt-snowflake` (Snowflake dbt adapter)
- `snowflake-connector-python` (Snowflake driver)
- `pymysql` (MySQL Dock source)
- `pymongo` (MongoDB Goldlantern source)

Remove:
- `psycopg2-binary` (not needed — Snowflake only)
- `boto3` (no S3/AWS)

### profiles.yml (Snowflake)

Three targets (dev/integration/prod) using env vars:
- account: SNOWFLAKE_ACCOUNT
- user: TARGET_USERNAME
- password: TARGET_PASSWORD
- database: BIO
- warehouse: COMPUTE_WH
- role: ACCOUNTADMIN
- dev schema: dev_staging
- integration schema: staging_dev
- prod schema: staging

### dbt_project.yml

- name: bio_dagster_dbt_analytics
- profile: default
- Model materialization: staging=view, core=table, analytics=table, report=table
- Update `models:` config key from `{{project_name}}_analytics` to `bio_dagster_dbt_analytics`

### Snowflake Adaptations

**io_managers.py:**
- Replace `psycopg2` with `snowflake.connector`
- Replace `psycopg2.sql.Identifier` and `psycopg2.sql.Placeholder` with double-quoted string formatting and `%s` placeholders directly
- MERGE syntax: use target aliases (`MERGE INTO schema.table AS tgt`)
- Bulk load: PUT file to internal stage + COPY INTO (replaces S3 copy path entirely)
- Remove all S3-related code paths, `s3` from `required_resource_keys`, and `s3_resource` from `__init__`
- Use `VARIANT` for JSON columns
- Use `TIMESTAMP_NTZ` for timestamps
- Use `CREATE OR REPLACE TEMPORARY TABLE` for staging tables (Snowflake-specific)
- Snowflake `cursor()` context manager: verify all `with conn.cursor() as cur:` patterns work; add explicit `cur.close()` where needed

**resources.py:**
- WarehouseResource: `snowflake.connector.connect()` with account/user/password/role/warehouse/database
- Remove `S3Resource` class entirely
- Remove `boto3` import
- Replace `psycopg2` import with `snowflake.connector`
- Add per-source API/DB resources for all 14 connections
- WatermarkResource: queries use `%s` paramstyle (compatible with snowflake-connector-python)
- When querying `information_schema`, use `.upper()` on schema/table name values

**asset_factory.py:**
- Change default `load_method` from `s3_copy` to `stage_copy`
- Remove `s3_bucket_config` references

**systems/assets.py:**
- Replace Postgres system catalog queries (`pg_tables`, `pg_views`) with Snowflake `information_schema` queries
- Update `EXCLUDED_SCHEMAS` to Snowflake's `INFORMATION_SCHEMA`
- Adapt grant SQL: `GRANT USAGE ON SCHEMA`, `GRANT SELECT ON ALL TABLES IN SCHEMA`

**DDL scripts (all under ingestion/raw/*/ddl/):**
- Replace `psycopg2` connections with `snowflake.connector`
- Remove `SERIAL PRIMARY KEY`, use Snowflake DDL conventions
- Use `VARIANT` instead of `JSONB`, `TIMESTAMP_NTZ` instead of `TIMESTAMP`
- No `DISTKEY`/`SORTKEY`

**dbt/models/core/dim_date.sql:**
- Remove `sort='date_day'` and `dist='all'` from config
- Convert `::date` casts to Snowflake-compatible syntax

**Dockerfile_user_code (in deployment/):**
- Remove `libpq-dev` (Postgres C library)
- Uncomment `dbt-snowflake` adapter line

**deployment/values.yaml:**
- Remove AWS/ECR/S3 references (no cloud staging)

### Watermark DDL (Snowflake)

Matches template's full schema from `create_metadata_schema.py`:

```sql
CREATE DATABASE IF NOT EXISTS BIO;
CREATE SCHEMA IF NOT EXISTS BIO.METADATA;
CREATE TABLE IF NOT EXISTS BIO.METADATA.PIPELINE_WATERMARKS (
    layer VARCHAR(50),
    target_schema VARCHAR(100),
    target_table VARCHAR(100),
    source_system VARCHAR(100),
    source_object VARCHAR(100),
    watermark_column VARCHAR(100),
    watermark_value VARCHAR(500),
    watermark_type VARCHAR(50) DEFAULT 'timestamp',
    last_run_at TIMESTAMP_NTZ,
    last_success_at TIMESTAMP_NTZ,
    rows_processed BIGINT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
ALTER TABLE BIO.METADATA.PIPELINE_WATERMARKS
    ADD PRIMARY KEY (layer, target_schema, target_table);
```

### Cleanup

After merge:
- Delete `dagster_template/` directory entirely
- Existing `dagster/README.md` removed (no markdown files per project rules)

## Out of Scope

- Actually running pipelines / extracting data (that's implementation)
- Filling in real API credentials (placeholders only, except Snowflake)
- Building dbt models (just the project skeleton)
- Creating the BIO database in Snowflake (DDL script provided, run during implementation)
