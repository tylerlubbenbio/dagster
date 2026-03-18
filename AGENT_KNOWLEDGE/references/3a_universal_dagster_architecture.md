# 3a. Universal Dagster Architecture — Systems DAG (Appendix)

> **Note:** This document uses generic warehouse terminology. Run /activate to get database-specific instructions in _RESOURCES/{db}.md.

**Appendix to [3. Universal Dagster Architecture](3_universal_dagster_architecture.md).** This document describes the **Systems** layer: a separate Dagster definitions layer that holds **system assets** — maintenance and operational tasks that are not data-ingestion or transformation pipelines.

---

## Table of Contents

1. [What Is the Systems DAG?](#what-is-the-systems-dag)
2. [When to Use System Assets](#when-to-use-system-assets)
3. [Definitions Structure](#definitions-structure)
4. [System Assets (Example: refresh_read_grants)](#system-assets-example-refresh_read_grants)
5. [Jobs and Schedules](#jobs-and-schedules)
6. [Adding New System Assets](#adding-new-system-assets)
7. [Quick Reference](#quick-reference)

---

## What Is the Systems DAG?

The **Systems** layer is a third definitions layer in Dagster, alongside **Ingestion** (raw data extraction) and **Transformation** (dbt models). It is merged into the main entry point in `dagster/definitions.py`.

**Purpose:** Run **maintenance and operational tasks** that:

- Do not produce a business data table (raw/core/obt/report).
- Act on infrastructure or permissions (e.g. data warehouse grants, cleanup, admin scripts).
- Benefit from the same scheduling, logging, and observability as other Dagster jobs.

**Examples of system assets:**

- Refreshing data warehouse read grants for specific users so they have USAGE on all schemas and SELECT on all tables/views.
- One-off or periodic admin tasks that must run as code (no stored procedure), with run history and failure alerts.

System assets typically:

- Use the same **resources** as ingestion (e.g. `warehouse`) where applicable.
- Return a **summary or metadata** (e.g. counts, errors skipped) rather than writing to a table via the IO manager.
- Are grouped under **group_name="systems"** and appear in the UI under the Systems asset group.

---

## When to Use System Assets

| Use system assets when | Use ingestion/transformation when |
|------------------------|-----------------------------------|
| Task is operational/maintenance (grants, cleanup, admin). | Task produces or transforms business data (raw tables, dbt models). |
| No "target table" in raw/core/obt/report. | Output is a table or view in the warehouse. |
| You want Dagster schedules, logs, and alerts for the task. | Same; plus you need asset lineage and IO manager persistence. |

If a task both maintains infrastructure and could be a stored procedure, you may still implement it as a **system asset** so it runs in Dagster with a single schedule and full visibility.

---

## Definitions Structure

**Location:** `dagster/systems/`

```
dagster/
├── definitions.py              # Merges ingestion_defs, transformation_defs, systems_defs
├── ingestion/
│   └── definitions.py
├── transformation/
│   └── definitions.py
└── systems/
    ├── __init__.py
    ├── definitions.py         # systems_defs (assets, jobs, schedules, resources)
    ├── assets.py               # System asset definitions (e.g. refresh_read_grants)
    ├── jobs.py                 # Job(s) that materialize system assets
    └── schedules.py            # Schedule(s) for those jobs
```

**Main entry point** (`dagster/definitions.py`):

```python
from ingestion import definitions as _ingestion_module
from transformation import definitions as _transformation_module
from systems import definitions as _systems_module

defs = Definitions.merge(
    _ingestion_module.ingestion_defs,
    _transformation_module.transformation_defs,
    _systems_module.systems_defs,
)
```

**Systems definitions** (`dagster/systems/definitions.py`):

- Imports assets, jobs, and schedules from `systems.assets`, `systems.jobs`, `systems.schedules`.
- Uses `get_all_resources()` from `dagster/resources.py` so system assets can use the same warehouse (and other) resources as ingestion.
- Respects `SCHEDULES_ENABLED` from `env_config` when attaching schedules (same pattern as ingestion).

---

## System Assets (Example: refresh_read_grants)

**Asset:** `refresh_read_grants`
**Group:** `systems`
**Job:** `systems_refresh_read_grants`
**Schedule:** `systems_refresh_read_grants_daily` (e.g. 07:00 UTC).

**What it does:**

- Connects to the data warehouse via `context.resources.warehouse`.
- Queries catalog views for schemas, tables, and views (excluding system schemas).
- For each configured grantee:
  - Runs `GRANT USAGE ON SCHEMA <schema> TO <grantee>` for each schema.
  - Runs `GRANT SELECT ON TABLE <schema>.<table> TO <grantee>` for each table.
  - Runs `GRANT SELECT ON <schema>.<view> TO <grantee>` for each view.
- Skips any GRANT that raises (e.g. permission denied) so one failure does not stop the run.
- Commits, logs summary counts, and attaches output metadata (e.g. grantees, schema/table/view counts, errors skipped).

**Implementation notes:**

- Uses parameterized SQL with safe identifier quoting for the target warehouse dialect.
- Single connection; all GRANTs in one transaction, then commit.
- No IO manager write; the asset returns a summary dict and uses `context.add_output_metadata()` so the run is visible in the UI.

**Why an asset and not only a job with an op:** The asset gives a clear "refresh read grants" node in the asset graph, materialization history, and metadata in the UI. The job is defined as "materialize the systems group" (or the specific asset).

---

## Jobs and Schedules

**Job:** `systems_refresh_read_grants`

- Defined in `dagster/systems/jobs.py`.
- Built with `define_asset_job`, e.g. `AssetSelection.groups("systems")`, name `systems_refresh_read_grants`.
- Description: refreshes USAGE and SELECT for the configured grantees on all non-system schemas, tables, and views.

**Schedule:** `systems_refresh_read_grants_daily`

- Defined in `dagster/systems/schedules.py`.
- Runs the above job daily (e.g. `0 7 * * *` UTC).
- Only attached when `SCHEDULES_ENABLED` is true (e.g. prod).

---

## Adding New System Assets

1. **Define the asset** in `dagster/systems/assets.py`:
   - `@asset(group_name="systems", required_resource_keys={"warehouse", ...})`
   - Implement the maintenance logic (e.g. more GRANTs, cleanup, admin SQL).
   - Use try/except per operation if you want to skip failures and continue.
   - Return a summary and call `context.add_output_metadata(metadata=...)`.

2. **Export the asset** in the same file (e.g. `assets = [refresh_read_grants, your_new_asset]`).

3. **Job:** The existing job `systems_refresh_read_grants` selects by group `systems`, so any new asset in that group is included. If you need a separate job (e.g. different schedule), add another `define_asset_job` in `systems/jobs.py` and a corresponding schedule in `systems/schedules.py`.

4. **Resources:** System assets use the same resources as ingestion (`get_all_resources()`). If a new asset needs a different connection (e.g. admin user), extend the resources or config as in the main architecture doc.

5. **Schedules:** Add a `ScheduleDefinition` in `systems/schedules.py` for the job that should run the new asset (or rely on the shared systems job if all system assets run together daily).

---

## Quick Reference

| Item | Location or value |
|------|--------------------|
| Systems definitions | `dagster/systems/definitions.py` |
| System assets | `dagster/systems/assets.py` |
| Systems jobs | `dagster/systems/jobs.py` |
| Systems schedules | `dagster/systems/schedules.py` |
| Asset group | `systems` |
| Example asset | `refresh_read_grants` |
| Example job | `systems_refresh_read_grants` |
| Example schedule | `systems_refresh_read_grants_daily` (daily, 07:00 UTC) |
| Resources | Same as ingestion (`get_all_resources()`); no separate systems-only resources by default. |

**References:** [3. Universal Dagster Architecture](3_universal_dagster_architecture.md) (main doc), [1. Universal API Architecture](1_universal_api_architecture.md), [2. Universal Pipeline Architecture](2_universal_pipeline_architecture.md).
