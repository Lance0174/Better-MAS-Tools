<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import {
  Table as ATable,
  InputNumber as AInputNumber,
  Pagination as APagination,
  Popconfirm as APopconfirm,
  message,
} from 'ant-design-vue'
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
  COOKIE_LIMIT,
  HEYBOX_PAYLOAD_LIMIT,
  cookieReady,
  defaultSource,
  heyboxIdValid,
  heyboxPageUrl,
  heyboxPayloadReady,
  heyboxPayloadTooLarge,
  isCookieGame,
  isHeyboxDerived,
  isHeyboxFill,
  sourceOptions,
  type FetchSource,
} from './heybox'

const { t } = useI18n()
const api = useGachaApi()
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
// 「获取记录」弹窗的状态：source 是本次要用的来源，linkText / heyboxPayload 只在本次请求使用。
const source = ref<FetchSource>(defaultSource('genshin'))
const linkText = ref('')
// 米游社 Cookie 只在本次弹窗里保存，提交后立即清空；留空时改用下面选中的账号组。
const cookieText = ref('')
const cookieAccountId = ref('')
const accountId = ref('')
const playerUid = ref('')
const timezone = ref(8)
const maxPages = ref(100)
const heyboxId = ref('')
const heyboxPayload = ref('')
const heyboxResult = ref<GachaHeyboxOut | null>(null)
const revoking = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
let generation = 0
const games = computed(() =>
  ['genshin', 'starrail', 'zzz', 'wuthering', 'arknights', 'endfield'].map(value => ({
    value,
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
const sklandAccounts = computed(() =>
  accounts.value
    .filter(item => item.data.SklandToken)
    .map(item => ({ value: item.uid, label: item.data.Name }))
)
const miyousheAccounts = computed(() =>
  accounts.value
    .filter(item => item.data.MiyousheToken)
    .map(item => ({ value: item.uid, label: item.data.Name }))
)
const supportsUigf = computed(() => ['genshin', 'starrail', 'zzz'].includes(game.value))
// 明日方舟只走森空岛授权；小黑盒补录只在终末地出现。
const sourceChoices = computed(() => {
  const labels: Record<FetchSource, string> = {
    link: t('standalone.gachaSourceNames.link'),
    cookie: t('standalone.gachaSourceNames.cookie'),
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
const cookieOverLimit = computed(() => cookieText.value.length > COOKIE_LIMIT)
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
  if (source.value === 'link') {
    return (
      linkText.value.trim().length > 0 && (!needsPlayerUid.value || playerUid.value.trim() !== '')
    )
  }
  if (source.value === 'cookie') {
    return (
      playerUid.value.trim() !== '' && cookieReady(cookieText.value, cookieAccountId.value)
    )
  }
  if (source.value === 'skland') {
    return accountId.value !== '' && playerUid.value.trim() !== ''
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
  refresh()
})
const openFetch = () => {
  source.value = defaultSource(game.value)
  fetchOpen.value = true
}
watch(fetchOpen, open => {
  if (!open) {
    linkText.value = ''
    cookieText.value = ''
    heyboxPayload.value = ''
    heyboxResult.value = null
  }
})
onBeforeUnmount(() => {
  generation++
  linkText.value = ''
  cookieText.value = ''
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
      accountId: accountId.value,
      playerUid: playerUid.value,
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
const fetchByCookie = async () => {
  if (!canSubmit.value || !isCookieGame(game.value)) return
  importing.value = true
  try {
    const response = await api.fetchCookie({
      game: game.value,
      accountId: cookieAccountId.value,
      playerUid: playerUid.value.trim(),
      cookie: cookieText.value,
      timezone: timezone.value,
      maxPages: maxPages.value,
    })
    // Cookie 是敏感凭据：用过就丢，不留在组件状态里。
    cookieText.value = ''
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
const importFile = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  try {
    if (file.size > 20_000_000) throw new Error(t('standalone.gachaFileTooLarge'))
    fetchOpen.value = false
    await finish(await api.import(game.value, await file.text()))
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
    <header class="page-toolbar">
      <h1 class="page-title">{{ t('standalone.gacha') }}</h1>
      <a-space wrap>
        <a-button :disabled="importing || !data.total" @click="exportFile('bmasc')">{{
          t('standalone.gachaExport')
        }}</a-button>
        <a-button
          v-if="supportsUigf"
          :disabled="importing || !data.total"
          @click="exportFile('uigf')"
          >{{ t('standalone.gachaUigf') }}</a-button
        >
        <a-button type="primary" :loading="importing" @click="openFetch">{{
          t('standalone.gachaFetch')
        }}</a-button>
      </a-space>
    </header>
    <div class="gacha-filters">
      <a-select
        v-model:value="game"
        :options="games"
        :disabled="importing"
        class="gacha-select"
        :aria-label="t('standalone.gachaGame')"
      />
      <a-select
        v-model:value="player"
        :options="players"
        :disabled="importing"
        class="gacha-select"
        :aria-label="t('standalone.allPlayers')"
        @change="refresh"
      />
      <a-select
        v-model:value="pool"
        :options="pools"
        :disabled="importing"
        class="gacha-select"
        :aria-label="t('standalone.allPools')"
        @change="refresh"
      />
    </div>
    <a-alert type="info" show-icon :message="t('standalone.gachaHistoryHint')" class="page-alert" />
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
    <a-spin v-if="isAndroidLocal" :spinning="loading || importing">
      <div class="mobile-records">
        <a-empty v-if="!data.total" />
        <article v-for="record in data.data" :key="keyOf(record)" class="mobile-record">
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
      :columns="columns"
      :data-source="data.data"
      :row-key="keyOf"
      :loading="loading || importing"
      :pagination="{ current: page, pageSize: 50, total: data.total, showSizeChanger: false }"
      :scroll="{ x: 800 }"
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
    <a-modal
      :open="fetchOpen"
      :title="t('standalone.gachaFetch')"
      :closable="!importing"
      :mask-closable="!importing"
      @cancel="fetchOpen = false"
    >
      <a-form
        layout="vertical"
        :model="{ linkText, playerUid, accountId, timezone, maxPages, heyboxId, heyboxPayload }"
        :disabled="importing"
      >
        <a-form-item name="source" :label="t('standalone.gachaSourceMode')">
          <a-radio-group v-model:value="source" button-style="solid">
            <a-radio-button v-for="choice in sourceChoices" :key="choice.value" :value="choice.value">
              {{ choice.label }}
            </a-radio-button>
          </a-radio-group>
        </a-form-item>
        <a-alert
          type="info"
          show-icon
          :message="t(`standalone.gachaHints.${game}`)"
          class="page-alert"
        />
        <template v-if="source === 'link'">
          <a-form-item name="linkText" :label="t('standalone.gachaSource')" required>
            <a-textarea v-model:value="linkText" :rows="3" autocomplete="off" />
          </a-form-item>
          <a-form-item v-if="needsPlayerUid" name="playerUid" label="UID" required>
            <a-input v-model:value="playerUid" autocomplete="off" />
          </a-form-item>
          <a-form-item v-if="supportsUigf" name="timezone" :label="t('standalone.gachaTimezone')">
            <a-input-number v-model:value="timezone" :min="-12" :max="14" />
          </a-form-item>
          <a-form-item
            v-if="game !== 'wuthering'"
            name="maxPages"
            :label="t('standalone.gachaMaxPages')"
          >
            <a-input-number v-model:value="maxPages" :min="1" :max="500" />
          </a-form-item>
        </template>
        <template v-else-if="source === 'cookie'">
          <a-alert
            type="info"
            show-icon
            :message="t('standalone.gachaCookieHint')"
            class="page-alert"
          />
          <a-form-item name="cookieAccountId" :label="t('standalone.gachaCookieAccount')">
            <a-select
              v-model:value="cookieAccountId"
              :options="miyousheAccounts"
              allow-clear
              :placeholder="t('standalone.gachaCookieAccountHint')"
            />
          </a-form-item>
          <a-form-item name="cookieText" :label="t('standalone.gachaCookieLabel')">
            <a-input-password
              v-model:value="cookieText"
              autocomplete="new-password"
              spellcheck="false"
              :status="cookieOverLimit ? 'error' : undefined"
            />
            <template #extra>
              <span v-if="cookieOverLimit">{{ t('standalone.gachaCookieTooLong') }}</span>
              <span v-else>{{ t('standalone.gachaCookieExtra') }}</span>
            </template>
          </a-form-item>
          <a-form-item name="playerUid" :label="t('standalone.gachaCookieUid')" required>
            <a-input v-model:value="playerUid" autocomplete="off" />
          </a-form-item>
          <a-form-item name="timezone" :label="t('standalone.gachaTimezone')">
            <a-input-number v-model:value="timezone" :min="-12" :max="14" />
          </a-form-item>
          <a-form-item name="maxPages" :label="t('standalone.gachaMaxPages')">
            <a-input-number v-model:value="maxPages" :min="1" :max="500" />
          </a-form-item>
        </template>
        <template v-else-if="source === 'skland'">
          <a-form-item name="accountId" :label="t('standalone.skland')" required>
            <a-select v-model:value="accountId" :options="sklandAccounts" allow-clear />
          </a-form-item>
          <a-form-item name="playerUid" label="UID" required>
            <a-input v-model:value="playerUid" autocomplete="off" />
          </a-form-item>
          <a-form-item v-if="game !== 'wuthering'" name="maxPages" :label="t('standalone.gachaMaxPages')">
            <a-input-number v-model:value="maxPages" :min="1" :max="500" />
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
          <a-popconfirm
            :title="t('standalone.gachaHeyboxRevokeHint')"
            :disabled="!playerUid.trim() || revoking"
            @confirm="revokeHeybox"
          >
            <a-button danger size="small" :loading="revoking" :disabled="!playerUid.trim()">
              {{ t('standalone.gachaHeyboxRevoke') }}
            </a-button>
          </a-popconfirm>
        </template>
      </a-form>
      <input
        ref="fileInput"
        type="file"
        accept=".json,application/json"
        hidden
        @change="importFile"
      />
      <template #footer>
        <a-button :disabled="importing" @click="fetchOpen = false">{{
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
          v-else-if="source === 'cookie'"
          type="primary"
          :loading="importing"
          :disabled="!canSubmit"
          @click="fetchByCookie"
          >{{ t('standalone.gachaCookieSubmit') }}</a-button
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
    </a-modal>
  </section>
</template>

<style scoped>
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
  background: var(--ant-color-primary-bg);
  border: 1px solid var(--ant-color-primary-border);
  border-radius: 8px;
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
  margin-bottom: 16px;
}
.mobile-record {
  padding: 12px 0;
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
@media (max-width: 600px) {
  .gacha-select {
    flex: 1 1 100%;
    min-width: 0;
    width: 100%;
  }
  .gacha-summary {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
