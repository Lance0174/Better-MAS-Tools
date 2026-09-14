import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  Alert,
  Button,
  Card,
  Collapse,
  ConfigProvider,
  Divider,
  Drawer,
  Empty,
  Form,
  Input,
  Layout,
  Menu,
  Modal,
  Progress,
  Select,
  Space,
  Spin,
  Steps,
  Switch,
  Tabs,
  Tag,
  Tooltip,
} from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import { i18n } from './i18n'
import { router } from './router'
import { getLogger } from './utils/logger'
import { installAndroidAdapter } from './services/android'
import './style.css'

installAndroidAdapter()
const app = createApp(App).use(createPinia()).use(i18n).use(router)
const logger = getLogger('界面异常')
const describeError = (error: unknown) =>
  error instanceof Error ? error.stack || error.message : `异常类型：${typeof error}`
app.config.errorHandler = (error, _instance, info) =>
  logger.error(`${info}\n${describeError(error)}`)
window.addEventListener('error', event =>
  logger.error(
    event.error
      ? describeError(event.error)
      : `${event.message}\n${event.filename}:${event.lineno}:${event.colno}`
  )
)
window.addEventListener('unhandledrejection', event => logger.error(describeError(event.reason)))
for (const component of [
  Alert,
  Button,
  Card,
  Collapse,
  ConfigProvider,
  Divider,
  Drawer,
  Empty,
  Form,
  Input,
  Layout,
  Menu,
  Modal,
  Progress,
  Select,
  Space,
  Spin,
  Steps,
  Switch,
  Tabs,
  Tag,
  Tooltip,
]) {
  app.use(component)
}
app.mount('#app')
