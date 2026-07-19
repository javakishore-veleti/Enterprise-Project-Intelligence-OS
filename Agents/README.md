# Agents

The 16 specialist agents coordinated by the Project Risk Manager. This tree is
kept **separate** from the middleware services that invoke it (agent/reasoning
logic never lives in Airflow DAGs or in operational workflows).

## Framework-agnostic port + adapters (planned)

Each agent is designed around one framework-agnostic **port** with pluggable
**adapters**, so the same contract + prompts + tools can execute under different
agent frameworks (a deliberate showcase of orchestration styles):

```
Agents/<agent>/
  contract.py            # PORT: (EvidencePackage) -> RiskFinding[]  (typed, framework-free)
  prompts/               # shared prompts (reused by every adapter)
  tools/                 # shared tool defs (evidence retrieval, scoring) — plain Python
  adapters/
    langgraph_adapter.py         # default
    crewai_adapter.py
    openai_agents_adapter.py
    strands_adapter.py
    google_adk_adapter.py
    ms_agent_framework_adapter.py
  registry.py            # selects adapter from the feature toggle
```

**Toggle:** the active framework is configuration, resolved per-agent (and
per-run overridable) via **Admin-API** agent configuration — extend its
existing agent/model/prompt config with a `framework` field. Values:
`langgraph | crewai | openai_agents | strands | google_adk | ms_agent_framework`.

**Constant across adapters:** the typed I/O contract, prompts, tool definitions,
and all deterministic sub-steps. Only the *orchestration* differs per adapter.

**Model independence:** framework choice is independent of model choice — route
every adapter to Claude (`claude-opus-4-8` / `claude-sonnet-5`) via that SDK's
model-provider abstraction, so comparisons measure orchestration, not models.

**Build order:** implement LangGraph fully first, define the port cleanly, then
add ONE alternative adapter to prove the seam. The rest are documented stubs
until needed — six adapters × 16 agents is a large surface to maintain.

## Status / package layout

This is an installable package (`epi-agents`); the flat packages under `Agents/`
are the import roots:

- `agent_core/` — the framework-free port: `EvidencePackage`, `RiskFinding`,
  `RiskAgent` ABC, and the `RiskCategory`/`Severity` enums.
- `schedule_risk/` — **implemented** (the first agent). `contract.py` (port),
  `prompts/`, `tools/` (deterministic scoring), `adapters/langgraph_adapter.py`
  (real LangGraph + `langchain-anthropic`), `adapters/other_frameworks.py`
  (stubs that raise until built), `registry.py` (`build_agent(framework, model)`).

`RiskAnalytics-API` consumes this package (installed via its `local-deps.txt`)
and maps agent keys to builders in `graphs/project_risk_manager`. The remaining
15 agents are not built yet.
