"""Transformation sensors — trigger dbt jobs based on upstream ingestion completion.

ACTIVATE: Add sensors to trigger dbt jobs after your raw ingestion jobs complete.

Example:
    from dagster import DagsterRunStatus, RunRequest, run_status_sensor
    from ingestion.jobs import raw_example_job
    from transformation.jobs import dbt_analytics_job

    @run_status_sensor(
        run_status=DagsterRunStatus.SUCCESS,
        monitored_jobs=[raw_example_job],
        request_job=dbt_analytics_job,
        name="dbt_analytics_on_example_success",
    )
    def dbt_analytics_sensor(context):
        return RunRequest(run_key=context.dagster_run.run_id)

    sensors = [dbt_analytics_sensor]
"""

sensors = []
