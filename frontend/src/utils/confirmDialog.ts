import { i18n } from '@/i18n'
import { Modal } from 'ant-design-vue'
import type { ModalFuncProps } from 'ant-design-vue/es/modal'
import { registerBackAction } from '@/composables/useBackAction'

/** 确认框的系统返回等同取消；执行中的确认不可从后面关闭父页面。 */
export function confirmDialog(options: ModalFuncProps) {
  let pending = false
  let remove = () => {}
  const dialog = Modal.confirm({
    okText: i18n.global.t('standalone.ui.confirm'),
    cancelText: i18n.global.t('standalone.cancel'),
    ...options,
    wrapClassName: 'app-confirm',
    keyboard: false,
    onOk: async (...args: unknown[]) => {
      pending = true
      try {
        return await options.onOk?.(...args)
      } finally {
        pending = false
      }
    },
    afterClose: () => {
      remove()
      options.afterClose?.()
    },
  })
  remove = registerBackAction(() => {
    if (pending) return
    options.onCancel?.()
    dialog.destroy()
  })
  return dialog
}
