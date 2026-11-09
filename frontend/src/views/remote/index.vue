<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import type { RelayCommandStatusOut, RelayNodeOut } from '@/api'
import { RelayService } from '@/api'
import { errorMessage } from '@/composables/useCommunityApi'
import { pollUntilSettled } from '@/utils/asyncGuard'

const { t, locale } = useI18n()
const busy = ref(false)
const error = ref('')
const node = ref<RelayNodeOut | null>(null)
const snapshot = ref<{ queues: Array<{ id: string; name: string }>; tasks: Array<{ id: string; mode: string; stopping: boolean }> } | null>(null)

type CommandStatus = 'done' | 'failed' | 'expired' | 'pending' | 'dispatched'
const isTerminal = (status: string): status is 'done' | 'failed' | 'expired' =>
  ['done', 'failed', 'expired'].includes(status)

// 组件卸载后轮询与定时刷新都要停下来，否则最长 300 秒里还在请求并给已关闭的页面弹提示。
let disposed = false
const COMMAND_POLL_INTERVAL_MS = 800

const waitCommand = async (commandId: string, timeoutSec: number) => {
  const outcome = await pollUntilSettled(() => RelayService.relayCommandStatus(commandId), {
    intervalMs: COMMAND_POLL_INTERVAL_MS,
    timeoutMs: timeoutSec * 1000,
    isDisposed: () => disposed,
    isSettled: status => isTerminal(status.commandStatus ?? ''),
  })
  // 卸载时返回 null，调用方据此结束，不再弹任何提示。
  if (outcome.status === 'disposed') return null
  if (outcome.status === 'timeout') throw new Error(t('standalone.relay.timeout'))
  return outcome.value
}

const runCommand = async (
  type: 'mas.snapshot' | 'mas.start' | 'mas.stop' | 'sign.run',
  payload: Record<string, unknown>,
  timeoutSec = 45,
): Promise<RelayCommandStatusOut | null> => {
  const accepted = await RelayService.relayCommand({ type, payload })
  return await waitCommand(accepted.id, timeoutSec)
}

let nodeErrorShown = false
const loadNodes = async () => {
  try {
    const { data } = await RelayService.relayNodes()
    if (disposed) return
    node.value = (data ?? [])[0] ?? null
    nodeErrorShown = false
  } catch (cause) {
    // 每 10 秒轮询一次，失败时只提示一次：既不产生 unhandled rejection，也不刷屏。
    if (disposed || nodeErrorShown) return
    nodeErrorShown = true
    error.value = errorMessage(cause, t('standalone.loadFailed'))
  }
}

// 与活动日历一致：把 ISO 时间格式化成当前语言环境的日期时间，不直接把原始字符串显示给用户。
const formatTime = (value?: string) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString(locale.value, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const refreshMas = async () => {
  busy.value = true
  error.value = ''
  try {
    const status = await runCommand('mas.snapshot', {})
    // 组件已卸载时 waitCommand 返回 null：直接结束，不再提示也不再写快照。
    if (!status) return
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
  if (!disposed) await loadNodes()
}

const start = async (queue: { id: string }) => {
  busy.value = true
  try {
    const status = await runCommand('mas.start', { taskId: queue.id, mode: 'AutoProxy' })
    if (!status) return
    if (status.commandStatus === 'done') message.success(t('standalone.masStarted'))
    else message.error(t('standalone.relay.loadFailed', { error: status.result?.error || '' }))
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.relay.loadFailed', { error: '' })))
  } finally {
    busy.value = false
  }
  if (!disposed) await refreshMas()
}

const stop = (task: { id: string; stopping: boolean }) =>
  Modal.confirm({
    title: t('standalone.masStopTitle'),
    content: task.id,
    onOk: async () => {
      busy.value = true
      try {
        const status = await runCommand('mas.stop', { taskId: task.id })
        if (!status) return
        if (status.commandStatus === 'done') message.success(t('standalone.relay.stopAccepted'))
        else message.error(t('standalone.relay.loadFailed', { error: status.result?.error || '' }))
      } catch (cause) {
        message.error(errorMessage(cause, t('standalone.relay.loadFailed', { error: '' })))
      } finally {
        busy.value = false
      }
      if (!disposed) await refreshMas()
    },
  })

const remoteSign = () =>
  Modal.confirm({
    title: t('standalone.relay.signConfirmTitle'),
    content: t('standalone.relay.signConfirmContent'),
    onOk: async () => {
      busy.value = true
      try {
        const status = await runCommand('sign.run', {}, 300)
        if (!status) return
        if (status.commandStatus === 'done') message.success(t('standalone.relay.signAccepted'))
        else message.error(t('standalone.relay.loadFailed', { error: status.result?.error || '' }))
      } catch (cause) {
        message.error(errorMessage(cause, t('standalone.relay.loadFailed', { error: '' })))
      } finally {
        busy.value = false
      }
    },
  })

const nodeStatusText = computed(() => {
  if (!node.value) return t('standalone.relay.nodeNone')
  const state = t(node.value.online ? 'standalone.relay.nodeOnline' : 'standalone.relay.nodeOffline')
  const seenAt = formatTime(node.value.lastSeenAt)
  return seenAt
    ? `${state} · ${t('standalone.relay.nodeLastSeen', { time: seenAt })}`
    : state
})

let nodesTimer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  void loadNodes()
  nodesTimer = setInterval(() => void loadNodes(), 10000)
})
onUnmounted(() => {
  disposed = true
  if (nodesTimer !== null) clearInterval(nodesTimer)
})
</script>

<template>
  <section>
    <header class="page-toolbar">

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
