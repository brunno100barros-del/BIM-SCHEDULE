import fs from 'fs';

// O visualizador usa o IFCLoader do web-ifc-three, que depende da sua PRÓPRIA versão do
// web-ifc (hoje 0.0.39, instalada em node_modules/web-ifc-three/node_modules/web-ifc).
// O arquivo .wasm precisa ser da mesma versão do código JavaScript que o carrega; copiar o
// web-ifc da raiz (0.0.50) causa "WebAssembly.instantiate(): Import #49 ... requires a callable".
const candidates = [
  'node_modules/web-ifc-three/node_modules/web-ifc',
  'node_modules/web-ifc',
];

fs.mkdirSync('public', { recursive: true });
const source = candidates.find((dir) => fs.existsSync(`${dir}/web-ifc.wasm`));
if (!source) {
  console.log('WASM files will be copied after npm install.');
} else {
  fs.copyFileSync(`${source}/web-ifc.wasm`, 'public/web-ifc.wasm');
  if (fs.existsSync(`${source}/web-ifc-mt.wasm`)) fs.copyFileSync(`${source}/web-ifc-mt.wasm`, 'public/web-ifc-mt.wasm');
  const version = JSON.parse(fs.readFileSync(`${source}/package.json`, 'utf8')).version;
  console.log(`Web-IFC WASM ${version} copied to public directory (from ${source}).`);
}
