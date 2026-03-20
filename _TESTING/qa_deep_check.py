"""Deep QA checks for Meta pipeline - duplicates, nulls, schema, freshness."""
import sys, os
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

passed = 0
failed = 0

def check(name, result, expected=True):
    global passed, failed
    status = "PASS" if result == expected else "FAIL"
    if result == expected:
        passed += 1
    else:
        failed += 1
    print(f"  [{status}] {name}")

print("=" * 60)
print("QA REPORT: META PIPELINE")
print("=" * 60)

print("\n--- ROW COUNTS ---")
cur.execute("SELECT COUNT(*) FROM RAW_META.CAMPAIGNS")
camp_count = cur.fetchone()[0]
print(f"  CAMPAIGNS: {camp_count} rows")
check("CAMPAIGNS has data (>0)", camp_count > 0)

cur.execute("SELECT COUNT(*) FROM RAW_META.CAMPAIGN_INSIGHTS")
ins_count = cur.fetchone()[0]
print(f"  CAMPAIGN_INSIGHTS: {ins_count} rows")
check("CAMPAIGN_INSIGHTS has data (>0)", ins_count > 0)

print("\n--- DUPLICATE PRIMARY KEY CHECK ---")
cur.execute("SELECT ID, COUNT(*) c FROM RAW_META.CAMPAIGNS GROUP BY ID HAVING c > 1")
camp_dupes = len(cur.fetchall())
print(f"  CAMPAIGNS duplicate IDs: {camp_dupes}")
check("CAMPAIGNS no duplicate PKs", camp_dupes, 0)

cur.execute("SELECT CAMPAIGN_ID, DATE_START, COUNT(*) c FROM RAW_META.CAMPAIGN_INSIGHTS GROUP BY CAMPAIGN_ID, DATE_START HAVING c > 1")
ins_dupes = len(cur.fetchall())
print(f"  CAMPAIGN_INSIGHTS duplicate PKs: {ins_dupes}")
check("CAMPAIGN_INSIGHTS no duplicate PKs", ins_dupes, 0)

print("\n--- NULL CHECKS: CAMPAIGNS ---")
cur.execute("SELECT SUM(CASE WHEN ID IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN NAME IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN STATUS IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN INSERTED_AT IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN UPDATED_AT IS NULL THEN 1 ELSE 0 END) FROM RAW_META.CAMPAIGNS")
r = cur.fetchone()
check("CAMPAIGNS.ID no nulls", r[0], 0)
check("CAMPAIGNS.NAME no nulls", r[1], 0)
check("CAMPAIGNS.STATUS no nulls", r[2], 0)
check("CAMPAIGNS.INSERTED_AT no nulls", r[3], 0)
check("CAMPAIGNS.UPDATED_AT no nulls", r[4], 0)

print("\n--- NULL CHECKS: CAMPAIGN_INSIGHTS ---")
cur.execute("SELECT SUM(CASE WHEN CAMPAIGN_ID IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN DATE_START IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN IMPRESSIONS IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN SPEND IS NULL THEN 1 ELSE 0 END), SUM(CASE WHEN INSERTED_AT IS NULL THEN 1 ELSE 0 END) FROM RAW_META.CAMPAIGN_INSIGHTS")
r = cur.fetchone()
check("INSIGHTS.CAMPAIGN_ID no nulls", r[0], 0)
check("INSIGHTS.DATE_START no nulls", r[1], 0)
check("INSIGHTS.IMPRESSIONS no nulls", r[2], 0)
check("INSIGHTS.SPEND no nulls", r[3], 0)
check("INSIGHTS.INSERTED_AT no nulls", r[4], 0)

print("\n--- SCHEMA STRUCTURE: CAMPAIGNS ---")
cur.execute("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM BIO.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='RAW_META' AND TABLE_NAME='CAMPAIGNS' ORDER BY ORDINAL_POSITION")
for r in cur.fetchall():
    print(f"  {r[0]:30s} {r[1]:15s} nullable={r[2]}")

print("\n--- SCHEMA STRUCTURE: CAMPAIGN_INSIGHTS ---")
cur.execute("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM BIO.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='RAW_META' AND TABLE_NAME='CAMPAIGN_INSIGHTS' ORDER BY ORDINAL_POSITION")
for r in cur.fetchall():
    print(f"  {r[0]:30s} {r[1]:15s} nullable={r[2]}")

print("\n--- VARIANT (JSON) COLUMN CHECK ---")
cur.execute("SELECT COUNT(*) FROM RAW_META.CAMPAIGNS WHERE SPECIAL_AD_CATEGORIES IS NOT NULL")
sac = cur.fetchone()[0]
print(f"  CAMPAIGNS.SPECIAL_AD_CATEGORIES non-null: {sac}/{camp_count}")
check("SPECIAL_AD_CATEGORIES has values", sac > 0)

cur.execute("SELECT COUNT(*) FROM RAW_META.CAMPAIGN_INSIGHTS WHERE ACTIONS IS NOT NULL")
act = cur.fetchone()[0]
print(f"  INSIGHTS.ACTIONS non-null: {act}/{ins_count}")

cur.execute("SELECT COUNT(*) FROM RAW_META.CAMPAIGN_INSIGHTS WHERE COST_PER_ACTION_TYPE IS NOT NULL")
cpa = cur.fetchone()[0]
print(f"  INSIGHTS.COST_PER_ACTION_TYPE non-null: {cpa}/{ins_count}")

print("\n--- DATA FRESHNESS ---")
cur.execute("SELECT MAX(INSERTED_AT) FROM RAW_META.CAMPAIGNS")
print(f"  CAMPAIGNS latest INSERTED_AT: {cur.fetchone()[0]}")
cur.execute("SELECT MAX(INSERTED_AT) FROM RAW_META.CAMPAIGN_INSIGHTS")
print(f"  INSIGHTS latest INSERTED_AT:  {cur.fetchone()[0]}")
cur.execute("SELECT MIN(DATE_START), MAX(DATE_START) FROM RAW_META.CAMPAIGN_INSIGHTS")
r = cur.fetchone()
print(f"  INSIGHTS date range: {r[0]} to {r[1]}")

print("\n--- WATERMARKS ---")
cur.execute("SELECT TARGET_SCHEMA, TARGET_TABLE, STATUS, ROWS_PROCESSED, WATERMARK_VALUE, LAST_SUCCESS_AT FROM METADATA.PIPELINE_WATERMARKS WHERE TARGET_SCHEMA = 'RAW_META' AND STATUS = 'success' ORDER BY UPDATED_AT DESC")
for r in cur.fetchall():
    print(f"  {r[0]}.{r[1]}: status={r[2]}, rows={r[3]}, watermark={r[4]}, last_success={r[5]}")
    check(f"Watermark {r[1]} status=success", r[2], "success")

print("\n--- REFERENTIAL INTEGRITY ---")
cur.execute("SELECT COUNT(DISTINCT CAMPAIGN_ID) FROM RAW_META.CAMPAIGN_INSIGHTS WHERE CAMPAIGN_ID NOT IN (SELECT ID FROM RAW_META.CAMPAIGNS)")
orphans = cur.fetchone()[0]
print(f"  Orphan campaign_ids in INSIGHTS (not in CAMPAIGNS): {orphans}")
check("No orphan campaign_ids", orphans, 0)

print("\n" + "=" * 60)
print(f"RESULTS: {passed} PASSED, {failed} FAILED out of {passed+failed} checks")
print("=" * 60)

conn.close()
