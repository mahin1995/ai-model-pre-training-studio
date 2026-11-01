import type { Project } from "../types/project";
import { readiness, validate } from "../features/project-setup/validation";
import { request } from "./api";
export function listProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}
export function loadProject(id: string): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(id)}`);
}
export async function saveProject(project: Project): Promise<Project> {
  if (validate(project).length)
    throw new Error("Fix the highlighted values before saving.");
  if (project.status === "scope-ready" && !readiness(project).ready)
    throw new Error("Complete the readiness checklist first.");
  return request<Project>(
    project.revision
      ? `/projects/${encodeURIComponent(project.id)}`
      : "/projects",
    {
      method: project.revision ? "PATCH" : "POST",
      body: JSON.stringify(project),
    },
  );
}
