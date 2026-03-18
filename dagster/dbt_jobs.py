"""dbt utility jobs: source freshness check."""

import subprocess
from pathlib import Path

from dagster import ScheduleDefinition, job, op

DBT_DIR = Path(__file__).resolve().parent / "dbt"


@op
def run_dbt_source_freshness(context):
    result = subprocess.run(
        ["dbt", "source", "freshness", "--profiles-dir", "."],
        cwd=str(DBT_DIR),
        capture_output=True,
        text=True,
    )
    context.log.info(result.stdout)
    if result.returncode != 0:
        context.log.error(result.stderr)
        raise Exception("dbt source freshness failed — sources may be stale")


@job
def dbt_source_freshness_job():
    run_dbt_source_freshness()


dbt_freshness_schedule = ScheduleDefinition(
    job=dbt_source_freshness_job,
    cron_schedule="50 5 * * *",
    name="dbt_source_freshness_daily",
)
