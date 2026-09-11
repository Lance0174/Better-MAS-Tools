import { GachaService, type GachaFetchIn, type GachaRecord } from '@/api'
import { assertSuccess } from './useCommunityApi'

export const useGachaApi = () => ({
  list: (game: GachaRecord['game'], uid: string, pool: string, page: number) => GachaService.listGachaRecords(game, uid, pool, page, 50).then(assertSuccess),
  fetch: (body: GachaFetchIn) => GachaService.fetchGachaRecords(body).then(assertSuccess),
  import: (game: GachaRecord['game'], payload: string) => GachaService.importGachaRecords({ game, payload }).then(assertSuccess),
  export: (game: GachaRecord['game'], uid: string, format: 'bmasc' | 'uigf') => GachaService.exportGachaRecords(game, uid, format).then(assertSuccess),
})
