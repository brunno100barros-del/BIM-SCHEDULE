import { Project, ProjectCreateInput } from '../types/project';
import { apiDelete, apiGet, apiPost, apiPut } from './apiClient';

export type ProjectUpdateInput = Partial<ProjectCreateInput>;

export const projectService = {
  getAll: (signal?: AbortSignal) => apiGet<Project[]>('/projects/', { signal }),
  get: (id: number, signal?: AbortSignal) => apiGet<Project>(`/projects/${id}`, { signal }),
  create: (data: ProjectCreateInput) => apiPost<Project>('/projects/', data),
  update: (id: number, data: ProjectUpdateInput) => apiPut<Project>(`/projects/${id}`, data),
  delete: (id: number) => apiDelete(`/projects/${id}`),
  duplicate: (id: number) => apiPost<Project>(`/projects/${id}/duplicate`),
};
