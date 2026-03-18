Start local Dagster in DEV mode (30-day data window, writes to *_dev schemas, schedules OFF).

1. Kill any running local Dagster processes:
```bash
pkill -9 -f "dagster dev" || true
sleep 2
```

2. Verify all stopped (should return nothing):
```bash
ps aux | grep "dagster dev" | grep -v grep
```

3. Start in dev mode:
```bash
DAGSTER_HOME=$(pwd)/.dagster_home \
DAGSTER_ENV=dev \
DBT_TARGET=dev \
.venv/bin/python -m dagster dev -f dagster/definitions.py > _LOGS/dagster.log 2>&1 &
```

4. Wait and confirm it's up:
```bash
sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
```
Expected: `200`

Tell the user: "Dagster is running in **dev** mode at http://localhost:3000 — 30-day data window, _dev schemas, schedules off."

**Notes:**
- dbt models write to `*_dev` schemas (e.g. `analytics_metabase_dev`) — safe, can't touch prod
- Schedules are OFF — run assets manually from the UI
- Slack alerts go to `#dev-pipeline-alerts`
- Check logs: `tail -f _LOGS/dagster.log`
- To stop: `pkill -9 -f "dagster dev"`
