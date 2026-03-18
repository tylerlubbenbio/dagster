"""Transformation schedules (dbt build - daily). analytics_adhoc triggered by sensor."""

from dagster import ScheduleDefinition

from transformation.jobs import dbt_build_job

# Run dbt build daily at 6am UTC (after overnight raw ingestion completes)
dbt_daily_schedule = ScheduleDefinition(
    job=dbt_build_job,
    cron_schedule="0 6 * * *",
    name="dbt_daily_schedule",
)

schedules = [dbt_daily_schedule]
