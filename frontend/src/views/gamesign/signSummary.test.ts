import { describe, expect, it } from 'vitest'
import { summarizeSignResults } from './signSummary'

describe('今日签到整体情况', () => {
  it('成功和已签到均算成功，风控保留失败', () => {
    expect(
      summarizeSignResults(
        [
          {
            games: ['成功', '已签到', '风控'].map(status => ({
              status,
              signedAt: '2026-09-10T08:00:00+08:00',
            })),
          },
        ],
        '2026-09-10'
      )
    ).toEqual({ success: 2, failed: 1, pending: 0 })
  })
  it('昨天成功及无日期的旧版本结果不能算今日成功', () => {
    expect(
      summarizeSignResults(
        [
          {
            games: [
              { status: '成功', signedAt: '2026-09-09T23:59:59+08:00' },
              { status: '成功' },
              { status: '失败', signedAt: '2026-09-10T00:00:00+08:00' },
            ],
          },
        ],
        '2026-09-10'
      )
    ).toEqual({ success: 0, failed: 1, pending: 2 })
  })
  it('没有结果时不产生成功数', () => {
    expect(summarizeSignResults([], '2026-09-10')).toEqual({ success: 0, failed: 0, pending: 0 })
  })
  it('已有成功但新账号未执行时不能算全部成功', () => {
    expect(summarizeSignResults([
      { games: [{ status: '成功', signedAt: '2026-09-10T08:00:00+08:00' }] },
      { games: [] },
    ], '2026-09-10')).toEqual({ success: 1, failed: 0, pending: 1 })
  })
})
