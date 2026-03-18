"""Warehouse IO Manager: handles persistence for all assets.

Two modes (set by asset's `load_method` metadata):
  - s3_copy:        records/file -> S3 NDJSON -> staging table -> MERGE into target
  - direct_insert:  records -> staging table -> MERGE into target

All load paths use a staging table + MERGE pattern:
  1. COPY/INSERT all rows into TEMP stg_{table} (no constraints, duplicates OK)
  2. MERGE INTO target USING deduped_subquery_from_stg:
       WHEN MATCHED     → UPDATE existing row in place (no delete/re-insert)
       WHEN NOT MATCHED → INSERT new row
  Dedup within the staging batch uses ROW_NUMBER() before the MERGE.

MERGE is an atomic UPSERT — no window between DELETE and INSERT where concurrent
runs can write duplicate rows. Duplicate PKs are structurally impossible.

full_refresh uses TRUNCATE + INSERT instead of MERGE (target is empty before load).

Also updates the watermark after a successful write.
All SQL uses psycopg2.sql for identifier quoting (no f-string interpolation).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from psycopg2 import sql

from dagster import IOManager, InputContext, OutputContext, io_manager

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from load_config import load_config


class WarehouseIOManager(IOManager):
    """Writes asset output (list[dict]) to the target warehouse."""

    def __init__(self, warehouse_resource, watermark_resource, s3_resource):
        self._warehouse = warehouse_resource
        self._watermark = watermark_resource
        self._s3 = s3_resource

    def _build_merge_sql(
        self,
        schema: str,
        table: str,
        staging_table: str,
        pk_cols: list,
        columns: list,
        incremental_col,
    ):
        """
        Build MERGE INTO target USING deduped-staging SQL.

        # ACTIVATE: This MERGE syntax works for Redshift and Snowflake. For Postgres, replace with INSERT ... ON CONFLICT. See _RESOURCES/{db}.md

        MERGE is an atomic UPSERT:
          WHEN MATCHED (PK exists in target) → UPDATE non-PK columns in place
          WHEN NOT MATCHED                   → INSERT new row

        Deduplication within the staging batch uses ROW_NUMBER() before the MERGE,
        ensuring the USING subquery has at most one row per PK (Redshift requires this).

        Used for incremental strategies (timestamp, incremental_id).
        full_refresh uses TRUNCATE + _build_insert_sql instead.
        """
        col_sql = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
        pk_partition = sql.SQL(", ").join(sql.Identifier(c) for c in pk_cols)
        pk_set = set(pk_cols)
        non_pk_cols = [c for c in columns if c not in pk_set]

        if incremental_col:
            order_sql = sql.SQL("ORDER BY {} DESC NULLS LAST").format(
                sql.Identifier(incremental_col)
            )
        else:
            order_sql = sql.SQL("ORDER BY 1")

        # Target table reference: schema.table (Redshift MERGE does not allow target aliases)
        target_ref = sql.SQL("{}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        )

        # ON condition: schema.table.pk1 = src.pk1 [AND ...]
        on_parts = [
            sql.SQL("{}.{} = src.{}").format(
                target_ref, sql.Identifier(c), sql.Identifier(c)
            )
            for c in pk_cols
        ]
        on_condition = sql.SQL(" AND ").join(on_parts)

        # INSERT values: src.col1, src.col2, ...
        insert_values = sql.SQL(", ").join(
            sql.SQL("src.{}").format(sql.Identifier(c)) for c in columns
        )

        if non_pk_cols:
            set_parts = [
                sql.SQL("{} = src.{}").format(sql.Identifier(c), sql.Identifier(c))
                for c in non_pk_cols
            ]
            matched_clause = sql.SQL("WHEN MATCHED THEN UPDATE SET {set} ").format(
                set=sql.SQL(", ").join(set_parts)
            )
        else:
            # All columns are PKs — nothing to update, only insert new rows
            matched_clause = sql.SQL("")

        return sql.SQL(
            "MERGE INTO {target} "
            "USING ("
            "  SELECT {cols} FROM ("
            "    SELECT *, ROW_NUMBER() OVER (PARTITION BY {pk} {order}) AS rn"
            "    FROM {staging}"
            "  ) sub WHERE rn = 1"
            ") src "
            "ON {on_cond} "
            "{matched}"
            "WHEN NOT MATCHED THEN INSERT ({cols}) VALUES ({values})"
        ).format(
            target=target_ref,
            cols=col_sql,
            pk=pk_partition,
            order=order_sql,
            staging=sql.Identifier(staging_table),
            on_cond=on_condition,
            matched=matched_clause,
            values=insert_values,
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
        """
        Build INSERT INTO target SELECT deduped FROM staging SQL.
        Used only for full_refresh (after TRUNCATE), where MERGE is not needed.
        """
        col_sql = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
        pk_partition = sql.SQL(", ").join(sql.Identifier(c) for c in pk_cols)

        if incremental_col:
            order_sql = sql.SQL("ORDER BY {} DESC NULLS LAST").format(
                sql.Identifier(incremental_col)
            )
        else:
            order_sql = sql.SQL("ORDER BY 1")

        return sql.SQL(
            "INSERT INTO {schema}.{table} ({cols}) "
            "SELECT {cols} FROM ("
            "  SELECT *, ROW_NUMBER() OVER (PARTITION BY {pk} {order}) AS rn"
            "  FROM {staging}"
            ") sub WHERE rn = 1"
        ).format(
            schema=sql.Identifier(schema),
            table=sql.Identifier(table),
            cols=col_sql,
            pk=pk_partition,
            order=order_sql,
            staging=sql.Identifier(staging_table),
        )

    def handle_output(self, context: OutputContext, records):
        """
        Handle asset output - can be list[dict] or file path (str).

        - list[dict]: Traditional in-memory records
        - str (*.ndjson): Path to NDJSON file for S3 COPY
        - str (*.csv): Path to CSV file for batch loading
        """
        # Check if output is a file path (string)
        if isinstance(records, str):
            if records.endswith(".ndjson"):
                return self._handle_ndjson_file(context, records)
            else:
                return self._handle_csv_file(context, records)

        # Traditional list[dict] handling
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

        # Normalize pk to list, stripping whitespace from each key
        pk_cols = [c.strip() for c in pk.split(",")] if isinstance(pk, str) else pk
        incremental_col = meta.get("incremental_column")

        conn = self._warehouse.get_connection()
        conn.autocommit = False

        try:
            cur = conn.cursor()
            incremental_strategy = meta.get("incremental_strategy", "")

            if incremental_strategy == "full_refresh":
                cur.execute(
                    sql.SQL("TRUNCATE TABLE {}.{}").format(
                        sql.Identifier(schema),
                        sql.Identifier(table),
                    )
                )
                context.log.info(f"TRUNCATE {schema}.{table} (full_refresh)")

            if load_method == "s3_copy":
                self._handle_s3_copy(context, cur, records, meta, schema, table)
            else:
                self._handle_direct_insert(
                    context, cur, records, schema, table, pk_cols, incremental_col
                )

            conn.commit()
            context.log.info(f"Committed {len(records)} records to {schema}.{table}")

            # Update watermark
            if incremental_col:
                values = [
                    r.get(incremental_col) for r in records if r.get(incremental_col)
                ]
                if values:
                    max_value = max(str(v) for v in values)
                    self._watermark.update_watermark(
                        layer, schema, table, max_value, len(records)
                    )
                    context.log.info(f"Watermark updated to {max_value}")
            elif incremental_strategy == "full_refresh":
                from datetime import datetime

                run_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                self._watermark.update_watermark(
                    layer, schema, table, run_ts, len(records)
                )
                context.log.info(f"Watermark updated (full_refresh) to {run_ts}")

        except Exception as e:
            conn.rollback()
            context.log.error(f"Write failed, rolling back: {e}")

            try:
                self._watermark.set_status(layer, schema, table, "failed", str(e))
            except Exception:
                pass

            raise
        finally:
            conn.close()

    def _handle_s3_copy(self, context, cur, records, meta, schema, table):
        """Upload to S3, then bulk load into warehouse staging table."""
        # ACTIVATE: bulk load command
        raise NotImplementedError("Run /activate to configure bulk load for your warehouse. See _RESOURCES/{db}.md")

    def _handle_direct_insert(
        self, context, cur, records, schema, table, pk_cols, incremental_col
    ):
        """INSERT records via staging table -> dedup INSERT to target. Guarantees one row per PK."""
        if not records:
            return

        columns = list(records[0].keys())
        pk_list = pk_cols if isinstance(pk_cols, list) else [pk_cols]
        staging_table = f"stg_{table}"

        # Step 1: Create temp staging table (auto-dropped at session end)
        # AS SELECT ... WHERE 1=0: copies column names/types, no constraints, fully nullable
        # (Redshift does not support LIKE ... EXCLUDING CONSTRAINTS)
        cur.execute(
            sql.SQL("CREATE TEMP TABLE {} AS SELECT * FROM {}.{} WHERE 1=0").format(
                sql.Identifier(staging_table),
                sql.Identifier(schema),
                sql.Identifier(table),
            )
        )

        # Intersect record columns with target table columns (in target schema order).
        # Protects against: (1) record cols not in target, (2) target NOT NULL cols absent from records.
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s "
            "ORDER BY ordinal_position",
            (schema, table),
        )
        target_cols = [row[0] for row in cur.fetchall()]
        record_col_set = set(columns)
        safe_columns = [c for c in target_cols if c in record_col_set]
        if not safe_columns:
            raise ValueError(
                f"No overlap between record columns and target {schema}.{table} columns. "
                f"record: {columns[:10]}, target: {target_cols[:10]}"
            )

        # Step 2: INSERT all records into staging (duplicates accepted here)
        insert_staging = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(staging_table),
            sql.SQL(", ").join(map(sql.Identifier, safe_columns)),
            sql.SQL(", ").join([sql.Placeholder()] * len(safe_columns)),
        )
        for record in records:
            values = [
                json.dumps(record.get(c), default=str)
                if isinstance(record.get(c), (dict, list))
                else record.get(c)
                for c in safe_columns
            ]
            cur.execute(insert_staging, tuple(values))

        # Step 3: MERGE staging -> target (atomic upsert: update existing, insert new)
        merge_sql = self._build_merge_sql(
            schema=schema,
            table=table,
            staging_table=staging_table,
            pk_cols=pk_list,
            columns=safe_columns,
            incremental_col=incremental_col,
        )
        cur.execute(merge_sql)
        context.log.info(
            f"MERGE of {len(records)} records into {schema}.{table} via staging"
        )

    def _handle_csv_file(self, context: OutputContext, csv_path: str):
        """
        Load from CSV file in batches - NEVER loads entire file into memory.

        Pattern:
        1. Read CSV in 1000-row batches
        2. Insert each batch to warehouse
        3. Truncate CSV file after completion
        4. Update watermark
        """
        import csv
        import os
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

        conn = self._warehouse.get_connection()
        conn.autocommit = False

        try:
            cur = conn.cursor()

            # Full refresh: truncate table
            if incremental_strategy == "full_refresh":
                cur.execute(
                    sql.SQL("TRUNCATE TABLE {}.{}").format(
                        sql.Identifier(schema),
                        sql.Identifier(table),
                    )
                )
                context.log.info(f"TRUNCATE {schema}.{table} (full_refresh)")

            # Read CSV in batches and insert
            with open(csv_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                batch = []
                total_inserted = 0
                max_watermark_value = None

                for row in reader:
                    batch.append(row)

                    # Track max watermark value
                    if incremental_col and row.get(incremental_col):
                        if max_watermark_value is None:
                            max_watermark_value = row[incremental_col]
                        else:
                            max_watermark_value = max(
                                str(max_watermark_value), str(row[incremental_col])
                            )

                    # Insert when batch reaches 1000 rows
                    if len(batch) >= 1000:
                        self._insert_batch(
                            cur, schema, table, pk, batch, incremental_strategy, context
                        )
                        total_inserted += len(batch)
                        context.log.info(f"  Inserted {total_inserted:,} rows...")
                        batch = []

                # Insert remaining rows
                if batch:
                    self._insert_batch(
                        cur, schema, table, pk, batch, incremental_strategy, context
                    )
                    total_inserted += len(batch)

            conn.commit()
            context.log.info(
                f"Committed {total_inserted:,} records to {schema}.{table}"
            )

            # Update watermark
            if incremental_col and max_watermark_value:
                self._watermark.update_watermark(
                    layer, schema, table, max_watermark_value, total_inserted
                )
                context.log.info(f"Watermark updated to {max_watermark_value}")
            elif incremental_strategy == "full_refresh":
                run_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                self._watermark.update_watermark(
                    layer, schema, table, run_ts, total_inserted
                )
                context.log.info(f"Watermark updated (full_refresh) to {run_ts}")

            # TRUNCATE CSV file
            with open(csv_path, "w") as f:
                f.truncate(0)
            context.log.info(f"Truncated CSV file: {csv_path}")

        except Exception as e:
            conn.rollback()
            context.log.error(f"CSV load failed, rolling back: {e}")
            try:
                self._watermark.set_status(layer, schema, table, "failed", str(e))
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def _handle_ndjson_file(self, context: OutputContext, ndjson_path: str):
        """
        Load from NDJSON file via bulk load - NEVER loads entire file into memory.

        Pattern:
        1. Stream NDJSON line-by-line: collect watermark value and column names
        2. Upload NDJSON file to staging location (zero-memory — no records in memory)
        3. CREATE TEMP TABLE stg_{table} AS SELECT * FROM target WHERE 1=0  (no constraints)
        4. ACTIVATE: bulk load command into staging (not target)
        5. MERGE staging -> target (atomic upsert: update existing, insert new)
        6. Update watermark and truncate local file
        """
        import json
        import os
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

        # Normalize pk to list, splitting comma-separated composite keys (matches _handle_direct_insert)
        pk_cols = [c.strip() for c in pk.split(",")] if isinstance(pk, str) else pk
        # Stream through NDJSON once: collect watermark value and column names (zero memory)
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
        conn.autocommit = False

        try:
            cur = conn.cursor()

            # TRUNCATE for full_refresh before staging load
            if incremental_strategy == "full_refresh":
                cur.execute(
                    sql.SQL("TRUNCATE TABLE {}.{}").format(
                        sql.Identifier(schema),
                        sql.Identifier(table),
                    )
                )
                context.log.info(f"TRUNCATE {schema}.{table} (full_refresh)")

            # Step 1: Create temp staging table (auto-dropped at session end)
            # AS SELECT ... WHERE 1=0: copies column names/types, no constraints, fully nullable
            staging_table = f"stg_{table}"
            cur.execute(
                sql.SQL("CREATE TEMP TABLE {} AS SELECT * FROM {}.{} WHERE 1=0").format(
                    sql.Identifier(staging_table),
                    sql.Identifier(schema),
                    sql.Identifier(table),
                )
            )
            context.log.info(f"Created staging table {staging_table}")

            # Intersect NDJSON columns with target table columns (in target schema order).
            # Protects against: (1) NDJSON cols not in target (schema drift),
            # (2) target NOT NULL cols absent from NDJSON (would fail INSERT).
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s "
                "ORDER BY ordinal_position",
                (schema, table),
            )
            target_cols = [row[0] for row in cur.fetchall()]
            ndjson_col_set = set(columns)
            safe_columns = [c for c in target_cols if c in ndjson_col_set]
            if not safe_columns:
                raise ValueError(
                    f"No overlap between NDJSON columns and target {schema}.{table} columns. "
                    f"NDJSON: {columns[:10]}, target: {target_cols[:10]}"
                )
            extra_in_ndjson = len(columns) - len(safe_columns)
            missing_from_ndjson = len(target_cols) - len(safe_columns)
            if extra_in_ndjson or missing_from_ndjson:
                context.log.info(
                    f"Column intersection: {len(safe_columns)}/{len(target_cols)} target cols "
                    f"({extra_in_ndjson} NDJSON cols not in target, "
                    f"{missing_from_ndjson} target cols not in NDJSON — will be NULL/DEFAULT)"
                )

            # Step 2: ACTIVATE: bulk load command into staging (not target)
            # Example for Redshift:
            #   COPY {staging} ({columns}) FROM {s3_path} IAM_ROLE {iam_role} REGION {region}
            #   FORMAT AS JSON 'auto' TIMEFORMAT 'auto' EMPTYASNULL BLANKSASNULL TRUNCATECOLUMNS
            # See _RESOURCES/{db}.md for your warehouse's bulk load syntax
            raise NotImplementedError("Run /activate to configure bulk load for your warehouse. See _RESOURCES/{db}.md")

            # Step 3: MERGE staging -> target (atomic upsert: update existing, insert new)
            # For full_refresh: target was already TRUNCATEd, so MERGE only hits WHEN NOT MATCHED.
            # For incremental: MERGE updates existing rows in place — no DELETE window where
            # concurrent runs can insert duplicates.
            if incremental_strategy == "full_refresh":
                load_sql = self._build_insert_sql(
                    schema=schema,
                    table=table,
                    staging_table=staging_table,
                    pk_cols=pk_cols,
                    columns=safe_columns,
                    incremental_col=incremental_col,
                )
                cur.execute(load_sql)
                context.log.info(
                    f"INSERT into {schema}.{table} completed (full_refresh)"
                )
            else:
                merge_sql = self._build_merge_sql(
                    schema=schema,
                    table=table,
                    staging_table=staging_table,
                    pk_cols=pk_cols,
                    columns=safe_columns,
                    incremental_col=incremental_col,
                )
                cur.execute(merge_sql)
                context.log.info(f"MERGE into {schema}.{table} completed")

            conn.commit()
            context.log.info(f"Committed {total_rows:,} records to {schema}.{table}")

            # Update watermark
            if incremental_col and max_watermark_value:
                self._watermark.update_watermark(
                    layer, schema, table, max_watermark_value, total_rows
                )
                context.log.info(f"Watermark updated to {max_watermark_value}")
            elif incremental_strategy == "full_refresh":
                from datetime import datetime

                run_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                self._watermark.update_watermark(
                    layer, schema, table, run_ts, total_rows
                )
                context.log.info(f"Watermark updated (full_refresh) to {run_ts}")

            # Truncate local NDJSON file
            with open(ndjson_path, "w") as f:
                f.truncate(0)
            context.log.info(f"Truncated NDJSON file: {ndjson_path}")

        except Exception as e:
            conn.rollback()
            context.log.error(f"NDJSON bulk load failed, rolling back: {e}")
            try:
                self._watermark.set_status(layer, schema, table, "failed", str(e))
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def _insert_batch(
        self, cur, schema, table, pk, batch, incremental_strategy, context
    ):
        """Insert a batch of records (DELETE + INSERT for upsert)."""
        if not batch:
            return

        # For incremental strategies: DELETE existing records with these PKs
        if incremental_strategy != "full_refresh":
            ids = [row[pk] for row in batch if row.get(pk)]
            if ids:
                delete_query = sql.SQL("DELETE FROM {}.{} WHERE {} IN ({})").format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                    sql.Identifier(pk),
                    sql.SQL(", ").join([sql.Placeholder()] * len(ids)),
                )
                cur.execute(delete_query, tuple(ids))

        # INSERT batch
        columns = list(batch[0].keys())

        # Add audit columns if not present
        from datetime import datetime as dt

        if "inserted_at" not in columns:
            columns.extend(["inserted_at", "updated_at"])
            for row in batch:
                now = dt.now()
                row["inserted_at"] = now
                row["updated_at"] = now
        elif "updated_at" not in columns:
            columns.append("updated_at")
            for row in batch:
                row["updated_at"] = dt.now()

        insert_query = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )

        for row in batch:
            values = tuple(row.get(c) for c in columns)
            cur.execute(insert_query, values)

    def load_input(self, context: InputContext):
        """Load data from warehouse for downstream assets."""
        meta = context.upstream_output.metadata or {}
        schema = meta.get("target_schema")
        table = meta.get("target_table")

        if not schema or not table:
            raise ValueError(
                "Upstream asset must provide target_schema and target_table in metadata"
            )

        conn = self._warehouse.get_connection()
        try:
            with conn.cursor() as cur:
                query = sql.SQL("SELECT * FROM {}.{}").format(
                    sql.Identifier(schema),
                    sql.Identifier(table),
                )
                cur.execute(query)
                if not cur.description:
                    return []
                col_names = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(col_names, row)) for row in rows]
        finally:
            conn.close()


@io_manager(required_resource_keys={"warehouse", "watermark", "s3"})
def warehouse_io_manager(context):
    """Factory for WarehouseIOManager. Injects shared resources."""
    return WarehouseIOManager(
        context.resources.warehouse, context.resources.watermark, context.resources.s3
    )
