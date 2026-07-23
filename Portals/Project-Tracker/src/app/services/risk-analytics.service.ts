import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  AnalysisRun,
  AnalysisRunsResponse,
  AttentionResponse,
  DashboardActivity,
  Decision,
  DecisionsPage,
  EarlyWarning,
  Forecast,
  ForecastsPage,
  Investigation,
  InvestigateRequest,
  InvestigationsPage,
  InvestigationTemplate,
  Scenario,
  ScenariosPage,
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

  /**
   * Deploy the autonomous Investigation Agent at a project. It forms hypotheses,
   * calls evidence-store tools (LangGraph ReAct loop), and returns a root-cause
   * conclusion + reasoning trace + evidence + confidence. Runs the LLM (~30-60s).
   */
  investigate(
    projectKey: string,
    question: string | null,
    requestedBy: string,
    templateKey: string | null = null,
  ): Observable<Investigation> {
    const body: InvestigateRequest = {
      project_key: projectKey,
      question: question && question.trim() ? question.trim() : null,
      template_key: templateKey,
      requested_by: requestedBy,
    };
    return this.http.post<Investigation>(`${this.baseUrl}/analysis/investigate`, body);
  }

  /** Paginated, searchable history of persisted investigations (newest first). */
  listInvestigations(
    opts: { scope?: string | null; q?: string; limit?: number; offset?: number } = {},
  ): Observable<InvestigationsPage> {
    let params = new HttpParams()
      .set('limit', opts.limit ?? 20)
      .set('offset', opts.offset ?? 0);
    if (opts.scope) params = params.set('scope', opts.scope);
    if (opts.q && opts.q.trim()) params = params.set('q', opts.q.trim());
    return this.http.get<InvestigationsPage>(`${this.baseUrl}/analysis/investigations`, { params });
  }

  /** Fetch one persisted investigation by its id. */
  getInvestigation(investigationId: string): Observable<Investigation> {
    return this.http.get<Investigation>(
      `${this.baseUrl}/analysis/investigations/${encodeURIComponent(investigationId)}`,
    );
  }

  /** The pre-configured (user-editable) investigation templates. */
  listTemplates(): Observable<InvestigationTemplate[]> {
    return this.http.get<InvestigationTemplate[]>(`${this.baseUrl}/analysis/investigation-templates`);
  }

  // ---- Predict: forecasts ----

  /**
   * Run a delivery forecast for a project (LLM narration, ~30-60s). The forecast
   * can be scoped to a release/component/tag via `subjectType`/`subjectValue`;
   * they are only sent when the scope is a real sub-scope (not the whole project).
   */
  runForecast(
    projectKey: string,
    requestedBy: string,
    subject: { subjectType?: string; subjectValue?: string } = {},
  ): Observable<Forecast> {
    const body: Record<string, unknown> = {
      project_key: projectKey,
      requested_by: requestedBy,
    };
    if (subject.subjectType && subject.subjectType !== 'project' && subject.subjectValue) {
      body['subject_type'] = subject.subjectType;
      body['subject_value'] = subject.subjectValue;
    }
    return this.http.post<Forecast>(`${this.baseUrl}/analysis/forecast`, body);
  }

  listForecasts(opts: { scope?: string | null; q?: string; limit?: number; offset?: number } = {}): Observable<ForecastsPage> {
    let params = new HttpParams().set('limit', opts.limit ?? 20).set('offset', opts.offset ?? 0);
    if (opts.scope) params = params.set('scope', opts.scope);
    if (opts.q && opts.q.trim()) params = params.set('q', opts.q.trim());
    return this.http.get<ForecastsPage>(`${this.baseUrl}/analysis/forecasts`, { params });
  }

  getForecast(forecastId: string): Observable<Forecast> {
    return this.http.get<Forecast>(`${this.baseUrl}/analysis/forecasts/${encodeURIComponent(forecastId)}`);
  }

  // ---- Predict: scenarios (Digital Twin) ----

  /** Simulate a natural-language what-if for a project (LLM narration, ~30-60s). */
  runScenario(projectKey: string, scenario: string, requestedBy: string): Observable<Scenario> {
    return this.http.post<Scenario>(`${this.baseUrl}/analysis/scenarios`, {
      project_key: projectKey,
      scenario,
      requested_by: requestedBy,
    });
  }

  listScenarios(opts: { scope?: string | null; q?: string; limit?: number; offset?: number } = {}): Observable<ScenariosPage> {
    let params = new HttpParams().set('limit', opts.limit ?? 20).set('offset', opts.offset ?? 0);
    if (opts.scope) params = params.set('scope', opts.scope);
    if (opts.q && opts.q.trim()) params = params.set('q', opts.q.trim());
    return this.http.get<ScenariosPage>(`${this.baseUrl}/analysis/scenarios`, { params });
  }

  getScenario(scenarioId: string): Observable<Scenario> {
    return this.http.get<Scenario>(`${this.baseUrl}/analysis/scenarios/${encodeURIComponent(scenarioId)}`);
  }

  // ---- Predict: early-warnings (computed on read) ----

  getEarlyWarnings(scope: string | null, limit = 10): Observable<{ items: EarlyWarning[] }> {
    let params = new HttpParams().set('limit', limit);
    if (scope) params = params.set('scope', scope);
    return this.http.get<{ items: EarlyWarning[] }>(`${this.baseUrl}/analysis/early-warnings`, { params });
  }

  // ---- Decide: options-first decisions ----

  /** Ask the Decide agent to generate 2-3 candidate options for a project (LLM, ~30-90s). */
  runDecision(projectKey: string, requestedBy: string): Observable<Decision> {
    return this.http.post<Decision>(`${this.baseUrl}/analysis/decide`, {
      project_key: projectKey,
      requested_by: requestedBy,
    });
  }

  /** Mark one option as selected — moves the decision to SELECTED. */
  selectOption(decisionId: string, optionId: string): Observable<Decision> {
    return this.http.post<Decision>(
      `${this.baseUrl}/analysis/decisions/${encodeURIComponent(decisionId)}/select`,
      { option_id: optionId },
    );
  }

  /** Approve the selected option (dry-run/preview) — moves the decision to APPROVED. */
  approveDecision(decisionId: string): Observable<Decision> {
    return this.http.post<Decision>(
      `${this.baseUrl}/analysis/decisions/${encodeURIComponent(decisionId)}/approve`,
      {},
    );
  }

  listDecisions(opts: { scope?: string | null; q?: string; limit?: number; offset?: number } = {}): Observable<DecisionsPage> {
    let params = new HttpParams().set('limit', opts.limit ?? 20).set('offset', opts.offset ?? 0);
    if (opts.scope) params = params.set('scope', opts.scope);
    if (opts.q && opts.q.trim()) params = params.set('q', opts.q.trim());
    return this.http.get<DecisionsPage>(`${this.baseUrl}/analysis/decisions`, { params });
  }

  getDecision(decisionId: string): Observable<Decision> {
    return this.http.get<Decision>(`${this.baseUrl}/analysis/decisions/${encodeURIComponent(decisionId)}`);
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
