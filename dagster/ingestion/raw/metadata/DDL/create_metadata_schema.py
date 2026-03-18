"""Bootstrap: create BIO database, METADATA schema, and PIPELINE_WATERMARKS table in Snowflake."""

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

        # Add PK if not exists
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
