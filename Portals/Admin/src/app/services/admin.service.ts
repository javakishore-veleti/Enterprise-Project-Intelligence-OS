import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  AgentConfig,
  AgentConfigListResponse,
  AuditListResponse,
  SystemHealth,
  UpsertAgentConfigRequest,
} from '../models/admin';

export interface PageParams {
  limit?: number;
  offset?: number;
}

/**
 * Client for the Admin-API (source of truth: OpenAPI/admin-api.yaml).
 * The middleware is the single governed boundary; this portal never touches
 * MongoDB/PostgreSQL directly.
 */
@Injectable({ providedIn: 'root' })
export class AdminService {
  private readonly baseUrl = `${environment.apiBaseUrl}/api/v1/admin`;

  constructor(private readonly http: HttpClient) {}

  private pageParams(params: PageParams): HttpParams {
    let httpParams = new HttpParams();
    if (params.limit != null) {
      httpParams = httpParams.set('limit', params.limit);
    }
    if (params.offset != null) {
      httpParams = httpParams.set('offset', params.offset);
    }
    return httpParams;
  }

  listAgents(params: PageParams = {}): Observable<AgentConfigListResponse> {
    return this.http.get<AgentConfigListResponse>(`${this.baseUrl}/agents`, {
      params: this.pageParams(params),
    });
  }

  getAgent(agentKey: string): Observable<AgentConfig> {
    return this.http.get<AgentConfig>(`${this.baseUrl}/agents/${encodeURIComponent(agentKey)}`);
  }

  upsertAgent(agentKey: string, body: UpsertAgentConfigRequest): Observable<AgentConfig> {
    return this.http.put<AgentConfig>(
      `${this.baseUrl}/agents/${encodeURIComponent(agentKey)}`,
      body,
    );
  }

  getAudit(params: PageParams = {}): Observable<AuditListResponse> {
    return this.http.get<AuditListResponse>(`${this.baseUrl}/audit`, {
      params: this.pageParams(params),
    });
  }

  getSystemHealth(): Observable<SystemHealth> {
    return this.http.get<SystemHealth>(`${this.baseUrl}/system/health`);
  }
}
