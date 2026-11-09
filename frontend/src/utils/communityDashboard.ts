import type { SignAccountOut } from '@/api'
import type { ActivitySnapshot } from '@/views/gamesign/useCommunityActivityApi'
import { getAccountSignSteps } from '@/views/gamesign/signSummary'

// 中文名称是后端游戏契约；日历使用英文 ID，便笺与签到使用中文名称。
export const GAME_NAMES: Record<string, string> = {
  arknights: '明日方舟',
  endfield: '终末地',
  genshin: '原神',
  starrail: '星穹铁道',
  zenless: '绝区零',
  wutheringwaves: '鸣潮',
  nte: '异环',
  stellasora: '星塔旅人',
  infinitynikki: '无限暖暖',
}
const BACKGROUNDS: Record<string, string> = {
  arknights: 'arknights-background.webp?v=6a23195b201d',
  endfield: 'endfield-background.webp?v=9d3a6fee469e',
  genshin: 'genshin-background.webp?v=f06788a6cb81',
  starrail: 'star-rail-background.webp?v=1048d29ea88f',
  zenless: 'zenless-background.webp?v=e4f8798de02c',
}
export function gameBackground(game: string) {
  const key = Object.keys(GAME_NAMES).find(key => key === game || GAME_NAMES[key] === game)
  const file = key ? BACKGROUNDS[key] : undefined
  return file ? `https://doc.auto-mas.top/community-notes/${file}` : ''
}
export const snapshotKey = (snapshot: ActivitySnapshot) =>
  JSON.stringify([
    snapshot.accountUid,
    snapshot.platform,
    snapshot.game,
    snapshot.server,
    snapshot.roleUid,
    snapshot.roleUid ? '' : snapshot.roleName,
  ])

export function groupSnapshots(snapshots: ActivitySnapshot[], order: string[] = []) {
  const groups = new Map<string, ActivitySnapshot[]>()
  for (const snapshot of snapshots) {
    const group = groups.get(snapshot.game) ?? []
    group.push(snapshot)
    groups.set(snapshot.game, group)
  }
  const keys = [...new Set([...order, ...groups.keys()])].filter(game => groups.has(game))
  return keys.map(game => ({ game, snapshots: groups.get(game)! }))
}

/** 首页只展示所选游戏的真实结果；缺日期、旧结果和未执行均保留待确认状态。 */
export function homeSignRows(
  results: Record<string, SignAccountOut[]>,
  game: string,
  today: string
) {
  return Object.entries(results).flatMap(([platform, accounts]) =>
    accounts.flatMap(account =>
      getAccountSignSteps(account)
        .filter(step => step.game === game)
        .map((step, index) => {
          const current = Boolean(today) && step.signedAt?.slice(0, 10) === today
          const success = current && (step.status === '成功' || step.status === '已签到')
          return {
            key: JSON.stringify([platform, account.account_uid, step.game, index]),
            name: step.account || account.account_alias || '',
            platform,
            status: current ? step.status : '',
            reward: current ? step.reward : '',
            reason: current ? step.reason : '',
            state: success ? 'success' : current ? 'error' : 'pending',
          }
        })
    )
  )
}
