"""
DDL script — create raw_example_api schema and tables.

ACTIVATE: Update schema name, table name, and column definitions.
Run: python dagster/ingestion/raw/_example_api_source/ddl/create_schema.py
"""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from load_config import load_config
import psycopg2


def create_schema_and_tables():
    config = load_config()
    target = config["target"]

    conn = psycopg2.connect(
        host=target["host"],
        port=int(target.get("port", 5432)),
        database=target["database"],
        user=target["username"],
        password=target["password"],
        sslmode="require",
    )

    try:
        cur = conn.cursor()

        cur.execute("CREATE SCHEMA IF NOT EXISTS raw_example_api")

        # ACTIVATE: Replace with your actual column definitions
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_example_api.records (
                id          VARCHAR(255) PRIMARY KEY,
                name        VARCHAR(500),
                status      VARCHAR(50),
                created_at  TIMESTAMP,
                updated_at  TIMESTAMP,
                metadata    JSONB,               -- Use JSONB (Postgres) / SUPER (Redshift) / VARIANT (Snowflake)
                inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at_ TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        print("Schema and tables created successfully")

    finally:
        conn.close()


if __name__ == "__main__":
    create_schema_and_tables()
