# Admin Portal

Angular portal for the **Enterprise Project Intelligence OS**. Provides the
platform administration experience: agent runtime configuration, an audit
trail, and system health — all served from the **Admin-API** (`:8002`).

- **Framework:** Angular 20 (standalone components, CSS)
- **Dev port:** `4200` (the repo run script starts it with `npm start -- --port 4200`)
- **API:** consumes `Admin-API` at `http://localhost:8002` (source of truth:
  `OpenAPI/admin-api.yaml` at the repo root). The middleware is the single
  governed boundary — this portal never touches MongoDB/PostgreSQL directly.

## Views

- **Agents** (default route `/agents`): table of agent configs. Each row edits
  `model`, `framework` (dropdown of the six frameworks — langgraph, crewai,
  openai_agents, strands, google_adk, ms_agent_framework) and `enabled` (toggle),
  and saves via `PUT /api/v1/admin/agents/{agent_key}`. Shows `updated_by` /
  `updated_at`.
- **Audit** (`/audit`): table of audit events (newest first) — action, entity,
  actor, timestamp, and the raw `details`.
- **System Health** (`/health`): panel showing overall status, dependency
  statuses, and `agent_count` / `enabled_agent_count`.

## Structure

```
src/
  app/
    models/admin.ts              # typed views of the Admin-API contract
    services/admin.service.ts    # HttpClient client (agents / audit / health)
    agents-list/                 # agent config table (inline edit + PUT save)
    audit-list/                  # audit event table
    system-health/               # system health panel
    app.{ts,html,css}            # app shell (top bar + nav + <router-outlet>)
    app.config.ts                # providers (router + HttpClient)
    app.routes.ts                # '' -> /agents, /audit, /health
  environments/
    environment.ts               # apiBaseUrl (prod)  -> http://localhost:8002
    environment.development.ts   # apiBaseUrl (dev)   -> http://localhost:8002
```

The API base URL lives in `src/environments`. Point the portal at a different
Admin-API by editing `apiBaseUrl` there.

## Run (local dev)

```bash
npm install
npm start -- --port 4200      # ng serve on http://localhost:4200
```

From the repo root you can instead use the orchestrated runner (installs deps
and serves automatically):

```bash
npm run local:portals:start-all
```

The views call the Admin-API, so it must be running on `:8002` for data to
appear. Start it with `npm run local:api-services:start-all` from the repo root.

## Build (production)

```bash
npm run build                 # ng build -> dist/admin/browser
```

## Test

```bash
npm test                      # ng test (Karma + Jasmine)
# Headless single run (CI):
CHROME_BIN="/path/to/chrome" npx ng test --watch=false --browsers=ChromeHeadless
```

Specs cover the app shell, the `AdminService` (HTTP contract), and each of the
three views (`AgentsList` including the PUT save path, `AuditList`, and
`SystemHealth`) rendering from mocked responses.

## Docker

Multi-stage build (Node build stage -> nginx static serve):

```bash
docker build -t epi-admin .
docker run --rm -p 4200:80 epi-admin
# open http://localhost:4200
```

`nginx.conf` provides SPA fallback (`try_files ... /index.html`) so client-side
routes resolve. Because the API base URL is baked into the bundle at build time,
rebuild the image if the Admin-API location changes (or serve behind a reverse
proxy that maps `/api` to the Admin-API).
