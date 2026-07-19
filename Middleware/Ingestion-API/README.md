# Ingestion API

Dataset ingestion management service for Enterprise Project Intelligence OS.
Runs on **port 8001**. This service is the **reference implementation** of the
platform's middleware layering — new microservices should mirror its structure.

## Endpoints

- Ingestion runs: `POST /api/v1/ingestion/runs`, `GET /api/v1/ingestion/runs/{run_id}`.
- **Operational sub-operations** (called by the Airflow DAGs over the boundary):
  `POST/GET /api/v1/ingestion/acquisitions` (+ `/{id}/verify`, `/{id}/extract`),
  `/validations`, `/indexes`, `/reconciliations`. Each runs synchronously and is
  persisted to `ingestion.operations`. `validate`/`index`/`reconcile` report real
  counts from the MongoDB evidence store; acquisition download/verify/extract are
  stubbed (no live 5.8 GB dataset).
- `GET /health/live`, `GET /health/ready` (readiness pings Postgres).

## Layering

```
api/ (routers)  ->  facades/ (use cases)  ->  services/ (domain rules)  ->  daos/ (persistence + gateways)
```

- Cross-layer calls use typed DTOs (`dtos/`) built on `common/models.TypedModel`.
- `interfaces/` holds abstract contracts; concrete classes implement them.
- `daos/airflow_gateway/` is the governed boundary to Apache Airflow — no agent
  or reasoning logic lives here.
- Wiring (DAO -> service -> facade) is declared once in `api/dependencies/`.

## Run locally

From the repo root, `npm run local:containers:start-all` brings up Postgres,
then apply migrations (`Database/PostgreSQL/apply_migrations.py`). To run just
this service:

```bash
cd Middleware/Ingestion-API
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn ingestion_api.api.main:app --port 8001 --reload
```

- Swagger UI: http://localhost:8001/docs
- OpenAPI JSON: http://localhost:8001/openapi.json
- Liveness: `GET /health/live` · Readiness (checks Postgres): `GET /health/ready`

## Test

```bash
pytest              # unit + contract tests; no infra required (fakes injected)
```

## Configuration

Environment variables (see repo `.env.example`): `INGESTION_API_PORT`,
`PG_HOST`, `PG_PORT`, `PG_USER`, `PG_PASSWORD`, `PG_DATABASE`, `AIRFLOW_BASE_URL`,
`LOG_LEVEL`.
