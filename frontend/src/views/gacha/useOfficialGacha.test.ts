import { effectScope, nextTick, ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AccountOut, GachaRecord } from '@/api'

const api = vi.hoisted(() => ({ listAccountRoles: vi.fn(), listAccounts: vi.fn() }))
vi.mock('@/composables/useCommunityApi', () => ({
  useCommunityApi: () => api,
  errorMessage: (cause: Error) => cause.message,
}))
import { useOfficialGacha } from './useOfficialGacha'

const account = (uid: string) =>
  ({ uid, data: { Name: uid, SklandToken: 'offline-session' } }) as AccountOut
const role = (uid: string, game = '明日方舟') => ({
  game,
  roleUid: uid,
  roleName: '示例旅行者',
  server: 'cn_gf01',
})
let scope = effectScope()
beforeEach(() => {
  scope = effectScope()
  vi.clearAllMocks()
})
afterEach(() => scope.stop())

describe('抽卡使用已登录账号', () => {
  it('森空岛账号自动发现所选游戏角色，不复用米游社凭据', async () => {
    const skland = {
      uid: 'skland',
      data: { Name: '森空岛测试账号', SklandToken: 'offline-session' },
    } as AccountOut
    api.listAccounts.mockResolvedValue({
      data: [{ uid: 'miyoushe', data: { Name: '米游社', MiyousheToken: 'offline' } }, skland],
    })
    api.listAccountRoles.mockResolvedValue({
      data: [role('100001', '明日方舟'), role('200002', '终末地')],
    })
    const state = scope.run(() => useOfficialGacha(ref('arknights'), ref([]), () => '获取失败'))!
    await state.prepare()
    expect(state.options.value.map(item => item.value)).toEqual(['skland'])
    expect(api.listAccountRoles).toHaveBeenLastCalledWith('skland', '森空岛')
    expect(state.playerUid.value).toBe('100001')
  })

  it('准备途中切换游戏，不让旧账号列表重新触发当前角色读取', async () => {
    let release!: (value: { data: AccountOut[] }) => void
    api.listAccounts.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          release = resolve
        })
    )
    const game = ref<GachaRecord['game']>('arknights')
    const state = scope.run(() => useOfficialGacha(game, ref([]), () => '获取失败'))!
    const pending = state.prepare()
    game.value = 'endfield'
    release({ data: [account('old')] })
    await pending
    expect(state.options.value).toEqual([])
    expect(state.playerUid.value).toBe('')
  })
  it('唯一账号与对应游戏的唯一角色直接就绪，不需要输入 Cookie', async () => {
    api.listAccounts.mockResolvedValue({ data: [account('a')] })
    api.listAccountRoles.mockResolvedValue({ data: [role('100001'), role('200002', '星穹铁道')] })
    const state = scope.run(() => useOfficialGacha(ref('arknights'), ref([]), () => '获取失败'))!
    await state.prepare()
    await nextTick()
    await Promise.resolve()
    expect(state.accountId.value).toBe('a')
    expect(state.playerUid.value).toBe('100001')
  })

  it('换账号立即清除 UID，迟到的旧角色不能串入新账号', async () => {
    let release!: (value: { data: ReturnType<typeof role>[] }) => void
    api.listAccountRoles
      .mockImplementationOnce(
        () =>
          new Promise(resolve => {
            release = resolve
          })
      )
      .mockResolvedValue({ data: [role('222')] })
    const accounts = ref([account('a'), account('b')])
    const state = scope.run(() => useOfficialGacha(ref('arknights'), accounts, () => '获取失败'))!
    state.accountId.value = 'a'
    await nextTick()
    state.playerUid.value = '111'
    state.accountId.value = 'b'
    await nextTick()
    expect(state.playerUid.value).not.toBe('111')
    release({ data: [role('111')] })
    await Promise.resolve()
    await nextTick()
    expect(state.playerUid.value).toBe('222')
  })

  it('多角色需明确选择，读取失败保留账号以便手填 UID', async () => {
    api.listAccounts.mockResolvedValue({ data: [account('a')] })
    api.listAccountRoles.mockResolvedValue({ data: [role('101'), role('102')] })
    const state = scope.run(() => useOfficialGacha(ref('arknights'), ref([]), () => '获取失败'))!
    await state.prepare()
    expect(state.playerUid.value).toBe('')
    api.listAccountRoles.mockRejectedValueOnce(new Error('角色读取失败'))
    await state.prepare()
    expect(state.roles.value).toEqual([])
    expect(state.issue.value).toBe('角色读取失败')
    expect(state.accountId.value).toBe('a')
  })

  it.each(['genshin', 'starrail', 'zzz', 'wuthering', 'endfield'] as const)(
    '%s 不读取已登录账号或角色',
    async game => {
      const state = scope.run(() => useOfficialGacha(ref(game), ref([account('a')]), () => '失败'))!
      await state.prepare()
      expect(state.options.value).toEqual([])
      expect(state.accountId.value).toBe('')
      expect(api.listAccounts).not.toHaveBeenCalled()
      expect(api.listAccountRoles).not.toHaveBeenCalled()
    }
  )

  it('角色读取中切走再切回，旧响应被丢弃并可重新读取', async () => {
    let release!: (value: { data: ReturnType<typeof role>[] }) => void
    api.listAccountRoles
      .mockImplementationOnce(
        () =>
          new Promise(resolve => {
            release = resolve
          })
      )
      .mockResolvedValue({ data: [role('333')] })
    const game = ref<GachaRecord['game']>('arknights')
    const state = scope.run(() => useOfficialGacha(game, ref([account('a')]), () => '失败'))!
    game.value = 'endfield'
    release({ data: [role('111')] })
    await nextTick()
    expect(state.roles.value).toEqual([])
    game.value = 'arknights'
    await nextTick()
    expect(state.playerUid.value).toBe('333')
  })
})
