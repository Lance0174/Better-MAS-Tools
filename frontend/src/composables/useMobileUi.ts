import { computed, onScopeDispose, ref } from 'vue'
import { isAndroidLocal } from '@/services/android'

/** 安卓始终采用手机交互；窄窗口也使用相同的触屏布局。 */
export function useMobileUi() {
  const media = window.matchMedia('(max-width: 700px)')
  const narrow = ref(media.matches)
  const changed = () => {
    narrow.value = media.matches
  }
  media.addEventListener('change', changed)
  onScopeDispose(() => media.removeEventListener('change', changed))
  return computed(() => import.meta.env.BMAT_ANDROID || isAndroidLocal || narrow.value)
}
