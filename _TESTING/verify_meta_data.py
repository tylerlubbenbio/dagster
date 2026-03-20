"""Verify Meta pipeline data in Snowflake."""
import sys
import os
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from load_config import load_config
import snowflake.connector

cfg = load_config()
t = cfg["target"]
conn = snowflake.connector.connect(
    account=t["account"], user=t["username"], password=t["password"],
    database=t["database"], warehouse=t["warehouse"], role=t["role"],
)
cur = conn.cursor()

print("=== ROW COUNTS ===")
cur.execute("SELECT COUNT(*) FROM RAW_META.CAMPAIGNS")
print(f"RAW_META.CAMPAIGNS: {cur.fetchone()[0]} rows")

cur.execute("SELECT COUNT(*) FROM RAW_META.CAMPAIGN_INSIGHTS")
print(f"RAW_META.CAMPAIGN_INSIGHTS: {cur.fetchone()[0]} rows")

print("\n=== DATE RANGE ===")
cur.execute("SELECT MIN(DATE_START), MAX(DATE_START) FROM RAW_META.CAMPAIGN_INSIGHTS")
r = cur.fetchone()
print(f"  {r[0]} to {r[1]}")

print("\n=== SAMPLE CAMPAIGNS ===")
cur.execute("SELECT ID, NAME, STATUS, OBJECTIVE FROM RAW_META.CAMPAIGNS LIMIT 3")
for r in cur.fetchall():
    print(f"  {r}")

print("\n=== SAMPLE INSIGHTS ===")
cur.execute("SELECT CAMPAIGN_ID, DATE_START, IMPRESSIONS, CLICKS, SPEND FROM RAW_META.CAMPAIGN_INSIGHTS LIMIT 3")
for r in cur.fetchall():
    print(f"  {r}")

print("\n=== WATERMARKS ===")
cur.execute("SELECT * FROM PIPELINE_WATERMARKS WHERE SCHEMA_NAME = 'RAW_META'")
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(f"  {dict(zip(cols, r))}")

conn.close()
print("\nVerification complete!")
