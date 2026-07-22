# Enterprise-Scale Architecture

How the platform serves **thousands of projects, millions of issues, and many concurrent users across multiple organizations** — without ever scanning the world on a page load.

## Scale targets (design envelope)

| Dimension | Target |
|---|---|
| Organizations (tenants) | 100s |
| Projects per org | up to ~10,000 |
| Issues (evidence) | 10M+ |
| Concurrent users | 1,000s |
| Home ("Mission") load | < 300 ms P95, scoped to the user |
| Portfolio recompute | event-driven, not on read |

## The golden rule: precompute, materialize, read cheap

A user's Mission must **never** trigger a scan/rank of their 3,000 projects. Instead:

```
INGEST (Airflow, batched)              ── writes evidence
   → METRICS (deterministic, no LLM)   ── precomputed per project  → project_metrics
   → RISK ANALYSIS (agents)            ── precomputed findings      → risk.*
   → MATERIALIZED ROLLUPS              ── precomputed, sorted       → project_risk_scores, portfolio_rollup
```

Every heavy computation happens **once, on a data-change event**, and is **stored sorted**. The read path is O(top-N), not O(projects).

- **`project_risk_scores`** — one row per project: `{ org_id, project_key, risk_score (0–100), risk_band, headline, signals, computed_at }`. Written when that project's metrics/analysis change. Indexed `(org_id, risk_score desc)`.
- **`portfolio_rollup`** — precomputed per **scope** (org, team, or user): `{ scope_key, portfolio_score, bands{high,med,low}, totals, top_project_keys[15], computed_at }`. The Mission read is a **single document fetch**.

Reads serve materialized data; the truth is refreshed asynchronously behind an event. Every materialized doc carries `computed_at` so the UI can show freshness ("as of 2m ago").

## Multi-tenancy & identity

- **`org_id` on every record** (tenant partition key). All queries are org-scoped; no cross-tenant leakage. Shard/partition by `org_id` when a single collection outgrows a node.
- **Users & RBAC.** `users(user_key, org_id, role)` + **`project_assignments(org_id, user_key, project_key, role∈{owner,manager,member})`**. Indexed `(org_id, user_key)` and `(org_id, project_key)`.
- **Per-user scoping is the default, not a filter.** The Mission for user X = the `portfolio_rollup` for X's assignment set. A manager of 40 projects and a director over 3,000 get different, precomputed rollups. Identity today flows via an `X-User-Key` header (the governed seam); tomorrow it's the JWT/SSO subject — **the scoping logic is unchanged**.
- **Scope resolution** is itself materialized: when assignments change, the affected users' `portfolio_rollup` is invalidated and recomputed off the already-sorted `project_risk_scores` (cheap: filter + top-15).

## Read path (Mission / portfolio summary)

1. Resolve caller → `org_id`, `user_key` (auth).
2. Fetch the caller's `portfolio_rollup` doc (1 indexed read). Cache in Redis/edge with a short TTL + event invalidation.
3. Return: portfolio score, band distribution, totals, and the **top-15** hydrated project cards (from `project_risk_scores`).
4. "View more" / Investigate paginates the sorted `project_risk_scores` by **cursor** (`risk_score, project_key`) — never offset scans, never all-in-memory.

Cost is independent of portfolio size. 40 projects or 30,000 — the browser gets one rollup + 15 cards.

## Write / refresh path (event-driven)

- Ingestion → metrics → analysis already run in **Airflow** (batched, checkpointed, idempotent). Completion emits a change event per affected project.
- A **rollup worker** consumes those events and updates `project_risk_scores` (that project) and the impacted `portfolio_rollup` scopes. Debounced/coalesced so a burst of updates yields one recompute.
- Backpressure via the queue; recompute is incremental (only touched scopes), so cost scales with *change rate*, not corpus size.
- Staleness SLA surfaced via `computed_at`; a manual "Recompute" is available but never required for a fast read.

## Horizontal scale & isolation

- **Stateless services** (the 4 FastAPI apps) behind the governed boundary → scale out horizontally; no session affinity.
- **Connection pooling** to Mongo/Postgres; **read replicas** for the read-heavy Mission/Investigate paths; writes to primary.
- **Indexes** are the contract: `project_assignments(org_id,user_key)`, `project_risk_scores(org_id,risk_score desc)`, `project_metrics(project_key)`, evidence collections by `(project_key, …)`.
- **Per-tenant limits & rate limiting** at the gateway; noisy-neighbor isolation; per-org quotas on analysis runs (LLM cost).
- **Caching tiers**: rollup docs (Redis, TTL + invalidation), and the expensive LLM narratives cached per run (never regenerated on read).

## Cost & correctness guards at scale

- **LLM spend is bounded**: agents run on a schedule / on-demand, per-org quota'd; the **evidence-grounding invariant** means deterministic metrics (cheap) do the heavy lifting and the LLM only interprets bounded packages — never 10M issues.
- **Idempotent, resumable** pipeline (already built) so a 10M-issue ingest survives restarts.
- **Observability**: tracing (LangSmith today), per-stage metrics, and freshness/lag dashboards on the rollup worker.

## Where the current build sits vs. this design

| Layer | Today | To reach the envelope |
|---|---|---|
| Evidence ingest | ✅ batched, checkpointed, resumable (Airflow) | shard evidence by org |
| Metrics (precomputed) | ✅ `project_metrics`, event-triggered | — |
| Risk findings (precomputed) | ✅ `risk.*` | — |
| **Materialized risk scores** | 🟡 request-time ranking (fine ≤ low-100s) | **`project_risk_scores` + rollup worker** |
| **Per-user scoping** | 🔲 add `project_assignments` + `X-User-Key` | JWT/SSO subject |
| **`portfolio_rollup`** | 🔲 | precompute per scope, cache |
| Multi-org (`org_id`) | 🔲 single-tenant today | add tenant partition key |
| Caching / read replicas | 🔲 | Redis + replicas |

**Honest status:** the *pipeline* (the hard part) is already precompute-first and event-driven. The remaining work to hit the envelope is (1) the `project_risk_scores` + `portfolio_rollup` materialized views, (2) the `project_assignments` scoping + identity seam, and (3) the `org_id` tenant key. These are additive to the existing governed layering — no rewrite.

## Immediate implementation order

1. `project_assignments` + `X-User-Key` scoping (identity seam).
2. `GET /portfolio-summary` reads a **materialized** per-user rollup (precomputed by the metrics/analysis completion hook), returns **portfolio score + bands + top-15**.
3. Rollup refresh hook on metrics/analysis completion (event-driven), with `computed_at` freshness.
4. Cursor pagination for Investigate; `org_id` threaded through (single tenant seeded now).
