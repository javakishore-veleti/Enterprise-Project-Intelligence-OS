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
}

export interface OrganizationListResponse {
  organizations: Organization[];
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

export interface Member {
  user_id: string;
  subject: string;
  email: string | null;
  display_name: string | null;
  roles: RoleView[];
}

export interface MembersResponse {
  org_id: string;
  members: Member[];
}

export interface AddMemberRequest {
  subject: string;
  roles: string[];
  inherits_down: boolean;
  email?: string | null;
  display_name?: string | null;
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
}
