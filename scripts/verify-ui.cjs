// Real built Vue pages, synthetic HTTP responses, isolated profile, zero external requests.
const { app, BrowserWindow, protocol } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const { fixtures } = require('./ui-fixtures.cjs');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'local/release-b5/ui');
fs.mkdirSync(output, { recursive: true });
app.setPath('userData', path.join(output, 'profile'));
app.disableHardwareAcceleration();
const origin = 'https://ui.bmat.test';
const failures = [], checks = [], consoleErrors = [], blocked = [], captureRetries = [];
let window, platform = 'android';
let handleApi = fixtures();
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const js = source => window.webContents.executeJavaScript(source);
const capture = async name => {
  for (let attempt = 0; attempt < 3; attempt++) {
    try { return await window.webContents.capturePage(undefined, { stayHidden: true, stayAwake: true }); }
    catch (error) {
      // Chromium 的离屏合成器在刚改变尺寸时偶尔尚未提交新帧；只重试该截图错误。
      if (!String(error).includes('UnknownVizError') || attempt === 2) throw error;
      captureRetries.push({ name, attempt: attempt + 1 });
      await pause(180);
    }
  }
};
const snapshot = async name => {
  // Hidden windows may retain the previous compositor frame until the first capture wakes it.
  await pause(120);
  await capture(name);
  await pause(180);
  fs.writeFileSync(path.join(output, name + '.png'), (await capture(name)).toPNG());
};
const finish = code => { fs.writeFileSync(path.join(output,'result.json'), JSON.stringify({ checks, failures, consoleErrors, blocked, captureRetries }, null, 2)); window?.destroy(); app.exit(code); };
const deadline = setTimeout(() => { failures.push('Probe deadline'); finish(1); }, 240000);
app.whenReady().then(async () => {
  protocol.handle('https', async request => {
    const url = new URL(request.url);
    if (url.origin !== origin) { blocked.push(url.origin); return new Response('',{ status: 403 }); }
    if (url.pathname.startsWith('/api/')) return new Response(JSON.stringify(await handleApi(request,url)), { headers: { 'content-type': 'application/json' } });
    if (url.pathname.startsWith('/fixtures/')) {
      const image = url.pathname === '/fixtures/square.webp' ? 'genshin.webp' : url.pathname === '/fixtures/wide.webp' ? 'endfield-background.webp' : '';
      return new Response(image ? fs.readFileSync(path.join(root,'frontend/src/assets/community-notes',image)) : 'invalid image fixture', { headers: { 'content-type': 'image/webp' } });
    }
    const directory = path.join(root, 'frontend', platform === 'android' ? 'dist-android' : 'dist');
    const file = path.resolve(directory, '.' + decodeURIComponent(url.pathname));
    if (!file.startsWith(directory + path.sep) || !fs.existsSync(file)) return new Response('',{ status: 404 });
    const type = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.webp': 'image/webp', '.json': 'application/json' }[path.extname(file)] || 'application/octet-stream';
    return new Response(fs.readFileSync(file), { headers: { 'content-type': type } });
  });
  window = new BrowserWindow({ show: false, width: 390, height: 844, useContentSize: true, webPreferences: { offscreen: true, sandbox: true, contextIsolation: true, backgroundThrottling: false } });
  window.webContents.on('console-message', event => { if (event.level === 'error') consoleErrors.push(event.message); });
  window.webContents.session.webRequest.onBeforeRequest((details, done) => {
    const allow = details.url.startsWith(origin + '/') || /^(data|blob):/.test(details.url);
    if (!allow) blocked.push(new URL(details.url).origin);
    done({ cancel: !allow });
  });
  const helpers = `
    const wait = async (test,label) => { for(let i=0;i<80;i++){ if(test()) return; await new Promise(r=>setTimeout(r,100)); } throw new Error(label); };
    const visible = selector => [...document.querySelectorAll(selector)].filter(node => node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden');
    const click = (selector,text) => { const node = visible(selector).find(node => node.textContent.replace(/\\s/g,'') === text); if(!node) throw new Error('Missing '+text); node.click(); };
    const back = () => { if(window.dispatchEvent(new Event('bmat-android-back',{cancelable:true}))) throw new Error('Back not consumed'); };
  `;
  await window.loadURL(origin + '/index.html#/home');
  await js(`(async()=>{ ${helpers} await wait(()=>!!document.querySelector('.home-notes .daily-note'),'Home notes'); })()`);
  for (const kind of ['android','desktop']) {
    platform = kind;
    if (kind === 'desktop') { handleApi = fixtures(); await window.loadURL(origin + '/index.html?desktop#/home'); await pause(600); }
    for (const width of kind === 'android' ? [390,320] : [1440]) {
      window.setContentSize(width, width === 1440 ? 1000 : 844);
      for (const dark of [false,true]) {
        await js(`(async()=>{ ${helpers} location.hash='#/home'; await wait(()=>!!document.querySelector('.home-overview'),'home'); if(document.documentElement.classList.contains('dark') !== ${dark}) document.querySelector('.theme-toggle').click(); await wait(()=>document.documentElement.classList.contains('dark') === ${dark},'theme'); })()`);
        for (const route of ['home','activity','gacha','calendar','more','accounts','sign','settings','wiki','logs', ...(kind === 'desktop' ? ['mas'] : [])]) {
          await js(`location.hash='#/${route}'`);
          await pause(350);
          const check = await js(`(()=>{const content=document.querySelector('.app-content');return { width:innerWidth, documentWidth:document.documentElement.scrollWidth, contentWidth:content.clientWidth, scrollWidth:content.scrollWidth, text:document.body.innerText, notePaper:document.querySelector('.note-paper') ? getComputedStyle(document.querySelector('.note-paper')).color : '' };})()`);
          if (check.documentWidth > width + 1 || check.scrollWidth > check.contentWidth + 1) failures.push(`${kind}/${width}/${dark}/${route}: overflow`);
          if (/standalone\.[A-Za-z]|gamesign\.[A-Za-z]/.test(check.text)) failures.push(`${route}: untranslated text`);
          if (check.text.includes('服务已连接')) failures.push(`${route}: redundant service status`);
          if (['home','calendar'].includes(route) && check.text.includes('操作成功')) failures.push(`${route}: generic success notice`);
          if (kind === 'android' && /MAS 管理|远程控制/.test(check.text)) failures.push(`${route}: desktop control exposed`);
          checks.push({ platform:kind,width,dark,route,overflow:check.scrollWidth-check.contentWidth });
          if (width !== 320 || ['home','activity','gacha','sign'].includes(route)) await snapshot(`${kind}-${route}${width === 320 ? '-320' : ''}-${dark ? 'dark' : 'light'}`);
        }
      }
    }
  }
  platform = 'android'; handleApi = fixtures(); window.setContentSize(390,844);
  await window.loadURL(origin + '/index.html?flows#/home');
  await js(`(async()=>{ ${helpers}
    await wait(()=>document.querySelectorAll('.home-notes .note-account .choice-select').length===2,'Single and multiple account controls');
    const buttons=[...document.querySelectorAll('.home-notes .note-account .choice-select')];
    if(buttons.some(button=>button.getBoundingClientRect().height>32)) throw new Error('Home account control is too tall');
    buttons[1].click(); await wait(()=>visible('.choice-option').length===1,'Single account choice');
    if(visible('.choice-option')[0].getAttribute('aria-pressed')!=='true') throw new Error('Single account is not selected');
    visible('.choice-option')[0].click(); await wait(()=>!visible('.choice-option').length,'Single account choice closed');
    if(document.querySelectorAll('.home-notes .note-account .choice-select').length!==2) throw new Error('Single account control disappeared');
    location.hash='#/activity';
  })()`);
  checks.push({ flows: 'compact home controls and usable single account choice' });
  await js(`(async()=>{ ${helpers}
    await wait(()=>!!document.querySelector('.activity-overview .note-account .choice-select'),'Note account');
    document.querySelector('.activity-overview .note-account .choice-select').click(); await wait(()=>visible('.choice-option').length>0,'Note choices');
    const option=visible('.choice-option').find(node=>node.textContent.includes('另一位测试角色')); if(!option) throw new Error('second account'); option.click(); await wait(()=>document.querySelector('.activity-metric-value')?.textContent.includes('68'),'Account resource isolation');
    const note=document.querySelector('.activity-card');
    if(!note.querySelector('.activity-background')?.getAttribute('src').includes('genshin-background') || !note.innerText.includes('每日任务') || !note.querySelector('.activity-card-footer')) throw new Error('Original note artwork or content lost');
  })()`);
  await js(`(async()=>{ ${helpers}
    document.querySelector('.note-account .choice-select').click(); await wait(()=>visible('.choice-option').length>0,'picker'); back(); await wait(()=>!visible('.choice-option').length,'picker closed');
    if(!document.querySelector('.daily-note')) throw new Error('Back left note page');
    location.hash='#/accounts'; await wait(()=>!!document.querySelector('.account-row'),'accounts'); click('.account-row button','编辑');
    await wait(()=>!!document.querySelector('.account-editor'),'editor');
    const name=document.querySelector('.account-editor input'); name.value='尚未保存'; name.dispatchEvent(new Event('input',{bubbles:true}));
    back(); await wait(()=>visible('.ant-modal-confirm').length>0,'discard confirmation'); back(); await wait(()=>!visible('.ant-modal-confirm').length,'cancel discard');
    if(!visible('.account-editor').length || name.value!=='尚未保存') throw new Error('Discard cancellation lost draft');
    back(); await wait(()=>visible('.ant-modal-confirm').length>0,'discard again'); click('.ant-modal-confirm button','确定'); await wait(()=>!visible('.account-editor').length,'editor closed');
    location.hash='#/gacha'; await wait(()=>!!document.querySelector('.gacha-page'),'gacha'); click('.page-toolbar button','获取记录');
    await wait(()=>visible('.adaptive-panel .ant-drawer-content').length>0,'fetch sheet'); document.querySelector('.adaptive-panel .choice-select').click(); await wait(()=>visible('.choice-option').length>0,'source choices'); back(); await wait(()=>!visible('.choice-option').length,'nested choice closed');
    if(!visible('.adaptive-panel .ant-drawer-content').length) throw new Error('Nested back closed fetch'); back(); await wait(()=>!visible('.adaptive-panel .ant-drawer-content').length,'fetch closed');
  })()`);
  checks.push({ flows: 'account isolation, choice return, discard cancel, nested back' });
  await js(`(async()=>{ ${helpers}
    location.hash='#/accounts'; await wait(()=>!!document.querySelector('.account-row'),'accounts'); click('.account-row button','编辑'); await wait(()=>visible('.account-editor').length>0,'editor');
    document.querySelectorAll('.binding-row button')[1].click(); await wait(()=>visible('.qr-login-container').length>0,'QR sheet'); back(); await wait(()=>!visible('.qr-login-container').length,'QR canceled');
    if(!visible('.account-editor').length) throw new Error('QR return closed editor');
    document.querySelectorAll('.binding-row button')[3].click(); await wait(()=>visible('.sms-hint').length>0,'SMS sheet'); back(); await wait(()=>!visible('.sms-hint').length,'SMS canceled');
    click('.ant-drawer-footer button','保存'); back(); if(!visible('.account-editor').length) throw new Error('Back closed saving editor'); await wait(()=>!visible('.account-editor').length,'saved editor');
    location.hash='#/wiki'; await wait(()=>!!document.querySelector('.wiki-search input'),'wiki search'); const keyword=document.querySelector('.wiki-search input'); keyword.value='测试'; keyword.dispatchEvent(new Event('input',{bubbles:true})); await wait(()=>visible('.wiki-result').length>0,'wiki result'); visible('.wiki-result')[0].click(); await wait(()=>visible('.mobile-panel--page .wiki-entry-header').length>0,'wiki detail'); back(); await wait(()=>!visible('.mobile-panel--page .wiki-entry-header').length,'wiki returned');
  })()`);
  checks.push({ flows: 'QR cancel, SMS cancel, busy save, wiki detail return' });
  window.setContentSize(320,480);
  await js(`(async()=>{ ${helpers} await wait(()=>innerWidth===320 && innerHeight===480,'editor viewport resized'); })()`);
  await js(`(async()=>{ ${helpers} location.hash='#/accounts'; await wait(()=>!!document.querySelector('.account-row'),'accounts'); click('.account-row button','编辑'); await wait(()=>visible('.account-editor').length>0,'editor'); })()`);
  await js(`(async()=>{ ${helpers} await wait(()=>Math.abs(document.querySelector('.mobile-panel--page .ant-drawer-content-wrapper').getBoundingClientRect().left)<1,'full-width editor settled'); })()`);
  await pause(250); await snapshot('android-editor-low-height');
  const footer = await js(`(()=>{const buttons=[...document.querySelectorAll('.ant-drawer-footer button')].filter(node=>node.getClientRects().length); return buttons.every(button=>{const r=button.getBoundingClientRect(); return r.bottom<=innerHeight && r.top>=0 && r.left>=0 && r.right<=innerWidth});})()`);
  if (!footer) failures.push('Low-height editor footer inaccessible');
  checks.push({ lowHeightFooter: footer });
  await js(`window.dispatchEvent(new Event('bmat-android-back',{cancelable:true}))`);

  await js(`(async()=>{ ${helpers}
    location.hash='#/gacha'; await wait(()=>!!document.querySelector('.gacha-page'),'gacha sources');
    for(const label of ['原神','崩坏：星穹铁道','绝区零','鸣潮','明日方舟：终末地']) {
      const tab=[...document.querySelectorAll('.game-tabs button')].find(node=>node.textContent.trim()===label);
      tab.click(); await wait(()=>tab.getAttribute('aria-selected')==='true','source game');
      click('.page-toolbar button','获取记录'); await wait(()=>visible('.adaptive-panel .choice-select').length>0,'fetch source');
      visible('.adaptive-panel .choice-select')[0].click(); await wait(()=>visible('.choice-option').length>0,'source options');
      if(visible('.choice-option').some(node=>/Cookie|账号|米游社|森空岛/.test(node.innerText))) throw new Error(label+' exposes account fetch');
      if(!visible('.choice-option').some(node=>node.innerText.includes('官方链接')) || !visible('.choice-option').some(node=>node.innerText.includes('文件导入'))) throw new Error(label+' lost link or file import');
      back(); await wait(()=>!visible('.choice-option').length,'source closed'); back(); await wait(()=>!visible('.adaptive-panel .ant-drawer-content').length,'fetch closed');
    }
  })()`);
  checks.push({ sources: 'Only Arknights has account/Cookie fetch; other five games retain links and files' });

  window.setContentSize(390,844);
  const calls = [];
  handleApi = fixtures({ calls });
  await window.loadURL(origin + '/index.html?official#/gacha');
  await js(`(async()=>{ ${helpers}
    await wait(()=>!!document.querySelector('.gacha-page'),'gacha');
    const tab=[...document.querySelectorAll('.game-tabs button')].find(node=>node.textContent.trim()==='明日方舟'); tab.scrollIntoView({block:'nearest',inline:'center'}); tab.click();
    await wait(()=>tab.getAttribute('aria-selected')==='true','game selected'); click('.page-toolbar button','获取记录');
    await wait(()=>visible('.adaptive-panel .choice-select').some(node=>node.innerText.includes('合成博士')),'Skland role ready');
    if(visible('input[type=password]').length) throw new Error('Saved Skland account requested credentials');
    await wait(()=>visible('.ant-drawer-footer button').length===2 && visible('.ant-drawer-footer button').every(button=>button.getBoundingClientRect().bottom<=innerHeight),'fetch footer settled');
  })()`);
  if (calls.some(call => call.path === '/api/gacha/fetch')) throw new Error('Records were fetched without confirmation');
  await snapshot('android-gacha-skland-confirm');
  window.setContentSize(320,480);
  await js(`(async()=>{ ${helpers} await wait(()=>innerWidth===320 && innerHeight===480,'fetch viewport resized'); })()`);
  await pause(300);
  await js(`(async()=>{ ${helpers} await wait(()=>visible('.ant-drawer-footer button').length===2 && visible('.ant-drawer-footer button').every(button=>{const r=button.getBoundingClientRect();return r.bottom<=innerHeight && r.top>=0 && r.left>=0 && r.right<=innerWidth}),'low height fetch footer'); })()`);
  await js(`(async()=>{ ${helpers}
    const body=visible('.ant-drawer-body')[0]; if(!body || body.scrollHeight<=body.clientHeight) throw new Error('Long form body did not scroll');
    body.scrollTop=body.scrollHeight; click('.gacha-advanced .ant-collapse-header','更多读取选项'); await wait(()=>visible('.gacha-advanced .ant-input-number').length>0,'advanced options');
  })()`);
  await pause(300);
  await js(`(()=>{const body=document.querySelector('.ant-drawer-body');body.scrollTop=body.scrollHeight;if([...document.querySelectorAll('.ant-drawer-footer button')].some(button=>button.getBoundingClientRect().bottom>innerHeight)) throw new Error('Advanced options moved footer off screen');})()`);
  await snapshot('android-gacha-low-height');
  checks.push({ lowHeightGachaFooter: true });
  window.setContentSize(390,844);
  await js(`(async()=>{ ${helpers} await wait(()=>innerWidth===390 && innerHeight===844,'fetch viewport restored'); })()`);
  await js(`(async()=>{ ${helpers} click('.ant-drawer-footer button','读取记录'); await wait(()=>!visible('.ant-drawer-content').length,'Skland completed'); })()`);
  const fetched = calls.find(call => call.path === '/api/gacha/fetch');
  if (!fetched || fetched.body.accountId !== 'fixture-one' || fetched.body.playerUid !== '200000001' || fetched.body.game !== 'arknights') throw new Error('Skland account and role not sent');
  checks.push({ flows: 'Skland saved account, auto role, explicit confirmation, no Cookie input' });

  await js(`(async()=>{ ${helpers}
    location.hash='#/sign'; await wait(()=>document.querySelectorAll('.sign-overview strong').length===3,'sign summary');
    const counts=[...document.querySelectorAll('.sign-overview strong')].map(node=>node.textContent.trim()).join(',');
    if(counts!=='3,1,1') throw new Error('Sign summary mismatch: '+counts);
    if(!document.querySelector('.result-step[data-kind=community]')?.textContent.includes('库洛币') || !document.querySelector('.result-step[data-kind=game]')?.textContent.includes('贝币')) throw new Error('Community and game rewards missing');
    if(!document.querySelector('.result-step[data-state=failed] .result-reason')?.textContent.includes('登录状态过期')) throw new Error('Sign failure reason lost');
    if(document.querySelectorAll('.result-step[data-state=pending]').length!==1 || !document.querySelector('.result-role')?.textContent.includes('100000001')) throw new Error('Historic result or UID presentation incorrect');
  })()`);
  checks.push({ flows: 'sign counts, roles and UID, separate tasks, failure reason, historic pending' });

  const day = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date());
  const baseApi = fixtures();
  const artworkCases = [
    { name: 'no-activity-image', banner: '', cover: '', expected: 'genshin-background' },
    { name: 'activity-image', banner: '/fixtures/wide.webp', cover: '', expected: '/fixtures/wide.webp' },
    { name: 'bad-activity-version-fallback', banner: '/fixtures/invalid.webp', cover: '/fixtures/wide.webp', expected: '/fixtures/wide.webp' },
    { name: 'square-icon-version-fallback', banner: '/fixtures/square.webp', cover: '/fixtures/wide.webp', expected: '/fixtures/wide.webp' },
    { name: 'bad-version-default-fallback', banner: '/fixtures/invalid.webp', cover: '/fixtures/square.webp', expected: 'genshin-background' },
    { name: 'no-known-artwork', game: 'unknown', banner: '', cover: '', expected: '' },
  ];
  for (const entry of artworkCases) {
    handleApi = async (request,url) => url.pathname === '/api/wiki/calendar-all' ? {
      code: 200, status: 'success', message: '操作成功', data: [{ game: entry.game || 'genshin', name: '合成游戏', cover: entry.cover, activities: [{ game: entry.game || 'genshin', title: '配图回退检查', kind: 'activity', banner: entry.banner, startsAt: day+'T00:00:00+08:00', endsAt: day+'T23:59:59+08:00', status: '进行中' }] }],
    } : baseApi(request,url);
    await window.loadURL(origin + '/index.html?artwork=' + entry.name + '#/calendar');
    await js(`(async()=>{ ${helpers}
      await wait(()=>!!document.querySelector('.calendar-card-artwork'),'artwork card');
      const expected=${JSON.stringify(entry.expected)};
      await wait(()=>{const image=document.querySelector('.calendar-card-artwork img');return expected ? image?.getAttribute('src').includes(expected) && image.complete && image.naturalWidth>=300 && image.naturalWidth/image.naturalHeight>=1.2 : !image},'artwork fallback');
      if(document.querySelector('.calendar-card-artwork').textContent.trim()) throw new Error('Text used as image');
    })()`);
    checks.push({ artwork: entry.name });
    if (entry.name === 'no-activity-image') { await js(`document.querySelector('.calendar-card').scrollIntoView({block:'center'})`); await pause(250); await snapshot('android-calendar-default-artwork'); }
  }
  handleApi = async (request,url) => url.pathname === '/api/gacha' ? { code: 200, status: 'success', data: [], total: 0, players: [], pools: [] } : baseApi(request,url);
  await window.loadURL(origin + '/index.html?empty-gacha#/gacha');
  await js(`(async()=>{ ${helpers} await wait(()=>!!document.querySelector('.gacha-empty'),'empty gacha'); if(document.querySelector('.gacha-table')) throw new Error('Empty table exposed'); })()`);
  await snapshot('android-gacha-empty-light');
  await js(`document.querySelector('.theme-toggle').click()`); await pause(250);
  await snapshot('android-gacha-empty-dark');
  checks.push({ state: 'gacha empty guidance and separate JSON import' });

  const realApi = handleApi;
  handleApi = async (request,url) => url.pathname === '/api/activity' ? { code: 200, status: 'success', data: [] } : realApi(request,url);
  await window.loadURL(origin + '/index.html?empty#/activity');
  await js(`(async()=>{ ${helpers} await wait(()=>document.querySelector('.activity-overview .ant-empty'),'empty notes'); })()`);
  checks.push({ state: 'empty notes are visible' });
  handleApi = async (request,url) => url.pathname === '/api/activity' ? { code: 400, status: 'error', message: '合成查询失败，请重试' } : realApi(request,url);
  await window.loadURL(origin + '/index.html?failed#/activity');
  await js(`(async()=>{ ${helpers} await wait(()=>document.body.innerText.includes('合成查询失败，请重试'),'failure reason'); })()`);
  checks.push({ state: 'failed notes preserve reason and retry' });
  clearTimeout(deadline);
  finish(failures.length || consoleErrors.length || blocked.length ? 1 : 0);
}).catch(async error => { clearTimeout(deadline); failures.push(error.stack); if (window && !window.isDestroyed()) await snapshot('failure'); finish(1); });
