/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type UpdateCheckOut = {
  /**
   * 状态码
   */
  code?: number
  /**
   * 操作状态
   */
  status?: string
  /**
   * 操作消息
   */
  message?: string
  currentVersion: string
  latestVersion: string
  available: boolean
  channel: 'stable' | 'beta'
  prerelease?: boolean
  releaseUrl?: string
  downloadUrl?: string
  sha256?: string
  assetName?: string
  size?: number
  notes?: string
}
