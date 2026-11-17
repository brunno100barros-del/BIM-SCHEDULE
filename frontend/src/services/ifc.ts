import { IfcElement, IfcModel, IfcUploadResult } from '../types/api';
import { apiGet, apiPost, apiUrl } from './apiClient';

const UPLOAD_TIMEOUT_MS = 10 * 60_000;

export const ifcService = {
  listModels: (projectId: number, signal?: AbortSignal) => apiGet<IfcModel[]>(`/ifc/project/${projectId}/models`, { signal }),
  listElements: (modelId: number, limit = 1000, signal?: AbortSignal) =>
    apiGet<IfcElement[]>(`/ifc/model/${modelId}/elements`, { params: { limit }, signal }),
  upload: (projectId: number, file: File, onUploadProgress?: (percent: number) => void, signal?: AbortSignal) => {
    const form = new FormData();
    form.append('file', file);
    return apiPost<IfcUploadResult>(`/ifc/project/${projectId}/upload`, form, {
      timeout: UPLOAD_TIMEOUT_MS,
      signal,
      onUploadProgress: (event) => {
        if (onUploadProgress && event.total) onUploadProgress(Math.round((event.loaded / event.total) * 100));
      },
    });
  },
  downloadUrl: (modelId: number) => apiUrl(`/ifc/model/${modelId}/download`),
};
