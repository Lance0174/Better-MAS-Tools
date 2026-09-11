import type { SignAccountOut } from '@/api'

/** 共享的库洛币签到放在游戏结果之后；旧记录保留合并状态，不猜测分项成功。 */
export function getAccountSignSteps(account: SignAccountOut) {
  return (account.games ?? [])
    .flatMap(game => {
      const details = game.details?.length
        ? game.details
        : [
            {
              kind: 'combined' as const,
              status: game.status,
              reward: game.reward,
              reason: game.reason,
            },
          ]
      return details.map(detail => ({
        ...detail,
        game: game.game,
        account: detail.kind === 'community' ? '' : game.account,
        signedAt: game.signedAt,
      }))
    })
    .sort(
      (first, second) => Number(first.kind === 'community') - Number(second.kind === 'community')
    )
}

/** 历史结果缺少时间时视为尚未确认，不能推断成今天成功。 */
export function summarizeSignResults(accounts: SignAccountOut[], today: string) {
  let success = 0
  let failed = 0
  let pending = 0
  for (const account of accounts) {
    const steps = getAccountSignSteps(account)
    if (!steps.length) pending++
    for (const step of steps) {
      if (!today || step.signedAt?.slice(0, 10) !== today) {
        pending++
      } else if (step.status === '成功' || step.status === '已签到') {
        // 中文状态是后端协议，不能翻译后比较。
        success++
      } else {
        failed++
      }
    }
  }
  return { success, failed, pending }
}

export function getSignSummaryState(counts: ReturnType<typeof summarizeSignResults>) {
  if (counts.failed) return counts.success ? 'partial' : 'failed'
  if (counts.pending || !counts.success) return 'pending'
  return 'success'
}
