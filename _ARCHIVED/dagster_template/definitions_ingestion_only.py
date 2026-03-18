"""
Ingestion-only definitions - for running raw sync jobs without dbt/transformation.
Run: dagster job execute -f dagster/definitions_ingestion_only.py -j raw_example_sync
"""

import sys
from pathlib import Path

_DAGSTER_DIR = Path(__file__).resolve().parent
if str(_DAGSTER_DIR) not in sys.path:
    sys.path.insert(0, str(_DAGSTER_DIR))

from ingestion import definitions as _ingestion_module  # noqa: E402

defs = _ingestion_module.ingestion_defs
