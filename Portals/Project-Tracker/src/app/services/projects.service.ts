import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { MetricsHistory, Project, ProjectMetrics, ProjectSearchResponse } from '../models/project';
import { ForecastSubjectsResponse, PortfolioSummary, ScopedProjectSearchResponse } from '../models/portfolio';

export interface SearchProjectsParams {
  query?: string;
  limit?: number;
  offset?: number;
}

export interface ScopedSearchParams {
  /** User key to scope to their assigned projects; null/empty → all projects. */
  scope?: string | null;
  /** Case-insensitive substring on project_key OR name. */
  q?: string;
  limit?: number;
  offset?: number;
}

/**
 * Client for the Projects-API (source of truth: OpenAPI/projects-api.yaml).
 * The middleware is the single governed boundary; this portal never touches
 * MongoDB/PostgreSQL directly.
 */
@Injectable({ providedIn: 'root' })
export class ProjectsService {
  private readonly baseUrl = `${environment.apiBaseUrl}/api/v1`;

  constructor(private readonly http: HttpClient) {}

  searchProjects(params: SearchProjectsParams = {}): Observable<ProjectSearchResponse> {
    let httpParams = new HttpParams();
    if (params.query) {
      httpParams = httpParams.set('query', params.query);
    }
    if (params.limit != null) {
      httpParams = httpParams.set('limit', params.limit);
    }
    if (params.offset != null) {
      httpParams = httpParams.set('offset', params.offset);
    }
    return this.http.get<ProjectSearchResponse>(`${this.baseUrl}/projects`, { params: httpParams });
  }

  /**
   * Server-side, risk-ranked, paginated project search scoped to the user
   * (GET /projects/search). Scales to thousands of projects — the DB ranks and
   * pages; the client only holds a window. Powers the card target-selectors.
   */
  searchScopedProjects(params: ScopedSearchParams = {}): Observable<ScopedProjectSearchResponse> {
    let httpParams = new HttpParams()
      .set('limit', params.limit ?? 25)
      .set('offset', params.offset ?? 0);
    if (params.scope) {
      httpParams = httpParams.set('scope', params.scope);
    }
    if (params.q && params.q.trim()) {
      httpParams = httpParams.set('q', params.q.trim());
    }
    return this.http.get<ScopedProjectSearchResponse>(`${this.baseUrl}/projects/search`, {
      params: httpParams,
    });
  }

  getProject(projectKey: string): Observable<Project> {
    return this.http.get<Project>(`${this.baseUrl}/projects/${encodeURIComponent(projectKey)}`);
  }

  getProjectMetrics(projectKey: string): Observable<ProjectMetrics> {
    return this.http.get<ProjectMetrics>(
      `${this.baseUrl}/projects/${encodeURIComponent(projectKey)}/metrics`,
    );
  }

  /** Time-series of metric snapshots (newest first) for the progress graph. */
  getMetricsHistory(projectKey: string, limit = 200): Observable<MetricsHistory> {
    const params = new HttpParams().set('limit', limit);
    return this.http.get<MetricsHistory>(
      `${this.baseUrl}/projects/${encodeURIComponent(projectKey)}/metrics/history`,
      { params },
    );
  }

  /**
   * The sub-scope facets a project can be forecast against (releases / components /
   * tags), each with an issue count — top-50 per facet, descending by count.
   * Powers the Forecasts sub-scope picker; lists are empty when none are recorded.
   */
  getForecastSubjects(projectKey: string): Observable<ForecastSubjectsResponse> {
    return this.http.get<ForecastSubjectsResponse>(
      `${this.baseUrl}/projects/${encodeURIComponent(projectKey)}/forecast-subjects`,
    );
  }

  /**
   * Server-ranked portfolio summary, scoped to the logged-in user's assigned
   * projects when a user key is supplied (X-User-Key seam → SSO subject later).
   * Ranking happens in the DB; the client only ever receives the top N.
   */
  getPortfolioSummary(top = 15, userKey?: string | null, asOf?: string): Observable<PortfolioSummary> {
    let params = new HttpParams().set('top', top);
    if (asOf) {
      params = params.set('as_of', asOf);
    }
    let headers = new HttpHeaders();
    if (userKey) {
      headers = headers.set('X-User-Key', userKey);
    }
    return this.http.get<PortfolioSummary>(`${this.baseUrl}/projects/portfolio-summary`, {
      params,
      headers,
    });
  }
}
