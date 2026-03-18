"""Ingestion schedules — one per source job.

ACTIVATE: Add schedules after defining jobs. Stagger by 10+ minutes to avoid resource contention.

Example pattern (6x/day, staggered):
    raw_example_schedule = ScheduleDefinition(
        job=raw_example_job,
        cron_schedule="0 0,4,8,12,16,20 * * *",
        name="raw_example_6x_daily",
    )
"""

from dagster import ScheduleDefinition

# ACTIVATE: Import your jobs and define schedules
# from ingestion.jobs import raw_example_job

# raw_example_schedule = ScheduleDefinition(
#     job=raw_example_job,
#     cron_schedule="0 0,4,8,12,16,20 * * *",
#     name="raw_example_6x_daily",
# )

schedules = []
