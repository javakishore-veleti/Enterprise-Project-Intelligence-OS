# Admin API

Platform administration for Enterprise Project Intelligence OS. Runs on **port
8002**, backed by PostgreSQL (operational state). Same reference layering as
`Ingestion-API` (Endpoint→Facade→Service→DAO, typed DTOs).

This service owns the **agent configuration the agent phase reads** — including
the per-agent `framework` toggle (`langgraph` default, plus the alternative
adapter frameworks). Every configuration change writes an **audit event**.

## Endpoints

- `GET  /api/v1/admin/agents` — list agent configs (paginated).
- `GET  /api/v1/admin/agents/{agent_key}` — one agent config.
- `PUT  /api/v1/admin/agents/{agent_key}` — create/update model, framework, enabled, prompt_ref (audited).
- `GET  /api/v1/admin/audit` — administrative audit history (newest first).
- `GET  /api/v1/admin/system/health` — aggregate health + agent counts.
- `GET  /health/live`, `GET /health/ready` (readiness pings Postgres).

Migration `V002__admin_config.sql` creates the `admin` schema and seeds the 16
specialist agents with defaults (LangGraph, `claude-opus-4-8`, enabled).

## Run locally

```bash
npm run local:containers:start-all
npm run local:db:migrate            # applies V001 + V002
cd Middleware/Admin-API
python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
./.venv/bin/uvicorn admin_api.api.main:app --port 8002 --reload
```

Swagger UI: http://localhost:8002/docs

## Test

```bash
pytest          # unit (fakes) + contract (TestClient); no live Postgres needed
```

## Configuration

`ADMIN_API_PORT`, `PG_*`, `AGENT_MODEL`, `AGENT_FRAMEWORK`, `LOG_LEVEL` (see repo `.env.example`).
