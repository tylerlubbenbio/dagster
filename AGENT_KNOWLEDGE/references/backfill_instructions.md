# Backfill Instructions (Warehouse-to-Warehouse)

> **Note:** This document uses generic warehouse terminology. Run /activate to get database-specific instructions in _RESOURCES/{db}.md.

Short, repeatable steps for backfilling many tables across different pipelines.

---

## Where the data is (avoid confusion)

- **Warehouse connection:** Use the config key **`target`** (in `config.json`). This is the **only** data warehouse — we are always in this cluster. All reads and writes use `config['target']`.
- **Source data:** The user will give you the **schema** name where the source data lives (e.g. `permissions`, `chat`). That schema is **in this same warehouse** (the target). There is no other database: source = a schema in current warehouse, target = a `raw_*` schema in the same warehouse.
- **Summary:** One data warehouse (`target`). User provides source schema name → copy from `"{source_schema}".{table}` into `raw_*.{table}`.
- **Table list:** Go to the **source schema** (in this same warehouse) and get the list of tables to mimic. **Exclude internal/temporary tables** — do **not** copy tables with names like `_airbyte_tmp`, `_airbyte_tmp_*`, or any suffix/prefix that indicates a temp or staging table (e.g. `*_tmp`, `_tmp_*`). ETL tools create these for sync; they are not source-of-truth tables. Query: `SELECT table_name FROM information_schema.tables WHERE table_schema = '<source_schema>' AND table_name NOT LIKE '%_airbyte_tmp%' AND table_name NOT LIKE '%\_tmp%' ORDER BY table_name` (adjust NOT LIKE as needed for your DB). Use only the resulting list for DDL and backfill.

---

## Source = warehouse schema (only)

**Backfill always reads from data already in the warehouse.** You are given the **schema** name (e.g. `permissions`, `chat`). We do **not** pull from MySQL, Postgres, APIs, etc. — that data is already in a schema in the current warehouse; we copy from that schema into the raw_* target schema.

---

## When to use

- Source data is already in a warehouse schema (you give the schema name).
- One-time copy from that schema into a raw_* schema (e.g. `raw_permissions`, `raw_chat`).
- Same pattern for any `api/internal_*` or `api/api_*` directory.

---

## Strategy (warehouse-to-warehouse)

1. **TRUNCATE** the target table.
2. **Single INSERT SELECT** — no batching:
   `INSERT INTO raw_*.{table} SELECT ... FROM "{source_schema}".{table}`
3. Completes in minutes even for large tables.

---

## Unique identifier (primary key) — mandatory

**Every table must have a primary key.** No exceptions. Do not write DDL until every table has a defined unique identifier.

**You must do this before writing any DDL:**

1. **Get the table list** from the source schema (`information_schema.tables`).
2. **For each table, determine the primary key:**
   - **Check if the source table already has a PK:**
     `SELECT kcu.column_name FROM information_schema.table_constraints tc JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name WHERE tc.table_schema = '<source_schema>' AND tc.table_name = '<table>' AND tc.constraint_type = 'PRIMARY KEY' ORDER BY kcu.ordinal_position`
     If it returns columns, use that (single column or composite).
   - **If no PK in source, look for an obvious single-column unique identifier:**
     Common names: `id`, `uuid`, `_id`, `account_id`, etc. If one exists and is NOT NULL (or will be), use it.
   - **If there is no obvious single-column key, you must propose composite keys.**
     A **composite key** is a set of columns that together uniquely identify each row (e.g. `(resource_type, level, context)`). Query the table's columns and consider: NOT NULL columns, natural business keys (e.g. type + level + context, or tenant_id + entity_id). **Present your proposed composite key(s) to the user** with a short justification (e.g. "Columns X, Y, Z are all NOT NULL and together look unique") and **do not write DDL until the user approves** which key to use.
3. **Document the chosen primary key for every table** (e.g. in a small table: Table → PK columns). Use this in the DDL script (e.g. `PRIMARY_KEYS = {"table1": ("id",), "table2": ("col_a", "col_b", "col_c")}`).

**Summary:** Single-column key when obvious (id, uuid, etc.); otherwise determine composite key and **present options to the user for approval** before implementing.

---

## Per-table checklist

### 1. DDL (create schema + table)

**First:** Query the source schema for the list of tables to mimic. **Exclude ETL/internal temp tables** (e.g. names containing `_airbyte_tmp`, `_tmp`). Example: `SELECT table_name FROM information_schema.tables WHERE table_schema = '<source_schema>' AND table_name NOT LIKE '%_airbyte_tmp%' ORDER BY table_name`. Do not create or backfill `*_airbyte_tmp*` or similar — only real business tables. Use that filtered list for all steps below.

**Before writing any DDL:** For each table, determine the primary key using the steps in **Unique identifier (primary key) — mandatory** above. If you need a composite key, propose it to the user and get approval. Then implement in DDL (add PRIMARY KEY in script).

**Easiest: create from source table (exact replica), then add audit column.**

1. **CREATE SCHEMA** `raw_{source_name}`.
2. **CREATE TABLE** target as replica of source:
   ```sql
   CREATE TABLE raw_{source}.{table} (LIKE "source_schema".{table});
   ```
   Quote the source schema if it's a reserved word (e.g. `"permissions"`).
3. **Drop ETL columns** (if present):
   Before dropping distribution/sort key columns, alter the table's distribution and sort settings first. Use try/except that only ignores errors for "same distribution" or "same sort key" conditions; re-raise all others. Not all warehouses support `DROP COLUMN IF EXISTS` — only drop columns you found via `information_schema`.
   - # ACTIVATE: distribution/clustering — set appropriate distribution style before dropping columns
   - # ACTIVATE: sort/clustering — set sort key before dropping columns
4. **Add audit column:**
   - If source has **no** `updated_at` → `ADD COLUMN inserted_at`, `ADD COLUMN updated_at`.
   - If source **has** `updated_at` → `ADD COLUMN inserted_at` only.
5. **Make DDL idempotent:** Before adding audit columns, check if they already exist (query `information_schema.columns`). Only `ADD COLUMN` if missing. That way re-running the DDL fixes tables that were created without audit columns (e.g. CREATE ran but ALTER failed or was skipped).
6. **Ensure primary key:** Every table must have a PRIMARY KEY (single column or composite). You must have determined it in the "Unique identifier — mandatory" step above. In the DDL script: add `PRIMARY_KEYS = {"table": ("id",), ...}` (or `("col_a", "col_b")` for composite), then after creating the table add the constraint if missing. `LIKE` does not copy PK constraints in all warehouses. PK columns must be NOT NULL; if they're nullable you must recreate the table or warn.

No hand-written column lists — same types and structure as source.

- **Script location:** `api/internal_{source}/ddl/create_raw_{source}_schema.py` (or under `api/api_*`).
- **Connection:** Warehouse only — use **`config['target']`** (load from repo root `config.json`). This is the warehouse we're in; the user will tell you the **source schema** name in this same warehouse.

**DDL script pattern — follow the sample below.**

```python
# Load config from repo root; connect with config["target"]
config_path = Path(__file__).parent.parent.parent.parent / "config.json"
with open(config_path) as f:
    config = json.load(f)
target = config["target"]
conn = connect_warehouse(target)   # use your warehouse connector
conn.autocommit = True   # always True — never False

SOURCE_SCHEMA = "permissions"   # user gives you this; quote if reserved e.g. '"permissions"'
TARGET_SCHEMA = "raw_permissions"
TABLES = ["permission", "resource_hierarchy", ...]   # from information_schema.tables in source schema

cursor = conn.cursor()
cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {TARGET_SCHEMA}")

for table in TABLES:
    cursor.execute(f'CREATE TABLE IF NOT EXISTS {TARGET_SCHEMA}.{table} (LIKE {SOURCE_SCHEMA}.{table})')

    # ETL columns: adjust distribution/sort then drop (try/except only for "same distribution" / "same sort key")
    cursor.execute("""SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s AND column_name LIKE '_airbyte%%'""", (TARGET_SCHEMA, table))
    etl_cols = [r[0] for r in cursor.fetchall()]
    if etl_cols:
        # # ACTIVATE: distribution/clustering — alter distribution style if needed
        # # ACTIVATE: sort/clustering — alter sort key if needed
        for col in etl_cols:
            cursor.execute(f'ALTER TABLE {TARGET_SCHEMA}.{table} DROP COLUMN "{col}"')

    # Add audit columns if missing (check information_schema first).
    # Add PRIMARY KEY if missing — use PRIMARY_KEYS[table] (single or composite); only add if key cols are NOT NULL.
cursor.close()
conn.close()
```

Rules: **autocommit = True** only. **No rollback(), no continue.** **Try/except** only around warehouse-specific ALTER operations; re-raise everything else.

### 2. Backfill (one-time copy)

- **Order:** Create schema/table first (DDL), then **have the user look at the table** (structure/columns, empty) before running inserts. Then run backfill.
- **SQL pattern:**
  ```sql
  TRUNCATE TABLE raw_{source}.{table};

  INSERT INTO raw_{source}.{table} (
    col1, col2, ..., inserted_at   -- or ..., inserted_at, updated_at
  )
  SELECT
    col1, col2, ..., CURRENT_TIMESTAMP   -- or ..., CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
  FROM "source_schema".{table}
  ```
- **Source schema:** The schema name the user gave you — it's in the **same warehouse** (target). Quote if reserved: `"permissions".{table}`.
- **Columns:** List every target column explicitly. Exclude `_airbyte_*` from the SELECT. Add `inserted_at` (and `updated_at` if the table has no source `updated_at`) with `CURRENT_TIMESTAMP`.

### 3. Run order and how to run

**Always run DDL and backfill scripts in the background** so long warehouse operations don't block the terminal or get killed (e.g. SSH disconnect). From repo root:

```bash
# Run DDL in background (run first)
nohup python3 api/internal_{source}/ddl/create_raw_{source}_schema.py > _LOGS/ddl_raw_{source}.log 2>&1 &

# Run backfill per table in background (after DDL finishes)
nohup python3 api/internal_{source}/backfill/backfill_raw_{source}_{table}.py > _LOGS/backfill_raw_{source}_{table}.log 2>&1 &
```

Check logs in `_LOGS/` and use `jobs` or `tail -f _LOGS/...` to monitor. Wait for DDL to finish, then **have the user look at the table** (e.g. `SELECT * FROM raw_*.{table} LIMIT 0` or describe columns) before starting backfill(s).

**Order:** (1) Run DDL first (creates schema + empty tables). (2) **Have the user look at the table** (structure, columns, empty state) before starting inserts. (3) Run backfill for each table. (4) If backfill fails with `column "inserted_at" … does not exist`, re-run the DDL (idempotent), then run the backfill again.

---

## Directory pattern (any pipeline)

```
api/internal_{source}/
├── ddl/
│   └── create_raw_{source}_schema.py   # CREATE SCHEMA + CREATE TABLE(s)
├── backfill/
│   └── backfill_raw_{source}_{table}.py   # optional; or inline TRUNCATE + INSERT SELECT
├── admin/
├── pipelines/
└── data/temp/
```

Same idea for `api/api_{source}/`: use `ddl/` and `backfill/` in that folder.

**Dagster raw layer:** For pipelines orchestrated by Dagster, DDL and backfill live under **`dagster/ingestion/raw/`**: e.g. `dagster/ingestion/raw/internal_raw_chat/ddl/`, `dagster/ingestion/raw/internal_raw_chat/backfill/`. Same pattern (ddl/, backfill/, admin/, pipelines/); use `config['target']` for the warehouse. The paths above (`api/internal_{source}/`) may refer to a legacy or non-Dagster layout.

---

## Common problems and fixes

| Problem | Cause | Fix |
|--------|--------|-----|
| `column "inserted_at" of relation "…" does not exist` | Target table was created (e.g. via LIKE) but audit columns were never added (ALTER failed or was skipped). | Re-run the DDL script. It is idempotent and will add missing `inserted_at` / `updated_at`. Then run the backfill again. Never run backfill before DDL. |
| `syntax error … DROP COLUMN IF EXISTS` | Some warehouses do not support `DROP COLUMN IF EXISTS`. | Only drop columns you found in `information_schema` (don't use IF EXISTS). |
| Cannot drop a column that is the distribution or sort key | Source table created with LIKE copies distribution/sort settings; ETL tools often use their own metadata columns. Some warehouses won't drop a column that is the distribution or sort key. | Before dropping any ETL columns: alter the table's distribution style and sort key settings first (see DDL pattern above). Make these ALTERs idempotent (try/except and ignore "same distribution style" / "same sort key" errors). |
| `Can not alter table to same distribution style` | Re-running DDL; table is already at the target distribution style. | Use try/except in the DDL and ignore this error so the script is idempotent. |
| Duplicate tables with `_airbyte_tmp` (or `_tmp`) suffix | Table list was taken from `information_schema.tables` without filtering; ETL tools create temp tables with these names. | **Exclude** any table whose name contains `_airbyte_tmp` or `_tmp` when building the list. Query with `AND table_name NOT LIKE '%_airbyte_tmp%'` (and similar). Only copy real business tables. |

---

## Quick reference

| Item    | Action |
|---------|--------|
| Source  | User gives the **schema** name; that schema is in the same warehouse (`config['target']`). Not MySQL/Postgres/API. |
| Copy    | Single TRUNCATE + INSERT SELECT. No batching. |
| Columns | No `_airbyte_*`. Add inserted_at; add updated_at only if source has no updated_at. |
| Schema  | Quote if reserved: `"permissions".table` |
| Config  | `config['target']` for warehouse; path: `Path(__file__).parent.../config.json` |
| Run     | Always run DDL and backfill scripts in the background (e.g. `nohup ... &`), log to `_LOGS/`. |
| Primary key | **Mandatory for every table.** Single column (id, uuid) or composite. Determine before DDL; if no obvious key, propose composite and get user approval. Add in DDL; LIKE does not copy PK in all warehouses. |
| Table list | Exclude internal/temp tables: do **not** copy `_airbyte_tmp`, `*_airbyte_tmp*`, or `*_tmp*`. Filter them out when querying `information_schema.tables`. Only real business tables. |

---

**Last updated:** 2026-02-04
