#!/usr/bin/env python3
"""DDL: Create RAW_META schema and tables (CAMPAIGNS, CAMPAIGN_INSIGHTS) in Snowflake.

Step 2 of Universal Pipeline Architecture.
Based on Step 1 sample data inspection (see data/temp/STEP1_HANDOFF.md).
"""

import sys
from pathlib import Path

import snowflake.connector

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
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
        database=target["database"],
        warehouse=target.get("warehouse", "COMPUTE_WH"),
        role=target.get("role", "ACCOUNTADMIN"),
    )
    cur = conn.cursor()

    try:
        cur.execute("CREATE SCHEMA IF NOT EXISTS RAW_META")
        print("Schema RAW_META: OK")

        # ── CAMPAIGNS ───────────────────────────────────────
        # PK: ID (source-native string)
        # Strategy: full_refresh (~500 rows)
        # VARIANT: SPECIAL_AD_CATEGORIES (JSON array)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS RAW_META.CAMPAIGNS (
                ID                      VARCHAR(100)    NOT NULL,
                NAME                    VARCHAR(500),
                STATUS                  VARCHAR(50),
                EFFECTIVE_STATUS        VARCHAR(50),
                OBJECTIVE               VARCHAR(100),
                BUYING_TYPE             VARCHAR(50),
                BID_STRATEGY            VARCHAR(100),
                DAILY_BUDGET            VARCHAR(50),
                LIFETIME_BUDGET         VARCHAR(50),
                BUDGET_REMAINING        VARCHAR(50),
                START_TIME              VARCHAR(100),
                STOP_TIME               VARCHAR(100),
                CREATED_TIME            VARCHAR(100),
                UPDATED_TIME            VARCHAR(100),
                SPECIAL_AD_CATEGORIES   VARIANT,
                INSERTED_AT             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                UPDATED_AT              TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                PRIMARY KEY (ID)
            )
        """)
        print("Table RAW_META.CAMPAIGNS: OK")

        # ── CAMPAIGN_INSIGHTS ───────────────────────────────
        # PK: CAMPAIGN_ID + DATE_START (composite)
        # Strategy: timestamp on DATE_START
        # VARIANT: ACTIONS, COST_PER_ACTION_TYPE (JSON arrays)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS RAW_META.CAMPAIGN_INSIGHTS (
                CAMPAIGN_ID             VARCHAR(100)    NOT NULL,
                CAMPAIGN_NAME           VARCHAR(500),
                DATE_START              DATE            NOT NULL,
                DATE_STOP               DATE,
                IMPRESSIONS             BIGINT,
                CLICKS                  BIGINT,
                SPEND                   FLOAT,
                CPC                     FLOAT,
                CPM                     FLOAT,
                CTR                     FLOAT,
                CPP                     FLOAT,
                REACH                   BIGINT,
                FREQUENCY               FLOAT,
                ACTIONS                 VARIANT,
                COST_PER_ACTION_TYPE    VARIANT,
                INSERTED_AT             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                UPDATED_AT              TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                PRIMARY KEY (CAMPAIGN_ID, DATE_START)
            )
        """)
        print("Table RAW_META.CAMPAIGN_INSIGHTS: OK")

        # Verify
        for t in ["CAMPAIGNS", "CAMPAIGN_INSIGHTS"]:
            cur.execute(f"SELECT COUNT(*) FROM RAW_META.{t}")
            print(f"  {t}: {cur.fetchone()[0]} rows")

    finally:
        cur.close()
        conn.close()

    print("\nDDL complete.")


if __name__ == "__main__":
    main()
