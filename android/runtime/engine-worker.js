// Python 和业务源码全部来自 APK 资源，网络与持久化经主 frame 转交 Android。
self.postMessage({ type: 'stage', text: '读取本地 Python 运行时' });
importScripts('/runtime/pyodide.js');

const nativeRequests = new Map();
let sequence = 0;
let engine;
let initialized;
let requestApi;
let cancelApi;
let runtime;

function nativeCall(operation, serialized) {
  const id = `worker-${++sequence}`;
  return new Promise((resolve, reject) => {
    nativeRequests.set(id, { resolve, reject });
    self.postMessage({ type: 'native', id, operation, payload: JSON.parse(serialized) });
  });
}

async function initialize(runStartup) {
  const bootStartedAt = performance.now();
  let stageStartedAt = bootStartedAt;
  const log = message => nativeCall('log.write', JSON.stringify({ message })).catch(() => {});
  // 每阶段完成时输出耗时，真机启动诊断据此归因（阶段=上一阶段起，累计=Worker 启动起）。
  const markStage = async name => {
    const now = performance.now();
    await log(
      `${name}：阶段 ${Math.round(now - stageStartedAt)} ms，累计 ${Math.round(now - bootStartedAt)} ms`,
    );
    stageStartedAt = now;
  };
  await log('引擎: 正在加载 Pyodide 运行时');
  self.postMessage({ type: 'stage', text: '启动本地 Python 引擎' });
  engine = await loadPyodide({ indexURL: '/runtime/' });
  engine.setStdout({ batched: log });
  engine.setStderr({ batched: log });
  await markStage('引擎: Pyodide 运行时已加载');
  self.postMessage({ type: 'stage', text: '加载核心运行依赖' });
  // numpy/pillow 体积大且只在本地滑块/抽卡时才 import；核心启动不等待，避免首屏 8 秒。
  await engine.loadPackage(['pydantic', 'pycryptodome', 'httpx', 'ssl']);
  const source = await fetch('/runtime/python-source.zip');
  if (!source.ok) throw new Error('Packaged Python source unavailable');
  engine.unpackArchive(await source.arrayBuffer(), 'zip', { extractDir: '/bmat' });
  engine.registerJsModule('bmat_native', { nativeCall });
  engine.globals.set('_bmat_run_startup', runStartup);
  await markStage('引擎: 核心依赖与业务源码已就绪');
  self.postMessage({ type: 'stage', text: '读取本机配置并初始化接口' });
  await engine.runPythonAsync(`
import sys
# pure wheel 内容已在 /bmat/site 下（含 dist-info），挂 sys.path 即可，免去每次启动重拷 site-packages。
sys.path.insert(0, '/bmat/site')
sys.path.insert(0, '/bmat')
from bmat_native import nativeCall
from app.core.android_runtime import AndroidRuntime
_bmat_engine = AndroidRuntime(nativeCall)
await _bmat_engine.initialize(run_startup=_bmat_run_startup)
`);
  runtime = engine.globals.get('_bmat_engine');
  requestApi = runtime.request;
  cancelApi = runtime.cancel;
  await markStage('引擎: 本机配置读取与接口初始化完成');
  // 方法代理依附于宿主代理；保留至 Worker 结束，不能在请求前销毁宿主。
  self.postMessage({ type: 'ready' });
  setInterval(() => self.postMessage({ type: 'heartbeat' }), 1000);
  // 后台补装重依赖；失败不阻断核心功能，只在用到滑块/抽卡时由 Python 侧报错。
  engine.loadPackage(['numpy', 'pillow']).catch(() => {
    void log('引擎: 可选依赖(numpy/pillow)安装失败，滑块识别不可用').catch(() => {});
  });
}

self.onmessage = event => {
  const message = event.data;
  if (message.type === 'native-result') {
    const pending = nativeRequests.get(message.id);
    if (!pending) return;
    nativeRequests.delete(message.id);
    if (message.error) pending.reject(new Error(message.error));
    else pending.resolve(JSON.stringify(message.result));
  } else if (message.type === 'boot') {
    initialized = initialize(message.runStartup);
    initialized.catch(error => {
      // 真实异常必须进入本机日志，否则手机上无法定位 Pyodide/WASM 启动失败原因。
      const detail = String(error && error.message ? error.message : error);
      void nativeCall('log.write', JSON.stringify({ message: `引擎启动失败: ${detail.slice(-16000)}` })).catch(() => {});
      // Python 异常原因通常位于调用栈末尾；界面显示原因，完整诊断交给原生日志脱敏。
      const reason = detail.trim().split('\n').pop().slice(-500);
      self.postMessage({ type: 'fatal', error: `本地服务启动失败: ${reason}` });
    });
  } else if (message.type === 'cancel') {
    if (cancelApi) cancelApi(message.id);
  } else if (message.type === 'foreground' && runtime) {
    const task = runtime.sign_on_open();
    Promise.resolve(task).catch(() => {}).finally(() => task.destroy());
  } else if (message.type === 'request') {
    (async () => {
      try {
        await initialized;
        const coroutine = requestApi(JSON.stringify(message.request));
        try {
          const response = await coroutine;
          self.postMessage({ type: 'response', id: message.id, response: JSON.parse(response) });
        } finally { coroutine.destroy(); }
      } catch {
        self.postMessage({ type: 'response', id: message.id, error: '本地请求未完成，请查看日志后重试' });
      }
    })();
  }
};
