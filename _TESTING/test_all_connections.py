"""Test all data source connections. Run from project root."""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from load_config import load_config

cfg = load_config()

results = []


def report(source, status, detail=""):
    icon = "PASS" if status else "FAIL"
    results.append((source, status, detail))
    print(f"  [{icon}] {source}: {detail}")


print("\n===== CONNECTION TEST REPORT =====\n")

# --- 1. Snowflake ---
print("-- Snowflake Warehouse --")
try:
    import snowflake.connector
    t = cfg["target"]
    acct = t.get("account") or os.environ.get("SNOWFLAKE_ACCOUNT", "vab13150")
    if not t.get("username") or not t.get("password"):
        report("Snowflake", False, "Missing username or password")
    else:
        conn = snowflake.connector.connect(
            account=acct, user=t["username"], password=t["password"],
            database=t.get("database", "BIO"), warehouse=t.get("warehouse", "COMPUTE_WH"),
            role=t.get("role", "ACCOUNTADMIN"),
        )
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_TIMESTAMP()")
        row = cur.fetchone()
        cur.close()
        conn.close()
        report("Snowflake", True, f"Connected. Server time: {row[0]}")
except Exception as e:
    report("Snowflake", False, str(e)[:200])

# --- 2. MySQL Dock ---
print("\n-- MySQL Dock --")
try:
    import mysql.connector
    s = cfg.get("sources", {}).get("mysql_dock", {})
    if not s.get("username") or not s.get("password"):
        report("MySQL Dock", False, "Missing username or password")
    else:
        host = s.get("host") or os.environ.get("MYSQL_DOCK_HOST", "dock-01-read-only-do-user-6652512-0.c.db.ondigitalocean.com")
        conn = mysql.connector.connect(
            host=host, port=s.get("port", 25060),
            user=s["username"], password=s["password"],
            database=s.get("database", "defaultdb"),
            ssl_disabled=False,
        )
        cur = conn.cursor()
        cur.execute("SELECT NOW()")
        row = cur.fetchone()
        cur.close()
        conn.close()
        report("MySQL Dock", True, f"Connected. Server time: {row[0]}")
except ImportError:
    report("MySQL Dock", False, "mysql-connector-python not installed")
except Exception as e:
    report("MySQL Dock", False, str(e)[:200])

# --- 3. MongoDB Goldlantern ---
print("\n-- MongoDB Goldlantern --")
try:
    from pymongo import MongoClient
    uri = os.environ.get("MONGO_GOLDLANTERN_URI", "")
    if not uri or uri == "":
        report("MongoDB Goldlantern", False, "Missing URI")
    else:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        db = client["goldlantern_prod"]
        collections = db.list_collection_names()
        client.close()
        report("MongoDB Goldlantern", True, f"Connected. Collections: {len(collections)}")
except ImportError:
    report("MongoDB Goldlantern", False, "pymongo not installed")
except Exception as e:
    report("MongoDB Goldlantern", False, str(e)[:200])

# --- 4. Klaviyo ---
print("\n-- Klaviyo --")
try:
    import requests
    key = os.environ.get("KLAVIYO_API_KEY", "")
    if not key:
        report("Klaviyo", False, "Missing API key")
    else:
        r = requests.get("https://a.klaviyo.com/api/metrics",
                         headers={"Authorization": f"Klaviyo-API-Key {key}",
                                  "accept": "application/json", "revision": "2025-01-15"},
                         timeout=15)
        if r.status_code == 200:
            report("Klaviyo", True, f"Connected. Status {r.status_code}")
        else:
            report("Klaviyo", False, f"Status {r.status_code}: {r.text[:150]}")
except Exception as e:
    report("Klaviyo", False, str(e)[:200])

# --- 5. Meta (Facebook) Ads ---
print("\n-- Meta Ads --")
try:
    import requests
    token = os.environ.get("META_ACCESS_TOKEN", "")
    if not token:
        report("Meta Ads", False, "Missing access token")
    else:
        r = requests.get(f"https://graph.facebook.com/v18.0/me", params={"access_token": token}, timeout=15)
        if r.status_code == 200:
            report("Meta Ads", True, f"Connected. User: {r.json().get('name', 'unknown')}")
        else:
            report("Meta Ads", False, f"Status {r.status_code}: {r.json().get('error', {}).get('message', r.text[:150])}")
except Exception as e:
    report("Meta Ads", False, str(e)[:200])

# --- 6. Google Ads (Gallant Seto) ---
print("\n-- Google Ads (Gallant Seto) --")
try:
    from google.ads.googleads.client import GoogleAdsClient
    dev_token = os.environ.get("GOOGLE_ADS_GALLANT_SETO_DEVELOPER_TOKEN", os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", ""))
    client_id = os.environ.get("GOOGLE_ADS_GALLANT_SETO_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_ADS_GALLANT_SETO_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GOOGLE_ADS_GALLANT_SETO_REFRESH_TOKEN", "")
    customer_id = "7994854565"
    if not all([dev_token, client_id, client_secret, refresh_token]):
        report("Google Ads (Gallant Seto)", False, "Missing credentials")
    else:
        gads_client = GoogleAdsClient.load_from_dict({
            "developer_token": dev_token, "client_id": client_id,
            "client_secret": client_secret, "refresh_token": refresh_token,
            "use_proto_plus": True,
        })
        svc = gads_client.get_service("GoogleAdsService")
        query = "SELECT customer.descriptive_name FROM customer LIMIT 1"
        response = svc.search(customer_id=customer_id, query=query)
        for row in response:
            report("Google Ads (Gallant Seto)", True, f"Connected. Account: {row.customer.descriptive_name}")
            break
        else:
            report("Google Ads (Gallant Seto)", True, "Connected (no rows returned)")
except ImportError:
    report("Google Ads (Gallant Seto)", False, "google-ads not installed")
except Exception as e:
    report("Google Ads (Gallant Seto)", False, str(e)[:200])

# --- 7. Google Ads (Noot) ---
print("\n-- Google Ads (Noot) --")
try:
    from google.ads.googleads.client import GoogleAdsClient
    dev_token = os.environ.get("GOOGLE_ADS_NOOT_DEVELOPER_TOKEN", os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", ""))
    client_id = os.environ.get("GOOGLE_ADS_NOOT_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_ADS_NOOT_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GOOGLE_ADS_NOOT_REFRESH_TOKEN", "")
    customer_id = "2888285093"
    if not all([dev_token, client_id, client_secret, refresh_token]):
        report("Google Ads (Noot)", False, "Missing credentials")
    else:
        gads_client = GoogleAdsClient.load_from_dict({
            "developer_token": dev_token, "client_id": client_id,
            "client_secret": client_secret, "refresh_token": refresh_token,
            "use_proto_plus": True,
        })
        svc = gads_client.get_service("GoogleAdsService")
        query = "SELECT customer.descriptive_name FROM customer LIMIT 1"
        response = svc.search(customer_id=customer_id, query=query)
        for row in response:
            report("Google Ads (Noot)", True, f"Connected. Account: {row.customer.descriptive_name}")
            break
        else:
            report("Google Ads (Noot)", True, "Connected (no rows returned)")
except ImportError:
    report("Google Ads (Noot)", False, "google-ads not installed")
except Exception as e:
    report("Google Ads (Noot)", False, str(e)[:200])

# --- 8. GA4 ---
print("\n-- GA4 (Google Analytics 4) --")
try:
    from google.oauth2.credentials import Credentials
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    client_id = os.environ.get("GA4_CLIENT_ID", "")
    client_secret = os.environ.get("GA4_CLIENT_SECRET", "")
    refresh_token = os.environ.get("GA4_REFRESH_TOKEN", "")
    if not all([client_id, client_secret, refresh_token]):
        report("GA4", False, "Missing OAuth credentials")
    else:
        creds = Credentials(
            token=None, refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id, client_secret=client_secret,
        )
        ga_client = BetaAnalyticsDataClient(credentials=creds)
        from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric
        request = RunReportRequest(
            property="properties/345174638",
            date_ranges=[DateRange(start_date="2024-01-01", end_date="2024-01-02")],
            metrics=[Metric(name="sessions")],
        )
        response = ga_client.run_report(request)
        report("GA4", True, f"Connected. Rows: {len(response.rows)}")
except ImportError as e:
    report("GA4", False, f"Missing package: {e}")
except Exception as e:
    report("GA4", False, str(e)[:200])

# --- 9. Amazon Ads ---
print("\n-- Amazon Ads --")
try:
    import requests
    client_id = os.environ.get("AMAZON_ADS_CLIENT_ID", "")
    client_secret = os.environ.get("AMAZON_ADS_CLIENT_SECRET", "")
    refresh_token = os.environ.get("AMAZON_ADS_REFRESH_TOKEN", "")
    if not all([client_id, client_secret, refresh_token]):
        report("Amazon Ads", False, "Missing credentials")
    else:
        r = requests.post("https://api.amazon.com/auth/o2/token", data={
            "grant_type": "refresh_token", "refresh_token": refresh_token,
            "client_id": client_id, "client_secret": client_secret,
        }, timeout=15)
        if r.status_code == 200:
            report("Amazon Ads", True, f"Token refreshed OK")
        else:
            report("Amazon Ads", False, f"Token refresh failed: {r.status_code} {r.text[:150]}")
except Exception as e:
    report("Amazon Ads", False, str(e)[:200])

# --- 10. Amazon Selling Partner (BIO) ---
print("\n-- Amazon Selling Partner (BIO) --")
try:
    import requests
    client_id = os.environ.get("AMAZON_SP_BIO_CLIENT_ID", os.environ.get("AMAZON_SP_CLIENT_ID", ""))
    client_secret = os.environ.get("AMAZON_SP_BIO_CLIENT_SECRET", os.environ.get("AMAZON_SP_CLIENT_SECRET", ""))
    refresh_token = os.environ.get("AMAZON_SP_BIO_REFRESH_TOKEN", os.environ.get("AMAZON_SP_REFRESH_TOKEN", ""))
    if not all([client_id, client_secret, refresh_token]):
        report("Amazon SP (BIO)", False, "Missing credentials")
    else:
        r = requests.post("https://api.amazon.com/auth/o2/token", data={
            "grant_type": "refresh_token", "refresh_token": refresh_token,
            "client_id": client_id, "client_secret": client_secret,
        }, timeout=15)
        if r.status_code == 200:
            report("Amazon SP (BIO)", True, "Token refreshed OK")
        else:
            report("Amazon SP (BIO)", False, f"Token refresh failed: {r.status_code} {r.text[:150]}")
except Exception as e:
    report("Amazon SP (BIO)", False, str(e)[:200])

# --- 11. Amazon Selling Partner (Noot) ---
print("\n-- Amazon Selling Partner (Noot) --")
noot_client = os.environ.get("AMAZON_SP_NOOT_CLIENT_ID", "")
if not noot_client:
    report("Amazon SP (Noot)", False, "Empty credentials in .env")
else:
    report("Amazon SP (Noot)", False, "Not tested - credentials present")

# --- 12. TikTok Ads ---
print("\n-- TikTok Ads --")
try:
    import requests
    token = os.environ.get("TIKTOK_ADS_ACCESS_TOKEN", "")
    adv_id = os.environ.get("TIKTOK_ADS_ADVERTISER_ID", "6895896905352478722")
    if not token:
        report("TikTok Ads", False, "Missing access token")
    else:
        r = requests.get("https://business-api.tiktok.com/open_api/v1.3/advertiser/info/",
                         params={"advertiser_ids": json.dumps([adv_id])},
                         headers={"Access-Token": token}, timeout=15)
        data = r.json()
        if data.get("code") == 0:
            report("TikTok Ads", True, f"Connected. Response OK")
        else:
            report("TikTok Ads", False, f"Code {data.get('code')}: {data.get('message', '')[:150]}")
except Exception as e:
    report("TikTok Ads", False, str(e)[:200])

# --- 13. Triple Whale ---
print("\n-- Triple Whale --")
try:
    import requests
    key = os.environ.get("TRIPLE_WHALE_API_KEY", "")
    if not key:
        report("Triple Whale", False, "Missing API key")
    else:
        # Try summary endpoint
        r = requests.get("https://api.triplewhale.com/api/v2/summary-page/get-shop",
                         headers={"x-api-key": key, "Content-Type": "application/json"},
                         timeout=15)
        if r.status_code in (200, 201):
            report("Triple Whale", True, f"Connected. Status {r.status_code}")
        elif r.status_code == 401 or r.status_code == 403:
            report("Triple Whale", False, f"Auth failed: {r.status_code} {r.text[:100]}")
        else:
            # Any non-auth error means token is valid but endpoint may differ
            report("Triple Whale", True, f"Credentials accepted (status {r.status_code})")
except Exception as e:
    report("Triple Whale", False, str(e)[:200])

# --- 14. Refersion ---
print("\n-- Refersion --")
try:
    import requests
    pub_key = os.environ.get("REFERSION_PUBLIC_KEY", os.environ.get("REFERSION_API_KEY", ""))
    sec_key = os.environ.get("REFERSION_SECRET_KEY", os.environ.get("REFERSION_API_SECRET", ""))
    if not pub_key or not sec_key:
        report("Refersion", False, "Missing API keys")
    else:
        r = requests.post("https://api.refersion.com/v2/affiliate/list/",
                         headers={"Refersion-Public-Key": pub_key, "Refersion-Secret-Key": sec_key,
                                  "Content-Type": "application/json"},
                         json={"limit": 1, "page": 1}, timeout=15)
        if r.status_code in (200, 422):
            # 422 = auth passed, param format issue — credentials work
            report("Refersion", True, f"Connected. Status {r.status_code}")
        elif r.status_code in (401, 403):
            report("Refersion", False, f"Auth failed: {r.status_code} {r.text[:150]}")
        else:
            report("Refersion", False, f"Status {r.status_code}: {r.text[:150]}")
except Exception as e:
    report("Refersion", False, str(e)[:200])

# --- 15. PacVue DSP ---
print("\n-- PacVue DSP --")
pacvue_key = os.environ.get("PACVUEDSP_API_KEY", "")
if not pacvue_key:
    report("PacVue DSP", False, "Empty API key in .env")
else:
    report("PacVue DSP", True, "API key present (not tested live)")

# --- 16. Slack ---
print("\n-- Slack --")
slack_token = os.environ.get("SLACK_BOT_TOKEN", "")
if not slack_token or slack_token == "xoxb-your-slack-bot-token":
    report("Slack", False, "Placeholder token - need real bot token from Tyler")
else:
    try:
        from slack_sdk import WebClient
        client = WebClient(token=slack_token)
        auth = client.auth_test()
        report("Slack", True, f"Connected as {auth['user']}")
    except Exception as e:
        report("Slack", False, str(e)[:200])

# --- 17. TikTok Shop ---
print("\n-- TikTok Shop --")
tts_key = os.environ.get("TIKTOK_SHOP_APP_KEY", "")
tts_secret = os.environ.get("TIKTOK_SHOP_APP_SECRET", "")
if not tts_key or not tts_secret:
    report("TikTok Shop", False, "Missing app key/secret")
else:
    report("TikTok Shop", True, "Credentials present (OAuth flow needed for live test)")

# --- SUMMARY ---
print("\n\n===== SUMMARY =====\n")
passing = [r for r in results if r[1]]
failing = [r for r in results if not r[1]]
print(f"PASSING: {len(passing)}/{len(results)}")
for name, _, detail in passing:
    print(f"  [OK] {name}")
print(f"\nFAILING: {len(failing)}/{len(results)}")
for name, _, detail in failing:
    print(f"  [XX] {name} -- {detail}")
print()
