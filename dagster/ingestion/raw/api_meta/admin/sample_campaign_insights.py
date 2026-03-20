#!/usr/bin/env python3
"""Phase 1: Extract 2 pages of Meta campaign insights to data/temp/campaign_insights.json.

Step 1 of Universal API Architecture.
Fetches daily campaign-level insights for the last 7 days to inspect
field names, types, nesting, PK, and incremental strategy.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from load_config import load_config

config = load_config()
meta_cfg = config["sources"]["meta"]

ACCESS_TOKEN = meta_cfg["access_token"]
AD_ACCOUNT_ID = meta_cfg["ad_account_id"]
API_VERSION = meta_cfg.get("api_version", "v18.0")
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

FIELDS = ",".join([
    "campaign_id", "campaign_name",
    "date_start", "date_stop",
    "impressions", "clicks", "spend",
    "cpc", "cpm", "ctr", "cpp",
    "reach", "frequency",
    "actions", "conversions",
    "cost_per_action_type",
])
PAGE_LIMIT = 2
PER_PAGE = 50

end_date = datetime.now(timezone.utc).date()
start_date = end_date - timedelta(days=7)

print(f"Extracting campaign insights from {AD_ACCOUNT_ID}")
print(f"  Date range: {start_date} to {end_date}")
print(f"  Max pages : {PAGE_LIMIT}, {PER_PAGE}/page")

url = f"{BASE_URL}/{AD_ACCOUNT_ID}/insights"
params = {
    "access_token": ACCESS_TOKEN,
    "fields": FIELDS,
    "level": "campaign",
    "time_increment": 1,
    "time_range": json.dumps({"since": str(start_date), "until": str(end_date)}),
    "limit": PER_PAGE,
}

all_records = []
page = 0

while url and page < PAGE_LIMIT:
    page += 1
    resp = requests.get(url, params=params if page == 1 else None)
    resp.raise_for_status()
    body = resp.json()

    records = body.get("data", [])
    all_records.extend(records)
    print(f"  Page {page}: {len(records)} records (running total: {len(all_records)})")

    url = body.get("paging", {}).get("next")

# Save to data/temp/
output_dir = Path(__file__).resolve().parent.parent / "data" / "temp"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "campaign_insights.json"

output = {
    "metadata": {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source": f"Meta Marketing API {API_VERSION}",
        "ad_account": AD_ACCOUNT_ID,
        "endpoint": f"/{AD_ACCOUNT_ID}/insights",
        "fields_requested": FIELDS,
        "params": {
            "level": "campaign",
            "time_increment": "1 (daily)",
            "time_range": f"{start_date} to {end_date}",
        },
        "pages_fetched": page,
        "total_records": len(all_records),
        "page_limit": PAGE_LIMIT,
    },
    "records": all_records,
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, default=str)

print(f"\nSaved {len(all_records)} records to {output_file}")

# --- Quick inspection ---
if all_records:
    sample = all_records[0]
    print("\n--- FIELD INSPECTION (first record) ---")
    json_cols = []
    for k, v in sample.items():
        vtype = type(v).__name__
        is_json = isinstance(v, (dict, list))
        if is_json:
            json_cols.append(k)
        flag = " ** JSON/ARRAY -> VARIANT **" if is_json else ""
        preview = str(v)[:80]
        print(f"  {k:25s} ({vtype:6s}){flag}: {preview}")

    print("\n--- STEP 1 FINDINGS: campaign_insights ---")
    print(f"  Primary Key        : campaign_id + date_start (composite)")
    print(f"  Incremental Strategy: timestamp on date_start (filter by date range)")
    print(f"  JSON/ARRAY columns : {', '.join(json_cols) if json_cols else 'none'}")
    print(f"  Row estimate       : {len(all_records)} rows for 7 days")
    daily_avg = len(all_records) / 7 if len(all_records) > 0 else 0
    yearly = int(daily_avg * 365)
    print(f"  Yearly estimate    : ~{yearly} rows ({daily_avg:.0f}/day x 365)")
else:
    print("\nNo records returned. Check date range or account activity.")
