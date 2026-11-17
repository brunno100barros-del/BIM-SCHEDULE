/**
 * Cliente HTTP único da aplicação.
 *
 * Todo acesso ao backend passa por aqui: endereço vindo da configuração de
 * execução, token local, tempo limite, cancelamento (AbortSignal) e erros
 * convertidos em {@link ApiError} com mensagem em português.
 */
import axios, { AxiosError, AxiosInstance, AxiosRequestConfig } from 'axios';
import { getRuntimeConfig, RuntimeConfig } from '../config/runtime';

export const TOKEN_HEADER = 'X-BIM-Schedule-Token';
export const DEFAULT_TIMEOUT_MS = 30_000;

export type ApiErrorKind = 'network' | 'timeout' | 'cancelled' | 'http' | 'unknown';

/** Formato de erro padronizado do backend (ver backend/app/core/errors.py). */
interface BackendErrorBody {
  error?: { code?: string; message?: string; details?: unknown; request_id?: string };
  detail?: unknown;
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly code?: string;
  readonly details?: unknown;
  readonly requestId?: string;

  constructor(kind: ApiErrorKind, message: string, extra: { status?: number; code?: string; details?: unknown; requestId?: string } = {}) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = extra.status;
    this.code = extra.code;
    this.details = extra.details;
    this.requestId = extra.requestId;
  }

  /** O backend não respondeu (serviço parado, porta errada, rede). */
  get isUnavailable(): boolean {
    return this.kind === 'network' || this.kind === 'timeout';
  }
}

const HTTP_FALLBACK: Record<number, string> = {
  400: 'Requisição inválida.',
  401: 'Acesso não autorizado ao serviço local.',
  403: 'Operação não permitida.',
  404: 'Registro não encontrado.',
  409: 'Conflito com dados existentes.',
  413: 'Arquivo muito grande.',
  422: 'Dados inválidos.',
  500: 'Erro interno no serviço BIM SCHEDULE.',
  502: 'Serviço BIM SCHEDULE indisponível.',
  503: 'Serviço BIM SCHEDULE indisponível.',
  504: 'O serviço BIM SCHEDULE não respondeu a tempo.',
};

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (axios.isCancel(error)) return new ApiError('cancelled', 'Operação cancelada.');
  if (axios.isAxiosError(error)) {
    const err = error as AxiosError<BackendErrorBody>;
    if (err.code === 'ECONNABORTED' || err.code === 'ETIMEDOUT') {
      return new ApiError('timeout', 'O serviço BIM SCHEDULE não respondeu a tempo.');
    }
    if (!err.response) {
      return new ApiError('network', 'Não foi possível conectar ao serviço BIM SCHEDULE. Verifique se ele está em execução.');
    }
    const { status, data } = err.response;
    // O proxy do Vite responde 502/504 quando o backend está parado.
    if ((status === 502 || status === 504) && !data?.error) {
      return new ApiError('network', 'Não foi possível conectar ao serviço BIM SCHEDULE. Verifique se ele está em execução.', { status });
    }
    const body = data?.error;
    const detail = typeof data?.detail === 'string' ? data.detail : undefined;
    const message = body?.message || detail || HTTP_FALLBACK[status] || `Erro ${status} na requisição.`;
    return new ApiError('http', message, { status, code: body?.code, details: body?.details, requestId: body?.request_id });
  }
  if (error instanceof Error) return new ApiError('unknown', error.message);
  return new ApiError('unknown', 'Erro inesperado.');
}

/** Mensagem pronta para exibir ao usuário. */
export function getErrorMessage(error: unknown, fallback?: string): string {
  const apiError = toApiError(error);
  if (apiError.kind === 'unknown' && fallback) return fallback;
  return apiError.message || fallback || 'Erro inesperado.';
}

export function createApiClient(config: RuntimeConfig = getRuntimeConfig()): AxiosInstance {
  const instance = axios.create({ baseURL: config.apiBaseUrl, timeout: DEFAULT_TIMEOUT_MS });
  instance.interceptors.request.use((request) => {
    if (config.apiToken) request.headers.set(TOKEN_HEADER, config.apiToken);
    return request;
  });
  instance.interceptors.response.use(undefined, (error) => Promise.reject(toApiError(error)));
  return instance;
}

let client: AxiosInstance | null = null;

export function getApiClient(): AxiosInstance {
  if (!client) client = createApiClient();
  return client;
}

/** Substitui o cliente (testes ou mudança de endereço do serviço). */
export function setApiClient(instance: AxiosInstance | null): void {
  client = instance;
}

/** URL absoluta (ou relativa ao app) para recursos baixados fora do axios, como o IFC no visualizador. */
export function apiUrl(path: string): string {
  return `${getRuntimeConfig().apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`;
}

/** Cabeçalhos necessários para downloads feitos fora do axios. */
export function apiAuthHeaders(): Record<string, string> {
  const token = getRuntimeConfig().apiToken;
  return token ? { [TOKEN_HEADER]: token } : {};
}

export async function apiGet<T>(path: string, config?: AxiosRequestConfig): Promise<T> {
  return (await getApiClient().get<T>(path, config)).data;
}

export async function apiPost<T>(path: string, body?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await getApiClient().post<T>(path, body, config)).data;
}

export async function apiPut<T>(path: string, body?: unknown, config?: AxiosRequestConfig): Promise<T> {
  return (await getApiClient().put<T>(path, body, config)).data;
}

export async function apiDelete(path: string, config?: AxiosRequestConfig): Promise<void> {
  await getApiClient().delete(path, config);
}
