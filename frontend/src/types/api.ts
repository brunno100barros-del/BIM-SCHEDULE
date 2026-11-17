/** Tipos das respostas do backend usados por mais de um módulo. */

export type JobStatus = 'queued' | 'running' | 'cancelling' | 'completed' | 'failed' | 'cancelled' | 'interrupted';

export interface Job {
  id: string;
  kind: string;
  project_id: number | null;
  status: JobStatus;
  progress: number;
  message: string | null;
  error: string | null;
  result: unknown;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
  updated_at: string;
  finished_at: string | null;
  is_terminal: boolean;
}

export type CapabilityState = 'available' | 'experimental' | 'not_implemented';

export interface SystemStatus {
  app: string;
  version: string;
  api_version: string;
  environment: string;
  started_at: string | null;
  database: { ok: boolean; revision?: string | null; error?: string };
  storage: {
    mode: 'data_dir' | 'legacy' | 'explicit_database_url';
    data_dir: string;
    database_path: string | null;
    uploads_dir: string;
    legacy_data_detected: boolean;
    migration: { status: string; message: string } | null;
  };
  jobs: { max_workers: number; running: number };
  ai: { provider: string };
  security: { local_token_required: boolean };
  capabilities: Record<string, CapabilityState>;
}

export interface Activity {
  id: number;
  project_id: number;
  wbs_id?: number | null;
  name: string;
  code: string;
  description?: string | null;
  duration: number;
  status: string;
  percent_complete: number;
  es: number; ef: number; ls: number; lf: number; tf: number; ff: number;
  is_critical: number;
}

export interface Precedence { id: number; predecessor_id: number; successor_id: number; relation_type: string; lag: number }

export interface WbsNode { id: number; project_id: number; name: string; code: string; description?: string | null; parent_id?: number | null; sort_order: number }

export interface CpmSummary {
  status: 'success' | 'empty';
  message?: string;
  duration?: number;
  project_finish?: number;
  project_deadline?: number | null;
  deadline_variance?: number | null;
  deadline_feasible?: boolean;
  activities?: Record<string, unknown>;
}

export interface IfcModel {
  id: number;
  project_id: number;
  filename: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled' | string;
  progress: number;
  processing_message?: string | null;
  error_message?: string | null;
  element_count: number;
  schema_name?: string | null;
  version: number;
  job_id?: string | null;
}

export interface IfcElement { id: number; global_id: string; name: string; ifc_type: string; description?: string | null; storey_name?: string | null }

export interface IfcUploadResult { id: number; filename: string; version: number; status: string; size_bytes: number; sha256: string; job_id: string; message: string }
