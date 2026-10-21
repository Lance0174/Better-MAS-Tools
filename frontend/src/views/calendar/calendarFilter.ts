import type { WikiCalendarRowOut } from '@/api'

export type CalendarStatusFilter = 'all' | 'active' | 'running' | 'upcoming' | 'permanent' | 'ended'
export type CalendarSortKey = 'endsAt' | 'startsAt' | 'title'

export interface CalendarFilterOptions {
  statusFilter: string
  sortBy: CalendarSortKey
  hidePermanent: boolean
}

// 排序优先级：进行中 → 即将开始 → 常驻 → 已结束；未知状态排在最后。
const STATUS_ORDER: Record<string, number> = { 进行中: 0, 即将开始: 1, 常驻: 2, 已结束: 3 }

/** 把 ISO 时间解析成毫秒；空值与非法值返回 null，调用方据此排到最后。 */
export function parseCalendarTime(value: string | undefined): number | null {
  if (!value) return null
  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? null : timestamp
}

/** 状态筛选：active 同时包含"进行中"与"即将开始"。 */
export function matchesStatus(status: string | undefined, filter: string): boolean {
  const value = status ?? ''
  switch (filter) {
    case 'active':
      return value.includes('进行') || value.includes('即将')
    case 'running':
      return value.includes('进行')
    case 'upcoming':
      return value.includes('即将')
    case 'permanent':
      return value.includes('常驻')
    case 'ended':
      return value.includes('已结束')
    default:
      return true
  }
}

/**
 * 先按状态分组、再按所选字段排序，最后应用筛选。
 * 时间缺失的条目一律排在最后，避免空值插在中间打乱阅读顺序。
 */
export function filterAndSortActivities(
  activities: WikiCalendarRowOut[],
  options: CalendarFilterOptions
): WikiCalendarRowOut[] {
  const filtered = activities.filter(
    item =>
      matchesStatus(item.status, options.statusFilter) &&
      !(options.hidePermanent && (item.status ?? '').includes('常驻'))
  )
  return [...filtered].sort((left, right) => {
    const rank = (STATUS_ORDER[left.status ?? ''] ?? 9) - (STATUS_ORDER[right.status ?? ''] ?? 9)
    if (rank !== 0) return rank
    if (options.sortBy === 'title') {
      return (left.title || '').localeCompare(right.title || '', 'zh-CN')
    }
    const leftValue = parseCalendarTime(options.sortBy === 'endsAt' ? left.endsAt : left.startsAt)
    const rightValue = parseCalendarTime(options.sortBy === 'endsAt' ? right.endsAt : right.startsAt)
    if (leftValue === null && rightValue === null) return 0
    if (leftValue === null) return 1
    if (rightValue === null) return -1
    return leftValue - rightValue
  })
}
