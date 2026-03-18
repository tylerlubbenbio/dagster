{# =============================================================================
   _docs.md — Long-form documentation (Docs Blocks)
   =============================================================================
   RULES:
     - Use for any description longer than 2-3 sentences
     - Link to _schema.yml using: description: '{{ doc("{block_name}") }}'
     - dbt preserves all Markdown formatting (bullets, bold, headers)
     - One _docs.md per subdirectory
   ============================================================================= #}


{% docs stg_{{source}}__{{table}} %}

## Overview

This staging model cleans and types raw data from `raw_{{source}}.{{table}}`.

**Grain:** One row per {{entity}}

## Transformations Applied

- **Surrogate Key:** MD5 hash generated from `{{entity}}_id`
- **Type Casting:** All IDs cast to `text`, timestamps cast to `timestamp`
- **Cleaning:** Names lowercased and trimmed
- **Filtering:** Test rows and null IDs removed

## Source

Raw table: `raw_{{source}}.{{table}}`

## Dependencies

None (staging models have no joins)

{% enddocs %}


{# --- Add more docs blocks below as needed --- #}

{# {% docs dim_account %}

## Overview

Dimension table for accounts. Contains current-state attributes.

**Grain:** One row per account
**SCD Type:** Type 1 (daily overwrite)

## Business Logic

- Accounts joined with Salesforce data for enrichment
- Account status derived from subscription and usage signals

## Usage

Join to fact tables using `account_sk`:
```sql
left join dim_account on fct.account_sk = dim_account.account_sk
```

{% enddocs %} #}
