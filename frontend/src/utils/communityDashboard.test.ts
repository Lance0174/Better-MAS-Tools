import { describe, expect, it } from 'vitest'
import type { ActivitySnapshot } from '@/views/gamesign/useCommunityActivityApi'
import { groupSnapshots, homeSignRows, snapshotKey } from '@/utils/communityDashboard'

const note = (accountUid: string, game = '原神', roleUid = '100000001') =>
  ({
    accountUid,
    game,
    roleUid,
    roleName: '角色',
    platform: '米游社',
    account: '测试账号',
  }) as ActivitySnapshot

describe('首页数据组织', () => {
  it('保留多账号和多区服，并按游戏排序而不改写原始数据', () => {
    const source = [note('a'), note('b'), note('a', '终末地'), note('a', '原神', '500000001')]
    const original = [...source]
    const groups = groupSnapshots(source, ['已删除', '终末地'])
    expect(groups.map(group => group.game)).toEqual(['终末地', '原神'])
    expect(groups[1].snapshots).toHaveLength(3)
    expect(source).toEqual(original)
    expect(new Set(source.map(snapshotKey)).size).toBe(4)
  })
  it('角色改名后仍可选中原 UID，分隔符也不会产生键冲突', () => {
    const before = note('a')
    expect(snapshotKey({ ...before, roleName: '新昵称' })).toBe(snapshotKey(before))
    expect(snapshotKey(note('a:b', 'c'))).not.toBe(snapshotKey(note('a', 'b:c')))
  })
  it('不把历史成功展示成今日成功，也不泄漏其他游戏的奖励', () => {
    const rows = homeSignRows(
      {
        米游社: [
          {
            account_uid: 'a',
            games: [
              {
                game: '原神',
                account: '白芷',
                status: '成功',
                reward: '今日奖励',
                signedAt: '2026-11-09T08:00:00+08:00',
              },
              {
                game: '星穹铁道',
                status: '成功',
                reward: '其他游戏奖励',
                signedAt: '2026-11-09T08:00:00+08:00',
              },
            ],
          },
          {
            account_uid: 'b',
            games: [
              {
                game: '原神',
                account: '云岚',
                status: '成功',
                reward: '历史奖励',
                signedAt: '2026-11-08T08:00:00+08:00',
              },
            ],
          },
          {
            account_uid: 'c',
            games: [
              {
                game: '原神',
                account: '夜雨',
                status: '失败',
                reason: '凭据失效',
                signedAt: '2026-11-09T08:00:00+08:00',
              },
            ],
          },
        ],
      },
      '原神',
      '2026-11-09'
    )
    expect(rows).toHaveLength(3)
    expect(rows.map(row => row.state)).toEqual(['success', 'pending', 'error'])
    expect(rows.map(row => row.reward)).toEqual(['今日奖励', '', undefined])
    expect(rows[2].reason).toBe('凭据失效')
    expect(new Set(rows.map(row => row.key)).size).toBe(3)
  })
})
