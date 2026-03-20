#!/usr/bin/env python3
"""Test: Load extracted NDJSON into Snowflake via PUT + COPY INTO + MERGE.

Validates the full pipeline path without Dagster.
"""

import json
import os
import sys
from pathlib import Path
from glob import glob

import snowflake.connector

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from load_config import load_config

cfg = load_config()
target = cfg["target"]

ndjson_dir = _REPO / "_LOCAL_FILES" / "meta"

# Find latest NDJSON files
campaigns_files = sorted(ndjson_dir.glob("CAMPAIGNS_*.ndjson"))
insights_files = sorted(ndjson_dir.glob("CAMPAIGN_INSIGHTS_*.ndjson"))

if not campaigns_files:
    print("No campaigns NDJSON found. Run test_meta_extractor.py first.")
    sys.exit(1)

campaigns_ndjson = str(campaigns_files[-1])
insights_ndjson = str(insights_files[-1]) if insights_files else None

conn = snowflake.connector.connect(
    account=target["account"],
    user=target["username"],
    password=target["password"],
    database=target["database"],
    warehouse=target.get("warehouse", "COMPUTE_WH"),
    role=target.get("role", "ACCOUNTADMIN"),
)
cur = conn.cursor()


def load_ndjson(cur, ndjson_path, schema, table, pk_cols, strategy):
    """Replicate the IO manager's NDJSON load path."""
    print(f"\nLoading {ndjson_path}")
    print(f"  Target: {schema}.{table} | PK: {pk_cols} | Strategy: {strategy}")

    # Count records
    with open(ndjson_path) as f:
        first_line = f.readline()
        columns = list(json.loads(first_line).keys())
        row_count = 1 + sum(1 for _ in f)
    print(f"  Records: {row_count}, Columns: {columns}")

    if strategy == "full_refresh":
        cur.execute(f'TRUNCATE TABLE "{schema}"."{table}"')
        print(f"  TRUNCATED {schema}.{table}")

    staging = f"stg_{table}"
    cur.execute(
        f'CREATE OR REPLACE TEMPORARY TABLE "{staging}" '
        f'AS SELECT * FROM "{schema}"."{table}" WHERE 1=0'
    )

    ndjson_path_fwd = ndjson_path.replace("\\", "/")
    cur.execute(
        f"PUT 'file://{ndjson_path_fwd}' @%\"{staging}\" "
        f"AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
    )
    put_result = cur.fetchall()
    print(f"  PUT: {put_result[0][6] if put_result else 'unknown'}")

    # Get safe columns (intersection of NDJSON keys and table columns)
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (schema, table),
    )
    target_cols = [r[0] for r in cur.fetchall()]
    col_upper = {c.upper() for c in columns}
    safe_cols = [tc for tc in target_cols if tc.upper() in col_upper]
    print(f"  Safe columns: {len(safe_cols)}/{len(target_cols)}")

    col_list = ", ".join(f'"{c}"' for c in safe_cols)
    cur.execute(
        f'COPY INTO "{staging}" '
        f'FROM @%"{staging}" '
        f'FILE_FORMAT = (TYPE = JSON) '
        f'MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE'
    )
    copy_result = cur.fetchall()
    rows_loaded = copy_result[0][3] if copy_result else 0
    print(f"  COPY: {rows_loaded} rows loaded")

    # MERGE or INSERT
    pk_partition = ", ".join(f'"{c}"' for c in pk_cols)

    if strategy == "full_refresh":
        sql = (
            f'INSERT INTO "{schema}"."{table}" ({col_list}) '
            f'SELECT {col_list} FROM ('
            f'  SELECT *, ROW_NUMBER() OVER (PARTITION BY {pk_partition} ORDER BY 1) AS rn'
            f'  FROM "{staging}"'
            f') sub WHERE rn = 1'
        )
    else:
        on_parts = " AND ".join(f'tgt."{c}" = src."{c}"' for c in pk_cols)
        non_pk = [c for c in safe_cols if c not in pk_cols]
        set_parts = ", ".join(f'tgt."{c}" = src."{c}"' for c in non_pk)
        src_vals = ", ".join(f'src."{c}"' for c in safe_cols)
        sql = (
            f'MERGE INTO "{schema}"."{table}" AS tgt '
            f'USING ('
            f'  SELECT {col_list} FROM ('
            f'    SELECT *, ROW_NUMBER() OVER (PARTITION BY {pk_partition} ORDER BY 1) AS rn'
            f'    FROM "{staging}"'
            f'  ) sub WHERE rn = 1'
            f') src '
            f'ON {on_parts} '
            f'WHEN MATCHED THEN UPDATE SET {set_parts} '
            f'WHEN NOT MATCHED THEN INSERT ({col_list}) VALUES ({src_vals})'
        )

    cur.execute(sql)
    print(f"  {'INSERT' if strategy == 'full_refresh' else 'MERGE'}: OK")

    cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
    final_count = cur.fetchone()[0]
    print(f"  Final row count: {final_count}")
    return final_count


try:
    cur.execute("USE SCHEMA RAW_META")

    # Load campaigns
    count1 = load_ndjson(
        cur, campaigns_ndjson, "RAW_META", "CAMPAIGNS", ["ID"], "full_refresh"
    )

    # Load insights
    if insights_ndjson:
        count2 = load_ndjson(
            cur, insights_ndjson, "RAW_META", "CAMPAIGN_INSIGHTS",
            ["CAMPAIGN_ID", "DATE_START"], "timestamp"
        )

    # Verify with sample queries
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    cur.execute("SELECT COUNT(*), COUNT(DISTINCT ID) FROM RAW_META.CAMPAIGNS")
    r = cur.fetchone()
    print(f"CAMPAIGNS: {r[0]} rows, {r[1]} unique IDs")

    cur.execute(
        "SELECT COUNT(*), COUNT(DISTINCT CAMPAIGN_ID), MIN(DATE_START), MAX(DATE_START) "
        "FROM RAW_META.CAMPAIGN_INSIGHTS"
    )
    r = cur.fetchone()
    print(f"CAMPAIGN_INSIGHTS: {r[0]} rows, {r[1]} campaigns, dates {r[2]} to {r[3]}")

    # Check VARIANT columns
    cur.execute("SELECT ACTIONS FROM RAW_META.CAMPAIGN_INSIGHTS LIMIT 1")
    row = cur.fetchone()
    print(f"VARIANT check (actions): type={type(row[0]).__name__}, preview={str(row[0])[:80]}")

    print("\nAll loads successful.")

finally:
    cur.close()
    conn.close()
