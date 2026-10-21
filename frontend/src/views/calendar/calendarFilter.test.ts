import { describe, expect, it } from 'vitest'
import { filterAndSortActivities, matchesStatus, parseCalendarTime } from './calendarFilter'

const row = (over: Record<string, unknown> = {}) => ({
  game: 'endfield' as const,
  kind: 'activity' as const,
  title: '占位',
  subtitle: '',
  startsAt: '',
  endsAt: '',
  banner: '',
  status: '进行中',
  ...over,
})

describe('日历筛选与排序', () => {
  it('按状态分组排序：进行中 → 即将开始 → 常驻 → 已结束', () => {
    const result = filterAndSortActivities(
      [
        row({ title: '已结束的', status: '已结束' }),
        row({ title: '常驻的', status: '常驻' }),
        row({ title: '即将的', status: '即将开始' }),
        row({ title: '进行中的', status: '进行中' }),
      ],
      { statusFilter: 'all', sortBy: 'endsAt', hidePermanent: false }
    )
    expect(result.map(item => item.title)).toEqual(['进行中的', '即将的', '常驻的', '已结束的'])
  })

  it('同状态内按结束时间升序，缺失时间的排在最后', () => {
    const result = filterAndSortActivities(
      [
        row({ title: '无结束时间', endsAt: '' }),
        row({ title: '晚结束', endsAt: '2026-11-11T00:00:00+08:00' }),
        row({ title: '早结束', endsAt: '2026-10-20T00:00:00+08:00' }),
      ],
      { statusFilter: 'all', sortBy: 'endsAt', hidePermanent: false }
    )
    expect(result.map(item => item.title)).toEqual(['早结束', '晚结束', '无结束时间'])
  })

  it('可按名称排序', () => {
    const result = filterAndSortActivities(
      [row({ title: 'b' }), row({ title: 'a' })],
      { statusFilter: 'all', sortBy: 'title', hidePermanent: false }
    )
    expect(result.map(item => item.title)).toEqual(['a', 'b'])
  })

  it('隐藏常驻时排除常驻条目', () => {
    const result = filterAndSortActivities(
      [row({ title: '常驻的', status: '常驻' }), row({ title: '进行中的' })],
      { statusFilter: 'all', sortBy: 'endsAt', hidePermanent: true }
    )
    expect(result.map(item => item.title)).toEqual(['进行中的'])
  })

  it('状态筛选覆盖进行中/即将开始/常驻/已结束与合并项', () => {
    expect(matchesStatus('进行中', 'running')).toBe(true)
    expect(matchesStatus('即将开始', 'running')).toBe(false)
    expect(matchesStatus('即将开始', 'upcoming')).toBe(true)
    expect(matchesStatus('常驻', 'permanent')).toBe(true)
    expect(matchesStatus('已结束', 'ended')).toBe(true)
    // active 同时包含进行中与即将开始
    expect(matchesStatus('进行中', 'active')).toBe(true)
    expect(matchesStatus('即将开始', 'active')).toBe(true)
    expect(matchesStatus('已结束', 'active')).toBe(false)
    expect(matchesStatus('', 'all')).toBe(true)
  })

  it('时间解析对空值与非法值返回 null', () => {
    expect(parseCalendarTime('')).toBeNull()
    expect(parseCalendarTime('不是时间')).toBeNull()
    expect(parseCalendarTime('2026-10-20T00:00:00+08:00')).toBeTypeOf('number')
  })
})
