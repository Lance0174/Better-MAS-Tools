import type { ActivitySnapshot } from './useCommunityActivityApi'

export interface NoteMetric {
  name: string
  current: number
  target: number
  status: string
  period: string
}

// 中文名称来自后端便笺合同；历练点、通行证等级及任务积分不属于经验。
const FEATURED_RESOURCES: Record<string, string[]> = {
  明日方舟: ['理智', '无人机', '训练室'],
  终末地: ['理智'],
  原神: ['原粹树脂', '洞天宝钱'],
  星穹铁道: ['开拓力', '储备开拓力'],
  绝区零: ['电量'],
  鸣潮: ['结晶波片'],
}

// 平台与游戏的中文名是后端稳定枚举，这里只做「枚举 → i18n 键」映射；
// 未知值返回 null，调用方直接显示后端原文，避免新平台上线时裸 key 或空白。
const PLATFORM_LABEL_KEYS: Record<string, string> = {
  森空岛: 'gamesign.activity.platform.skland',
  米游社: 'gamesign.activity.platform.miyoushe',
  库街区: 'gamesign.activity.platform.kuro',
  塔吉多: 'gamesign.activity.platform.taygedo',
}

const GAME_LABEL_KEYS: Record<string, string> = {
  明日方舟: 'gamesign.activity.game.arknights',
  终末地: 'gamesign.activity.game.endfield',
  原神: 'gamesign.activity.game.genshin',
  星穹铁道: 'gamesign.activity.game.starrail',
  绝区零: 'gamesign.activity.game.zenless',
  鸣潮: 'gamesign.activity.game.wuthering',
  异环: 'gamesign.activity.game.nte',
}

export const platformLabelKey = (platform: string): string | null =>
  PLATFORM_LABEL_KEYS[platform] ?? null

export const gameLabelKey = (game: string): string | null => GAME_LABEL_KEYS[game] ?? null

export function presentActivity(snapshot: ActivitySnapshot) {
  const visible = (metric: { name: string }) => !/经验|experience|\bexp\b/i.test(metric.name)
  const resources: NoteMetric[] = snapshot.resources.filter(visible).map(resource => ({
    ...resource,
    period: 'resource',
  }))
  const tasks: NoteMetric[] = snapshot.tasks.filter(visible).map(task => ({
    name: task.name,
    current: task.completed,
    target: task.target,
    status: task.status,
    period: task.period,
  }))
  const featured = (FEATURED_RESOURCES[snapshot.game] ?? []).flatMap(name =>
    resources.filter(resource => resource.name === name)
  )
  if (snapshot.game === '绝区零') {
    featured.push(...tasks.filter(task => task.name === '今日活跃度'))
  }
  const remainingResources = resources.filter(resource => !featured.includes(resource))
  const remainingTasks = tasks.filter(task => !featured.includes(task))
  // 鸣潮便笺只有结晶波片一项资源，用单列总览把体力与回满倒计时放大展示。
  const overview =
    snapshot.game === '明日方舟' || snapshot.game === '绝区零' || snapshot.game === '鸣潮'
  const groups = overview
    ? [
        { labelKey: 'gamesign.activity.noteTasks', metrics: remainingTasks },
        { labelKey: 'gamesign.activity.resources', metrics: remainingResources },
      ]
    : [{ labelKey: '', metrics: [...remainingTasks, ...remainingResources] }]
  if (snapshot.game === '明日方舟') groups.reverse()
  return { featured, groups: groups.filter(group => group.metrics.length), overview }
}
