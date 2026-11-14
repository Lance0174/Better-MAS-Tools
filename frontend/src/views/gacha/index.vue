<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import {
  Table as ATable,
  InputNumber as AInputNumber,
  Pagination as APagination,
  message,
} from 'ant-design-vue'
import AdaptivePanel from '@/components/AdaptivePanel.vue'
import ChoiceSelect from '@/components/ChoiceSelect.vue'
import GameTabs from '@/components/GameTabs.vue'
import { useMobileUi } from '@/composables/useMobileUi'
import { confirmDialog } from '@/utils/confirmDialog'
import { ExportOutlined, GiftOutlined, ImportOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { useI18n } from 'vue-i18n'
import type {
  AccountOut,
  GachaHeyboxOut,
  GachaRecord,
  GachaRecordsOut,
  GachaUpdateOut,
} from '@/api'
import { useGachaApi } from '@/composables/useGachaApi'
import { useCommunityApi, errorMessage } from '@/composables/useCommunityApi'
import { isAndroidLocal } from '@/services/android'
import { saveTextFile } from '@/utils/download'
import {
  HEYBOX_PAYLOAD_LIMIT,
  defaultSource,
  heyboxIdValid,
  heyboxPageUrl,
  heyboxPayloadReady,
  heyboxPayloadTooLarge,
  isHeyboxDerived,
  isHeyboxFill,
  sourceOptions,
  type FetchSource,
} from './heybox'
import { useOfficialGacha } from './useOfficialGacha'

const { t } = useI18n()
const api = useGachaApi()
const mobile = useMobileUi()
const accountsApi = useCommunityApi()
const game = ref<GachaRecord['game']>('genshin')
const player = ref('')
const pool = ref('')
const page = ref(1)
const data = ref<GachaRecordsOut>({ data: [], total: 0, players: [], pools: [] })
const accounts = ref<AccountOut[]>([])
const importing = ref(false)
const loading = ref(false)
const error = ref('')
const warnings = ref<string[]>([])
const fetchOpen = ref(false)
const exportOpen = ref(false)
// 「获取记录」弹窗的状态：source 是本次要用的来源，linkText / heyboxPayload 只在本次请求使用。
const source = ref<FetchSource>(defaultSource('genshin'))
const linkText = ref('')
// 明日方舟复用已登录森空岛账号；其他游戏使用链接或文件。
const playerUid = ref('')
const official = useOfficialGacha(game, accounts, () => t('standalone.loadFailed'))
const accountId = official.accountId
const preparing = ref(false)
const timezone = ref(8)
const maxPages = ref(100)
const heyboxId = ref('')
const heyboxPayload = ref('')
const heyboxResult = ref<GachaHeyboxOut | null>(null)
const revoking = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
let generation = 0
let sourcePreparation = 0
const games = computed(() =>
  ['genshin', 'starrail', 'zzz', 'wuthering', 'arknights', 'endfield'].map(value => ({
    value: value as GachaRecord['game'],
    label: t(`standalone.gachaGames.${value}`),
  }))
)
const players = computed(() => [
  { value: '', label: t('standalone.allPlayers') },
  ...(data.value.players ?? []).map(value => ({ value, label: value })),
])
const pools = computed(() => [
  { value: '', label: t('standalone.allPools') },
  ...Array.from(
    new Map(
      (data.value.pools ?? []).map(item => [
        item.poolType,
        { value: item.poolType, label: item.poolName },
      ])
    ).values()
  ),
])
const sklandAccounts = official.options
const supportsUigf = computed(() => ['genshin', 'starrail', 'zzz'].includes(game.value))
// 明日方舟只走森空岛授权；小黑盒补录只在终末地出现。
const sourceChoices = computed(() => {
  const labels: Record<FetchSource, string> = {
    link: t('standalone.gachaSourceNames.link'),
    skland: t('standalone.gachaSourceNames.skland'),
    file: t('standalone.gachaSourceNames.file'),
    heybox: t('standalone.gachaSourceNames.heybox'),
  }
  return sourceOptions(game.value).map(value => ({ value, label: labels[value] }))
})
const needsPlayerUid = computed(() => game.value === 'arknights' || game.value === 'endfield')
const heyboxIdInvalid = computed(
  () => heyboxId.value.trim().length > 0 && !heyboxIdValid(heyboxId.value)
)
const heyboxPayloadOver = computed(() => heyboxPayloadTooLarge(heyboxPayload.value))
const heyboxIssues = computed(() => [
  ...(heyboxResult.value?.warnings ?? []),
  ...(heyboxResult.value?.skipped ?? []),
])
const heyboxSummary = computed(() => {
  const result = heyboxResult.value
  if (!result) return ''
  return t('standalone.gachaHeyboxResult', {
    added: result.added ?? 0,
    replaced: result.replaced ?? 0,
    skipped: result.skipped?.length ?? 0,
  })
})
const canSubmit = computed(() => {
  if (preparing.value || importing.value || revoking.value) return false
  if (source.value === 'link') {
    return (
      linkText.value.trim().length > 0 && (!needsPlayerUid.value || playerUid.value.trim() !== '')
    )
  }
  if (source.value === 'skland') {
    return (
      !official.loading.value && accountId.value !== '' && official.playerUid.value.trim() !== ''
    )
  }
  if (source.value === 'heybox') {
    return (
      heyboxIdValid(heyboxId.value) &&
      playerUid.value.trim() !== '' &&
      heyboxPayloadReady(heyboxPayload.value)
    )
  }
  return false
})
const columns = computed(() => [
  { title: t('standalone.gachaTime'), dataIndex: 'time', width: 190 },
  { title: t('standalone.gachaItem'), key: 'item', dataIndex: 'name' },
  { title: t('standalone.gachaRarity'), dataIndex: 'rarity', width: 90 },
  { title: t('standalone.gachaPool'), key: 'pool', width: 200 },
  { title: 'UID', dataIndex: 'playerUid', width: 150 },
])
const keyOf = (item: GachaRecord) => [item.game, item.playerUid, item.poolType, item.id].join(':')
const load = async () => {
  const current = ++generation
  loading.value = true
  try {
    const response = await api.list(game.value, player.value, pool.value, page.value)
    if (current === generation) {
      data.value = response
      error.value = ''
    }
  } catch (cause) {
    if (current === generation) error.value = errorMessage(cause, t('standalone.loadFailed'))
  } finally {
    if (current === generation) loading.value = false
  }
}
const refresh = () => {
  page.value = 1
  void load()
}
watch(game, () => {
  player.value = ''
  pool.value = ''
  warnings.value = []
  // 换游戏后原来选的来源可能不适用（例如小黑盒补录只有终末地有）。
  if (!sourceOptions(game.value).includes(source.value)) source.value = defaultSource(game.value)
  if (fetchOpen.value) void prepareSource()
  refresh()
})
const prepareSource = async () => {
  const current = ++sourcePreparation
  preparing.value = false
  if (source.value === 'skland') {
    preparing.value = true
    try {
      await official.prepare()
    } catch (cause) {
      if (current === sourcePreparation && fetchOpen.value)
        message.error(errorMessage(cause, t('standalone.loadFailed')))
    } finally {
      if (current === sourcePreparation) preparing.value = false
    }
  }
}
const openFetch = (nextSource?: FetchSource) => {
  source.value =
    nextSource && sourceOptions(game.value).includes(nextSource)
      ? nextSource
      : defaultSource(game.value)
  fetchOpen.value = true
  void prepareSource()
}
watch(fetchOpen, open => {
  if (!open) {
    sourcePreparation++
    preparing.value = false
    linkText.value = ''
    heyboxPayload.value = ''
    heyboxResult.value = null
  }
})
onBeforeUnmount(() => {
  generation++
  sourcePreparation++
  linkText.value = ''
  heyboxPayload.value = ''
})
onMounted(async () => {
  await load()
  try {
    accounts.value = (await accountsApi.listAccounts()).data
  } catch (cause) {
    error.value = errorMessage(cause, t('standalone.loadFailed'))
  }
})
const finish = async (response: GachaUpdateOut) => {
  warnings.value = response.warnings ?? []
  const text = t('standalone.gachaAdded', {
    added: response.added ?? 0,
    fetched: response.fetched ?? 0,
  })
  if (warnings.value.length) message.warning(text)
  else message.success(text)
  // 导入/抓取会改变记录总数，原本停在最后一页时页码可能越界（表格空但 total>0），统一回到第一页。
  page.value = 1
  await load()
}
const fetchRecords = async () => {
  if (!canSubmit.value) return
  importing.value = true
  try {
    const response = await api.fetch({
      game: game.value,
      source: linkText.value,
      accountId: source.value === 'skland' ? accountId.value : '',
      playerUid: source.value === 'skland' ? official.playerUid.value : playerUid.value,
      timezone: timezone.value,
      maxPages: maxPages.value,
    })
    fetchOpen.value = false
    await finish(response)
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.gachaFetchFailed')))
  } finally {
    importing.value = false
  }
}
const importHeybox = async () => {
  if (!canSubmit.value) return
  importing.value = true
  try {
    const response = await api.heybox({
      game: 'endfield',
      heyboxId: heyboxId.value.trim(),
      playerUid: playerUid.value.trim(),
      payload: heyboxPayload.value,
    })
    heyboxResult.value = response
    warnings.value = response.warnings ?? []
    const text = t('standalone.gachaHeyboxAdded', {
      added: response.added ?? 0,
      replaced: response.replaced ?? 0,
    })
    if (warnings.value.length || (response.skipped ?? []).length) message.warning(text)
    else message.success(text)
    page.value = 1
    await load()
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.gachaHeyboxFailed')))
  } finally {
    importing.value = false
  }
}
const revokeHeybox = async () => {
  revoking.value = true
  try {
    const response = await api.revokeHeybox(playerUid.value.trim())
    heyboxResult.value = null
    warnings.value = response.warnings ?? []
    message.success(response.message || t('standalone.gachaHeyboxRevokeNone'))
    page.value = 1
    await load()
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.gachaHeyboxFailed')))
  } finally {
    revoking.value = false
  }
}
const confirmRevoke = () =>
  confirmDialog({
    title: t('standalone.gachaHeyboxRevoke'),
    content: t('standalone.gachaHeyboxRevokeHint'),
    okButtonProps: { danger: true },
    onOk: revokeHeybox,
  })
const importFile = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  try {
    if (file.size > 20_000_000) throw new Error(t('standalone.gachaFileTooLarge'))
    await finish(await api.import(game.value, await file.text()))
    fetchOpen.value = false
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.gachaImportFailed')))
  } finally {
    importing.value = false
    input.value = ''
  }
}
const exportFile = async (format: 'bmasc' | 'uigf') => {
  importing.value = true
  try {
    const response = await api.export(game.value, player.value, format)
    await saveTextFile(response.filename, response.content)
    exportOpen.value = false
  } catch (cause) {
    message.error(errorMessage(cause, t('standalone.gachaExportFailed')))
  } finally {
    importing.value = false
  }
}
const changePage = (value: { current?: number }) => {
  page.value = value.current ?? 1
  void load()
}
</script>

<template>
  <section class="gacha-page">
    <div class="gacha-workspace">
      <GameTabs
        :value="game"
        :options="games"
        :disabled="importing"
        :label="t('standalone.gachaGame')"
        @update:value="value => (game = value as GachaRecord['game'])"
      />
      <header class="page-toolbar">
        <div class="gacha-actions">
          <a-button class="gacha-fetch" type="primary" :loading="importing" @click="openFetch()">{{
            t('standalone.ui.getRecords')
          }}</a-button>
          <a-button :disabled="importing" @click="openFetch('file')"
            ><ImportOutlined />{{ t('standalone.gachaImport') }}</a-button
          >
          <a-button
            :disabled="importing || !data.total"
            :aria-label="t('standalone.ui.exportRecords')"
            @click="exportOpen = true"
            ><ExportOutlined /><span v-if="!mobile">{{
              t('standalone.ui.exportRecords')
            }}</span></a-button
          >
        </div>
        <p class="gacha-entry-hint">{{ t('standalone.ui.gachaEntryHint') }}</p>
      </header>
      <div class="gacha-filters">
        <ChoiceSelect
          v-model:value="player"
          :options="players"
          :disabled="importing"
          class="gacha-select"
          :aria-label="t('standalone.allPlayers')"
          @change="refresh"
        />
        <ChoiceSelect
          v-model:value="pool"
          :options="pools"
          :disabled="importing"
          class="gacha-select"
          :aria-label="t('standalone.allPools')"
          @change="refresh"
        />
      </div>
      <p class="gacha-history-hint">{{ t('standalone.gachaHistoryHint') }}</p>
    </div>
    <a-alert v-if="error" type="error" show-icon :message="error" class="page-alert" />
    <a-alert
      v-for="warning in warnings"
      :key="warning"
      type="warning"
      show-icon
      :message="warning"
      class="page-alert"
    />
    <div class="gacha-summary">
      <article v-for="summary in data.pools" :key="summary.poolName" class="gacha-pool">
        <strong>{{ summary.poolName }}</strong>
        <span>{{
          t('standalone.gachaPoolSummary', {
            total: summary.total,
            top: summary.topRarity,
            count: summary.topCount,
            since: summary.sinceTop,
          })
        }}</span>
      </article>
    </div>
    <h2 v-if="data.total || loading" class="records-heading">
      {{ t('standalone.ui.latestRecords')
      }}<a-button type="text" size="small" :loading="loading" :disabled="importing" @click="refresh"
        ><ReloadOutlined />{{ t('standalone.ui.refreshRecords') }}</a-button
      ><small>{{ t('standalone.ui.recordCount', { count: data.total }) }}</small>
    </h2>
    <div v-if="!data.total && !loading" class="gacha-empty">
      <span class="gacha-empty-icon" aria-hidden="true"><GiftOutlined /></span>
      <h2>{{ t('standalone.ui.noRecords') }}</h2>
      <p>{{ t('standalone.ui.gachaEmptyHint') }}</p>
      <a-button type="primary" :disabled="importing" @click="openFetch()">{{
        t('standalone.ui.getRecords')
      }}</a-button>
    </div>
    <a-spin v-else-if="mobile" :spinning="loading || importing">
      <div class="mobile-records">
        <a-empty v-if="!data.total" :description="t('standalone.ui.noRecords')" />
        <article
          v-for="record in data.data"
          :key="keyOf(record)"
          class="mobile-record"
          :class="{ 'top-rarity': record.rarity >= 5 }"
        >
          <div>
            <strong>{{ record.name }}</strong>
            <span class="mobile-tags">
              <a-tag v-if="isHeyboxFill(record.kind)">{{ t('standalone.gachaHeyboxFill') }}</a-tag>
              <a-tag v-if="isHeyboxDerived(record.id)" color="purple">{{
                t('standalone.gachaHeyboxBadge')
              }}</a-tag>
              <a-tag color="blue">{{ record.rarity }} ★</a-tag>
            </span>
          </div>
          <span>{{ record.poolName || record.poolType }} · {{ record.time }}</span>
          <small>UID {{ record.playerUid }}</small>
        </article>
      </div>
      <a-pagination
        v-if="data.total"
        :current="page"
        :page-size="50"
        :total="data.total"
        simple
        @change="value => changePage({ current: value })"
      />
    </a-spin>
    <a-table
      v-else
      class="gacha-table"
      table-layout="fixed"
      :columns="columns"
      :data-source="data.data"
      :row-key="keyOf"
      :loading="loading || importing"
      :pagination="{ current: page, pageSize: 50, total: data.total, showSizeChanger: false }"
      @change="changePage"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'pool'">{{ record.poolName || record.poolType }}</template>
        <template v-else-if="column.key === 'item'">
          <span>{{ record.name }}</span>
          <a-tag v-if="isHeyboxFill(record.kind)">{{ t('standalone.gachaHeyboxFill') }}</a-tag>
          <a-tag v-if="isHeyboxDerived(record.id)" color="purple">{{
            t('standalone.gachaHeyboxBadge')
          }}</a-tag>
        </template>
      </template>
    </a-table>
    <AdaptivePanel
      :open="exportOpen"
      :title="t('standalone.ui.exportRecords')"
      :busy="importing"
      @close="exportOpen = false"
    >
      <div class="export-options">
        <a-button :disabled="importing" @click="exportFile('bmasc')">{{
          t('standalone.gachaExport')
        }}</a-button
        ><a-button v-if="supportsUigf" :disabled="importing" @click="exportFile('uigf')">{{
          t('standalone.gachaUigf')
        }}</a-button>
      </div>
    </AdaptivePanel>
    <AdaptivePanel
      :open="fetchOpen"
      :title="t('standalone.ui.getRecords')"
      :busy="importing || revoking"
      desktop-modal
      @close="fetchOpen = false"
    >
      <a-form
        layout="vertical"
        :model="{ linkText, playerUid, accountId, timezone, maxPages, heyboxId, heyboxPayload }"
        :disabled="importing || revoking"
      >
        <a-alert
          v-if="source === 'skland' && !preparing && !official.options.value.length"
          type="info"
          show-icon
          :message="t('standalone.ui.gachaNeedsAccount')"
          class="page-alert"
        >
          <template #action
            ><router-link to="/accounts" @click="fetchOpen = false">{{
              t('standalone.accountList')
            }}</router-link></template
          >
        </a-alert>
        <a-form-item name="source" :label="t('standalone.gachaSourceMode')">
          <ChoiceSelect
            v-model:value="source"
            :options="sourceChoices"
            :disabled="importing || revoking"
            :aria-label="t('standalone.gachaSourceMode')"
            @change="prepareSource"
          />
        </a-form-item>
        <a-alert
          v-if="source === 'link' || source === 'skland'"
          type="info"
          show-icon
          :message="
            source === 'skland'
              ? t('standalone.ui.gachaSklandHint')
              : t(`standalone.gachaHints.${game}`)
          "
          class="page-alert"
        />
        <template v-if="source === 'link'">
          <a-form-item name="linkText" :label="t('standalone.gachaSource')" required>
            <a-textarea v-model:value="linkText" :rows="3" autocomplete="off" />
          </a-form-item>
          <a-form-item v-if="needsPlayerUid" name="playerUid" label="UID" required>
            <a-input v-model:value="playerUid" autocomplete="off" />
          </a-form-item>
        </template>
        <template v-else-if="source === 'skland'">
          <a-form-item name="accountId" :label="t('standalone.skland')" required>
            <ChoiceSelect
              v-model:value="accountId"
              :options="sklandAccounts"
              :disabled="importing || revoking || preparing"
              allow-clear
            />
          </a-form-item>
          <a-alert
            v-if="official.issue.value"
            type="warning"
            show-icon
            :message="official.issue.value"
            class="page-alert"
          />
          <a-form-item name="playerUid" :label="t('standalone.gachaCookieUid')" required>
            <ChoiceSelect
              v-if="official.roleOptions.value.length"
              v-model:value="official.playerUid.value"
              :options="official.roleOptions.value"
              :disabled="importing || revoking || preparing || official.loading.value"
              :loading="official.loading.value"
              :placeholder="t('standalone.gachaChooseRole')"
            />
            <a-input
              v-else
              v-model:value="official.playerUid.value"
              :disabled="official.loading.value || preparing"
              :placeholder="t('standalone.gachaUidFallback')"
              autocomplete="off"
            />
          </a-form-item>
        </template>
        <template v-else-if="source === 'file'">
          <a-alert
            type="info"
            show-icon
            :message="t('standalone.gachaFileHint')"
            class="page-alert"
          />
        </template>
        <template v-else>
          <a-alert
            type="info"
            show-icon
            :message="
              isAndroidLocal
                ? t('standalone.gachaHeyboxMobileHint')
                : t('standalone.gachaHeyboxHint')
            "
            class="page-alert"
          />
          <a-form-item name="heyboxId" :label="t('standalone.gachaHeyboxId')" required>
            <a-input
              v-model:value="heyboxId"
              :maxlength="12"
              autocomplete="off"
              :status="heyboxIdInvalid ? 'error' : undefined"
            />
            <template #extra>
              <span v-if="heyboxIdInvalid">{{ t('standalone.gachaHeyboxIdInvalid') }}</span>
              <a
                v-else-if="!isAndroidLocal && heyboxIdValid(heyboxId)"
                :href="heyboxPageUrl(heyboxId)"
                target="_blank"
                rel="noreferrer"
                >{{ t('standalone.gachaHeyboxOpen') }}</a
              >
            </template>
          </a-form-item>
          <a-form-item name="playerUid" :label="t('standalone.gachaHeyboxUid')" required>
            <a-input v-model:value="playerUid" autocomplete="off" />
          </a-form-item>
          <a-form-item name="heyboxPayload" :label="t('standalone.gachaHeyboxPayload')" required>
            <a-textarea
              v-model:value="heyboxPayload"
              :rows="6"
              autocomplete="off"
              :status="heyboxPayloadOver ? 'error' : undefined"
            />
            <template #extra>
              <span v-if="heyboxPayloadOver">{{ t('standalone.gachaHeyboxTooLarge') }}</span>
              <span v-else>{{
                t('standalone.gachaHeyboxPayloadHint', {
                  limit: HEYBOX_PAYLOAD_LIMIT.toLocaleString(),
                })
              }}</span>
            </template>
          </a-form-item>
          <div v-if="heyboxResult" class="gacha-result">
            <a-alert type="success" show-icon :message="heyboxSummary" />
            <ul v-if="heyboxIssues.length">
              <li v-for="item in heyboxIssues" :key="item">{{ item }}</li>
            </ul>
          </div>
          <a-button
            danger
            size="small"
            :loading="revoking"
            :disabled="!playerUid.trim() || revoking"
            @click="confirmRevoke"
            >{{ t('standalone.gachaHeyboxRevoke') }}</a-button
          >
        </template>
        <a-collapse
          v-if="['skland', 'link'].includes(source) && game !== 'wuthering'"
          ghost
          class="gacha-advanced"
        >
          <a-collapse-panel key="options" :header="t('standalone.ui.gachaAdvanced')">
            <a-form-item v-if="supportsUigf" name="timezone" :label="t('standalone.gachaTimezone')"
              ><a-input-number v-model:value="timezone" :min="-12" :max="14"
            /></a-form-item>
            <a-form-item name="maxPages" :label="t('standalone.gachaMaxPages')"
              ><a-input-number v-model:value="maxPages" :min="1" :max="500"
            /></a-form-item>
          </a-collapse-panel>
        </a-collapse>
      </a-form>
      <input
        ref="fileInput"
        type="file"
        accept=".json,application/json"
        hidden
        @change="importFile"
      />
      <template #footer>
        <a-button :disabled="importing || revoking" @click="fetchOpen = false">{{
          t('standalone.cancel')
        }}</a-button>
        <a-button
          v-if="source === 'file'"
          type="primary"
          :loading="importing"
          @click="fileInput?.click()"
          >{{ t('standalone.gachaImport') }}</a-button
        >
        <a-button
          v-else-if="source === 'heybox'"
          type="primary"
          :loading="importing"
          :disabled="!canSubmit"
          @click="importHeybox"
          >{{ t('standalone.gachaHeyboxImport') }}</a-button
        >
        <a-button
          v-else
          type="primary"
          :loading="importing"
          :disabled="!canSubmit"
          @click="fetchRecords"
          >{{ t('standalone.gachaFetch') }}</a-button
        >
      </template>
    </AdaptivePanel>
  </section>
</template>

<style scoped>
.gacha-workspace {
  padding: 24px;
  margin-bottom: 24px;
  background: var(--ant-color-bg-container);
  border-radius: 24px;
}
.gacha-workspace .page-toolbar {
  display: block;
  margin: 20px 0;
}
.gacha-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.gacha-entry-hint {
  color: var(--ant-color-text-secondary);
  font-size: 12px;
  line-height: 1.7;
  margin: 12px 0 0;
}
.gacha-empty {
  padding: 40px 24px;
  text-align: center;
  border-radius: 24px;
  background: var(--ant-color-bg-container);
}
.gacha-empty-icon {
  display: inline-grid;
  place-items: center;
  width: 64px;
  height: 64px;
  border-radius: 22px;
  color: var(--ant-color-primary);
  background: var(--ant-color-primary-bg);
  font-size: 28px;
}
.gacha-empty h2 {
  margin: 18px 0 8px;
  font-size: 17px;
}
.gacha-empty p {
  color: var(--ant-color-text-secondary);
  font-size: 12px;
  line-height: 1.8;
  margin: 0 auto 22px;
  max-width: 420px;
}
.gacha-advanced {
  margin-top: 12px;
}
.export-options {
  display: grid;
  gap: 12px;
}
/* 保留表内横向滚动与外部分页，避免空表测量反复触发尺寸通知。 */
.gacha-table :deep(.ant-table-content) {
  overflow-x: auto;
}
.gacha-table :deep(.ant-table-content > table) {
  min-width: 800px;
}
.gacha-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.gacha-select {
  width: 220px;
}
.gacha-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.gacha-pool {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: var(--ant-color-bg-container);
  border: 0;
  border-radius: 24px;
}
.gacha-pool span {
  color: var(--ant-color-text-secondary);
  font-size: 12px;
}
.gacha-result {
  margin-bottom: 16px;
}
.gacha-result ul {
  margin: 8px 0 0;
  padding-left: 20px;
  color: var(--ant-color-text-secondary);
  font-size: 12px;
}
.mobile-records {
  min-height: 120px;
  padding: 4px 18px;
  background: var(--ant-color-bg-container);
  border-radius: 24px;
  margin-bottom: 16px;
}
.mobile-record {
  padding: 16px 0;
  border-bottom: 1px solid var(--ant-color-border-secondary);
  overflow-wrap: anywhere;
}
.mobile-record > div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}
.mobile-tags {
  display: flex;
  gap: 4px;
}
.mobile-record > span,
.mobile-record small {
  display: block;
  color: var(--ant-color-text-secondary);
  font-size: 12px;
}
.records-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-size: 17px;
  margin: 24px 0 14px;
  flex-wrap: wrap;
}
.records-heading > .ant-btn {
  margin-left: auto;
}
.records-heading small {
  font-size: 12px;
  color: var(--ant-color-text-secondary);
  font-weight: 400;
}
.gacha-history-hint {
  font-size: 12px;
  color: var(--ant-color-text-secondary);
  margin: 12px 0 0;
  line-height: 1.7;
}
.mobile-record.top-rarity strong {
  color: var(--ant-color-warning-text);
}
@media (max-width: 600px) {
  .gacha-workspace {
    padding: 18px 16px;
    margin-bottom: 18px;
  }
  .gacha-workspace .page-toolbar {
    margin-block: 16px;
  }
  .gacha-actions {
    width: 100%;
    gap: 8px;
  }
  .gacha-actions .gacha-fetch {
    flex: 1;
  }
  .gacha-actions .ant-btn {
    font-size: 12px;
    padding-inline: 12px;
  }
  .gacha-select {
    flex: 1 1 40%;
    min-width: 0;
    width: 100%;
  }
  .gacha-summary {
    display: flex;
    overflow-x: auto;
    gap: 12px;
    padding-bottom: 5px;
  }
  .gacha-pool {
    min-width: 240px;
    flex-shrink: 0;
  }
  .gacha-empty {
    padding: 32px 20px;
  }
  .records-heading {
    font-size: 16px;
    gap: 6px;
  }
  .records-heading > .ant-btn {
    padding-inline: 4px;
    font-size: 12px;
  }
}
</style>
