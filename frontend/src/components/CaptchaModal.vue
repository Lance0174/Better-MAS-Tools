<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  open: boolean
  version: 3 | 4
  captchaId?: string
  gt?: string
  challenge?: string
}>()
const emit = defineEmits<{ close: []; solved: [solution: Record<string, string>] }>()
const { t } = useI18n()
const frame = ref<HTMLIFrameElement | null>(null)
const nonce = ref('')
const failed = ref(false)
let loadTimer: ReturnType<typeof setTimeout> | undefined
const reload = () => {
  clearTimeout(loadTimer)
  nonce.value = crypto.randomUUID()
  failed.value = false
  // iframe 自身脚本若被拦截，也必须结束等待并提供重试入口。
  loadTimer = setTimeout(() => {
    failed.value = true
  }, 25000)
}
const source = computed(
  () =>
    `/captcha.html#${encodeURIComponent(
      JSON.stringify({
        version: props.version,
        captchaId: props.captchaId,
        gt: props.gt,
        challenge: props.challenge,
        nonce: nonce.value,
        parentOrigin: window.location.origin,
      })
    )}`
)
watch(
  () => props.open,
  open => {
    if (open) reload()
    else clearTimeout(loadTimer)
  },
  { immediate: true }
)
function receive(event: MessageEvent) {
  if (!props.open || event.source !== frame.value?.contentWindow) return
  const data: unknown = event.data
  if (
    !data ||
    typeof data !== 'object' ||
    !('nonce' in data) ||
    data.nonce !== nonce.value ||
    !('kind' in data) ||
    data.kind !== 'community-captcha'
  )
    return
  if ('ready' in data || 'error' in data || 'solution' in data) clearTimeout(loadTimer)
  if ('ready' in data) return
  if ('error' in data) {
    failed.value = true
    return
  }
  if (!('solution' in data) || !data.solution || typeof data.solution !== 'object') return
  const values = Object.entries(data.solution)
  if (
    values.length > 12 ||
    values.some(([, value]) => typeof value !== 'string' || value.length > 8192)
  )
    return
  emit('solved', Object.fromEntries(values) as Record<string, string>)
}
window.addEventListener('message', receive)
onBeforeUnmount(() => {
  clearTimeout(loadTimer)
  window.removeEventListener('message', receive)
})
</script>

<template>
  <a-modal
    :open="open"
    :title="t('standalone.humanVerification')"
    :footer="null"
    :width="440"
    centered
    destroy-on-close
    @cancel="emit('close')"
  >
    <a-space v-if="failed" direction="vertical" class="captcha-error">
      <a-alert type="error" show-icon :message="t('standalone.captchaFailed')" />
      <a-button @click="reload">{{ t('standalone.retry') }}</a-button>
    </a-space>
    <iframe
      v-if="open && !failed"
      :key="nonce"
      ref="frame"
      :src="source"
      sandbox="allow-scripts allow-same-origin"
      class="captcha-frame"
      :title="t('standalone.humanVerification')"
    />
  </a-modal>
</template>

<style scoped>
.captcha-frame {
  display: block;
  width: 100%;
  height: 440px;
  border: 0;
}
.captcha-error {
  width: 100%;
  padding: 24px 0;
}
</style>
