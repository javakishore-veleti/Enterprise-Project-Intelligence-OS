# Risk Analytics API

Multi-agent risk analysis for Enterprise Project Intelligence OS. Runs on
**port 8004**. This is where the platform's core value lives: it turns bounded,
deterministic evidence into validated, agent-generated risk findings.

## Flow (one analysis run)

```
POST /api/v1/analysis/projects/{key}
  1. Evidence retrieval  — deterministic package from MongoDB (no LLM, no raw records)
  2. Agent config        — read enabled/model/framework from admin.agent_configs (Admin-API)
  3. Framework toggle     — build the agent via its registry (langgraph default)
  4. Agent reasoning      — LangGraph graph -> Claude (langchain-anthropic) -> typed RiskFinding[]
  5. Persist             — risk.graph_runs + risk.risk_findings (PostgreSQL)
GET  /api/v1/analysis/runs/{run_id}    — read a run, its findings, and reports
POST /api/v1/analysis/portfolios/{key} — cross-project analysis + portfolio reports
```

With `include_review: true`, the review pipeline runs after detection:
`validate → dedup → correlate → score → [critic loop] → report`, producing
refined findings (annotated in `meta`) and mitigation/project/executive reports.
The critic is a bounded revision loop (re-runs until it converges or hits its
max). Which review agents run — and their model — comes from Admin-API config.
Portfolio runs analyze each project (detection) then synthesize the aggregate
(cross-project dedup/correlation/scoring + reports).

Specialist agents live in the repo `Agents/` package (`epi-agents`), behind a
framework-agnostic port. This service depends on it (see `local-deps.txt`); only
`schedule_risk` is implemented so far.

## Run locally

Requires `ANTHROPIC_API_KEY` in the environment (read by the model SDK; never
stored by this service). MongoDB must have project evidence (see
`Database/MongoDB/seed/`), and Postgres must be migrated through V003.

```bash
export ANTHROPIC_API_KEY=...           # in your shell / .env, not committed
npm run local:containers:start-all
npm run local:db:migrate               # V001..V003
mongosh "mongodb://localhost:27017/epi_os" Database/MongoDB/seed/001_sample_projects.js
npm run local:api-services:start-all   # installs Agents (editable) then this service

curl -X POST localhost:8004/api/v1/analysis/projects/APACHE -H 'content-type: application/json' -d '{}'
```

## Test

```bash
pip install -e ../../Agents && pip install -e ".[dev]"
pytest        # unit (fake agent, no LLM) + contract (fake facade). Live LLM is not exercised in tests.
```

## Configuration

`RISK_ANALYTICS_API_PORT`, `PG_*`, `MONGO_URI`, `MONGO_DATABASE`, `AGENT_MODEL`,
`AGENT_FRAMEWORK`, `LOG_LEVEL`, and `ANTHROPIC_API_KEY` (environment only).
