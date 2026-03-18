# Schema Drift Protection

## The Problem

Source databases and APIs add new columns/fields without notice. If a pipeline extracts those new columns but the warehouse target table doesn't have them yet, the COPY or INSERT fails with `UndefinedColumn` errors.

## The Rule

**Never use `SELECT *` or dynamic source-column discovery.** Always select only the columns that exist in the warehouse target DDL.

---

## How Each Source Type Is Protected

### Internal DB Sources (DB → Warehouse)

**Mechanism:** `_get_safe_columns()` function in DB source extractors

This function:
1. Queries `information_schema.columns` on the **source** DB to get its current column list
2. Queries `information_schema.columns` on the **warehouse** to get the target table's column list
3. Returns only the **intersection** — columns present in both, in warehouse column order
4. Excludes `inserted_at` (added by IO manager, not from source)

The `extract()` function then builds `SELECT col1, col2, col3 FROM table` using that intersection. New source columns not yet in the warehouse DDL are silently skipped — the pipeline does not break.

```python
# Pattern used in DB source extractors
target_config = config['target']
safe_cols = _get_safe_columns(conn, source_table, target_config, target_schema, target_table)
col_list = ", ".join(f'"{c}"' for c in safe_cols)
query = f'SELECT {col_list} FROM public."{source_table}" WHERE ...'
```

---

### API Sources (HTTP → Warehouse)

APIs return JSON — there is no `SELECT *`. Protection works via field selection instead:

| Source | Mechanism |
|---|---|
| Dynamic API (e.g. Salesforce) | `extractor.py` queries warehouse `information_schema` and only requests those fields from the API. Same intersection pattern as internal DB. |
| APIs with explicit mappers | Hardcoded mapper functions that name every field. New API fields are simply not included. |
| APIs with field_mappings | `field_mappings` in `config.yaml`. Asset factory transform step only picks mapped fields — new API fields are discarded. |

---

## What Happens When Source Adds a Column

| Source type | Behavior |
|---|---|
| Internal DB | New column is in source DB but not in warehouse DDL → `_get_safe_columns` intersection excludes it → pipeline runs normally, new column is skipped |
| API with field_mappings | New API field is not in `field_mappings` → asset factory transform ignores it → pipeline runs normally |
| API with hardcoded mappers | New API field is not in the mapper → ignored → pipeline runs normally |

**In all cases: pipeline does not break.** The new column simply doesn't land in the warehouse until you:
1. Add it to the warehouse DDL (`ALTER TABLE ADD COLUMN`)
2. On the next run, `_get_safe_columns` (or the mapper) will include it automatically

---

## IO Manager: Column Intersection (Safety Net)

Even if an extractor passes extra columns, the IO manager provides a second layer of protection:

1. After COPY/INSERT into staging, it queries `information_schema.columns` for the **target** table
2. Computes `safe_columns = target_cols ∩ ndjson_cols`
3. MERGE only uses `safe_columns` — extra columns in staging are never written to the target

This means schema drift cannot cause pipeline failures even if the extractor-level protection is incomplete.

---

## Summary

All active Dagster extractors are protected from schema drift. The mechanism differs by source type but the outcome is the same: new source additions are silently skipped rather than causing pipeline failures.
