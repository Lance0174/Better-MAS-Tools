import {
  GachaService,
  type GachaCookieFetchIn,
  type GachaFetchIn,
  type GachaHeyboxIn,
  type GachaRecord,
} from '@/api'
import { assertSuccess } from './useCommunityApi'

export const useGachaApi = () => ({
  list: (game: GachaRecord['game'], uid: string, pool: string, page: number) => GachaService.listGachaRecords(game, uid, pool, page, 50).then(assertSuccess),
  fetch: (body: GachaFetchIn) => GachaService.fetchGachaRecords(body).then(assertSuccess),
  // 米游社 Cookie 换 authkey：cookie 留空时后端用所选账号组已绑定的凭据。
  fetchCookie: (body: GachaCookieFetchIn) =>
    GachaService.fetchGachaRecordsByCookie(body).then(assertSuccess),
  import: (game: GachaRecord['game'], payload: string) => GachaService.importGachaRecords({ game, payload }).then(assertSuccess),
  heybox: (body: GachaHeyboxIn) => GachaService.importGachaHeybox(body).then(assertSuccess),
  revokeHeybox: (uid: string) => GachaService.revokeGachaHeybox(uid, 'endfield').then(assertSuccess),
  export: (game: GachaRecord['game'], uid: string, format: 'bmasc' | 'uigf') => GachaService.exportGachaRecords(game, uid, format).then(assertSuccess),
})
