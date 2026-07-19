# Project-Tracker Portal

Angular portal for the **Enterprise Project Intelligence OS**. Provides the
project-tracking experience: a searchable list of projects served from the
**Projects-API** (`:8003`). It is the first, foundational slice — dashboards,
risk register, and reports land in later phases.

- **Framework:** Angular 20 (standalone components, CSS)
- **Dev port:** `4201` (the repo run script starts it with `npm start -- --port 4201`)
- **API:** consumes `Projects-API` at `http://localhost:8003` (source of truth:
  `OpenAPI/projects-api.yaml` at the repo root). The middleware is the single
  governed boundary — this portal never touches MongoDB/PostgreSQL directly.

## Structure

```
src/
  app/
    models/project.ts            # typed views of the Projects-API contract
    services/projects.service.ts # HttpClient client for GET /api/v1/projects[...]
    projects-list/               # projects list view (table + search box)
    app.{ts,html,css}            # app shell (top bar + <router-outlet>)
    app.config.ts                # providers (router + HttpClient)
    app.routes.ts                # '' -> ProjectsList
  environments/
    environment.ts               # apiBaseUrl (prod)  -> http://localhost:8003
    environment.development.ts   # apiBaseUrl (dev)   -> http://localhost:8003
```

The API base URL lives in `src/environments`. Point the portal at a different
Projects-API by editing `apiBaseUrl` there.

## Run (local dev)

```bash
npm install
npm start -- --port 4201      # ng serve on http://localhost:4201
```

From the repo root you can instead use the orchestrated runner (installs deps
and serves on :4201 automatically):

```bash
npm run local:portals:start-all
```

The projects list calls `GET /api/v1/projects?query=&limit=&offset=`, so the
Projects-API must be running on `:8003` for data to appear. Start it with
`npm run local:api-services:start-all` from the repo root.

## Build (production)

```bash
npm run build                 # ng build -> dist/project-tracker/browser
```

## Test

```bash
npm test                      # ng test (Karma + Jasmine)
# Headless single run (CI):
CHROME_BIN="/path/to/chrome" npx ng test --watch=false --browsers=ChromeHeadless
```

Specs cover the app shell, the `ProjectsService` (HTTP contract), and the
`ProjectsList` component (renders rows from a mocked response).

## Docker

Multi-stage build (Node build stage -> nginx static serve):

```bash
docker build -t epi-project-tracker .
docker run --rm -p 4201:80 epi-project-tracker
# open http://localhost:4201
```

`nginx.conf` provides SPA fallback (`try_files ... /index.html`) so client-side
routes resolve. Because the API base URL is baked into the bundle at build time,
rebuild the image if the Projects-API location changes (or serve behind a
reverse proxy that maps `/api` to the Projects-API).
