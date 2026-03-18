"""Sensors for monitoring run status and posting alerts."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dagster import (
    AssetCheckSeverity,
    DagsterEventType,
    DagsterRunStatus,
    DefaultSensorStatus,
    RunsFilter,
    run_status_sensor,
    sensor,
)
from slack_sdk import WebClient

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from env_config import SLACK_CHANNEL as _DEFAULT_SLACK_CHANNEL

# Default UI URLs by env; override with config.json dagster.ui_base_url or DAGSTER_UI_BASE_URL
_DAGSTER_UI_URLS = {
    "dev": "http://127.0.0.1:3000",
    "prod": "http://localhost:3000",  # Override via DAGSTER_UI_BASE_URL env var or config.json dagster.ui_base_url
}


def _get_dagster_ui_base_url() -> str:
    """Resolve Dagster UI base URL: env var > config.json dagster.ui_base_url > config.env > dev default."""
    url = os.environ.get("DAGSTER_UI_BASE_URL")
    if url:
        return url.rstrip("/")
    try:
        from load_config import load_config

        cfg = load_config()
        dagster = cfg.get("dagster") or {}
        url = dagster.get("ui_base_url")
        if url:
            return url.rstrip("/")
        env = dagster.get("env", "dev")
        return _DAGSTER_UI_URLS.get(env, _DAGSTER_UI_URLS["dev"])
    except Exception:
        return _DAGSTER_UI_URLS["dev"]


@sensor(
    name="slack_run_failure_sensor",
    minimum_interval_seconds=30,
    default_status=DefaultSensorStatus.RUNNING,
)
def slack_run_failure_sensor(context):
    """Poll for failed runs and post to Slack. No-op if SLACK_BOT_TOKEN is not set."""

    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token:
        context.log.warning("SLACK_BOT_TOKEN not set, skipping notification")
        context.update_cursor(str(datetime.now().timestamp()))
        return

    # Get cursor (last checked timestamp) - defaults to 2 minutes ago on first run
    cursor = context.cursor

    # Handle legacy cursor format or invalid cursor
    try:
        if cursor and not cursor.replace(".", "").isdigit():
            # Invalid/legacy cursor format, reset it
            context.log.warning(f"Resetting invalid cursor: {cursor[:100]}")
            cursor = None

        cursor_timestamp = (
            float(cursor)
            if cursor
            else (datetime.now() - timedelta(minutes=2)).timestamp()
        )
        cursor_dt = datetime.fromtimestamp(cursor_timestamp)
    except (ValueError, TypeError) as e:
        context.log.warning(f"Error parsing cursor, resetting: {e}")
        cursor_timestamp = (datetime.now() - timedelta(minutes=2)).timestamp()
        cursor_dt = datetime.fromtimestamp(cursor_timestamp)

    context.log.info(f"Checking for failed runs since {cursor_dt}")

    # Query for failed runs since last check
    try:
        runs_list = list(
            context.instance.get_runs(
                filters=RunsFilter(statuses=[DagsterRunStatus.FAILURE]),
                limit=50,
            )
        )
        context.log.info(f"Retrieved {len(runs_list)} failed runs from instance")
    except Exception as e:
        context.log.error(f"Error getting runs: {e}")
        context.update_cursor(str(datetime.now().timestamp()))
        return

    # Filter for runs that ended after our cursor timestamp
    failed_runs = []
    for run in runs_list:
        try:
            run_stats = context.instance.get_run_stats(run.run_id)
            if run_stats.end_time is None:
                continue
            if run_stats.end_time > cursor_timestamp:
                failed_runs.append(run)
        except Exception as e:
            context.log.warning(f"Could not get run stats for {run.run_id}: {e}")

    if not failed_runs:
        context.log.info("No new failed runs")
        context.update_cursor(str(datetime.now().timestamp()))
        return

    context.log.info(f"Found {len(failed_runs)} failed run(s)")

    channel = os.environ.get("SLACK_ALERT_CHANNEL", _DEFAULT_SLACK_CHANNEL)
    client = WebClient(token=slack_token)
    ui_base = _get_dagster_ui_base_url()

    for run in failed_runs:
        try:
            run_url = f"{ui_base}/runs/{run.run_id}"
            response = client.chat_postMessage(
                channel=channel,
                text=(
                    f":x: *Dagster Run Failed*\n"
                    f"*Job:* `{run.job_name}`\n"
                    f"*Run ID:* `{run.run_id}`\n"
                    f"*Status:* {run.status.value if run.status else 'FAILED'}\n"
                    f"View details at {run_url}"
                ),
            )
            context.log.info(
                f"Posted failure alert for {run.run_id} (ts: {response.get('ts', 'unknown')})"
            )
        except Exception as e:
            context.log.error(
                f"Slack alert failed for {run.run_id}: {type(e).__name__}: {e}"
            )

    # Update cursor to now
    context.update_cursor(str(datetime.now().timestamp()))


def _post_asset_check_failure_alerts(run_id: str, job_name: str, context) -> None:
    """Fetch ASSET_CHECK_EVALUATION events for a run and post Slack alerts for each failed check."""
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token:
        return

    try:
        result = context.instance.get_records_for_run(
            run_id=run_id,
            of_type=DagsterEventType.ASSET_CHECK_EVALUATION,
        )
        records = result.records if hasattr(result, "records") else []
    except Exception as e:
        context.log.warning(f"Could not fetch asset check events for {run_id}: {e}")
        return

    channel = os.environ.get("SLACK_ALERT_CHANNEL", _DEFAULT_SLACK_CHANNEL)
    client = WebClient(token=slack_token)
    ui_base = _get_dagster_ui_base_url()
    run_url = f"{ui_base}/runs/{run_id}"

    for event_record in records:
        try:
            entry = event_record.event_log_entry
            dagster_event = entry.dagster_event
            if not dagster_event or not dagster_event.event_specific_data:
                continue
            data = dagster_event.event_specific_data
            if getattr(data, "passed", True):
                continue
            asset_key = getattr(data, "asset_key", None)
            asset_key_str = asset_key.to_user_string() if asset_key else "unknown"
            check_name = getattr(data, "check_name", "unknown")
            severity = getattr(data, "severity", AssetCheckSeverity.ERROR)
            is_warn = severity == AssetCheckSeverity.WARN
            emoji = ":warning:" if is_warn else ":x:"
            client.chat_postMessage(
                channel=channel,
                text=(
                    f"{emoji} *Asset Check Failed*\n"
                    f"*Job:* `{job_name}`\n"
                    f"*Asset:* `{asset_key_str}`\n"
                    f"*Check:* `{check_name}`\n"
                    f"*Run ID:* `{run_id}`\n"
                    f"View details at {run_url}"
                ),
            )
            context.log.info(
                f"Posted asset check failure alert for {asset_key_str}.{check_name}"
            )
        except Exception as e:
            context.log.warning(f"Could not post asset check alert: {e}")


@run_status_sensor(
    run_status=DagsterRunStatus.FAILURE,
    default_status=DefaultSensorStatus.RUNNING,
)
def slack_asset_check_failure_on_run_failure(context):
    """Post to Slack when a run fails and had failed asset checks."""
    run = context.dagster_run
    _post_asset_check_failure_alerts(run.run_id, run.job_name or "unknown", context)


@run_status_sensor(
    run_status=DagsterRunStatus.SUCCESS,
    default_status=DefaultSensorStatus.RUNNING,
)
def slack_asset_check_failure_on_run_success(context):
    """Post to Slack when a run succeeds but had failed asset checks (e.g. WARN severity)."""
    run = context.dagster_run
    _post_asset_check_failure_alerts(run.run_id, run.job_name or "unknown", context)


sensors = [
    slack_run_failure_sensor,
    slack_asset_check_failure_on_run_failure,
    slack_asset_check_failure_on_run_success,
]
