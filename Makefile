# Data Platform - Makefile
# ========================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Project settings (Python 3.11)
PROJECT_NAME := bio-dagster-dbt
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DAGSTER := $(VENV)/bin/dagster

# ============================================================================
# Help
# ============================================================================

.PHONY: help
help: ## Show this help message
	@echo "Data Platform Commands"
	@echo "========================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# Local Development
# ============================================================================

.PHONY: venv
venv: ## Create .venv with Python 3.11 (run once: make venv && make install)
	@command -v python3.11 >/dev/null 2>&1 || { echo "Install Python 3.11: brew install python@3.11"; exit 1; }
	python3.11 -m venv $(VENV)
	@echo "Created $(VENV). Run: make install"

.PHONY: install
install: ## Install Python dependencies into .venv (uses $(PYTHON))
	$(PYTHON) -m pip install --upgrade pip
	$(PIP) install -r requirements.txt

DAGSTER_HOME ?= $(shell pwd)/.dagster_home

.PHONY: dev
dev: ## Run Dagster in DEV mode (30-day data window, _dev schemas, schedules OFF)
	DAGSTER_HOME=$(shell pwd)/.dagster_home DAGSTER_ENV=dev DBT_TARGET=dev \
		$(DAGSTER) dev -f dagster/definitions.py > _LOGS/dagster.log 2>&1 &
	@echo "Dagster [dev] started — UI: http://localhost:3000  |  tail -f _LOGS/dagster.log"

.PHONY: integration
integration: ## Run Dagster in INTEGRATION mode (full data, _dev schemas, schedules OFF)
	DAGSTER_HOME=$(shell pwd)/.dagster_home DAGSTER_ENV=integration DBT_TARGET=integration \
		$(DAGSTER) dev -f dagster/definitions.py > _LOGS/dagster.log 2>&1 &
	@echo "Dagster [integration] started — UI: http://localhost:3000  |  tail -f _LOGS/dagster.log"

.PHONY: kill
kill: ## Kill all local Dagster processes
	pkill -9 -f "dagster dev" || true
	@echo "All Dagster processes stopped."

.PHONY: check
check: ## Validate Dagster definitions load correctly
	$(DAGSTER) definitions validate -f dagster/definitions.py

.PHONY: lint
lint: ## Run linting (requires ruff in .venv)
	@$(PYTHON) -c "import ruff" 2>/dev/null || { echo "Run: make install"; exit 1; }
	$(VENV)/bin/ruff check .

.PHONY: format
format: ## Format code (requires ruff in .venv)
	@$(PYTHON) -c "import ruff" 2>/dev/null || { echo "Run: make install"; exit 1; }
	$(VENV)/bin/ruff format .

# ============================================================================
# Utilities
# ============================================================================

.PHONY: clean
clean: ## Clean up local artifacts (including orphaned .tmp_dagster_home_* dirs)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".tmp_dagster_home_*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
