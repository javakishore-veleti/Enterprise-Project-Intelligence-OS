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

  children(orgId: string): Observable<OrganizationListResponse> {
    return this.http.get<OrganizationListResponse>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/children`,
    );
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

  listMembers(orgId: string): Observable<MembersResponse> {
    return this.http.get<MembersResponse>(
      `${this.baseUrl}/orgs/${encodeURIComponent(orgId)}/members`,
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
