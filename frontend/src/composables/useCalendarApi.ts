import { WikiService } from '@/api'
import { assertSuccess } from './useCommunityApi'

// 日历只做「一次取全部游戏」：单游戏接口没有调用方，游戏枚举已由生成的
// WikiCalendarGameOut['game'] 提供，这里不再手写一份容易失同步的类型。
export function useCalendarApi() {
  return {
    all: () => WikiService.getWikiCalendarAll().then(assertSuccess),
  }
}
