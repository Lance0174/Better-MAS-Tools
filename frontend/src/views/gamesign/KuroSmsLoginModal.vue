<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { GeetestV4Data } from '@/api'
import { useCommunityApi, errorMessage } from '@/composables/useCommunityApi'
import CaptchaModal from '@/components/CaptchaModal.vue'

const props = defineProps<{ open: boolean; accountId?: string }>()
const emit = defineEmits<{ close: []; saved: [] }>()
const { t } = useI18n()
const api = useCommunityApi()
const phone = ref('')
const code = ref('')
const sessionId = ref('')
const captchaId = ref('')
const verifying = ref(false)
const busy = ref(false)
const automaticPending = ref(false)
const sent = ref(false)
const cooldown = ref(0)
let generation = 0
let timer: ReturnType<typeof setInterval> | undefined

const reset = () => {
  generation++
  if (sessionId.value) void api.cancelKuroSms(sessionId.value).catch(() => undefined)
  sessionId.value = ''
  phone.value = ''
  code.value = ''
  verifying.value = false
  busy.value = false
  automaticPending.value = false
  sent.value = false
  cooldown.value = 0
  clearInterval(timer)
}
watch(() => [props.open, props.accountId], reset)
onBeforeUnmount(reset)

const markSent = () => {
  sent.value = true
  cooldown.value = 60
  clearInterval(timer)
  timer = setInterval(() => {
    cooldown.value = Math.max(0, cooldown.value - 1)
    if (!cooldown.value) clearInterval(timer)
  }, 1000)
  message.success(t('standalone.smsSent'))
}

const start = async (manual = false) => {
  if (!props.accountId || !/^1[3-9]\d{9}$/.test(phone.value)) {
    message.error(t('standalone.validPhone'))
    return
  }
  const current = generation
  busy.value = true
  try {
    if (!sessionId.value) {
      const response = await api.createKuroSms(props.accountId, phone.value)
      if (current !== generation) {
        void api.cancelKuroSms(response.sessionId).catch(() => undefined)
        return
      }
      sessionId.value = response.sessionId
      captchaId.value = response.captchaId
    }
    if (manual) {
      verifying.value = true
      return
    }
    automaticPending.value = true
    const automatic = await api.automaticKuroSms(sessionId.value)
    if (current !== generation) return
    if (automatic.sent) markSent()
    else {
      message.info(automatic.message || t('standalone.humanVerification'))
      verifying.value = true
    }
  } catch (cause) {
    if (current === generation) message.error(errorMessage(cause, t('standalone.loginFailed')))
  } finally {
    if (current === generation) {
      busy.value = false
      automaticPending.value = false
    }
  }
}
const send = async (solution: Record<string, string>) => {
  verifying.value = false
  const current = generation
  busy.value = true
  try {
    await api.sendKuroSms(sessionId.value, solution as GeetestV4Data)
    if (current !== generation) return
    markSent()
  } catch (cause) {
    if (current === generation) message.error(errorMessage(cause, t('standalone.loginFailed')))
  } finally {
    if (current === generation) busy.value = false
  }
}
const login = async () => {
  if (!/^\d{6}$/.test(code.value)) {
    message.error(t('standalone.validSmsCode'))
    return
  }
  const current = generation
  busy.value = true
  try {
    await api.loginKuroSms(sessionId.value, code.value)
    if (current !== generation) return
    sessionId.value = ''
    message.success(t('standalone.loginSuccess'))
    emit('saved')
    emit('close')
  } catch (cause) {
    if (current === generation) message.error(errorMessage(cause, t('standalone.loginFailed')))
  } finally {
    if (current === generation) {
      busy.value = false
      code.value = ''
    }
  }
}
</script>

<template>
  <a-modal
    :open="open"
    :title="t('standalone.kuroSmsLogin')"
    :confirm-loading="busy"
    :ok-button-props="{ disabled: !sent }"
    :ok-text="t('standalone.login')"
    @ok="login"
    @cancel="emit('close')"
  >
    <a-alert type="info" show-icon :message="t('standalone.smsLoginHint')" class="sms-hint" />
    <a-form layout="vertical" :model="{ phone, code }">
      <a-form-item name="phone" :label="t('standalone.phone')" required>
        <a-input
          v-model:value="phone"
          inputmode="tel"
          autocomplete="off"
          :maxlength="11"
          :disabled="!!sessionId || busy"
        />
      </a-form-item>
      <a-form-item name="code" :label="t('standalone.smsCode')" required>
        <a-space wrap>
          <a-input
            v-model:value="code"
            inputmode="numeric"
            autocomplete="one-time-code"
            :maxlength="6"
            :disabled="!sent || busy"
            @press-enter="login"
          />
          <a-button :loading="busy" :disabled="cooldown > 0" @click="start()">{{
            cooldown ? t('standalone.smsCooldown', { seconds: cooldown }) : t('standalone.sendSms')
          }}</a-button>
          <a-button :disabled="busy || cooldown > 0" @click="start(true)">{{
            t('standalone.captchaUseManual')
          }}</a-button>
        </a-space>
      </a-form-item>
    </a-form>
    <a-alert
      v-if="automaticPending"
      type="info"
      show-icon
      :message="t('standalone.captchaAutomaticPending')"
    />
  </a-modal>
  <CaptchaModal
    :open="verifying"
    :version="4"
    :captcha-id="captchaId"
    @close="verifying = false"
    @solved="send"
  />
</template>

<style scoped>
.sms-hint {
  margin-bottom: 20px;
}
</style>
