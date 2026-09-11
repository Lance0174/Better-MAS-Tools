// 验证 SDK 在独立 iframe 中运行，桥接仅传递本次挑战及验证结果。
const config = JSON.parse(decodeURIComponent(location.hash.slice(1)))
const status = document.getElementById('status')
let failed = false
let instance
function notify(data) {
  parent.postMessage(
    { kind: 'community-captcha', nonce: config.nonce, ...data },
    config.parentOrigin
  )
}
function fail() {
  if (failed) return
  failed = true
  clearTimeout(loadTimer)
  status.textContent = '验证服务加载失败，请点击重试。'
  notify({ error: true })
}
const loadTimer = setTimeout(fail, 20000)
window.addEventListener('pagehide', () => {
  clearTimeout(loadTimer)
  instance?.destroy()
})
const script = document.createElement('script')
script.src =
  config.version === 4
    ? 'https://static.geetest.com/v4/gt4.js'
    : 'https://static.geetest.com/static/tools/gt.js'
script.onerror = fail
script.onload = () => {
  if (failed) return
  const initialize = config.version === 4 ? window.initGeetest4 : window.initGeetest
  if (typeof initialize !== 'function') return script.onerror()
  const options =
    config.version === 4
      ? { captchaId: config.captchaId, product: 'bind', language: 'zho', protocol: 'https://' }
      : {
          gt: config.gt,
          challenge: config.challenge,
          new_captcha: true,
          offline: false,
          product: 'embed',
          lang: 'zh-cn',
          https: true,
          width: '100%',
        }
  try {
    initialize(options, captcha => {
      if (failed) {
        captcha.destroy()
        return
      }
      instance = captcha
      captcha.onReady(() => {
        if (failed) return
        clearTimeout(loadTimer)
        status.textContent = '请完成下方验证'
        notify({ ready: true })
        if (config.version === 4) captcha.showCaptcha()
      })
      captcha.onSuccess(() => {
        const solution = captcha.getValidate()
        if (!failed && solution) notify({ solution })
      })
      captcha.onError(() => script.onerror())
      if (config.version === 4) captcha.onClose(fail)
      else captcha.appendTo('#captcha')
    })
  } catch {
    fail()
  }
}
document.head.append(script)
