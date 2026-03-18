Start local Dagster in INTEGRATION mode (full data, writes to *_dev schemas, schedules OFF). Use this to validate the full pipeline before opening a PR.

1. Check if local Dagster is already running:
```bash
ps aux | grep "dagster dev" | grep -v grep
```

2. Kill it regardless (can't change env vars without restart):
```bash
pkill -9 -f "dagster dev" || true
sleep 2
```

3. Verify all stopped (should return nothing):
```bash
ps aux | grep "dagster dev" | grep -v grep
```

4. Start in integration mode:
```bash
DAGSTER_HOME=$(pwd)/.dagster_home \
DAGSTER_ENV=integration \
DBT_TARGET=integration \
.venv/bin/python -m dagster dev -f dagster/definitions.py > _LOGS/dagster.log 2>&1 &
```

5. Wait and confirm it's up:
```bash
sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```
Expected: `200`

Tell the user: "Dagster is running in **integration** mode at http://localhost:3000 — full data, _dev schemas, schedules off."

**Notes:**
- dbt models write to `*_dev` schemas — still safe, not prod
- Full data window — use this to validate before deploying to prod
- Schedules are OFF — run assets manually from the UI
- Slack alerts go to `#dev-pipeline-alerts`
- Check logs: `tail -f _LOGS/dagster.log`
- When validation passes, run `/pr` to deploy to prod
