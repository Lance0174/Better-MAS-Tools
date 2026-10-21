import { describe, expect, it } from 'vitest'
import zhCN from '@/i18n/locales/zh-CN'
import type { ActivitySnapshot } from './useCommunityActivityApi'
import { gameLabelKey, platformLabelKey, presentActivity } from './communityActivityPresentation'

// 按点号路径从词表取值，等价于页面里 t(key) 的结果；不读 .vue 源码做断言。
const resolveKey = (key: string): unknown =>
  key.split('.').reduce<unknown>((node, segment) => {
    if (node && typeof node === 'object' && segment in node)
      return (node as Record<string, unknown>)[segment]
    return undefined
  }, zhCN)

// 塔吉多只登记异环，且后端把它的便笺能力固定成 limited：每个角色一张快照，
// resources/tasks 为空数组，卡片只应展示平台、游戏、角色与状态文案。
const nteLimitedSnapshot: ActivitySnapshot = {
  account: '主号',
  accountUid: 'account-1',
  platform: '塔吉多',
  game: '异环',
  status: 'limited',
  completed: null,
  target: null,
  tasks: [],
  resources: [],
  reason: '塔吉多社区未公开资源便笺接口，仅展示角色信息',
  updatedAt: '2026-10-21T18:00:00+08:00',
  roleName: '测试角色',
  roleUid: '10000001',
  server: '官服',
  source: 'local',
}

describe('塔吉多 · 异环 limited 快照的展示层', () => {
  it('平台名与游戏名都能映射到词表文案', () => {
    const platformKey = platformLabelKey(nteLimitedSnapshot.platform)
    const gameKey = gameLabelKey(nteLimitedSnapshot.game)
    expect(platformKey).toBe('gamesign.activity.platform.taygedo')
    expect(gameKey).toBe('gamesign.activity.game.nte')
    expect(resolveKey(platformKey ?? '')).toBe('塔吉多')
    expect(resolveKey(gameKey ?? '')).toBe('异环')
  })

  it('状态徽标文案取自既有 status.limited 键，而不是裸 key', () => {
    const label = resolveKey(`gamesign.activity.status.${nteLimitedSnapshot.status}`)
    expect(typeof label).toBe('string')
    expect(String(label).length).toBeGreaterThan(0)
    expect(label).not.toBe(`gamesign.activity.status.${nteLimitedSnapshot.status}`)
  })

  it('角色信息完整，可直接渲染卡片标题区与页脚', () => {
    expect(nteLimitedSnapshot.roleName).toBe('测试角色')
    expect(nteLimitedSnapshot.roleUid).toBe('10000001')
    expect(nteLimitedSnapshot.server).toBe('官服')
    expect(nteLimitedSnapshot.reason).toContain('仅展示角色信息')
  })

  it('没有资源与任务时不报错，也不产出指标区', () => {
    const presentation = presentActivity(nteLimitedSnapshot)
    expect(presentation.featured).toEqual([])
    expect(presentation.groups).toEqual([])
    expect(presentation.overview).toBe(false)
  })

  it('未知平台或游戏回退到后端原文（映射返回 null）', () => {
    expect(platformLabelKey('某新平台')).toBeNull()
    expect(gameLabelKey('某新游戏')).toBeNull()
  })
})
