{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is not none -%}
        {%- if target.name == 'prod' -%}
            {{ custom_schema_name | trim }}
        {%- else -%}
            {{ custom_schema_name | trim }}_dev
        {%- endif -%}
    {%- else -%}
        {{ target.schema }}
    {%- endif -%}
{%- endmacro %}
