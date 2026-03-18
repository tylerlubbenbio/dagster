"""Transformation layer definitions - dbt models (staging → core → obt → report)."""

from dagster import Definitions

from transformation.assets import assets as transformation_assets
from transformation.jobs import jobs as transformation_jobs
from transformation.schedules import schedules as transformation_schedules
from transformation.sensors import sensors as transformation_sensors
from transformation.resources import resources as transformation_resources

transformation_defs = Definitions(
    assets=transformation_assets,
    jobs=transformation_jobs,
    schedules=transformation_schedules,
    sensors=transformation_sensors,
    resources=transformation_resources,
)
