import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

/**
 * Testes de ponta a ponta: sobem o serviço FastAPI real (pasta de dados temporária,
 * isolada dos dados do usuário) e o frontend Vite, e controlam um Chromium.
 *
 * Variáveis opcionais:
 *   BIM_SCHEDULE_PYTHON   interpretador Python com as dependências do backend
 *                         (padrão: "python" no Windows e "python3" nos demais)
 *   E2E_API_PORT          porta do serviço de teste (padrão 8765)
 *   E2E_WEB_PORT          porta do frontend de teste (padrão 4174)
 */
const apiPort = Number(process.env.E2E_API_PORT ?? 8765);
const webPort = Number(process.env.E2E_WEB_PORT ?? 4174);
const python = process.env.BIM_SCHEDULE_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3');
const dataDir = mkdtempSync(join(tmpdir(), 'bim-schedule-e2e-'));

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: 'off',
    ...devices['Desktop Chrome'],
  },
  webServer: [
    {
      command: `"${python}" -m app --port ${apiPort}`,
      cwd: resolve(here, '../backend'),
      url: `http://127.0.0.1:${apiPort}/api/v1/system/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        BIM_SCHEDULE_DATA_DIR: join(dataDir, 'data'),
        BIM_SCHEDULE_LEGACY_DIR: join(dataDir, 'legacy'),
        BIM_SCHEDULE_CORS_ORIGINS: JSON.stringify([`http://127.0.0.1:${webPort}`]),
        BIM_SCHEDULE_LOG_LEVEL: 'WARNING',
        PYTHONPATH: resolve(here, '../backend'),
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${webPort} --strictPort`,
      url: `http://127.0.0.1:${webPort}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { BIM_SCHEDULE_API_PROXY: `http://127.0.0.1:${apiPort}` },
    },
  ],
});
