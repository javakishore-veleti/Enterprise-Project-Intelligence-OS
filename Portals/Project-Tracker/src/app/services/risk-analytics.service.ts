import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  AnalysisRun,
  AnalysisRunsResponse,
  AttentionResponse,
  DashboardActivity,
  StartAnalysisRequest,
  StartPortfolioRequest,
} from '../models/analysis';

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

  /** Live cross-project activity for the dashboard (recent runs + findings + totals). */
  getActivity(limit = 15): Observable<DashboardActivity> {
    const params = new HttpParams().set('limit', limit);
    return this.http.get<DashboardActivity>(`${this.baseUrl}/analysis/activity`, { params });
  }

  /**
   * Ranked attention feed. Server ranks by attention score; `projects` scopes it
   * (user's or a group's project keys), `asOf` gives the feed as of a past date.
   */
  getAttention(
    top = 10,
    opts: { projects?: string[]; asOf?: string; offset?: number } = {},
  ): Observable<AttentionResponse> {
    let params = new HttpParams().set('top', top);
    if (opts.offset != null) params = params.set('offset', opts.offset);
    if (opts.asOf) params = params.set('as_of', opts.asOf);
    if (opts.projects?.length) params = params.set('projects', opts.projects.join(','));
    return this.http.get<AttentionResponse>(`${this.baseUrl}/analysis/attention`, { params });
  }

  /** Run a combined portfolio-risk analysis over a group's member projects. */
  startPortfolioAnalysis(
    groupKey: string,
    options: { agents: string[]; projectKeys: string[]; requestedBy: string },
  ): Observable<AnalysisRun> {
    const body: StartPortfolioRequest = {
      agents: options.agents,
      project_keys: options.projectKeys,
      requested_by: options.requestedBy,
    };
    return this.http.post<AnalysisRun>(
      `${this.baseUrl}/analysis/portfolios/${encodeURIComponent(groupKey)}`,
      body,
    );
  }

  /**
   * List the most recent analysis runs for a project (newest first),
   * as lightweight run summaries for the history table.
   */
  listRuns(projectKey: string, limit = 20): Observable<AnalysisRunsResponse> {
    const params = new HttpParams().set('limit', limit);
    return this.http.get<AnalysisRunsResponse>(
      `${this.baseUrl}/analysis/projects/${encodeURIComponent(projectKey)}/runs`,
      { params },
    );
  }
}
