# Snowflake Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate the dagster_template framework for Snowflake, merge into dagster/, wire all 14 connections, targeting a new BIO database.

**Architecture:** Template-based Dagster+dbt project with YAML-driven asset factory. Ingestion writes to RAW_* schemas in BIO database via Snowflake internal stages (PUT + COPY INTO). dbt transforms through staging → core → analytics → report layers. All psycopg2/S3 code replaced with snowflake-connector-python.

**Tech Stack:** Python 3.11, Dagster 1.12, dbt-snowflake, snowflake-connector-python, pymysql, pymongo

**Spec:** `docs/superpowers/specs/2026-03-18-snowflake-activation-design.md`

---

## Task 1: Merge Template into dagster/ and Clean Up

**Files:**
- Move: `dagster/dagster.yaml` → `dagster/deployment/dagster.yaml`
- Move: `dagster/workspace.yaml` → `dagster/deployment/workspace.yaml`
- Move: `dagster/Dockerfile_dagster` → `dagster/deployment/Dockerfile_dagster`
- Move: `dagster/Dockerfile_user_code` → `dagster/deployment/Dockerfile_user_code`
- Move: `dagster/nginx-dagster.example.conf` → `dagster/deployment/nginx-dagster.example.conf`
- Move: `dagster/nginx-dagster-bootstrap.conf` → `dagster/deployment/nginx-dagster-bootstrap.conf`
- Delete: `dagster/README.md`
- Copy: all files from `dagster_template/` → `dagster/`
- Delete: `dagster_template/` directory

- [ ] **Step 1: Create deployment directory and move existing dagster files**

```bash
mkdir -p dagster/deployment_tmp
mv dagster/dagster.yaml dagster/deployment_tmp/
mv dagster/workspace.yaml dagster/deployment_tmp/
mv dagster/Dockerfile_dagster dagster/deployment_tmp/
mv dagster/Dockerfile_user_code dagster/deployment_tmp/
mv dagster/nginx-dagster.example.conf dagster/deployment_tmp/
mv dagster/nginx-dagster-bootstrap.conf dagster/deployment_tmp/
rm dagster/README.md
rm dagster/definitions.py
```

- [ ] **Step 2: Copy template into dagster/**

```bash
cp -r dagster_template/* dagster/
```

- [ ] **Step 3: Merge deployment files**

Move the saved deployment files into `dagster/deployment/` (template already has this dir with values.yaml):

```bash
mv dagster/deployment_tmp/* dagster/deployment/
rmdir dagster/deployment_tmp
```

- [ ] **Step 4: Remove example/template source directories**

```bash
rm -rf dagster/ingestion/raw/_example_api_source
rm -rf dagster/ingestion/raw/_example_db_source
rm -rf dagster/ingestion/raw/_TEMPLATE_source
```

- [ ] **Step 5: Delete dagster_template/**

```bash
rm -rf dagster_template/
```

- [ ] **Step 6: Verify directory structure**

```bash
ls dagster/
# Expected: definitions.py, definitions_ingestion_only.py, asset_factory.py, resources.py,
#           io_managers.py, env_config.py, field_transforms.py, dbt_jobs.py,
#           ingestion/, transformation/, systems/, dbt/, deployment/

ls dagster/deployment/
# Expected: dagster.yaml, workspace.yaml, Dockerfile_dagster, Dockerfile_user_code,
#           nginx-dagster.example.conf, nginx-dagster-bootstrap.conf, values.yaml
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "merge dagster_template into dagster/, move deployment files"
```

---

## Task 2: Update Config Files (.env, config.json, load_config.py)

**Files:**
- Modify: `.env`
- Modify: `config.json`
- Modify: `load_config.py`

- [ ] **Step 1: Update .env with Snowflake credentials and all source placeholders**

Replace the entire `.env` with:

```
# Snowflake target warehouse
SNOWFLAKE_ACCOUNT=vab13150
TARGET_DATABASE=BIO
TARGET_USERNAME=TYLERLUBBEN
TARGET_PASSWORD=Bioptimizers21!
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
GOOGLE_ADS_GALLANT_SETO_CLIENT_ID=
GOOGLE_ADS_GALLANT_SETO_CLIENT_SECRET=
GOOGLE_ADS_NOOT_CLIENT_ID=
GOOGLE_ADS_NOOT_CLIENT_SECRET=
GA4_CREDENTIALS_JSON=
GA4_PROPERTY_ID_1=270052061
GA4_PROPERTY_ID_2=345174638
GTM_CREDENTIALS_JSON=
AMAZON_ADS_CLIENT_ID=
AMAZON_ADS_CLIENT_SECRET=
AMAZON_ADS_REFRESH_TOKEN=
AMAZON_ADS_PROFILE_ID=
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

- [ ] **Step 2: Update config.json**

Replace entire `config.json` with:

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

- [ ] **Step 3: Update load_config.py with full secrets mapping**

Replace the `_SECRETS` list with:

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

- [ ] **Step 4: Verify .env is in .gitignore**

```bash
grep "^\.env$" .gitignore || echo ".env" >> .gitignore
```

.env contains real credentials — NEVER commit it.

- [ ] **Step 5: Commit (config.json and load_config.py only, NOT .env)**

```bash
git add config.json load_config.py .gitignore
git commit -m "configure config.json, load_config.py for Snowflake + all 14 sources"
```

---

## Task 3: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Add Snowflake + source DB packages. Remove Postgres + S3 packages:

```
# Python 3.11 only. Use .python-version or pyenv.
# Dagster core
dagster==1.12.14
dagster-webserver==1.12.14
dagster-graphql==1.12.14
dagster-postgres==0.28.14
dagster-k8s==0.28.14
dagster-slack==0.28.14

# dbt + Snowflake
dbt-snowflake>=1.7.0,<2.0.0
dagster-dbt==0.28.14

# Database drivers
snowflake-connector-python>=3.6.0,<4.0.0
pymysql>=1.1.0,<2.0.0
pymongo>=4.6.0,<5.0.0
SQLAlchemy==2.0.46

# API clients
requests==2.32.5

# Utilities
PyYAML==6.0.3
Jinja2==3.1.6
ruff>=0.8.0

# gRPC (Dagster user code server)
grpcio==1.78.0
grpcio-health-checking==1.78.0
```

Note: `dagster-postgres` is kept — it's for Dagster's internal metadata storage (dagster.yaml), not the target warehouse.

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "update requirements: add dbt-snowflake, snowflake-connector, pymysql, pymongo; remove psycopg2, boto3"
```

---

## Task 4: Rewrite resources.py for Snowflake

**Files:**
- Modify: `dagster/resources.py`

- [ ] **Step 1: Replace entire resources.py**

Key changes from template:
- `psycopg2` → `snowflake.connector`
- Remove `psycopg2.sql` — use f-strings with double-quoted identifiers
- Remove `S3Resource` and `boto3`
- Remove `ExampleApiResource`, `ExampleDbResource`
- `WarehouseResource.get_connection()` → snowflake.connector.connect(account, user, password, role, warehouse, database)
- `get_row_count()` / `get_column_stats()` / `get_sample_rows()` → use f-strings with `"{schema}"."{table}"` quoting
- `information_schema` queries → use `.upper()` on schema/table names
- `WatermarkResource` — SQL uses `%s` paramstyle (compatible with snowflake-connector-python, no changes needed to query strings)
- `get_all_resources()` → remove `"s3"` key

```python
"""
Shared Dagster resources: connections, API clients, config.

All resources use ConfigurableResource for proper Dagster integration.
Secrets come from .env via load_config(). No hardcoded credentials.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import snowflake.connector
import requests
from dagster import ConfigurableResource

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from load_config import load_config


def _qi(name: str) -> str:
    """Quote identifier for Snowflake SQL (double-quote)."""
    return f'"{name}"'


class WarehouseResource(ConfigurableResource):
    """Snowflake connection factory. Reads credentials from .env via load_config()."""

    def _get_target(self) -> dict:
        return load_config()["target"]

    def get_connection(self):
        target = self._get_target()
        return snowflake.connector.connect(
            account=target["account"],
            user=target["username"],
            password=target["password"],
            database=target["database"],
            warehouse=target.get("warehouse", "COMPUTE_WH"),
            role=target.get("role", "ACCOUNTADMIN"),
        )

    def execute(self, query, params=None):
        """Execute SQL. Returns rows if SELECT, else None."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute(query, params)
                if cur.description:
                    return cur.fetchall()
                return None
            finally:
                cur.close()
        finally:
            conn.close()

    def get_row_count(self, schema: str, table: str) -> int:
        q = f'SELECT COUNT(*) FROM {_qi(schema)}.{_qi(table)}'
        result = self.execute(q)
        return result[0][0] if result else 0

    def get_column_stats(self, schema: str, table: str) -> list[dict]:
        """Get column-level stats: name, type, null count, distinct count."""
        columns = self.execute(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s "
            "ORDER BY ordinal_position",
            (schema.upper(), table.upper()),
        )
        if not columns:
            return []

        tbl = f'{_qi(schema)}.{_qi(table)}'
        stats = []
        for col_name, col_type in columns:
            null_count = self.execute(
                f'SELECT COUNT(*) FROM {tbl} WHERE {_qi(col_name)} IS NULL'
            )
            distinct_count = self.execute(
                f'SELECT COUNT(DISTINCT {_qi(col_name)}) FROM {tbl}'
            )
            stats.append({
                "column": col_name,
                "type": col_type,
                "null_count": null_count[0][0] if null_count else 0,
                "distinct_count": distinct_count[0][0] if distinct_count else 0,
            })
        return stats

    def get_sample_rows(self, schema: str, table: str, limit: int = 5) -> list[dict]:
        """Get sample rows as list of dicts for metadata display."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute(
                    f'SELECT * FROM {_qi(schema)}.{_qi(table)} LIMIT %s',
                    (limit,),
                )
                if not cur.description:
                    return []
                col_names = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(col_names, row)) for row in rows]
            finally:
                cur.close()
        finally:
            conn.close()


class WatermarkResource(ConfigurableResource):
    """Read/update metadata.pipeline_watermarks via warehouse."""

    warehouse: WarehouseResource

    def get_watermark(self, layer: str, schema: str, table: str) -> str | None:
        rows = self.warehouse.execute(
            "SELECT watermark_value FROM metadata.pipeline_watermarks "
            "WHERE layer = %s AND target_schema = %s AND target_table = %s "
            "ORDER BY updated_at DESC LIMIT 1",
            (layer, schema, table),
        )
        return rows[0][0] if rows else None

    def _row_exists(self, layer: str, schema: str, table: str) -> bool:
        rows = self.warehouse.execute(
            "SELECT 1 FROM metadata.pipeline_watermarks "
            "WHERE layer = %s AND target_schema = %s AND target_table = %s LIMIT 1",
            (layer, schema, table),
        )
        return bool(rows)

    def update_watermark(
        self,
        layer: str,
        schema: str,
        table: str,
        value: str,
        rows_processed: int,
        status: str = "success",
    ):
        self.warehouse.execute(
            "DELETE FROM metadata.pipeline_watermarks "
            "WHERE layer = %s AND target_schema = %s AND target_table = %s",
            (layer, schema, table),
        )
        self.warehouse.execute(
            "INSERT INTO metadata.pipeline_watermarks "
            "(layer, target_schema, target_table, watermark_value, rows_processed, status, "
            "last_run_at, last_success_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())",
            (layer, schema, table, str(value), rows_processed, status),
        )

    def get_last_run_at(self, layer: str, schema: str, table: str) -> str | None:
        rows = self.warehouse.execute(
            "SELECT last_run_at FROM metadata.pipeline_watermarks "
            "WHERE layer = %s AND target_schema = %s AND target_table = %s "
            "ORDER BY updated_at DESC LIMIT 1",
            (layer, schema, table),
        )
        return str(rows[0][0]) if rows and rows[0][0] else None

    def mark_run_started(self, layer: str, schema: str, table: str):
        if self._row_exists(layer, schema, table):
            self.warehouse.execute(
                "UPDATE metadata.pipeline_watermarks "
                "SET last_run_at = CURRENT_TIMESTAMP(), updated_at = CURRENT_TIMESTAMP() "
                "WHERE layer = %s AND target_schema = %s AND target_table = %s",
                (layer, schema, table),
            )

    def set_status(
        self,
        layer: str,
        schema: str,
        table: str,
        status: str,
        error_message: str | None = None,
    ):
        err_truncated = error_message[:500] if error_message else None
        is_success = status in ("success", "no_new_data")
        if not self._row_exists(layer, schema, table):
            self.warehouse.execute(
                "INSERT INTO metadata.pipeline_watermarks "
                "(layer, target_schema, target_table, status, error_message, last_run_at, "
                "last_success_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP(), "
                "CASE WHEN %s THEN CURRENT_TIMESTAMP() ELSE NULL END, CURRENT_TIMESTAMP())",
                (layer, schema, table, status, err_truncated, is_success),
            )
        else:
            self.warehouse.execute(
                "UPDATE metadata.pipeline_watermarks "
                "SET status = %s, error_message = %s, last_run_at = CURRENT_TIMESTAMP(), "
                "last_success_at = CASE WHEN %s THEN CURRENT_TIMESTAMP() ELSE last_success_at END, "
                "updated_at = CURRENT_TIMESTAMP() "
                "WHERE layer = %s AND target_schema = %s AND target_table = %s",
                (status, err_truncated, is_success, layer, schema, table),
            )


def get_all_resources() -> dict:
    """Build the resources dict for Definitions."""
    warehouse = WarehouseResource()
    return {
        "warehouse": warehouse,
        "watermark": WatermarkResource(warehouse=warehouse),
        # Source resources added per-pipeline as needed
    }
```

- [ ] **Step 2: Verify file has no psycopg2, boto3, or S3 references**

```bash
grep -n "psycopg2\|boto3\|S3Resource" dagster/resources.py
# Expected: no output
```

- [ ] **Step 3: Commit**

```bash
git add dagster/resources.py
git commit -m "rewrite resources.py for Snowflake: snowflake.connector, remove S3/psycopg2"
```

---

## Task 5: Rewrite io_managers.py for Snowflake

**Files:**
- Modify: `dagster/io_managers.py`

This is the largest change. Complete replacement file below.

- [ ] **Step 1: Replace dagster/io_managers.py with this complete file**

```python
"""Warehouse IO Manager: handles persistence for all assets (Snowflake).

Two modes (set by asset's `load_method` metadata):
  - stage_copy:     records/file -> PUT to internal stage -> COPY INTO staging -> MERGE into target
  - direct_insert:  records -> staging table -> MERGE into target

All load paths use a staging table + MERGE pattern:
  1. COPY/INSERT all rows into TEMPORARY stg_{table} (no constraints, duplicates OK)
  2. MERGE INTO target AS tgt USING deduped_subquery_from_stg:
       WHEN MATCHED     -> UPDATE existing row in place
       WHEN NOT MATCHED -> INSERT new row
  Dedup within the staging batch uses ROW_NUMBER() before the MERGE.

full_refresh uses TRUNCATE + INSERT instead of MERGE.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from dagster import IOManager, InputContext, OutputContext, io_manager

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from load_config import load_config


def _qi(name: str) -> str:
    """Quote identifier for Snowflake SQL (double-quote)."""
    return f'"{name}"'


class WarehouseIOManager(IOManager):
    """Writes asset output (list[dict]) to Snowflake."""

    def __init__(self, warehouse_resource, watermark_resource):
        self._warehouse = warehouse_resource
        self._watermark = watermark_resource

    def _build_merge_sql(
        self,
        schema: str,
        table: str,
        staging_table: str,
        pk_cols: list,
        columns: list,
        incremental_col,
    ):
        """Build MERGE INTO target AS tgt USING deduped-staging SQL (Snowflake)."""
        col_list = ", ".join(_qi(c) for c in columns)
        pk_partition = ", ".join(_qi(c) for c in pk_cols)
        pk_set = set(pk_cols)
        non_pk_cols = [c for c in columns if c not in pk_set]

        if incremental_col:
            order_clause = f"ORDER BY {_qi(incremental_col)} DESC NULLS LAST"
        else:
            order_clause = "ORDER BY 1"

        target_ref = f'{_qi(schema)}.{_qi(table)}'

        on_parts = [f"tgt.{_qi(c)} = src.{_qi(c)}" for c in pk_cols]
        on_condition = " AND ".join(on_parts)

        insert_values = ", ".join(f"src.{_qi(c)}" for c in columns)

        if non_pk_cols:
            set_parts = [f"tgt.{_qi(c)} = src.{_qi(c)}" for c in non_pk_cols]
            matched_clause = f"WHEN MATCHED THEN UPDATE SET {', '.join(set_parts)} "
        else:
            matched_clause = ""

        return (
            f"MERGE INTO {target_ref} AS tgt "
            f"USING ("
            f"  SELECT {col_list} FROM ("
            f"    SELECT *, ROW_NUMBER() OVER (PARTITION BY {pk_partition} {order_clause}) AS rn"
            f"    FROM {_qi(staging_table)}"
            f"  ) sub WHERE rn = 1"
            f") src "
            f"ON {on_condition} "
            f"{matched_clause}"
            f"WHEN NOT MATCHED THEN INSERT ({col_list}) VALUES ({insert_values})"
        )

    def _build_insert_sql(
        self,
        schema: str,
        table: str,
        staging_table: str,
        pk_cols: list,
        columns: list,
        incremental_col,
    ):
        """Build INSERT INTO target SELECT deduped FROM staging SQL (for full_refresh after TRUNCATE)."""
        col_list = ", ".join(_qi(c) for c in columns)
        pk_partition = ", ".join(_qi(c) for c in pk_cols)

        if incremental_col:
            order_clause = f"ORDER BY {_qi(incremental_col)} DESC NULLS LAST"
        else:
            order_clause = "ORDER BY 1"

        return (
            f"INSERT INTO {_qi(schema)}.{_qi(table)} ({col_list}) "
            f"SELECT {col_list} FROM ("
            f"  SELECT *, ROW_NUMBER() OVER (PARTITION BY {pk_partition} {order_clause}) AS rn"
            f"  FROM {_qi(staging_table)}"
            f") sub WHERE rn = 1"
        )

    def _get_safe_columns(self, cur, schema, table, record_columns):
        """Intersect record columns with target table columns (in target order).
        Uses .upper() for information_schema queries (Snowflake stores unquoted as uppercase)."""
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s "
            "ORDER BY ordinal_position",
            (schema.upper(), table.upper()),
        )
        target_cols = [row[0] for row in cur.fetchall()]
        record_col_set = set(record_columns)
        # Match case-insensitively: target cols are uppercase, record cols may be lowercase
        safe_columns = []
        for tc in target_cols:
            if tc in record_col_set:
                safe_columns.append(tc)
            elif tc.lower() in record_col_set:
                safe_columns.append(tc.lower())
            elif tc.upper() in record_col_set:
                safe_columns.append(tc.upper())
        if not safe_columns:
            raise ValueError(
                f"No overlap between record columns and target {schema}.{table} columns. "
                f"record: {record_columns[:10]}, target: {target_cols[:10]}"
            )
        return safe_columns

    def handle_output(self, context: OutputContext, records):
        """Handle asset output - can be list[dict] or file path (str)."""
        if isinstance(records, str):
            if records.endswith(".ndjson"):
                return self._handle_ndjson_file(context, records)
            else:
                return self._handle_csv_file(context, records)

        if records is None or len(records) == 0:
            context.log.info("No records to write.")
            return

        meta = context.metadata or {}
        schema = meta.get("target_schema")
        table = meta.get("target_table")
        pk = meta.get("primary_key")
        load_method = meta.get("load_method", "direct_insert")
        layer = meta.get("layer", "raw")

        if not schema or not table or not pk:
            raise ValueError(
                f"Asset metadata must include target_schema, target_table, primary_key. Got: {meta}"
            )

        pk_cols = [c.strip() for c in pk.split(",")] if isinstance(pk, str) else pk
        incremental_col = meta.get("incremental_column")

        conn = self._warehouse.get_connection()
        try:
            cur = conn.cursor()
            try:
                incremental_strategy = meta.get("incremental_strategy", "")

                if incremental_strategy == "full_refresh":
                    cur.execute(f"TRUNCATE TABLE {_qi(schema)}.{_qi(table)}")
                    context.log.info(f"TRUNCATE {schema}.{table} (full_refresh)")

                if load_method == "stage_copy":
                    self._handle_stage_copy(context, cur, records, meta, schema, table)
                else:
                    self._handle_direct_insert(
                        context, cur, records, schema, table, pk_cols, incremental_col
                    )

                context.log.info(f"Committed {len(records)} records to {schema}.{table}")

                # Update watermark
                if incremental_col:
                    values = [r.get(incremental_col) for r in records if r.get(incremental_col)]
                    if values:
                        max_value = max(str(v) for v in values)
                        self._watermark.update_watermark(layer, schema, table, max_value, len(records))
                        context.log.info(f"Watermark updated to {max_value}")
                elif incremental_strategy == "full_refresh":
                    from datetime import datetime
                    run_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                    self._watermark.update_watermark(layer, schema, table, run_ts, len(records))
                    context.log.info(f"Watermark updated (full_refresh) to {run_ts}")

            except Exception as e:
                context.log.error(f"Write failed: {e}")
                try:
                    self._watermark.set_status(layer, schema, table, "failed", str(e))
                except Exception:
                    pass
                raise
            finally:
                cur.close()
        finally:
            conn.close()

    def _handle_stage_copy(self, context, cur, records, meta, schema, table):
        """Bulk load via PUT to internal stage + COPY INTO (Snowflake)."""
        if not records:
            return

        pk = meta.get("primary_key")
        pk_cols = [c.strip() for c in pk.split(",")] if isinstance(pk, str) else pk
        incremental_col = meta.get("incremental_column")
        columns = list(records[0].keys())
        staging_table = f"stg_{table}"

        # Write records to temp NDJSON file
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".ndjson")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                for record in records:
                    f.write(json.dumps(record, default=str) + "\n")

            # Create temp staging table
            cur.execute(
                f"CREATE OR REPLACE TEMPORARY TABLE {_qi(staging_table)} "
                f"AS SELECT * FROM {_qi(schema)}.{_qi(table)} WHERE 1=0"
            )

            safe_columns = self._get_safe_columns(cur, schema, table, columns)

            # PUT file to table stage
            cur.execute(f"PUT 'file://{tmp_path}' @%{_qi(staging_table)} AUTO_COMPRESS=TRUE OVERWRITE=TRUE")

            # COPY INTO staging table from stage
            col_list = ", ".join(_qi(c) for c in safe_columns)
            cur.execute(
                f"COPY INTO {_qi(staging_table)} ({col_list}) "
                f"FROM @%{_qi(staging_table)} "
                f"FILE_FORMAT = (TYPE = JSON) "
                f"MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE"
            )

            # MERGE or INSERT
            incremental_strategy = meta.get("incremental_strategy", "")
            if incremental_strategy == "full_refresh":
                load_sql = self._build_insert_sql(
                    schema, table, staging_table, pk_cols, safe_columns, incremental_col
                )
            else:
                load_sql = self._build_merge_sql(
                    schema, table, staging_table, pk_cols, safe_columns, incremental_col
                )
            cur.execute(load_sql)
            context.log.info(f"Stage copy: {len(records)} records into {schema}.{table}")

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _handle_direct_insert(
        self, context, cur, records, schema, table, pk_cols, incremental_col
    ):
        """INSERT records via staging table -> MERGE to target."""
        if not records:
            return

        columns = list(records[0].keys())
        pk_list = pk_cols if isinstance(pk_cols, list) else [pk_cols]
        staging_table = f"stg_{table}"

        # Create temp staging table
        cur.execute(
            f"CREATE OR REPLACE TEMPORARY TABLE {_qi(staging_table)} "
            f"AS SELECT * FROM {_qi(schema)}.{_qi(table)} WHERE 1=0"
        )

        safe_columns = self._get_safe_columns(cur, schema, table, columns)

        # INSERT all records into staging
        placeholders = ", ".join(["%s"] * len(safe_columns))
        insert_sql = (
            f"INSERT INTO {_qi(staging_table)} ({', '.join(_qi(c) for c in safe_columns)}) "
            f"VALUES ({placeholders})"
        )
        for record in records:
            values = [
                json.dumps(record.get(c), default=str)
                if isinstance(record.get(c), (dict, list))
                else record.get(c)
                for c in safe_columns
            ]
            cur.execute(insert_sql, tuple(values))

        # MERGE staging -> target
        merge_sql = self._build_merge_sql(
            schema=schema,
            table=table,
            staging_table=staging_table,
            pk_cols=pk_list,
            columns=safe_columns,
            incremental_col=incremental_col,
        )
        cur.execute(merge_sql)
        context.log.info(f"MERGE of {len(records)} records into {schema}.{table} via staging")

    def _handle_csv_file(self, context: OutputContext, csv_path: str):
        """Load from CSV file in batches via staging table."""
        import csv
        from datetime import datetime

        if not os.path.exists(csv_path):
            context.log.error(f"CSV file not found: {csv_path}")
            return

        meta = context.metadata or {}
        schema = meta.get("target_schema")
        table = meta.get("target_table")
        pk = meta.get("primary_key")
        layer = meta.get("layer", "raw")
        incremental_strategy = meta.get("incremental_strategy", "")
        incremental_col = meta.get("incremental_column")

        if not schema or not table or not pk:
            raise ValueError(
                f"Asset metadata must include target_schema, target_table, primary_key. Got: {meta}"
            )

        pk_cols = [c.strip() for c in pk.split(",")] if isinstance(pk, str) else pk

        conn = self._warehouse.get_connection()
        try:
            cur = conn.cursor()
            try:
                if incremental_strategy == "full_refresh":
                    cur.execute(f"TRUNCATE TABLE {_qi(schema)}.{_qi(table)}")
                    context.log.info(f"TRUNCATE {schema}.{table} (full_refresh)")

                total_inserted = 0
                max_watermark_value = None

                with open(csv_path, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    batch = []

                    for row in reader:
                        batch.append(row)
                        if incremental_col and row.get(incremental_col):
                            val = str(row[incremental_col])
                            if max_watermark_value is None or val > max_watermark_value:
                                max_watermark_value = val

                        if len(batch) >= 1000:
                            self._insert_batch(cur, schema, table, pk_cols, batch, incremental_strategy, incremental_col, context)
                            total_inserted += len(batch)
                            context.log.info(f"  Inserted {total_inserted:,} rows...")
                            batch = []

                    if batch:
                        self._insert_batch(cur, schema, table, pk_cols, batch, incremental_strategy, incremental_col, context)
                        total_inserted += len(batch)

                context.log.info(f"Committed {total_inserted:,} records to {schema}.{table}")

                if incremental_col and max_watermark_value:
                    self._watermark.update_watermark(layer, schema, table, max_watermark_value, total_inserted)
                elif incremental_strategy == "full_refresh":
                    run_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                    self._watermark.update_watermark(layer, schema, table, run_ts, total_inserted)

                with open(csv_path, "w") as f:
                    f.truncate(0)
                context.log.info(f"Truncated CSV file: {csv_path}")

            except Exception as e:
                context.log.error(f"CSV load failed: {e}")
                try:
                    self._watermark.set_status(layer, schema, table, "failed", str(e))
                except Exception:
                    pass
                raise
            finally:
                cur.close()
        finally:
            conn.close()

    def _handle_ndjson_file(self, context: OutputContext, ndjson_path: str):
        """Load from NDJSON file via PUT + COPY INTO (Snowflake internal stage)."""
        from datetime import datetime

        if not os.path.exists(ndjson_path):
            context.log.error(f"NDJSON file not found: {ndjson_path}")
            return

        meta = context.metadata or {}
        schema = meta.get("target_schema")
        table = meta.get("target_table")
        pk = meta.get("primary_key")
        layer = meta.get("layer", "raw")
        incremental_strategy = meta.get("incremental_strategy", "")
        incremental_col = meta.get("incremental_column")

        if not schema or not table or not pk:
            raise ValueError(
                f"Asset metadata must include target_schema, target_table, primary_key. Got: {meta}"
            )

        pk_cols = [c.strip() for c in pk.split(",")] if isinstance(pk, str) else pk

        # Stream through NDJSON once: collect watermark value and column names
        columns = None
        max_watermark_value = None
        total_rows = 0

        with open(ndjson_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                total_rows += 1
                if columns is None:
                    columns = list(record.keys())
                if incremental_col and record.get(incremental_col):
                    val = str(record[incremental_col])
                    if max_watermark_value is None or val > max_watermark_value:
                        max_watermark_value = val

        if total_rows == 0:
            context.log.info("No records in NDJSON file — nothing to load.")
            self._watermark.set_status(layer, schema, table, "no_new_data")
            with open(ndjson_path, "w") as f:
                f.truncate(0)
            return

        context.log.info(f"Scanned {total_rows:,} records from {ndjson_path}")

        conn = self._warehouse.get_connection()
        try:
            cur = conn.cursor()
            try:
                if incremental_strategy == "full_refresh":
                    cur.execute(f"TRUNCATE TABLE {_qi(schema)}.{_qi(table)}")
                    context.log.info(f"TRUNCATE {schema}.{table} (full_refresh)")

                staging_table = f"stg_{table}"
                cur.execute(
                    f"CREATE OR REPLACE TEMPORARY TABLE {_qi(staging_table)} "
                    f"AS SELECT * FROM {_qi(schema)}.{_qi(table)} WHERE 1=0"
                )
                context.log.info(f"Created staging table {staging_table}")

                safe_columns = self._get_safe_columns(cur, schema, table, columns)

                # PUT file to staging table's internal stage
                cur.execute(
                    f"PUT 'file://{ndjson_path}' @%{_qi(staging_table)} "
                    f"AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
                )

                # COPY INTO staging table
                col_list = ", ".join(_qi(c) for c in safe_columns)
                cur.execute(
                    f"COPY INTO {_qi(staging_table)} ({col_list}) "
                    f"FROM @%{_qi(staging_table)} "
                    f"FILE_FORMAT = (TYPE = JSON) "
                    f"MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE"
                )

                # MERGE or INSERT into target
                if incremental_strategy == "full_refresh":
                    load_sql = self._build_insert_sql(
                        schema, table, staging_table, pk_cols, safe_columns, incremental_col
                    )
                    cur.execute(load_sql)
                    context.log.info(f"INSERT into {schema}.{table} completed (full_refresh)")
                else:
                    merge_sql = self._build_merge_sql(
                        schema, table, staging_table, pk_cols, safe_columns, incremental_col
                    )
                    cur.execute(merge_sql)
                    context.log.info(f"MERGE into {schema}.{table} completed")

                context.log.info(f"Committed {total_rows:,} records to {schema}.{table}")

                # Update watermark
                if incremental_col and max_watermark_value:
                    self._watermark.update_watermark(layer, schema, table, max_watermark_value, total_rows)
                    context.log.info(f"Watermark updated to {max_watermark_value}")
                elif incremental_strategy == "full_refresh":
                    run_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                    self._watermark.update_watermark(layer, schema, table, run_ts, total_rows)
                    context.log.info(f"Watermark updated (full_refresh) to {run_ts}")

                # Truncate local NDJSON file
                with open(ndjson_path, "w") as f:
                    f.truncate(0)
                context.log.info(f"Truncated NDJSON file: {ndjson_path}")

            except Exception as e:
                context.log.error(f"NDJSON bulk load failed: {e}")
                try:
                    self._watermark.set_status(layer, schema, table, "failed", str(e))
                except Exception:
                    pass
                raise
            finally:
                cur.close()
        finally:
            conn.close()

    def _insert_batch(self, cur, schema, table, pk_cols, batch, incremental_strategy, incremental_col, context):
        """Insert a batch of records via staging table + MERGE (Snowflake)."""
        if not batch:
            return

        columns = list(batch[0].keys())
        staging_table = f"stg_{table}_batch"

        cur.execute(
            f"CREATE OR REPLACE TEMPORARY TABLE {_qi(staging_table)} "
            f"AS SELECT * FROM {_qi(schema)}.{_qi(table)} WHERE 1=0"
        )

        safe_columns = self._get_safe_columns(cur, schema, table, columns)

        placeholders = ", ".join(["%s"] * len(safe_columns))
        insert_sql = (
            f"INSERT INTO {_qi(staging_table)} ({', '.join(_qi(c) for c in safe_columns)}) "
            f"VALUES ({placeholders})"
        )
        for row in batch:
            values = [
                json.dumps(row.get(c), default=str)
                if isinstance(row.get(c), (dict, list))
                else row.get(c)
                for c in safe_columns
            ]
            cur.execute(insert_sql, tuple(values))

        if incremental_strategy == "full_refresh":
            load_sql = self._build_insert_sql(
                schema, table, staging_table, pk_cols, safe_columns, incremental_col
            )
        else:
            load_sql = self._build_merge_sql(
                schema, table, staging_table, pk_cols, safe_columns, incremental_col
            )
        cur.execute(load_sql)

    def load_input(self, context: InputContext):
        """Load data from warehouse for downstream assets."""
        meta = context.upstream_output.metadata or {}
        schema = meta.get("target_schema")
        table = meta.get("target_table")

        if not schema or not table:
            raise ValueError("Upstream asset must provide target_schema and target_table in metadata")

        conn = self._warehouse.get_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute(f"SELECT * FROM {_qi(schema)}.{_qi(table)}")
                if not cur.description:
                    return []
                col_names = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(col_names, row)) for row in rows]
            finally:
                cur.close()
        finally:
            conn.close()


@io_manager(required_resource_keys={"warehouse", "watermark"})
def warehouse_io_manager(context):
    """Factory for WarehouseIOManager. Injects shared resources (no S3)."""
    return WarehouseIOManager(context.resources.warehouse, context.resources.watermark)
```

- [ ] **Step 2: Verify no psycopg2/S3 references remain**

```bash
grep -n "psycopg2\|boto3\|s3_resource\|S3Resource" dagster/io_managers.py
# Expected: no output
```

- [ ] **Step 3: Commit**

```bash
git add dagster/io_managers.py
git commit -m "rewrite io_managers.py for Snowflake: MERGE with aliases, PUT+COPY INTO, remove S3"
```

---

## Task 6: Update asset_factory.py (load_method default)

**Files:**
- Modify: `dagster/asset_factory.py`

- [ ] **Step 1: Change default load_method from s3_copy to stage_copy**

Find the line where `load_method` defaults to `"s3_copy"` and change to `"stage_copy"`. Also find any `s3_bucket_config` references and remove them.

Search for: `load_method.*s3_copy` and `s3_bucket_config`

- [ ] **Step 2: Verify**

```bash
grep -n "s3_copy\|s3_bucket" dagster/asset_factory.py
# Expected: no output
```

- [ ] **Step 3: Commit**

```bash
git add dagster/asset_factory.py
git commit -m "asset_factory: change default load_method to stage_copy, remove s3_bucket_config"
```

---

## Task 7: Update ingestion/definitions.py (remove S3 resource)

**Files:**
- Modify: `dagster/ingestion/definitions.py`

- [ ] **Step 1: Remove s3 from resources dict**

In the `_resources` dict construction, remove the `"s3": S3Resource()` entry and the S3Resource import.

- [ ] **Step 2: Verify**

```bash
grep -n "s3\|S3" dagster/ingestion/definitions.py
# Expected: no output (or only comments)
```

- [ ] **Step 3: Commit**

```bash
git add dagster/ingestion/definitions.py
git commit -m "ingestion definitions: remove S3 resource"
```

---

## Task 8: Update dbt Configuration (profiles.yml, dbt_project.yml, packages.yml)

**Files:**
- Modify: `dagster/dbt/profiles.yml`
- Modify: `dagster/dbt/dbt_project.yml`
- Modify: `dagster/dbt/packages.yml`

- [ ] **Step 1: Replace profiles.yml with Snowflake targets**

```yaml
default:
  target: "{{ env_var('DBT_TARGET', 'dev') }}"
  outputs:
    dev:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('TARGET_USERNAME') }}"
      password: "{{ env_var('TARGET_PASSWORD') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE', 'ACCOUNTADMIN') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH') }}"
      database: "{{ env_var('TARGET_DATABASE', 'BIO') }}"
      schema: dev_staging
      threads: 4
    integration:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('TARGET_USERNAME') }}"
      password: "{{ env_var('TARGET_PASSWORD') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE', 'ACCOUNTADMIN') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH') }}"
      database: "{{ env_var('TARGET_DATABASE', 'BIO') }}"
      schema: staging_dev
      threads: 4
    prod:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('TARGET_USERNAME') }}"
      password: "{{ env_var('TARGET_PASSWORD') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE', 'ACCOUNTADMIN') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH') }}"
      database: "{{ env_var('TARGET_DATABASE', 'BIO') }}"
      schema: staging
      threads: 4
```

- [ ] **Step 2: Update dbt_project.yml**

Replace ALL `{{project_name}}` placeholders with `bio_dagster_dbt`:
- `name: bio_dagster_dbt_analytics`
- Under `models:`, change `{{project_name}}_analytics:` to `bio_dagster_dbt_analytics:`
- Under `snapshots:`, change `{{project_name}}_analytics:` to `bio_dagster_dbt_analytics:`

- [ ] **Step 2b: Fix dim_date.sql for Snowflake**

In `dagster/dbt/models/core/dim_date.sql` (if it exists):
- Remove `sort='date_day'` and `dist='all'` from the config block (Snowflake has no DISTKEY/SORTKEY)
- `::date` casts work in Snowflake, no change needed

- [ ] **Step 3: Verify packages.yml has no Postgres-specific packages**

packages.yml should have dbt_utils, dbt_expectations, audit_helper. No changes needed unless it references a Postgres adapter.

- [ ] **Step 4: Commit**

```bash
git add dagster/dbt/profiles.yml dagster/dbt/dbt_project.yml dagster/dbt/packages.yml
git commit -m "dbt config: Snowflake profiles, project name bio_dagster_dbt_analytics"
```

---

## Task 9: Rewrite Watermark DDL for Snowflake

**Files:**
- Modify: `dagster/ingestion/raw/metadata/DDL/create_metadata_schema.py`

- [ ] **Step 1: Rewrite create_metadata_schema.py**

Replace psycopg2 with snowflake.connector. Create BIO database, METADATA schema, PIPELINE_WATERMARKS table with full column set from spec. Use `TIMESTAMP_NTZ`, `BIGINT`, `VARCHAR(500)`.

```python
"""Bootstrap: create BIO database, METADATA schema, and PIPELINE_WATERMARKS table in Snowflake."""

import sys
from pathlib import Path

import snowflake.connector

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from load_config import load_config


def main():
    cfg = load_config()
    target = cfg["target"]

    conn = snowflake.connector.connect(
        account=target["account"],
        user=target["username"],
        password=target["password"],
        warehouse=target.get("warehouse", "COMPUTE_WH"),
        role=target.get("role", "ACCOUNTADMIN"),
    )
    cur = conn.cursor()

    try:
        cur.execute("CREATE DATABASE IF NOT EXISTS BIO")
        cur.execute("USE DATABASE BIO")
        cur.execute("CREATE SCHEMA IF NOT EXISTS METADATA")
        cur.execute("USE SCHEMA METADATA")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS PIPELINE_WATERMARKS (
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
            )
        """)

        # Add PK if not exists (idempotent via TRY)
        try:
            cur.execute(
                "ALTER TABLE PIPELINE_WATERMARKS "
                "ADD PRIMARY KEY (layer, target_schema, target_table)"
            )
        except snowflake.connector.errors.ProgrammingError:
            pass  # PK already exists

        # Verify
        cur.execute("SELECT COUNT(*) FROM PIPELINE_WATERMARKS")
        count = cur.fetchone()[0]
        print(f"OK: BIO.METADATA.PIPELINE_WATERMARKS exists ({count} rows)")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the DDL script to create the BIO database**

```bash
python dagster/ingestion/raw/metadata/DDL/create_metadata_schema.py
# Expected: OK: BIO.METADATA.PIPELINE_WATERMARKS exists (0 rows)
```

- [ ] **Step 3: Commit**

```bash
git add dagster/ingestion/raw/metadata/DDL/create_metadata_schema.py
git commit -m "watermark DDL: Snowflake BIO.METADATA.PIPELINE_WATERMARKS"
```

---

## Task 10: Rewrite systems/assets.py for Snowflake

**Files:**
- Modify: `dagster/systems/assets.py`

- [ ] **Step 1: Replace Postgres system catalog queries with Snowflake information_schema**

Key changes:
- Replace `pg_tables` / `pg_views` queries with `SHOW SCHEMAS IN DATABASE BIO` + `SHOW TABLES IN SCHEMA` + `SHOW VIEWS IN SCHEMA`
- Update `EXCLUDED_SCHEMAS` to `("INFORMATION_SCHEMA",)`
- Grant syntax: `GRANT USAGE ON SCHEMA {schema} TO ROLE {role}` + `GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO ROLE {role}`

- [ ] **Step 2: Commit**

```bash
git add dagster/systems/assets.py
git commit -m "systems/assets.py: Snowflake grant syntax and information_schema queries"
```

---

## Task 11: Create All 14 Source Pipeline Directories

**Files:**
- Create: `dagster/ingestion/raw/api_klaviyo/config.yaml`
- Create: `dagster/ingestion/raw/api_meta/config.yaml`
- Create: `dagster/ingestion/raw/api_google_ads_gallant_seto/config.yaml`
- Create: `dagster/ingestion/raw/api_google_ads_noot/config.yaml`
- Create: `dagster/ingestion/raw/api_ga4/config.yaml`
- Create: `dagster/ingestion/raw/api_gtm/config.yaml`
- Create: `dagster/ingestion/raw/api_amazon_ads/config.yaml`
- Create: `dagster/ingestion/raw/api_amazon_selling_partner/config.yaml`
- Create: `dagster/ingestion/raw/api_tiktok_ads/config.yaml`
- Create: `dagster/ingestion/raw/api_pacvuedsp/config.yaml`
- Create: `dagster/ingestion/raw/api_refersion/config.yaml`
- Create: `dagster/ingestion/raw/api_triple_whale/config.yaml`
- Create: `dagster/ingestion/raw/internal_mysql_dock/config.yaml`
- Create: `dagster/ingestion/raw/internal_mongo_goldlantern/config.yaml`

Each source directory gets:
- `config.yaml` — asset definitions for the YAML-driven asset factory
- `ddl/` — empty dir for future DDL scripts
- `data/temp/` — empty dir for local staging

- [ ] **Step 1: Create all 14 source directories with config.yaml stubs**

Each config.yaml follows the template pattern. Example for Klaviyo:

```yaml
source: klaviyo
source_type: api
connection_resource: klaviyo
custom_extractor: true
default_group: raw_klaviyo

assets:
  - name: klaviyo_lists
    target_schema: raw_klaviyo
    target_table: lists
    primary_key: id
    incremental_strategy: full_refresh
    load_method: stage_copy

  - name: klaviyo_campaigns
    target_schema: raw_klaviyo
    target_table: campaigns
    primary_key: id
    incremental_strategy: full_refresh
    load_method: stage_copy

  - name: klaviyo_metrics
    target_schema: raw_klaviyo
    target_table: metrics
    primary_key: id
    incremental_strategy: full_refresh
    load_method: stage_copy
```

Create similar config.yaml for each source, referencing the connection verification CSVs to determine which endpoints/tables each source exposes. Use the actual endpoint names visible in the CSV filenames.

- [ ] **Step 2: Create ddl/ and data/temp/ subdirs for each source**

```bash
for src in api_klaviyo api_meta api_google_ads_gallant_seto api_google_ads_noot api_ga4 api_gtm api_amazon_ads api_amazon_selling_partner api_tiktok_ads api_pacvuedsp api_refersion api_triple_whale internal_mysql_dock internal_mongo_goldlantern; do
  mkdir -p "dagster/ingestion/raw/$src/ddl"
  mkdir -p "dagster/ingestion/raw/$src/data/temp"
  touch "dagster/ingestion/raw/$src/ddl/.gitkeep"
  touch "dagster/ingestion/raw/$src/data/temp/.gitkeep"
done
```

- [ ] **Step 3: Commit**

```bash
git add dagster/ingestion/raw/
git commit -m "create 14 source pipeline directories with config.yaml stubs"
```

---

## Task 12: Update dbt sources.yml for All 14 Sources

**Files:**
- Modify: `dagster/dbt/models/sources.yml`

- [ ] **Step 1: Write sources.yml with all 14 raw sources**

```yaml
version: 2

sources:
  - name: raw_klaviyo
    database: BIO
    schema: raw_klaviyo
    tables:
      - name: lists
      - name: campaigns
      - name: metrics

  - name: raw_meta
    database: BIO
    schema: raw_meta
    tables:
      - name: campaigns
      - name: campaign_insights

  - name: raw_google_ads_gallant_seto
    database: BIO
    schema: raw_google_ads_gallant_seto
    tables:
      - name: campaigns
      - name: ad_groups
      - name: ads
      - name: keywords
      - name: campaign_performance
      - name: ad_group_performance
      - name: accounts

  - name: raw_google_ads_noot
    database: BIO
    schema: raw_google_ads_noot
    tables:
      - name: campaigns
      - name: ad_groups
      - name: ads
      - name: keywords
      - name: campaign_performance
      - name: ad_group_performance
      - name: accounts

  - name: raw_ga4
    database: BIO
    schema: raw_ga4
    tables:
      - name: events
      - name: users
      - name: ecommerce

  - name: raw_gtm
    database: BIO
    schema: raw_gtm
    tables:
      - name: containers
      - name: tags
      - name: triggers
      - name: variables

  - name: raw_amazon_ads
    database: BIO
    schema: raw_amazon_ads
    tables:
      - name: campaigns
      - name: ad_groups

  - name: raw_amazon_selling_partner
    database: BIO
    schema: raw_amazon_selling_partner
    tables:
      - name: orders
      - name: inventory
      - name: financial_events

  - name: raw_tiktok_ads
    database: BIO
    schema: raw_tiktok_ads
    tables:
      - name: campaigns
      - name: ad_groups
      - name: ads
      - name: campaign_stats

  - name: raw_pacvuedsp
    database: BIO
    schema: raw_pacvuedsp
    tables:
      - name: ads_type_analysis_line_chart

  - name: raw_refersion
    database: BIO
    schema: raw_refersion
    tables:
      - name: affiliate_performance

  - name: raw_triple_whale
    database: BIO
    schema: raw_triple_whale
    tables:
      - name: attribution
      - name: summary

  - name: raw_mysql_dock
    database: BIO
    schema: raw_mysql_dock
    tables:
      - name: orders
      - name: customers

  - name: raw_mongo_goldlantern
    database: BIO
    schema: raw_mongo_goldlantern
    tables:
      - name: processes
      - name: scheduled_reports
```

(Table names derived from connection_verification CSV filenames. Exact tables will be refined during pipeline implementation.)

- [ ] **Step 2: Commit**

```bash
git add dagster/dbt/models/sources.yml
git commit -m "dbt sources.yml: all 14 raw sources targeting BIO database"
```

---

## Task 13: Update CLAUDE.md and RULES.md

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENT_KNOWLEDGE/RULES.md`

- [ ] **Step 1: Update CLAUDE.md**

Replace `{{PROJECT_NAME}}` with `bio-dagster-dbt`. Replace `{{WAREHOUSE_MCP_DESCRIPTION}}` with `Snowflake (account vab13150, database BIO)`. Ensure target type references say Snowflake not Postgres.

- [ ] **Step 2: Update RULES.md with Snowflake-specific rules**

Add rules from `_RESOURCES/snowflake.md` "Rules to Add to RULES.md" section:
- Snowflake MERGE supports target aliases
- VARIANT columns: use `:` notation for nested field access
- QUALIFY ROW_NUMBER() works in Snowflake
- COPY INTO requires a stage
- psycopg2.sql is NOT available
- Unquoted identifiers stored as UPPERCASE
- Use TIMESTAMP_NTZ

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md AGENT_KNOWLEDGE/RULES.md
git commit -m "update CLAUDE.md and RULES.md for Snowflake activation"
```

---

## Task 14: Update Deployment Files (Dockerfile, values.yaml)

**Files:**
- Modify: `dagster/deployment/Dockerfile_user_code`
- Modify: `dagster/deployment/values.yaml`

- [ ] **Step 1: Update Dockerfile_user_code**

- Change base image to `python:3.11-slim` (if currently 3.10)
- Remove `libpq-dev` from apt-get install (no Postgres C library needed)
- Uncomment or add `dbt-snowflake` in the pip install section
- Add `snowflake-connector-python` if not already present

- [ ] **Step 2: Clean up values.yaml**

- Remove or comment out AWS-specific values (ECR registry, S3 compute logs, IAM role ARN)
- Replace with placeholder comments for future cloud deployment config

- [ ] **Step 3: Commit**

```bash
git add dagster/deployment/Dockerfile_user_code dagster/deployment/values.yaml
git commit -m "deployment: update Dockerfile for Snowflake, clean AWS refs from values.yaml"
```

---

## Task 15: Verify — Dagster Definitions Load and Snowflake Connectivity

**Files:** None (verification only)

- [ ] **Step 1: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Validate Dagster definitions load without errors**

```bash
cd dagster && python -c "from definitions import defs; print(f'Loaded {len(list(defs.get_all_asset_specs()))} assets')"
```

Expected: Definitions load successfully (may show 0 assets if no config.yaml files have valid assets yet, but should NOT error).

- [ ] **Step 3: Verify Snowflake connectivity**

```bash
python -c "
from dagster.resources import WarehouseResource
w = WarehouseResource()
result = w.execute('SELECT CURRENT_DATABASE(), CURRENT_WAREHOUSE(), CURRENT_ROLE()')
print(result)
"
```

Expected: `[('BIO', 'COMPUTE_WH', 'ACCOUNTADMIN')]` or similar.

- [ ] **Step 4: Verify watermark table exists**

```bash
python -c "
from dagster.resources import WarehouseResource
w = WarehouseResource()
result = w.execute('SELECT COUNT(*) FROM BIO.METADATA.PIPELINE_WATERMARKS')
print(f'Watermark table OK: {result[0][0]} rows')
"
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "snowflake activation complete: all configs, resources, io_managers, 14 sources wired"
```
