"""
Asset Factory: generates @asset + @asset_check definitions from YAML configs.

Scans dagster/ingestion/raw/*/config.yaml. Each config defines source connection,
field mappings, and asset metadata. No source-specific code lives here.

Pipeline phases per asset (each is a standalone function):
  1. _resolve_date_range() — watermark → from/to dates
  2. _extract()            — fetch raw records from source
  3. _transform()          — apply field_mappings, add timestamps, filter bad rows
  4. _filter_by_watermark() — incremental dedup
  5. _build_run_metadata()  — validation stats + run info for Dagster UI

Usage:
    from asset_factory import build_assets_from_yaml
    all_assets, all_checks = build_assets_from_yaml()
"""

from __future__ import annotations

import importlib.util
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetKey,
    MetadataValue,
    RetryPolicy,
    asset,
    asset_check,
)

from field_transforms import apply_mapping

RAW_DIR = Path(__file__).resolve().parent / "ingestion" / "raw"

# Default asset owner (pipeline maintainer); overridable per-source or per-asset in YAML via owners: [email]
DEFAULT_OWNERS = ["{{DEFAULT_OWNER_EMAIL}}"]

# Default retry policies by source_type (overridable per-source or per-asset in YAML)
DEFAULT_RETRY = {
    "api": {"max_retries": 2, "delay": 30},
    "internal_db": {"max_retries": 1, "delay": 15},
    "s3": {"max_retries": 2, "delay": 30},
}


def _load_custom_extractor(config_dir: Path):
    """Import extractor.py from a source directory. Must export an extract() function.
    Returns None if extractor.py does not exist (caller skips such sources).
    Clears cached 'utils' to avoid cross-source import conflicts.
    """
    extractor_path = config_dir / "extractor.py"
    if not extractor_path.exists():
        return None
    config_dir_str = str(config_dir.resolve())
    # Clear cached utils from previous extractor to avoid wrong-package import
    for key in list(sys.modules.keys()):
        if key == "utils" or key.startswith("utils."):
            del sys.modules[key]
    if config_dir_str not in sys.path:
        sys.path.insert(0, config_dir_str)
    mod_name = f"extractor_{config_dir.name}"
    spec = importlib.util.spec_from_file_location(mod_name, extractor_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod.extract


# ---------------------------------------------------------------------------
# Pipeline phases (pure functions — no closures, no side effects except logging)
# ---------------------------------------------------------------------------


def _resolve_date_range(
    wm: str | None, incremental_strategy: str, default_days: int = 90
) -> tuple[str, str]:
    """Watermark value → (from_date, to_date)."""
    if incremental_strategy == "timestamp" and wm:
        from_date = wm[:10] if len(str(wm)) >= 10 else str(wm)
    else:
        from_date = (datetime.now() - timedelta(days=default_days)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")
    return from_date, to_date


def _extract(
    context,
    connection_resource: str,
    fetch_method: str | None,
    extract_fn,
    from_date: str,
    to_date: str,
    asset_config: dict,
) -> list[dict] | str:
    """Fetch raw records from source API or custom extractor.

    Returns list[dict] for in-memory path, or str (file path) for zero-memory extractors
    that stream to CSV/NDJSON. When str is returned, the asset passes it through to the
    IO manager (no transform/filter).
    """
    if extract_fn:
        return extract_fn(context, from_date, to_date, asset_config)

    resource = getattr(context.resources, connection_resource)
    if not fetch_method:
        raise ValueError(
            f"No fetch_method for '{connection_resource}' and no custom_extractor"
        )

    raw_records = getattr(resource, fetch_method)(from_date, to_date)
    context.log.info(f"Fetched {len(raw_records)} raw records")
    return raw_records


def _transform(
    raw_records: list[dict],
    field_mappings: list[dict] | None,
    auto_timestamps: list[str] | None,
    pk: str,
) -> tuple[list[dict], dict]:
    """Apply field mappings, add timestamps, filter rows missing PK.

    Returns (records, validation_stats).
    """
    if not field_mappings:
        return raw_records, {
            "total_raw": len(raw_records),
            "pk_missing": 0,
            "mapped": len(raw_records),
        }

    records = []
    pk_missing = 0
    for r in raw_records:
        mapped = apply_mapping(r, field_mappings, auto_timestamps)
        if not mapped.get(pk):
            pk_missing += 1
            continue
        records.append(mapped)

    return records, {
        "total_raw": len(raw_records),
        "pk_missing": pk_missing,
        "mapped": len(records),
    }


def _filter_by_watermark(
    records: list[dict],
    wm: str | None,
    incremental_strategy: str,
    incremental_column: str | None,
) -> tuple[list[dict], int]:
    """Remove already-processed records. Returns (filtered, skipped_count)."""
    if not (incremental_strategy == "timestamp" and wm and incremental_column):
        return records, 0
    before = len(records)
    filtered = [r for r in records if str(r.get(incremental_column, "")) > str(wm)]
    return filtered, before - len(filtered)


def _compute_custom_metadata(
    records: list[dict], custom_metadata_config: list[dict] | None
) -> dict:
    """Compute YAML-driven custom metadata from records.

    Supported types:
      - null_count: count NULL vs non-NULL for a column
      - value_counts: count distinct values for a column (top 20)
      - row_count_by_event_type: row count per event_type (same as value_counts for event_type; key row_count_by_event_type)
    """
    if not custom_metadata_config or not records:
        return {}

    result = {}
    for spec in custom_metadata_config:
        col = spec.get("column", "event_type")
        analyzer = spec["type"]

        if analyzer == "null_count":
            null_n = sum(1 for r in records if r.get(col) is None or r.get(col) == "")
            present_n = len(records) - null_n
            result[f"{col}_null"] = null_n
            result[f"{col}_present"] = present_n

        elif analyzer == "value_counts":
            counts: dict[str, int] = {}
            for r in records:
                val = r.get(col)
                key = str(val) if val is not None else "NULL"
                counts[key] = counts.get(key, 0) + 1
            # Store top 20 as a formatted string for the UI
            top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:20]
            formatted = ", ".join(f"{k}: {v}" for k, v in top)
            result[f"{col}_distribution"] = formatted

        elif analyzer == "row_count_by_event_type":
            # Row count by event_type; explicit key for UI (column defaults to event_type)
            col = spec.get("column", "event_type")
            counts: dict[str, int] = {}
            for r in records:
                val = r.get(col)
                key = str(val) if val is not None else "NULL"
                counts[key] = counts.get(key, 0) + 1
            top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:20]
            formatted = ", ".join(f"{k}: {v}" for k, v in top)
            result["row_count_by_event_type"] = formatted

    return result


def _format_sample_table(records: list[dict], limit: int = 5) -> str:
    """Convert records to a markdown table for Dagster UI metadata display."""
    if not records:
        return "No data"
    sample = records[:limit]
    headers = list(sample[0].keys())

    # Truncate wide values for readability
    def _trunc(val, maxlen=40):
        s = str(val) if val is not None else ""
        return s[:maxlen] + "..." if len(s) > maxlen else s

    table = "| " + " | ".join(headers) + " |\n"
    table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
    for row in sample:
        table += "| " + " | ".join(_trunc(row.get(h)) for h in headers) + " |\n"
    return table


def _build_run_metadata(
    records: list[dict],
    validation_stats: dict,
    wm: str | None,
    duration: float,
    row_count_before: int,
    incremental_column: str | None,
    run_id: str,
    custom_metadata_config: list[dict] | None = None,
    hours_since_last_run: float | None = None,
    errors: int = 0,
) -> dict:
    """Assemble metadata dict for Dagster UI."""
    new_wm = wm or "none"
    if incremental_column:
        vals = [
            str(r.get(incremental_column, ""))
            for r in records
            if r.get(incremental_column)
        ]
        if vals:
            new_wm = max(vals)

    metadata = {
        "row_count": row_count_before + len(records),
        "row_count_delta": len(records),
        "records_processed": len(records),
        "errors": errors,
        "processing_duration_seconds": round(duration, 1),
        "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "watermark_before": wm or "none",
        "watermark_after": new_wm,
        "dagster_run_id": run_id,
        # Validation stats
        "raw_records_fetched": validation_stats.get("total_raw", 0),
        "records_missing_pk": validation_stats.get("pk_missing", 0),
        # Sample data (markdown table, clickable in Dagster UI)
        "sample_data": MetadataValue.md(_format_sample_table(records)),
    }

    # Freshness
    if hours_since_last_run is not None:
        metadata["hours_since_last_run"] = round(hours_since_last_run, 1)

    if incremental_column:
        date_vals = [
            str(r.get(incremental_column, ""))
            for r in records
            if r.get(incremental_column)
        ]
        if date_vals:
            metadata["date_range_min"] = min(date_vals)
            metadata["date_range_max"] = max(date_vals)

    # Custom metadata from YAML config
    custom = _compute_custom_metadata(records, custom_metadata_config)
    metadata.update(custom)

    return metadata


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _get_retry_policy(
    source_type: str, source_config: dict, asset_config: dict
) -> RetryPolicy:
    """Resolve retry: asset YAML > source YAML > default by source_type."""
    cfg = (
        asset_config.get("retry")
        or source_config.get("retry")
        or DEFAULT_RETRY.get(source_type, {"max_retries": 1, "delay": 15})
    )
    return RetryPolicy(
        max_retries=cfg.get("max_retries", 1), delay=cfg.get("delay", 15)
    )


def _build_asset(source_config: dict, asset_config: dict, config_dir: Path):
    """Build a single @asset from YAML config."""
    source = source_config["source"]
    source_type = source_config.get("source_type", "api")
    connection_resource = source_config["connection_resource"]
    fetch_method = source_config.get("fetch_method")
    custom_extractor = source_config.get("custom_extractor", False)
    group = asset_config.get(
        "group", source_config.get("default_group", f"raw_{source}")
    )

    tags = dict(source_config.get("default_tags", {}))
    tags.update(asset_config.get("tags", {}))

    # Concurrency: prevent overlapping runs for the same asset
    max_concurrent = asset_config.get(
        "max_concurrent_runs", source_config.get("max_concurrent_runs", 1)
    )
    tags["dagster/max_concurrent_runs"] = str(max_concurrent)

    asset_name = asset_config["name"]
    target_schema = asset_config["target_schema"]
    target_table = asset_config["target_table"]
    pk = asset_config["primary_key"]
    incremental_strategy = asset_config.get("incremental_strategy", "full_refresh")
    incremental_column = asset_config.get("incremental_column")
    load_method = asset_config.get(
        "load_method", "s3_copy"
    )  # Default: s3_copy for all tables
    s3_bucket_config = asset_config.get("s3_bucket_config") or source_config.get(
        "s3_bucket_config"
    )
    compute_kind = asset_config.get(
        "compute_kind", source_config.get("source_system", source)
    )
    field_mappings = asset_config.get("field_mappings")
    custom_metadata_config = asset_config.get("custom_metadata")

    # auto_timestamps: default always on; set `auto_timestamps: false` in YAML to disable
    auto_ts = asset_config.get("auto_timestamps", ["inserted_at", "updated_at"])
    if auto_ts is False:
        auto_ts = None

    retry = _get_retry_policy(source_type, source_config, asset_config)
    extract_fn = _load_custom_extractor(config_dir) if custom_extractor else None

    # Owners: asset YAML > source default_owners > DEFAULT_OWNERS (pipeline maintainer for alerts)
    owners = (
        asset_config.get("owners")
        or source_config.get("default_owners")
        or DEFAULT_OWNERS
    )
    if isinstance(owners, str):
        owners = [owners]

    required_resources = {"warehouse", "watermark", connection_resource}

    @asset(
        name=asset_name,
        key_prefix=[group],
        group_name=group,
        compute_kind=compute_kind,
        retry_policy=retry,
        tags=tags,
        owners=owners,
        required_resource_keys=required_resources,
        metadata={
            k: v
            for k, v in {
                "target_schema": target_schema,
                "target_table": target_table,
                "primary_key": pk,
                "load_method": load_method,
                "layer": tags.get("layer", "raw"),
                "incremental_strategy": incremental_strategy,
                "incremental_column": incremental_column or "",
                "s3_bucket_config": s3_bucket_config
                if load_method == "s3_copy"
                else None,
            }.items()
            if v is not None
        },
        description=asset_config.get(
            "description",
            f"Extracts {asset_name} from {source} into {target_schema}.{target_table}. "
            f"Incremental strategy: {incremental_strategy}. Load method: {load_method}.",
        ),
    )
    def _asset_fn(context):
        start = time.time()
        warehouse = context.resources.warehouse
        watermark = context.resources.watermark
        layer = tags.get("layer", "raw")

        context.log.info(
            f"[START] {target_schema}.{target_table} | source={source} | strategy={incremental_strategy}"
        )

        try:
            # 1. Watermark + freshness
            wm = watermark.get_watermark(layer, target_schema, target_table)
            last_run_at = watermark.get_last_run_at(layer, target_schema, target_table)
            hours_since = None
            if last_run_at:
                try:
                    last_dt = datetime.fromisoformat(
                        str(last_run_at).replace("Z", "+00:00")
                    )
                    delta = (
                        datetime.now(tz=last_dt.tzinfo) - last_dt
                        if last_dt.tzinfo
                        else datetime.now() - last_dt
                    )
                    hours_since = delta.total_seconds() / 3600
                except Exception:
                    pass
            watermark.mark_run_started(layer, target_schema, target_table)
            context.log.info(
                f"Watermark: {wm or 'none'} | hours_since_last_run: {round(hours_since, 1) if hours_since else 'N/A'}"
            )

            # 2. Extract
            from_date, to_date = _resolve_date_range(wm, incremental_strategy)
            context.log.info(
                f"Extracting: {from_date} → {to_date} via {connection_resource}.{fetch_method or 'custom_extractor'}"
            )
            raw_records = _extract(
                context,
                connection_resource,
                fetch_method,
                extract_fn,
                from_date,
                to_date,
                asset_config,
            )

            # Zero-memory path: extractor returned file path (str) — pass through to IO manager
            if isinstance(raw_records, str):
                context.log.info(
                    f"Extractor returned file path (zero-memory): {raw_records}"
                )
                duration = round(time.time() - start, 1)
                context.add_output_metadata(
                    {
                        "records_processed": "streamed from file",
                        "processing_duration_seconds": duration,
                        "dagster_run_id": context.run_id,
                        "watermark_before": wm or "none",
                        "hours_since_last_run": round(hours_since, 1)
                        if hours_since
                        else None,
                    }
                )
                context.log.info(
                    f"[END] Returning file path to IO Manager | duration={duration}s"
                )
                return raw_records

            context.log.info(f"Extracted {len(raw_records)} raw records")

            # 3. Transform
            records, vstats = _transform(raw_records, field_mappings, auto_ts, pk)
            context.log.info(
                f"Transform: {vstats['total_raw']} raw → {vstats['mapped']} mapped | {vstats['pk_missing']} missing PK"
            )

            # 4. Watermark filter
            records, wm_skipped = _filter_by_watermark(
                records,
                wm,
                incremental_strategy,
                incremental_column,
            )
            if wm_skipped:
                context.log.info(
                    f"Watermark filter: skipped {wm_skipped} already-processed"
                )

            # 5. Empty check
            if not records:
                duration = round(time.time() - start, 1)
                context.log.info(f"[END] No new records | duration={duration}s")
                watermark.set_status(layer, target_schema, target_table, "success")
                context.add_output_metadata(
                    {
                        "row_count": warehouse.get_row_count(
                            target_schema, target_table
                        ),
                        "records_processed": 0,
                        "errors": 0,
                        "processing_duration_seconds": duration,
                        "dagster_run_id": context.run_id,
                    }
                )
                return None

            # 6. Build metadata + return records (IO Manager handles the write)
            error_count = vstats.get("pk_missing", 0)
            metadata = _build_run_metadata(
                records,
                vstats,
                wm,
                time.time() - start,
                warehouse.get_row_count(target_schema, target_table),
                incremental_column,
                context.run_id,
                custom_metadata_config=custom_metadata_config,
                hours_since_last_run=hours_since,
                errors=error_count,
            )
            context.add_output_metadata(metadata)
            duration = round(time.time() - start, 1)
            context.log.info(
                f"[END] Returning {len(records)} records to IO Manager | "
                f"errors={error_count} | duration={duration}s"
            )
            return records

        except Exception as e:
            duration = round(time.time() - start, 1)
            context.log.error(
                f"[FAILED] {target_schema}.{target_table} after {duration}s: {e}"
            )
            try:
                watermark.set_status(
                    layer, target_schema, target_table, "failed", str(e)
                )
            except Exception:
                context.log.warning("Could not update watermark status to 'failed'")
            raise

    _asset_fn.__name__ = asset_name
    _asset_fn.__qualname__ = asset_name
    return _asset_fn


def _build_checks(source_config: dict, asset_config: dict) -> list:
    """Build asset checks for a single asset.

    Auto-generated checks:
      1. zero_rows (ERROR)       — table must have data
      2. duplicate_pk (ERROR)    — no duplicate primary keys
      3. null_pk (ERROR)         — no NULL primary keys
      4. freshness (WARNING)     — data updated within expected window
      5. schema (WARNING)        — expected columns exist in table
    """
    asset_name = asset_config["name"]
    source = source_config.get("source", "raw")
    group = asset_config.get(
        "group", source_config.get("default_group", f"raw_{source}")
    )
    asset_key = AssetKey([group, asset_name])
    target_schema = asset_config["target_schema"]
    target_table = asset_config["target_table"]
    pk = asset_config["primary_key"]
    pk_cols = pk if isinstance(pk, list) else [c.strip() for c in str(pk).split(",")]
    layer = source_config.get("default_tags", {}).get("layer", "raw")
    field_mappings = asset_config.get("field_mappings")
    schedule_tier = asset_config.get("tags", {}).get(
        "schedule_tier",
        source_config.get("default_tags", {}).get("schedule_tier", "daily"),
    )
    freshness_defaults = {"hourly": 6, "daily": 48, "weekly": 192}
    freshness_max_hours = asset_config.get(
        "freshness_max_hours", freshness_defaults.get(schedule_tier, 48)
    )
    checks = []
    skip_zero_rows = asset_config.get("skip_zero_rows_check", False)

    # --- 1. Zero rows (ERROR) ---
    @asset_check(
        asset=asset_key,
        name=f"{asset_name}_zero_rows",
        description=f"Table {target_schema}.{target_table} must have at least 1 row.",
        required_resource_keys={"warehouse"},
    )
    def check_zero_rows(context):
        if skip_zero_rows:
            return AssetCheckResult(
                passed=True,
                severity=AssetCheckSeverity.ERROR,
                metadata={"status": "skipped", "reason": "skip_zero_rows_check: true"},
            )
        warehouse = context.resources.warehouse
        count = warehouse.get_row_count(target_schema, target_table)
        return AssetCheckResult(
            passed=count > 0,
            severity=AssetCheckSeverity.ERROR,
            metadata={"row_count": count},
        )

    # --- 2. Duplicate PK (ERROR) ---
    cols_sql = ", ".join(f'"{c}"' for c in pk_cols)
    group_by_sql = ", ".join(str(i + 1) for i in range(len(pk_cols)))

    @asset_check(
        asset=asset_key,
        name=f"{asset_name}_duplicate_pk",
        description=f"No duplicate values in primary key ({pk}).",
        required_resource_keys={"warehouse"},
    )
    def check_duplicate_pk(context):
        warehouse = context.resources.warehouse
        result = warehouse.execute(
            f"""SELECT COUNT(*) FROM (
                SELECT {cols_sql} FROM "{target_schema}"."{target_table}"
                GROUP BY {group_by_sql} HAVING COUNT(*) > 1 LIMIT 5
            )"""
        )
        dup_count = result[0][0] if result else 0
        return AssetCheckResult(
            passed=dup_count == 0,
            severity=AssetCheckSeverity.ERROR,
            metadata={"duplicate_pk_groups": dup_count},
        )

    # --- 3. Null PK (ERROR) ---
    null_conds = " OR ".join(f'"{c}" IS NULL' for c in pk_cols)

    @asset_check(
        asset=asset_key,
        name=f"{asset_name}_null_pk",
        description=f"Primary key ({pk}) must never be NULL.",
        required_resource_keys={"warehouse"},
    )
    def check_null_pk(context):
        warehouse = context.resources.warehouse
        result = warehouse.execute(
            f"""SELECT COUNT(*) FROM "{target_schema}"."{target_table}" WHERE {null_conds}"""
        )
        null_count = result[0][0] if result else 0
        return AssetCheckResult(
            passed=null_count == 0,
            severity=AssetCheckSeverity.ERROR,
            metadata={"null_pk_count": null_count},
        )

    # --- 4. Freshness (WARNING) ---
    @asset_check(
        asset=asset_key,
        name=f"{asset_name}_freshness",
        description=f"Data must be updated within {freshness_max_hours}h ({schedule_tier} schedule).",
        required_resource_keys={"warehouse"},
    )
    def check_freshness(context):
        warehouse = context.resources.warehouse
        result = warehouse.execute(
            """SELECT last_success_at FROM metadata.pipeline_watermarks
               WHERE layer = %s AND target_schema = %s AND target_table = %s""",
            (layer, target_schema, target_table),
        )
        if not result or not result[0][0]:
            return AssetCheckResult(
                passed=True,
                severity=AssetCheckSeverity.WARN,
                metadata={
                    "status": "no history (first run)",
                    "max_allowed_hours": freshness_max_hours,
                },
            )
        last_success = result[0][0]
        try:
            last_dt = datetime.fromisoformat(str(last_success).replace("Z", "+00:00"))
            if last_dt.tzinfo:
                hours = (
                    datetime.now(tz=last_dt.tzinfo) - last_dt
                ).total_seconds() / 3600
            else:
                hours = (datetime.now() - last_dt).total_seconds() / 3600
        except Exception:
            return AssetCheckResult(
                passed=True,
                severity=AssetCheckSeverity.WARN,
                metadata={"status": "could not parse last_success_at"},
            )
        return AssetCheckResult(
            passed=hours <= freshness_max_hours,
            severity=AssetCheckSeverity.WARN,
            metadata={
                "hours_since_last_success": round(hours, 1),
                "max_allowed_hours": freshness_max_hours,
            },
        )

    # --- 5. Schema validation (WARNING) ---
    expected_columns = (
        {m["column"] for m in field_mappings} if field_mappings else set()
    )

    @asset_check(
        asset=asset_key,
        name=f"{asset_name}_schema",
        description=f"All mapped columns must exist in {target_schema}.{target_table}.",
        required_resource_keys={"warehouse"},
    )
    def check_schema(context):
        warehouse = context.resources.warehouse
        if not expected_columns:
            return AssetCheckResult(
                passed=True,
                severity=AssetCheckSeverity.WARN,
                metadata={"status": "no field_mappings defined, skipping"},
            )
        result = warehouse.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema = %s AND table_name = %s""",
            (target_schema, target_table),
        )
        existing = {row[0] for row in result} if result else set()
        missing = expected_columns - existing
        return AssetCheckResult(
            passed=len(missing) == 0,
            severity=AssetCheckSeverity.WARN,
            metadata={
                "missing_columns": ", ".join(sorted(missing)) if missing else "none",
                "expected": len(expected_columns),
                "found": len(existing & expected_columns),
            },
        )

    check_zero_rows.__name__ = f"{asset_name}_zero_rows"
    check_duplicate_pk.__name__ = f"{asset_name}_duplicate_pk"
    check_null_pk.__name__ = f"{asset_name}_null_pk"
    check_freshness.__name__ = f"{asset_name}_freshness"
    check_schema.__name__ = f"{asset_name}_schema"

    checks.extend(
        [
            check_zero_rows,
            check_duplicate_pk,
            check_null_pk,
            check_freshness,
            check_schema,
        ]
    )
    return checks


def build_assets_from_yaml() -> tuple[list, list]:
    """Scan dagster/ingestion/raw/*/config.yaml and generate all assets + checks."""
    all_assets = []
    all_checks = []

    if not RAW_DIR.exists():
        return all_assets, all_checks

    for config_file in sorted(RAW_DIR.glob("*/config.yaml")):
        with open(config_file) as f:
            source_config = yaml.safe_load(f)

        if not source_config or "assets" not in source_config:
            continue

        config_dir = config_file.parent
        custom_extractor = source_config.get("custom_extractor", False)

        # Skip sources with custom_extractor but no extractor.py (not yet implemented)
        if custom_extractor and not (config_dir / "extractor.py").exists():
            continue

        for asset_config in source_config["assets"]:
            all_assets.append(_build_asset(source_config, asset_config, config_dir))
            all_checks.extend(_build_checks(source_config, asset_config))

    return all_assets, all_checks
