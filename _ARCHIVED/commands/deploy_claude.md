Build, push to ECR, and roll the production Dagster user-code pod.

**PATH NOTE:** `aws`, `docker`, and `kubectl` are NOT in the default shell PATH. Always use full paths or export PATH first:
```bash
export PATH="/usr/local/bin:/usr/bin:/bin:/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:$PATH"
```
Do NOT use `make ecr-push` — it fails because make doesn't inherit this PATH.

---

**PRE-FLIGHT CHECKS (run ALL before proceeding):**

1. Scan for conflict markers — they crash the container at startup:
```bash
grep -rn "<<<<<<< HEAD" dagster/ --include="*.py" --include="*.yml" && echo "STOP: conflicts found" || echo "Clean"
```
If anything is found, resolve all conflicts before continuing.

2. Check Docker credential store — `credsStore: desktop` causes hangs:
```bash
grep credsStore ~/.docker/config.json && echo "REMOVE credsStore — see RULES.md" || echo "OK"
```
If found, remove the `"credsStore": "desktop"` line from `~/.docker/config.json` and kill stuck processes: `pkill -f "docker-credential-desktop"`. Docker Desktop's credential helper hangs indefinitely and blocks all login/push/pull operations. Restarting Docker or the computer does NOT fix it — only removing credsStore does.

---

1. Check AWS SSO is valid:
```bash
/usr/local/bin/aws sts get-caller-identity --profile prod --query Account --output text
```
If expired, run: `AWS_PROFILE=prod /usr/local/bin/aws sso login` (opens browser)

2. ECR login:
```bash
export PATH="/usr/local/bin:/usr/bin:/bin:/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:$PATH"
/usr/local/bin/aws ecr get-login-password --region us-east-1 --profile prod | \
  /usr/local/bin/docker login --username AWS --password-stdin YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```
**This must complete in <5 seconds.** If it hangs, the credsStore check above was missed — go fix it.

3. Build for linux/amd64 and push:
```bash
export PATH="/usr/local/bin:/usr/bin:/bin:/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:$PATH"
/usr/local/bin/docker build --platform linux/amd64 -t dagster-user-code:latest .
/usr/local/bin/docker tag dagster-user-code:latest YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/dagster-user-code:latest
/usr/local/bin/docker push YOUR_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/dagster-user-code:latest
```
**Expected timing:** Build <30s (cached), push <30s (most layers already exist). If push takes >2 minutes, something is wrong — check credsStore and ECR auth.

4. Roll the user-code pod (PATH must include aws for kubectl EKS auth):
```bash
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"
/opt/homebrew/bin/kubectl --context prod rollout restart deployment/dagster-dagster-user-deployments-dagster-user-code -n dagster
/opt/homebrew/bin/kubectl --context prod rollout status deployment/dagster-dagster-user-deployments-dagster-user-code -n dagster --timeout=120s
```

5. Confirm pod is running:
```bash
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"
/opt/homebrew/bin/kubectl --context prod get pods -n dagster
```
Look for `dagster-dagster-user-deployments-dagster-user-code-*` with `Running` status and age < 2 min.

**Notes:**
- Must be run from project root (repo root directory)
- Docker Desktop must be running before step 2
- Only the user-code pod needs restart — daemon and webserver pods are untouched
- After rollout, Dagster picks up new definitions within ~30 seconds
- To check user-code logs: `/opt/homebrew/bin/kubectl --context prod logs -l component=dagster-user-deployments -n dagster --tail=50`
- **NEVER use the Dagster UI "Reload" button** — the pod uses `dagster api grpc` which doesn't support hot-reload. Always use `rollout restart`.
- **If only restarting (no code change):** skip steps 2–3, just run steps 4–5.
- **New schedules deploy as OFF** — after rollout, go to Schedules tab in Dagster UI and manually toggle any new schedules ON.
- **If UI looks stale after rollout:** hard refresh the browser (Cmd+Shift+R) — Dagster caches definitions heavily.
- **NEVER manually trigger pipelines after deployment.** All pipelines run on their own `*_6x_daily` schedules and will pick up automatically. Manual post-deploy runs cause duplicates and cascade failures.
