-- =============================================================================
-- Macro: clean_string
-- Purpose: Standardize text columns — lowercase, trimmed
-- Usage: {{ clean_string('column_name') }}
-- =============================================================================
{% macro clean_string(column_name) %}
    lower(trim({{ column_name }}))
{% endmacro %}


-- =============================================================================
-- Macro: safe_cast_id
-- Purpose: Cast any ID column to text for safe joins (prevents Redshift
--          varchar vs text silent join failures)
-- Usage: {{ safe_cast_id('account_id') }}
-- =============================================================================
{% macro safe_cast_id(column_name) %}
    cast({{ column_name }} as text)
{% endmacro %}


-- =============================================================================
-- Macro: limit_dev_data
-- Purpose: Filter to recent data in dev for fast iteration
-- Usage: Add to WHERE clause: {{ limit_dev_data('created_at') }}
-- =============================================================================
{% macro limit_dev_data(date_column) %}
    {% if target.name == 'dev' %}
        {{ date_column }} >= current_date - interval '{{ var("dev_data_days", 30) }} days'
    {% else %}
        1 = 1
    {% endif %}
{% endmacro %}


-- =============================================================================
-- Macro: generate_md5_sk
-- Purpose: Wrapper around dbt_utils surrogate key for consistency
-- Usage: {{ generate_md5_sk(['col1', 'col2']) }} as table_sk
-- =============================================================================
{% macro generate_md5_sk(columns) %}
    {{ dbt_utils.generate_surrogate_key(columns) }}
{% endmacro %}
