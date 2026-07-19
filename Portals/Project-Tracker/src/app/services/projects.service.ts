import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { Project, ProjectMetrics, ProjectSearchResponse } from '../models/project';

export interface SearchProjectsParams {
  query?: string;
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

  getProject(projectKey: string): Observable<Project> {
    return this.http.get<Project>(`${this.baseUrl}/projects/${encodeURIComponent(projectKey)}`);
  }

  getProjectMetrics(projectKey: string): Observable<ProjectMetrics> {
    return this.http.get<ProjectMetrics>(
      `${this.baseUrl}/projects/${encodeURIComponent(projectKey)}/metrics`,
    );
  }
}
