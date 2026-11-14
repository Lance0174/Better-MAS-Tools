import type { WikiCalendarRowOut } from '@/api'

/** 日历统一使用北京时间；结束点为半开区间，午夜结束不占用次日。 */
export function occursOnDay(event: WikiCalendarRowOut, day: string) {
  const start = event.startsAt ? Date.parse(event.startsAt) : NaN
  const end = event.endsAt ? Date.parse(event.endsAt) : NaN
  const from = Date.parse(`${day}T00:00:00+08:00`)
  if (!Number.isFinite(from) || (!Number.isFinite(start) && !Number.isFinite(end))) return false
  return (
    (!Number.isFinite(start) || start < from + 86400000) && (!Number.isFinite(end) || end > from)
  )
}

export function beijingDay(date = new Date()) {
  return new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}
