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
  Member,
  MemberQuery,
  MembersResponse,
  MoveOrganizationRequest,
  Organization,
  OrganizationListResponse,
  RepositoriesResponse,
  Repository,
  TrackerProjectsResponse,
  UpdateOrganizationRequest,
  UpdateVisibilityRequest,
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
   * One PAGE of an org's direct children. Used by the lazy tree — a node's
   * children are fetched only when it is expanded, never a whole subtree.
   */
  children(orgId: string, limit = 50, offset = 0): Observable<OrganizationListResponse> {
    const params = new HttpParams().set('limit', limit).set('offset', offset);
    return this.http.get<OrganizationListResponse>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/children`,
      { params },
    );
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

  listRepositories(orgId: string): Observable<RepositoriesResponse> {
    return this.http.get<RepositoriesResponse>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/repositories`,
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

  visibleProjects(subject: string): Observable<VisibleProjectsResponse> {
    return this.http.get<VisibleProjectsResponse>(
      `${this.baseUrl}/users/${encodeURIComponent(subject)}/visible-projects`,
    );
  }
}
