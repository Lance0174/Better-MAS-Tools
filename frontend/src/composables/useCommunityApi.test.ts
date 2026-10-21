import { AxiosError } from 'axios'
import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api'
import type { ApiRequestOptions } from '@/api/core/ApiRequestOptions'
import type { ApiResult } from '@/api/core/ApiResult'
import { assertSuccess, errorMessage } from './useCommunityApi'

const request: ApiRequestOptions = { method: 'GET', url: '/api/demo' }
const apiResult = (body: unknown): ApiResult => ({
  url: '/api/demo',
  ok: false,
  status: 400,
  statusText: 'Bad Request',
  body,
})

describe('errorMessage', () => {
  it('网络错误用传入的兜底文案，而不是英文 Network Error', () => {
    expect(errorMessage(new AxiosError('Network Error'), '加载失败，请稍后重试')).toBe(
      '加载失败，请稍后重试'
    )
  })

  it('后端业务消息优先于兜底文案', () => {
    const error = new ApiError(request, apiResult({ message: '凭据已失效' }), 'Bad Request')
    expect(errorMessage(error, '兜底文案')).toBe('凭据已失效')
  })

  it('ApiError 没有业务消息时用兜底，而不是英文状态描述', () => {
    const error = new ApiError(request, apiResult({}), 'Bad Request')
    expect(errorMessage(error, '兜底文案')).toBe('兜底文案')
  })

  it('assertSuccess 缺少业务消息时同样走兜底', () => {
    let caught: unknown
    try {
      assertSuccess({ code: 500 })
    } catch (error) {
      caught = error
    }
    expect(errorMessage(caught, '保存失败，请稍后重试')).toBe('保存失败，请稍后重试')
  })

  it('assertSuccess 保留后端业务消息', () => {
    let caught: unknown
    try {
      assertSuccess({ code: 500, message: '手机号格式错误' })
    } catch (error) {
      caught = error
    }
    expect(errorMessage(caught, '兜底文案')).toBe('手机号格式错误')
  })
})

describe('assertSuccess', () => {
  it('code 为 200 或缺失时原样返回响应', () => {
    expect(assertSuccess({ code: 200 }).code).toBe(200)
    expect(assertSuccess<{ code?: number }>({}).code).toBeUndefined()
  })
})
