"""
Create metadata schema and pipeline_watermarks table.

This table is required by the WatermarkResource and all pipeline assets.
Run ONCE per new project/warehouse.

Run: python dagster/ingestion/raw/_TEMPLATE_source/ddl/create_metadata_schema.py
"""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from load_config import load_config
import psycopg2


def create_metadata_schema():
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

        cur.execute("CREATE SCHEMA IF NOT EXISTS metadata")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS metadata.pipeline_watermarks (
                id              SERIAL PRIMARY KEY,
                layer           VARCHAR(50)  NOT NULL,
                target_schema   VARCHAR(255) NOT NULL,
                target_table    VARCHAR(255) NOT NULL,
                watermark_value VARCHAR(255),
                rows_processed  INTEGER      DEFAULT 0,
                status          VARCHAR(50)  DEFAULT 'pending',
                error_message   VARCHAR(500),
                last_run_at     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                last_success_at TIMESTAMP,
                updated_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (layer, target_schema, target_table)
            )
        """)

        conn.commit()
        print("metadata.pipeline_watermarks created successfully")

    finally:
        conn.close()


if __name__ == "__main__":
    create_metadata_schema()
