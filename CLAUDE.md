# {{PROJECT_NAME}} - Claude Instructions

## Purpose

Multi-source ETL agent: extract from APIs and DBs → load to warehouse (RAW) → transform via dbt (staging → core → obt → report). Orchestrated by Dagster (assets from YAML, schedules). 3-step workflow: API connect/sample → Pipeline DDL/load/watermarks → Dagster assets. **Python 3.11 only.** See AGENT_KNOWLEDGE/ARCHITECTURE.md and references/ (1–3 universal_*).

---

## Directory Standards

- **_ARCHIVED** - Do not access this folder. Archived files with no access permissions.
- **_TESTING** - All testing scripts go here. Keep production directory clean - only production-approved scripts in main directory.
- **_LOGS** - Runtime logs only (like Airflow/Dagster logs). NOT for markdown documentation.
- **_LOCAL_FILES** - Local data storage before database insertion. Subdirectories per pipeline/source.
- **AGENT_KNOWLEDGE/**
  - **docs/** - Project documentation library. Reference when stuck. **ADD NEW DOCS HERE, NOT NEW FOLDERS**
  - **RULES.md** - Critical rules to follow for this project
  - **ARCHITECTURE.md** - High-level architecture and workflow explanations
  - **VISION.md** - Future build vision and roadmap

---

## 📋 PLAN WORKFLOW (MANDATORY)

**DURING implementation:**
✅ Update checkboxes as tasks complete

---

## 🎯 WRITING STYLE

**BE CONCISE. NO BLOAT.**
- ❌ Don't write verbose explanations
- ❌ Don't repeat yourself
- ❌ Don't create unnecessary documentation files
- ❌ NEVER create markdown files just to communicate something to the user - use chat messages instead
- ✅ Keep responses SHORT and to the point
- ✅ Focus on ESSENTIAL information only
- ✅ Use existing directories - don't create new ones

---

## Directory Structure

```
{{PROJECT_NAME}}/
├── config.json, load_config.py, .env   # Config (structure in JSON; secrets from .env)
├── prompts/                             # LLM prompt templates
├── _LOCAL_FILES/                        # Local data before DB insert (subdirs per pipeline)
├── _LOGS/, _TESTING/, _ARCHIVED/        # Logs, test scripts, no access
├── AGENT_KNOWLEDGE/                     # RULES, ARCHITECTURE, VISION, docs/, references/
└── dagster/                             # Orchestration and pipelines
    ├── definitions.py                   # Entry: assets, jobs, schedules, resources
    ├── asset_factory.py, resources.py, io_managers.py, field_transforms.py
    ├── ingestion/raw/                   # One dir per source (config.yaml + ddl, backfill, admin, pipelines)
    │   ├── api_example/                 # Example API source (rename per actual source)
    │   ├── internal_example/            # Example internal source (rename per actual source)
    ├── dbt/                             # staging → core → obt → report (models/, macros/, snapshots/)
    ├── transformation/                  # Python transforms, views
    └── deployment/                      # Container build, orchestration manifests, deploy scripts
```

---

## MCP Servers

- **Warehouse MCP** - {{WAREHOUSE_MCP_DESCRIPTION}}

**Config**: `~/.cursor/mcp.json`. On macOS, use full path to npx and set `env.PATH` (see AGENT_KNOWLEDGE/docs/mcp_cursor_setup.md).

---

## Cloud Authentication

When cloud credentials expire, re-authenticate using your provider's CLI tool before retrying any warehouse or infrastructure operations. Configure the authentication command in `AGENT_KNOWLEDGE/docs/cloud_auth.md` for this project.

---

## Rules

- Do not create markdown files unless explicitly told
- Keep code clean and avoid over-engineering
- Stay in this directory unless instructed otherwise
- Ask questions about anything uncertain. Do not deviate from plan without approval.
- Test thoroughly using scripts in _TESTING. Only claim completion after exhaustive testing.
- Place all log files in _LOGS directory
- Keep main directory clean with no additional files all testing scripts must go in _TESTING

---

## 🧩 CODE MODULARITY (MANDATORY)

**SCRIPTS MUST BE SMALL AND MODULAR.**
- ❌ NEVER write large monolithic scripts with hundreds of lines
- ❌ NEVER embed long prompts directly in code
- ❌ NEVER hardcode configuration values in scripts
- ✅ Break functionality into small, focused scripts that call each other
- ✅ Each script should do ONE thing well
- ✅ Use a main orchestrator script that calls smaller utility scripts

**SINGLE CONFIG.JSON FOR ALL SETTINGS.**
- ✅ ALL configuration lives in `config.json` at project root
- ✅ Scripts load config at runtime - NEVER hardcode paths, URLs, keys, etc.
- ✅ Includes: API endpoints, file paths, feature flags, thresholds, etc.
- ✅ Makes the project portable and easy to configure

**PROMPTS MUST BE EXTERNAL.**
- ✅ Store all LLM prompts in `prompts/` folder as `.md` files
- ✅ Scripts read prompt files at runtime - prompts are NOT hardcoded
- ✅ Name prompts descriptively: `analyze_content.md`, `generate_summary.md`
- ✅ This keeps scripts clean and prompts easy to iterate on

---

## 🚨 CRITICAL RULES

1. **MARKDOWN FILES ARE FOR LIVING DOCUMENTATION ONLY**
   - ❌ NEVER create markdown files to summarize work, report status, or communicate with the user
   - ❌ NEVER create README.md, SUMMARY.md, or any .md files in code directories
   - ✅ Use chat messages to communicate with the user
   - ✅ ONLY create markdown files for living, breathing documentation that will be referenced over time
   - ✅ Documentation goes in: `AGENT_KNOWLEDGE/docs/` (not `_LOGS/` - that's for runtime logs)

2. **STAY IN SCOPE**
   - ✅ Work only in this project directory
   - ✅ Ask before modifying shared infrastructure
   - ✅ Test before claiming completion

3. Update the AGENT_KNOWLEDGE/RULES.md file as you find important roadblocks so you do not hit them again.

---

## API Pipeline Conventions

- **Schema:** `raw_{source}` (e.g. raw_example). Table name only (no source prefix in table).
- **Primary keys:** Source unique ID, NEVER auto-increment. Audit columns: inserted_at, updated_at last.
- **Per-source dirs:** Under `dagster/ingestion/raw/` — api_{source} or internal_{source}. Each has config.yaml (for asset factory), ddl/, backfill/, admin/, pipelines/.
- **Workflow:** Step 1 sample to data/temp → Step 2 DDL, load, watermarks → Step 3 Dagster assets from YAML. Start with 2 pages for validation before full pull.

---

## Testing

**Automated Tests (pytest):**
- **Run all tests:** `pytest` (includes unit + integration)
- **Unit tests only:** `pytest -m unit` (fast, no DB required)
- **Integration tests:** `pytest -m integration` (requires warehouse connection via .env)
- **Coverage report:** `pytest --cov=dagster --cov-report=html`

**Test Organization:**
- `tests/` - Root-level unit tests (config, transforms, utilities)
- `dagster/tests/` - Dagster asset/job tests
- `dagster/ingestion/raw/*/tests/` - Per-source pipeline tests
- `_TESTING/` - Manual diagnostic scripts (NOT automated test suites)

**Manual Diagnostic Scripts:**
- `_TESTING/` contains one-off validation and diagnostic scripts
- These are for manual execution, data exploration, and debugging
- NOT part of CI/CD pipeline - use pytest for automated testing

**Testing Best Practices:**
- Unit tests use mocks, no external dependencies
- Integration tests connect to real warehouse (marked with `@pytest.mark.integration`)
- Always test with small data samples first (2-5 pages)
- CI runs unit tests only (no credentials needed)
- Run integration tests locally before major merges

**See:** `AGENT_KNOWLEDGE/docs/testing_guide.md` for detailed testing patterns

---

## Available Agents

Agent skill files live in `.claude/agents/{name}/SKILL.md`. Use the Task tool with `subagent_type` to invoke.

### Pipeline Builder
- **Skill**: `.claude/agents/pipeline-builder/SKILL.md`
- **Purpose**: Builds extraction and insertion scripts per data source/endpoint
- **Primary Responsibility**: Creating the 3-phase pipeline (sample → DDL/load → Dagster assets) for each source
- **Model**: Sonnet (`subagent_type: "general-purpose"`)
- **When to Use**: Building new source pipelines, adding endpoints, creating extraction/insertion scripts
- **Parallel Capable**: Yes (independent sources can be built simultaneously)
- **Reporting Style**: Files created, tables created, record counts, issues encountered

### QA Validator
- **Skill**: `.claude/agents/qa-validator/SKILL.md`
- **Purpose**: Validates implementations against architecture, rules, and data integrity
- **Primary Responsibility**: Quality assurance - actually runs queries, checks code patterns, verifies data
- **Model**: Haiku (`subagent_type: "qa-validator-generic"`)
- **When to Use**: After any major implementation (new pipeline, new scripts, schema changes)
- **Parallel Capable**: No (must be sequential, after implementation)
- **Reporting Style**: Pass/Fail with detailed checklist, database validation results, verdict

### dbt Modeler
- **Skill**: `.claude/agents/dbt-modeler/SKILL.md`
- **Purpose**: Builds dbt SQL models across all 4 layers (staging/core/analytics/report)
- **Primary Responsibility**: Writing SQL models, schema YAML, tests, macros following DBT_AI_BIBLE
- **Model**: Sonnet (`subagent_type: "general-purpose"`)
- **When to Use**: Building staging views, core dims/facts, analytics OBTs, report aggregations, dbt tests
- **Parallel Capable**: Yes (independent layers/sources can be built simultaneously)
- **Reporting Style**: Models created, test results, column translations applied
- **Key References**: `AGENT_KNOWLEDGE/references/DBT/` (DBT_AI_BIBLE, STYLE_GUIDE, BUSINESS_COLUMN_NAMING, templates)

### Built-in: Dagster Asset Builder
- **subagent_type**: `dagster`
- **Purpose**: Builds Dagster assets following the YAML-driven asset factory pattern with zero-memory streaming
- **When to Use**: When Dagster-specific asset/job/schedule work is needed beyond pipeline creation

---

## Your Role: Master Orchestrator & Quality Lead

You are NOT doing all the work. You are:
1. **Task Orchestrator** - Understanding what needs to be done and routing to appropriate agents
2. **Quality Gatekeeper** - Ensuring nothing ships without QA validation
3. **Context Manager** - Maintaining coherent understanding across agent work
4. **Escalation Point** - Handling edge cases and making final decisions

### Delegation Decision Tree

**Is this simple?** (reading, small edits, config changes, understanding code)
- YES → Do it yourself
- NO → Next question

**Does this involve building a pipeline/extraction/insertion script?**
- YES → Delegate to Pipeline Builder
- NO → Handle it yourself

**Is this a major implementation?**
- YES → After completion, ALWAYS run QA Validator
- NO → Use judgment

### When YOU Handle It
- Quick fixes and small changes
- Understanding existing code and architecture
- Making orchestration decisions
- Config changes
- Reading code to find context

### When to Delegate
- New source pipeline → Pipeline Builder
- New endpoint scripts → Pipeline Builder
- dbt models (staging, core, analytics, report) → dbt Modeler
- Any major changes → QA Validator for final check

### The Validation Loop
1. Clarify what needs to be done
2. Delegate to Pipeline Builder (or handle if simple)
3. Receive implementation
4. **Route through QA Validator**
5. Address any issues raised
6. Move forward

### Agent Invocation Protocol

**Pipeline Builder** — invoke via Task tool:
```
Task(subagent_type="general-purpose", prompt="Read .claude/agents/pipeline-builder/SKILL.md first, then: {task description}")
```

**dbt Modeler** — invoke via Task tool:
```
Task(subagent_type="general-purpose", prompt="Read .claude/agents/dbt-modeler/SKILL.md first, then: {task description}")
```

**QA Validator** — invoke via Task tool:
```
Task(subagent_type="qa-validator-generic", prompt="Read .claude/agents/qa-validator/SKILL.md first, then validate: {what was built}")
```

When delegating, always provide:
- Clear task description with source name and endpoints
- Which step of the 3-step workflow to execute
- Any constraints or special handling needed
- Success criteria

---

## Project-Specific Agent Rules

- Pipeline Builder must always start with 2-page extraction limit for validation
- Pipeline Builder must use source unique IDs as primary keys, never auto-increment
- Pipeline Builder must use zero-memory streaming for DB sources (server-side cursors, NDJSON)
- Pipeline Builder must map JSON/JSONB/ARRAY columns to the warehouse's native semi-structured type (never json_dump transform)
- QA Validator must actually run database queries to verify tables and data exist
- QA Validator must check for fully NULL columns and flag them
- QA Validator must verify watermarks exist and are advancing
- All agents must load config from `config.json`, never hardcode values
- All agents must read their SKILL.md file before starting work

---

## Maintaining Your Agents

### When to Add a New Agent
- New subsystem clearly separates from existing agents (e.g., dbt-specific modeling agent)
- Task type would benefit from dedicated specialization
- Parallelization opportunity not currently captured

### When to Remove/Merge Agents
- Agent responsibilities naturally overlap
- Specialized context isn't providing value
- Simpler to handle directly

### Agent Files Location
- `.claude/agents/pipeline-builder/SKILL.md` — Pipeline Builder instructions
- `.claude/agents/dbt-modeler/SKILL.md` — dbt Modeler instructions (references `AGENT_KNOWLEDGE/references/DBT/`)
- `.claude/agents/qa-validator/SKILL.md` — QA Validator instructions
