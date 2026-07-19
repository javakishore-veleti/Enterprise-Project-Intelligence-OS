# PostgreSQL Changelog

Ordered ledger of operational-state migrations. Files live in `../migrations/`
and are applied by `../apply_migrations.py` (filename order, once each).

| Version | File | Summary |
|---|---|---|
| V001 | `V001__ingestion_runs.sql` | `ingestion` schema + `ingestion_runs` table and indexes. |
