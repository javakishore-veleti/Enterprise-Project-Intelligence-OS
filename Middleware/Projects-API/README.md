# Projects API

Project intelligence queries over the **MongoDB evidence store**. Runs on
**port 8003**. Read-only: it never writes to the evidence store. Structure
mirrors the reference `Ingestion-API` (same Endpoint→Facade→Service→DAO layering
and typed DTOs); the difference is the datastore (MongoDB via pymongo) and that
all use cases are queries.

## Endpoints

- `GET /api/v1/projects?query=&limit=&offset=` — search/filter projects (paginated).
- `GET /api/v1/projects/{project_key}` — one project.
- `GET /api/v1/projects/{project_key}/metrics` — latest computed delivery-health metrics.
- `GET /health/live`, `GET /health/ready` (readiness pings MongoDB).

## Run locally

```bash
# infra (MongoDB) up + sample data
npm run local:containers:start-all
mongosh "mongodb://localhost:27017/epi_os" Database/MongoDB/seed/001_sample_projects.js

cd Middleware/Projects-API
python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
./.venv/bin/uvicorn projects_api.api.main:app --port 8003 --reload
```

Swagger UI: http://localhost:8003/docs

## Test

```bash
pytest          # unit (fakes) + integration (mongomock) + contract (TestClient); no live Mongo needed
```

## Configuration

`PROJECTS_API_PORT`, `MONGO_URI`, `MONGO_DATABASE`, `LOG_LEVEL` (see repo `.env.example`).
