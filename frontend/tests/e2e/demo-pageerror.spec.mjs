// Garante que a demo estática (demo.html + schedule-enhancements.js) carrega e
// navega por todos os módulos sem nenhum erro JavaScript não tratado (pageerror).
import { test, expect } from "@playwright/test";

test.beforeEach(async ({ context }) => {
  // Mantém o teste determinístico: nenhuma chamada externa (esm.sh, Open-Meteo).
  await context.route(url => !["127.0.0.1", "localhost"].includes(url.hostname), route => route.abort());
});

async function collectErrors(page) {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  return errors;
}

test("demo.html carrega sem pageerror", async ({ page }) => {
  const errors = await collectErrors(page);
  await page.goto("/demo.html");
  await page.waitForLoadState("load");
  await page.waitForTimeout(300);
  expect(errors, errors.join("\n")).toEqual([]);
  await expect(page.locator("#view")).not.toBeEmpty();
});

test("todas as páginas da navegação renderizam sem pageerror", async ({ page }) => {
  const errors = await collectErrors(page);
  await page.goto("/demo.html");
  await page.waitForLoadState("load");
  expect(errors, errors.join("\n")).toEqual([]);
  const pages = await page.locator("#nav button[data-page]").evaluateAll(buttons => buttons.map(b => b.dataset.page));
  expect(pages).toEqual(expect.arrayContaining(["overview", "gantt", "weather", "exchange"]));
  for (const id of pages) {
    await page.locator(`#nav button[data-page="${id}"]`).click();
    await expect(page.locator(`#nav button[data-page="${id}"]`)).toHaveClass(/active/);
    await expect(page.locator("#view")).not.toBeEmpty();
  }
  await page.waitForTimeout(300);
  expect(errors, errors.join("\n")).toEqual([]);
});
