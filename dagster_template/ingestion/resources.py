"""
Ingestion resources — re-exports from shared dagster/resources.py.

All resources are defined in dagster/resources.py (ConfigurableResource classes).
This file exists for backward compatibility with ingestion/__init__.py imports.
"""

import sys
from pathlib import Path

_DAGSTER_DIR = Path(__file__).resolve().parent.parent
if str(_DAGSTER_DIR) not in sys.path:
    sys.path.insert(0, str(_DAGSTER_DIR))

from resources import get_all_resources  # noqa: F401
