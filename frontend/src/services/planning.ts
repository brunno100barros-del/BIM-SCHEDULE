import { Activity, CpmSummary, Precedence, WbsNode } from '../types/api';
import { apiDelete, apiGet, apiPost, apiPut } from './apiClient';

/** Planejamento: EAP, atividades, precedências e CPM (rotas /activities, mantidas por compatibilidade). */
export const planningService = {
  listActivities: (projectId: number, signal?: AbortSignal) => apiGet<Activity[]>(`/activities/project/${projectId}`, { signal }),
  createActivity: (data: { project_id: number; wbs_id: number | null; name: string; code: string; duration: number }) =>
    apiPost<Activity>('/activities/', data),
  updateActivity: (id: number, data: Partial<Activity>) => apiPut<Activity>(`/activities/${id}`, data),
  deleteActivity: (id: number) => apiDelete(`/activities/${id}`),

  listPrecedences: (projectId: number, signal?: AbortSignal) => apiGet<Precedence[]>(`/activities/project/${projectId}/precedences`, { signal }),
  createPrecedence: (data: { predecessor_id: number; successor_id: number; relation_type: string; lag: number }) =>
    apiPost<Precedence>('/activities/precedences', data),
  deletePrecedence: (id: number) => apiDelete(`/activities/precedences/${id}`),

  calculateCpm: (projectId: number) => apiPost<CpmSummary>(`/activities/project/${projectId}/calculate-cpm`),

  listWbs: (projectId: number, signal?: AbortSignal) => apiGet<WbsNode[]>(`/activities/project/${projectId}/wbs`, { signal }),
  createWbs: (data: { project_id: number; name: string; code: string; parent_id: number | null }) => apiPost<WbsNode>('/activities/wbs', data),
  updateWbs: (id: number, data: Partial<WbsNode>) => apiPut<WbsNode>(`/activities/wbs/${id}`, data),
  deleteWbs: (id: number) => apiDelete(`/activities/wbs/${id}`),

  linkIfcElement: (activityId: number, ifcElementId: number) =>
    apiPost(`/activities/${activityId}/ifc-elements`, { ifc_element_id: ifcElementId }),
};
