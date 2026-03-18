"""Systems jobs."""

from dagster import AssetSelection, define_asset_job

refresh_read_grants_job = define_asset_job(
    name="systems_refresh_read_grants",
    selection=AssetSelection.groups("systems"),
    description="Refresh USAGE and SELECT grants for configured read-only users on all non-system schemas, tables, and views.",
)

jobs = [refresh_read_grants_job]
