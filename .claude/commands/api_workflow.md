# API Data Pipeline Workflow

## Directory Structure

```
project_root/
├── zero_setup/                      # Config, credentials, API client, DB client
├── one_scripts_local/               # Scripts to fetch data locally (validation phase)
├── two_insert_database_scripts/     # Scripts to upsert data to database
└── data/                            # Local JSON/CSV files for validation
```

---

## Phase 0: Setup (zero_setup/)

### Purpose
Prepare configuration, credentials, and shared utilities before writing data scripts.

### Contents
- `config.json` - API credentials, endpoints, database connection
- `api_client.py` - Generic API client with authentication and pagination
- `db_client.py` - Database connection and helper functions
- `.env` or credentials files (add to .gitignore)

### Checklist
- [ ] API credentials obtained and stored securely
- [ ] API documentation reviewed
- [ ] API client created with proper authentication
- [ ] Database connection configured
- [ ] All secrets added to .gitignore

---

## Phase 1: Local Data Extraction (one_scripts_local/)

### Purpose
Fetch data from API and save locally for validation BEFORE inserting into database.

### Rules

1. **Script name = endpoint name**
   - `/orders/search` → `orders.py`
   - `/products/list` → `products.py`
   - `/return_refund/returns` → `returns.py`

2. **Limit to first 2 pages initially**
   - Validate data structure before fetching all data
   - Prevents wasting API calls on broken scripts

3. **Save to data/ directory**
   - JSON format preferred for nested data
   - Filename matches script: `orders.py` → `data/orders.json`

4. **Include metadata**
   - Endpoint path
   - Fetch timestamp
   - Total count
   - Pages fetched

### Validation Steps

1. Run script and check output
2. Open JSON file and verify data structure
3. Check field names match API documentation
4. Verify data types (strings, integers, timestamps)
5. **Identify the primary key field** - the unique identifier from the source
6. Document findings

---

## Phase 2: Database Insertion (two_insert_database_scripts/)

### Purpose
Take validated local data and upsert into database with proper schema.

### Table Naming Convention

```
source_[source_name]_[endpoint_name]
```

Examples:
- `source_tiktok_orders`
- `source_shopify_products`
- `source_stripe_transactions`

### Primary Key Rules

**NEVER use auto-incremental IDs.**

1. Identify the unique identifier from the source data
2. Use that field as the primary key
3. This enables proper upserts (insert or update on conflict)

Examples:
| Endpoint | Primary Key |
|----------|-------------|
| orders | order_id |
| products | product_id |
| returns | return_id |
| transactions | transaction_id |

### Script Requirements

1. **Read from local file first** - `data/[endpoint].json`
2. **Create table if not exists** - Primary key is source's unique ID
3. **Upsert logic** - Insert new, update existing on conflict
4. **Truncate local file after successful insert** - Prevents re-inserting

---

## Phase 3: Validation & QA

### Database Verification

```sql
-- Count records
SELECT COUNT(*) FROM source_[source]_[endpoint];

-- Check sample data
SELECT * FROM source_[source]_[endpoint] LIMIT 10;

-- Check for duplicates
SELECT [primary_key], COUNT(*)
FROM source_[source]_[endpoint]
GROUP BY [primary_key]
HAVING COUNT(*) > 1;
```

### Null Column Investigation

Check for columns where ALL values are null:

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'source_[source]_[endpoint]';
```

**If a column has ALL null values:**

1. Go back to local files in `data/`
2. Check the raw JSON for that field
3. Verify field name and path (might be nested differently)
4. Check API documentation
5. Decision:
   - If genuinely always null → consider removing column
   - If parsing error → fix script and re-run

---

## Phase 4: Full Data Pull

After validation with 2 pages:

1. Update local scripts to remove page limit
2. Run full extraction: `python one_scripts_local/orders.py`
3. Run database insert: `python two_insert_database_scripts/orders.py`
4. Verify counts match between API response and database

---

## Endpoint Checklist

For each endpoint, complete all steps:

```
□ Phase 1a: Create local script in one_scripts_local/[endpoint].py
□ Phase 1b: Run with 2-page limit
□ Phase 1c: Validate JSON structure in data/[endpoint].json
□ Phase 1d: Identify primary key field (source's unique ID)

□ Phase 2a: Create insert script in two_insert_database_scripts/[endpoint].py
□ Phase 2b: Create table with primary key = source's unique ID (NOT auto-increment)
□ Phase 2c: Run insert script
□ Phase 2d: Truncate local file after success

□ Phase 3a: Query database to verify data exists
□ Phase 3b: Check for null columns
□ Phase 3c: If nulls found, verify against local files for parsing errors

□ Phase 4a: Remove 2-page limit from local script
□ Phase 4b: Run full extraction
□ Phase 4c: Run full insert
□ Phase 4d: Final count verification
```

---

## Key Rules Summary

| Rule | Why |
|------|-----|
| Always pull locally first | Debug before database insert |
| Never use auto-increment IDs | Use source's unique ID for upserts |
| Start with 2 pages | Validate before full pull |
| Script name = endpoint name | Easy to trace and maintain |
| Check null columns | May indicate parsing bugs |
| Truncate after insert | Prevent duplicate inserts |
| Table name = source_[source]_[endpoint] | Clear data lineage |

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| All values in column null | Wrong field path in parsing | Check JSON structure, fix field name |
| Duplicate key errors | Primary key not unique | Verify correct unique field from source |
| Missing data | Pagination broken | Check next_page_token logic |
| API errors | Rate limiting | Add delays between calls |
| Empty files | No data in date range | Expand date range |
| Count mismatch | Pagination stopped early | Check for API errors in logs |
