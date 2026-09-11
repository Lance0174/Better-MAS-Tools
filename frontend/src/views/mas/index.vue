<script setup lang="ts">
import { ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { MasSnapshotOut, MasQueueOut, MasTaskOut } from '@/api'
import { useMasApi } from '@/composables/useMasApi'
import { errorMessage } from '@/composables/useCommunityApi'
import { useSettingsStore } from '@/stores/settings'

const { t } = useI18n()
const api = useMasApi()
const settings = useSettingsStore()
const data = ref<MasSnapshotOut | null>(null)
const busy = ref(false)
const error = ref('')
const connect = async () => {
  busy.value = true
  try { data.value = await api.snapshot(); error.value = '' }
  catch (cause) { error.value = errorMessage(cause, t('standalone.masFailed')) }
  finally { busy.value = false }
}
const start = async (queue: MasQueueOut) => {
  busy.value = true
  try {
    await api.start({ taskId: queue.id, mode: 'AutoProxy' })
    message.success(t('standalone.masStarted'))
  } catch (cause) { message.error(errorMessage(cause, t('standalone.masFailed'))) }
  finally { await connect() }
}
const stop = (task: MasTaskOut) => Modal.confirm({
  title: t('standalone.masStopTitle'), content: task.id,
  onOk: async () => {
    busy.value = true
    try { message.info((await api.stop(task.id)).message) }
    catch (cause) { message.error(errorMessage(cause, t('standalone.masFailed'))) }
    finally { await connect() }
  },
})
</script>

<template>
  <section>
    <header class="page-toolbar"><h1 class="page-title">{{ t('standalone.mas') }}</h1><a-button type="primary" :disabled="!settings.localConnections" :loading="busy" @click="connect">{{ t('standalone.masConnect') }}</a-button></header>
    <a-alert type="info" show-icon :message="t(settings.localConnections ? 'standalone.masHint' : 'standalone.workerLocalUnavailable')" class="page-alert" />
    <p>{{ t('standalone.masAddress') }}：{{ settings.data?.MasBaseUrl }}</p>
    <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert" />
    <template v-if="data">
      <a-list :header="t('standalone.masQueues')" :data-source="data.queues" bordered class="mas-list">
        <template #renderItem="{ item }"><a-list-item><span>{{ item.name }}</span><template #actions><a-button :disabled="busy" @click="start(item)">{{ t('standalone.masStart') }}</a-button></template></a-list-item></template>
      </a-list>
      <a-list :header="t('standalone.masTasks')" :data-source="data.tasks" bordered>
        <template #renderItem="{ item }"><a-list-item><span>{{ item.id }} · {{ item.mode }}</span><template #actions><a-button danger :disabled="busy || item.stopping" @click="stop(item)">{{ t(item.stopping ? 'standalone.masStopping' : 'standalone.masStop') }}</a-button></template></a-list-item></template>
      </a-list>
    </template>
    <a-empty v-else :description="t('standalone.masNotConnected')" class="page-state" />
  </section>
</template>

<style scoped>
.mas-list { margin-bottom: 24px; }
</style>
