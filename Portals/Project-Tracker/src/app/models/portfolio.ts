/** Typed views of the Projects-API portfolio-summary contract (:8003). */

export type RiskBand = 'High' | 'Medium' | 'Low';

export interface PortfolioProject {
  project_key: string;
  name: string;
  category: string | null;
  risk_score: number;
  risk_band: RiskBand;
  issue_count: number;
  open_issue_count: number;
  blocker_count: number;
  reopen_rate: number;
  issue_aging_days: number;
  critical_defect_ratio: number;
  headline: string;
}

export interface PortfolioSummary {
  scope: { user_key: string | null; project_count: number; scoped: boolean };
  as_of?: string | null;
  portfolio_score: number;
  overall_risk: RiskBand;
  totals: { projects: number; issues: number; open_issues: number };
  risk_bands: { high: number; medium: number; low: number; unscored: number };
  top_projects: PortfolioProject[];
  computed_at: string;
}

/**
 * One row of the server-side, risk-ranked scoped project search
 * (GET /api/v1/projects/search). A lighter view than PortfolioProject —
 * only what a project card needs. risk_score/risk_band are null when unscored.
 */
export interface ProjectSearchItem {
  project_key: string;
  name: string;
  risk_score: number | null;
  risk_band: RiskBand | null;
  open_issue_count: number;
}

/**
 * Paginated response of GET /api/v1/projects/search — scales to thousands of
 * projects per user (the DB ranks + pages; the client only ever holds a window).
 */
export interface ScopedProjectSearchResponse {
  total: number;
  returned: number;
  offset: number;
  limit: number;
  items: ProjectSearchItem[];
}

/** One selectable forecast sub-scope value (a release/component/tag) + its issue count. */
export interface ForecastSubjectFacet {
  value: string;
  count: number;
}

/**
 * Facets a project can be forecast against — GET /projects/{key}/forecast-subjects.
 * Each list is top-50, descending by count; empty when none are recorded yet.
 */
export interface ForecastSubjectsResponse {
  project_key: string;
  releases: ForecastSubjectFacet[];
  components: ForecastSubjectFacet[];
  tags: ForecastSubjectFacet[];
}
