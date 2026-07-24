# OpenAPI Contracts

Source-of-truth API specs for the five middleware services. UI API clients are
generated/validated from these — do not hand-duplicate contracts.

| File | Service | Status |
|---|---|---|
| `ingestion-api.yaml` | Ingestion API (:8001) | generated |
| `admin-api.yaml` | Admin API (:8002) | generated |
| `projects-api.yaml` | Projects API (:8003) | generated |
| `risk-analytics-api.yaml` | Risk Analytics API (:8004) | generated |
| `org-management-api.yaml` | Org Management API (:8005) | generated |

## Regenerate a spec

Each FastAPI service is the authority for its own contract. Export from the app:

```bash
cd Middleware/Ingestion-API
./.venv/bin/python -c "import yaml; from ingestion_api.api.main import create_app; \
  yaml.safe_dump(create_app().openapi(), open('../../OpenAPI/ingestion-api.yaml','w'), sort_keys=False)"
```

The same one-liner regenerates the other services — swap the service dir, module,
and output file. For the Org Management API (:8005):

```bash
cd Middleware/Org-Management-API
./.venv/bin/python -c "import yaml; from org_management_api.api.main import create_app; \
  yaml.safe_dump(create_app().openapi(), open('../../OpenAPI/org-management-api.yaml','w'), sort_keys=False)"
```
