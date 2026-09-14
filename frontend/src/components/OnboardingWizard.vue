<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; done: [] }>()
const { t } = useI18n()
const step = ref(0)
const STEPS = 4

watch(
  () => props.open,
  open => {
    if (open) step.value = 0
  }
)

const next = () => {
  if (step.value < STEPS - 1) step.value += 1
  else finish()
}
const prev = () => {
  if (step.value > 0) step.value -= 1
}
const finish = () => {
  emit('done')
  emit('close')
}
</script>

<template>
  <a-modal
    :open="open"
    :title="t('onboarding.title')"
    :width="520"
    :footer="null"
    :mask-closable="false"
    :keyboard="false"
    centered
    @cancel="emit('close')"
  >
    <a-steps :current="step" size="small" class="onboarding-steps">
      <a-step :title="t('onboarding.step1Title')" />
      <a-step :title="t('onboarding.step2Title')" />
      <a-step :title="t('onboarding.step3Title')" />
      <a-step :title="t('onboarding.step4Title')" />
    </a-steps>

    <div class="onboarding-body">
      <template v-if="step === 0">
        <h3>{{ t('onboarding.welcomeTitle') }}</h3>
        <p>{{ t('onboarding.welcomeBody') }}</p>
        <ul class="onboarding-list">
          <li>{{ t('onboarding.welcomeItem1') }}</li>
          <li>{{ t('onboarding.welcomeItem2') }}</li>
          <li>{{ t('onboarding.welcomeItem3') }}</li>
        </ul>
      </template>

      <template v-else-if="step === 1">
        <h3>{{ t('onboarding.step1Title') }}</h3>
        <p>{{ t('onboarding.step1Body') }}</p>
        <ol class="onboarding-list">
          <li>{{ t('onboarding.step1List1') }}</li>
          <li>{{ t('onboarding.step1List2') }}</li>
          <li>{{ t('onboarding.step1List3') }}</li>
        </ol>
      </template>

      <template v-else-if="step === 2">
        <h3>{{ t('onboarding.step2Title') }}</h3>
        <p>{{ t('onboarding.step2Body') }}</p>
        <ul class="onboarding-list">
          <li>{{ t('onboarding.step2Item1') }}</li>
          <li>{{ t('onboarding.step2Item2') }}</li>
          <li>{{ t('onboarding.step2Item3') }}</li>
        </ul>
      </template>

      <template v-else>
        <h3>{{ t('onboarding.step4Title') }}</h3>
        <p>{{ t('onboarding.step3Body') }}</p>
        <ul class="onboarding-list">
          <li>{{ t('onboarding.step3Item1') }}</li>
          <li>{{ t('onboarding.step3Item2') }}</li>
          <li>{{ t('onboarding.step3Item3') }}</li>
        </ul>
        <a-alert type="info" show-icon :message="t('onboarding.step4Hint')" />
      </template>
    </div>

    <div class="onboarding-actions">
      <a-space>
        <a-button v-if="step > 0" @click="prev">{{ t('onboarding.prev') }}</a-button>
        <a-button v-if="step < STEPS - 1" type="primary" @click="next">{{
          t('onboarding.next')
        }}</a-button>
        <a-button v-else type="primary" @click="finish">{{ t('onboarding.finish') }}</a-button>
        <a-button @click="emit('close')">{{ t('onboarding.skip') }}</a-button>
      </a-space>
    </div>
  </a-modal>
</template>

<style scoped>
.onboarding-steps {
  margin-bottom: 20px;
}
.onboarding-body {
  min-height: 200px;
}
.onboarding-body h3 {
  margin: 0 0 8px;
  font-size: 16px;
}
.onboarding-list {
  margin: 8px 0 0;
  padding-left: 20px;
  line-height: 1.9;
}
.onboarding-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--ant-color-border-secondary);
}
</style>
