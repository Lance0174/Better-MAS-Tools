import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ActivitySnapshot } from '@/views/gamesign/useCommunityActivityApi'
import { snapshotKey } from '@/utils/communityDashboard'

const query = vi.hoisted(() => vi.fn())
vi.mock('@/views/gamesign/useCommunityActivityApi', () => ({
  useCommunityActivityApi: () => ({ queryActivity: query }),
}))
import { useActivityStore } from './activity'
const note = (uid: string, value: number) =>
  ({
    accountUid: uid,
    game: '原神',
    platform: '米游社',
    roleUid: uid,
    roleName: uid,
    resources: [{ name: '原粹树脂', current: value, target: 200, status: '' }],
  }) as ActivitySnapshot

beforeEach(() => {
  setActivePinia(createPinia())
  query.mockReset()
})
describe('便笺共享状态', () => {
  it('刷新后保留仍存在的账号选择，删除后安全回退', async () => {
    const first = note('a', 86),
      second = note('b', 164)
    query.mockResolvedValueOnce([first, second])
    const store = useActivityStore()
    await store.load()
    store.select('原神', snapshotKey(second))
    expect(store.current('原神')?.resources[0].current).toBe(164)
    query.mockResolvedValueOnce([first, { ...second, roleName: '已改名' }])
    await store.load(true)
    expect(store.current('原神')?.roleName).toBe('已改名')
    query.mockResolvedValueOnce([first])
    await store.load(true)
    expect(store.current('原神')?.roleUid).toBe('a')
    store.select('原神', '不存在的角色')
    expect(store.current('原神')?.roleUid).toBe('a')
  })
  it('两个页面同时加载时合并请求，失败保留旧快照并暴露错误', async () => {
    let resolve!: (items: ActivitySnapshot[]) => void
    query.mockImplementationOnce(
      () =>
        new Promise<ActivitySnapshot[]>(done => {
          resolve = done
        })
    )
    const store = useActivityStore()
    const first = store.load(),
      second = store.load()
    expect(query).toHaveBeenCalledTimes(1)
    resolve([note('a', 86)])
    await Promise.all([first, second])
    query.mockRejectedValueOnce(new Error('查询失败'))
    await store.load(true)
    expect(store.current('原神')?.resources[0].current).toBe(86)
    expect(store.failure).toBeInstanceOf(Error)
    expect(store.loading).toBe(false)
  })
})
