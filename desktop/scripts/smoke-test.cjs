/*
 * Teste de fumaça do aplicativo desktop EMPACOTADO (dist/win-unpacked/BIM SCHEDULE.exe).
 *
 *   node scripts/smoke-test.cjs [caminho-do-ifc] [--exe <caminho>] [--keep-data]
 *
 * Usa uma pasta de dados temporária (não toca em %LOCALAPPDATA%\BIM-SCHEDULE).
 * Verifica: abertura sem terminal, conexão ao serviço (token + CORS app://), criação de
 * projeto, importação de IFC em processo separado, visualizador 3D (WASM via app://),
 * CPM e encerramento do serviço ao fechar a janela.
 */
'use strict';

const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const { execFileSync } = require('node:child_process');

const repo = path.resolve(__dirname, '..', '..');
const { _electron: electron } = require(path.join(repo, 'frontend', 'node_modules', 'playwright'));

const argv = process.argv.slice(2);
const exeIdx = argv.indexOf('--exe');
const exe = exeIdx >= 0 ? argv[exeIdx + 1] : path.join(repo, 'desktop', 'dist', 'win-unpacked', 'BIM SCHEDULE.exe');
const keepData = argv.includes('--keep-data');
const ifcArg = argv.find((a, i) => !a.startsWith('--') && argv[i - 1] !== '--exe');
const ifc = ifcArg || path.join(repo, 'frontend', 'tests', 'e2e', 'fixtures', 'edificio-teste.ifc');
const shots = path.join(repo, 'desktop', 'dist', 'smoke');
fs.mkdirSync(shots, { recursive: true });

const results = [];
function step(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'OK  ' : 'FALHA'} ${name}${detail ? ' — ' + detail : ''}`);
}

function serviceProcesses() {
  try {
    return execFileSync('tasklist', ['/FI', 'IMAGENAME eq bim-schedule-service.exe', '/FO', 'CSV', '/NH'], { encoding: 'utf8' })
      .split(/\r?\n/).filter((l) => l.includes('bim-schedule-service.exe')).length;
  } catch { return -1; }
}

(async () => {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bim-schedule-desktop-smoke-'));
  const before = serviceProcesses();
  const t0 = Date.now();
  const app = await electron.launch({ executablePath: exe, env: { ...process.env, BIM_SCHEDULE_DATA_DIR: dataDir } });
  let page;
  try {
    page = await app.firstWindow();
    const consoleErrors = [];
    page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
    page.on('pageerror', (e) => consoleErrors.push(String(e)));

    await page.getByRole('heading', { name: /Gerenciamento de Projetos/ }).waitFor({ timeout: 120_000 });
    step('Abre a interface conectada ao serviço', true, `${((Date.now() - t0) / 1000).toFixed(1)} s até a tela de projetos; URL ${page.url()}`);
    const version = await page.getByText(/^v0\.6\.0/).first().textContent().catch(() => null);
    step('Versão lida do serviço', !!version, version || '');

    const code = `SMOKE-${Date.now().toString(36).toUpperCase()}`;
    await page.getByRole('button', { name: 'Novo Projeto' }).click();
    const form = page.locator('form').filter({ hasText: 'Nome do Projeto' });
    await form.locator('input[type="text"]').nth(0).fill('Teste desktop');
    await form.locator('input[type="text"]').nth(1).fill(code);
    await form.getByRole('button', { name: /Salvar Projeto/ }).click();
    await page.getByText(`Projeto ${code} criado e salvo.`).waitFor();
    step('Cria projeto (POST com token e Origin app://bim-schedule)', true, code);

    const card = page.locator('div').filter({ hasText: code }).filter({ has: page.getByRole('button', { name: /Abrir Projeto/ }) }).last();
    await card.getByRole('button', { name: /Abrir Projeto/ }).click();
    await page.getByRole('button', { name: /Modelos IFC/ }).click();
    const t1 = Date.now();
    await page.locator('input[type="file"]').setInputFiles(ifc);
    const done = page.getByText('Processamento IFC concluído.');
    const failedJob = page.locator('[aria-live="polite"]').filter({ hasText: 'Processamento IFC' }).getByText(/Falhou|Falha|Erro/);
    await done.or(failedJob).first().waitFor({ timeout: 30 * 60_000 });
    if (!(await done.isVisible())) throw new Error(`Processamento IFC falhou: ${await failedJob.first().textContent()}`);
    const count = await page.getByText(/Elementos \(\d+\)/).first().textContent();
    step('Importa e processa IFC em processo separado', true, `${path.basename(ifc)}: ${count}, ${((Date.now() - t1) / 1000).toFixed(1)} s`);

    // Visualizador 3D
    await page.locator('canvas').first().waitFor({ timeout: 30_000 });
    const t2 = Date.now();
    const loading = page.getByText('Carregando geometria IFC…');
    await loading.waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
    await loading.waitFor({ state: 'hidden', timeout: 10 * 60_000 });
    const viewerError = await page.getByText(/Falha ao carregar o IFC/).count();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(shots, 'viewer-3d.png') });
    step('Visualizador 3D carrega o modelo (web-ifc WASM via app://)', viewerError === 0, `${((Date.now() - t2) / 1000).toFixed(1)} s; captura em desktop/dist/smoke/viewer-3d.png`);

    // CPM
    await page.getByRole('button', { name: /Gráfico de Gantt/ }).click();
    const af = page.locator('form').filter({ hasText: 'Nova atividade' });
    for (const [c, n, d] of [['A-01', 'Escavação', '3'], ['A-02', 'Fundação', '4']]) {
      await af.getByPlaceholder('EST-001').fill(c);
      await af.getByPlaceholder('Execução das fundações').fill(n);
      await af.locator('input[type="number"]').fill(d);
      await af.getByRole('button', { name: /Adicionar atividade/ }).click();
      await page.locator('table').getByText(c).waitFor();
    }
    const rel = page.locator('form').filter({ hasText: 'Nova precedência' });
    await rel.locator('select').nth(0).selectOption({ label: 'A-01 — Escavação' });
    await rel.locator('select').nth(1).selectOption({ label: 'A-02 — Fundação' });
    await rel.getByRole('button', { name: 'Adicionar relação' }).click();
    await page.getByRole('button', { name: /Calcular CPM/ }).click();
    await page.getByText(/Duração calculada: 7 dias/).waitFor();
    await page.screenshot({ path: path.join(shots, 'gantt-cpm.png') });
    step('Calcula CPM pelo motor do serviço', true, 'Duração calculada: 7 dias');

    const relevant = consoleErrors.filter((e) => !/favicon/i.test(e));
    step('Sem erros de JavaScript no console', relevant.length === 0, relevant.slice(0, 5).join(' | '));
  } catch (err) {
    step('Execução do teste', false, String(err && err.message || err).split('\n')[0]);
    if (page) await page.screenshot({ path: path.join(shots, 'falha.png') }).catch(() => {});
  } finally {
    await app.close().catch(() => {});
  }
  await new Promise((r) => setTimeout(r, 3000));
  const after = serviceProcesses();
  step('Serviço encerrado ao fechar o app', after <= before, `processos bim-schedule-service.exe antes=${before}, depois=${after}`);
  if (!keepData) fs.rmSync(dataDir, { recursive: true, force: true });
  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} verificações aprovadas.`);
  process.exit(failed ? 1 : 0);
})();
