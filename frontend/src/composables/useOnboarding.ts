import { ref } from 'vue'

/** 引导完成或跳过后的本地标记：两种结果都表示用户已处理过引导。 */
const ONBOARDING_KEY = 'bmat-onboarding-done'

/**
 * 读取本地标记；存储不可用（隐私模式、被禁用等）时按“未处理”处理，
 * 宁可多显示一次，也不影响正常使用。
 */
export const isOnboardingDone = (): boolean => {
  try {
    return localStorage.getItem(ONBOARDING_KEY) === '1'
  } catch {
    return false
  }
}

/**
 * 记录“已完成 / 已跳过”。两者语义不同，但对“下次启动是否自动弹出”是同一件事，
 * 因此共用同一个键；写入失败时静默降级。
 */
export const markOnboardingDone = (): void => {
  try {
    localStorage.setItem(ONBOARDING_KEY, '1')
  } catch {
    /* 浏览器标记不可用时仍由后端持久化状态负责判断。 */
  }
}

/**
 * 首启引导的开关与入口：
 * - complete / skip 结束引导并写标记，之后不再自动弹出；
 * - show 供设置页“重新查看引导”主动打开，不写也不清标记；
 * - maybeShow 是连接成功后的首启判定，仅在未完成/未跳过时自动打开。
 */
interface OnboardingOptions {
  isDone?: () => boolean
  saveDone?: () => Promise<void>
  onFailure?: (cause: unknown) => void
}

export const useOnboarding = (options: OnboardingOptions = {}) => {
  const open = ref(false)
  let dismissed = false
  const show = () => {
    open.value = true
  }
  const hide = () => {
    open.value = false
  }
  // 完成与跳过对“是否再自动弹出”是同一件事：先写标记再关闭。
  const finish = async () => {
    dismissed = true
    markOnboardingDone()
    hide()
    try {
      await options.saveDone?.()
    } catch (cause) {
      options.onFailure?.(cause)
    }
  }
  const complete = finish
  const skip = finish
  const maybeShow = () => {
    if (dismissed || options.isDone?.()) return
    if (isOnboardingDone()) {
      // 将旧版浏览器标记迁移到后端；Electron 随机端口不共享 localStorage。
      void finish()
      return
    }
    show()
  }
  return { open, show, hide, complete, skip, maybeShow }
}
