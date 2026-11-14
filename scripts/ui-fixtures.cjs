// Only synthetic data for the isolated renderer probe. Never loaded by the application.
const day = new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Shanghai' }).format(new Date());
const stamp = `${day}T10:30:00+08:00`;
const ok = data => ({ code: 200, status: 'success', message: '操作成功', data });
function fixtures(options = {}) {
  let settings = { Theme: 'light', GlassEffect: false, ActivityEnabled: true, OnboardingDismissed: true, Enabled: false };
  let accounts = [
    { uid: 'fixture-one', data: { Name: '合成旅行者', Enabled: true, MiyousheToken: '***', SklandToken: '***', KuroToken: '***' } },
    { uid: 'fixture-two', data: { Name: '另一位测试角色', Enabled: true, MiyousheToken: '***' } },
  ];
  const note = (game, name, current, target, role = '合成旅行者', uid = 'fixture-one') => ({ account: role, accountUid: uid, game, platform: '测试社区', status: 'success', roleName: role, roleUid: uid, server: '测试区服', updatedAt: stamp, resources: [{ name, current, target, status: '预计 3 小时后回满' }], tasks: [{ name: '每日任务', completed: 3, target: 4, status: '已完成 3 / 4 项', period: 'daily' }] });
  const notes = [note('原神', '原粹树脂', 128, 200), note('星穹铁道', '开拓力', 186, 300), note('原神', '原粹树脂', 68, 200, '另一位测试角色', 'fixture-two'), note('鸣潮', '结晶波片', 180, 240)];
  notes[3].resources.push({ name: '结晶单质', current: 120, target: 480, status: '' });
  notes[3].tasks.push({ name: '活跃度', completed: 60, target: 100, status: '', period: 'daily' }, { name: '电台等级', completed: 32, target: 70, status: '', period: 'weekly' }, { name: '周本剩余次数', completed: 2, target: 3, status: '', period: 'weekly' });
  const calendar = [['genshin','原神'],['starrail','崩坏：星穹铁道'],['arknights','明日方舟']].map(([game,name]) => ({ game, name, source: 'cache', activities: [{ game, kind: 'activity', title: '测试活动 · 星海中的约定', subtitle: '隔离界面验收数据', startsAt: `${day}T00:00:00+08:00`, endsAt: `${day}T23:59:59+08:00`, status: '进行中' }] }));
  const results = {
    '米游社': [
      { account_uid: 'fixture-one', account_alias: '合成旅行者', games: [
        { game: '原神', account: '合成旅行者/合成旅行者(100000001)', status: '成功', signedAt: stamp, reward: '原石 × 20' },
        { game: '星穹铁道', account: '合成旅行者/星海旅客(100000002)', status: '失败', signedAt: stamp, reason: '合成登录状态过期，请重新绑定' },
      ] },
      { account_uid: 'fixture-two', account_alias: '另一位测试角色', games: [{ game: '原神', account: '另一位测试角色', status: '成功', reward: '历史记录奖励' }] },
    ],
    '库街区': [{ account_uid: 'fixture-one', account_alias: '合成旅行者', games: [
      { game: '鸣潮', account: '合成旅行者', signedAt: stamp, status: '成功', details: [
        { kind: 'game', status: '成功', reward: '贝币 × 5000' },
        { kind: 'community', status: '成功', reward: '库洛币 × 20' },
      ] },
    ] }],
  };
  return async (request, url) => {
    const body = ['POST','PUT','DELETE'].includes(request.method) ? await request.json().catch(() => ({})) : {};
    options.calls?.push({ path: url.pathname, method: request.method, body });
    if (url.pathname === '/api/session') return { ...ok(), key: 'isolated-ui-fixture' };
    if (url.pathname === '/api/settings') { if (request.method === 'PUT') settings = { ...settings, ...body }; return { ...ok(settings), localConnections: true }; }
    if (url.pathname === '/api/accounts') { if (request.method === 'POST') { const item = { uid: 'fixture-new', data: { Name: '账号 3', Enabled: true } }; accounts.push(item); return ok(item); } return ok(accounts); }
    if (url.pathname === '/api/accounts/roles') return ok(body.platform === '森空岛'
      ? [{ game: '明日方舟', roleName: '合成博士', roleUid: '200000001', server: '测试区服' }, { game: '终末地', roleName: '合成管理员', roleUid: '200000002', server: '测试区服' }]
      : [{ game: '原神', roleName: '合成旅行者', roleUid: '100000001', server: '测试区服' }]);
    if (url.pathname === '/api/accounts/update') { await new Promise(resolve => setTimeout(resolve,450)); const item = accounts.find(item => item.uid === body.accountId); if (item) item.data = body.data; return ok(); }
    if (url.pathname === '/api/accounts/delete') { accounts = accounts.filter(item => item.uid !== body.accountId); return ok(); }
    if (url.pathname === '/api/status') return { ...ok(), today: day, results };
    if (url.pathname === '/api/activity') return ok(notes);
    if (url.pathname === '/api/wiki/calendar-all') return ok(calendar);
    if (url.pathname === '/api/wiki/status') return ok({ ready: true, version: 'fixture', counts: { characters: 2 } });
    if (url.pathname === '/api/wiki/search') return ok([{ kind: 'character', id: 'fixture', name: '测试干员', subtitle: '合成资料卡' }]);
    if (url.pathname === '/api/wiki/entry') return ok({ name: '测试干员', sections: [{ title: '测试属性', fields: [{ label: '生命', value: '1000' }] }] });
    if (url.pathname === '/api/gacha') return { ...ok(Array.from({ length: 8 }, (_, i) => ({ game: url.searchParams.get('game') || 'genshin', id: String(i), playerUid: '100000001', poolType: '301', poolName: '测试角色卡池', name: i % 3 ? '测试武器' : '测试五星角色', rarity: i % 3 ? 3 : 5, time: `${day} 10:30:00` }))), total: 8, players: ['100000001'], pools: [{ poolType: '301', poolName: '测试角色卡池', total: 8, topRarity: 5, topCount: 3, sinceTop: 2 }] };
    if (url.pathname === '/api/gacha/fetch' || url.pathname === '/api/gacha/fetch-cookie') return { ...ok(), added: 0, fetched: 8, warnings: [] };
    if (url.pathname === '/api/logs') return { ...ok([{ id: 1, time: stamp, level: 'INFO', module: '界面检查', requestId: 'fixture', message: '隔离验证，没有读取真实账号' }]), capacity: 2000 };
    if (url.pathname.includes('/qr/create')) return { ...ok(), ticket: 'fixture-ticket', qr_url: 'https://example.invalid/fixture' };
    if (url.pathname.includes('/qr/check')) return { ...ok(), status: 'waiting' };
    if (url.pathname === '/api/mas/snapshot') return { ...ok(), queues: [], tasks: [] };
    return ok([]);
  };
}
module.exports = { fixtures };
