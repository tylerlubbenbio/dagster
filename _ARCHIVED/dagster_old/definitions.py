"""BIOptimizers Dagster definitions - assets and jobs."""
import dagster as dg


@dg.asset(
    description="Example asset for BIOptimizers BI",
)
def example_asset(context: dg.AssetExecutionContext):
    context.log.info("BIOptimizers Dagster is running")


example_job = dg.define_asset_job("example_job", selection=[example_asset])

defs = dg.Definitions(
    assets=[example_asset],
    jobs=[example_job],
)
