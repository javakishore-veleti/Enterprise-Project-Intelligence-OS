import { HttpClient } from '@angular/common/http';
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

/**
 * Client for the Org-Management-API (:8005). Read-only tree navigation used to
 * populate the org switcher; never scoped by X-Org-Key itself (the interceptor
 * deliberately excludes this host).
 */
@Injectable({ providedIn: 'root' })
export class OrgService {
  private readonly baseUrl = `${environment.orgApiBaseUrl}/api/v1/orgs`;

  constructor(private readonly http: HttpClient) {}

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
