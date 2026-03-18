"""Field transform utilities for generic asset extraction.

Provides:
  - get_nested(): dot-notation access into nested dicts
  - Named transforms: to_str, warehouse_ts, json_dump
  - apply_mapping(): converts a raw API record into a flat DB row using YAML field_mappings
"""

from __future__ import annotations

import json
from datetime import datetime


def get_nested(record: dict, path: str):
    """Get a value from a nested dict using dot notation. e.g. 'host.email'"""
    parts = path.split(".")
    val = record
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


# --- Named transforms ---


def to_str(val):
    """Convert to string. Returns None if value is None."""
    return str(val) if val is not None else None


def warehouse_ts(val) -> str:
    """Convert ISO 8601 to warehouse TIMESTAMP format (YYYY-MM-DD HH:MM:SS)."""
    if val is None or val == "":
        return "1970-01-01 00:00:00"
    s = str(val).strip()
    if not s:
        return "1970-01-01 00:00:00"
    try:
        s = s.replace("Z", "").replace("z", "")
        if "T" in s:
            date_part, time_part = s.split("T", 1)
        else:
            date_part, time_part = s.split(" ", 1) if " " in s else (s, "00:00:00")
        time_part = time_part.split(".")[0].split("+")[0][:8]
        return f"{date_part} {time_part}"
    except Exception:
        return "1970-01-01 00:00:00"


# Keep redshift_ts as an alias for backwards compatibility
redshift_ts = warehouse_ts


def json_dump(val):
    """Serialize to JSON string. Returns None for None."""
    if val is None:
        return None
    return json.dumps(val, default=str)


# Transform registry — referenced by name in config.yaml
TRANSFORMS = {
    "to_str": to_str,
    "warehouse_ts": warehouse_ts,
    "redshift_ts": warehouse_ts,  # alias
    "json_dump": json_dump,
}


def apply_mapping(
    record: dict, field_mappings: list[dict], auto_timestamps: list[str] | None = None
) -> dict:
    """Apply field mappings to a source record, returning a flat dict for DB insert.

    Each mapping: {source: "apiField", column: "db_column", transform: "optional_fn"}
    """
    result = {}

    for mapping in field_mappings:
        source_path = mapping["source"]
        column = mapping["column"]
        transform_name = mapping.get("transform")

        val = get_nested(record, source_path)

        if transform_name and transform_name in TRANSFORMS:
            val = TRANSFORMS[transform_name](val)

        result[column] = val

    # Auto-populated timestamp columns
    if auto_timestamps:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        for ts_col in auto_timestamps:
            result[ts_col] = now

    return result
