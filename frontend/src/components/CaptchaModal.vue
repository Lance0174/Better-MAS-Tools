<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { getLogger } from '@/utils/logger'

const props = defineProps<{
  open: boolean
  version: 3 | 4
  captchaId?: string
  gt?: string
  challenge?: string
}>()
const emit = defineEmits<{ close: []; solved: [solution: Record<string, string>] }>()
const { t } = useI18n()
const logger = getLogger('人工验证')
const frame = ref<HTMLIFrameElement | null>(null)
const nonce = ref('')
const failed = ref(false)
const ready = ref(false)
const pageLoaded = ref(false)
const failureReason = ref('standalone.captchaFailed')
let loadTimer: ReturnType<typeof setTimeout> | undefined
const reload = () => {
  clearTimeout(loadTimer)
  nonce.value = crypto.randomUUID()
  failed.value = false
  ready.value = false
  pageLoaded.value = false
  failureReason.value = 'standalone.captchaFailed'
  // iframe 自身脚本若被拦截，也必须结束等待并提供重试入口。
  loadTimer = setTimeout(() => {
    failureReason.value = pageLoaded.value
      ? 'standalone.captchaNetworkFailed'
      : 'standalone.captchaBackendFailed'
    failed.value = true
    logger.warn(t(failureReason.value))
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
  if (
    !props.open ||
    event.origin !== window.location.origin ||
    event.source !== frame.value?.contentWindow
  )
    return
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
  if ('loading' in data) {
    pageLoaded.value = true
    return
  }
  if ('ready' in data || 'error' in data || 'solution' in data || 'closed' in data)
    clearTimeout(loadTimer)
  if ('closed' in data) {
    emit('close')
    return
  }
  if ('ready' in data) {
    ready.value = true
    logger.info('官方验证码已加载')
    return
  }
  if ('error' in data) {
    failureReason.value =
      'reason' in data && data.reason === 'policy'
        ? 'standalone.captchaPolicyFailed'
        : 'standalone.captchaNetworkFailed'
    failed.value = true
    logger.warn(t(failureReason.value))
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
      <a-alert type="error" show-icon :message="t(failureReason)" />
      <a-button @click="reload">{{ t('standalone.retry') }}</a-button>
    </a-space>
    <a-spin v-if="open && !failed" :spinning="!ready">
      <iframe
        :key="nonce"
        ref="frame"
        :src="source"
        sandbox="allow-scripts allow-same-origin"
        class="captcha-frame"
        :title="t('standalone.humanVerification')"
      />
    </a-spin>
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
