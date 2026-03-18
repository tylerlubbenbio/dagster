# Deployment & GitHub Workflow

Reference for how the repo is set up, how CI works, and how to deploy to live Dagster.

---

## Repo: {{YOUR_ORG}}/{{PROJECT_NAME}}

- **Main branch:** `main` — production source of truth
- **Feature branches:** cut from main, PR back to main
- **Convention:** `feature/your-name` or `feat/description`
- **PR title format:** `feat: Capital letter description` (enforced by CI)

---

## GitHub Actions (CI)

Two workflows run on every PR to main:

### `ci.yml` — runs on PR + push to main/feature/**
| Job | What it does |
|-----|-------------|
| emoji-check | Scans all `.py` files for emojis — Dagster gRPC crashes on them |
| validate | Imports `definitions.py` to confirm it loads without error |
| lint | Ruff — Python style and format check |
| super-linter | YAML, JSON, Markdown, Bash checks |
| test | `pytest -m "not integration"` — unit tests only (no DB needed) |
| dbt-parse | `dbt parse` — validates all models, macros, refs (no DB connection needed) |
| summary | Reports pass/fail of all above |

### `pr-validation.yml` — runs on PR to main only
- Enforces semantic PR title: `feat:`, `fix:`, `chore:`, etc. with capital subject

**Key rule:** No emojis in Python files. Ever. They break the Dagster gRPC server in production.

---

## Environment Tiers

| Tier | `DAGSTER_ENV` | `DBT_TARGET` | dbt schemas | Data window | Schedules | Slack channel |
|------|-------------|-------------|-------------|-------------|-----------|---------------|
| dev | `dev` | `dev` | `*_dev` | 30 days | OFF | `{{SLACK_CHANNEL_DEV}}` |
| integration | `integration` | `integration` | `*_dev` | Full | OFF | `{{SLACK_CHANNEL_DEV}}` |
| prod | `prod` | `prod` | `*` (no suffix) | Full | ON | `{{SLACK_CHANNEL_PROD}}` |

### How to start local Dagster

```bash
make dev          # 30-day window, safe for rapid iteration
make integration  # full data, validate before opening a PR
make kill         # stop local Dagster
```

### Rules
- Local work always defaults to `dev` — can never accidentally write to prod schemas
- Before opening a PR: run `make integration`, validate the full pipeline
- Schedules are OFF in dev and integration — run assets manually from the UI
- `DAGSTER_ENV` drives everything: dbt target, Slack channel, schedule toggle
- Prod deploys only happen via PR → merge → `make ecr-push` → kubectl rollout

---

## GitHub Workflow

**No PR required** — branch protection is not enforced. Push directly to `main`:

```bash
git add <files>
git commit -m "fix: Description of change"
git push origin main
```

CI still runs on push to main (emoji check, validate, lint, dbt-parse, tests). Monitor at GitHub → Actions.

---

## Infrastructure

- **Cluster:** AWS EKS, cluster name `{{K8S_CLUSTER_NAME}}`, region `{{AWS_REGION}}`
- **Namespace:** `{{K8S_NAMESPACE}}`
- **Live URL:** `{{DAGSTER_INGRESS_HOST}}` (internal only)
- **Docker image:** stored in AWS ECR at `{{ECR_REGISTRY_URL}}/{{PROJECT_NAME}}`
- **Helm release:** `dagster` in namespace `{{K8S_NAMESPACE}}`
- **Helm values:** `dagster/deployment/values.yaml`
- **IAM role for pods:** `{{IAM_ROLE_ARN}}` (IRSA — required for S3 access)

### What's running in the cluster
```
dagster-daemon              # schedules, sensors, run queue
dagster-webserver           # UI at {{DAGSTER_INGRESS_HOST}}
dagster-user-deployments    # YOUR code (gRPC server, port 3030)
dagster-postgresql          # Dagster's internal metadata DB
```

---

## Getting kubectl Access

Run once (AWS SSO must be active):

```bash
AWS_PROFILE=prod aws sso login
AWS_PROFILE=prod aws eks update-kubeconfig --name {{K8S_CLUSTER_NAME}} --region {{AWS_REGION}} --alias prod
kubectl get nodes  # verify you're in
```

---

## Deploying to Production

### Prerequisites
- Docker Desktop installed and running
- kubectl connected to prod cluster (see above)
- AWS SSO active: `AWS_PROFILE=prod aws sso login`

### First-time only: create Kubernetes secret
```bash
kubectl create secret generic dagster-user-code-secrets \
  --from-env-file=/path/to/{{PROJECT_NAME}}/.env -n {{K8S_NAMESPACE}}
```
This loads all your `.env` credentials into the cluster so the container can access the warehouse, APIs, Slack, etc.

Note: use the full absolute path to `.env` — relative paths can fail depending on where you run the command from.

### Every deploy (preferred method — direct commands)

The `/deploy` slash command automates this, but here are the raw steps:

```bash
export PATH="/usr/local/bin:/usr/bin:/bin:/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:$PATH"

# 1. Pre-flight: check for conflict markers
grep -rn "<<<<<<< HEAD" dagster/ --include="*.py" --include="*.yml" && echo "STOP: conflicts" || echo "Clean"

# 2. Check AWS SSO
/usr/local/bin/aws sts get-caller-identity --profile prod --query Account --output text
# If expired: AWS_PROFILE=prod /usr/local/bin/aws sso login

# 3. ECR login
/usr/local/bin/aws ecr get-login-password --region {{AWS_REGION}} --profile prod | \
  /usr/local/bin/docker login --username AWS --password-stdin {{ECR_REGISTRY_URL}}

# 4. Build + tag + push
/usr/local/bin/docker build --platform linux/amd64 -t {{PROJECT_NAME}}:latest .
/usr/local/bin/docker tag {{PROJECT_NAME}}:latest {{ECR_REGISTRY_URL}}/{{PROJECT_NAME}}:latest
/usr/local/bin/docker push {{ECR_REGISTRY_URL}}/{{PROJECT_NAME}}:latest

# 5. Roll pod
/opt/homebrew/bin/kubectl --context prod rollout restart deployment/dagster-dagster-user-deployments-dagster-user-code -n {{K8S_NAMESPACE}}
/opt/homebrew/bin/kubectl --context prod rollout status deployment/dagster-dagster-user-deployments-dagster-user-code -n {{K8S_NAMESPACE}} --timeout=120s
```

**Expected timing:** Build <30s (cached), push <30s (most layers exist), rollout ~60s. If any step takes more than 2 minutes, something is wrong — see troubleshooting below.

### Verify it worked
```bash
kubectl --context prod get pods -n {{K8S_NAMESPACE}}       # user-code pod should show Running, age < 2 min
kubectl --context prod logs -l component=dagster-user-deployments -n {{K8S_NAMESPACE}} --tail=50
```

---

## Docker / ECR Troubleshooting

### `docker login` or `docker push` hangs indefinitely

**Root cause:** `docker-credential-desktop` (Docker Desktop's macOS Keychain credential helper) gets stuck. This blocks ALL Docker auth operations — login, push, pull to private registries.

**How to diagnose:**
```bash
# This will hang if the credential helper is broken:
echo '{{ECR_REGISTRY_URL}}' | docker-credential-desktop get

# But this returns instantly (proves Docker daemon is fine):
echo "test" | docker login --username AWS --password-stdin {{ECR_REGISTRY_URL}}
# (will get 400 Bad Request — that's expected with dummy password, the point is it responds)
```

**Fix:**
1. Check `~/.docker/config.json` for `"credsStore": "desktop"` — this is the problem line
2. Remove it:
```json
{
  "auths": {
    "{{ECR_REGISTRY_URL}}": {}
  },
  "currentContext": "desktop-linux"
}
```
3. Kill stuck processes: `pkill -f "docker-credential-desktop"`
4. Re-run ECR login (step 3 above) — should complete in <5 seconds
5. Push should now work normally

**Why this happens:** Docker Desktop stores credentials via macOS Keychain. The `docker-credential-desktop` binary can hang when Keychain is locked, corrupted, or Docker Desktop's internal state is inconsistent. Restarting Docker Desktop or the computer does NOT fix it — the `credsStore` config just re-triggers the same broken helper.

**Prevention:** Keep `"credsStore": "desktop"` removed from `~/.docker/config.json`. Docker will store ECR tokens directly in the JSON file (base64-encoded, auto-refreshed on each `docker login`). This is slightly less secure but 100% reliable.

### `docker push` uploads slowly then gets EOF

If push starts uploading but fails with `Unavailable: error reading from server: EOF` after 10-20 minutes, the credential helper was partially working but timing out mid-transfer. Same fix as above.

### AWS SSO expired

```bash
/usr/local/bin/aws sts get-caller-identity --profile prod --query Account --output text
# If error → re-auth:
AWS_PROFILE=prod /usr/local/bin/aws sso login
```

---

## Dependabot

Dependabot auto-opens PRs to bump package versions. Strategy:
- **Merge:** minor/patch bumps (same major version)
- **Close:** major version jumps (pytest 8→9, super-linter 6→8, etc.) — test these manually first
- If PRs conflict on `requirements.txt`, comment `@dependabot rebase` on each one

---

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Builds the user code container |
| `dagster/deployment/values.yaml` | Helm config for the cluster |
| `dagster/deployment/deploy.sh` | Manual deploy script (Makefile wraps this) |
| `Makefile` | `make ecr-push`, `make deploy`, `make status`, etc. |
| `.github/workflows/ci.yml` | CI pipeline (includes dbt-parse job) |
| `.github/workflows/pr-validation.yml` | PR title check |
| `dagster/env_config.py` | Reads `DAGSTER_ENV`, exports `DBT_TARGET`, `SLACK_CHANNEL`, `SCHEDULES_ENABLED` |
| `dagster/dbt_jobs.py` | `dbt_source_freshness_job` + daily schedule (prod only) |
| `dagster/dbt/profiles.yml` | dbt targets: dev, integration, prod |
| `requirements.txt` | Python deps (what goes in the Docker image) |
