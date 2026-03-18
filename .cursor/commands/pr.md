Full automated deploy: pre-flight → commit → PR → CI auto-merge → deploy. One run, walk away.

**Before starting:** Validate in integration mode first (`/integration`). Make sure AWS SSO is active: `AWS_PROFILE=prod aws sso login`

---

## Step 1: Pre-flight checks (stop if anything fails)

```bash
# Conflict markers check — MUST be first. These crash Docker at startup.
grep -rn "<<<<<<< HEAD" dagster/ --include="*.py" --include="*.yml" --include="*.yaml" && echo "FAIL: conflict markers found" || echo "OK"

# Emoji check
grep -rn '[^\x00-\x7F]' dagster/ --include="*.py" && echo "FAIL: emojis found" || echo "OK"

# Lint + format
ruff check . && ruff format --check .

# Unit tests
pytest -m "not integration" -q

# dbt parse
cd dagster/dbt && \
  TARGET_HOST=localhost TARGET_PORT=5439 TARGET_USERNAME=x TARGET_PASSWORD=x TARGET_DATABASE=x \
  DBT_TARGET=dev dbt deps --profiles-dir . && \
  TARGET_HOST=localhost TARGET_PORT=5439 TARGET_USERNAME=x TARGET_PASSWORD=x TARGET_DATABASE=x \
  DBT_TARGET=dev dbt parse --profiles-dir . && cd ../..
```

If anything fails, fix it before continuing.

---

## Step 2: Ask the user ONE question

"What's the PR title and a 1-2 sentence description of what changed?"

(Infer the branch name from the title: `feat/short-description`)

---

## Step 3: Commit, push, create PR, enable auto-merge

```bash
# Create branch and commit everything staged
git checkout -b [branch-name]
git add -A
git status  # show user what's being committed (never add .env)
git commit -m "[title]

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push -u origin [branch-name]

# Create PR
cat > /tmp/pr_body.txt << 'EOF'
[description]

🤖 Generated with Claude Code
EOF

gh pr create \
  --title "[title]" \
  --body-file /tmp/pr_body.txt \
  --base main \
  --head [branch-name]

# Enable auto-merge: GitHub will squash+merge automatically when CI passes
gh pr merge --auto --squash --delete-branch
```

Tell the user: "PR created and auto-merge enabled. CI is running — will merge automatically when all checks pass. Watching..."

---

## Step 4: Watch CI and wait for merge

Poll until merged:
```bash
# Check every 30s until merged
while true; do
  STATE=$(gh pr view --json state -q '.state')
  if [ "$STATE" = "MERGED" ]; then
    echo "Merged!"
    break
  fi
  echo "State: $STATE — waiting..."
  sleep 30
done

git checkout main && git pull origin main
```

---

## Step 5: Deploy to prod

```bash
make ecr-push
kubectl rollout restart deployment dagster-dagster-user-deployments-dagster-user-code -n dagster --context prod
kubectl rollout status deployment dagster-dagster-user-deployments-dagster-user-code -n dagster --context prod --timeout=120s
```

---

## Step 6: Confirm and report

Run `kubectl get pods -n dagster --context prod` — all pods should show `Running`.

Report: "Deployed. Changes are live at dagster.internal.example.com"

---

**Notes:**
- `--auto` requires auto-merge to be enabled in the repo settings (GitHub → Settings → General → Allow auto-merge)
- Never stage `.env`, secrets, or credential files
- `make ecr-push` builds for `linux/amd64`, pushes to ECR with tag `latest`
- If AWS SSO expired: `AWS_PROFILE=prod aws sso login`
