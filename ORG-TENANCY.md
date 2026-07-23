# Organization & Multi-Tenancy Design

Locked design (2026-07-23) for org management + multi-tenancy. Isolation model chosen: **shared schema + row scoping** — one schema; every operational + evidence record carries `root_org_id` (tenant boundary) and `org_id`; scoping enforced centrally at the DAO/query boundary. Scales to thousands of tenants, one migration path, cross-tree sharing via grants. Complements `ENTERPRISE-SCALE-ARCHITECTURE.md` (which already put `org_id` on every record).

## New service: `Org-Management-API` (port 8005)
Same FastAPI layering (Endpoint→Facade→Service→DAO, typed DTOs). **Owns the tenancy schema + migrations.** CRUD + resolution over four domains.

## Domain model (Postgres)
- **organizations**(`org_id` uuid PK, `parent_org_id` null, `root_org_id`, `path` (materialized path, portable — no ltree extension), `depth`, `name`, `kind`, `status`, timestamps). Arbitrary depth: main → branch → sub → sub-sub → … A different `root_org_id` = a totally separate tree/tenant. Subtree/ancestor queries via `path` prefix.
- **users**(`user_id`, `subject`/email — global identity → SSO subject) + **memberships**(`user_id`, `org_id`) — a user in many orgs/branches.
- **role_assignments**(`user_id`, `org_id`, `role`, `inherits_down` bool) — MANY roles per user per org; a role may inherit down the subtree or be branch-scoped.
- **repositories**(`repo_id`, `org_id`, `provider` ∈ {jira, github, azure_devops, …}, `external_account`, `connection_config` jsonb, `visibility_scope`, timestamps) — a connected tracker account, provider-agnostic.
- **tracker_projects**(`tracker_project_id`, `repo_id`, `external_key`, `name`) — Jira projects / GitHub repos / ADO projects. The existing evidence `projects` map here (each becomes a tracker_project under a repo under an org).
- **repository_grants**(`repo_id`, `grantee_org_id`, `direction`) — explicit cross-tree / cross-tenant sharing.

### Repository visibility / cascade (`visibility_scope`)
- `org` — owning org only
- `subtree` — owning org + all descendants (cascade DOWN)
- `ancestors` — owning org + all ancestors (cascade UP)
- `tenant` — every org under the same `root_org_id` (cross-branch)
- `shared` — explicit `repository_grants` to another org / different tree (cross-tenant)

**Effective access** for a user = union of `tracker_projects` from repos their orgs OWN or that are VISIBLE to those orgs via scope + grants. Computed by this service; the other services call it to scope evidence/queries. Replaces today's flat `project_assignments` / `X-User-Key` with org-aware scoping.

## Phasing
- **Phase 1 (foundation):** Org-Management-API — schema/migrations, CRUD (orgs tree incl. create-subbranch/move/list ancestors+descendants; users/memberships/roles; repositories/tracker_projects/grants), and the **effective-access resolution** endpoint. Seed a demo org tree. Hermetic tests.
- **Phase 2 (scoping integration):** thread `root_org_id`/`org_id` through Projects/RiskAnalytics evidence + queries; gate project visibility via Phase 1's effective-access. Invasive (every service).
- **Phase 3 (UI):** org switcher + org admin (tree / employees / roles / repositories / visibility) in the Admin portal.
