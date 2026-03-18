"""Transformation-specific resources."""

from dagster_dbt import DbtCliResource

from transformation.assets import dbt_project

resources = {
    "dbt": DbtCliResource(project_dir=dbt_project),
}
