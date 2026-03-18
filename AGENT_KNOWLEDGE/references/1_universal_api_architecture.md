# 1. Universal API Architecture

**Step 1 of 3.** Sequence: **1 (this doc) → 2 (Pipeline) → 3 (Dagster).** Handoff is strict: finish Step 1 before Step 2; finish Step 2 before Step 3.

**Purpose:** Connect to an API and get a test run going — authenticate, pull a small sample to local JSON, and document primary key and incremental strategy. Step 1 does **not** load to data warehouse or run the full pipeline. That is Step 2 ([2. Universal Pipeline Architecture](universal_pipeline_architecture.md)). Step 3 is [3. Universal Dagster Architecture](universal_dagster_architecture.md) (assets and schedules).

---

## Table of Contents

1. [Position in the Workflow (1 → 2 → 3)](#position-in-the-workflow-1--2--3)
2. [Naming (for Handoff to Step 2)](#naming-for-handoff-to-step-2)
3. [Directory Structure](#directory-structure)
4. [Phase 0: Setup & Connection](#phase-0-setup--connection)
5. [Phase 1: Initial Extraction (Test Run)](#phase-1-initial-extraction-test-run)
6. [Incremental Strategy (What to Identify)](#incremental-strategy-what-to-identify)
7. [API-Specific Patterns](#api-specific-patterns)
8. [Troubleshooting](#troubleshooting)
9. [Handoff to Step 2 (Pipeline)](#handoff-to-step-2-pipeline)

---

## Position in the Workflow (1 → 2 → 3)

| Step | Document | Outcome |
|------|----------|---------|
| **1** | This document (API) | Working connection, sample in `data/temp/{table}.json`, PK and incremental strategy documented |
| **2** | [2. Universal Pipeline Architecture](universal_pipeline_architecture.md) | DDL, load to data warehouse, watermarks, full sync, validation |
| **3** | [3. Universal Dagster Architecture](universal_dagster_architecture.md) | Assets, schedules, orchestration |

Do not start Step 2 until Step 1 is done (test run + documented PK and incremental strategy). Do not start Step 3 until Step 2 is done.

---

## 🚨 CRITICAL RULES: JSON Data & Large Datasets

**RULE 1: ALWAYS use JSON column type (JSONB/VARIANT/SUPER depending on warehouse) columns for JSON data**
- When inspecting API response, identify ANY column containing JSON arrays or objects
- Examples: `["tag1", "tag2"]`, `{"name": "John", "age": 30}`, nested objects
- In DDL (Step 2): Create these columns as `JSON column type (JSONB/VARIANT/SUPER depending on warehouse)` type in data warehouse
- In field_mappings (Step 3): Do NOT use `json_dump` transform - pass raw dicts/lists through
- **Why:** JSON column type (JSONB/VARIANT/SUPER depending on warehouse) columns let data warehouse query JSON fields directly (e.g., `WHERE data.name = 'John'`) instead of parsing strings

**RULE 2: ALWAYS use bulk load (S3 COPY / COPY FROM / PUT+COPY INTO depending on warehouse) + NDJSON for large datasets (1000+ rows)**
- For any endpoint with 1000+ rows, use `load_method: s3_copy` in config.yaml (Step 3)
- Extractor streams to NDJSON file (newline-delimited JSON), returns file path
- IO Manager uploads to S3 → data warehouse COPY (10-100x faster than row-by-row INSERT)
- **Why:** bulk load (S3 COPY / COPY FROM / PUT+COPY INTO depending on warehouse) is data warehouse's optimized bulk loader - handles millions of rows efficiently

**These are INDEPENDENT concepts:**
- **SUPER** = column type for JSON data (use when column contains JSON)
- **bulk load (S3 COPY / COPY FROM / PUT+COPY INTO depending on warehouse)** = load method for speed (use when table is large)
- You can have: bulk load (S3 COPY / COPY FROM / PUT+COPY INTO depending on warehouse) without SUPER, or SUPER without bulk load (S3 COPY / COPY FROM / PUT+COPY INTO depending on warehouse), or both together

**Document in Step 1:**
- [ ] List all columns containing JSON arrays/objects → mark for JSON column type (JSONB/VARIANT/SUPER depending on warehouse) type in Step 2
- [ ] Estimate row count → if 1000+, note "use s3_copy" for Step 3

---

## Naming (for Handoff to Step 2)

**Full naming rules live in Step 2.** For handoff from Step 1, use only:

- **Schema:** `raw_{api_name}` (e.g. `raw_salesforce`, `raw_hubspot`).
- **Table:** Endpoint name only (e.g. `accounts`, `contacts`). No source prefix in table name.
- **Primary key:** Source system’s unique ID — document it in Step 1 (e.g. `Id`, `id`).
- **Local file:** `data/temp/{table}.json`.

Audit columns, script naming, and all other conventions are defined in Step 2.

---

## Directory Structure

**Full layout is defined in Step 2.** For Step 1, create only:

- `api/api_{source}/admin/` — for `connect.py` and listing endpoints.
- `api/api_{source}/data/temp/` — for saving sample JSON.

Do not create `ddl/`, `backfill/`, or `pipelines/` in Step 1; those are used in Step 2.

---

## Phase 0: Setup & Connection

**Goal:** Add credentials, test authentication, and list available endpoints.

**Tasks:**
- [ ] Add API credentials to `config.json` (or use env; secrets not in repo).
- [ ] Review API documentation (e.g. Context7 MCP).
- [ ] Create `admin/connect.py` to test authentication and list endpoints/objects.
- [ ] Document which endpoints you will extract (for Step 2).

**Deliverables:**
- `config.json` (or equivalent) updated with API config keys.
- `api/api_{source}/admin/connect.py` — connection tester.
- List of endpoints/objects to extract.

**Example connect.py:**
```python
#!/usr/bin/env python3
"""Test API connection and list available endpoints."""

import json
import requests
from pathlib import Path

config_path = Path(__file__).parent.parent.parent.parent / 'config.json'
with open(config_path) as f:
    config = json.load(f)

api_config = config['salesforce']  # or hubspot, stripe, etc.

headers = {'Authorization': f'Bearer {api_config["access_token"]}'}
response = requests.get('https://api.example.com/v1/objects', headers=headers)

if response.status_code == 200:
    print("✅ Authentication successful")
    print(f"Available objects: {response.json()}")
else:
    print(f"❌ Authentication failed: {response.status_code}")
```

---

## Phase 1: Initial Extraction (Test Run)

**Goal:** Pull a small sample from the API, save to local JSON, and document primary key and incremental strategy for Step 2.

**Tasks:**
- [ ] Create a script (or use admin tooling) to call one endpoint.
- [ ] Fetch **only 2 pages** or **LIMIT 100 records**.
- [ ] Save raw response to `data/temp/{table}.json`.
- [ ] Inspect JSON: field names, nesting, types.
- [ ] Identify and document: **primary key** (source’s unique ID).
- [ ] Identify and document: **incremental strategy** (timestamp field, cursor, or full refresh).
- [ ] Document findings (for Pipeline step).

**Script requirements:**
1. Load config from `config.json`.
2. Authenticate with the API.
3. Fetch with pagination, **limited to 2 pages or 100 records**.
4. Save raw JSON to `data/temp/{table}.json`.
5. Include minimal metadata in the file (e.g. extracted_at, record count).

**Example structure:**
```python
#!/usr/bin/env python3
"""Extract Salesforce Accounts — test run only (2 pages)."""

import json
import requests
from pathlib import Path
from datetime import datetime

config_path = Path(__file__).parent.parent.parent.parent / 'config.json'
with open(config_path) as f:
    config = json.load(f)

api_config = config['salesforce']
PAGE_LIMIT = 2
url = 'https://your-org.my.salesforce.com/services/data/v59.0/query'
query = "SELECT Id, Name, Type, CreatedDate, LastModifiedDate FROM Account LIMIT 200"

headers = {'Authorization': f'Bearer {api_config["access_token"]}'}
response = requests.get(url, headers=headers, params={'q': query})
data = response.json()

output_file = Path(__file__).parent.parent / 'data/temp/accounts.json'
output_file.parent.mkdir(parents=True, exist_ok=True)

output = {
    'metadata': {
        'extracted_at': datetime.now().isoformat(),
        'source': 'Salesforce Account',
        'total_records': len(data.get('records', [])),
        'page_limit': PAGE_LIMIT
    },
    'records': data.get('records', [])
}

with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)

print(f"✅ Extracted {len(output['records'])} records to {output_file}")
```

**Checklist before moving to Step 2:**
- [ ] JSON file exists in `data/temp/`.
- [ ] Records present; structure matches API docs.
- [ ] **Primary key** identified and documented (e.g. `Id`, `id`).
- [ ] **Incremental strategy** identified and documented (timestamp column, cursor, or full refresh).
- [ ] Nested objects noted (for Step 2 mapping).

---

## Data Handling for Full Extraction (Step 2)

**CRITICAL: Zero-Memory NDJSON Pattern for Production Pipelines**

While **Step 1** test runs (2 pages, ~100 records) can save directly to JSON, **Step 2** full extraction pipelines **MUST** use the zero-memory NDJSON streaming pattern.

### 🚨 MANDATORY RULES for All API Extractors

1. **Return `str` (file path), NEVER `list[dict]`** — The IO manager's `_handle_ndjson_file()` accepts a file path and streams it to S3 → data warehouse COPY. Returning a list loads all records into memory → OOM on K8s pods.
2. **Format MUST be NDJSON** (newline-delimited JSON, one record per line) — NOT CSV. The asset_factory and IO manager are built for NDJSON + bulk load (S3 COPY / COPY FROM / PUT+COPY INTO depending on warehouse).
3. **Write each record immediately** — Open the file once, write line-by-line per API page. NEVER accumulate in a list.
4. **Output directory:** `_LOCAL_FILES/{source}/{table}_{timestamp}.ndjson` (relative to repo root).
5. **NEVER accumulate all API responses in memory** — Maximum 1 API page in memory at any time.

### Test Run (Step 1) - Direct Save OK
```python
# Step 1: Small sample - direct save is fine
records = api_fetch_limited(limit=100)
with open('data/temp/table.json', 'w') as f:
    json.dump(records, f)
```

### Full Extraction (Step 2) - MUST Use NDJSON Streaming

**MANDATORY Pattern:**
1. **Open NDJSON output file at the start of `extract()`**
2. **Per API page: write records immediately to file** (no list accumulation)
3. **Return file path string** — IO manager handles S3 upload → data warehouse COPY

**Canonical pattern for REST/JSON APIs:**
```python
def extract(context, from_date: str, to_date: str, asset_config: dict) -> str:
    """Returns NDJSON file path (str). IO manager streams file → S3 → data warehouse COPY."""
    from pathlib import Path
    from datetime import datetime, timezone
    import json

    _REPO = Path(__file__).resolve().parent.parent.parent.parent.parent
    output_dir = _REPO / "_LOCAL_FILES" / "source_name"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{target_table}_{timestamp}.ndjson"

    count = 0
    with open(output_file, "w", encoding="utf-8") as f:
        after_cursor = None
        while True:
            records, after_cursor = api_client.fetch_page(limit=100, after=after_cursor)
            if not records:
                break
            for record in records:
                f.write(json.dumps(record, default=str) + "\n")
                count += 1
            if not after_cursor:
                break

    context.log.info(f"Wrote {count:,} records to {output_file}")
    return str(output_file)  # ← ALWAYS return str, never list
```

### Gzip Downloads (e.g. Gzip Export API)

**NEVER:** `gzip.decompress(response.content)` + `.split('\n')` + `events = []` list — this loads the entire compressed file into memory then builds a full in-memory list.

**CORRECT — stream gzip line-by-line:**
```python
import gzip
import io
import requests

def _stream_export_to_file(download_url, output_file, context) -> int:
    """Stream gzip export → decompress line-by-line → write NDJSON. Returns row count."""
    count = 0
    with requests.get(download_url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with gzip.GzipFile(fileobj=io.BufferedReader(resp.raw)) as gz:
            with open(output_file, "w", encoding="utf-8") as f:
                for raw_line in gz:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        f.write(json.dumps(record, default=str) + "\n")
                        count += 1
                    except json.JSONDecodeError:
                        continue
    return count
```

**Why This Matters:**
- ❌ `gzip.decompress(response.content)` = entire compressed file in RAM
- ❌ `.split('\n')` = entire decompressed string in RAM
- ❌ `events = []` list = all records in RAM → K8s pod OOM kill
- ✅ `requests.get(stream=True)` + `gzip.GzipFile(fileobj=...)` = constant memory regardless of file size

**Complete Implementation Guide:** See [Zero-Memory Pipeline Pattern](../docs/zero_memory_pipeline_pattern.md)

**Summary checklist for every API extractor:**
- [ ] Returns `str` (NDJSON file path), not `list[dict]`
- [ ] Output file in `_LOCAL_FILES/{source}/{table}_{timestamp}.ndjson`
- [ ] Opens file once, writes line-by-line per API page
- [ ] Gzip downloads use `requests.get(stream=True)` + `gzip.GzipFile(fileobj=io.BufferedReader(resp.raw))`
- [ ] No in-memory list accumulation at any point

---

## Incremental Strategy (What to Identify)

When inspecting the sample, decide which strategy the pipeline will use in Step 2. Document your choice.

| Priority | Strategy | What to look for | Use when |
|----------|----------|------------------|----------|
| 1 | **Modified timestamp** | `LastModifiedDate`, `updated_at`, `modifiedAt`, `lastUpdated` | API supports filter by this field; best for new + updated rows. |
| 2 | **Created timestamp** | `CreatedDate`, `created_at`, `createdAt` | No modified date; catches new rows only. |
| 3 | **Cursor/token** | `nextPageToken`, `cursor`, `after` | Append-only or cursor-based APIs. |
| 4 | **Full refresh** | — | Small dataset (<10k rows), no suitable filter. |
| 5 | **Discuss** | — | No clear option; agree approach before Step 2. |

Step 2 will implement the chosen strategy using the pipeline watermark table and load logic.

---

## API-Specific Patterns

**Salesforce (SOQL):**  
Incremental: `LastModifiedDate`. Pagination: `nextRecordsUrl`.  
Sample query: `SELECT Id, Name, LastModifiedDate FROM Account WHERE LastModifiedDate > {value}`.

**HubSpot (REST v3):**  
Incremental: `hs_lastmodifieddate` or `updatedAt`. Pagination: `after` cursor.  
Example: `GET /crm/v3/objects/contacts?after={cursor}&limit=100`.

**REST (generic):**  
Incremental: `updated_since` or similar query param. Pagination: `page` / `offset` + `limit`.

---

## Troubleshooting

- **429 Rate limit:** Use `Retry-After` and exponential backoff; add short sleep between pages.
- **Auth expiry:** Implement token refresh in connect/fetch logic; long runs may need refresh mid-run.
- **Nested JSON:** Note structure for Step 2; pipeline will flatten or map to columns.
- **Large responses:** Consider streaming or chunking in Step 2; for Step 1, limit size with page/limit.

---

## Handoff to Step 2 (Pipeline)

You are done with **Step 1** when:

1. **connect.py** runs successfully and you can list endpoints.
2. **Sample data** is in `data/temp/{table}.json` for each endpoint you plan to load.
3. **Primary key** and **incremental strategy** are documented per endpoint.

**Critical for Step 2:**
- Step 2 full extraction **MUST** use NDJSON zero-memory streaming pattern
- Extractor returns `str` (NDJSON file path) — NEVER `list[dict]`
- Output file in `_LOCAL_FILES/{source}/{table}_{timestamp}.ndjson`
- IO Manager streams NDJSON file → S3 upload → data warehouse COPY (never row-by-row insert)
- Gzip downloads: use `requests.get(stream=True)` + `gzip.GzipFile(fileobj=io.BufferedReader(resp.raw))` — never `gzip.decompress(response.content)`
- See "Data Handling for Full Extraction" section above for canonical patterns

**Next:** Open **[2. Universal Pipeline Architecture](universal_pipeline_architecture.md)** (Step 2). It will use your sample and documentation to create DDL, load to data warehouse, set watermarks, run validation, and full sync. After Step 2 is complete, use **[3. Universal Dagster Architecture](universal_dagster_architecture.md)** (Step 3) for assets and schedules.

---

**Last Updated:** 2026-02-09  
**Document 1 of 3.** No overlap with 2 or 3: this doc = connection + test run only. No data warehouse, watermark, or pipeline execution.
