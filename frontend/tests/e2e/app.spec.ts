import { expect, Page, test } from '@playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

const unique = () => `E2E-${Date.now().toString(36).toUpperCase()}`;

async function createProject(page: Page, name: string, code: string) {
  await page.getByRole('button', { name: 'Novo Projeto' }).click();
  const dialog = page.locator('form').filter({ hasText: 'Nome do Projeto' });
  await dialog.locator('input[type="text"]').nth(0).fill(name);
  await dialog.locator('input[type="text"]').nth(1).fill(code);
  await dialog.getByRole('button', { name: /Salvar Projeto/ }).click();
}

test('abre a aplicação principal (sem iframe nem parâmetro ?connected) conectada ao serviço', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Gerenciamento de Projetos/ })).toBeVisible();
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(page.getByText(/^v0\.6\.0-dev/)).toBeVisible(); // versão lida do backend
});

test('cria um projeto, persiste no banco e o recupera após recarregar', async ({ page, request }) => {
  const code = unique();
  await page.goto('/');
  await createProject(page, 'Edifício E2E', code);
  await expect(page.getByText(`Projeto ${code} criado e salvo.`)).toBeVisible();
  await expect(page.getByText(code, { exact: true })).toBeVisible();

  // Gravado no backend (consulta direta à API, sem passar pela interface).
  const projects = await (await request.get('/api/v1/projects/')).json();
  expect(projects.some((p: { code: string }) => p.code === code)).toBe(true);

  await page.reload();
  await expect(page.getByText(code, { exact: true })).toBeVisible();
});

test('exibe o erro devolvido pelo backend (código duplicado)', async ({ page }) => {
  const code = unique();
  await page.goto('/');
  await createProject(page, 'Primeiro', code);
  await expect(page.getByText(`Projeto ${code} criado e salvo.`)).toBeVisible();
  await createProject(page, 'Segundo', code);
  await expect(page.getByText('Projeto com este código já existe.')).toBeVisible();
});

test('fluxo de planejamento: atividade, precedência e CPM calculados pelo backend', async ({ page }) => {
  const code = unique();
  await page.goto('/');
  await createProject(page, 'Planejamento E2E', code);
  const card = page.locator('div').filter({ hasText: code }).filter({ has: page.getByRole('button', { name: /Abrir Projeto/ }) }).last();
  await card.getByRole('button', { name: /Abrir Projeto/ }).click();
  await expect(page.getByText('Painel do projeto')).toBeVisible();

  await page.getByRole('button', { name: /Gráfico de Gantt/ }).click();
  const form = page.locator('form').filter({ hasText: 'Nova atividade' });
  for (const [c, n, d] of [['A-01', 'Escavação', '3'], ['A-02', 'Fundação', '4']]) {
    await form.getByPlaceholder('EST-001').fill(c);
    await form.getByPlaceholder('Execução das fundações').fill(n);
    await form.locator('input[type="number"]').fill(d);
    await form.getByRole('button', { name: /Adicionar atividade/ }).click();
    await expect(page.locator('table').getByText(c)).toBeVisible();
  }
  const rel = page.locator('form').filter({ hasText: 'Nova precedência' });
  await rel.locator('select').nth(0).selectOption({ label: 'A-01 — Escavação' });
  await rel.locator('select').nth(1).selectOption({ label: 'A-02 — Fundação' });
  await rel.getByRole('button', { name: 'Adicionar relação' }).click();
  await page.getByRole('button', { name: /Calcular CPM/ }).click();
  await expect(page.getByText(/Duração calculada: 7 dias/)).toBeVisible();
});

test('processa um IFC real em segundo plano e mostra o progresso da tarefa', async ({ page }) => {
  const code = unique();
  await page.goto('/');
  await createProject(page, 'IFC E2E', code);
  const card = page.locator('div').filter({ hasText: code }).filter({ has: page.getByRole('button', { name: /Abrir Projeto/ }) }).last();
  await card.getByRole('button', { name: /Abrir Projeto/ }).click();
  await page.getByRole('button', { name: /Modelos IFC/ }).click();
  await page.locator('input[type="file"]').setInputFiles(resolve(here, 'fixtures/edificio-teste.ifc'));
  const job = page.locator('[aria-live="polite"]').filter({ hasText: 'Processamento IFC' });
  await expect(job.getByText('Concluída')).toBeVisible();
  await expect(page.getByText('Processamento IFC concluído.')).toBeVisible();
  await expect(page.getByText(/Elementos \(13\)/)).toBeVisible(); // 8 paredes + 2 lajes + terreno, edifício e pavimento
});

test('serviço indisponível: mostra orientação e acesso à demonstração, sem dados simulados', async ({ page }) => {
  // Configuração em tempo de execução apontando para uma porta sem serviço (conexão recusada real).
  await page.route('**/runtime-config.js', (route) =>
    route.fulfill({ contentType: 'application/javascript', body: 'window.__BIM_SCHEDULE_CONFIG__ = { apiBaseUrl: "http://127.0.0.1:9/api/v1" };' }),
  );
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Serviço BIM SCHEDULE não encontrado' })).toBeVisible();
  await expect(page.getByText('Endereço configurado: http://127.0.0.1:9/api/v1')).toBeVisible();
  await expect(page.getByText(/Não foi possível conectar ao serviço/)).toBeVisible();
  await expect(page.getByRole('link', { name: /Abrir demonstração/ })).toHaveAttribute('href', './demo.html');
  await expect(page.getByRole('heading', { name: /Gerenciamento de Projetos/ })).toHaveCount(0);
});

test('requisição sem conexão durante o uso mostra erro de conexão no formulário', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Gerenciamento de Projetos/ })).toBeVisible();
  await page.route('**/api/v1/**', (route) => route.abort('connectionrefused'));
  await page.getByRole('button', { name: 'Novo Projeto' }).click();
  const dialog = page.locator('form').filter({ hasText: 'Nome do Projeto' });
  await dialog.locator('input[type="text"]').nth(0).fill('Sem conexão');
  await dialog.getByRole('button', { name: /Salvar Projeto/ }).click();
  await expect(dialog.getByText(/Não foi possível conectar ao serviço/)).toBeVisible();
  await page.unroute('**/api/v1/**');
});

test('a demonstração estática continua disponível e identificada', async ({ page }) => {
  await page.goto('/demo.html');
  await expect(page.getByText('AMBIENTE DEMONSTRATIVO')).toBeVisible();
});

test('gera o cronograma a partir do IFC: quantitativos, pré-visualização, aceite e Gantt', async ({ page }) => {
  test.setTimeout(120_000);
  const code = unique();
  await page.goto('/');
  await createProject(page, 'Gerador E2E', code);
  const card = page.locator('div').filter({ hasText: code }).filter({ has: page.getByRole('button', { name: /Abrir Projeto/ }) }).last();
  await card.getByRole('button', { name: /Abrir Projeto/ }).click();
  await page.getByRole('button', { name: /Modelos IFC/ }).click();
  await page.locator('input[type="file"]').setInputFiles(resolve(here, 'fixtures/edificio-teste.ifc'));
  await expect(page.getByText('Processamento IFC concluído.')).toBeVisible();

  await page.getByRole('button', { name: /Gerar Cronograma/ }).click();
  await expect(page.getByRole('heading', { name: /Gerar cronograma a partir do IFC/ })).toBeVisible();
  await page.getByRole('button', { name: /Calcular quantitativos dos selecionados/ }).click();
  await expect(page.locator('[data-testid^="takeoff-status-"]').first()).toHaveText('Concluído', { timeout: 60_000 });

  await page.getByRole('button', { name: /Pré-visualizar cronograma/ }).click();
  await expect(page.getByTestId('proposal-01-ALV')).toBeVisible();
  await expect(page.getByTestId('proposal-01-ALV').getByText('provisória')).toBeVisible(); // sem produtividade
  await page.getByLabel('Duração 01-LAJ').fill('4');
  await page.getByRole('button', { name: /Aceitar e criar cronograma/ }).click();
  await expect(page.getByTestId('generator-result')).toContainText('CPM calculado');

  await page.getByRole('button', { name: 'Abrir Gráfico de Gantt' }).click();
  await expect(page.locator('table').getByText('G1-01-LAJ')).toBeVisible();
  await expect(page.locator('table').getByText('G1-01-ALV')).toBeVisible();
  await expect(page.locator('table tr').filter({ hasText: 'G1-01-ALV' }).getByText('provisória')).toBeVisible();
  await expect(page.locator('table tr').filter({ hasText: 'G1-01-LAJ' }).getByText('provisória')).toHaveCount(0);
});
