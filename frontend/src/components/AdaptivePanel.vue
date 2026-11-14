<script setup lang="ts">
import { ArrowLeftOutlined } from '@ant-design/icons-vue'
import { useMobileUi } from '@/composables/useMobileUi'
import { useBackAction } from '@/composables/useBackAction'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    width?: number
    fullMobile?: boolean
    busy?: boolean
    maskClosable?: boolean
    desktopModal?: boolean
  }>(),
  { width: 560, fullMobile: false, busy: false, maskClosable: true }
)
const emit = defineEmits<{ close: [] }>()
const mobile = useMobileUi()
const close = () => {
  if (!props.busy) emit('close')
}
useBackAction(() => props.open, close)
</script>

<template>
  <a-modal
    v-if="desktopModal && !mobile"
    :open="open"
    :title="title"
    :width="width"
    :closable="!busy"
    :mask-closable="maskClosable && !busy"
    :keyboard="!busy"
    :footer="null"
    destroy-on-close
    @cancel="close"
  >
    <slot />
    <div v-if="$slots.footer" class="panel-actions"><slot name="footer" /></div>
  </a-modal>
  <a-drawer
    v-else
    :open="open"
    :title="title"
    :width="mobile ? '100%' : width"
    :placement="mobile && !fullMobile ? 'bottom' : 'right'"
    :height="mobile && !fullMobile ? 'auto' : undefined"
    :closable="!busy"
    :mask-closable="maskClosable && !busy"
    :keyboard="!busy"
    :root-class-name="`adaptive-panel ${mobile ? 'mobile-panel' : ''} ${mobile && fullMobile ? 'mobile-panel--page' : ''}`"
    destroy-on-close
    @close="close"
  >
    <template v-if="mobile && fullMobile" #closeIcon><ArrowLeftOutlined /></template>
    <div class="panel-content"><slot /></div>
    <template v-if="$slots.footer" #footer
      ><div class="panel-actions"><slot name="footer" /></div
    ></template>
  </a-drawer>
</template>

<style>
.adaptive-panel .ant-drawer-content {
  border-radius: 24px 0 0 24px;
}
.adaptive-panel .ant-drawer-header {
  padding: 22px 24px;
  border-bottom: 0;
}
.adaptive-panel .ant-drawer-title {
  font-size: 19px;
  font-weight: 650;
}
.adaptive-panel .ant-drawer-body {
  padding: 0 24px 24px;
}
.adaptive-panel .ant-drawer-footer {
  padding: 16px 24px;
  border-color: var(--ant-color-border-secondary);
}
.panel-content {
  min-width: 0;
}
.panel-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.mobile-panel .ant-drawer-content-wrapper {
  max-height: 90dvh;
  box-shadow: none;
}
.mobile-panel .ant-drawer-content,
.mobile-panel .ant-drawer-wrapper-body {
  max-height: 90dvh;
}
.mobile-panel .ant-drawer-content {
  overflow: hidden;
  border-radius: 26px 26px 0 0;
  background: var(--ant-color-bg-container);
}
.mobile-panel .ant-drawer-header {
  padding: 25px 20px 18px;
}
.mobile-panel .ant-drawer-header::before {
  content: '';
  position: absolute;
  top: 9px;
  left: calc(50% - 18px);
  width: 36px;
  height: 4px;
  border-radius: 4px;
  background: var(--ant-color-border);
}
.mobile-panel .ant-drawer-body {
  padding: 0 20px 20px;
  overscroll-behavior: contain;
}
.mobile-panel .ant-drawer-footer {
  padding: 14px 20px calc(14px + var(--app-safe-area-bottom));
}
.mobile-panel .panel-actions > .ant-btn {
  flex: 1;
  height: 46px;
}
.mobile-panel--page .ant-drawer-content-wrapper {
  height: 100%;
  max-height: 100dvh;
  transition-duration: 180ms;
}
.mobile-panel--page .ant-drawer-content {
  border-radius: 0;
  background: var(--ant-color-bg-layout);
}
.mobile-panel--page .ant-drawer-content,
.mobile-panel--page .ant-drawer-wrapper-body {
  max-height: 100dvh;
}
.mobile-panel--page .ant-drawer-header {
  padding-top: calc(20px + var(--app-safe-area-top));
}
.mobile-panel--page .ant-drawer-header::before {
  display: none;
}
.mobile-panel--page .ant-drawer-footer {
  background: var(--ant-color-bg-layout);
}
@media (prefers-reduced-motion: reduce) {
  .adaptive-panel .ant-drawer-content-wrapper {
    transition: none !important;
  }
}
</style>
