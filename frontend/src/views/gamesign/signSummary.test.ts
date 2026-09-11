import { describe, expect, it } from 'vitest'
import { getAccountSignSteps, getSignSummaryState, summarizeSignResults } from './signSummary'

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
    expect(
      summarizeSignResults(
        [{ games: [{ status: '成功', signedAt: '2026-09-10T08:00:00+08:00' }] }, { games: [] }],
        '2026-09-10'
      )
    ).toEqual({ success: 1, failed: 0, pending: 1 })
  })

  it('游戏已签到但库洛币失败时分别计数，并显示部分失败', () => {
    const counts = summarizeSignResults(
      [
        {
          games: [
            {
              game: '鸣潮',
              status: '失败',
              signedAt: '2026-09-11T22:00:00+08:00',
              details: [
                { kind: 'game', status: '已签到', reward: '星声x20' },
                { kind: 'community', status: '失败', reason: '参数错误' },
              ],
            },
          ],
        },
      ],
      '2026-09-11'
    )
    expect(counts).toEqual({ success: 1, failed: 1, pending: 0 })
    expect(getSignSummaryState(counts)).toBe('partial')
  })

  it('多游戏账号的库洛币只计一次，并放在游戏结果之后', () => {
    const account = {
      games: [
        {
          game: '战双帕弥什',
          status: '失败',
          signedAt: '2026-09-11T22:00:00+08:00',
          details: [
            { kind: 'game' as const, status: '成功', reward: '测试奖励x1' },
            { kind: 'community' as const, status: '失败', reason: '参数错误' },
          ],
        },
        {
          game: '鸣潮',
          status: '失败',
          signedAt: '2026-09-11T22:00:00+08:00',
          details: [{ kind: 'game' as const, status: '已签到' }],
        },
      ],
    }
    const before = JSON.stringify(account)
    expect(summarizeSignResults([account], '2026-09-11')).toEqual({
      success: 2,
      failed: 1,
      pending: 0,
    })
    expect(getAccountSignSteps(account).map(step => [step.kind, step.game])).toEqual([
      ['game', '战双帕弥什'],
      ['game', '鸣潮'],
      ['community', '战双帕弥什'],
    ])
    expect(JSON.stringify(account)).toBe(before)
  })

  it('历史合并结果同时保留奖励与错误，不能从文案推断分项成功', () => {
    const account = {
      games: [
        {
          game: '鸣潮',
          status: '失败',
          reward: '星声x20',
          reason: '游戏签到已完成；社区打卡：参数错误',
          signedAt: '2026-09-11T22:00:00+08:00',
        },
      ],
    }
    expect(getAccountSignSteps(account)[0]).toMatchObject({
      kind: 'combined',
      status: '失败',
      reward: '星声x20',
      reason: account.games[0].reason,
    })
    const counts = summarizeSignResults([account], '2026-09-11')
    expect(counts).toEqual({ success: 0, failed: 1, pending: 0 })
    expect(getSignSummaryState(counts)).toBe('failed')
  })

  it('昨天的分项成功不能显示为今天全部成功', () => {
    const counts = summarizeSignResults(
      [
        {
          games: [
            {
              status: '成功',
              signedAt: '2026-09-10T22:00:00+08:00',
              details: [
                { kind: 'game', status: '已签到' },
                { kind: 'community', status: '成功' },
              ],
            },
          ],
        },
      ],
      '2026-09-11'
    )
    expect(counts).toEqual({ success: 0, failed: 0, pending: 2 })
    expect(getSignSummaryState(counts)).toBe('pending')
  })
})
