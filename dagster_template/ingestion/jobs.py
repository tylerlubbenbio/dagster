"""Ingestion jobs — one per source group.

ACTIVATE: Add a job per source after running the pipeline builder.

Example:
    from dagster import AssetSelection, define_asset_job, in_process_executor

    raw_example_job = define_asset_job(
        name="raw_example_sync",
        selection=AssetSelection.groups("raw_example"),
        description="Sync Example data to raw_example",
        executor_def=in_process_executor,
        tags={"dagster/max_concurrent_runs": "1"},
    )

    jobs = [raw_example_job]
"""

from dagster import AssetSelection, define_asset_job, in_process_executor

# ACTIVATE: Define one job per source, then add to the list below
# raw_example_job = define_asset_job(
#     name="raw_example_sync",
#     selection=AssetSelection.groups("raw_example"),
#     description="Sync Example to raw_example (incremental by updated_at)",
#     executor_def=in_process_executor,
#     tags={"dagster/max_concurrent_runs": "1"},
# )

jobs = []
