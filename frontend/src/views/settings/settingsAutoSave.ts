import type { SettingsData } from '@/api'

type SaveReason = 'change' | 'blur'

interface SettingsAutoSaveOptions {
  getSnapshot: () => SettingsData
  save: (data: SettingsData) => Promise<void>
  onFailure: (error: unknown) => void
}

const TEXT_DELAY = 500
const RETRY_DELAY = 500
const MAX_ATTEMPTS = 5

/** Serializes settings writes so an earlier response cannot replace a newer draft. */
export function createSettingsAutoSave(options: SettingsAutoSaveOptions) {
  let textTimer: ReturnType<typeof setTimeout> | undefined
  let retryTimer: ReturnType<typeof setTimeout> | undefined
  let saving = false
  let pending = false
  let attempts = 0
  let failureShown = false

  const snapshot = () => JSON.parse(JSON.stringify(options.getSnapshot())) as SettingsData
  const clearTextTimer = () => {
    if (textTimer) clearTimeout(textTimer)
    textTimer = undefined
  }
  const persist = async (reason: SaveReason) => {
    if (saving) {
      pending = true
      return
    }
    saving = true
    try {
      await options.save(snapshot())
      attempts = 0
      failureShown = false
    } catch (error) {
      attempts += 1
      if (attempts >= MAX_ATTEMPTS) {
        if (!failureShown) options.onFailure(error)
        failureShown = true
      }
      if (attempts < MAX_ATTEMPTS) retryTimer = setTimeout(() => void persist('change'), RETRY_DELAY)
    } finally {
      saving = false
      if (pending) {
        pending = false
        attempts = 0
        if (retryTimer) clearTimeout(retryTimer)
        retryTimer = undefined
        void persist(reason)
      }
    }
  }
  return {
    changed() {
      clearTextTimer()
      if (retryTimer) clearTimeout(retryTimer)
      retryTimer = undefined
      attempts = 0
      void persist('change')
    },
    textChanged() {
      clearTextTimer()
      textTimer = setTimeout(() => void persist('change'), TEXT_DELAY)
    },
    textBlurred() {
      clearTextTimer()
      void persist('blur')
    },
    dispose() {
      clearTextTimer()
      if (retryTimer) clearTimeout(retryTimer)
    },
  }
}
