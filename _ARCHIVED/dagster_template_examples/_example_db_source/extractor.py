"""
Example DB extractor — template for internal database sources.

Copy this file and customize for your specific database.
Uses zero-memory streaming pattern with fetchmany(1000).
"""

import json
import sys
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from load_config import load_config


def extract(context, from_date: str, to_date: str, asset_config: dict) -> str:
    """
    Stream records from source DB to NDJSON file.

    Returns: str — path to NDJSON file
    """
    target_table = asset_config["target_table"]
    target_schema = asset_config["target_schema"]
    incremental_strategy = asset_config.get("incremental_strategy", "full_refresh")
    incremental_column = asset_config.get("incremental_column")

    # Get watermark
    watermark_resource = context.resources.watermark
    watermark_value = watermark_resource.get_watermark("raw", target_schema, target_table)

    data_dir = Path(__file__).parent / "data" / "temp"
    data_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = data_dir / f"{target_table}.ndjson"

    def json_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return str(obj)

    db_resource = context.resources.example_db
    conn = db_resource.get_connection()

    try:
        cur = conn.cursor()

        if incremental_strategy == "full_refresh":
            cur.execute(f'SELECT * FROM "{target_table}"')
        elif watermark_value:
            cur.execute(
                f'SELECT * FROM "{target_table}" WHERE "{incremental_column}" > %s',
                (watermark_value,)
            )
        else:
            cur.execute(f'SELECT * FROM "{target_table}"')

        columns = [desc[0] for desc in cur.description]

        with open(ndjson_path, "w", encoding="utf-8") as f:
            total_rows = 0
            while True:
                rows = cur.fetchmany(1000)  # NEVER use fetchall()
                if not rows:
                    break
                for row in rows:
                    record = dict(zip(columns, row))
                    f.write(json.dumps(record, default=json_serializer) + "\n")
                    total_rows += 1

                if total_rows % 10000 == 0:
                    context.log.info(f"  Streamed {total_rows:,} rows...")

        context.log.info(f"Extracted {total_rows:,} records to {ndjson_path}")
        return str(ndjson_path)

    finally:
        conn.close()
