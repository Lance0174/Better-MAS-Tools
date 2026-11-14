import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const api = vi.hoisted(() => ({ all: vi.fn() }))
vi.mock('@/composables/useCalendarApi', () => ({ useCalendarApi: () => api }))
import { useCalendarStore } from './calendar'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})
describe('日历状态提示', () => {
  it('正常加载不展示默认的操作成功条，部分失败仍保留说明', async () => {
    api.all
      .mockResolvedValueOnce({ code: 200, status: 'success', message: '操作成功', data: [] })
      .mockResolvedValueOnce({
        code: 200,
        status: 'partial',
        message: '部分游戏暂不可用',
        data: [],
      })
    const store = useCalendarStore()
    await store.load()
    expect(store.notice).toBe('')
    await store.load()
    expect(store.notice).toBe('部分游戏暂不可用')
  })
})
