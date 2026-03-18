#!/usr/bin/env python3
"""
Create metadata schema and pipeline_watermarks table in the warehouse.
Uses target credentials from config.json.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from load_config import load_config

# Replace with your warehouse connector (e.g. psycopg2 for Redshift/Postgres,
# snowflake.connector for Snowflake, etc.)
import psycopg2

config = load_config()

# Connect to the warehouse using target credentials from config.json
target = config["target"]
conn = psycopg2.connect(
    host=target["host"],
    port=target["port"],
    database=target["database"],
    user=target["username"],
    password=target["password"],
    sslmode="require",
)
conn.autocommit = True
cursor = conn.cursor()

print(f"Connected to warehouse as: {target['username']}")

print("\nCreating schema metadata...")
cursor.execute("CREATE SCHEMA IF NOT EXISTS metadata")
print(" Schema created")

print("\nCreating table metadata.pipeline_watermarks...")
cursor.execute("""
CREATE TABLE IF NOT EXISTS metadata.pipeline_watermarks (
    -- Identity
    layer VARCHAR(50) NOT NULL,
    target_schema VARCHAR(100) NOT NULL,
    target_table VARCHAR(100) NOT NULL,

    -- Source tracking
    source_system VARCHAR(100),
    source_object VARCHAR(100),

    -- Watermark details
    watermark_column VARCHAR(100),
    watermark_value VARCHAR(500),
    watermark_type VARCHAR(50),

    -- Run metadata
    last_run_at TIMESTAMP,
    last_success_at TIMESTAMP,
    rows_processed BIGINT,

    -- Status tracking
    status VARCHAR(50),
    error_message TEXT,

    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (layer, target_schema, target_table)
)
""")
print(" Table metadata.pipeline_watermarks created")

print("\nAdding comments to table...")
cursor.execute("""
COMMENT ON TABLE metadata.pipeline_watermarks IS
'Tracks incremental load progress across all pipeline layers (RAW/STAGING/CORE/REPORT).
Watermark values represent the high-water mark from SOURCE SYSTEM data, not script run time.';
""")

cursor.execute("""
COMMENT ON COLUMN metadata.pipeline_watermarks.watermark_value IS
'High-water mark from SOURCE SYSTEM (e.g., MAX(updated_at) from extracted data), NOT script run timestamp';
""")
print(" Comments added")

# Verify table
print("\nVerifying table structure...")
cursor.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_schema = 'metadata'
      AND table_name = 'pipeline_watermarks'
    ORDER BY ordinal_position
""")
results = cursor.fetchall()

print("\nmetadata.pipeline_watermarks columns:")
for column, dtype, max_len in results:
    if max_len:
        print(f"  - {column}: {dtype}({max_len})")
    else:
        print(f"  - {column}: {dtype}")

# Get row count
cursor.execute("SELECT COUNT(*) FROM metadata.pipeline_watermarks")
count = cursor.fetchone()[0]
print(f"\nRow count: {count}")

cursor.close()
conn.close()

print("\n Metadata schema and pipeline_watermarks table created successfully!")
print("\nNext steps:")
print("  1. Create watermark helper functions (get_watermark, update_watermark)")
print("  2. Initialize watermarks for existing pipelines")
