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

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".ndjson")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                for record in records:
                    f.write(json.dumps(record, default=str) + "\n")

            cur.execute(
                f"CREATE OR REPLACE TEMPORARY TABLE {_qi(staging_table)} "
                f"AS SELECT * FROM {_qi(schema)}.{_qi(table)} WHERE 1=0"
            )

            safe_columns = self._get_safe_columns(cur, schema, table, columns)

            cur.execute(f"PUT 'file://{tmp_path}' @%{_qi(staging_table)} AUTO_COMPRESS=TRUE OVERWRITE=TRUE")

            col_list = ", ".join(_qi(c) for c in safe_columns)
            cur.execute(
                f"COPY INTO {_qi(staging_table)} ({col_list}) "
                f"FROM @%{_qi(staging_table)} "
                f"FILE_FORMAT = (TYPE = JSON) "
                f"MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE"
            )

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
        for record in records:
            values = [
                json.dumps(record.get(c), default=str)
                if isinstance(record.get(c), (dict, list))
                else record.get(c)
                for c in safe_columns
            ]
            cur.execute(insert_sql, tuple(values))

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

                cur.execute(
                    f"PUT 'file://{ndjson_path}' @%{_qi(staging_table)} "
                    f"AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
                )

                col_list = ", ".join(_qi(c) for c in safe_columns)
                cur.execute(
                    f"COPY INTO {_qi(staging_table)} ({col_list}) "
                    f"FROM @%{_qi(staging_table)} "
                    f"FILE_FORMAT = (TYPE = JSON) "
                    f"MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE"
                )

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

                if incremental_col and max_watermark_value:
                    self._watermark.update_watermark(layer, schema, table, max_watermark_value, total_rows)
                    context.log.info(f"Watermark updated to {max_watermark_value}")
                elif incremental_strategy == "full_refresh":
                    run_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                    self._watermark.update_watermark(layer, schema, table, run_ts, total_rows)
                    context.log.info(f"Watermark updated (full_refresh) to {run_ts}")

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
