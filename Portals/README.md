# Portals

Two Angular applications:

- `Admin/` (:4200) — dataset ingestion, configuration, and monitoring.
- `Project-Tracker/` (:4201) — dashboards, risk register, and reports.

Both are scaffolded in a later phase. Once each has a `package.json`, start them
with `npm run local:portals:start-all` from the repo root (each portal runs
`npm install` on start). API clients are generated from the `OpenAPI/` contracts.
