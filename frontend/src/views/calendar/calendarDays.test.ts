import type { WikiCalendarRowOut } from '@/api'
import { describe, expect, it } from 'vitest'
import { beijingDay, occursOnDay } from './calendarDays'

describe('北京时间活动日期', () => {
  const base = { title: 'fixture', game: 'genshin', kind: 'activity' } as const
  it('处理跨时区与午夜结束边界', () => {
    const event: WikiCalendarRowOut = {
      ...base,
      startsAt: '2026-11-13T16:00:00Z',
      endsAt: '2026-11-15T00:00:00+08:00',
    }
    expect(occursOnDay(event, '2026-11-13')).toBe(false)
    expect(occursOnDay(event, '2026-11-14')).toBe(true)
    expect(occursOnDay(event, '2026-11-15')).toBe(false)
    expect(beijingDay(new Date('2026-11-13T16:01:00Z'))).toBe('2026-11-14')
  })
  it('不为无日期条目猜测日程，允许只有起点或终点的活动', () => {
    expect(occursOnDay({ ...base }, '2026-11-14')).toBe(false)
    expect(occursOnDay({ ...base, startsAt: '2026-11-14T12:00:00+08:00' }, '2026-11-14')).toBe(true)
    expect(occursOnDay({ ...base, endsAt: '2026-11-14T20:00:00+08:00' }, '2026-11-15')).toBe(false)
  })
})
