"""Ingestion layer definitions - raw data extraction assets, jobs, schedules, sensors."""

import os
import sys
from pathlib import Path

from dagster import Definitions, EnvVar
from dagster_slack import SlackResource

_INGESTION_DIR = Path(__file__).resolve().parent
_DAGSTER_DIR = _INGESTION_DIR.parent
_PROJECT_ROOT = _DAGSTER_DIR.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_DAGSTER_DIR) not in sys.path:
    sys.path.insert(0, str(_DAGSTER_DIR))

from env_config import SCHEDULES_ENABLED
from load_config import load_config
from resources import get_all_resources
from io_managers import warehouse_io_manager
from asset_factory import build_assets_from_yaml

from ingestion.jobs import jobs as ingestion_jobs
from dbt_jobs import dbt_freshness_schedule
from ingestion.schedules import schedules as ingestion_schedules
from ingestion.sensors import (
    slack_asset_check_failure_on_run_failure,
    slack_asset_check_failure_on_run_success,
    slack_run_failure_sensor,
)

# Build factory-generated assets from YAML configs
factory_assets, factory_checks = build_assets_from_yaml()

# Build resources
load_config()  # ensure .env is loaded
_resources = get_all_resources()
_resources["io_manager"] = warehouse_io_manager

# Add Slack resource if token is available
if os.environ.get("SLACK_BOT_TOKEN"):
    _resources["slack"] = SlackResource(token=EnvVar("SLACK_BOT_TOKEN"))

# Ingestion layer definitions
ingestion_defs = Definitions(
    assets=factory_assets,
    asset_checks=factory_checks,
    jobs=ingestion_jobs,
    schedules=[*ingestion_schedules, dbt_freshness_schedule]
    if SCHEDULES_ENABLED
    else [],
    sensors=[
        slack_run_failure_sensor,
        slack_asset_check_failure_on_run_failure,
        slack_asset_check_failure_on_run_success,
    ],
    resources=_resources,
)
