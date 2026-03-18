"""Systems assets: maintenance tasks (e.g. refresh warehouse read grants)."""

import sys
from pathlib import Path

from dagster import asset

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from load_config import load_config

# ACTIVATE: Set the warehouse roles that should have read access
# These roles get USAGE on all schemas and SELECT on all tables/views
GRANTEES = (
    # "READ_ONLY_ROLE",  # Add your read-only warehouse role(s) here
)

EXCLUDED_SCHEMAS = ("INFORMATION_SCHEMA",)


@asset(
    group_name="systems",
    required_resource_keys={"warehouse"},
    description="Refresh USAGE on all non-system schemas and SELECT on all tables/views for configured grantee roles.",
)
def refresh_read_grants(context):
    """Grant configured roles USAGE on all schemas and SELECT on all tables/views."""
    if not GRANTEES:
        context.log.info("No GRANTEES configured. Set GRANTEES in systems/assets.py to enable.")
        context.add_output_metadata({"status": "skipped", "reason": "no grantees configured"})
        return {"status": "skipped"}

    cfg = load_config()
    database = cfg["target"]["database"]

    warehouse = context.resources.warehouse
    conn = warehouse.get_connection()
    cur = conn.cursor()

    try:
        # Get all non-system schemas in the target database
        cur.execute(
            "SELECT SCHEMA_NAME FROM {db}.INFORMATION_SCHEMA.SCHEMATA "
            "WHERE SCHEMA_NAME NOT IN ({excl})".format(
                db=database,
                excl=", ".join(f"'{s}'" for s in EXCLUDED_SCHEMAS),
            )
        )
        schemas = [r[0] for r in cur.fetchall()]

        granted_schemas = granted_tables = granted_views = errors = 0

        for role in GRANTEES:
            for schema in schemas:
                fq_schema = f"{database}.{schema}"
                # Grant USAGE on schema
                try:
                    cur.execute(f"GRANT USAGE ON SCHEMA {fq_schema} TO ROLE {role}")
                    granted_schemas += 1
                except Exception as e:
                    errors += 1
                    context.log.debug("Skip GRANT USAGE %s to %s: %s", schema, role, e)

                # Grant SELECT on all tables in schema
                try:
                    cur.execute(
                        f"GRANT SELECT ON ALL TABLES IN SCHEMA {fq_schema} TO ROLE {role}"
                    )
                    granted_tables += 1
                except Exception as e:
                    errors += 1
                    context.log.debug("Skip GRANT SELECT tables %s to %s: %s", schema, role, e)

                # Grant SELECT on all views in schema
                try:
                    cur.execute(
                        f"GRANT SELECT ON ALL VIEWS IN SCHEMA {fq_schema} TO ROLE {role}"
                    )
                    granted_views += 1
                except Exception as e:
                    errors += 1
                    context.log.debug("Skip GRANT SELECT views %s to %s: %s", schema, role, e)

        summary = {
            "database": database,
            "grantees": list(GRANTEES),
            "granted_schemas": granted_schemas,
            "granted_tables": granted_tables,
            "granted_views": granted_views,
            "errors_skipped": errors,
        }
        context.add_output_metadata(metadata=summary)
        return summary
    finally:
        cur.close()
        conn.close()


assets = [refresh_read_grants]
