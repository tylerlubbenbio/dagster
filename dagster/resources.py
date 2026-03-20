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


class MetaResource(ConfigurableResource):
    """Meta Marketing API connection. Reads config from load_config()."""

    def _get_config(self) -> dict:
        cfg = load_config()
        return cfg["sources"]["meta"]

    def get_access_token(self) -> str:
        return self._get_config()["access_token"]

    def get_ad_account_id(self) -> str:
        return self._get_config()["ad_account_id"]

    def get_api_version(self) -> str:
        return self._get_config().get("api_version", "v18.0")

    def test_connection(self) -> bool:
        meta = self._get_config()
        url = f"https://graph.facebook.com/{meta.get('api_version', 'v18.0')}/me"
        resp = requests.get(url, params={"access_token": meta["access_token"]})
        return resp.status_code == 200


def get_all_resources() -> dict:
    """Build the resources dict for Definitions."""
    warehouse = WarehouseResource()
    return {
        "warehouse": warehouse,
        "watermark": WatermarkResource(warehouse=warehouse),
        "meta": MetaResource(),
    }
