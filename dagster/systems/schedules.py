"""Systems schedules."""

from dagster import ScheduleDefinition

from systems.jobs import refresh_read_grants_job

refresh_read_grants_schedule = ScheduleDefinition(
    job=refresh_read_grants_job,
    cron_schedule="0 7 * * *",
    name="systems_refresh_read_grants_daily",
)

schedules = [refresh_read_grants_schedule]
