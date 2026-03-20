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
cur.execute(
    "SELECT TARGET_SCHEMA, TARGET_TABLE, STATUS, ROWS_PROCESSED, "
    "WATERMARK_VALUE, LAST_SUCCESS_AT, UPDATED_AT "
    "FROM METADATA.PIPELINE_WATERMARKS "
    "WHERE TARGET_SCHEMA ILIKE '%META%' "
    "ORDER BY UPDATED_AT DESC"
)
cols = [d[0] for d in cur.description]
for r in cur.fetchall():
    print(dict(zip(cols, r)))
conn.close()
