import axios from 'axios'
import {
  ApiError,
  CommunityService,
  KuroLoginService,
  MiyousheMissionsService,
  type GeetestV3Data,
  type GeetestV4Data,
  type AccountUpdateIn,
  type SettingsData,
  type OutBase,
} from '@/api'

export function assertSuccess<T extends OutBase>(response: T): T {
  // 后端没给 message 时抛空消息，由 errorMessage 用调用方传入的本地化兜底补文本，
  // 避免在语言无关的桥接层硬编码一份中文提示。
  if (response.code !== undefined && response.code !== 200)
    throw new Error(response.message ?? '')
  return response
}

/**
 * 统一错误文案：后端业务消息 > 自有异常消息 > 调用方传入的 i18n 兜底。
 * axios 的网络/超时错误只有英文 message（如 Network Error），对用户没有信息量，直接走兜底。
 */
export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const body: unknown = error.body
    if (
      body &&
      typeof body === 'object' &&
      'message' in body &&
      typeof body.message === 'string' &&
      body.message.trim()
    )
      return body.message
    // 生成客户端自带的 message 是英文状态描述，没有业务文案时交给兜底。
    return fallback
  }
  if (axios.isAxiosError(error)) return fallback
  if (error instanceof Error && error.message.trim()) return error.message
  return fallback
}

export function useCommunityApi() {
  return {
    miyousheVerifications: () => MiyousheMissionsService.listMiyousheVerifications().then(assertSuccess),
    submitMiyousheVerification: (sessionId: string, verification: GeetestV3Data) => MiyousheMissionsService.submitMiyousheVerification({ sessionId, verification }).then(assertSuccess),
    automaticKuroSms: (sessionId: string) => KuroLoginService.automaticKuroSms({ sessionId }).then(assertSuccess),
    listAccounts: () => CommunityService.listAccounts().then(assertSuccess),
    createAccount: () => CommunityService.createAccount().then(assertSuccess),
    updateAccount: (body: AccountUpdateIn) =>
      CommunityService.updateAccount(body).then(assertSuccess),
    deleteAccount: (accountId: string) =>
      CommunityService.deleteAccount({ accountId }).then(assertSuccess),
    reorderAccounts: (order: string[]) =>
      CommunityService.reorderAccounts({ order }).then(assertSuccess),
    status: () => CommunityService.getStatus().then(assertSuccess),
    sign: () => CommunityService.manualSign().then(assertSuccess),
    getSettings: () => CommunityService.getSettings().then(assertSuccess),
    updateSettings: (data: SettingsData) =>
      CommunityService.updateSettings(data).then(assertSuccess),
    loginTaygedo: (accountId: string, phone: string, password: string) =>
      CommunityService.loginTaygedo({ accountId, phone, password }).then(assertSuccess),
    createKuroSms: (accountId: string, phone: string) =>
      KuroLoginService.createKuroSms({ accountId, phone }).then(assertSuccess),
    sendKuroSms: (sessionId: string, verification: GeetestV4Data) =>
      KuroLoginService.sendKuroSms({ sessionId, verification }).then(assertSuccess),
    loginKuroSms: (sessionId: string, smsCode: string) =>
      KuroLoginService.loginKuroSms({ sessionId, smsCode }).then(assertSuccess),
    cancelKuroSms: (sessionId: string) =>
      KuroLoginService.cancelKuroSms({ sessionId }).then(assertSuccess),
  }
}
