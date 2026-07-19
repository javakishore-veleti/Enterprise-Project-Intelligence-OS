# PostgreSQL Changelog

Ordered ledger of operational-state migrations. Files live in `../migrations/`
and are applied by `../apply_migrations.py` (filename order, once each).

| Version | File | Summary |
|---|---|---|
| V001 | `V001__ingestion_runs.sql` | `ingestion` schema + `ingestion_runs` table and indexes. |
| V002 | `V002__admin_config.sql` | `admin` schema + `agent_configs` and `audit_events`; seeds the 16 agents (LangGraph, Claude defaults). |
