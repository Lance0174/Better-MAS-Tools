import { describe, expect, it } from 'vitest'
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
    expect(sourceOptions('endfield')).toEqual(['link', 'file', 'heybox'])
    expect(sourceOptions('starrail')).toEqual(['link', 'file'])
    expect(sourceOptions('arknights')).toEqual(['skland', 'file'])
    for (const game of ['genshin', 'starrail', 'zzz', 'wuthering', 'arknights']) {
      expect(sourceOptions(game)).not.toContain('heybox')
    }
  })

  it('账号授权只向明日方舟开放', () => {
    for (const game of ['genshin', 'starrail', 'zzz', 'wuthering', 'endfield']) {
      expect(sourceOptions(game)).not.toContain('skland')
      expect(sourceOptions(game)).not.toContain('cookie')
      expect(sourceOptions(game)).toContain('link')
      expect(sourceOptions(game)).toContain('file')
    }
  })

  it('默认来源一定在可用来源里', () => {
    for (const game of ['genshin', 'starrail', 'zzz', 'wuthering', 'arknights', 'endfield']) {
      expect(sourceOptions(game)).toContain(defaultSource(game))
    }
    expect(defaultSource('endfield')).toBe('link')
    for (const game of ['genshin', 'starrail', 'zzz']) {
      expect(defaultSource(game)).toBe('link')
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
