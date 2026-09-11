<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { MiyousheVerificationOut, GeetestV3Data } from '@/api'
import { useCommunityApi, errorMessage } from '@/composables/useCommunityApi'
import CaptchaModal from '@/components/CaptchaModal.vue'

defineProps<{ busy: boolean }>()
const emit = defineEmits<{ completed: [] }>()
const { t } = useI18n()
const api = useCommunityApi()
const pending = ref<MiyousheVerificationOut[]>([])
const selected = ref<MiyousheVerificationOut | null>(null)
const submitting = ref(false)
const error = ref('')
let alive = true
let timer: ReturnType<typeof setTimeout> | undefined
const load = async () => {
  try {
    const response = await api.miyousheVerifications()
    if (alive) { pending.value = response.data ?? []; error.value = '' }
  } catch (cause) {
    if (alive) error.value = errorMessage(cause, t('standalone.loadFailed'))
  }
  if (alive) timer = setTimeout(load, 10000)
}
const solve = async (proof: Record<string, string>) => {
  const current = selected.value
  selected.value = null
  if (!current) return
  submitting.value = true
  try {
    const response = await api.submitMiyousheVerification(current.sessionId, proof as GeetestV3Data)
    message.info(response.message)
    clearTimeout(timer)
    await load()
    emit('completed')
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.captchaFailed')))
  } finally { submitting.value = false }
}
onMounted(load)
onBeforeUnmount(() => { alive = false; clearTimeout(timer) })
</script>

<template>
  <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert" />
  <a-alert v-if="pending.length" type="info" show-icon :message="t('standalone.miyousheVerifyHint')" class="page-alert">
    <template #description>
      <a-space wrap>
        <a-button v-for="item in pending" :key="item.sessionId" :disabled="busy" :loading="submitting" @click="selected = item">{{ item.label }}</a-button>
      </a-space>
    </template>
  </a-alert>
  <CaptchaModal :open="!!selected" :version="3" :gt="selected?.gt" :challenge="selected?.challenge" @close="selected = null" @solved="solve" />
</template>
