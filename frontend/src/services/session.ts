import { OpenAPI, SessionService } from '@/api'

export class LoginRequiredError extends Error {}

/** 本机同源握手；短时会话标记只保留在内存，不写浏览器存储。 */
export async function connectSession(password?: string): Promise<void> {
  let data = await SessionService.getSession()
  if (data.loginRequired) {
    if (!password) throw new LoginRequiredError()
    data = await SessionService.loginSession({ password })
  }
  if (!data.key) throw new Error('会话响应无效')
  OpenAPI.BASE = ''
  OpenAPI.HEADERS = { 'X-Community-Session': data.key }
}
