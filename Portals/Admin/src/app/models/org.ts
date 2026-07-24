/**
 * Typed views of the Org-Management-API contract (Middleware/Org-Management-API,
 * on :8005). These mirror the request/response DTOs exposed by that service and
 * back the Organizations admin area. The middleware is the single governed
 * boundary; this portal never touches PostgreSQL directly.
 */

/** Supported tracker providers (Provider enum). */
export type Provider = 'jira' | 'github' | 'azure_devops';

/** The three providers, in contract order — used to populate dropdowns. */
export const PROVIDERS: Provider[] = ['jira', 'github', 'azure_devops'];

/** Human labels for the providers. */
export const PROVIDER_LABELS: Record<Provider, string> = {
  jira: 'Jira',
  github: 'GitHub',
  azure_devops: 'Azure DevOps',
};

/** How far a repository's tracker projects are visible (VisibilityScope enum). */
export type VisibilityScope = 'org' | 'subtree' | 'ancestors' | 'tenant' | 'shared';

/** The five visibility scopes, in contract order. */
export const VISIBILITY_SCOPES: VisibilityScope[] = [
  'org',
  'subtree',
  'ancestors',
  'tenant',
  'shared',
];

/** Short human descriptions of each visibility scope (shown as helper text). */
export const VISIBILITY_HINTS: Record<VisibilityScope, string> = {
  org: 'Owning org only',
  subtree: 'Owning org + all descendants (cascade down)',
  ancestors: 'Owning org + all ancestors (cascade up)',
  tenant: 'Every org under the same root',
  shared: 'Explicit grants to another org / tree',
};

/** How a `shared` grant cascades to the grantee side (GrantDirection enum). */
export type GrantDirection = 'org' | 'subtree';

/** The two grant directions, in contract order. */
export const GRANT_DIRECTIONS: GrantDirection[] = ['org', 'subtree'];

/** Common role names offered in the add-member multi-select (roles are free text). */
export const ROLE_OPTIONS: string[] = [
  'owner',
  'admin',
  'manager',
  'member',
  'contributor',
  'viewer',
];

// --- Organizations ----------------------------------------------------------

/** Public view of an organization node (materialized-path tree). */
export interface Organization {
  org_id: string;
  parent_org_id: string | null;
  root_org_id: string;
  path: string;
  depth: number; // 0-indexed (root = 0)
  level: number; // 1-indexed (root = 1 = depth + 1)
  name: string;
  kind: string | null;
  status: string;
  created_at: string;
  /** Number of DIRECT children (cheap COUNT) — drives the expand chevron. */
  child_count?: number;
  /** Number of direct memberships in this org. */
  member_count?: number;
}

export interface OrganizationListResponse {
  organizations: Organization[];
  /** Paging envelope — present on the paginated reads (children, search). */
  total?: number;
  returned?: number;
  offset?: number;
  limit?: number;
}

/**
 * Cheap tenancy aggregate counts (`GET /orgs/stats`) — computed with COUNT
 * queries, never a subtree fetch. Powers the dashboard org summary.
 */
export interface OrgStats {
  total_orgs: number;
  root_count: number;
  total_members: number;
  total_repositories: number;
}

/** Whitelisted sort keys for the direct-children page (mirrors the API). */
export type OrgChildSort = 'name' | 'created_at' | 'child_count';

/** Query options for the paginated + filterable direct-children list. */
export interface OrgChildrenQuery {
  q?: string;
  sort?: OrgChildSort;
  limit?: number;
  offset?: number;
}

export interface CreateOrganizationRequest {
  name: string;
  parent_org_id?: string | null;
  kind?: string | null;
}

export interface UpdateOrganizationRequest {
  name?: string | null;
  kind?: string | null;
}

export interface MoveOrganizationRequest {
  new_parent_org_id: string;
}

// --- Users / membership / roles ---------------------------------------------

export interface RoleView {
  role: string;
  inherits_down: boolean;
}

/** A role that applies to a member via an ancestor org (inherited down). */
export interface InheritedRoleView {
  role: string;
  source_org_id: string;
  source_org_name: string;
  source_org_level: number;
}

export interface Member {
  user_id: string;
  subject: string;
  email: string | null;
  display_name: string | null;
  /** Direct role_assignments in this org (== direct_roles; kept for compat). */
  roles: RoleView[];
  direct_roles?: RoleView[];
  /** Roles inherited from an ancestor org, each with its source org. */
  inherited_roles?: InheritedRoleView[];
}

export interface MembersResponse {
  org_id: string;
  members: Member[];
  /** Paging envelope — present on the paginated members list. */
  total?: number;
  returned?: number;
  offset?: number;
  limit?: number;
}

/** Query options for the paginated members list. */
export interface MemberQuery {
  q?: string;
  role?: string;
  limit?: number;
  offset?: number;
}

export interface AddMemberRequest {
  subject: string;
  roles: string[];
  inherits_down: boolean;
  email?: string | null;
  display_name?: string | null;
}

/** Distinct role names for the searchable role picker (`GET /roles`). */
export interface RolesResponse {
  /** Capped, ordered distinct role names matching the query. */
  roles: string[];
  /** Total number of distinct roles matching (may exceed `roles.length`). */
  total: number;
}

// --- Repositories / tracker projects / grants -------------------------------

export interface Repository {
  repo_id: string;
  org_id: string;
  root_org_id: string;
  provider: string;
  external_account: string | null;
  connection_config: Record<string, unknown>;
  visibility_scope: string;
  created_at: string;
}

export interface RepositoriesResponse {
  org_id: string;
  repositories: Repository[];
  /** Paging envelope — present on the paginated list. */
  total?: number;
  returned?: number;
  offset?: number;
  limit?: number;
}

/** Query options for the paginated + searchable repositories list. */
export interface RepositoryQuery {
  q?: string;
  limit?: number;
  offset?: number;
}

export interface CreateRepositoryRequest {
  provider: Provider;
  external_account?: string | null;
  visibility_scope: VisibilityScope;
  connection_config?: Record<string, unknown>;
}

export interface TrackerProject {
  tracker_project_id: string;
  repo_id: string;
  external_key: string;
  name: string | null;
}

export interface TrackerProjectsResponse {
  repo_id: string;
  projects: TrackerProject[];
  /** Paging envelope — present on the paginated LIST endpoint. */
  total?: number;
  returned?: number;
  offset?: number;
  limit?: number;
}

/** Query options for the paginated + searchable tracker-projects list. */
export interface TrackerProjectQuery {
  q?: string;
  limit?: number;
  offset?: number;
}

export interface TrackerProjectInput {
  external_key: string;
  name?: string | null;
}

export interface AddTrackerProjectsRequest {
  projects: TrackerProjectInput[];
}

export interface UpdateVisibilityRequest {
  visibility_scope: VisibilityScope;
}

export interface Grant {
  repo_id: string;
  grantee_org_id: string;
  direction: string;
}

export interface AddGrantRequest {
  grantee_org_id: string;
  direction: GrantDirection;
}

/** A page of cross-org sharing grants on a repo (`GET /repositories/{id}/grants`). */
export interface GrantsResponse {
  repo_id: string;
  grants: Grant[];
  total?: number;
  returned?: number;
  offset?: number;
  limit?: number;
}

// --- Effective access resolution --------------------------------------------

export interface VisibleProject {
  external_key: string;
  name: string | null;
  repo_id: string;
  org_id: string;
  provider: string;
}

export interface VisibleProjectsResponse {
  subject: string;
  projects: VisibleProject[];
  /** Paging envelope — present when the caller pages/searches. */
  total?: number;
  returned?: number;
  offset?: number;
  limit?: number;
}

/** Query options for the paginated + searchable effective-access list. */
export interface VisibleProjectQuery {
  q?: string;
  limit?: number;
  offset?: number;
}
