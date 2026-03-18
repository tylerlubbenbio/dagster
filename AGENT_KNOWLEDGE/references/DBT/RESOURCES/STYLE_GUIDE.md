# STYLE_GUIDE.md — {{project_name}}_analytics

> **PURPOSE:** Technical structure rules for all dbt code in this project. Every model MUST comply with these rules and pass SQLFluff linting.

---

## 1. SQL FORMATTING

### Casing
- All SQL keywords MUST be lowercase: `select`, `from`, `where`, `join`, `group by`, `order by`, `with`, `as`
- All column names MUST be lowercase `snake_case`
- All table/model names MUST be lowercase `snake_case`
- NEVER use capital letters anywhere in SQL

### Indentation
- Use 4 spaces (not tabs)
- Indent column lists under `select` by 4 spaces
- Indent `on` clauses under `join` by 4 spaces
- Indent conditions under `where` by 4 spaces

### Line Breaks
- Every column in a `select` gets its own line
- Every `join` starts on a new line
- Every `and`/`or` in a `where` starts on a new line
- Opening and closing parentheses for subqueries get their own lines

### Trailing Commas (Project Standard)

Trailing commas are the standard for this project. Use them on every column list:

```sql
select
    user_id,
    user_name,
    email,
    created_at,
from {{ ref('stg_{{source}}__{{entity_plural}}') }}
```

Trailing commas go AFTER the column name, including the last column in the list. This makes diffs cleaner and reordering easier.

### Whitespace
- Blank line between each CTE
- Blank line before `from`, `where`, `group by`, `order by`
- Blank line before and after comment blocks
- DO NOT compress or minimize whitespace

---

## 2. NAMING CONVENTIONS

### Table/Model Prefixes by Layer

| Layer    | Prefix     | Example                          |
|----------|------------|----------------------------------|
| Raw      | `raw_`     | `raw_salesforce`                 |
| Staging  | `stg_`     | `stg_salesforce__accounts`       |
| Core Dim | `dim_`     | `dim_account`                    |
| Core Fact| `fct_`     | `fct_crunches`                   |
| Analytics| `{team}_`  | `product_monthly_usage`          |
| Report   | `rpt_`     | `rpt_executive_dashboard`        |
| Snapshot | `snap_`    | `snap_salesforce__accounts`      |

### Segment Separator

- Use `__` (double underscore) to separate logical name segments: `stg_salesforce__accounts`
- Use `_` (single underscore) to separate words within a segment: `dim_account_health`

### Column Suffixes

| Suffix    | Data Type    | Example               |
|-----------|--------------|-----------------------|
| `_id`     | Natural Key  | `account_id`          |
| `_sk`     | Surrogate Key (MD5) | `account_sk`   |
| `_at`     | Timestamp    | `created_at`          |
| `_date`   | Date only    | `start_date`          |
| `_name`   | Name string  | `organization_name`   |
| `_amount` | Currency     | `deal_amount`         |
| `_count`  | Count metric | `crunch_count`        |
| `_pct`    | Percentage   | `completion_pct`      |
| `_flag`   | Boolean int  | `is_deleted_flag`     |

### Column Prefixes

| Prefix    | Data Type    | Example               |
|-----------|--------------|-----------------------|
| `is_`     | Boolean      | `is_active`           |
| `has_`    | Boolean      | `has_subscription`    |
| `total_`  | Aggregate    | `total_revenue`       |
| `avg_`    | Average      | `avg_crunch_duration` |
| `min_`/`max_` | Extremes | `min_start_date`     |

---

## 3. COLUMN ORDER

Every final CTE MUST order columns in this sequence:

```
1. Primary Surrogate Key     →  account_sk
2. Foreign Surrogate Keys    →  organization_sk, user_sk
3. Natural Keys              →  account_id
4. Attributes                →  account_name, industry
5. Metrics                   →  crunch_count, document_count
6. Audit / Metadata          →  created_at, updated_at, inserted_at
```

---

## 4. CTE STRUCTURE

### Every model follows the 4-step CTE pattern:

```
STEP 1: {{ config() }}           — Materialization, keys, dist/sort
STEP 2: Import CTEs              — select * from ref/source
STEP 3: Logic CTEs               — One per transformation unit
STEP 4: Final CTE + SELECT       — Column selection, then select * from final
```

### CTE Naming Conventions

| CTE Type    | Naming Pattern           | Example                     |
|-------------|-------------------------|-----------------------------|
| Import      | `import_{model_name}`    | `import_accounts`           |
| Logic       | `{descriptive_action}`   | `user_crunch_counts`        |
| Filter      | `filtered_{entity}`      | `filtered_active_users`     |
| Dedupe      | `deduped_{entity}`       | `deduped_events`            |
| Pivot       | `pivoted_{entity}`       | `pivoted_metrics`           |
| Final       | `final`                  | `final`                     |

---

## 5. JINJA AND MACROS

- Always use `{{ ref('model_name') }}` — never hardcode table names
- Always use `{{ source('source_name', 'table_name') }}` for raw sources
- Use `{% set %}` to declare variables at the top of macros
- Parameterize macros — never hardcode column/table names inside them
- Use `{{ target.name }}` for environment-aware logic

---

## 6. YAML FORMATTING

- 2-space indentation in all YAML files
- Descriptions mandatory for every model and every column
- Use `>` for multi-line descriptions:
  ```yaml
  description: >
    This model contains one row per account.
    It joins staging accounts with organization dimensions.
  ```

---

## 7. SQLFLUFF CONFIGURATION

```ini
[sqlfluff]
dialect = ansi   # Change to: redshift, snowflake, postgres
templater = dbt
max_line_length = 120
indent_unit = space

[sqlfluff:indentation]
tab_space_size = 4

[sqlfluff:rules:capitalisation.keywords]
capitalisation_policy = lower

[sqlfluff:rules:capitalisation.identifiers]
capitalisation_policy = lower

[sqlfluff:rules:capitalisation.functions]
capitalisation_policy = lower

[sqlfluff:rules:layout.long_lines]
max_line_length = 120
```

---

## 8. GIT COMMIT CONVENTIONS

```
feat: add new dim_account model
fix: correct join logic in fct_crunches
refactor: extract date math into macro
docs: add column descriptions to stg_{{source}}
test: add relationship test for fct_crunches → dim_account
```

---

## CUSTOM RULES

- Trailing commas are mandatory on all column lists, including the last column.
- All warehouse COPY/LOAD commands should use appropriate timestamp format options.
- Cast IDs to `::text` in all joins to avoid silent varchar/text mismatches.
- Use appropriate JSON column type for your warehouse: SUPER (Redshift), VARIANT (Snowflake), JSONB (Postgres).
