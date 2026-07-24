import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, forkJoin, map, of, switchMap } from 'rxjs';

import { environment } from '../../environments/environment';

/** A node in the organization hierarchy (Org-Management-API :8005). */
export interface OrgNode {
  org_id: string;
  name: string;
  /** 1-indexed depth in the tree (roots are level 1). */
  level: number;
  parent_org_id: string | null;
  path: string;
  root_org_id: string;
}

interface OrgListResponse {
  organizations?: OrgNode[];
  items?: OrgNode[];
}

/** Parameters for the scalable server-side org search. */
export interface OrgSearchParams {
  /** Free-text query (matched against name/path server-side). */
  q?: string;
  /** Restrict the search to a single root's subtree. */
  root?: string;
  /** Max results to return (server default 25; the picker asks for 20). */
  limit?: number;
  /** Result offset for paging. */
  offset?: number;
}

/** Bounded search result page from `GET /api/v1/orgs/search`. */
export interface ScopedOrgSearch {
  organizations: OrgNode[];
  total: number;
}

interface OrgSearchResponse {
  organizations?: OrgNode[];
  items?: OrgNode[];
  total?: number;
}

/**
 * Client for the Org-Management-API (:8005). Read-only tree navigation used to
 * populate the org switcher; never scoped by X-Org-Key itself (the interceptor
 * deliberately excludes this host).
 */
@Injectable({ providedIn: 'root' })
export class OrgService {
  private readonly baseUrl = `${environment.orgApiBaseUrl}/api/v1/orgs`;

  constructor(private readonly http: HttpClient) {}

  /**
   * Scalable, server-side org search — never loads the whole tree. Returns a
   * bounded page (`limit` results) so the switcher's DOM/network stay flat
   * regardless of how many organizations exist. Tolerates
   * `{organizations:[...]}`, `{items:[...]}`, or a bare array in the body.
   */
  searchOrgs(params: OrgSearchParams = {}): Observable<ScopedOrgSearch> {
    let httpParams = new HttpParams();
    if (params.q) {
      httpParams = httpParams.set('q', params.q);
    }
    if (params.root) {
      httpParams = httpParams.set('root', params.root);
    }
    httpParams = httpParams.set('limit', String(params.limit ?? 20));
    httpParams = httpParams.set('offset', String(params.offset ?? 0));
    return this.http
      .get<OrgSearchResponse | OrgNode[]>(`${this.baseUrl}/search`, { params: httpParams })
      .pipe(
        map((r) => {
          const organizations = Array.isArray(r) ? r : (r.organizations ?? r.items ?? []);
          const total = Array.isArray(r) ? r.length : (r.total ?? organizations.length);
          return { organizations, total };
        }),
      );
  }

  /** Root organizations. Tolerates `{organizations:[...]}`, `{items:[...]}`, or a bare array. */
  roots(): Observable<OrgNode[]> {
    return this.http
      .get<OrgListResponse | OrgNode[]>(this.baseUrl)
      .pipe(map((r) => (Array.isArray(r) ? r : (r.organizations ?? r.items ?? []))));
  }

  /** Full subtree rooted at {orgId}, flattened (each item carries its level/path). */
  subtree(orgId: string): Observable<OrgNode[]> {
    return this.http
      .get<OrgListResponse>(`${this.baseUrl}/${encodeURIComponent(orgId)}/subtree`)
      .pipe(map((r) => r.organizations ?? r.items ?? []));
  }

  /**
   * Convenience for the dropdown: every root expanded into its full subtree,
   * concatenated in root order. Levels are 1-indexed for label indentation.
   */
  tree(): Observable<OrgNode[]> {
    return this.roots().pipe(
      switchMap((roots) => {
        if (!roots.length) {
          return of<OrgNode[]>([]);
        }
        return forkJoin(roots.map((r) => this.subtree(r.org_id))).pipe(
          map((subtrees) => subtrees.flat()),
        );
      }),
    );
  }
}
