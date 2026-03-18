"""Systems layer definitions - maintenance jobs (e.g. refresh read grants)."""

import sys
from pathlib import Path

from dagster import Definitions

_SYSTEMS_DIR = Path(__file__).resolve().parent
_DAGSTER_DIR = _SYSTEMS_DIR.parent
_PROJECT_ROOT = _DAGSTER_DIR.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_DAGSTER_DIR) not in sys.path:
    sys.path.insert(0, str(_DAGSTER_DIR))

from env_config import SCHEDULES_ENABLED

from systems.assets import assets as systems_assets
from systems.jobs import jobs as systems_jobs
from systems.schedules import schedules as systems_schedules

# No resources: use merged defs' resources (ingestion provides warehouse, etc.)
systems_defs = Definitions(
    assets=systems_assets,
    jobs=systems_jobs,
    schedules=systems_schedules if SCHEDULES_ENABLED else [],
)
