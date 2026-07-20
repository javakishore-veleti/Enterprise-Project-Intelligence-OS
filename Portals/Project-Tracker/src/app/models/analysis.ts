/**
 * Typed views of the RiskAnalytics-API contract (OpenAPI/risk-analytics-api.yaml).
 * These mirror the response schemas exposed by the RiskAnalytics-API on :8004.
 */

export type AnalysisStatus = 'RUNNING' | 'COMPLETED' | 'FAILED';

/** A persisted risk finding surfaced to clients. */
export interface RiskFinding {
  finding_id: string;
  agent_key: string;
  risk_category: string;
  probability: number;
  impact: number;
  severity: string;
  score: number;
  confidence: number;
  explanation: string;
  assumptions: string[];
  recommended_actions: string[];
  affected: string[];
  analysis_timestamp: string;
  /** Free-form review annotations (priority_rank, merged_count, critic_verdict, …). */
  meta: Record<string, unknown>;
}

/** One heading/body block within a narrative report. */
export interface ReportSection {
  heading: string;
  body: string;
  [key: string]: unknown;
}

/** A generated narrative report over a run's findings. */
export interface Report {
  report_id: string;
  kind: string;
  title: string;
  summary: string;
  sections: ReportSection[];
  source_agent: string;
  generated_at: string;
}

/** A multi-agent analysis run, its findings, and any review reports. */
export interface AnalysisRun {
  run_id: string;
  project_key: string;
  status: AnalysisStatus;
  agent_keys: string[];
  started_at: string;
  finished_at: string | null;
  findings: RiskFinding[];
  reports: Report[];
}

/** Request body for POST /api/v1/analysis/projects/{project_key}. */
export interface StartAnalysisRequest {
  agents: string[];
  include_review: boolean;
  requested_by: string;
}

/** One row in a project's analysis-run history (lightweight run header). */
export interface AnalysisRunSummary {
  run_id: string;
  project_key: string;
  status: AnalysisStatus;
  agent_keys: string[];
  started_at: string;
  finished_at: string | null;
  finding_count: number;
  report_count: number;
}

/** Response for GET /api/v1/analysis/projects/{project_key}/runs. */
export interface AnalysisRunsResponse {
  project_key: string;
  runs: AnalysisRunSummary[];
}
