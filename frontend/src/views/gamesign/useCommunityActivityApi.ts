import {
  CommunityService,
  type CommunityActivitySnapshotOut,
  type CommunityActivityResourceOut,
  type CommunityActivityTaskOut,
} from '@/api'
import { assertSuccess } from '@/composables/useCommunityApi'

export type ActivityStatus = CommunityActivitySnapshotOut['status']
export type ActivityTask = CommunityActivityTaskOut & { period: string }
export type ActivityResource = CommunityActivityResourceOut
export type ActivitySnapshot = Omit<
  CommunityActivitySnapshotOut,
  'completed' | 'target' | 'tasks' | 'resources'
> & {
  completed: number | null
  target: number | null
  tasks: ActivityTask[]
  resources: ActivityResource[]
  reason: string
  updatedAt: string
  roleName: string
  roleUid: string
  server: string
  source: string
}

export function useCommunityActivityApi() {
  const queryActivity = async (accountIds: string[] | null = null): Promise<ActivitySnapshot[]> => {
    const payload = assertSuccess(await CommunityService.queryActivity({ accountIds }))
    return (payload.data ?? []).map(snapshot => ({
      ...snapshot,
      completed: snapshot.completed ?? null,
      target: snapshot.target ?? null,
      tasks: (snapshot.tasks ?? []).map(task => ({ ...task, period: task.period ?? 'daily' })),
      resources: snapshot.resources ?? [],
      reason: snapshot.reason ?? '',
      updatedAt: snapshot.updatedAt ?? '',
      roleName: snapshot.roleName ?? '',
      roleUid: snapshot.roleUid ?? '',
      server: snapshot.server ?? '',
      source: snapshot.source ?? '',
    }))
  }
  return { queryActivity }
}
