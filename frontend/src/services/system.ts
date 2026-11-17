import { SystemStatus } from '../types/api';
import { apiGet } from './apiClient';

const STATUS_TIMEOUT_MS = 5_000;

export const systemService = {
  status: (signal?: AbortSignal) => apiGet<SystemStatus>('/system/status', { signal, timeout: STATUS_TIMEOUT_MS }),
};
