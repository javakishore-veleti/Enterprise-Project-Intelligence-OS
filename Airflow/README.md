# Airflow

Operational workflow scheduling: dataset acquisition, batch ingestion,
validation, index creation, reconciliation, and scheduled project/portfolio
analysis. DAGs invoke the risk-analysis capability **only** through the FastAPI
boundary — no agent prompts or reasoning logic live here.

- `dags/` — one package per workflow (`project_dataset_acquire`, `..._ingest`,
  `..._validate`, `..._index`, `..._reconcile`, `project_risk_schedule`,
  `portfolio_risk_schedule`).
- `plugins/`, `config/`, `tests/`.

## Run locally

Airflow is heavier than the datastores and is **not** required for the
foundation slice. Start it explicitly:

```bash
WITH_AIRFLOW=1 bash CICD/LocalDev/docker-all-up.sh   # serves on :8080
```

The local compose uses `apache/airflow:2.10.0-python3.12` (standalone,
LocalExecutor) and expects an `airflow` metadata database in the local Postgres.
