# {{PROJECT_NAME}} Vision

## What We've Built

A fully operational data platform: multi-source extraction → data warehouse → dbt transformation → analytics. Production-grade, Kubernetes-deployed, Dagster-orchestrated.

## The Problem (Still True)

Data lives across many disconnected systems — internal databases, SaaS APIs, streaming sources. No single place to query across all of them for analytics, reporting, or cross-source insights.

## What's Live Today

> Configure via /activate once your sources and warehouse are defined.

**Ingestion (RAW layer):** Sources operational in production:
- API sources: (list here)
- Internal DBs: (list here)
- Streaming sources: (list here)

**Transformation (dbt):** 4-layer dbt stack running daily:
- Staging views across source systems
- Core dims/facts
- Analytics OBTs (cross-source joins)
- Report layer with exposures

**Orchestration:** Dagster on Kubernetes with:
- YAML-driven asset factory — no boilerplate per source
- Watermark-based incremental loads
- Daily dbt schedule
- Slack alerting on failures
- 3 environments: dev (local) → integration (local, full data) → prod (K8s)

## Guiding Principles

**YAML-driven, zero boilerplate:** New sources plug in via `config.yaml` + `extractor.py`. The asset factory handles everything else.

**NDJSON streaming:** Extractors write to local NDJSON → bulk load into warehouse. No in-memory accumulation. Scales to tens of millions of rows.

**Watermark-based incremental:** Every source tracks its own watermark in `raw_metadata.watermarks`. No full-refresh rebuilds in production.

**Source-native primary keys:** Use the source system's unique ID as primary key. Never auto-increment. Every load uses a staging table with ROW_NUMBER dedup — duplicate PKs are structurally impossible regardless of what the source sends.

**Environment isolation:** `DAGSTER_ENV` controls everything — schema prefix, schedule activation, Slack channel, dbt target. Local runs never touch prod schemas.

## Where We're Going

**Near Term**
- Build out core dims/facts layer (proper dimensional models per your domain)
- Expand analytics OBTs for cross-source reporting
- Add report-layer aggregations for BI dashboards

**Medium Term**
- Self-service BI dashboard layer with dbt exposures wired to reporting tool
- Semantic layer integration for standardized business metrics
- Schema drift detection and alerting (raw schema changes don't silently break dbt)

**Long Term**
- Near-real-time sync for high-value sources
- Cross-source identity resolution (users/entities across systems)
- Data quality SLAs with automated monitoring

## What This Isn't

- Not a real-time streaming platform (batch-first, incremental windows)
- Not a BI tool — a BI layer sits on top; this is extraction + transformation
- Not a monolith — each source is independently deployable and debuggable
