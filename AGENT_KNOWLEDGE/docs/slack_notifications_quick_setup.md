# Slack Notifications Quick Setup

**For existing Dagster projects that need to add Slack failure notifications.**

## Overview

ONE sensor monitors ALL jobs automatically. No per-job configuration needed.

## Setup Steps

### 1. Create Sensor File

Create `dagster/ingestion/sensors.py` - copy the full sensor code from [3_universal_dagster_architecture.md](../references/3_universal_dagster_architecture.md#slack-failure-notifications-sensor-based)

### 2. Export Sensor

Add to `dagster/ingestion/__init__.py`:
```python
from ingestion.sensors import slack_run_failure_sensor
```

### 3. Register in Definitions

Update `dagster/definitions.py`:
```python
from dagster_slack import SlackResource, EnvVar

from ingestion import (
    # ... existing imports ...
    slack_run_failure_sensor,  # ADD THIS
)

# Add Slack resource (after building other resources)
if os.environ.get("SLACK_BOT_TOKEN"):
    _resources["slack"] = SlackResource(token=EnvVar("SLACK_BOT_TOKEN"))

defs = Definitions(
    assets=all_assets,
    jobs=[...],
    sensors=[slack_run_failure_sensor],  # ADD THIS
    resources=_resources,
)
```

### 4. Environment Variables

Add to `.env`:
```bash
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_ALERT_CHANNEL={{SLACK_CHANNEL_PROD}}
```

For dev/staging alerts use a separate channel:
```bash
SLACK_ALERT_CHANNEL={{SLACK_CHANNEL_DEV}}
```

### 5. Install Dependency

```bash
pip install dagster-slack
```

### 6. Reload

Reload definitions in Dagster UI: **Deployment → Reload**

## Testing

1. Add `raise Exception("TEST")` to an asset
2. Run the job
3. Wait 30 seconds
4. Check Slack for notification
5. Remove test error

## Key Points

- ONE sensor for ALL jobs
- Monitors every 30 seconds
- No per-job configuration
- Minimal resource usage

For detailed explanation, see [Universal Dagster Architecture](../references/3_universal_dagster_architecture.md#slack-failure-notifications-sensor-based)
