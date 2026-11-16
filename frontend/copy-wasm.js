import fs from 'fs';
fs.mkdirSync('public', { recursive: true });
try {
  fs.copyFileSync('node_modules/web-ifc/web-ifc.wasm', 'public/web-ifc.wasm');
  fs.copyFileSync('node_modules/web-ifc/web-ifc-mt.wasm', 'public/web-ifc-mt.wasm');
  console.log('Web-IFC WASM files copied to public directory.');
} catch (e) {
  console.log('WASM files will be copied after npm install.');
}
