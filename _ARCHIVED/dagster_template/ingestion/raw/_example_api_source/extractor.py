"""
Example API extractor — template for API sources.

Copy this file and customize for your specific API.
This implements the zero-memory streaming pattern:
  1. Fetch from API page by page
  2. Write to local NDJSON file
  3. Return file path (IO manager handles S3 COPY)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add repo root to path
_REPO = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from load_config import load_config


def extract(context, from_date: str, to_date: str, asset_config: dict) -> str:
    """
    Extract records from API and write to NDJSON file.

    Returns: str — path to NDJSON file (IO manager uploads to S3 and COPYs to warehouse)
    """
    target_table = asset_config["target_table"]
    target_schema = asset_config["target_schema"]

    data_dir = Path(__file__).parent / "data" / "temp"
    data_dir.mkdir(parents=True, exist_ok=True)
    ndjson_path = data_dir / f"{target_table}.ndjson"

    # Get API resource from context
    api_resource = context.resources.example_api

    context.log.info(f"Extracting {target_table} from {from_date} to {to_date}")

    with open(ndjson_path, "w", encoding="utf-8") as f:
        total_rows = 0
        page = 1

        while True:
            data = api_resource.fetch_records(from_date, to_date, page=page)
            records = data.get("records") or data.get("data") or []

            if not records:
                break

            for record in records:
                f.write(json.dumps(record, default=str) + "\n")
                total_rows += 1

            page_count = data.get("pageCount") or data.get("totalPages") or 0
            if not records or page >= page_count:
                break
            page += 1

    context.log.info(f"Extracted {total_rows:,} records to {ndjson_path}")
    return str(ndjson_path)
