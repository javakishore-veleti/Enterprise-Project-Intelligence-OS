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

## `project_dataset_ingest` DAG

`dags/project_dataset_ingest/` triggers and monitors dataset ingestion through
the **Ingestion-API** FastAPI boundary (`:8001`) — it never touches a database
directly and contains no agent/LLM logic. Triggered on demand (`schedule=None`).

Task flow:

```
read_metadata -> check_disk_space -> start_ingestion -> poll_status -> finalize
```

- `read_metadata` — validate/shape the run request from DAG params
  (`dataset_id`, `batch_size`, `parallelism`, `requested_by`).
- `check_disk_space` — fail fast if the worker lacks free disk.
- `start_ingestion` — `POST /api/v1/ingestion/runs`, returns `run_id`.
- `poll_status` — `GET /api/v1/ingestion/runs/{run_id}` until a terminal status
  (`COMPLETED`/`FAILED`/`CANCELLED`).
- `finalize` — succeed on `COMPLETED`, otherwise fail the DAG.

The base URL comes from the `INGESTION_API_BASE_URL` env var (default
`http://localhost:8001`). The task logic lives in `tasks.py` as pure functions
that take the base URL + an HTTP client (injected as `requests` in the DAG), so
they are unit-testable with a fake client — no network, scheduler, or live API.

Trigger with params, e.g.:

```bash
airflow dags trigger project_dataset_ingest \
  --conf '{"dataset_id": "msr-issue-tracking", "batch_size": 1000, "parallelism": 4, "requested_by": "ops"}'
```

## Dataset operational DAGs (`acquire` / `validate` / `index` / `reconcile`)

Four on-demand (`schedule=None`) DAGs cover the rest of the dataset lifecycle.
Each follows the same shape as `project_dataset_ingest`: pure task callables in
`tasks.py` (fake-client testable) and a thin `@dag`/`@task` wrapper. All call the
**Ingestion-API** boundary (`:8001`, `INGESTION_API_BASE_URL`, default
`http://localhost:8001`) — no DB access, no agent/LLM logic.

| DAG | Task flow | Ingestion-API calls |
| --- | --- | --- |
| `project_dataset_acquire` | `build_acquire_spec -> start_acquisition -> poll_acquisition -> verify_checksum -> extract_dataset -> finalize` | `POST /acquisitions`, `GET /acquisitions/{id}`, `POST /acquisitions/{id}/verify`, `POST /acquisitions/{id}/extract` |
| `project_dataset_validate` | `build_validation_request -> start_validation -> poll_validation -> evaluate_validation` | `POST /validations`, `GET /validations/{id}` |
| `project_dataset_index` | `build_index_request -> start_indexing -> poll_indexing -> finalize` | `POST /indexes`, `GET /indexes/{id}` |
| `project_dataset_reconcile` | `build_reconcile_request -> start_reconciliation -> poll_reconciliation -> evaluate_reconciliation` | `POST /reconciliations`, `GET /reconciliations/{id}` |

> **Middleware status — PENDING endpoints.** Today the Ingestion-API implements
> only `POST /api/v1/ingestion/runs` and `GET /api/v1/ingestion/runs/{run_id}`.
> The acquire/validate/index/reconcile endpoints above are the **intended REST
> contract and are not yet implemented** in `Middleware/Ingestion-API/`. Each is
> marked `PENDING` in the DAG's `tasks.py`; the DAGs parse and their callables
> are fully unit-tested against a fake client regardless.

## Scheduled risk-analysis DAGs

Two cron DAGs drive multi-agent risk analysis **only** through the
**RiskAnalytics-API** boundary (`:8004`, `RISK_ANALYTICS_API_BASE_URL`, default
`http://localhost:8004`). Agent prompts and reasoning live behind the
FastAPI/LangGraph boundary, never in the DAG.

- `project_risk_schedule` — daily (`0 6 * * *`). `resolve_projects ->
  analyze_project (dynamic task mapping, one instance per configured project) ->
  summarize`. Calls the **existing** endpoint
  `POST /api/v1/analysis/projects/{project_key}` with body
  `{"agents": [...], "requested_by": "airflow"}`. Configure the project set and
  agents via DAG params (`project_keys`, `agents`, `requested_by`).
- `portfolio_risk_schedule` — weekly (`0 7 * * 1`). `build_portfolio_request ->
  start_portfolio_analysis -> finalize`. Models the **planned**
  `POST /api/v1/analysis/portfolios/{portfolio_key}` endpoint (mirrors the
  per-project body). **This portfolio endpoint is not yet implemented** in the
  RiskAnalytics-API (tracked as the `portfolio_risk_orchestrator` graph); the
  call is marked `PENDING` in `tasks.py`.

### Tests

Hermetic (no scheduler/webserver, no live API). Per DAG: a DagBag parse test
asserts zero import errors and the expected task graph/schedule; the rest
exercise the pure task callables against a fake HTTP client. As of the latest
run: **114 tests pass** across all seven DAGs.

```bash
cd Airflow
python3.12 -m venv .venv   # airflow 2.10.0 supports Python 3.8–3.12
./.venv/bin/pip install "apache-airflow==2.10.0" requests pytest \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.0/constraints-3.12.txt"
./.venv/bin/python -m pytest tests
```
