import { AxiosError, AxiosHeaders, InternalAxiosRequestConfig } from 'axios';
import { describe, expect, it } from 'vitest';
import { ApiError, createApiClient, getErrorMessage, TOKEN_HEADER, toApiError } from '../../src/services/apiClient';

type Adapter = (config: InternalAxiosRequestConfig) => Promise<any>;

function clientWith(adapter: Adapter, token?: string) {
  const client = createApiClient({ apiBaseUrl: 'http://127.0.0.1:9/api/v1', apiToken: token, mode: 'local' });
  client.defaults.adapter = adapter as any;
  return client;
}

function httpError(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  const response = { status, statusText: '', headers: {}, config, data } as any;
  return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_RESPONSE', config, null, response);
}

describe('cliente da API', () => {
  it('usa a URL base configurada e envia o token local', async () => {
    let seen: InternalAxiosRequestConfig | null = null;
    const client = clientWith(async (config) => {
      seen = config;
      return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config };
    }, 'token-123');
    const response = await client.get('/projects/');
    expect(response.data).toEqual({ ok: true });
    expect(seen!.baseURL).toBe('http://127.0.0.1:9/api/v1');
    expect(AxiosHeaders.from(seen!.headers as any).get(TOKEN_HEADER)).toBe('token-123');
  });

  it('converte backend indisponível em erro de rede', async () => {
    const client = clientWith(async (config) => { throw new AxiosError('Network Error', 'ERR_NETWORK', config, {}); });
    const error = await client.get('/projects/').catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.kind).toBe('network');
    expect(error.isUnavailable).toBe(true);
    expect(error.message).toContain('Não foi possível conectar');
  });

  it('trata 502 do proxy do Vite (backend parado) como indisponibilidade', async () => {
    const client = clientWith(async (config) => { throw httpError(config, 502, ''); });
    const error = await client.get('/projects/').catch((e) => e);
    expect(error.kind).toBe('network');
  });

  it('converte tempo esgotado', async () => {
    const client = clientWith(async (config) => { throw new AxiosError('timeout', 'ECONNABORTED', config, {}); });
    const error = await client.get('/x').catch((e) => e);
    expect(error.kind).toBe('timeout');
    expect(error.isUnavailable).toBe(true);
  });

  it('usa a mensagem e o código do envelope padronizado do backend', async () => {
    const client = clientWith(async (config) => {
      throw httpError(config, 409, { error: { code: 'project_code_conflict', message: 'Projeto com este código já existe.', details: null, request_id: 'r1' }, detail: 'Projeto com este código já existe.' });
    });
    const error = await client.post('/projects/', {}).catch((e) => e);
    expect(error.kind).toBe('http');
    expect(error.status).toBe(409);
    expect(error.code).toBe('project_code_conflict');
    expect(error.requestId).toBe('r1');
    expect(getErrorMessage(error)).toBe('Projeto com este código já existe.');
  });

  it('aceita o formato antigo { detail } e mensagens padrão por status', async () => {
    const legacy = clientWith(async (config) => { throw httpError(config, 400, { detail: 'Ciclo detectado' }); });
    expect((await legacy.get('/x').catch((e) => e)).message).toBe('Ciclo detectado');
    const bare = clientWith(async (config) => { throw httpError(config, 404, null); });
    expect((await bare.get('/x').catch((e) => e)).message).toBe('Registro não encontrado.');
  });

  it('identifica cancelamento por AbortSignal', async () => {
    const controller = new AbortController();
    const client = clientWith((config) => new Promise((_resolve, reject) => {
      config.signal?.addEventListener?.('abort', () => reject(new AxiosError('canceled', AxiosError.ERR_CANCELED, config)));
    }));
    const pending = client.get('/lento', { signal: controller.signal }).catch((e) => e);
    controller.abort();
    const error = await pending;
    expect(error.kind).toBe('cancelled');
  });

  it('getErrorMessage usa o texto alternativo para erros desconhecidos', () => {
    expect(getErrorMessage({}, 'Falha ao salvar.')).toBe('Falha ao salvar.');
    expect(toApiError(new Error('x')).kind).toBe('unknown');
  });
});
