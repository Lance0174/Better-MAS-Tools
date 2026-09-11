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
  Switch,
  Tabs,
  Tag,
  Tooltip,
} from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import App from './App.vue'
import { i18n } from './i18n'
import { router } from './router'
import './style.css'

const app = createApp(App).use(createPinia()).use(i18n).use(router)
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
  Switch,
  Tabs,
  Tag,
  Tooltip,
]) {
  app.use(component)
}
app.mount('#app')
