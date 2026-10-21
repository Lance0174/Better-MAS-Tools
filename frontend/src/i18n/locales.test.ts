import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import standalone from './locales/standalone'
import zhCN from './locales/zh-CN'

/**
 * 词表守卫：页面里有大量运行时拼出来的 key（例如设置页的 t(`standalone.${value}`)），
 * 拼错或漏键时 vue-i18n 只会把裸 key 渲染到界面上，测试与类型检查都发现不了。
 * 因此在 node 环境直接读源码，把「源码里出现的 key」与「词表里存在的 key」对齐。
 */
const SOURCE_ROOT = fileURLToPath(new URL('../', import.meta.url))
const SOURCE_EXTENSIONS = ['.ts', '.vue']
// 只认引用 `t()` 时以命名空间开头的字面量，避免把 CSS 类名、路径之类的点号字符串当成 key。
const KEY_LITERAL = /['"`]([A-Za-z]\w*(?:\.\w+)+)['"`]/g
// 模板拼接只校验到最后一个静态段：t(`standalone.gachaGames.${value}`) → standalone.gachaGames。
const KEY_TEMPLATE_PREFIX = /`([A-Za-z]\w*(?:\.\w+)*)\.\$\{/g

type Messages = Record<string, unknown>

/** 把嵌套词表摊平成点号路径，对象路径（命名空间）与叶子路径都保留。 */
function flatten(messages: Messages, prefix = ''): string[] {
  return Object.entries(messages).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (!value || typeof value !== 'object' || Array.isArray(value)) return [path]
    return [path, ...flatten(value as Messages, path)]
  })
}

function collectSourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return collectSourceFiles(path)
    return SOURCE_EXTENSIONS.some(extension => entry.name.endsWith(extension)) ? [path] : []
  })
}

/** 收集一个源文件里出现的所有候选 key，返回相对 src 的路径便于定位。 */
function collectReferencedKeys(source: string, namespaces: Set<string>): string[] {
  const keys = new Set<string>()
  const add = (candidate: string) => {
    const [namespace] = candidate.split('.')
    if (namespaces.has(namespace)) keys.add(candidate)
  }
  for (const match of source.matchAll(KEY_LITERAL)) add(match[1])
  for (const match of source.matchAll(KEY_TEMPLATE_PREFIX)) add(match[1])
  return [...keys]
}

/** 顶层键若本身是对象，它就是一个可以被运行时拼接的命名空间。 */
function namespacesOf(messages: Messages): Set<string> {
  const namespaces = new Set<string>()
  for (const [key, value] of Object.entries(messages)) {
    if (value && typeof value === 'object' && !Array.isArray(value)) namespaces.add(key)
  }
  return namespaces
}

describe('i18n 词表', () => {
  // 与 i18n/index.ts 的挂载方式保持一致：standalone 整体挂在 standalone 命名空间下，
  // onboarding 另在顶层暴露一份给引导组件直接取用。
  const messages: Messages = { standalone, onboarding: standalone.onboarding, ...zhCN }
  const known = new Set(flatten(messages))
  const namespaces = namespacesOf(messages)

  it('源码里引用的 key 都能在 standalone.ts 或 zh-CN.ts 里找到', () => {
    const missing: string[] = []
    let referenced = 0
    for (const file of collectSourceFiles(SOURCE_ROOT)) {
      const source = readFileSync(file, 'utf8')
      const keys = collectReferencedKeys(source, namespaces)
      referenced += keys.length
      for (const key of keys) {
        if (!known.has(key)) missing.push(`${file.slice(SOURCE_ROOT.length)} → ${key}`)
      }
    }
    // 扫描器失效时这个用例会退化成空断言，因此先确认它确实读到了大量 key。
    expect(referenced).toBeGreaterThan(200)
    expect(missing.sort(), `这些 key 在词表里不存在：\n${missing.sort().join('\n')}`).toEqual([])
  })

  it('外观下拉使用的主题取值都有对应文案', () => {
    // light/dark/system 与 settings 页的 t(`standalone.${value}`) 必须一一对应。
    for (const theme of ['light', 'dark', 'system']) {
      expect(known.has(`standalone.${theme}`), `缺少 standalone.${theme}`).toBe(true)
    }
  })
})
