/**
 * Typed views of the Admin-API contract (OpenAPI/admin-api.yaml).
 * These mirror the response schemas exposed by the Admin-API on :8002.
 */

/** Orchestration framework an agent executes under (AgentFramework enum). */
export type AgentFramework =
  | 'langgraph'
  | 'crewai'
  | 'openai_agents'
  | 'strands'
  | 'google_adk'
  | 'ms_agent_framework';

/** The six frameworks, in contract order — used to populate the dropdown. */
export const AGENT_FRAMEWORKS: AgentFramework[] = [
  'langgraph',
  'crewai',
  'openai_agents',
  'strands',
  'google_adk',
  'ms_agent_framework',
];

export interface PageMeta {
  total: number;
  limit: number;
  offset: number;
}

export interface AgentConfig {
  agent_key: string;
  display_name: string;
  enabled: boolean;
  model: string;
  framework: AgentFramework;
  prompt_ref: string | null;
  updated_by: string;
  updated_at: string;
}

export interface AgentConfigListResponse {
  items: AgentConfig[];
  page: PageMeta;
}

export interface UpsertAgentConfigRequest {
  enabled: boolean;
  model: string;
  framework: AgentFramework;
  prompt_ref: string | null;
  updated_by: string;
}

export interface AuditEvent {
  event_id: string;
  entity_type: string;
  entity_key: string;
  action: string;
  actor: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface AuditListResponse {
  items: AuditEvent[];
  page: PageMeta;
}

export interface SystemHealth {
  status: string;
  service: string;
  dependencies: Record<string, string>;
  agent_count: number;
  enabled_agent_count: number;
}

/** Lifecycle state of the managed dataset (Admin-API dataset contract). */
export type DatasetState = 'NOT_DOWNLOADED' | 'DOWNLOADING' | 'DOWNLOADED' | 'FAILED';

/** The four dataset states, in contract order. */
export const DATASET_STATES: DatasetState[] = [
  'NOT_DOWNLOADED',
  'DOWNLOADING',
  'DOWNLOADED',
  'FAILED',
];

/** Status of the initial dataset acquisition, from the Admin-API on :8002. */
export interface DatasetStatus {
  dataset_id: string;
  title: string;
  state: DatasetState;
  file_name: string;
  size_bytes: number;
  expected_md5: string;
  downloaded_bytes: number;
  message: string;
  updated_at: string;
}

/** Body for POST /api/v1/admin/dataset/download. */
export interface TriggerDatasetDownloadRequest {
  requested_by: string;
}
