import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  CreateProjectGroupRequest,
  ProjectGroup,
  ProjectGroupListResponse,
  UpdateProjectGroupRequest,
} from '../models/group';

/** Client for the Projects-API project-groups CRUD (:8003). */
@Injectable({ providedIn: 'root' })
export class GroupsService {
  private readonly baseUrl = `${environment.apiBaseUrl}/api/v1/project-groups`;

  constructor(private readonly http: HttpClient) {}

  list(): Observable<ProjectGroupListResponse> {
    return this.http.get<ProjectGroupListResponse>(this.baseUrl);
  }

  create(body: CreateProjectGroupRequest): Observable<ProjectGroup> {
    return this.http.post<ProjectGroup>(this.baseUrl, body);
  }

  update(groupKey: string, body: UpdateProjectGroupRequest): Observable<ProjectGroup> {
    return this.http.put<ProjectGroup>(`${this.baseUrl}/${encodeURIComponent(groupKey)}`, body);
  }

  remove(groupKey: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${encodeURIComponent(groupKey)}`);
  }
}
