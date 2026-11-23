/*
 * BIM SCHEDULE — aplicativo desktop (Electron).
 *
 * Arquitetura descrita em docs/architecture/WINDOWS_DESKTOP.md:
 *  - a interface (build do Vite) é servida pelo protocolo privilegiado app://bim-schedule;
 *  - o serviço local (FastAPI) é iniciado pelo próprio app em uma porta livre, com um
 *    token aleatório por sessão e CORS restrito à origem app://bim-schedule;
 *  - runtime-config.js é gerado dinamicamente com o endereço e o token da sessão;
 *  - ao fechar a janela, a árvore de processos do serviço é encerrada (taskkill /T).
 */
'use strict';

const { app, BrowserWindow, Menu, dialog, protocol, shell } = require('electron');
const { spawn, execFile } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');

const SCHEME = 'app';
const HOST = 'bim-schedule';
const ORIGIN = `${SCHEME}://${HOST}`;
const READY_PREFIX = 'BIM_SCHEDULE_READY ';
const START_TIMEOUT_MS = 120_000;

protocol.registerSchemesAsPrivileged([
  { scheme: SCHEME, privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true } },
]);

// ---------------------------------------------------------------------------
// Caminhos
// ---------------------------------------------------------------------------
const isPackaged = app.isPackaged;
const repoRoot = path.resolve(__dirname, '..');
const frontendDir = isPackaged ? path.join(process.resourcesPath, 'frontend') : path.join(repoRoot, 'frontend', 'dist');
const docsDir = isPackaged ? path.join(process.resourcesPath, 'docs') : path.join(repoRoot, 'docs');
const dataDir = process.env.BIM_SCHEDULE_DATA_DIR || path.join(process.env.LOCALAPPDATA || app.getPath('userData'), 'BIM-SCHEDULE');
const logsDir = path.join(dataDir, 'logs');

function serviceCommand() {
  if (isPackaged) {
    const exe = path.join(process.resourcesPath, 'service', 'bim-schedule-service.exe');
    return { command: exe, args: ['--port', '0'], cwd: path.dirname(exe), extraEnv: {} };
  }
  // Desenvolvimento: usa a .venv do repositório (ou BIM_SCHEDULE_PYTHON).
  const python = process.env.BIM_SCHEDULE_PYTHON || path.join(repoRoot, '.venv', 'Scripts', 'python.exe');
  const backend = path.join(repoRoot, 'backend');
  return { command: python, args: ['-m', 'app', '--port', '0'], cwd: backend, extraEnv: { PYTHONPATH: backend } };
}

// ---------------------------------------------------------------------------
// Serviço local
// ---------------------------------------------------------------------------
let service = null; // { proc, apiBaseUrl, token }
let quitting = false;
let mainWindow = null;
let serviceLog = null;

function openServiceLog() {
  fs.mkdirSync(logsDir, { recursive: true });
  const file = path.join(logsDir, 'desktop-service.log');
  // Mantém só a sessão atual + a anterior.
  try { if (fs.existsSync(file)) fs.renameSync(file, path.join(logsDir, 'desktop-service.prev.log')); } catch { /* em uso */ }
  serviceLog = fs.createWriteStream(file, { flags: 'a' });
  serviceLog.write(`=== ${new Date().toISOString()} BIM SCHEDULE desktop ${app.getVersion()} ===\n`);
  return file;
}

function healthOk(apiBaseUrl) {
  return new Promise((resolve) => {
    const req = http.get(`${apiBaseUrl}/system/health`, { timeout: 2000 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

function startService() {
  return new Promise((resolve, reject) => {
    const { command, args, cwd, extraEnv } = serviceCommand();
    if (!fs.existsSync(command)) {
      reject(new Error(`Serviço não encontrado: ${command}\n\nNo modo de desenvolvimento, execute install.bat primeiro.`));
      return;
    }
    const token = crypto.randomBytes(32).toString('hex');
    const env = {
      ...process.env,
      ...extraEnv,
      BIM_SCHEDULE_LOCAL_API_TOKEN: token,
      BIM_SCHEDULE_CORS_ORIGINS: JSON.stringify([ORIGIN]),
      BIM_SCHEDULE_ENVIRONMENT: 'desktop',
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
    };
    const proc = spawn(command, args, { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let settled = false;
    let buffer = '';
    const timer = setTimeout(() => fail(new Error('O serviço local não respondeu em 2 minutos.')), START_TIMEOUT_MS);

    function fail(err) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      killTree(proc.pid);
      reject(err);
    }

    proc.stdout.on('data', async (chunk) => {
      const text = chunk.toString('utf8');
      serviceLog?.write(text);
      if (settled) return;
      buffer += text;
      const line = buffer.split(/\r?\n/).find((l) => l.startsWith(READY_PREFIX));
      if (!line) return;
      buffer = '';
      let apiBaseUrl;
      try { apiBaseUrl = JSON.parse(line.slice(READY_PREFIX.length)).api_base_url; } catch (e) { fail(e); return; }
      const deadline = Date.now() + START_TIMEOUT_MS;
      while (Date.now() < deadline && !settled) {
        if (await healthOk(apiBaseUrl)) {
          settled = true;
          clearTimeout(timer);
          service = { proc, apiBaseUrl, token };
          resolve(service);
          return;
        }
        await new Promise((r) => setTimeout(r, 300));
      }
      fail(new Error('O serviço iniciou, mas a verificação de saúde não respondeu.'));
    });
    proc.stderr.on('data', (chunk) => serviceLog?.write(chunk.toString('utf8')));
    proc.on('error', (err) => fail(err));
    proc.on('exit', (code) => {
      serviceLog?.write(`\n[serviço encerrado, código ${code}]\n`);
      if (!settled) { fail(new Error(`O serviço local encerrou durante a inicialização (código ${code}).`)); return; }
      if (service && service.proc === proc) service = null;
      if (!quitting) onServiceCrashed(code);
    });
  });
}

function killTree(pid) {
  if (!pid) return Promise.resolve();
  return new Promise((resolve) => {
    execFile('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true }, () => resolve());
  });
}

async function stopService() {
  if (!service) return;
  const { proc } = service;
  service = null;
  await killTree(proc.pid);
}

async function onServiceCrashed(code) {
  if (!mainWindow) return;
  const { response } = await dialog.showMessageBox(mainWindow, {
    type: 'error',
    title: 'BIM SCHEDULE',
    message: 'O serviço local foi encerrado inesperadamente.',
    detail: `Código: ${code}. Detalhes em ${path.join(logsDir, 'desktop-service.log')}`,
    buttons: ['Reiniciar serviço', 'Abrir pasta de logs', 'Fechar'],
    defaultId: 0,
  });
  if (response === 0) {
    try { await startService(); mainWindow.loadURL(`${ORIGIN}/index.html`); }
    catch (err) { showFatal(err); }
  } else if (response === 1) {
    shell.openPath(logsDir);
  }
}

// ---------------------------------------------------------------------------
// Protocolo app://bim-schedule (arquivos do frontend + runtime-config.js)
// ---------------------------------------------------------------------------
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.wasm': 'application/wasm', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2',
  '.map': 'application/json', '.txt': 'text/plain; charset=utf-8',
};

function registerAppProtocol() {
  const root = path.resolve(frontendDir);
  protocol.handle(SCHEME, async (request) => {
    const url = new URL(request.url);
    if (url.host !== HOST) return new Response('Host inválido', { status: 403 });
    let rel = decodeURIComponent(url.pathname);
    if (rel === '/' || rel === '') rel = '/index.html';
    if (rel === '/runtime-config.js') {
      const cfg = service ? { apiBaseUrl: service.apiBaseUrl, apiToken: service.token, mode: 'desktop' } : { mode: 'desktop' };
      const body = `window.__BIM_SCHEDULE_CONFIG__ = Object.assign({}, window.__BIM_SCHEDULE_CONFIG__ || {}, ${JSON.stringify(cfg)});\n`;
      return new Response(body, { headers: { 'content-type': MIME['.js'], 'cache-control': 'no-store' } });
    }
    const file = path.resolve(root, '.' + rel);
    if (file !== root && !file.startsWith(root + path.sep)) return new Response('Proibido', { status: 403 });
    try {
      const data = await fs.promises.readFile(file);
      const type = MIME[path.extname(file).toLowerCase()] || 'application/octet-stream';
      return new Response(data, { headers: { 'content-type': type } });
    } catch {
      return new Response('Não encontrado', { status: 404 });
    }
  });
}

// ---------------------------------------------------------------------------
// Janelas
// ---------------------------------------------------------------------------
function secureWebPreferences() {
  return { contextIsolation: true, sandbox: true, nodeIntegration: false, webSecurity: true, spellcheck: false };
}

function guardNavigation(win) {
  win.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(`${ORIGIN}/`)) { event.preventDefault(); if (/^https?:/i.test(url)) shell.openExternal(url); }
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(`${ORIGIN}/`)) {
      return { action: 'allow', overrideBrowserWindowOptions: { width: 1280, height: 800, autoHideMenuBar: true, webPreferences: secureWebPreferences() } };
    }
    if (/^https?:/i.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
}

function splashHtml(message) {
  return `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html><html><body style="margin:0;height:100vh;display:flex;align-items:center;justify-content:center;flex-direction:column;background:#0f172a;color:#e2e8f0;font-family:Segoe UI,sans-serif">
  <div style="font-size:28px;font-weight:700;letter-spacing:1px">BIM SCHEDULE</div>
  <div style="margin-top:12px;color:#94a3b8">${message}</div>
  <div style="margin-top:24px;width:220px;height:4px;background:#1e293b;border-radius:2px;overflow:hidden"><div style="width:40%;height:100%;background:#38bdf8;animation:a 1.2s infinite ease-in-out"></div></div>
  <style>@keyframes a{0%{transform:translateX(-100%)}100%{transform:translateX(250%)}}</style></body></html>`)}`;
}

function buildMenu() {
  const tutorial = path.join(docsDir, 'TUTORIAL-DESKTOP.md');
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {
      label: 'Arquivo',
      submenu: [
        { label: 'Recarregar', accelerator: 'F5', click: () => mainWindow?.webContents.reload() },
        { type: 'separator' },
        { label: 'Abrir pasta de dados', click: () => shell.openPath(dataDir) },
        { label: 'Abrir pasta de logs', click: () => { fs.mkdirSync(logsDir, { recursive: true }); shell.openPath(logsDir); } },
        { type: 'separator' },
        { label: 'Sair', accelerator: 'Alt+F4', role: 'quit' },
      ],
    },
    {
      label: 'Exibir',
      submenu: [
        { role: 'zoomIn', label: 'Aumentar zoom' }, { role: 'zoomOut', label: 'Diminuir zoom' }, { role: 'resetZoom', label: 'Zoom padrão' },
        { type: 'separator' }, { role: 'togglefullscreen', label: 'Tela cheia' },
        { label: 'Ferramentas do desenvolvedor', accelerator: 'Ctrl+Shift+I', click: () => mainWindow?.webContents.toggleDevTools() },
      ],
    },
    {
      label: 'Ajuda',
      submenu: [
        { label: 'Tutorial de uso', click: () => (fs.existsSync(tutorial) ? shell.openPath(tutorial) : null) },
        { label: 'Documentação da API (Swagger)', click: () => service && shell.openExternal(service.apiBaseUrl.replace(/\/api\/v1$/, '/docs')) },
        { type: 'separator' },
        { label: `Sobre (versão ${app.getVersion()})`, click: () => dialog.showMessageBox(mainWindow, { title: 'BIM SCHEDULE', message: `BIM SCHEDULE ${app.getVersion()}`, detail: `Dados: ${dataDir}\nServiço: ${service ? service.apiBaseUrl : 'parado'}` }) },
      ],
    },
  ]));
}

function showFatal(err) {
  dialog.showErrorBox('BIM SCHEDULE — falha ao iniciar', `${err && err.message ? err.message : err}\n\nLog: ${path.join(logsDir, 'desktop-service.log')}`);
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1440, height: 900, minWidth: 1024, minHeight: 680, show: false, backgroundColor: '#0f172a',
    title: 'BIM SCHEDULE', icon: path.join(__dirname, 'build', 'icon.ico'),
    webPreferences: secureWebPreferences(),
  });
  guardNavigation(mainWindow);
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });
  await mainWindow.loadURL(splashHtml('Iniciando o serviço local…'));
  mainWindow.show();

  try {
    await startService();
  } catch (err) {
    showFatal(err);
    app.quit();
    return;
  }
  await mainWindow.loadURL(`${ORIGIN}/index.html`);
}

// ---------------------------------------------------------------------------
// Ciclo de vida
// ---------------------------------------------------------------------------
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) { if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.focus(); }
  });

  app.whenReady().then(() => {
    openServiceLog();
    registerAppProtocol();
    buildMenu();
    createMainWindow();
  });

  app.on('window-all-closed', () => app.quit());

  app.on('before-quit', (event) => {
    if (quitting) return;
    quitting = true;
    if (service) {
      event.preventDefault();
      stopService().finally(() => app.quit());
    }
  });
}
