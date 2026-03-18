"""Environment-specific settings driven by DAGSTER_ENV.

DAGSTER_ENV controls: dbt target, Slack alert channel, schedule activation.
Defaults to 'dev' so local runs are always safe.

Environments:
  dev         - local Dagster, _dev schemas, 30-day data window, schedules OFF
  integration - local Dagster, _dev schemas, full data, schedules OFF
  prod        - K8s Dagster, prod schemas, full data, schedules ON
"""

import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

_ENVIRONMENTS = {
    "dev": {
        "dbt_target": "dev",
        "slack_channel": "#dev-pipeline-alerts",
        "schedules_enabled": False,
    },
    "integration": {
        "dbt_target": "integration",
        "slack_channel": "#dev-pipeline-alerts",
        "schedules_enabled": False,
    },
    "prod": {
        "dbt_target": "prod",
        "slack_channel": "#data-pipeline-alerts",
        "schedules_enabled": True,
    },
}

_DAGSTER_ENV = os.environ.get("DAGSTER_ENV", "dev")

# Allow config.json to override per-env settings if present
try:
    from load_config import load_config

    _cfg_envs = load_config().get("environments", {})
    if _DAGSTER_ENV in _cfg_envs:
        _ENVIRONMENTS[_DAGSTER_ENV].update(_cfg_envs[_DAGSTER_ENV])
except Exception:
    pass

_env_cfg = _ENVIRONMENTS.get(_DAGSTER_ENV, _ENVIRONMENTS["dev"])

DBT_TARGET: str = os.environ.get("DBT_TARGET", _env_cfg["dbt_target"])
SLACK_CHANNEL: str = _env_cfg["slack_channel"]
SCHEDULES_ENABLED: bool = _env_cfg["schedules_enabled"]
DAGSTER_ENV: str = _DAGSTER_ENV
