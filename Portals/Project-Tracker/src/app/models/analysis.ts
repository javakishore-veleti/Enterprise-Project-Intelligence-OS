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

/** A recent finding surfaced on the dashboard (cross-project, trimmed). */
export interface RecentFinding {
  finding_id: string;
  run_id: string;
  project_key: string;
  agent_key: string;
  risk_category: string;
  severity: string;
  score: number;
  explanation: string;
}

/** Response for GET /api/v1/analysis/activity — live cross-project dynamics. */
export interface DashboardActivity {
  recent_runs: AnalysisRunSummary[];
  recent_findings: RecentFinding[];
  totals: {
    total_runs: number;
    total_findings: number;
    projects_analyzed: number;
  };
}

/** Request body for POST /api/v1/analysis/portfolios/{group_key}. */
export interface StartPortfolioRequest {
  agents: string[];
  project_keys: string[];
  requested_by: string;
}

/** One step in the Investigation Agent's reasoning trace (an action + what it observed). */
export interface InvestigationStep {
  action: string;
  observation: string;
  hypothesis: string | null;
}

/** One piece of evidence the Investigation Agent cited. */
export interface InvestigationEvidence {
  kind: string;
  detail: string;
  count: number | null;
}

/** Result of the autonomous Investigation Agent — POST /api/v1/analysis/investigate. */
export interface Investigation {
  project_key: string;
  question: string | null;
  hypotheses: string[];
  steps: InvestigationStep[];
  root_cause: string;
  causal_chain: string[];
  confidence: number;
  evidence: InvestigationEvidence[];
  recommended_action: string;
  run_id: string;
  generated_at: string;
}

/** Request body for POST /api/v1/analysis/investigate. */
export interface InvestigateRequest {
  project_key: string;
  question: string | null;
  requested_by: string | null;
}

/** One ranked attention item from GET /api/v1/analysis/attention. */
export interface AttentionItem {
  finding_id: string;
  run_id: string;
  project_key: string;
  agent_key: string;
  risk_category: string;
  severity: string;
  score: number;
  probability: number;
  confidence: number;
  attention_score: number;
  explanation: string;
  recommended_actions: string[];
  analysis_timestamp: string;
}

/** Response for GET /api/v1/analysis/attention (ranked feed + paging totals). */
export interface AttentionResponse {
  as_of: string | null;
  scope_projects: number;
  total: number;
  returned: number;
  items: AttentionItem[];
}
