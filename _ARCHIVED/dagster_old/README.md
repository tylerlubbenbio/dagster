# Dagster @ dagster.bioptimizers.net

Data orchestration (BIOptimizers BI). Deployed via Docker Compose with PostgreSQL, webserver, daemon, and one code location.

## Access

- **URL:** https://dagster.bioptimizers.net
- **SSL:** Let's Encrypt (Cloudflare proxy). Cert renews via `certbot renew` (see `/opt/apps/scripts/certbot-renew.sh`).

## Logins

Access is protected by **nginx HTTP Basic Auth**:

| Field | Value |
|-------|--------|
| **URL** | https://dagster.bioptimizers.net |
| **Username** | tylerlubben@bioptimizers.com |
| **Password** | Bioptimizers11= |

The password file is `/etc/nginx/.htpasswd-dagster`. To change the password:  
`printf 'USER:%s\n' "$(openssl passwd -apr1 'NEWPASSWORD')" | sudo tee /etc/nginx/.htpasswd-dagster` then `sudo systemctl reload nginx`.

## SMTP (AWS SES)

SMTP is not used by Dagster OSS for alerts out of the box. The credentials you provided are available for the rest of the stack (Airflow, NocoDB, Outline, Baserow). If you add alerting (e.g. custom code or a future Dagster feature), use:

- Host: `email-smtp.us-east-1.amazonaws.com`
- Port: 465 (TLS/SSL)
- User: (your SES SMTP user)
- From: BIOptimizers BI Team \<bi_team@bioptimizers.net\>

## Stack

- **dagster_postgres** – Run/schedule/event storage
- **dagster_user_code** – Code location (gRPC), image `dagster_user_code:latest`
- **dagster_webserver** – UI on port 3000 (proxied by nginx)
- **dagster_daemon** – Scheduler, run launcher (Docker)

## Config files

- `dagster.yaml` – Instance (storage, run launcher, scheduler)
- `workspace.yaml` – Code locations
- `definitions.py` – Assets/jobs (edit and rebuild `dagster_user_code` to apply)

## Nginx

- Example: `nginx-dagster.example.conf`
- Bootstrap (HTTP-only for cert issuance): `nginx-dagster-bootstrap.conf`
- Live config: `/etc/nginx/sites-available/dagster.bioptimizers.net`

## Production checklist

- **Postgres:** All storage (run, schedule, event_log) points to `dagster_postgres` (hostname in `dagster.yaml`). Webserver, daemon, and user-code containers use the same `DAGSTER_POSTGRES_*` env vars from docker-compose.
- **Concurrency:** `max_concurrent_runs: 5` (at most 5 runs at once). Same job cannot run twice at once: `tag_concurrency_limits` on `dagster/job_name` with `applyLimitPerUniqueValue: true` and `limit: 1`.

## Versions (pinned)

- dagster 1.12.14
- dagster-webserver 1.12.14
- dagster-postgres 0.28.14
- dagster-docker 0.28.14
