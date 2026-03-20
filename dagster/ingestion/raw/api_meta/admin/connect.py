#!/usr/bin/env python3
"""Phase 0: Test Meta Marketing API connection and list available endpoints/objects.

Step 1 of Universal API Architecture.
Authenticates against the Meta Graph API and lists ad objects available
for the configured ad account.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from load_config import load_config

config = load_config()
meta_cfg = config["sources"]["meta"]

ACCESS_TOKEN = meta_cfg.get("access_token", "")
AD_ACCOUNT_ID = meta_cfg.get("ad_account_id", "")
API_VERSION = meta_cfg.get("api_version", "v18.0")
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

if not ACCESS_TOKEN:
    print("FAIL: META_ACCESS_TOKEN is empty. Check .env")
    sys.exit(1)
if not AD_ACCOUNT_ID:
    print("FAIL: META_AD_ACCOUNT_ID is empty. Check .env")
    sys.exit(1)

print(f"Ad Account : {AD_ACCOUNT_ID}")
print(f"API Version: {API_VERSION}")
print(f"Base URL   : {BASE_URL}")
print("-" * 60)

import requests

# --- Test 1: Verify token is valid ---
print("\n[1] Testing access token validity...")
resp = requests.get(f"{BASE_URL}/me", params={"access_token": ACCESS_TOKEN})
if resp.status_code == 200:
    me = resp.json()
    print(f"    OK - Token owner: {me.get('name', me.get('id', 'unknown'))}")
else:
    err = resp.json().get("error", {})
    print(f"    FAIL - {err.get('message', resp.text)}")
    sys.exit(1)

# --- Test 2: Verify ad account access ---
print("\n[2] Testing ad account access...")
resp = requests.get(
    f"{BASE_URL}/{AD_ACCOUNT_ID}",
    params={
        "access_token": ACCESS_TOKEN,
        "fields": "id,name,account_status,currency,timezone_name,business_name",
    },
)
if resp.status_code == 200:
    acct = resp.json()
    print(f"    OK - Account: {acct.get('name', 'N/A')}")
    print(f"    ID: {acct.get('id')}")
    print(f"    Status: {acct.get('account_status')} (1=ACTIVE)")
    print(f"    Currency: {acct.get('currency')}")
    print(f"    Timezone: {acct.get('timezone_name')}")
    print(f"    Business: {acct.get('business_name', 'N/A')}")
else:
    err = resp.json().get("error", {})
    print(f"    FAIL - {err.get('message', resp.text)}")
    sys.exit(1)

# --- Test 3: List available ad objects (endpoints we can extract) ---
ENDPOINTS = {
    "campaigns": f"{BASE_URL}/{AD_ACCOUNT_ID}/campaigns",
    "adsets": f"{BASE_URL}/{AD_ACCOUNT_ID}/adsets",
    "ads": f"{BASE_URL}/{AD_ACCOUNT_ID}/ads",
    "insights": f"{BASE_URL}/{AD_ACCOUNT_ID}/insights",
    "customaudiences": f"{BASE_URL}/{AD_ACCOUNT_ID}/customaudiences",
}

print("\n[3] Checking available endpoints...")
for name, url in ENDPOINTS.items():
    resp = requests.get(url, params={"access_token": ACCESS_TOKEN, "limit": 1})
    if resp.status_code == 200:
        data = resp.json().get("data", [])
        paging = resp.json().get("paging", {})
        has_next = "next" in paging
        print(f"    {name:20s} -> OK ({len(data)} sample, has_more={has_next})")
    else:
        err = resp.json().get("error", {})
        print(f"    {name:20s} -> FAIL ({err.get('message', 'unknown')})")

# --- Test 4: Count campaigns to estimate volume ---
print("\n[4] Estimating data volumes...")
resp = requests.get(
    f"{BASE_URL}/{AD_ACCOUNT_ID}/campaigns",
    params={"access_token": ACCESS_TOKEN, "limit": 500, "fields": "id"},
)
if resp.status_code == 200:
    all_ids = resp.json().get("data", [])
    print(f"    Campaigns: ~{len(all_ids)} total")
else:
    print("    Campaigns: could not estimate")

print("\n" + "=" * 60)
print("STEP 1 - PHASE 0 COMPLETE")
print("Endpoints to extract for Step 2: campaigns, campaign_insights")
print("=" * 60)
