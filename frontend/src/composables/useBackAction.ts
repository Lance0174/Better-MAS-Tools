import { onScopeDispose, watch, type WatchSource } from 'vue'

const actions: { close: () => void }[] = []

/** 原生返回只处理最上层；关闭确认尚未完成时保留原来的页面。 */
export function registerBackAction(close: () => void) {
  const action = { close }
  actions.push(action)
  return () => {
    const index = actions.indexOf(action)
    if (index >= 0) actions.splice(index, 1)
  }
}

export function consumeBackAction() {
  const action = actions.at(-1)
  if (!action) return false
  action.close()
  return true
}

export function useBackAction(open: WatchSource<boolean>, close: () => void) {
  let remove = () => {}
  const stop = watch(
    open,
    visible => {
      remove()
      remove = visible ? registerBackAction(close) : () => {}
    },
    { immediate: true, flush: 'sync' }
  )
  onScopeDispose(() => {
    stop()
    remove()
  })
}
