# Sequential Scripts Standard

<!--
=============================================================================
WHEN TO USE THIS PATTERN
=============================================================================
Use numbered sequential scripts when:
• Multiple distinct operations must run in order
• Each step produces output for the next step
• Steps can be tested/debugged independently
• Process needs to be resumable from any point

Don't use when:
• Single monolithic script is clearer
• No natural execution order exists
• Steps aren't truly independent
=============================================================================
-->

## Extreme Modularity Requirements

**All code must be highly modular and template-ready:**
- Break large scripts into small, manageable, single-purpose scripts
- Design code as if creating a template for other clients to reuse
- Each script should do ONE thing well
- Functions and logic should be easily transferable and adaptable
- Avoid monolithic scripts that combine multiple responsibilities

## Script Naming Convention

**Use numbered prefixes with spelled-out numbers to indicate execution order:**

**Setup/Initialization Scripts:**
- `zero_setup_database.py` - Database table creation and initial setup
- `zero_config_environment.py` - Environment configuration
- `zero_initialize_connections.py` - Connection initialization

**Sequential Processing Scripts:**
- `one_pull_data.py` - First step: data retrieval
- `two_transform_data.py` - Second step: data transformation
- `three_load_database.py` - Third step: database loading
- `four_generate_reports.py` - Fourth step: report generation

**Examples:**
```
zero_create_tables.sql
one_fetch_api_data.py
two_clean_data.py
three_analyze_metrics.py
four_export_results.py
five_send_notifications.py
```

## Script Header Documentation

**Every script must have a header with project information:**
- Project name
- Author
- Date
- Purpose
- Dependencies
- Usage instructions

**Template:**
```python
"""
Project: [Project Name]
Author: [Your Name]
Date: [YYYY-MM-DD]
Purpose: [One sentence - what this script does]
Dependencies: [What must run before this / required packages]
Usage: python [script_name].py [args if any]
"""
```

## Script Execution Order

**The scripts should be executed in the following order:**

1. `zero_setup_database.py` - Initialize database and create tables
2. `zero_config_environment.py` - Configure environment variables and settings
3. `zero_initialize_connections.py` - Establish database and API connections
4. `one_pull_data.py` - Retrieve data from sources
5. `two_transform_data.py` - Process and transform data
6. `three_load_database.py` - Store data in database
7. `four_generate_reports.py` - Create reports and analytics
8. `five_send_notifications.py` - Send notifications and alerts

**This order ensures that all dependencies are properly set up before any data processing occurs.**

## Code Standards

**All code must follow these standards:**

1. Use consistent indentation (4 spaces)
2. Follow PEP8 guidelines
3. Include comments for complex logic
4. Use descriptive variable names
5. Include error handling and logging
6. Include documentation for all public functions and classes

## Documentation Requirements

**All documentation should be:**
- Written in clear, concise language
- Well-documented to ensure code can be understood and maintained by others
- Stored in `AGENT_KNOWLEDGE/docs/` only

**Document when:**
- Execution order is non-obvious
- Dependencies between scripts are complex
- Configuration/setup is non-standard
- Future reference will be needed