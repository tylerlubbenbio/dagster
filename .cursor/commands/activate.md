# Activate Project for a Specific Database

## Arguments
$ARGUMENTS

## Instructions
Initialize this Dagster+dbt project template for a specific data warehouse.

### Step 1: Validate
User specified: $ARGUMENTS. Must be postgres, snowflake, or redshift.

### Step 2: Read _RESOURCES/$ARGUMENTS.md

### Step 3: Scan _RESOURCES/ for user files

### Step 4: Ask questions before changes
1. Project name? 2. Owner email? 3. Host? 4. DB name?
5. Port? 6. Username? 7. Slack channel? 8. Cloud staging?
9. Bucket/region? 10. Data sources?
Plus DB-specific questions from _RESOURCES.

### Step 5: Update files
.env, config.json, load_config.py, CLAUDE.md, profiles.yml,
dbt_project.yml, requirements.txt, resources.py, io_managers.py,
asset_factory.py, Makefile, ci.yml, ARCHITECTURE.md, RULES.md

### Step 6: Create source pipelines if provided
### Step 7: Create watermark DDL
### Step 8: Verify (config + dbt parse)
### Step 9: Print summary