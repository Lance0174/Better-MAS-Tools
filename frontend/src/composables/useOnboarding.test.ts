import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { isOnboardingDone, markOnboardingDone, useOnboarding } from './useOnboarding'

const KEY = 'bmat-onboarding-done'

/** 默认环境没有 jsdom，用最小实现替代 localStorage，只覆盖代码用到的读写。 */
const createStorage = () => {
  const store = new Map<string, string>()
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value)
    },
    removeItem: (key: string) => {
      store.delete(key)
    },
    clear: () => {
      store.clear()
    },
  }
}

beforeEach(() => {
  vi.stubGlobal('localStorage', createStorage())
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('首启引导标记', () => {
  it('未写过标记时不认为已处理', () => {
    expect(isOnboardingDone()).toBe(false)
  })

  it('写入标记后认为已处理，值固定为 1', () => {
    markOnboardingDone()
    expect(localStorage.getItem(KEY)).toBe('1')
    expect(isOnboardingDone()).toBe(true)
  })
})

describe('useOnboarding', () => {
  it('桌面端口改变导致浏览器存储清空后仍尊重后端的跳过标记', async () => {
    let saved = false
    const first = useOnboarding({
      isDone: () => saved,
      saveDone: async () => { saved = true },
    })
    first.maybeShow()
    await first.skip()
    localStorage.clear()
    const nextLaunch = useOnboarding({ isDone: () => saved })
    nextLaunch.maybeShow()
    expect(nextLaunch.open.value).toBe(false)
    nextLaunch.show()
    expect(nextLaunch.open.value).toBe(true)
  })

  it('跳过保存失败时报告失败，并保持本次会话关闭状态', async () => {
    const onFailure = vi.fn()
    const onboarding = useOnboarding({
      saveDone: async () => { throw new Error('offline') },
      onFailure,
    })
    onboarding.maybeShow()
    await onboarding.skip()
    localStorage.clear()
    onboarding.maybeShow()
    expect(onboarding.open.value).toBe(false)
    expect(onFailure).toHaveBeenCalledOnce()
  })

  it('旧版本地标记会迁移到持久化设置', () => {
    markOnboardingDone()
    const saveDone = vi.fn(async () => {})
    const onboarding = useOnboarding({ saveDone })
    onboarding.maybeShow()
    expect(saveDone).toHaveBeenCalledOnce()
    expect(onboarding.open.value).toBe(false)
  })

  it('跳过：写入标记并关闭，之后不再自动打开', () => {
    const onboarding = useOnboarding()
    onboarding.show()
    expect(onboarding.open.value).toBe(true)

    onboarding.skip()

    expect(localStorage.getItem(KEY)).toBe('1')
    expect(onboarding.open.value).toBe(false)
    onboarding.maybeShow()
    expect(onboarding.open.value).toBe(false)
  })

  it('完成：与跳过共用同一标记', () => {
    const onboarding = useOnboarding()
    onboarding.complete()
    expect(localStorage.getItem(KEY)).toBe('1')
    expect(onboarding.open.value).toBe(false)
  })

  it('未写过标记时 maybeShow 自动打开', () => {
    const onboarding = useOnboarding()
    onboarding.maybeShow()
    expect(onboarding.open.value).toBe(true)
  })

  it('已跳过时“重新查看引导”仍能打开，且不清除已跳过状态', () => {
    const onboarding = useOnboarding()
    onboarding.skip()

    // 设置页“重新查看引导”走 show()：只打开，不写也不清标记。
    onboarding.show()
    expect(onboarding.open.value).toBe(true)
    expect(localStorage.getItem(KEY)).toBe('1')

    // 看完关闭后，也不会因此又在下次启动自动弹出。
    onboarding.hide()
    onboarding.maybeShow()
    expect(onboarding.open.value).toBe(false)
  })

  it('存储不可用时不抛错，按未处理处理', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('storage disabled')
      },
      setItem: () => {
        throw new Error('storage disabled')
      },
    })
    expect(isOnboardingDone()).toBe(false)
    expect(() => markOnboardingDone()).not.toThrow()
    const onboarding = useOnboarding()
    onboarding.maybeShow()
    expect(onboarding.open.value).toBe(true)
  })
})
