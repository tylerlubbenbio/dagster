"""Transformation jobs (dbt build)."""

from dagster import AssetSelection, define_asset_job

from transformation.assets import dbt_transformation_assets

dbt_build_job = define_asset_job(
    name="dbt_build_job",
    selection=[dbt_transformation_assets],
    description="Run dbt build across all transformation models (staging → core → analytics → report).",
)

dbt_analytics_job = define_asset_job(
    name="dbt_analytics_job",
    selection=AssetSelection.groups("analytics"),
    description="Run dbt build for analytics models only.",
)

dbt_analytics_adhoc_job = define_asset_job(
    name="dbt_analytics_adhoc_job",
    selection=AssetSelection.groups("analytics_adhoc"),
    description="Run dbt build for analytics_adhoc models only (ad-hoc enriched tables).",
)

jobs = [dbt_build_job, dbt_analytics_job, dbt_analytics_adhoc_job]
