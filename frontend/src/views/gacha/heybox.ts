/** 获取记录的来源：官方链接 / 明日方舟森空岛账号 / 文件导入 / 小黑盒补录。 */
export type FetchSource = 'link' | 'skland' | 'file' | 'heybox'

/**
 * 与 app/models/schema.py 的 GachaHeyboxIn 保持一致：
 * heyboxId 只允许 4-12 位数字，payload 上限 2 000 000 字符。
 */
export const HEYBOX_ID_PATTERN = /^[0-9]{4,12}$/
export const HEYBOX_PAYLOAD_LIMIT = 2_000_000
/** 与 app/core/gacha.py 的 is_derived 保持一致：派生行的 id 以 heybox: 开头。 */
export const HEYBOX_DERIVED_PREFIX = 'heybox:'
/** 与 app/tools/gacha_heybox.py 的 KIND_FILL 保持一致（四星占位）。 */
export const HEYBOX_FILL_KIND = 'heybox_fill'
export const HEYBOX_PAGE = 'https://www.xiaoheihe.cn/game/endfield/card_statistic?user_id='

/** Cookie／已登录账号获取仅向明日方舟开放；其余保留链接与文件，小黑盒仅终末地。 */
export const sourceOptions = (game: string): FetchSource[] => {
  const options: FetchSource[] = []
  if (game === 'arknights') options.push('skland')
  if (game !== 'arknights') options.push('link')
  options.push('file')
  if (game === 'endfield') options.push('heybox')
  return options
}

export const defaultSource = (game: string): FetchSource => sourceOptions(game)[0] ?? 'link'

export const heyboxIdValid = (value: string) => HEYBOX_ID_PATTERN.test(value.trim())

export const heyboxPayloadTooLarge = (value: string) => value.length > HEYBOX_PAYLOAD_LIMIT

/** 与后端一致的最小长度是 2（SecretStr 的 min_length）。 */
export const heyboxPayloadReady = (value: string) =>
  value.trim().length >= 2 && !heyboxPayloadTooLarge(value)

export const heyboxPageUrl = (id: string) => `${HEYBOX_PAGE}${id.trim()}`

/** 派生行：小黑盒补录出来的四星占位与五星补名，官方原始行的 id 不带前缀。 */
export const isHeyboxDerived = (id: string) => id.startsWith(HEYBOX_DERIVED_PREFIX)

/** 四星占位行：只为补齐抽数，不代表真实的四星道具。 */
export const isHeyboxFill = (kind?: string) => kind === HEYBOX_FILL_KIND
