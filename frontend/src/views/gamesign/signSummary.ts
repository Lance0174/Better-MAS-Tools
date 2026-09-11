import type { SignAccountOut } from '@/api'

/** 历史结果缺少时间时视为尚未确认，不能推断成今天成功。 */
export function summarizeSignResults(accounts: SignAccountOut[], today: string) {
  let success = 0
  let failed = 0
  let pending = 0
  for (const account of accounts) {
    if (!account.games?.length) pending++
    for (const game of account.games ?? []) {
      if (!today || game.signedAt?.slice(0, 10) !== today) {
        pending++
      } else if (game.status === '成功' || game.status === '已签到') {
        // 中文状态是后端协议，不能翻译后比较。
        success++
      } else {
        failed++
      }
    }
  }
  return { success, failed, pending }
}
