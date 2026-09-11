import { MasService, type MasStartIn } from '@/api'
import { assertSuccess } from './useCommunityApi'

export const useMasApi = () => ({
  snapshot: () => MasService.getMasSnapshot().then(assertSuccess),
  start: (body: MasStartIn) => MasService.startMasTask(body).then(assertSuccess),
  stop: (taskId: string) => MasService.stopMasTask({ taskId }).then(assertSuccess),
})
