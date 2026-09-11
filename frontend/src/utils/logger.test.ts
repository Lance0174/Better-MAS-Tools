import { afterEach, describe, expect, it, vi } from 'vitest'
import { DiagnosticsService } from '@/api'
import { getLogger } from './logger'

vi.mock('@/api', () => ({
  DiagnosticsService: { writeClientLog: vi.fn().mockResolvedValue({ code: 200 }) },
}))
afterEach(() => vi.restoreAllMocks())

describe('前端诊断日志', () => {
  it('控制台与后端都只接收脱敏后的凭据和 URL', () => {
    const output = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    getLogger('登录').error(
      'stoken_v2=fixture-secret https://example.test/path?authkey=fixture-auth 13800000000'
    )
    const text = String(output.mock.calls[0]?.[0])
    expect(text).not.toContain('fixture-secret')
    expect(text).not.toContain('fixture-auth')
    expect(text).not.toContain('13800000000')
    expect(DiagnosticsService.writeClientLog).toHaveBeenLastCalledWith({
      module: '登录',
      level: 'ERROR',
      message: 'stoken_v2=*** https://example.test/path ***',
    })
  })
  it('后端不可用时不递归发送错误日志', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    vi.mocked(DiagnosticsService.writeClientLog).mockRejectedValueOnce(new Error('offline'))
    const before = vi.mocked(DiagnosticsService.writeClientLog).mock.calls.length
    getLogger('连接').warn('backend unavailable')
    await Promise.resolve()
    expect(vi.mocked(DiagnosticsService.writeClientLog).mock.calls.length).toBe(before + 1)
  })
  it('森空岛凭据、验证证明和含空格的密码也在控制台前脱敏', () => {
    const output = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    const values = Object.fromEntries(
      ['cred', 'mid', 'captcha_output', 'geetest_validate', 'x-community-session', 'password'].map(
        (key, index) => [key, `fixture private ${index}`]
      )
    )
    getLogger('验证').error(JSON.stringify(values))
    const consoleText = String(output.mock.calls[0]?.[0])
    const posted = vi.mocked(DiagnosticsService.writeClientLog).mock.lastCall?.[0]?.message ?? ''
    for (const value of Object.values(values)) {
      expect(consoleText).not.toContain(value)
      expect(posted).not.toContain(value)
    }
    expect(consoleText).not.toContain('private')
  })
})
