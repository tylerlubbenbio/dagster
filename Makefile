# Data Platform - Makefile
# ========================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Project settings (Python 3.11)
PROJECT_NAME := dagster-user-code
IMAGE_TAG ?= latest
VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DAGSTER := $(VENV)/bin/dagster

# AWS/ECR settings (override via environment or command line)
AWS_PROFILE ?= prod
AWS_REGION ?= us-east-1
AWS_ACCOUNT_ID ?= $(shell aws sts get-caller-identity --profile $(AWS_PROFILE) --query Account --output text 2>/dev/null)
ECR_REGISTRY ?= $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com
IMAGE_NAME := $(ECR_REGISTRY)/$(PROJECT_NAME)

# Kubernetes settings
KUBE_CONTEXT ?= prod
NAMESPACE ?= dagster
RELEASE_NAME ?= dagster

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
# Docker
# ============================================================================

.PHONY: docker-build
docker-build: ## Build Docker image locally (for amd64/linux)
	docker build --platform linux/amd64 -t $(PROJECT_NAME):$(IMAGE_TAG) .
	@echo "Built: $(PROJECT_NAME):$(IMAGE_TAG)"

.PHONY: docker-run
docker-run: ## Run Docker container locally (for testing)
	docker run --rm -p 3030:3030 $(PROJECT_NAME):$(IMAGE_TAG)

.PHONY: docker-shell
docker-shell: ## Open shell in Docker container
	docker run --rm -it $(PROJECT_NAME):$(IMAGE_TAG) /bin/bash

# ============================================================================
# ECR (AWS Container Registry)
# ============================================================================

.PHONY: ecr-login
ecr-login: ## Authenticate Docker with AWS ECR
	aws ecr get-login-password --region $(AWS_REGION) --profile $(AWS_PROFILE) | \
		docker login --username AWS --password-stdin $(ECR_REGISTRY)

.PHONY: ecr-create
ecr-create: ## Create ECR repository (if it doesn't exist)
	aws ecr create-repository \
		--repository-name $(PROJECT_NAME) \
		--region $(AWS_REGION) \
		--profile $(AWS_PROFILE) \
		--image-scanning-configuration scanOnPush=true \
		--encryption-configuration encryptionType=AES256 \
	|| echo "Repository may already exist"

.PHONY: ecr-push
ecr-push: ecr-login docker-build ## Build and push image to ECR
	docker tag $(PROJECT_NAME):$(IMAGE_TAG) $(IMAGE_NAME):$(IMAGE_TAG)
	docker push $(IMAGE_NAME):$(IMAGE_TAG)
	@echo "Pushed: $(IMAGE_NAME):$(IMAGE_TAG)"

.PHONY: ecr-list
ecr-list: ## List images in ECR repository
	aws ecr describe-images \
		--repository-name $(PROJECT_NAME) \
		--region $(AWS_REGION) \
		--profile $(AWS_PROFILE) \
		--query 'imageDetails[*].{Tag:imageTags[0],Pushed:imagePushedAt,Size:imageSizeInBytes}' \
		--output table

# ============================================================================
# Kubernetes / Helm Deployment
# ============================================================================

.PHONY: helm-add
helm-add: ## Add Dagster Helm repository
	helm repo add dagster https://dagster-io.github.io/helm
	helm repo update

.PHONY: deploy
deploy: ## Deploy Dagster to Kubernetes using Helm
	./dagster/deployment/deploy.sh $(NAMESPACE) $(RELEASE_NAME)

.PHONY: deploy-dry-run
deploy-dry-run: ## Dry-run Helm deployment (shows what would be deployed)
	helm upgrade --install $(RELEASE_NAME) dagster/dagster \
		-f dagster/deployment/values.yaml \
		--namespace $(NAMESPACE) \
		--kube-context $(KUBE_CONTEXT) \
		--dry-run

.PHONY: undeploy
undeploy: ## Uninstall Dagster from Kubernetes
	helm uninstall $(RELEASE_NAME) --namespace $(NAMESPACE) --kube-context $(KUBE_CONTEXT)

.PHONY: status
status: ## Check deployment status
	@echo "=== Pods ==="
	kubectl --context $(KUBE_CONTEXT) get pods -n $(NAMESPACE)
	@echo ""
	@echo "=== Services ==="
	kubectl --context $(KUBE_CONTEXT) get svc -n $(NAMESPACE)

.PHONY: logs
logs: ## View Dagster daemon logs
	kubectl --context $(KUBE_CONTEXT) logs -l component=dagster-daemon -n $(NAMESPACE) -f

.PHONY: logs-web
logs-web: ## View Dagster webserver logs
	kubectl --context $(KUBE_CONTEXT) logs -l component=dagster-webserver -n $(NAMESPACE) -f

.PHONY: logs-user
logs-user: ## View user code deployment logs
	kubectl --context $(KUBE_CONTEXT) logs -l component=dagster-user-deployments -n $(NAMESPACE) -f

.PHONY: port-forward
port-forward: ## Port-forward Dagster UI to localhost:8080
	@echo "Opening Dagster UI at http://localhost:8080"
	kubectl --context $(KUBE_CONTEXT) port-forward svc/$(RELEASE_NAME)-webserver 8080:80 -n $(NAMESPACE)

# ============================================================================
# Utilities
# ============================================================================

.PHONY: clean
clean: ## Clean up local artifacts (including orphaned .tmp_dagster_home_* dirs)
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".tmp_dagster_home_*" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
