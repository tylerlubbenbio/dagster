# Testing Guide

## Overview

This project uses **pytest** for automated testing with a focus on both unit tests (fast, mocked) and integration tests (real database connections).

---

## Quick Start

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run unit tests only (fast, no DB required)
pytest -m unit

# Run integration tests (requires warehouse .env config)
pytest -m integration

# Run with coverage
pytest --cov=dagster --cov-report=html
open htmlcov/index.html
```

---

## Test Organization

### Directory Structure

```
{{PROJECT_NAME}}/
├── pytest.ini                  # pytest configuration
├── conftest.py                 # Root fixtures (config, warehouse connection)
├── tests/                      # Root-level unit tests
│   ├── conftest.py
│   ├── test_config.py          # Config loading tests
│   └── test_transforms.py      # Field transform tests
├── dagster/
│   ├── conftest.py             # Dagster fixtures
│   ├── tests/                  # Dagster asset/job tests
│   │   ├── conftest.py
│   │   ├── test_assets.py
│   │   └── test_asset_factory.py
│   └── ingestion/raw/
│       └── api_*/              # Per-source directories
│           ├── tests/          # Source-specific tests
│           │   ├── conftest.py
│           │   ├── test_pipeline.py
│           │   └── test_integration.py
│           └── admin/          # Manual validation scripts (NOT pytest)
└── _TESTING/                   # Manual diagnostic scripts
```

### Test Categories

**Unit Tests (`@pytest.mark.unit`):**
- No external dependencies (databases, APIs)
- Use mocks for warehouse, S3, APIs
- Fast execution (<1s per test)
- Run in CI on every PR

**Integration Tests (`@pytest.mark.integration`):**
- Require real warehouse connection
- Use test schemas/tables
- Slower execution (5-30s per test)
- Run locally before major merges
- NOT run in CI (avoid credential complexity)

**Manual Scripts (`_TESTING/`):**
- One-off diagnostic and validation scripts
- Run manually for debugging
- NOT part of automated CI/CD

---

## Writing Tests

### Unit Test Example

```python
import pytest

@pytest.mark.unit
def test_field_transform():
    """Test field transformation logic without DB."""
    from dagster.field_transforms import clean_email

    assert clean_email("  USER@EXAMPLE.COM  ") == "user@example.com"
    assert clean_email(None) is None
```

### Integration Test Example

```python
import pytest

@pytest.mark.integration
def test_source_extraction(config, warehouse_cursor):
    """Test source extraction."""
    from dagster.ingestion.raw.api_example.extractors import extract_records

    # Extract small batch
    records = extract_records(config, limit=5)

    # Verify data
    assert len(records) > 0
    assert all('id' in r for r in records)

    # Insert into test table
    # (use test schema to avoid polluting production)
    warehouse_cursor.execute("CREATE SCHEMA IF NOT EXISTS test_raw_example")
    # ... insert and verify
```

---

## Fixtures

### Root Fixtures (`conftest.py`)

**`config`** - Loads `config.json` + `.env`:
```python
def test_something(config):
    warehouse_host = config['target']['host']
```

**`warehouse_connection`** - Session-scoped warehouse connection:
```python
def test_with_db(warehouse_connection):
    cursor = warehouse_connection.cursor()
    cursor.execute("SELECT 1")
```

**`warehouse_cursor`** - Function-scoped cursor with auto-commit:
```python
def test_insert(warehouse_cursor):
    warehouse_cursor.execute("INSERT INTO ...")
    # Auto-commits on teardown
```

### Dagster Fixtures (`dagster/conftest.py`)

**`mock_asset_context`** - Mock Dagster asset context:
```python
def test_asset(mock_asset_context):
    from dagster import build_asset_context
    # Use for unit testing assets without materializing
```

---

## Running Tests

### Local Execution

```bash
# All tests (requires .env with warehouse creds)
pytest -v

# Unit tests only (no DB needed)
pytest -m unit -v

# Integration tests only
pytest -m integration -v

# Specific file
pytest tests/test_config.py -v

# Specific test
pytest tests/test_config.py::test_config_structure -v

# With coverage
pytest --cov=dagster --cov-report=term-missing

# Stop on first failure
pytest -x
```

### CI/CD Execution

**GitHub Actions automatically runs:**
- Unit tests on every PR/push to main
- NO integration tests (avoids needing secrets)
- Coverage reports generated

**See:** `.github/workflows/ci.yml` → `test` job

---

## Best Practices

### 1. Mark Tests Appropriately

```python
@pytest.mark.unit        # Fast, mocked
@pytest.mark.integration # Requires DB
@pytest.mark.slow        # >5 seconds
```

### 2. Use Small Data Samples

```python
# Good: Small batch for testing
records = extract_records(limit=5)

# Bad: Full extraction in tests
records = extract_records()  # Could be 10k+ records
```

### 3. Clean Up Test Data

```python
@pytest.fixture
def test_table(warehouse_cursor):
    """Create and clean up test table."""
    warehouse_cursor.execute("CREATE TABLE test_schema.test_table (...)")
    yield
    warehouse_cursor.execute("DROP TABLE test_schema.test_table")
```

### 4. Use Test Schemas

```python
# Good: Isolate from production
CREATE SCHEMA IF NOT EXISTS test_raw_example

# Bad: Pollute production schema
CREATE TABLE raw_example.records ...
```

### 5. Test Edge Cases

```python
def test_null_handling():
    assert transform_field(None) is None

def test_empty_string():
    assert transform_field("") == ""

def test_special_characters():
    assert transform_field("user@special.com") == "user@special.com"
```

---

## Troubleshooting

### Tests Can't Find Modules

**Problem:** `ModuleNotFoundError: No module named 'dagster'`

**Solution:** Ensure pytest runs from project root:
```bash
cd /path/to/{{PROJECT_NAME}}
pytest
```

### Integration Tests Fail with Connection Error

**Problem:** `psycopg2.OperationalError: could not connect to server`

**Solution:** Verify `.env` has warehouse credentials:
```bash
cat .env | grep -i warehouse
```

### Fixtures Not Found

**Problem:** `fixture 'config' not found`

**Solution:** Ensure `conftest.py` exists in root or parent directory. Pytest auto-discovers fixtures.

### Coverage Too Low

**Problem:** `FAILED: coverage is 45%, required 80%`

**Solution:** Add tests for uncovered modules:
```bash
pytest --cov=dagster --cov-report=term-missing
# Shows which lines are missing coverage
```

---

## Converting Manual Scripts to pytest

### Before (Manual Script in `_TESTING/`)

```python
# _TESTING/test_example_manual.py
if __name__ == "__main__":
    config = load_config()
    conn = connect(...)

    print("Testing extraction...")
    records = extract_records(config, limit=5)
    print(f"Extracted {len(records)} records")
```

### After (pytest in `dagster/ingestion/raw/api_example/tests/`)

```python
# dagster/ingestion/raw/api_example/tests/test_pipeline.py
import pytest

@pytest.mark.integration
def test_extraction(config, warehouse_cursor):
    """Test source record extraction."""
    records = extract_records(config, limit=5)
    assert len(records) > 0, "Should extract at least 1 record"

@pytest.mark.integration
def test_insertion(config, warehouse_cursor):
    """Test record insertion to warehouse."""
    records = extract_records(config, limit=5)
    insert_records(warehouse_cursor, records)

    warehouse_cursor.execute("SELECT COUNT(*) FROM test_raw_example.records")
    count = warehouse_cursor.fetchone()[0]
    assert count >= 5
```

**Key Differences:**
- Use fixtures instead of `load_config()`
- Use assertions instead of print statements
- Mark with appropriate decorator
- Can run with `pytest` command

---

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [Dagster Testing Guide](https://docs.dagster.io/guides/test)
- [pytest Fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html)
- Project-specific: `AGENT_KNOWLEDGE/RULES.md`, `AGENT_KNOWLEDGE/ARCHITECTURE.md`
