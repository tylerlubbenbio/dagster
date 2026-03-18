"""Systems assets: maintenance tasks (e.g. refresh warehouse read grants)."""

import sys
from pathlib import Path

from dagster import asset
from psycopg2 import sql

_DAGSTER_DIR = Path(__file__).resolve().parent.parent
if str(_DAGSTER_DIR) not in sys.path:
    sys.path.insert(0, str(_DAGSTER_DIR))

# ACTIVATE: Set the warehouse users that should have read access
# These users get USAGE on all schemas and SELECT on all tables/views
GRANTEES = (
    # "read_only_user",  # Add your read-only warehouse user(s) here
)

EXCLUDED_SCHEMAS = (
    "pg_catalog",
    "pg_internal",
    "information_schema",
    "pg_automv",
    "pg_auto_copy",
)


@asset(
    group_name="systems",
    required_resource_keys={"warehouse"},
    description="Refresh USAGE on all non-system schemas and SELECT on all tables/views for configured grantees.",
)
def refresh_read_grants(context):
    """Grant configured users USAGE on all schemas and SELECT on all tables/views."""
    if not GRANTEES:
        context.log.info("No GRANTEES configured. Set GRANTEES in systems/assets.py to enable.")
        context.add_output_metadata({"status": "skipped", "reason": "no grantees configured"})
        return {"status": "skipped"}

    warehouse = context.resources.warehouse
    conn = warehouse.get_connection()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT schema_name FROM information_schema.schemata
            WHERE schema_name NOT IN %s
            """,
            (EXCLUDED_SCHEMAS,),
        )
        schemas = [r[0] for r in cur.fetchall()]

        cur.execute(
            """
            SELECT schemaname, tablename FROM pg_tables
            WHERE schemaname NOT IN %s
            """,
            (EXCLUDED_SCHEMAS,),
        )
        tables = cur.fetchall()

        cur.execute(
            """
            SELECT schemaname, viewname FROM pg_views
            WHERE schemaname NOT IN %s
            """,
            (EXCLUDED_SCHEMAS,),
        )
        views = cur.fetchall()

        granted_schemas = granted_tables = granted_views = errors = 0

        for grantee in GRANTEES:
            grantee_id = sql.Identifier(grantee)
            for schema in schemas:
                try:
                    cur.execute(
                        sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                            sql.Identifier(schema), grantee_id
                        )
                    )
                    granted_schemas += 1
                except Exception as e:
                    errors += 1
                    conn.rollback()
                    context.log.debug("Skip GRANT USAGE %s to %s: %s", schema, grantee, e)

            for schemaname, tablename in tables:
                try:
                    cur.execute(
                        sql.SQL("GRANT SELECT ON TABLE {}.{} TO {}").format(
                            sql.Identifier(schemaname),
                            sql.Identifier(tablename),
                            grantee_id,
                        )
                    )
                    granted_tables += 1
                except Exception as e:
                    errors += 1
                    conn.rollback()

            for schemaname, viewname in views:
                try:
                    cur.execute(
                        sql.SQL("GRANT SELECT ON {}.{} TO {}").format(
                            sql.Identifier(schemaname),
                            sql.Identifier(viewname),
                            grantee_id,
                        )
                    )
                    granted_views += 1
                except Exception as e:
                    errors += 1
                    conn.rollback()

            conn.commit()

        conn.commit()
        summary = {
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
