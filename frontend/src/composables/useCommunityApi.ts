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
  if (response.code !== undefined && response.code !== 200)
    throw new Error(response.message || '操作未完成')
  return response
}

export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    const body: unknown = error.body
    if (body && typeof body === 'object' && 'message' in body && typeof body.message === 'string')
      return body.message
  }
  return error instanceof Error ? error.message : fallback
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
