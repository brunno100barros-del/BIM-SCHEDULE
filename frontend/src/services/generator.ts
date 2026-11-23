import { apiGet, apiPost, apiPut } from './apiClient';

/** Quantitativos por elemento (/takeoff) e gerador de cronograma por regras (/schedule-generator). */

export type TakeoffStatus = 'none' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';

export interface TakeoffTotalsRow { count: number; volume_m3: number; area_m2: number; length_m: number; weight_kg: number; with_geometry: number }

export interface TakeoffModel {
  model_id: number;
  filename: string;
  model_status: string;
  status: TakeoffStatus;
  job_id: string | null;
  error_message: string | null;
  is_current: boolean;
  element_count: number;
  summary: null | {
    application: string;
    schema: string;
    units: Record<string, string>;
    elements: number;
    included: number;
    excluded: number;
    with_geometry: number;
    geometry_attempted: number;
    sources_by_measure: Record<string, Record<string, number>>;
  };
  totals?: { by_type: Record<string, TakeoffTotalsRow>; by_storey: Record<string, number> };
}

export type QuantityBasis = 'volume_m3' | 'area_m2' | 'length_m' | 'weight_kg' | 'count';

export interface ScheduleService {
  id: number;
  project_id: number;
  code: string;
  name: string;
  discipline: string | null;
  sequence: number;
  quantity_basis: QuantityBasis;
  unit: string;
  ifc_types: string;
  quantity_ifc_types: string | null;
  material_class: string | null;
  predecessors: string | null;
  after_previous_level: string | null;
  productivity_per_day: number | null;
  productivity_note: string | null;
  default_duration_days: number;
  is_active: boolean;
  include_by_default: boolean;
}

export type LevelMode = 'auto' | 'storey' | 'elevation';

export interface ProposalActivity {
  key: string;
  level_key: string;
  level_name: string;
  level_order: number;
  service_code: string;
  service_name: string;
  code: string;
  name: string;
  quantity: number;
  unit: string;
  quantity_basis: QuantityBasis;
  coverage: number;
  productivity: number | null;
  duration: number;
  provisional: boolean;
  provisional_reason: string | null;
  element_count: number;
  include: boolean;
  has_predecessor: boolean;
}

export interface Proposal {
  level_mode: 'storey' | 'elevation';
  levels: { key: string; name: string; order: number; elevation_m: number | null; element_count: number }[];
  activities: ProposalActivity[];
  precedences: { pred_key: string; succ_key: string; relation_type: string; lag: number; rule: string }[];
  unmapped: Record<string, number>;
  warnings: string[];
  stats: { elements: number; activities: number; provisional: number; precedences: number };
}

export interface ApplyResult {
  generation_id: number;
  number: number;
  activities: number;
  precedences: number;
  element_links: number;
  provisional: number;
  removed_previous: number;
  warnings: string[];
  cpm: { status: string; duration?: number; critical_activities?: number; deadline_feasible?: boolean; project_deadline?: number | null; message?: string } | null;
}

export interface GeneratorOptions { model_ids: number[]; level_mode: LevelMode; band_height_m: number }

export interface ActivityOverride { key: string; include?: boolean; name?: string; duration?: number }

export const generatorService = {
  projectModels: (projectId: number, signal?: AbortSignal) => apiGet<TakeoffModel[]>(`/takeoff/project/${projectId}/models`, { signal }),
  modelTakeoff: (modelId: number, signal?: AbortSignal) => apiGet<TakeoffModel>(`/takeoff/model/${modelId}`, { signal }),
  startTakeoff: (modelId: number) => apiPost<{ model_id: number; job_id: string; status: string }>(`/takeoff/model/${modelId}`),

  listServices: (projectId: number, signal?: AbortSignal) => apiGet<ScheduleService[]>(`/schedule-generator/project/${projectId}/services`, { signal }),
  resetServices: (projectId: number) => apiPost<ScheduleService[]>(`/schedule-generator/project/${projectId}/services/reset`),
  updateService: (id: number, data: Partial<ScheduleService> & { clear_productivity?: boolean }) =>
    apiPut<ScheduleService>(`/schedule-generator/services/${id}`, data),

  preview: (projectId: number, options: GeneratorOptions) =>
    apiPost<Proposal>(`/schedule-generator/project/${projectId}/preview`, options, { timeout: 120_000 }),
  apply: (projectId: number, options: GeneratorOptions & { overrides: ActivityOverride[]; replace_previous: boolean; run_cpm: boolean }) =>
    apiPost<ApplyResult>(`/schedule-generator/project/${projectId}/apply`, options, { timeout: 300_000 }),
  activityFlags: (projectId: number, signal?: AbortSignal) =>
    apiGet<Record<string, { provisional: boolean; reason: string | null; service_code: string | null; coverage: number | null }>>(
      `/schedule-generator/project/${projectId}/activity-flags`, { signal }),
};
