# Dagster One-Time Setup

**Human-facing steps for initial Dagster setup.** Not used by the AI when creating DAGs. For DAG design and conventions, see `universal_dagster_architecture.md`.

**Environment:** Python 3.11 only (see `.python-version`). Use 3.11 for `dagster dev` and all pipeline runs.

---

## Slack Integration

**Goal:** Post to Slack when a run fails, when an asset check fails, or (optionally) when an asset is stale.

### Prerequisites

1. **Slack app with bot token**
   - Go to [api.slack.com/apps](https://api.slack.com/apps) → your app → **OAuth & Permissions**.
   - Add Bot Token Scopes: `chat:write`, and `chat:write.public` (if posting to channels the app isn't in).
   - Click **Install to Workspace** (requires admin approval if your workspace requires it). After install, copy the **Bot User OAuth Token** (starts with `xoxb-`). This is the only token the Dagster integration uses—not Client ID/Secret or Signing Secret.
   - Put it in `.env`: `SLACK_BOT_TOKEN=xoxb-...`. Do not commit.

2. **Channel**
   - Create a channel (e.g. `#data-pipeline-alerts`) or pick an existing one. Invite the app to the channel (e.g. `/invite @YourAppName`).

3. **Dagster dependency**
   - `pip install dagster-slack` (or add `dagster-slack` to `requirements-dagster.txt`).

### Step 1: Slack resource

In `dagster/resources.py` (or wherever you define resources):

```python
import os
from dagster_slack import SlackResource

def get_slack_resource():
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        return None  # or a no-op mock for local dev
    return SlackResource(token=token)
```

Register in Definitions:

```python
resources = {
    "warehouse": warehouse_resource,
    # ...
}
if get_slack_resource():
    resources["slack"] = get_slack_resource()

defs = Definitions(assets=..., jobs=..., schedules=..., resources=resources)
```

### Step 2: Run failure → Slack

**Run failure hook (recommended):** On any run failure, post to Slack.

```python
from dagster import failure_hook

@failure_hook
def slack_on_run_failure(context):
    slack = context.resources.get("slack")
    if not slack:
        return
    slack.get_client().chat_postMessage(
        channel="{{SLACK_CHANNEL_PROD}}",
        text=f":x: Dagster run failed: {context.run_id}\nJob: {context.job_name}\nError: {context.failure_event.message}",
    )
```

Attach the hook to the job(s) you care about:

```python
my_job = define_asset_job(
    name="my_source_daily",
    selection=AssetSelection.groups("my_source"),
).with_hooks([slack_on_run_failure])
```

### Step 3: Asset check failure

The run failure hook in Step 2 also fires when a run fails because an asset check failed—one message per failed run. For a dedicated "check failed" message, you can post from inside the check using `context.resources.slack` when the check fails (in addition to returning `AssetCheckResult(passed=False, ...)`).

### Step 4: Freshness violation (optional)

Use a sensor that runs periodically, checks for stale assets (e.g. via Dagster API or run storage), and posts to Slack. Or use Dagster Cloud/Plus "alert when asset is stale" if available.

### Step 5: Verify

1. Set `SLACK_BOT_TOKEN` in .env.
2. Run `dagster dev -f definitions.py`, trigger a job that will **fail** (e.g. bad script path). Confirm a message appears in `{{SLACK_CHANNEL_PROD}}`.
3. Fix the job and run again; no failure message.

**Summary:** Install `dagster-slack`, add Slack resource from env, register in Definitions, add a failure hook to your jobs. Keep the token in .env only.
