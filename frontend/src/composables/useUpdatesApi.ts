import { UpdatesService } from '@/api'
import { assertSuccess } from './useCommunityApi'

export const useUpdatesApi = () => ({
  check: (platform: 'windows' | 'android', channel: 'stable' | 'beta') =>
    UpdatesService.checkUpdates(platform, channel).then(assertSuccess),
})
