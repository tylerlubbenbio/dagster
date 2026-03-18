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

import boto3
import psycopg2
from psycopg2 import sql
import requests
from dagster import ConfigurableResource

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from load_config import load_config


class WarehouseResource(ConfigurableResource):
    """Warehouse connection factory. Reads credentials from .env via load_config()."""

    def _get_target(self) -> dict:
        return load_config()["target"]

    def get_connection(self):
        target = self._get_target()
        return psycopg2.connect(
            host=target["host"],
            port=int(target.get("port", 5432)),
            database=target["database"],
            user=target["username"],
            password=target["password"],
            sslmode="require",
        )

    def execute(self, query, params=None):
        """Execute SQL. query may be str or psycopg2.sql.Composed. Returns rows if SELECT, else None."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if cur.description:
                    return cur.fetchall()
            conn.commit()
        finally:
            conn.close()

    def get_row_count(self, schema: str, table: str) -> int:
        q = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
        result = self.execute(q)
        return result[0][0] if result else 0

    def get_column_stats(self, schema: str, table: str) -> list[dict]:
        """Get column-level stats: name, type, null count, distinct count."""
        columns = self.execute(
            """SELECT column_name, data_type
               FROM information_schema.columns
               WHERE table_schema = %s AND table_name = %s
               ORDER BY ordinal_position""",
            (schema, table),
        )
        if not columns:
            return []

        tbl = sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(table))
        stats = []
        for col_name, col_type in columns:
            col_id = sql.Identifier(col_name)
            null_q = sql.SQL("SELECT COUNT(*) FROM {} WHERE {} IS NULL").format(
                tbl, col_id
            )
            distinct_q = sql.SQL("SELECT COUNT(DISTINCT {}) FROM {}").format(
                col_id, tbl
            )
            null_count = self.execute(null_q)
            distinct_count = self.execute(distinct_q)
            stats.append(
                {
                    "column": col_name,
                    "type": col_type,
                    "null_count": null_count[0][0] if null_count else 0,
                    "distinct_count": distinct_count[0][0] if distinct_count else 0,
                }
            )
        return stats

    def get_sample_rows(self, schema: str, table: str, limit: int = 5) -> list[dict]:
        """Get sample rows as list of dicts for metadata display."""
        q = sql.SQL("SELECT * FROM {}.{} LIMIT %s").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(q, (limit,))
                if not cur.description:
                    return []
                col_names = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(col_names, row)) for row in rows]
        finally:
            conn.close()


class WatermarkResource(ConfigurableResource):
    """Read/update metadata.pipeline_watermarks via warehouse."""

    warehouse: WarehouseResource

    def get_watermark(self, layer: str, schema: str, table: str) -> str | None:
        rows = self.warehouse.execute(
            """SELECT watermark_value FROM metadata.pipeline_watermarks
               WHERE layer = %s AND target_schema = %s AND target_table = %s
               ORDER BY updated_at DESC LIMIT 1""",
            (layer, schema, table),
        )
        return rows[0][0] if rows else None

    def _row_exists(self, layer: str, schema: str, table: str) -> bool:
        rows = self.warehouse.execute(
            """SELECT 1 FROM metadata.pipeline_watermarks
               WHERE layer = %s AND target_schema = %s AND target_table = %s LIMIT 1""",
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
        # DELETE + INSERT is the upsert pattern — always results in exactly 1 row
        self.warehouse.execute(
            "DELETE FROM metadata.pipeline_watermarks WHERE layer = %s AND target_schema = %s AND target_table = %s",
            (layer, schema, table),
        )
        self.warehouse.execute(
            """INSERT INTO metadata.pipeline_watermarks
               (layer, target_schema, target_table, watermark_value, rows_processed, status,
                last_run_at, last_success_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (layer, schema, table, str(value), rows_processed, status),
        )

    def get_last_run_at(self, layer: str, schema: str, table: str) -> str | None:
        rows = self.warehouse.execute(
            """SELECT last_run_at FROM metadata.pipeline_watermarks
               WHERE layer = %s AND target_schema = %s AND target_table = %s
               ORDER BY updated_at DESC LIMIT 1""",
            (layer, schema, table),
        )
        return str(rows[0][0]) if rows and rows[0][0] else None

    def mark_run_started(self, layer: str, schema: str, table: str):
        """Stamp last_run_at without changing status. Enables last_run_at > last_success_at as the in-flight signal."""
        if self._row_exists(layer, schema, table):
            self.warehouse.execute(
                """UPDATE metadata.pipeline_watermarks
                   SET last_run_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                   WHERE layer = %s AND target_schema = %s AND target_table = %s""",
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
                """INSERT INTO metadata.pipeline_watermarks
                   (layer, target_schema, target_table, status, error_message, last_run_at,
                    last_success_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP,
                    CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END, CURRENT_TIMESTAMP)""",
                (layer, schema, table, status, err_truncated, is_success),
            )
        else:
            self.warehouse.execute(
                """UPDATE metadata.pipeline_watermarks
                   SET status = %s, error_message = %s, last_run_at = CURRENT_TIMESTAMP,
                       last_success_at = CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE last_success_at END,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE layer = %s AND target_schema = %s AND target_table = %s""",
                (status, err_truncated, is_success, layer, schema, table),
            )


class S3Resource(ConfigurableResource):
    """S3 client for uploading NDJSON files (used by IO Manager for s3_copy mode)."""

    def get_client(self, region: str = "us-east-1"):
        return boto3.client("s3", region_name=region)

    def upload_ndjson(
        self,
        bucket: str,
        prefix: str,
        records: list[dict],
        batch_size: int = 1000,
        region: str = "us-east-1",
    ) -> list[str]:
        """Upload records as NDJSON files to S3. Returns list of S3 keys."""
        from datetime import datetime

        s3 = self.get_client(region)
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        s3_keys = []

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            lines = [json.dumps(r, default=str) for r in batch]
            body = "\n".join(lines)
            key = f"{prefix}/run_{run_id}_{i // batch_size + 1}.ndjson"
            s3.put_object(
                Bucket=bucket, Key=key, Body=body, ContentType="application/x-ndjson"
            )
            s3_keys.append(key)

        return s3_keys

    def upload_ndjson_file(
        self, bucket: str, prefix: str, file_path: str, region: str = "us-east-1"
    ) -> str:
        """Upload a local NDJSON file directly to S3 (no in-memory records). Returns S3 key."""
        from datetime import datetime

        s3 = self.get_client(region)
        run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        key = f"{prefix}/run_{run_id}_1.ndjson"
        s3.upload_file(
            file_path, bucket, key, ExtraArgs={"ContentType": "application/x-ndjson"}
        )
        return key


class ExampleApiResource(ConfigurableResource):
    """Example API client. Replace with your actual API resource."""

    def _get_api_key(self) -> str:
        return load_config().get("example_api", {}).get("api_key", "")

    def fetch_records(self, from_date: str, to_date: str) -> list[dict]:
        """Fetch records from API. Implement for your source."""
        raise NotImplementedError("Implement fetch_records for your API source")


class ExampleDbResource(ConfigurableResource):
    """Example source database connection. Replace with your actual DB resource."""

    def _get_config(self) -> dict:
        return load_config()["databases"]["_example_source"]

    def get_connection(self):
        db = self._get_config()
        return psycopg2.connect(
            host=db["host"],
            port=int(db.get("port", 5432)),
            database=db["database"],
            user=db["username"],
            password=db["password"],
            connect_timeout=15,
        )


def get_all_resources() -> dict:
    """Build the resources dict for Definitions."""
    warehouse = WarehouseResource()
    return {
        "warehouse": warehouse,
        "watermark": WatermarkResource(warehouse=warehouse),
        "s3": S3Resource(),
        # Add your source resources below:
        # "example_api": ExampleApiResource(),
        # "example_db": ExampleDbResource(),
    }
