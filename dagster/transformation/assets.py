"""Transformation assets (dbt models: staging, core, obt, report)."""

from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

# Resolve dbt project directory relative to this file
_DBT_PROJECT_DIR = Path(__file__).resolve().parent.parent / "dbt"

dbt_project = DbtProject(
    project_dir=_DBT_PROJECT_DIR,
    profiles_dir=_DBT_PROJECT_DIR,
)

# Generates the manifest at startup in dev; in prod the manifest is pre-built
dbt_project.prepare_if_dev()


@dbt_assets(manifest=dbt_project.manifest_path)
def dbt_transformation_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


assets = [dbt_transformation_assets]
