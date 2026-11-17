import { describe, expect, it } from 'vitest';
import { resolveRuntimeConfig } from '../../src/config/runtime';

describe('resolveRuntimeConfig', () => {
  it('usa o proxy do Vite por padrão', () => {
    expect(resolveRuntimeConfig(undefined, undefined)).toEqual({ apiBaseUrl: '/api/v1', apiToken: undefined, mode: 'local' });
  });

  it('prioriza a configuração em tempo de execução (app Windows) sobre a de compilação', () => {
    const config = resolveRuntimeConfig(
      { apiBaseUrl: 'http://127.0.0.1:8732/api/v1/', apiToken: ' abc ', mode: 'desktop' },
      'https://servidor.exemplo/api/v1',
    );
    expect(config).toEqual({ apiBaseUrl: 'http://127.0.0.1:8732/api/v1', apiToken: 'abc', mode: 'desktop' });
  });

  it('usa VITE_API_BASE_URL quando não há configuração em tempo de execução', () => {
    expect(resolveRuntimeConfig({}, 'https://servidor.exemplo/api/v1').apiBaseUrl).toBe('https://servidor.exemplo/api/v1');
  });

  it('ignora valores inválidos', () => {
    const config = resolveRuntimeConfig({ apiBaseUrl: 42, apiToken: '', mode: 'qualquer' }, '');
    expect(config).toEqual({ apiBaseUrl: '/api/v1', apiToken: undefined, mode: 'local' });
  });
});
