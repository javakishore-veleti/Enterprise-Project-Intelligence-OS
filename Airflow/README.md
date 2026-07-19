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

### Tests

Hermetic (no scheduler/webserver, no live Ingestion-API). A DAG-parse test uses
`airflow.models.DagBag` to assert zero import errors; the rest exercise the task
callables against a fake HTTP client.

```bash
cd Airflow
python3.12 -m venv .venv   # airflow 2.10.0 supports Python 3.8–3.12
./.venv/bin/pip install "apache-airflow==2.10.0" requests pytest \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.0/constraints-3.12.txt"
./.venv/bin/python -m pytest tests
```
