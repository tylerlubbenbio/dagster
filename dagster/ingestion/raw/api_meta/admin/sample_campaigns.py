#!/usr/bin/env python3
"""Phase 1: Extract 2 pages of Meta campaigns to data/temp/campaigns.json.

Step 1 of Universal API Architecture.
Fetches a limited sample to inspect field names, types, nesting, and PK.
"""

import json
import sys
from datetime import datetime, timezone
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
    "id", "name", "status", "effective_status", "objective",
    "buying_type", "bid_strategy",
    "daily_budget", "lifetime_budget", "budget_remaining",
    "start_time", "stop_time", "created_time", "updated_time",
    "special_ad_categories",
])
PAGE_LIMIT = 2
PER_PAGE = 50

print(f"Extracting campaigns from {AD_ACCOUNT_ID} (max {PAGE_LIMIT} pages, {PER_PAGE}/page)...")

url = f"{BASE_URL}/{AD_ACCOUNT_ID}/campaigns"
params = {"access_token": ACCESS_TOKEN, "fields": FIELDS, "limit": PER_PAGE}

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
output_file = output_dir / "campaigns.json"

output = {
    "metadata": {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "source": f"Meta Marketing API {API_VERSION}",
        "ad_account": AD_ACCOUNT_ID,
        "endpoint": f"/{AD_ACCOUNT_ID}/campaigns",
        "fields_requested": FIELDS,
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
    for k, v in sample.items():
        vtype = type(v).__name__
        is_json = isinstance(v, (dict, list))
        flag = " ** JSON/ARRAY -> VARIANT **" if is_json else ""
        preview = str(v)[:80]
        print(f"  {k:25s} ({vtype:6s}){flag}: {preview}")

    print("\n--- STEP 1 FINDINGS: campaigns ---")
    print(f"  Primary Key        : id (source unique, string)")
    print(f"  Incremental Strategy: full_refresh (small dataset, no reliable updated_time filter)")
    print(f"  JSON/ARRAY columns : special_ad_categories (list)")
    print(f"  Row estimate       : {len(all_records)}+ (fetched {page} of {PAGE_LIMIT} pages)")
