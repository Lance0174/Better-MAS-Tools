import { CommunityService } from '@/api'

/** 保留已迁移扫码状态机的调用契约，所有请求均来自生成客户端。 */
export function useGameSignApi() {
  return {
    createMiyousheQr: () => CommunityService.createQr('miyoushe'),
    checkMiyousheQr: (ticket: string, device: string) =>
      CommunityService.checkQr('miyoushe', { ticket, device }),
    saveMiyousheQr: (accountUid: string, cookie: string) =>
      CommunityService.saveQr('miyoushe', { account_uid: accountUid, cookie }),
    createSklandQr: () => CommunityService.createQr('skland'),
    checkSklandQr: (ticket: string, device: string) =>
      CommunityService.checkQr('skland', { ticket, device }),
    saveSklandQr: (accountUid: string, scanCode: string) =>
      CommunityService.saveQr('skland', { account_uid: accountUid, scan_code: scanCode }),
  }
}
