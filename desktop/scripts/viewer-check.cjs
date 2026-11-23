/*
 * Abre o app desktop empacotado com a pasta de dados REAL e verifica o visualizador 3D
 * de cada modelo IFC dos projetos cujo código começa com um prefixo (padrão "TST-").
 *
 *   node scripts/viewer-check.cjs [--prefix TST-] [--out resultado.json]
 *
 * Somente leitura do ponto de vista dos dados: apenas navega e abre os modelos.
 */
'use strict';
const path = require('node:path');
const fs = require('node:fs');
const repo = path.resolve(__dirname, '..', '..');
const { _electron: electron } = require(path.join(repo, 'frontend', 'node_modules', 'playwright'));

const argv = process.argv.slice(2);
const arg = (n, d) => (argv.includes(n) ? argv[argv.indexOf(n) + 1] : d);
const prefix = arg('--prefix', 'TST-');
const out = arg('--out', path.join(repo, 'desktop', 'dist', 'smoke', 'viewer-check.json'));
const shots = path.join(path.dirname(out), 'viewer');
fs.mkdirSync(shots, { recursive: true });
const exe = path.join(repo, 'desktop', 'dist', 'win-unpacked', 'BIM SCHEDULE.exe');

(async () => {
  const app = await electron.launch({ executablePath: exe });
  const results = [];
  try {
    const page = await app.firstWindow();
    await page.getByRole('heading', { name: /Gerenciamento de Projetos/ }).waitFor({ timeout: 120_000 });
    const codes = (await page.getByText(new RegExp(`^${prefix}`)).allTextContents()).map((s) => s.trim());
    for (const code of [...new Set(codes)]) {
      await page.getByRole('button', { name: /Voltar aos projetos/ }).click({ timeout: 3000 }).catch(() => {});
      await page.getByRole('heading', { name: /Gerenciamento de Projetos/ }).waitFor();
      const card = page.locator('div').filter({ hasText: code }).filter({ has: page.getByRole('button', { name: /Abrir Projeto/ }) }).last();
      await card.getByRole('button', { name: /Abrir Projeto/ }).click();
      await page.getByRole('button', { name: /Modelos IFC/ }).click();
      const cards = page.locator('div[role="button"]').filter({ hasText: /\.ifc/i });
      await cards.first().waitFor({ timeout: 30_000 });
      const n = await cards.count();
      for (let i = 0; i < n; i++) {
        const c = cards.nth(i);
        const filename = (await c.locator('p').first().textContent()).trim();
        const metrics = await app.evaluate(async ({ app: a }) => (await a.getAppMetrics()).filter((m) => m.type === 'Tab' || m.type === 'GPU').map((m) => ({ type: m.type, ws: m.memory.workingSetSize })));
        const t0 = Date.now();
        await c.click();
        const loading = page.getByText('Carregando geometria IFC…');
        await loading.waitFor({ state: 'visible', timeout: 4_000 }).catch(() => {});
        let timedOut = false;
        await loading.waitFor({ state: 'hidden', timeout: 10 * 60_000 }).catch(() => { timedOut = true; });
        const seconds = (Date.now() - t0) / 1000;
        const errText = await page.locator('text=/Falha ao carregar o IFC|não contém geometria/').first().textContent({ timeout: 1000 }).catch(() => null);
        await page.waitForTimeout(1500);
        const after = await app.evaluate(async ({ app: a }) => (await a.getAppMetrics()).filter((m) => m.type === 'Tab' || m.type === 'GPU').map((m) => ({ type: m.type, ws: m.memory.workingSetSize })));
        const shot = path.join(shots, `${code}-${i + 1}.png`);
        await page.screenshot({ path: shot });
        const rendererMb = Math.round(Math.max(...after.filter((m) => m.type === 'Tab').map((m) => m.ws)) / 1024);
        const rec = { code, filename, ok: !errText && !timedOut, seconds, error: errText, timedOut, renderer_working_set_mb: rendererMb, screenshot: shot };
        results.push(rec);
        console.log(`${rec.ok ? 'OK   ' : 'FALHA'} ${code} ${filename} — ${seconds.toFixed(1)} s, renderer ${rendererMb} MB${errText ? ' — ' + errText : ''}${timedOut ? ' — tempo esgotado' : ''}`);
        fs.writeFileSync(out, JSON.stringify(results, null, 2));
      }
    }
  } finally {
    await app.close().catch(() => {});
  }
})();
