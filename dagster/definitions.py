"""
Dagster Definitions - main entry point.

Run locally:  dagster dev -f dagster/definitions.py
Deploy:       loaded by gRPC server

Structure:
  - ingestion/definitions.py    -> Raw data extraction (API/DB sources)
  - transformation/definitions.py -> dbt models (staging → core → obt → report)
  - systems/definitions.py       -> Systems: maintenance jobs (e.g. refresh read grants)

This file merges all layer definitions into a single entry point.
"""

import sys
from pathlib import Path

from dagster import Definitions

# Ensure dagster package is importable
_DAGSTER_DIR = Path(__file__).resolve().parent
if str(_DAGSTER_DIR) not in sys.path:
    sys.path.insert(0, str(_DAGSTER_DIR))

# Import ingestion layer definitions
from ingestion import definitions as _ingestion_module  # noqa: E402

# Import transformation layer definitions (dbt)
from transformation import definitions as _transformation_module  # noqa: E402

# Import systems layer definitions (maintenance)
from systems import definitions as _systems_module  # noqa: E402

defs = Definitions.merge(
    _ingestion_module.ingestion_defs,
    _transformation_module.transformation_defs,
    _systems_module.systems_defs,
)
