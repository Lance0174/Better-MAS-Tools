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

// 塔吉多只登记异环。名片接口能给出真实数值，所以空快照只是降级路径
// （角色列表没读到、或接口没返回可识别字段）：resources/tasks 为空数组时，
// 卡片只展示平台、游戏、角色与状态文案，不能崩。
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

describe('塔吉多 · 异环便笺的展示层', () => {
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

  it('名片成功快照把资源与活跃度都渲染成指标', () => {
    const presentation = presentActivity({
      ...nteLimitedSnapshot,
      status: 'success',
      completed: 60,
      target: 100,
      tasks: [
        { name: '活跃度', completed: 60, target: 100, status: '未完成', period: 'daily' },
        { name: '周本次数', completed: 1, target: 3, status: '未完成', period: 'weekly' },
      ],
      resources: [
        { name: '本性像素', current: 100, target: 240, status: '可用' },
        { name: '都市活力', current: 20, target: 100, status: '可用' },
      ],
      reason: '名片快照（等级45）；官方名片接口不含恢复倒计时与每日任务明细',
    })
    const metrics = presentation.groups.flatMap(group => group.metrics)
    expect(metrics.map(metric => metric.name)).toEqual([
      '活跃度',
      '周本次数',
      '本性像素',
      '都市活力',
    ])
    // 异环没有"大图资源"，走普通网格而不是鸣潮那种单列总览。
    expect(presentation.overview).toBe(false)
    expect(presentation.featured).toEqual([])
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
