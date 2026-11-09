/**
 * 轻量模式开关的「关 → 开」确认门。
 * 关闭不弹确认；开启需先确认，取消时保持关闭且不触发保存/桌面壳同步。
 * 抽成纯函数便于单测，组件只负责把 Modal.confirm 包成 Promise。
 */
export interface LightModeChangeOptions {
  /** 写回设置草稿值。 */
  setEnabled: (enabled: boolean) => void
  /** 询问用户是否开启；resolve false 表示取消。 */
  confirm: () => Promise<boolean>
  /** 值确定变化后触发原有的保存与桌面壳同步。 */
  onChange: () => void
}

/** 处理一次轻量模式开关切换；取消时不会置为开启，也不会调用 onChange。 */
export async function applyLightModeChange(
  enabled: boolean,
  options: LightModeChangeOptions
): Promise<void> {
  if (!enabled) {
    options.setEnabled(false)
    options.onChange()
    return
  }
  // v-model 已先把草稿置为 true；确认前先回落，取消即保持关闭且不保存。
  options.setEnabled(false)
  if (!(await options.confirm())) return
  options.setEnabled(true)
  options.onChange()
}
