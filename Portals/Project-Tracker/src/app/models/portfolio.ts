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
