"""Meta Marketing API extractor — zero-memory NDJSON streaming.

Step 2 of Universal Pipeline Architecture.
Called by asset_factory.py when custom_extractor: true.

Returns str (NDJSON file path) for each asset. IO Manager handles
PUT + COPY INTO Snowflake.

Endpoints:
  - campaigns:         GET /{ad_account_id}/campaigns (cursor pagination, full refresh)
  - campaign_insights: GET /{ad_account_id}/insights  (date range + cursor pagination)
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from load_config import load_config

OUTPUT_DIR = _REPO_ROOT / "_LOCAL_FILES" / "meta"

CAMPAIGN_FIELDS = ",".join([
    "id", "name", "status", "effective_status", "objective",
    "buying_type", "bid_strategy",
    "daily_budget", "lifetime_budget", "budget_remaining",
    "start_time", "stop_time", "created_time", "updated_time",
    "special_ad_categories",
])

INSIGHT_FIELDS = ",".join([
    "campaign_id", "campaign_name",
    "date_start", "date_stop",
    "impressions", "clicks", "spend",
    "cpc", "cpm", "ctr", "cpp",
    "reach", "frequency",
    "actions", "cost_per_action_type",
])


def _get_meta_config() -> dict:
    cfg = load_config()
    meta = cfg["sources"]["meta"]
    return {
        "access_token": meta["access_token"],
        "ad_account_id": meta["ad_account_id"],
        "api_version": meta.get("api_version", "v18.0"),
    }


def _api_get(url: str, params: dict, context, max_retries: int = 5) -> dict:
    """GET with retry and rate-limit handling."""
    for attempt in range(max_retries):
        resp = requests.get(url, params=params, timeout=120)

        if resp.status_code == 200:
            return resp.json()

        error_msg = ""
        try:
            error_msg = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            error_msg = resp.text

        is_transient = (
            resp.status_code == 429
            or resp.status_code >= 500
            or "temporarily unavailable" in error_msg.lower()
            or "unknown error" in error_msg.lower()
        )

        if is_transient and attempt < max_retries - 1:
            wait = int(resp.headers.get("Retry-After", min(2 ** (attempt + 2), 60)))
            context.log.warning(
                f"Transient error ({resp.status_code}: {error_msg}), "
                f"retrying in {wait}s (attempt {attempt+1}/{max_retries})"
            )
            time.sleep(wait)
            continue

        raise RuntimeError(f"Meta API error {resp.status_code}: {error_msg}")

    raise RuntimeError(f"Meta API failed after {max_retries} retries")


def _extract_campaigns(context, meta_cfg: dict, output_file: Path) -> int:
    """Stream all campaigns to NDJSON. Returns row count."""
    base = f"https://graph.facebook.com/{meta_cfg['api_version']}"
    url = f"{base}/{meta_cfg['ad_account_id']}/campaigns"
    params = {
        "access_token": meta_cfg["access_token"],
        "fields": CAMPAIGN_FIELDS,
        "limit": 200,
    }

    count = 0
    page = 0
    with open(output_file, "w", encoding="utf-8") as f:
        while url:
            page += 1
            body = _api_get(url, params if page == 1 else None, context)
            records = body.get("data", [])
            for rec in records:
                f.write(json.dumps(rec, default=str) + "\n")
                count += 1
            context.log.info(f"Campaigns page {page}: {len(records)} records (total: {count})")
            url = body.get("paging", {}).get("next")

    return count


def _extract_campaign_insights(
    context, meta_cfg: dict, from_date: str, to_date: str, output_file: Path
) -> int:
    """Stream campaign insights (daily) to NDJSON. Returns row count."""
    base = f"https://graph.facebook.com/{meta_cfg['api_version']}"
    url = f"{base}/{meta_cfg['ad_account_id']}/insights"
    params = {
        "access_token": meta_cfg["access_token"],
        "fields": INSIGHT_FIELDS,
        "level": "campaign",
        "time_increment": 1,
        "time_range": json.dumps({"since": from_date, "until": to_date}),
        "limit": 200,
    }

    count = 0
    page = 0
    with open(output_file, "w", encoding="utf-8") as f:
        while url:
            page += 1
            body = _api_get(url, params if page == 1 else None, context)
            records = body.get("data", [])
            for rec in records:
                f.write(json.dumps(rec, default=str) + "\n")
                count += 1
            context.log.info(
                f"Insights page {page}: {len(records)} records (total: {count})"
            )
            url = body.get("paging", {}).get("next")

    return count


def extract(context, from_date: str, to_date: str, asset_config: dict) -> str:
    """Entry point called by asset_factory. Returns NDJSON file path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    meta_cfg = _get_meta_config()

    target_table = asset_config["target_table"]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"{target_table}_{timestamp}.ndjson"

    context.log.info(f"Extracting {target_table} to {output_file}")

    if target_table.upper() == "CAMPAIGNS":
        count = _extract_campaigns(context, meta_cfg, output_file)
    elif target_table.upper() == "CAMPAIGN_INSIGHTS":
        count = _extract_campaign_insights(context, meta_cfg, from_date, to_date, output_file)
    else:
        raise ValueError(f"Unknown target_table: {target_table}")

    context.log.info(f"Wrote {count:,} records to {output_file}")
    return str(output_file)
