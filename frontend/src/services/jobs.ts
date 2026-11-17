import { Job } from '../types/api';
import { apiGet, apiPost } from './apiClient';

export const TERMINAL_JOB_STATUSES = ['completed', 'failed', 'cancelled', 'interrupted'] as const;

export const jobService = {
  get: (id: string, signal?: AbortSignal) => apiGet<Job>(`/jobs/${id}`, { signal }),
  list: (params: { project_id?: number; kind?: string; limit?: number } = {}, signal?: AbortSignal) =>
    apiGet<Job[]>('/jobs/', { params, signal }),
  cancel: (id: string) => apiPost<Job>(`/jobs/${id}/cancel`),
};
