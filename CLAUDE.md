# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current State

**Foundation slice is built and verified running.** The rest of the platform is still scaffolding/spec — the README's "## Enterprise Project Intelligence OS — Folder Structure" is the authoritative target layout; create new code at the paths it prescribes.

What exists and runs today (verified end-to-end against live Postgres):
- Local infra compose + idempotent scripts under `CICD/LocalDev/` (reuses already-running containers).
- Root `package.json` task runner, `pyproject.toml`, `.env.example`.
- **`Middleware/Ingestion-API/` (:8001) — the reference microservice.** Full Endpoint→Facade→Service→DAO layering, DTOs, health endpoints, Postgres-backed DAO (pg8000) + stubbed `airflow_gateway`. Also the **operational sub-operations** the DAGs call: acquire/validate/index/reconcile (`POST/GET /api/v1/ingestion/{acquisitions,validations,indexes,reconciliations}` — persisted to `ingestion.operations`, run synchronously; validate/index/reconcile compute real counts against the Mongo evidence store, acquisition download/verify/extract are stubbed). 18 tests. **Copy its structure when building new services.**
- **`Middleware/Projects-API/` (:8003) — queries over the MongoDB evidence store** (pymongo). Search/get/metrics endpoints, **plus deterministic metric computation** (`POST /projects/{key}/metrics/compute` and `/metrics/compute-all`): reads ingested issues/histories/links and computes backlog growth, reopen rate, blocker count, and dependency depth (pure Python + Mongo, **no LLM**), upserting `project_metrics` + project counts. This is what turns raw ingested records into the evidence the agents consume. 21 tests. Verified live (metrics match seeded evidence; agents cite the real numbers).
- **`Middleware/Admin-API/` (:8002) — platform/agent configuration on Postgres.** Owns the per-agent `framework` toggle + model/prompt/enabled config (read by the agent phase), plus audit history and system health. V002 migration seeds the 16 agents (LangGraph/Claude defaults). Config changes write audit events. 8 tests; verified live (framework toggle persisted + audited).
- **`Middleware/RiskAnalytics-API/` (:8004) — multi-agent risk analysis, the core value.** Spans both stores: reads agent config from Postgres (`admin.agent_configs`), builds deterministic evidence from Mongo, runs specialists via the framework toggle, persists findings + reports to `risk.*`. `POST /api/v1/analysis/projects/{key}` (with optional `include_review`) → LangGraph → Claude → typed `RiskFinding[]` (+ reports); `POST /api/v1/analysis/portfolios/{key}` (cross-project); `GET /api/v1/analysis/runs/{id}`. 22 tests (fakes, no LLM). **Verified live against real Claude** (7-detector fan-out, full review pipeline, 4-project portfolio). Requires `ANTHROPIC_API_KEY` in env at runtime.
- **`Agents/` — the specialist-agent package (`epi-agents`). All 16 agents implemented.** `agent_core` = three ports: `RiskAgent` (`EvidencePackage → RiskFinding[]`), `FindingProcessor` (`findings → findings`), `Reporter` (`findings → RiskReport`), plus shared deterministic scoring.
  - **7 detectors** (LangGraph adapters + registry toggle): `schedule_risk`, `quality_risk`, `project_status_tracking`, `dependency_risk`, `resource_risk`, `backlog_health`, `delivery_forecasting`. `schedule_risk` also has a real **`openai_agents` adapter** (OpenAI Agents SDK → LiteLLM → Claude) proving the multi-framework seam. Optional extra `frameworks-openai`.
  - **8 review agents**: 3 **deterministic** processors — no LLM (`risk_scoring` rank, `risk_deduplication` merge, `risk_correlation` group); 5 **LLM** agents (LangChain single-step) — `evidence_validation`, `critic` (processors), `mitigation_planning`, `project_reporting`, `executive_reporting` (reporters). Processor annotations land in each finding's `meta`.
  - 39 hermetic tests (deterministic processors fully covered; LLM agents wiring-tested).
- **`Middleware/RiskAnalytics-API/graphs/project_risk_manager`** — LangGraph map-reduce **detector fan-out** (`Send` per agent, merge findings, capture per-agent errors). Verified live with a 7-detector fan-out.
- **`Middleware/RiskAnalytics-API/graphs/risk_review`** — a sequential **LangGraph review pipeline** run when `include_review=true`: `validate → dedup → correlate → score → [critic loop] → report`. The critic is a **bounded revision loop** (LangGraph conditional edge — re-runs until it converges or hits max revisions). Assembled from Admin-API config (disabled review agents skipped; models config-driven). **Verified live**: detectors → validated/deduped/scored/critiqued findings + 3 narrative reports, all persisted. Portfolio runs reuse this pipeline (deterministic stages + reporters) over the cross-project aggregate.
- **`Airflow/dags/` — 8 DAGs** (pure fake-client-testable task logic; 88 tests). `project_dataset_acquire` = **real Zenodo download + md5**; `project_dataset_ingest` = **real, batched, resumable Mongo ingestion** (extract → discover → dynamic-mapped per-entity loaders → checkpoints); `project_metrics_compute` = fan-out recompute of metrics via Projects-API; `_validate`/`_index`/`_reconcile` call Ingestion-API ops; `project_risk_schedule` (daily) / `portfolio_risk_schedule` (weekly) → RiskAnalytics-API. Only `acquire`+`ingest` write data; the rest are HTTP-only. Run Airflow: `WITH_AIRFLOW=1 bash CICD/LocalDev/docker-all-up.sh`.
- **`Portals/` — two Angular 20 apps** (`ng build` + unit tests pass). `Project-Tracker` (:4201): projects list over Projects-API **plus a Project Risk view** that runs an analysis (optionally with the review pipeline) over RiskAnalytics-API and renders findings + the generated reports. `Admin` (:4200): agent config + framework toggle + audit + system health, **plus a Data Management → Initial Dataset page** to trigger + monitor the dataset **download and batch ingestion** (live per-entity progress) — over Admin-API. Each: `npm start` = `ng serve`, multi-stage Dockerfile; started via `portals.sh`.
- `Database/PostgreSQL/` migrations `V001`–`V007` (ingestion runs; admin config+audit seeding 16 agents; risk runs+findings; findings `meta`+`risk.reports`; `ingestion.operations`; `ingestion.datasets`; `ingestion_batches`+`ingestion_log`) + `apply_migrations.py` (idempotent, pg8000); `Database/MongoDB/` init + indexes + local-dev `seed/`.
- `OpenAPI/{ingestion,projects,admin,risk-analytics}-api.yaml` generated from the services.

**Initial Dataset download** (Admin portal → **Data Management → Initial Dataset**): the button calls Admin-API `POST /api/v1/admin/dataset/download`, which proxies to Ingestion-API `POST /api/v1/ingestion/datasets/{id}/acquire`, which **triggers the Airflow `project_dataset_acquire` DAG via Airflow's REST API**. The DAG streams the real 5.8 GB Jira dataset from Zenodo to `DATASET_DATA_DIR`, verifies md5 (idempotent skip if already present), and reports `DOWNLOADING → DOWNLOADED` back to `ingestion.datasets` (V006, seeded with the Zenodo record + checksum). Requires Airflow running (`WITH_AIRFLOW=1`); the portal polls status. Download logic + real URL connectivity are verified; the full 5.8 GB pull happens when the button is clicked.

**Batch ingestion into Mongo** (Admin portal → Data Management → Initial Dataset → **"Ingest into evidence store"**, enabled once `DOWNLOADED`): Admin-API `POST /admin/dataset/ingest` → Ingestion-API creates a run + **triggers the Airflow `project_dataset_ingest` DAG**. The DAG extracts the archive, discovers per-entity JSON-lines files, and **dynamic-maps one loader per entity** (parallel): streams **bounded batches**, **idempotent-upserts** into Mongo, **skips already-committed batches to resume**, and reports a checkpoint + progress per batch through the governed Ingestion-API boundary (`ingestion_batches`/`ingestion_log`, V007). The whole dataset is never held in memory. The UI polls aggregated progress (`GET /admin/dataset/ingestion`: per-entity records-done/total + log). Evidence writes go straight to Mongo (throughput); status stays governed. Verified live on a bounded sample (extract→discover→batch upsert + idempotency + checkpoint/resume/aggregation); the full 2.7 M runs when clicked. **Note:** the record-file format is assumed JSON-lines with the entity = file stem; `tasks.discover_entities`/`natural_key` may need tuning once the real archive's internal layout is known.

**End-to-end data path is complete:** download (Zenodo) → batch-ingest records into Mongo → **compute deterministic metrics** → agents analyze real evidence. The seed evidence (`Database/MongoDB/seed/002_sample_evidence.js`) exercises this before the real 5.8 GB archive is loaded.

Functionally complete against the README vision. Intentionally deferred (add incrementally): the other alternative-framework adapters (`strands`/`google_adk`/`ms_agent_framework` for detectors; framework variants for review agents — **CrewAI now installs on Python 3.12** and can be added); wiring `project_metrics_compute` to auto-run after ingestion completes; more metric facts (issue aging, resolution velocity, contributor concentration, critical-defect trends — the engine covers the four the agents consume today); and richer `docs/` content. **Metric computation assumes the ingested schema** (issues/histories/links field names in `daos/metrics_computation`) — tune once the real archive layout is known.

### Running an analysis locally (needs the LLM)
`ANTHROPIC_API_KEY` must be in the environment (the model SDK reads it; it is never stored/committed). The `api-services.sh` launcher inherits the shell env. Flow: containers up → `npm run local:db:migrate` (V001–V007) → seed Mongo → `local:api-services:start-all` → `POST /api/v1/analysis/projects/APACHE` (add `{"include_review": true}` for the full pipeline + reports; or `POST /api/v1/analysis/portfolios/{key}` for cross-project). The per-agent model/framework comes from `admin.agent_configs` (set via Admin-API `PUT /api/v1/admin/agents/{key}`).

**Key environment facts:** **Python 3.12** (standardized: matches the service Dockerfiles and supports every agentic framework we target — LangGraph, CrewAI, OpenAI Agents, etc.; `api-services.sh` creates venvs with `python3.12`). Node 20. Docker infra reuses local images `postgres:16`, `mongo:7`, `chromadb/chroma:latest`, `apache/airflow:2.10.0-python3.12`. **Port map** (ChromaDB owns :8000, so APIs start at 8001): Postgres 5432 · Mongo 27017 · Chroma 8000 · Airflow 8080 · Ingestion 8001 · Admin 8002 · Projects 8003 · RiskAnalytics 8004 · Portals 4200/4201. **DB driver is pg8000** (pure-Python, no libpq); DAOs depend only on the DB-API surface so swapping to psycopg later is confined to `daos/connection.py`.

## Repository Layout (planned monorepo)

Top-level directories, each a distinct deliverable:

- `CICD/LocalDev/` — `docker-compose.yaml` per infra service (MongoDB, PostgreSQL, Airflow, ChromaDB) plus `docker-all-up.sh` / `docker-all-down.sh` / `status.sh`. Reuse existing local Docker images where noted.
- `Airflow/` — `dags/` for operational + scheduled-analysis workflows (`project_dataset_acquire|ingest|validate|index|reconcile`, `project_risk_schedule`, `portfolio_risk_schedule`), plus `plugins/`, `config/`, `tests/`.
- `Middleware/` — **four independent FastAPI microservices**, each on its own port: `Ingestion-API`, `Admin-API`, `Projects-API`, `RiskAnalytics-API` (see per-service structure below).
- `Agents/` — the 16 LangGraph specialist agents as standalone packages (`project_risk_manager`, `schedule_risk`, `quality_risk`, `critic`, `executive_reporting`, …), kept **separate** from the middleware services that invoke them.
- `Portals/` — two Angular apps: `Admin/` and `Project-Tracker/`.
- `Database/` — `PostgreSQL/` (`changelogs/`, `migrations/`, `seed/`) and `MongoDB/` (`indexes/`, `initialization/`, `validation/`).
- `OpenAPI/` — the four API contracts (`ingestion-api.yaml`, `admin-api.yaml`, `projects-api.yaml`, `risk-analytics-api.yaml`), the source of truth from which UI clients are generated.
- `docs/`, `tests/` (repo-wide `end_to_end/`, `performance/`, `resilience/`, `fixtures/`).

### Per-microservice structure (consistent across all four)

Each service (`Middleware/<Name>-API/<name>_api/`) uses the same internal shape, which mirrors the layering rule below:

- `api/` — `routers/`, `dependencies/`, `exception_handlers/`, `main.py` (HTTP surface only)
- `interfaces/` — abstract `facades/` / `services/` / `daos/` contracts; the concrete `facades/`, `services/`, `daos/` implement them
- `facades/` — one directory per use case (e.g. `start_ingestion/`, `get_risk_findings/`)
- `services/` — reusable domain capabilities; `daos/` — DB access, including **gateway DAOs** (`airflow_gateway/`, `graph_run_gateway/`) that wrap calls to Airflow and LangGraph runs
- `dtos/` — `requests/` / `responses/` / `common/` (the typed cross-layer objects; note the repo term is **dtos**, not "models")
- `common/` — configuration, exceptions, logging, models, security, utilities
- `tests/` — `unit/` / `integration/` / `contract/`

`RiskAnalytics-API` additionally has a `graphs/` package (`project_risk_manager/`, `portfolio_risk_orchestrator/`, `evidence_retrieval/`, `risk_review/`) and a `tests/graph_paths/` suite — this is where LangGraph orchestration lives.

## Commands

Root `package.json` is the developer entry point (a task runner, not a JS app). Each group has `start-all` / `stop-all` / `status-all`:

```bash
npm run local:containers:start-all   # infra up (reuses running Mongo/Chroma, starts Postgres; Airflow skipped unless WITH_AIRFLOW=1)
npm run local:db:migrate             # apply Postgres migrations (idempotent)
npm run local:api-services:start-all # per-service .venv + pip install + uvicorn on each port; PIDs/logs in CICD/LocalDev/.run/
npm run local:portals:start-all      # each portal npm install + ng serve (once portals scaffolded)
npm run local:api-portals:start-all  # services + portals
```

- The `api-services`/`portals` start scripts **auto-install deps on every start** (per-service `.venv` / `npm install`) — developers never install manually after adding a dependency.
- Bring up Airflow explicitly: `WITH_AIRFLOW=1 bash CICD/LocalDev/docker-all-up.sh`.
- Add a new microservice to the run loop by uncommenting its line in `CICD/LocalDev/api-services.sh` (`SERVICES` array).

Per-service dev loop (reference = Ingestion-API):
```bash
cd Middleware/Ingestion-API
python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
./.venv/bin/pytest                                   # unit + contract, no infra (fakes injected)
./.venv/bin/pytest tests/unit/test_ingestion_orchestration.py::test_get_run_missing_raises_not_found  # single test
./.venv/bin/uvicorn ingestion_api.api.main:app --port 8001 --reload
```
Regenerate a service's OpenAPI contract with the one-liner in `OpenAPI/README.md`.

## What This Project Is

Enterprise Project Intelligence OS is a multi-agent platform that analyzes a large public issue-tracking dataset (1,822 projects, ~2.7M issues, ~32M historical changes) to detect delivery risks, ground each finding in project evidence, and surface risks/mitigations through admin and project-tracking UIs.

## Planned Architecture

The system is a pipeline of distinct runtimes, not a monolith. Understanding the boundaries between them is the key to working here:

```
Public dataset → Airflow batch ingestion → Evidence store (MongoDB) + Operational state (PostgreSQL)
              → FastAPI governed middleware → LangGraph multi-agent risk workflows → Angular UIs
```

- **Apache Airflow** owns *operational* work: dataset acquisition, restartable/checkpointed batch ingestion, index creation, count reconciliation, and scheduled analysis runs. Airflow triggers risk analysis **only through the FastAPI boundary** — agent prompts and reasoning logic must **not** live inside Airflow DAGs.
- **FastAPI middleware** is the single governed boundary between UIs, workflows, databases, and LangGraph. UIs and Airflow never touch MongoDB/PostgreSQL/LangGraph directly.
- **LangGraph** owns *reasoning*: multi-agent state, conditional routing, parallel specialist execution, evidence validation, risk correlation/deduplication, scoring, critic/revision loops, mitigation, and report generation. A central **Project Risk Manager** coordinates ~15 specialist agents (schedule, quality, dependency, resource, backlog, forecasting, scoring, evidence-validation, correlation, dedup, mitigation, critic, reporting).
- **Angular** provides two separate experiences: Administration (ingestion/config/monitoring) and Project Tracking (dashboards/risk register/reports).

### Agent & LLM stack decisions

Decisions taken for the agent/reasoning layer (apply when the risk-analytics phase starts):

- **Framework split (three tiers).** Deterministic metric computation = **plain Python, no framework** (preserves the evidence-grounding invariant). A single LLM reasoning step = a **LangChain** runnable (`langchain-anthropic`). Coordinating the 16 agents = **LangGraph** graphs in `RiskAnalytics-API/graphs/` + `Agents/`. LangGraph is built on LangChain primitives, so `langchain-core`/`langchain-anthropic` are expected deps — but orchestration is LangGraph. Reasoning logic never lives in Airflow DAGs.
- **Default models:** Claude — `claude-opus-4-8` / `claude-sonnet-5` (`AGENT_MODEL` in `.env.example`).
- **Framework-agnostic agents (port + adapters).** Each agent in `Agents/<agent>/` has a framework-free typed **port** (`contract.py`: `EvidencePackage → RiskFinding[]`), shared `prompts/` and `tools/`, and pluggable `adapters/` (langgraph default; crewai, openai_agents, strands, google_adk, ms_agent_framework as alternatives). A `registry.py` selects the adapter from an **Admin-API `framework` config field** (`AGENT_FRAMEWORK` default `langgraph`), per-agent and per-run overridable. Constant across adapters: contract + prompts + tools + deterministic sub-steps; only orchestration differs. **Model choice is independent of framework choice** — route every adapter to Claude so comparisons measure orchestration, not models. Build order: LangGraph fully first + clean port, then ONE alternative adapter to prove the seam; others are documented stubs (6 adapters × 16 agents is a large surface). See `Agents/README.md`.
- **Tracing/observability:** README requires OpenTelemetry-compatible tracing. Planned: **LangFuse** as the self-hosted backend (slots into `CICD/LocalDev/` compose), optionally **LangSmith** in dev for LangGraph step debugging. Keep tracing behind config so agents are unaware of the backend. Not yet added.
- **ChromaDB collection naming (avoid cross-framework/embedding overlap).** A collection is bound to its embedding model's vector space — mixing embedding models in one collection corrupts search. Convention: `epi_<domain>_<framework>_<embedmodel>_v<n>`. **Shared evidence** embeddings namespace by **embedding model, not framework** (`epi_evidence_<embedmodel>_v1`) so all frameworks reuse one copy (don't re-embed 2.7M issues per framework); only genuinely framework-owned data (agent memory/scratchpads) namespaces by framework. Framework acronyms: `lg`/`ca`/`oai`/`str`/`adk`/`maf`.

### Data ownership (do not blur these)

- **MongoDB** = authoritative *evidence* store: projects, issues, histories, comments, links, anonymized users, computed metrics.
- **PostgreSQL** = *operational* state: dataset definitions, ingestion runs/batches/checkpoints/failures, reconciliation results, analysis requests, agent-run metadata, schedules, config, audit records.
- **ChromaDB** = vector store (runs as local infra alongside Mongo/Postgres/Airflow). Used for embedding/semantic retrieval in evidence workflows.
- Operational workflow metadata stays isolated from application data.

### Evidence-grounding invariant

Raw records are **never** sent to the LLM. Deterministic code computes observable facts (backlog growth, issue aging, resolution velocity, reopen rate, blocker count, dependency depth, contributor concentration, defect trends) into **bounded evidence packages**; agents interpret those packages. The full dataset is never loaded into memory at once — ingestion is batched, checkpointed, idempotent, and resumable.

### Middleware layering convention

Each FastAPI service follows a strict layered flow, and this is a hard rule for any new endpoint:

```
API Endpoint → Use-Case Facade → Business Service → Data Access Object → Database
```

- Endpoints handle HTTP + typed request validation only.
- Facades implement complete use cases; Services implement reusable domain rules; DAOs encapsulate DB access.
- **Cross-layer communication uses typed request/response objects — never untyped dicts.** Public facade/service/DAO methods take one request object and return one response object. Database entities are never exposed directly through API responses.
- Every API is versioned with an OpenAPI spec + Swagger UI, stable operation IDs, standard error/pagination contracts, and liveness/readiness endpoints. UI API clients are generated/validated from the OpenAPI contracts — do not hand-duplicate contracts.

## Dataset

Public MSR issue-tracking dataset (Montgomery, Lüders, Maalej — https://zenodo.org/records/15719919), ~5.8 GB compressed. **Not** included in the repo; it is acquired at runtime through the ingestion workflow and remains under its own license.

## Licensing Constraint

Copyright © 2026 Dr. Kishore Veleti, all rights reserved. The repo is provided for viewing/evaluation only — this affects how code may be reused or redistributed, but does not restrict development work within this repository.
