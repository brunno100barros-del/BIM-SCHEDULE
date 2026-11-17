/**
 * Monta o site estático do GitHub Pages (pasta pages-dist/).
 *
 * Decisão da Etapa 2: o GitHub Pages continua publicando a DEMONSTRAÇÃO na raiz.
 * A aplicação React depende do serviço local (FastAPI), que o GitHub Pages não
 * executa; por isso ela não é publicada no Pages. Ela é a aplicação principal das
 * versões local e Windows. Uma edição Web completa exigirá um backend remoto
 * (ver docs/architecture/ARCHITECTURE.md).
 */
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const publicDir = join(root, 'public');
const out = join(root, 'pages-dist');

const required = ['demo.html', 'schedule-enhancements.js'];
for (const file of required) {
  if (!existsSync(join(publicDir, file))) throw new Error(`Arquivo da demonstração ausente: public/${file}`);
}

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
for (const file of required) cpSync(join(publicDir, file), join(out, file));
// Raiz do site = demonstração (mesmo conteúdo de demo.html).
writeFileSync(join(out, 'index.html'), readFileSync(join(publicDir, 'demo.html')));
writeFileSync(join(out, '.nojekyll'), '');
console.log(`GitHub Pages: demonstração montada em ${out}`);
