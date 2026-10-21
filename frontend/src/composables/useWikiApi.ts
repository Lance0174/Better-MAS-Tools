import { WikiService } from '@/api'
import { assertSuccess } from './useCommunityApi'

type WikiEntryKind = 'character' | 'weapon' | 'equipSuit' | 'dungeon' | 'enemy'

export function useWikiApi() {
  return {
    status: () => WikiService.getWikiStatus().then(assertSuccess),
    sync: (force = false) =>
      WikiService.syncWikiData({ force }).then(assertSuccess),
    search: (query: string, limit = 20) =>
      WikiService.searchWikiEntries(query, limit).then(assertSuccess),
    entry: (kind: WikiEntryKind, id: string) =>
      WikiService.getWikiEntry(kind, id).then(assertSuccess),
  }
}
