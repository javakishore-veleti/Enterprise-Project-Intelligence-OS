/** Typed views of the Projects-API project-groups contract (:8003). */

export interface ProjectGroup {
  group_key: string;
  name: string;
  description: string;
  project_keys: string[];
  created_at: string;
  updated_at: string;
}

export interface ProjectGroupListResponse {
  items: ProjectGroup[];
}

export interface CreateProjectGroupRequest {
  name: string;
  description?: string;
  project_keys: string[];
}

export interface UpdateProjectGroupRequest {
  name?: string;
  description?: string;
  project_keys?: string[];
}
