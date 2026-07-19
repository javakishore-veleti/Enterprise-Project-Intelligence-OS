import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import { AnalysisRun, StartAnalysisRequest } from '../models/analysis';

export interface StartAnalysisOptions {
  agents: string[];
  includeReview: boolean;
  requestedBy: string;
}

/**
 * Client for the RiskAnalytics-API (source of truth: OpenAPI/risk-analytics-api.yaml).
 * The middleware is the single governed boundary; this portal never touches
 * MongoDB/PostgreSQL/LangGraph directly.
 */
@Injectable({ providedIn: 'root' })
export class RiskAnalyticsService {
  private readonly baseUrl = `${environment.riskApiBaseUrl}/api/v1`;

  constructor(private readonly http: HttpClient) {}

  /**
   * Kick off a multi-agent risk analysis for a project. The request may take
   * 30-60s to return while the detector fan-out (and optional review pipeline)
   * runs against the LLM.
   */
  startAnalysis(projectKey: string, options: StartAnalysisOptions): Observable<AnalysisRun> {
    const body: StartAnalysisRequest = {
      agents: options.agents,
      include_review: options.includeReview,
      requested_by: options.requestedBy,
    };
    return this.http.post<AnalysisRun>(
      `${this.baseUrl}/analysis/projects/${encodeURIComponent(projectKey)}`,
      body,
    );
  }

  /** Fetch a previously started run by id. */
  getRun(runId: string): Observable<AnalysisRun> {
    return this.http.get<AnalysisRun>(
      `${this.baseUrl}/analysis/runs/${encodeURIComponent(runId)}`,
    );
  }
}
