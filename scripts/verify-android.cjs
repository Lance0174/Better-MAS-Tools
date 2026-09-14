// Isolated packaged Web/Python regression; native operations are mocked, external network denied.
const { app, BrowserWindow, protocol } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const assets = path.join(root, 'android/app/src/main/assets');
const output = path.join(root, 'local/android-ui-probe');
fs.mkdirSync(output, { recursive: true });
app.setPath('userData', path.join(output, 'user-data'));
app.disableHardwareAcceleration();
const origin = 'https://appassets.androidplatform.net';
const logs = [], blocked = [];
let window, finished = false;
const deadline = setTimeout(() => finish({ error: 'Android integration probe timed out' }, 1), 150000);
function finish(result, code = 0) {
  if (finished) return;
  finished = true;
  clearTimeout(deadline);
  const report = { ...result, logs, blocked };
  fs.writeFileSync(path.join(output, `result-${Date.now()}.json`), JSON.stringify(report, null, 2));
  fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2));
  process.stdout.write(JSON.stringify(report) + '\n');
  window?.destroy();
  app.exit(code);
}
app.whenReady().then(async () => {
  protocol.handle('https', request => {
    const uri = new URL(request.url);
    if (uri.origin !== origin) { blocked.push(uri.origin); return new Response('', { status: 403 }); }
    const file = path.resolve(assets, '.' + decodeURIComponent(uri.pathname));
    if (!file.startsWith(assets + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) return new Response('', { status: 404 });
    const type = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.wasm': 'application/wasm', '.svg': 'image/svg+xml', '.webp': 'image/webp' }[path.extname(file)] || 'application/octet-stream';
    const mainPolicy = "default-src 'self'; script-src 'self'; worker-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://doc.auto-mas.top; font-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'";
    const workerPolicy = "default-src 'none'; script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval'; connect-src 'self'";
    return new Response(fs.readFileSync(file), { headers: { 'Content-Type': type, 'Content-Security-Policy': uri.pathname === '/runtime/engine-worker.js' ? workerPolicy : mainPolicy } });
  });
  window = new BrowserWindow({ show: false, width: 390, height: 844, useContentSize: true, webPreferences: { sandbox: true, contextIsolation: true } });
  window.webContents.setUserAgent(window.webContents.getUserAgent() + ' BMAT-Android/1');
  window.webContents.session.webRequest.onBeforeRequest((details, callback) => {
    const allowed = details.url.startsWith(origin + '/') || details.url.startsWith('blob:') || details.url.startsWith('data:');
    if (!allowed) blocked.push(new URL(details.url).origin);
    callback({ cancel: !allowed });
  });
  window.webContents.on('console-message', event => logs.push(event.message));
  await window.loadURL(origin + '/index.html');
  const installMock = async (savedState = null) => window.webContents.executeJavaScript(`(() => {
    window.probe = { state: ${JSON.stringify(savedState)}, calls: [], logs: [], exports: [] };
    window.nativeMock = async (operation, payload) => {
      probe.calls.push(operation);
      if (operation === 'state.read') return { state: probe.state };
      if (operation === 'state.write') { probe.state = payload.state; return { saved: true }; }
      if (operation === 'http.request') return { error: 'network' };
      if (operation === 'log.write') { probe.logs.push(payload.message); return {}; }
      if (operation === 'log.read') return { content: probe.logs.join('\\n') };
      if (operation === 'file.save') { probe.exports.push(payload.filename); return { saved: true }; }
      return {};
    };
    const channel = new MessageChannel();
    channel.port1.onmessage = async event => {
      const request = JSON.parse(event.data);
      try { channel.port1.postMessage(JSON.stringify({ id: request.id, result: await nativeMock(request.operation, request.payload) })); }
      catch { channel.port1.postMessage(JSON.stringify({ id: request.id, error: 'Mock operation failed' })); }
    };
    window.dispatchEvent(new MessageEvent('message', { data: 'bmat-native-ready', ports: [channel.port2], source: null }));
  })()`);
  await installMock();
  const result = await window.webContents.executeJavaScript(`(async () => {
    const wait = async predicate => { for (let i = 0; i < 150; i++) { if (predicate()) return; if (document.querySelector('.page-state .ant-alert-error')) break; await new Promise(r => setTimeout(r, 400)); } throw new Error('UI did not become ready: ' + document.body.innerText.slice(0,300)); };
    await wait(() => !document.querySelector('.app-content > .page-state'));
    const check = name => ({ name, width: innerWidth, scrollWidth: document.documentElement.scrollWidth, text: document.body.innerText.slice(0, 1500) });
    const pages = [check('sign')];
    for (const route of ['activity', 'gacha', 'logs', 'settings']) {
      location.hash = '#/' + route;
      await new Promise(r => setTimeout(r, 900));
      pages.push(check(route));
    }
    return { pages, nativeCalls: probe.calls, nativeLogs: probe.logs };
  })()`);
  fs.writeFileSync(path.join(output, 'settings-light.png'), (await window.webContents.capturePage()).toPNG());
  await window.webContents.executeJavaScript(`location.hash = '#/gacha'`);
  await new Promise(resolve => setTimeout(resolve, 1000));
  const filterLayout = await window.webContents.executeJavaScript(`(() => {
    const filters = document.querySelector('.gacha-filters');
    const last = filters.lastElementChild.getBoundingClientRect();
    const hint = filters.nextElementSibling.getBoundingClientRect();
    return { lastBottom: last.bottom, hintTop: hint.top };
  })()`);
  if (filterLayout.lastBottom > filterLayout.hintTop) throw new Error('Gacha filters overlap history hint');
  fs.writeFileSync(path.join(output, 'gacha-light.png'), (await window.webContents.capturePage()).toPNG());
  result.operations = await window.webContents.executeJavaScript(`(async () => {
    const wait = async predicate => { for (let i = 0; i < 60; i++) { if (predicate()) return; await new Promise(r => setTimeout(r, 100)); } throw new Error('UI operation timeout'); };
    const clickText = (selector, text) => { const node = Array.from(document.querySelectorAll(selector)).find(item => item.textContent.replace(/\\s/g, '') === text); if (!node) throw new Error('Control missing: ' + text); node.click(); };
    const item = { game: 'genshin', playerUid: '100000001', id: '12345678901234567890', poolType: '301', poolName: '合成卡池', name: '合成测试角色', itemId: '1', itemType: '角色', rarity: 5, time: '2026-09-14 12:00:00' };
    const transfer = new DataTransfer();
    transfer.items.add(new File([JSON.stringify({ records: [item] })], 'fixture.json', { type: 'application/json' }));
    const input = document.querySelector('input[type=file]');
    input.files = transfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await wait(() => document.body.innerText.includes('合成测试角色'));
    clickText('button', '导出JSON');
    await wait(() => probe.exports.length === 1);
    location.hash = '#/settings';
    await wait(() => !!document.querySelector('.settings-page'));
    clickText('.ant-tabs-tab', '外观与查询');
    await new Promise(r => setTimeout(r, 300));
    document.querySelector('.ant-tabs-tabpane-active .ant-select-selector').dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    await new Promise(r => setTimeout(r, 300));
    clickText('.ant-select-item-option-content', '深色');
    await wait(() => !document.querySelector('.settings-page .ant-btn-primary').disabled);
    clickText('button', '保存');
    await wait(() => document.documentElement.classList.contains('dark'));
    const state = JSON.parse(probe.state);
    if (state.gacha.length !== 1 || state.settings.Theme !== 'dark') throw new Error('Native persistence mismatch');
    return { imported: state.gacha.length, exported: probe.exports.length, theme: state.settings.Theme };
  })()`);
  fs.writeFileSync(path.join(output, 'settings-dark.png'), (await window.webContents.capturePage()).toPNG());
  const savedState = await window.webContents.executeJavaScript('probe.state');
  await window.loadURL(origin + '/index.html?probe=restart#/gacha');
  await installMock(savedState);
  result.restored = await window.webContents.executeJavaScript(`(async () => {
    for (let i = 0; i < 150; i++) {
      if (document.body.innerText.includes('合成测试角色') && document.documentElement.classList.contains('dark')) return true;
      await new Promise(r => setTimeout(r, 100));
    }
    throw new Error('State did not survive engine restart');
  })()`);
  await new Promise(resolve => setTimeout(resolve, 700));
  fs.writeFileSync(path.join(output, 'gacha-dark.png'), (await window.webContents.capturePage()).toPNG());
  await window.webContents.executeJavaScript("location.hash = '#/logs'");
  await new Promise(resolve => setTimeout(resolve, 700));
  fs.writeFileSync(path.join(output, 'logs-dark.png'), (await window.webContents.capturePage()).toPNG());
  if (result.pages.some(page => page.scrollWidth > page.width)) throw new Error('Page overflow');
  // 损坏合成状态验证启动错误可见，并通知独立的原生诊断层。
  await window.loadURL(origin + '/index.html?probe=invalid-state');
  await installMock('{"accounts":"fixture-invalid-state"}');
  result.failure = await window.webContents.executeJavaScript(`(async () => {
    for (let i = 0; i < 150; i++) {
      if (document.querySelector('.app-content > .page-state .ant-alert-error') && probe.calls.includes('engine.failed')) {
        const text = document.body.innerText;
        if (!text.includes('原数据已保留')) throw new Error('Startup failure reason was lost');
        if (text.includes('fixture-invalid-state') || probe.logs.some(line => line.includes('fixture-invalid-state'))) throw new Error('Invalid state leaked into diagnostic output');
        if (!probe.logs.some(line => line.includes('引擎启动失败'))) throw new Error('Startup failure log missing');
        return { reported: true, nativeErrorSignaled: true };
      }
      await new Promise(r => setTimeout(r, 200));
    }
    throw new Error('Startup failure did not become diagnosable');
  })()`);
  await new Promise(resolve => setTimeout(resolve, 700));
  fs.writeFileSync(path.join(output, 'startup-failure.png'), (await window.webContents.capturePage()).toPNG());
  finish(result);
}).catch(async error => {
  const native = window && !window.isDestroyed() ? await window.webContents.executeJavaScript('JSON.stringify(window.probe ?? {})').catch(() => '') : '';
  finish({ error: error.stack, native: JSON.parse(native || '{}') }, 1);
});
