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
    const mainPolicy = "default-src 'self'; script-src 'self'; worker-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://doc.auto-mas.top https://data.akedata.wiki https://www.akedata.wiki https://resource.starrailassistant.top https://prod-alicdn-community.kurobbs.com https://webusstatic.yo-star.com https://web.hycdn.cn https://aka.doubaocdn.com https://i0.hdslb.com; font-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'";
    const workerPolicy = "default-src 'none'; script-src 'self' 'unsafe-eval' 'wasm-unsafe-eval'; connect-src 'self'";
    return new Response(fs.readFileSync(file), { headers: { 'Content-Type': type, 'Content-Security-Policy': uri.pathname === '/runtime/engine-worker.js' ? workerPolicy : mainPolicy } });
  });
  window = new BrowserWindow({ show: false, width: 390, height: 844, useContentSize: true, webPreferences: { sandbox: true, contextIsolation: true, backgroundThrottling: false } });
  // 隔离的校验 profile 也会留下旧引导标记；每次首启用例先清空它，重启阶段再验证保留。
  await window.webContents.session.clearStorageData({ storages: ['localstorage'] });
  window.webContents.setUserAgent(window.webContents.getUserAgent() + ' BMAT-Android/1');
  window.webContents.session.webRequest.onBeforeRequest((details, callback) => {
    const allowed = details.url.startsWith(origin + '/') || details.url.startsWith('blob:') || details.url.startsWith('data:');
    if (!allowed) blocked.push(new URL(details.url).origin);
    callback({ cancel: !allowed });
  });
  window.webContents.on('console-message', event => logs.push(event.message));
  await window.loadURL(origin + '/index.html');
  const installMock = async (savedState = null) => window.webContents.executeJavaScript(`(() => {
    window.probe = { state: ${JSON.stringify(savedState)}, wiki: {}, calls: [], logs: [], exports: [], httpCalls: [] };
    window.nativeMock = async (operation, payload) => {
      probe.calls.push(operation);
      if (operation === 'state.read') return { state: probe.state };
      if (operation === 'state.write') { probe.state = payload.state; return { saved: true }; }
      if (operation === 'wiki.read') return { content: probe.wiki[payload.path] ?? null };
      if (operation === 'wiki.write') { probe.wiki[payload.path] = payload.content; return { saved: true }; }
      if (operation === 'http.request') {
        const uri = new URL(payload.url);
        probe.httpCalls.push(uri.host + uri.pathname);
        const json = value => ({ status: 200, headers: [['content-type', 'application/json']], body: btoa(unescape(encodeURIComponent(JSON.stringify(value)))) });
        if (uri.host === 'api-takumi.mihoyo.com' && uri.pathname === '/binding/api/getUserGameRolesByCookie')
          return json({ retcode: 0, data: { list: [{ game_biz: 'hk4e_cn', game_uid: '100000001', nickname: '合成旅行者', region: 'cn_gf01' }] } });
        if (uri.host === 'public-operation-hk4e.mihoyo.com' && uri.pathname.endsWith('/getGachaLog'))
          return json({ retcode: 0, data: { list: uri.searchParams.get('gacha_type') === '301' && ['0', null].includes(uri.searchParams.get('end_id')) ? [{ uid: '100000001', id: '12345678901234567890', gacha_type: '301', name: '合成测试角色', item_id: '1', item_type: '角色', rank_type: '5', time: '2026-09-14 12:00:00' }] : [] } });
        if (payload.url.startsWith('https://api.github.com/repos/Lance0174/Better-MAS-Tools/releases?')) {
          const name = 'BMT-9.0.0-android.apk';
          const releases = [{ tag_name: 'v9.0.0', draft: false, prerelease: false, body: 'Offline update fixture', assets: [{ name, state: 'uploaded', size: 100, digest: 'sha256:' + 'a'.repeat(64), browser_download_url: 'https://github.com/Lance0174/Better-MAS-Tools/releases/download/v9.0.0/' + name }] }];
          return { status: 200, headers: [['content-type', 'application/json']], body: btoa(JSON.stringify(releases)) };
        }
        return { error: 'network' };
      }
      if (operation === 'update.download') {
        if (!payload.downloadUrl.endsWith('/v9.0.0/BMT-9.0.0-android.apk') || payload.sha256 !== 'a'.repeat(64)) throw new Error('Update metadata lost');
        return { ready: true };
      }
      if (operation === 'update.install') return { permissionRequired: true };
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
    await wait(() => !document.querySelector('.page-frame > .page-state'));
    await wait(() => !!document.querySelector('.onboarding-actions'));
    const skip = Array.from(document.querySelectorAll('.onboarding-actions button')).find(button => button.textContent.replace(/\\s/g, '') === '跳过');
    if (!skip) throw new Error('First-run skip control missing');
    skip.click();
    await wait(() => JSON.parse(probe.state || '{}').settings?.OnboardingDismissed === true);
    const check = name => ({ name, width: innerWidth, scrollWidth: document.documentElement.scrollWidth, text: document.body.innerText.slice(0, 1500) });
    const pages = [check('home')];
    for (const route of ['accounts', 'sign', 'activity', 'calendar', 'gacha', 'more', 'wiki', 'logs', 'settings']) {
      location.hash = '#/' + route;
      await new Promise(r => setTimeout(r, 900));
      pages.push(check(route));
    }
    if (document.body.innerText.includes('MAS 管理')) throw new Error('Android exposes MAS management');
    for (const route of ['mas', 'remote']) {
      location.hash = '#/' + route;
      await wait(() => location.hash === '#/home');
    }
    location.hash = '#/settings';
    await wait(() => !!document.querySelector('.settings-page'));
    return { pages, nativeCalls: probe.calls, nativeLogs: probe.logs, onboardingDismissed: true };
  })()`);
  result.systemInsets = await window.webContents.executeJavaScript(`(() => {
    const simulated = document.createElement('style');
    simulated.textContent = ':root { --app-safe-area-top: 72px; --app-safe-area-bottom: 48px; }';
    document.head.append(simulated);
    const header = document.querySelector('.app-page-header');
    const measured = { top: header.getBoundingClientRect().top, paddingTop: parseFloat(getComputedStyle(header).paddingTop), safeTop: getComputedStyle(document.documentElement).getPropertyValue('--app-safe-area-top').trim(), safeBottom: getComputedStyle(document.documentElement).getPropertyValue('--app-safe-area-bottom').trim() };
    simulated.remove();
    if (measured.top !== 0 || measured.paddingTop !== 16 || measured.safeTop !== '0px' || measured.safeBottom !== '0px') throw new Error('Native and web system insets are duplicated: ' + JSON.stringify(measured));
    return measured;
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
    // JSON 有独立入口；只向本次隔离页面注入合成文件。
    clickText('.page-toolbar button', '导入JSON');
    await wait(() => !!document.querySelector('.adaptive-panel input[type=file]'));
    const transfer = new DataTransfer();
    transfer.items.add(new File([JSON.stringify({ records: [item] })], 'fixture.json', { type: 'application/json' }));
    const input = document.querySelector('input[type=file]');
    input.files = transfer.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
    await wait(() => document.body.innerText.includes('合成测试角色'));
    document.querySelector('[aria-label=导出记录]').click();
    await wait(() => Array.from(document.querySelectorAll('.export-options button')).some(button => button.textContent.replace(/\\s/g, '') === '导出JSON'));
    clickText('.export-options button', '导出JSON');
    await wait(() => probe.exports.length === 1);
    await wait(() => !document.querySelector('.export-options'));
    await new Promise(r => setTimeout(r, 350));
    location.hash = '#/settings';
    await wait(() => !!document.querySelector('.settings-page'));
    clickText('.ant-tabs-tab', '软件更新');
    await wait(() => !!document.querySelector('.software-update button'));
    clickText('button', '检查更新');
    await wait(() => document.body.innerText.includes('9.0.0'));
    clickText('button', '下载更新');
    await wait(() => probe.calls.includes('update.download'));
    await wait(() => Array.from(document.querySelectorAll('button')).some(button => button.textContent.replace(/\\s/g, '') === '安装更新'));
    clickText('button', '安装更新');
    await wait(() => !!document.querySelector('.ant-modal-confirm .ant-btn-primary'));
    document.querySelector('.ant-modal-confirm .ant-btn-primary').click();
    await wait(() => probe.calls.includes('update.install'));
    await wait(() => !document.querySelector('.ant-modal-confirm'));
    clickText('.ant-tabs-tab', '外观');
    await new Promise(r => setTimeout(r, 300));
    document.querySelector('.ant-tabs-tabpane-active .choice-select').click();
    await new Promise(r => setTimeout(r, 300));
    clickText('.choice-option', '深色');
    // 设置页已改为自动保存（无保存按钮），主题选择本地即时生效。
    await wait(() => document.documentElement.classList.contains('dark'));
    await wait(() => JSON.parse(probe.state || '{}').settings?.Theme === 'dark');
    const state = JSON.parse(probe.state);
    if (state.gacha.length !== 1 || state.settings.Theme !== 'dark') throw new Error('Native persistence mismatch');
    return { imported: state.gacha.length, exported: probe.exports.length, theme: state.settings.Theme, updateChecked: true, updateDownloaded: true, updatePermissionFlow: true };
  })()`);
  fs.writeFileSync(path.join(output, 'settings-dark.png'), (await window.webContents.capturePage()).toPNG());
  result.userFlows = await window.webContents.executeJavaScript(`(async () => {
    const wait = async (predicate, label) => { for (let i = 0; i < 120; i++) { if (predicate()) return; await new Promise(r => setTimeout(r, 100)); } throw new Error('User flow timeout: ' + label); };
    const click = (selector, text) => { const element = [...document.querySelectorAll(selector)].find(item => item.textContent.replace(/\\s/g, '') === text); if (!element) throw new Error('User flow control missing: ' + text); element.click(); };
    const modal = () => [...document.querySelectorAll('.adaptive-panel .ant-drawer-content')].find(item => item.getClientRects().length > 0);
    window.__BMAT_SYSTEM_DARK__ = true;
    window.dispatchEvent(new CustomEvent('bmat-system-theme-change', { detail: { dark: true } }));
    document.querySelector('.theme-toggle').click();
    await wait(() => JSON.parse(probe.state).settings.Theme === 'light', 'explicit light persisted');
    await new Promise(r => setTimeout(r, 350));
    if (document.documentElement.classList.contains('dark') || document.documentElement.style.colorScheme !== 'light') throw new Error('System dark overrode explicit light');
    const light = getComputedStyle(document.documentElement).getPropertyValue('--ant-color-bg-container').trim();
    // 偏好修改与外观保存共用队列，切换后再改其它开关不能写回旧外观。
    document.querySelector('.ant-tabs-tabpane-active .ant-switch').click();
    await wait(() => JSON.parse(probe.state).settings.GlassEffect === false, 'preference saved');
    if (JSON.parse(probe.state).settings.Theme !== 'light') throw new Error('Preference reverted theme');
    document.querySelector('.theme-toggle').click();
    await wait(() => JSON.parse(probe.state).settings.Theme === 'dark', 'explicit dark persisted');
    await new Promise(r => setTimeout(r, 350));
    const dark = getComputedStyle(document.documentElement).getPropertyValue('--ant-color-bg-container').trim();
    if (light === dark || !document.documentElement.classList.contains('dark')) throw new Error('Palette did not change');
    location.hash = '#/accounts';
    await wait(() => !!document.querySelector('.community-sign-page'), 'accounts page');
    click('button', '添加账号');
    await wait(() => !!document.querySelector('.ant-drawer-body input'), 'account editor');
    click('.ant-collapse-header', '手动凭据与高级设置');
    await wait(() => !!document.querySelector('.ant-drawer-body .ant-input-password input'), 'manual credentials expanded');
    const cookie = document.querySelector('.ant-drawer-body .ant-input-password input');
    cookie.value = 'stuid=100000001; stoken=v2_offline; mid=offline-mid; cookie_token=offline-cookie; ltoken=offline-ltoken';
    cookie.dispatchEvent(new Event('input', { bubbles: true }));
    click('.ant-drawer-footer button', '保存');
    await wait(() => !document.querySelector('.ant-drawer-body'), 'account saved');
    click('.account-row button', '编辑');
    await wait(() => !!document.querySelector('.ant-drawer-body .choice-select'), 'game nickname offered');
    document.querySelector('.ant-drawer-body .choice-select').click();
    await wait(() => [...document.querySelectorAll('.choice-option')].some(item => item.textContent.includes('合成旅行者')), 'nickname choices');
    [...document.querySelectorAll('.choice-option')].find(item => item.textContent.includes('合成旅行者')).click();
    await wait(() => document.querySelector('.ant-drawer-body input')?.value === '合成旅行者', 'chosen nickname applied');
    click('.ant-drawer-footer button', '保存');
    await wait(() => !document.querySelector('.ant-drawer-body'), 'nickname saved');
    location.hash = '#/gacha';
    await wait(() => !!document.querySelector('.gacha-page'), 'gacha page');
    click('.page-toolbar button', '获取记录');
    await wait(() => !!modal()?.querySelector('textarea'), 'official link field');
    if (modal().innerText.includes('米游社账号') || modal().querySelector('input[type=password]')) throw new Error('Unopened Cookie flow is exposed');
    const source = modal().querySelector('textarea');
    source.value = 'https://public-operation-hk4e.mihoyo.com/gacha_info/api/getGachaLog?authkey=offline-authkey';
    source.dispatchEvent(new Event('input', { bubbles: true }));
    await wait(() => [...(modal()?.querySelectorAll('.ant-drawer-footer button') ?? [])].some(button => button.textContent.replace(/\\s/g, '') === '读取记录' && !button.disabled), 'link fetch ready');
    [...modal().querySelectorAll('.ant-drawer-footer button')].find(button => button.textContent.replace(/\\s/g, '') === '读取记录').click();
    await wait(() => !modal(), 'link fetch completed');
    if (probe.httpCalls.some(path => path.endsWith('/binding/api/genAuthKey')) || !probe.httpCalls.some(path => path.endsWith('/getGachaLog'))) throw new Error('Link flow bypassed Cookie restriction');
    if (!Object.values(JSON.parse(probe.state).accounts).some(account => account.Name === '合成旅行者')) throw new Error('Nickname missing in persisted account');
    return { explicitLightWithSystemDark: true, otherPreferenceKeptTheme: true, light, dark, nicknameFromGame: true, officialCookieEntryHidden: true, officialLinkSyncExercised: true };
  })()`);
  const savedState = await window.webContents.executeJavaScript('probe.state');
  await window.loadURL(origin + '/index.html?probe=restart#/gacha');
  await installMock(savedState);
  result.restored = await window.webContents.executeJavaScript(`(async () => {
    for (let i = 0; i < 150; i++) {
      if (document.body.innerText.includes('合成测试角色') && document.documentElement.classList.contains('dark')) {
        const guide = document.querySelector('.onboarding-actions');
        if (guide && guide.getClientRects().length) throw new Error('Skipped onboarding appeared after restart');
        return true;
      }
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
      if (document.querySelector('.page-frame > .page-state .ant-alert-error') && probe.calls.includes('engine.failed')) {
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
  const ui = window && !window.isDestroyed() ? await window.webContents.executeJavaScript('document.body.innerText').catch(() => '') : '';
  if (window && !window.isDestroyed()) fs.writeFileSync(path.join(output, 'failure.png'), (await window.webContents.capturePage()).toPNG());
  finish({ error: error.stack, ui, native: JSON.parse(native || '{}') }, 1);
});
