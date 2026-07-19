# PostgreSQL Changelog

Ordered ledger of operational-state migrations. Files live in `../migrations/`
and are applied by `../apply_migrations.py` (filename order, once each).

| Version | File | Summary |
|---|---|---|
| V001 | `V001__ingestion_runs.sql` | `ingestion` schema + `ingestion_runs` table and indexes. |
| V002 | `V002__admin_config.sql` | `admin` schema + `agent_configs` and `audit_events`; seeds the 16 agents (LangGraph, Claude defaults). |
| V003 | `V003__risk_analysis.sql` | `risk` schema + `graph_runs` and `risk_findings` for analysis run + finding persistence. |
| V004 | `V004__risk_review.sql` | `risk_findings.meta` column + `risk.reports` table for the review pipeline. |
| V005 | `V005__ingestion_operations.sql` | `ingestion.operations` table for acquire/validate/index/reconcile sub-operations. |
| V006 | `V006__datasets.sql` | `ingestion.datasets` dataset-acquisition status; seeds the public Jira dataset. |
