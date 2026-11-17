/**
 * Configuração de execução do frontend.
 *
 * Ordem de precedência para o endereço da API:
 *  1. `window.__BIM_SCHEDULE_CONFIG__.apiBaseUrl` — definido em tempo de execução
 *     por `runtime-config.js` (no aplicativo Windows, gerado pelo handler do protocolo app://);
 *  2. `VITE_API_BASE_URL` — definido na compilação (ex.: edição Web com backend remoto);
 *  3. `/api/v1` — proxy do servidor de desenvolvimento do Vite.
 */
export type RuntimeMode = 'local' | 'desktop' | 'remote';

export interface RuntimeConfig {
  apiBaseUrl: string;
  apiToken?: string;
  mode: RuntimeMode;
}

interface RawRuntimeConfig {
  apiBaseUrl?: unknown;
  apiToken?: unknown;
  mode?: unknown;
}

declare global {
  interface Window {
    __BIM_SCHEDULE_CONFIG__?: RawRuntimeConfig;
  }
}

const DEFAULT_API_BASE_URL = '/api/v1';

function clean(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

export function resolveRuntimeConfig(
  raw: RawRuntimeConfig | undefined = typeof window !== 'undefined' ? window.__BIM_SCHEDULE_CONFIG__ : undefined,
  buildBaseUrl: string | undefined = import.meta.env.VITE_API_BASE_URL,
): RuntimeConfig {
  const apiBaseUrl = (clean(raw?.apiBaseUrl) ?? clean(buildBaseUrl) ?? DEFAULT_API_BASE_URL).replace(/\/+$/, '');
  const mode = raw?.mode === 'desktop' || raw?.mode === 'remote' ? raw.mode : 'local';
  return { apiBaseUrl, apiToken: clean(raw?.apiToken), mode };
}

let current: RuntimeConfig | null = null;

export function getRuntimeConfig(): RuntimeConfig {
  if (!current) current = resolveRuntimeConfig();
  return current;
}

/** Usado em testes e pelo app desktop caso o endereço mude após a inicialização. */
export function setRuntimeConfig(config: RuntimeConfig | null): void {
  current = config;
}
