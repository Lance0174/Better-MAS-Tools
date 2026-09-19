<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { RelayNodeOut } from '@/api'
import { RelayService } from '@/api'
import { errorMessage } from '@/composables/useCommunityApi'

const { t } = useI18n()
const busy = ref(false)
const error = ref('')
const node = ref<RelayNodeOut | null>(null)
const snapshot = ref<{ queues: Array<{ id: string; name: string }>; tasks: Array<{ id: string; mode: string; stopping: boolean }> } | null>(null)

type CommandStatus = 'done' | 'failed' | 'expired' | 'pending' | 'dispatched'
const isTerminal = (status: string): status is 'done' | 'failed' | 'expired' =>
  ['done', 'failed', 'expired'].includes(status)

const waitCommand = async (commandId: string, timeoutSec: number) => {
  const deadline = Date.now() + timeoutSec * 1000
  while (Date.now() < deadline) {
    const status = await RelayService.relayCommandStatus(commandId)
    if (isTerminal(status.commandStatus ?? '')) return status
    await new Promise((resolve) => setTimeout(resolve, 800))
  }
  throw new Error(t('standalone.relay.timeout'))
}

const runCommand = async (
  type: 'mas.snapshot' | 'mas.start' | 'mas.stop' | 'sign.run',
  payload: Record<string, unknown>,
  timeoutSec = 45,
) => {
  const accepted = await RelayService.relayCommand({ type, payload })
  return await waitCommand(accepted.id, timeoutSec)
}

const loadNodes = async () => {
  const { data } = await RelayService.relayNodes()
  node.value = (data ?? [])[0] ?? null
}

const refreshMas = async () => {
  busy.value = true
  error.value = ''
  try {
    const status = await runCommand('mas.snapshot', {})
    if (status.commandStatus === 'done' && status.result) {
      snapshot.value = status.result.data
    } else {
      message.error(t('standalone.relay.loadFailed', { error: status.result?.error || status.commandStatus }))
    }
  } catch (cause) {
    error.value = errorMessage(cause, t('standalone.relay.loadFailed', { error: '' }))
  } finally {
    busy.value = false
  }
  await loadNodes()
}

const start = async (queue: { id: string }) => {
  busy.value = true
  try {
    const status = await runCommand('mas.start', { taskId: queue.id, mode: 'AutoProxy' })
    if (status.commandStatus === 'done') message.success(t('standalone.masStarted'))
    else message.error(t('standalone.relay.loadFailed', { error: status.result?.error || '' }))
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.relay.loadFailed', { error: '' })))
  } finally {
    busy.value = false
  }
  await refreshMas()
}

const stop = (task: { id: string; stopping: boolean }) =>
  Modal.confirm({
    title: t('standalone.masStopTitle'),
    content: task.id,
    onOk: async () => {
      busy.value = true
      try {
        const status = await runCommand('mas.stop', { taskId: task.id })
        if (status.commandStatus === 'done') message.success(t('standalone.relay.stopAccepted'))
        else message.error(t('standalone.relay.loadFailed', { error: status.result?.error || '' }))
      } catch (cause) {
        message.error(errorMessage(cause, t('standalone.relay.loadFailed', { error: '' })))
      } finally {
        busy.value = false
      }
      await refreshMas()
    },
  })

const remoteSign = () =>
  Modal.confirm({
    title: t('standalone.relay.signConfirmTitle'),
    content: t('standalone.relay.signConfirmContent'),
    onOk: async () => {
      busy.value = true
      try {
        await runCommand('sign.run', {}, 300)
        message.success(t('standalone.relay.signAccepted'))
      } catch (cause) {
        message.error(errorMessage(cause, t('standalone.relay.loadFailed', { error: '' })))
      } finally {
        busy.value = false
      }
    },
  })

const nodeStatusText = computed(() =>
  node.value
    ? t(node.value.online ? 'standalone.relay.nodeOnline' : 'standalone.relay.nodeOffline') +
      ' · ' +
      t('standalone.relay.nodeLastSeen', { time: node.value.lastSeenAt })
    : t('standalone.relay.nodeNone'),
)

let nodesTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  void loadNodes()
  nodesTimer = setInterval(() => void loadNodes(), 10000)
})
onBeforeUnmount(() => {
  if (nodesTimer !== null) clearInterval(nodesTimer)
})
</script>

<template>
  <section>
    <header class="page-toolbar">
      <h1 class="page-title">{{ t('standalone.remote') }}</h1>
      <a-space>
        <a-button :loading="busy" @click="loadNodes">{{ t('standalone.refresh') }}</a-button>
        <a-button type="primary" :loading="busy" @click="refreshMas">{{ t('standalone.relay.refresh') }}</a-button>
        <a-button danger :loading="busy" @click="remoteSign">{{ t('standalone.relay.signNow') }}</a-button>
      </a-space>
    </header>
    <a-alert type="info" show-icon :message="t('standalone.relay.hint')" class="page-alert" />
    <p>
      {{ t('standalone.relay.nodeTitle') }}：<a-tag :color="node?.online ? 'green' : 'default'">{{ nodeStatusText }}</a-tag>
    </p>
    <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert" />
    <template v-if="snapshot">
      <a-list :header="t('standalone.masQueues')" :data-source="snapshot.queues" bordered class="relay-list">
        <template #renderItem="{ item }"><a-list-item><span>{{ item.name }}</span><template #actions><a-button :disabled="busy" @click="start(item)">{{ t('standalone.masStart') }}</a-button></template></a-list-item></template>
      </a-list>
      <a-list :header="t('standalone.masTasks')" :data-source="snapshot.tasks" bordered>
        <template #renderItem="{ item }"><a-list-item><span>{{ item.id }} · {{ item.mode }}</span><template #actions><a-button danger :disabled="busy || item.stopping" @click="stop(item)">{{ t(item.stopping ? 'standalone.masStopping' : 'standalone.masStop') }}</a-button></template></a-list-item></template>
      </a-list>
    </template>
    <a-empty v-else :description="t('standalone.relay.noResult')" class="page-state" />
  </section>
</template>

<style scoped>
.relay-list { margin-bottom: 24px; }
</style>
