import { effectScope, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { consumeBackAction, registerBackAction, useBackAction } from './useBackAction'

describe('安卓逐层返回', () => {
  it('先关闭选择弹层，再关闭编辑页，最后交还页面导航', () => {
    const scope = effectScope()
    const editor = ref(true),
      picker = ref(false)
    scope.run(() => {
      useBackAction(editor, () => {
        editor.value = false
      })
      useBackAction(picker, () => {
        picker.value = false
      })
    })
    picker.value = true
    expect(consumeBackAction()).toBe(true)
    expect(picker.value).toBe(false)
    expect(editor.value).toBe(true)
    expect(consumeBackAction()).toBe(true)
    expect(editor.value).toBe(false)
    expect(consumeBackAction()).toBe(false)
    scope.stop()
  })

  it('未保存确认取消后仍留在编辑页，卸载后不残留返回操作', () => {
    const scope = effectScope()
    const requested = vi.fn()
    scope.run(() => useBackAction(() => true, requested))
    const cancel = vi.fn()
    const remove = registerBackAction(cancel)
    consumeBackAction()
    expect(cancel).toHaveBeenCalledOnce()
    expect(requested).not.toHaveBeenCalled()
    remove()
    consumeBackAction()
    expect(requested).toHaveBeenCalledOnce()
    scope.stop()
    expect(consumeBackAction()).toBe(false)
  })
})
