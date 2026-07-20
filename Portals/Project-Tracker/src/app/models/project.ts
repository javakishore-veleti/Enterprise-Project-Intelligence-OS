/**
 * Typed views of the Projects-API contract (OpenAPI/projects-api.yaml).
 * These mirror the response schemas exposed by the Projects-API on :8003.
 */

export interface Project {
  project_key: string;
  name: string;
  category: string | null;
  issue_count: number;
  open_issue_count: number;
}

export interface PageMeta {
  total: number;
  limit: number;
  offset: number;
}

export interface ProjectSearchResponse {
  items: Project[];
  page: PageMeta;
}

export interface ProjectMetrics {
  project_key: string;
  computed_at: string;
  backlog_growth: number;
  reopen_rate: number;
  blocker_count: number;
  dependency_depth: number;
  issue_aging_days: number;
  resolution_velocity: number;
  contributor_concentration: number;
  critical_defect_ratio: number;
}
