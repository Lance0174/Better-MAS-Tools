import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { afterEach, describe, expect, it, vi } from 'vitest'

const source = readFileSync(new URL('../../public/captcha.js', import.meta.url), 'utf8')

function bridge(version: 3 | 4 = 4) {
  vi.useFakeTimers()
  const listeners: Record<string, () => void> = {}
  const events: Record<string, () => void> = {}
  const status = { textContent: '' }
  const script = { src: '', onload: () => {}, onerror: () => {} }
  const proof = { captcha_id: 'fixture-id', pass_token: 'fixture-proof' }
  const captcha = {
    onReady: (fn: () => void) => {
      events.ready = fn
    },
    onSuccess: (fn: () => void) => {
      events.success = fn
    },
    onError: (fn: () => void) => {
      events.error = fn
    },
    onClose: (fn: () => void) => {
      events.close = fn
    },
    appendTo: vi.fn(),
    showCaptcha: vi.fn(),
    destroy: vi.fn(),
    getValidate: () => proof,
  }
  const initialize = vi.fn((_options, callback) => callback(captcha))
  const postMessage = vi.fn()
  runInNewContext(source, {
    location: {
      hash:
        '#' +
        encodeURIComponent(
          JSON.stringify({
            version,
            captchaId: 'fixture-id',
            gt: 'fixture-gt',
            challenge: 'fixture-challenge',
            nonce: 'fixture-nonce',
            parentOrigin: 'https://community.test',
          })
        ),
    },
    document: {
      getElementById: () => status,
      createElement: () => script,
      head: { append: vi.fn() },
    },
    parent: { postMessage },
    window: {
      initGeetest4: initialize,
      initGeetest: initialize,
      addEventListener: (name: string, fn: () => void) => {
        listeners[name] = fn
      },
    },
    setTimeout,
    clearTimeout,
  })
  return { script, captcha, initialize, postMessage, events, listeners, proof }
}

afterEach(() => vi.useRealTimers())

describe('验证码隔离页的加载和消息桥接', () => {
  it('极验4就绪后显示挑战并只向父页面来源传回结果', () => {
    const app = bridge()
    app.script.onload()
    expect(app.initialize.mock.calls[0]?.[0]).toMatchObject({
      product: 'bind',
      protocol: 'https://',
    })
    app.events.ready!()
    expect(app.captcha.showCaptcha).toHaveBeenCalledOnce()
    app.events.success!()
    expect(app.postMessage).toHaveBeenLastCalledWith(
      { kind: 'community-captcha', nonce: 'fixture-nonce', solution: app.proof },
      'https://community.test'
    )
    vi.advanceTimersByTime(25000)
    expect(app.postMessage.mock.calls.some(([data]) => data.error)).toBe(false)
  })

  it('极验3直接嵌入内容，不使用容易被iframe裁切的浮层', () => {
    const app = bridge(3)
    app.script.onload()
    expect(app.initialize.mock.calls[0]?.[0]).toMatchObject({ product: 'embed', https: true })
    expect(app.captcha.appendTo).toHaveBeenCalledWith('#captcha')
  })

  it('SDK网络挂起20秒后报告失败，迟到回调不能再次初始化', () => {
    const app = bridge()
    vi.advanceTimersByTime(20000)
    expect(app.postMessage).toHaveBeenCalledWith(
      { kind: 'community-captcha', nonce: 'fixture-nonce', error: true, reason: 'timeout' },
      'https://community.test'
    )
    app.script.onload()
    expect(app.initialize).not.toHaveBeenCalled()
  })

  it('SDK资源错误立即报告；卸载销毁实例和加载定时器', () => {
    const app = bridge()
    app.script.onload()
    app.script.onerror()
    app.listeners.pagehide!()
    expect(app.captcha.destroy).toHaveBeenCalledOnce()
    vi.advanceTimersByTime(25000)
    expect(app.postMessage.mock.calls.filter(([data]) => data.error)).toHaveLength(1)
  })

  it('旧后端阻断官方资源时立即给出策略错误，关闭挑战只取消验证', () => {
    const blocked = bridge()
    blocked.script.onload()
    blocked.listeners.securitypolicyviolation!()
    expect(blocked.postMessage).toHaveBeenLastCalledWith(
      { kind: 'community-captcha', nonce: 'fixture-nonce', error: true, reason: 'policy' },
      'https://community.test'
    )
    const closed = bridge()
    closed.script.onload()
    closed.events.close!()
    expect(closed.postMessage).toHaveBeenLastCalledWith(
      { kind: 'community-captcha', nonce: 'fixture-nonce', closed: true },
      'https://community.test'
    )
  })
})
