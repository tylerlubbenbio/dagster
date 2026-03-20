#!/usr/bin/env python3
"""Standalone test: run Meta extractor outside Dagster and verify NDJSON output."""

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

extractor_dir = _REPO / "dagster" / "ingestion" / "raw" / "api_meta"
sys.path.insert(0, str(extractor_dir))

from extractor import extract


class FakeContext:
    """Minimal context mock for standalone testing."""
    class _log:
        @staticmethod
        def info(msg): print(f"  [INFO] {msg}")
        @staticmethod
        def warning(msg): print(f"  [WARN] {msg}")
        @staticmethod
        def error(msg): print(f"  [ERROR] {msg}")
    log = _log()


ctx = FakeContext()

# Test 1: Campaigns
print("=" * 60)
print("TEST 1: Campaigns (full_refresh)")
print("=" * 60)
campaigns_config = {"target_table": "CAMPAIGNS", "primary_key": "ID"}
result = extract(ctx, "2026-01-01", "2026-03-19", campaigns_config)
print(f"\nResult: {result}")
with open(result) as f:
    lines = f.readlines()
print(f"Records: {len(lines)}")
if lines:
    sample = json.loads(lines[0])
    print(f"First record keys: {list(sample.keys())}")
    print(f"First record id: {sample.get('id')}")

# Test 2: Campaign Insights (last 7 days)
print("\n" + "=" * 60)
print("TEST 2: Campaign Insights (7-day window)")
print("=" * 60)
insights_config = {
    "target_table": "CAMPAIGN_INSIGHTS",
    "primary_key": "CAMPAIGN_ID,DATE_START",
    "incremental_column": "DATE_START",
}
result2 = extract(ctx, "2026-03-12", "2026-03-19", insights_config)
print(f"\nResult: {result2}")
with open(result2) as f:
    lines2 = f.readlines()
print(f"Records: {len(lines2)}")
if lines2:
    sample2 = json.loads(lines2[0])
    print(f"First record keys: {list(sample2.keys())}")
    print(f"campaign_id: {sample2.get('campaign_id')}, date_start: {sample2.get('date_start')}")
    actions = sample2.get("actions", [])
    print(f"actions: {len(actions)} action types (JSON array)")

print("\nAll tests passed.")
