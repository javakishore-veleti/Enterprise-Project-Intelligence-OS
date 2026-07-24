import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  AddGrantRequest,
  AddMemberRequest,
  AddTrackerProjectsRequest,
  CreateOrganizationRequest,
  CreateRepositoryRequest,
  Grant,
  GrantsResponse,
  Member,
  MemberQuery,
  MembersResponse,
  MoveOrganizationRequest,
  Organization,
  OrgChildrenQuery,
  OrgStats,
  OrganizationListResponse,
  RepositoriesResponse,
  Repository,
  RepositoryQuery,
  RolesResponse,
  TrackerProjectQuery,
  TrackerProjectsResponse,
  UpdateOrganizationRequest,
  UpdateVisibilityRequest,
  VisibleProjectQuery,
  VisibleProjectsResponse,
} from '../models/org';

/**
 * Client for the Org-Management-API (source of truth:
 * OpenAPI/org-management-api.yaml, served on :8005). Covers the tenancy model:
 * the org tree, membership/roles, repositories + visibility/grants, and the
 * effective-access resolution query. The middleware is the single governed
 * boundary; this portal never touches PostgreSQL directly.
 */
@Injectable({ providedIn: 'root' })
export class OrgAdminService {
  private readonly baseUrl = `${environment.orgApiBaseUrl}/api/v1`;

  constructor(private readonly http: HttpClient) {}

  // --- Organizations --------------------------------------------------------

  /** All root/tenant orgs (no `root` query). */
  listRoots(): Observable<OrganizationListResponse> {
    return this.http.get<OrganizationListResponse>(`${this.baseUrl}/orgs`);
  }

  /** The whole tenant tree rooted at `rootOrgId`. */
  listTenant(rootOrgId: string): Observable<OrganizationListResponse> {
    const params = new HttpParams().set('root', rootOrgId);
    return this.http.get<OrganizationListResponse>(`${this.baseUrl}/orgs`, { params });
  }

  getOrg(orgId: string): Observable<Organization> {
    return this.http.get<Organization>(`${this.baseUrl}/orgs/${encodeURIComponent(orgId)}`);
  }

  /**
   * Cheap tenancy aggregate counts (COUNT queries only — never a subtree
   * fetch). Backs the dashboard org summary. `root` scopes to one tenant.
   */
  orgStats(root?: string | null): Observable<OrgStats> {
    let params = new HttpParams();
    if (root) {
      params = params.set('root', root);
    }
    return this.http.get<OrgStats>(`${this.baseUrl}/orgs/stats`, { params });
  }

  /**
   * One PAGE of an org's direct children — bounded, server-filtered (`q`) and
   * sorted (`sort`). The page browser replaces rows per page (never a whole
   * subtree, never an accumulating list) so the DOM stays bounded at scale.
   */
  children(
    orgId: string,
    opts: OrgChildrenQuery = {},
  ): Observable<OrganizationListResponse> {
    let params = new HttpParams()
      .set('limit', opts.limit ?? 50)
      .set('offset', opts.offset ?? 0);
    if (opts.q) {
      params = params.set('q', opts.q);
    }
    if (opts.sort) {
      params = params.set('sort', opts.sort);
    }
    return this.http.get<OrganizationListResponse>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/children`,
      { params },
    );
  }

  /**
   * Distinct role names matching `q` (case-insensitive substring), capped.
   * Backs the searchable role picker so a large role catalog is never loaded
   * into a scroll list.
   */
  roles(q: string, limit = 25): Observable<RolesResponse> {
    let params = new HttpParams().set('limit', limit);
    if (q) {
      params = params.set('q', q);
    }
    return this.http.get<RolesResponse>(`${this.baseUrl}/roles`, { params });
  }

  /**
   * Search orgs by name (case-insensitive substring), optionally scoped to a
   * tenant (`root`). Returns a paged list; each item carries path/level/counts.
   */
  searchOrgs(
    q: string,
    root?: string | null,
    limit = 25,
    offset = 0,
  ): Observable<OrganizationListResponse> {
    let params = new HttpParams().set('q', q).set('limit', limit).set('offset', offset);
    if (root) {
      params = params.set('root', root);
    }
    return this.http.get<OrganizationListResponse>(`${this.baseUrl}/orgs/search`, { params });
  }

  subtree(orgId: string): Observable<OrganizationListResponse> {
    return this.http.get<OrganizationListResponse>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/subtree`,
    );
  }

  ancestors(orgId: string): Observable<OrganizationListResponse> {
    return this.http.get<OrganizationListResponse>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/ancestors`,
    );
  }

  createOrg(body: CreateOrganizationRequest): Observable<Organization> {
    return this.http.post<Organization>(`${this.baseUrl}/orgs`, body);
  }

  updateOrg(orgId: string, body: UpdateOrganizationRequest): Observable<Organization> {
    return this.http.put<Organization>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}`,
      body,
    );
  }

  /** Reparent an org (and its subtree). The API guards against cycles. */
  moveOrg(orgId: string, body: MoveOrganizationRequest): Observable<Organization> {
    return this.http.post<Organization>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/move`,
      body,
    );
  }

  // --- Members / roles ------------------------------------------------------

  /** One PAGE of an org's members, server-filtered by `q` / `role`. */
  listMembers(orgId: string, opts: MemberQuery = {}): Observable<MembersResponse> {
    let params = new HttpParams()
      .set('limit', opts.limit ?? 25)
      .set('offset', opts.offset ?? 0);
    if (opts.q) {
      params = params.set('q', opts.q);
    }
    if (opts.role) {
      params = params.set('role', opts.role);
    }
    return this.http.get<MembersResponse>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/members`,
      { params },
    );
  }

  addMember(orgId: string, body: AddMemberRequest): Observable<Member> {
    return this.http.post<Member>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/members`,
      body,
    );
  }

  // --- Repositories / tracker projects / visibility / grants ----------------

  /**
   * One PAGE of an org's repositories — server-filtered (`q` on provider /
   * external_account) and bounded so a large repo set never loads all at once.
   */
  listRepositories(
    orgId: string,
    opts: RepositoryQuery = {},
  ): Observable<RepositoriesResponse> {
    let params = new HttpParams()
      .set('limit', opts.limit ?? 25)
      .set('offset', opts.offset ?? 0);
    if (opts.q) {
      params = params.set('q', opts.q);
    }
    return this.http.get<RepositoriesResponse>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/repositories`,
      { params },
    );
  }

  /**
   * One PAGE of a repo's tracker projects — server-filtered (`q` on
   * external_key / name). A repo can carry thousands, so this is always paged.
   */
  listRepositoryProjects(
    repoId: string,
    opts: TrackerProjectQuery = {},
  ): Observable<TrackerProjectsResponse> {
    let params = new HttpParams()
      .set('limit', opts.limit ?? 25)
      .set('offset', opts.offset ?? 0);
    if (opts.q) {
      params = params.set('q', opts.q);
    }
    return this.http.get<TrackerProjectsResponse>(
      `${this.baseUrl}/repositories/${encodeURIComponent(repoId)}/projects`,
      { params },
    );
  }

  /** One PAGE of a repo's cross-org sharing grants. */
  listRepositoryGrants(
    repoId: string,
    limit = 25,
    offset = 0,
  ): Observable<GrantsResponse> {
    const params = new HttpParams().set('limit', limit).set('offset', offset);
    return this.http.get<GrantsResponse>(
      `${this.baseUrl}/repositories/${encodeURIComponent(repoId)}/grants`,
      { params },
    );
  }

  createRepository(orgId: string, body: CreateRepositoryRequest): Observable<Repository> {
    return this.http.post<Repository>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/repositories`,
      body,
    );
  }

  addTrackerProjects(
    repoId: string,
    body: AddTrackerProjectsRequest,
  ): Observable<TrackerProjectsResponse> {
    return this.http.post<TrackerProjectsResponse>(
      `${this.baseUrl}/repositories/${encodeURIComponent(repoId)}/projects`,
      body,
    );
  }

  setVisibility(repoId: string, body: UpdateVisibilityRequest): Observable<Repository> {
    return this.http.put<Repository>(
      `${this.baseUrl}/repositories/${encodeURIComponent(repoId)}/visibility`,
      body,
    );
  }

  addGrant(repoId: string, body: AddGrantRequest): Observable<Grant> {
    return this.http.post<Grant>(
      `${this.baseUrl}/repositories/${encodeURIComponent(repoId)}/grants`,
      body,
    );
  }

  // --- Effective access resolution ------------------------------------------

  /**
   * One PAGE of a subject's visible tracker projects — server-filtered (`q` on
   * external_key / name) and bounded (the visible set can be huge).
   */
  visibleProjects(
    subject: string,
    opts: VisibleProjectQuery = {},
  ): Observable<VisibleProjectsResponse> {
    let params = new HttpParams()
      .set('limit', opts.limit ?? 25)
      .set('offset', opts.offset ?? 0);
    if (opts.q) {
      params = params.set('q', opts.q);
    }
    return this.http.get<VisibleProjectsResponse>(
      `${this.baseUrl}/users/${encodeURIComponent(subject)}/visible-projects`,
      { params },
    );
  }
}
