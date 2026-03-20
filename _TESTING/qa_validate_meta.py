#!/usr/bin/env python3
"""QA validation for Meta API pipeline implementation."""
import json
import sys
from pathlib import Path

import snowflake.connector

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from load_config import load_config

# Load config and establish connection
cfg = load_config()
target = cfg["target"]

print("=" * 80)
print("QA VALIDATION: Meta API Pipeline Implementation")
print("=" * 80)

try:
    conn = snowflake.connector.connect(
        account=target["account"],
        user=target["username"],
        password=target["password"],
        database=target["database"],
        warehouse=target.get("warehouse", "COMPUTE_WH"),
        role=target.get("role", "ACCOUNTADMIN"),
    )
    cur = conn.cursor()

    print("\n1. TABLE EXISTENCE CHECK")
    print("-" * 80)
    for table in ["CAMPAIGNS", "CAMPAIGN_INSIGHTS"]:
        cur.execute(f"""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = '{table}' AND TABLE_SCHEMA = 'RAW_META'
        """)
        result = cur.fetchone()
        status = "EXISTS" if result else "MISSING"
        print(f"   RAW_META.{table}: {status}")

    print("\n2. ROW COUNT CHECK")
    print("-" * 80)
    for table in ["CAMPAIGNS", "CAMPAIGN_INSIGHTS"]:
        cur.execute(f"SELECT COUNT(*) FROM RAW_META.{table}")
        count = cur.fetchone()[0]
        print(f"   RAW_META.{table}: {count:,} rows")

    print("\n3. PRIMARY KEY INTEGRITY CHECK")
    print("-" * 80)
    # Campaigns: check for null IDs
    cur.execute("SELECT COUNT(*) FROM RAW_META.CAMPAIGNS WHERE ID IS NULL")
    null_count = cur.fetchone()[0]
    print(f"   CAMPAIGNS - Null PKs: {null_count} (should be 0)")

    # Campaigns: check for duplicates
    cur.execute("""
        SELECT ID, COUNT(*) as cnt FROM RAW_META.CAMPAIGNS
        GROUP BY ID HAVING COUNT(*) > 1
    """)
    dups = cur.fetchall()
    print(f"   CAMPAIGNS - Duplicate PKs: {len(dups)} (should be 0)")
    if dups:
        for row in dups:
            print(f"      {row[0]}: {row[1]} duplicates")

    # Campaign Insights: check for null composite key
    cur.execute("""
        SELECT COUNT(*) FROM RAW_META.CAMPAIGN_INSIGHTS
        WHERE CAMPAIGN_ID IS NULL OR DATE_START IS NULL
    """)
    null_count = cur.fetchone()[0]
    print(f"   CAMPAIGN_INSIGHTS - Null PKs: {null_count} (should be 0)")

    # Campaign Insights: check for duplicates
    cur.execute("""
        SELECT CAMPAIGN_ID, DATE_START, COUNT(*) as cnt
        FROM RAW_META.CAMPAIGN_INSIGHTS
        GROUP BY CAMPAIGN_ID, DATE_START HAVING COUNT(*) > 1
    """)
    dups = cur.fetchall()
    print(f"   CAMPAIGN_INSIGHTS - Duplicate PKs: {len(dups)} (should be 0)")

    print("\n4. AUDIT COLUMNS CHECK")
    print("-" * 80)
    # Campaigns
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(INSERTED_AT) as non_null_inserted,
            COUNT(UPDATED_AT) as non_null_updated
        FROM RAW_META.CAMPAIGNS
    """)
    row = cur.fetchone()
    print(f"   CAMPAIGNS:")
    print(f"      Total rows: {row[0]}")
    print(f"      INSERTED_AT non-null: {row[1]} (should be {row[0]})")
    print(f"      UPDATED_AT non-null: {row[2]} (should be {row[0]})")

    # Campaign Insights
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(INSERTED_AT) as non_null_inserted,
            COUNT(UPDATED_AT) as non_null_updated
        FROM RAW_META.CAMPAIGN_INSIGHTS
    """)
    row = cur.fetchone()
    print(f"   CAMPAIGN_INSIGHTS:")
    print(f"      Total rows: {row[0]}")
    print(f"      INSERTED_AT non-null: {row[1]} (should be {row[0]})")
    print(f"      UPDATED_AT non-null: {row[2]} (should be {row[0]})")

    print("\n5. VARIANT COLUMN POPULATION CHECK")
    print("-" * 80)
    # CAMPAIGNS.SPECIAL_AD_CATEGORIES
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(SPECIAL_AD_CATEGORIES) as non_null
        FROM RAW_META.CAMPAIGNS
    """)
    row = cur.fetchone()
    print(f"   CAMPAIGNS.SPECIAL_AD_CATEGORIES: {row[1]}/{row[0]} non-null")

    # CAMPAIGN_INSIGHTS.ACTIONS
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(ACTIONS) as non_null
        FROM RAW_META.CAMPAIGN_INSIGHTS
    """)
    row = cur.fetchone()
    print(f"   CAMPAIGN_INSIGHTS.ACTIONS: {row[1]}/{row[0]} non-null")

    # CAMPAIGN_INSIGHTS.COST_PER_ACTION_TYPE
    cur.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(COST_PER_ACTION_TYPE) as non_null
        FROM RAW_META.CAMPAIGN_INSIGHTS
    """)
    row = cur.fetchone()
    print(f"   CAMPAIGN_INSIGHTS.COST_PER_ACTION_TYPE: {row[1]}/{row[0]} non-null")

    print("\n6. FULLY NULL COLUMN CHECK")
    print("-" * 80)

    # Get all columns for both tables
    cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'CAMPAIGNS' AND TABLE_SCHEMA = 'RAW_META'
        ORDER BY ORDINAL_POSITION
    """)
    campaign_cols = [row[0] for row in cur.fetchall()]

    cur.execute("""
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'CAMPAIGN_INSIGHTS' AND TABLE_SCHEMA = 'RAW_META'
        ORDER BY ORDINAL_POSITION
    """)
    insight_cols = [row[0] for row in cur.fetchall()]

    fully_null_cols = []

    # Check CAMPAIGNS columns
    for col in campaign_cols:
        cur.execute(f"""
            SELECT COUNT(*) as total, COUNT({col}) as non_null
            FROM RAW_META.CAMPAIGNS
        """)
        total, non_null = cur.fetchone()
        if total > 0 and non_null == 0 and col not in ["INSERTED_AT", "UPDATED_AT"]:
            fully_null_cols.append(("CAMPAIGNS", col, total))
            print(f"   WARNING: CAMPAIGNS.{col} is fully NULL ({total} rows)")

    # Check CAMPAIGN_INSIGHTS columns
    for col in insight_cols:
        cur.execute(f"""
            SELECT COUNT(*) as total, COUNT({col}) as non_null
            FROM RAW_META.CAMPAIGN_INSIGHTS
        """)
        total, non_null = cur.fetchone()
        if total > 0 and non_null == 0 and col not in ["INSERTED_AT", "UPDATED_AT"]:
            fully_null_cols.append(("CAMPAIGN_INSIGHTS", col, total))
            print(f"   WARNING: CAMPAIGN_INSIGHTS.{col} is fully NULL ({total} rows)")

    if not fully_null_cols:
        print("   No fully NULL columns detected (good!)")

    print("\n7. WATERMARK CHECK")
    print("-" * 80)
    # Check if RAW_METADATA schema exists
    cur.execute("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.SCHEMATA
        WHERE SCHEMA_NAME = 'RAW_METADATA'
    """)
    has_schema = cur.fetchone()[0] > 0
    if has_schema:
        cur.execute("""
            SELECT COUNT(*) FROM RAW_METADATA.WATERMARKS
            WHERE SOURCE_NAME = 'meta'
        """)
        wm_count = cur.fetchone()[0]
        print(f"   Watermarks for 'meta': {wm_count}")

        if wm_count > 0:
            cur.execute("""
                SELECT TABLE_NAME, INCREMENTAL_COLUMN, WATERMARK_VALUE, UPDATED_AT
                FROM RAW_METADATA.WATERMARKS
                WHERE SOURCE_NAME = 'meta'
                ORDER BY TABLE_NAME
            """)
            for row in cur.fetchall():
                print(f"      {row[0]}: {row[1]} = {row[2]}")
    else:
        print("   RAW_METADATA schema not found (may not be created yet)")

    print("\n8. RECENT DATA CHECK")
    print("-" * 80)
    # CAMPAIGNS
    cur.execute("SELECT MAX(UPDATED_AT) FROM RAW_META.CAMPAIGNS")
    max_updated = cur.fetchone()[0]
    print(f"   CAMPAIGNS max UPDATED_AT: {max_updated}")

    # CAMPAIGN_INSIGHTS
    cur.execute("SELECT MAX(DATE_START) FROM RAW_META.CAMPAIGN_INSIGHTS")
    max_date = cur.fetchone()[0]
    print(f"   CAMPAIGN_INSIGHTS max DATE_START: {max_date}")

    print("\n9. SCHEMA COLUMN LIST")
    print("-" * 80)
    print("   CAMPAIGNS columns:")
    for col in campaign_cols:
        print(f"      - {col}")

    print("   CAMPAIGN_INSIGHTS columns:")
    for col in insight_cols:
        print(f"      - {col}")

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)

finally:
    cur.close()
    conn.close()
