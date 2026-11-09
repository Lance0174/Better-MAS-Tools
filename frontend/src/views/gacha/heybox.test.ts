import { describe, expect, it } from 'vitest'
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
} from './heybox'


describe('小黑盒补录的输入校验', () => {
  it('小黑盒 ID 只接受 4-12 位数字', () => {
    expect(heyboxIdValid('1234')).toBe(true)
    expect(heyboxIdValid(' 123456789012 ')).toBe(true)
    expect(heyboxIdValid('123')).toBe(false)
    expect(heyboxIdValid('1234567890123')).toBe(false)
    expect(heyboxIdValid('12a4')).toBe(false)
    expect(heyboxIdValid('')).toBe(false)
  })

  it('响应文本长度与后端 GachaHeyboxIn 的口径一致', () => {
    expect(heyboxPayloadReady('')).toBe(false)
    expect(heyboxPayloadReady('   ')).toBe(false)
    expect(heyboxPayloadReady('{}')).toBe(true)
    expect(heyboxPayloadTooLarge('x'.repeat(HEYBOX_PAYLOAD_LIMIT))).toBe(false)
    expect(heyboxPayloadTooLarge('x'.repeat(HEYBOX_PAYLOAD_LIMIT + 1))).toBe(true)
    expect(heyboxPayloadReady('x'.repeat(HEYBOX_PAYLOAD_LIMIT + 1))).toBe(false)
  })

  it('页面地址用校验过的 ID 拼接', () => {
    expect(heyboxPageUrl(' 1234 ')).toBe(
      'https://www.xiaoheihe.cn/game/endfield/card_statistic?user_id=1234'
    )
  })
})

describe('按游戏给出可用来源', () => {
  it('小黑盒补录只在终末地出现', () => {
    expect(sourceOptions('endfield')).toEqual(['skland', 'link', 'file', 'heybox'])
    expect(sourceOptions('starrail')).toEqual(['cookie', 'link', 'file'])
    expect(sourceOptions('arknights')).toEqual(['skland', 'file'])
    for (const game of ['genshin', 'starrail', 'zzz', 'wuthering', 'arknights']) {
      expect(sourceOptions(game)).not.toContain('heybox')
    }
  })

  it('米家三游戏多一个「米游社 Cookie」来源', () => {
    for (const game of ['genshin', 'starrail', 'zzz']) {
      expect(sourceOptions(game)).toContain('cookie')
    }
    for (const game of ['wuthering', 'arknights', 'endfield']) {
      expect(sourceOptions(game)).not.toContain('cookie')
    }
  })

  it('默认来源一定在可用来源里', () => {
    for (const game of ['genshin', 'starrail', 'zzz', 'wuthering', 'arknights', 'endfield']) {
      expect(sourceOptions(game)).toContain(defaultSource(game))
    }
    expect(defaultSource('endfield')).toBe('skland')
    for (const game of ['genshin', 'starrail', 'zzz']) {
      expect(defaultSource(game)).toBe('cookie')
    }
    expect(defaultSource('arknights')).toBe('skland')
  })
})

describe('记录行的来源标记', () => {
  it('只把 heybox: 前缀认作派生行', () => {
    expect(isHeyboxDerived('heybox:1234:special:3')).toBe(true)
    expect(isHeyboxDerived('1234567890_1_2')).toBe(false)
  })

  it('四星占位按 kind 识别', () => {
    expect(isHeyboxFill('heybox_fill')).toBe(true)
    expect(isHeyboxFill('heybox')).toBe(false)
    expect(isHeyboxFill()).toBe(false)
  })
})

describe('米游社 Cookie 的输入校验', () => {
  it('Cookie 或已绑定账号二选一即可', () => {
    expect(cookieReady('', '')).toBe(false)
    expect(cookieReady('   ', '')).toBe(false)
    expect(cookieReady('ltuid=1; ltoken=abc', '')).toBe(true)
    expect(cookieReady('', '5c1f0f7e-9f4b-4f2f-8d8a-1d2c3b4a5e6f')).toBe(true)
  })

  it('与后端 GachaCookieFetchIn 的 16000 上限一致', () => {
    expect(cookieReady('x'.repeat(COOKIE_LIMIT), '')).toBe(true)
    expect(cookieReady('x'.repeat(COOKIE_LIMIT + 1), '')).toBe(false)
  })

  it('只对米家三游戏开放', () => {
    expect(isCookieGame('genshin')).toBe(true)
    expect(isCookieGame('starrail')).toBe(true)
    expect(isCookieGame('zzz')).toBe(true)
    expect(isCookieGame('wuthering')).toBe(false)
    expect(isCookieGame('endfield')).toBe(false)
  })
})
