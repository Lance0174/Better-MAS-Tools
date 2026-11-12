<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Modal } from 'ant-design-vue'
import type { UpdateCheckOut } from '@/api'
import { useUpdatesApi } from '@/composables/useUpdatesApi'
import { errorMessage } from '@/composables/useCommunityApi'
import { androidCall, isAndroidLocal } from '@/services/android'
import { isDesktop } from '@/services/desktop'

const { t } = useI18n()
const api = useUpdatesApi()
const currentVersion = String(import.meta.env.BMAT_VERSION)
const channel = ref<'stable' | 'beta'>(currentVersion.includes('-') ? 'beta' : 'stable')
const result = ref<UpdateCheckOut | null>(null)
const busy = ref(false)
const downloaded = ref(false)
const failure = ref('')
const notice = ref('')
const canInstall = isAndroidLocal || (isDesktop && !!window.bmatDesktop)
const channels = computed(() => [
  { value: 'stable', label: t('standalone.updateStable') },
  { value: 'beta', label: t('standalone.updateBeta') },
])
function resetResult() {
  result.value = null
  downloaded.value = false
  notice.value = ''
  failure.value = ''
}
async function check() {
  if (busy.value) return
  busy.value = true
  failure.value = ''
  notice.value = ''
  downloaded.value = false
  result.value = null
  try {
    result.value = await api.check(isAndroidLocal ? 'android' : 'windows', channel.value)
  } catch (cause) {
    failure.value = errorMessage(cause, t('standalone.updateCheckFailed'))
  } finally {
    busy.value = false
  }
}
async function download() {
  if (busy.value || !result.value?.available || !canInstall) return
  busy.value = true
  failure.value = ''
  notice.value = t('standalone.updateDownloading')
  try {
    const data = result.value
    const asset = {
      downloadUrl: data.downloadUrl ?? '',
      sha256: data.sha256 ?? '',
      size: data.size ?? 0,
      assetName: data.assetName ?? '',
    }
    const response = isAndroidLocal
      ? await androidCall('update.download', asset)
      : await window.bmatDesktop!.downloadUpdate(asset)
    downloaded.value = response.ready === true
    notice.value = downloaded.value ? t('standalone.updateDownloaded') : ''
  } catch (cause) {
    notice.value = ''
    failure.value = errorMessage(cause, t('standalone.updateDownloadFailed'))
  } finally {
    busy.value = false
  }
}
function install() {
  if (!downloaded.value || busy.value) return
  Modal.confirm({
    title: t('standalone.updateInstallTitle'),
    content: t(
      isAndroidLocal ? 'standalone.updateAndroidInstallHint' : 'standalone.updateDesktopInstallHint'
    ),
    okText: t('standalone.updateInstall'),
    cancelText: t('standalone.cancel'),
    onOk: async () => {
      busy.value = true
      failure.value = ''
      try {
        if (isAndroidLocal) {
          const response = await androidCall('update.install')
          notice.value = t(
            response.permissionRequired
              ? 'standalone.updatePermissionHint'
              : 'standalone.updateInstallerOpened'
          )
        } else {
          const response = await window.bmatDesktop!.installUpdate()
          notice.value = t(
            response.restarting ? 'standalone.updateRestarting' : 'standalone.updateFolderOpened'
          )
        }
      } catch (cause) {
        failure.value = errorMessage(cause, t('standalone.updateInstallFailed'))
      } finally {
        busy.value = false
      }
    },
  })
}
</script>

<template>
  <section class="software-update">
    <h2>{{ t('standalone.softwareUpdate') }}</h2>
    <p>{{ t('standalone.updateCurrent', { version: currentVersion }) }}</p>
    <a-form-item :label="t('standalone.updateChannel')">
      <a-select
        v-model:value="channel"
        :options="channels"
        :disabled="busy"
        class="update-channel"
        @change="resetResult"
      />
    </a-form-item>
    <p class="update-hint">{{ t('standalone.updateSourceHint') }}</p>
    <a-space wrap>
      <a-button :loading="busy && !result" :disabled="busy" @click="check">{{
        t('standalone.updateCheck')
      }}</a-button>
      <a-button
        v-if="result?.available && canInstall && !downloaded"
        type="primary"
        :loading="busy"
        @click="download"
        >{{ t('standalone.updateDownload') }}</a-button
      >
      <a-button v-if="downloaded" type="primary" :loading="busy" @click="install">{{
        t('standalone.updateInstall')
      }}</a-button>
      <a
        v-if="result?.releaseUrl"
        :href="result.releaseUrl"
        target="_blank"
        rel="noopener noreferrer"
        >{{ t('standalone.updateReleasePage') }}</a
      >
    </a-space>
    <a-alert v-if="failure" type="error" show-icon :message="failure" />
    <a-alert v-if="notice" type="info" show-icon :message="notice" />
    <a-alert
      v-if="result"
      :type="result.available ? 'info' : 'success'"
      show-icon
      :message="
        result.available
          ? t('standalone.updateAvailable', { version: result.latestVersion })
          : t('standalone.updateUpToDate')
      "
    />
    <p v-if="result?.available && !canInstall">{{ t('standalone.updateBrowserHint') }}</p>
    <pre v-if="result?.notes" class="update-notes">{{ result.notes }}</pre>
  </section>
</template>

<style scoped>
.software-update {
  max-width: 760px;
  padding: 8px 0;
}
.software-update h2 {
  font-size: 18px;
  margin: 0 0 12px;
}
.update-channel {
  max-width: 240px;
}
.update-hint {
  color: var(--ant-color-text-secondary);
}
.software-update .ant-alert {
  margin-top: 16px;
}
.update-notes {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font: inherit;
  line-height: 1.8;
  padding: 24px;
  background: var(--ant-color-bg-elevated);
  border-radius: 20px;
  margin-top: 20px;
}
</style>
