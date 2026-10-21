"""Android 本地网络与存储适配；凭据只交给应用私有存储。"""

import asyncio
import base64
import json
import secrets
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import httpx

from app.models.config import SavedState

NativeCall = Callable[[str, str], Awaitable[str]]


class AndroidStorage:
    """Android Keystore 加密写入完成后，编排层才发布新状态。"""

    def __init__(self, call: NativeCall):
        self.call = call

    async def load(self) -> SavedState:
        response = json.loads(await self.call("state.read", "{}"))
        value = response.get("state")
        if value is None:
            return SavedState()
        try:
            return SavedState.model_validate_json(value)
        except Exception:
            raise RuntimeError("手机配置读取失败，原数据已保留") from None

    async def save_async(self, state: SavedState) -> None:
        value = state.model_dump_json()
        if len(value.encode("utf-8")) > 16_000_000:
            raise ValueError("手机存储超过16MB，请先导出并整理抽卡记录")
        response = json.loads(
            await self.call("state.write", json.dumps({"state": value}))
        )
        if response.get("saved") is not True:
            raise OSError("手机配置未保存，请重试；原数据已保留")


class AndroidWikiStorage:
    """通过原生应用私有文件目录保存资料库 JSON。"""

    def __init__(self, call: NativeCall):
        self.call = call

    async def read(self, name: str) -> str | None:
        response = json.loads(
            await self.call("wiki.read", json.dumps({"path": name}))
        )
        value = response.get("content")
        return value if isinstance(value, str) else None

    async def write(self, name: str, text: str) -> None:
        response = json.loads(
            await self.call(
                "wiki.write", json.dumps({"path": name, "content": text})
            )
        )
        if response.get("saved") is not True:
            raise OSError("手机资料库缓存未保存")


class AndroidTransport(httpx.AsyncBaseTransport):
    """由原生 HTTPS 执行平台请求，保留协议层的响应和取消语义。"""

    def __init__(self, call: NativeCall):
        self.call = call

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.scheme != "https":
            raise httpx.UnsupportedProtocol(
                "手机平台请求必须使用 HTTPS", request=request
            )
        request_id = secrets.token_hex(12)
        timeout = request.extensions.get("timeout", {}).get("read") or 30
        payload = {
            "id": request_id,
            "url": str(request.url),
            "method": request.method,
            "headers": list(request.headers.multi_items()),
            "body": base64.b64encode(await request.aread()).decode("ascii"),
            "timeoutMs": min(int(timeout * 1000), 60_000),
        }
        cloud_host = self._cloud_host(request)
        if cloud_host:
            # 原生层只代发平台白名单主机；用户显式配置的云端后端按本次请求声明放行，
            # 不写进原生静态状态，因此伪造一次请求也拿不到"永久可用的任意主机"。
            payload["allowHosts"] = [cloud_host]
        try:
            async with asyncio.timeout(timeout):
                response = json.loads(
                    await self.call("http.request", json.dumps(payload))
                )
            if response.get("error"):
                if response.get("error") == "timeout":
                    raise httpx.ReadTimeout("平台请求超时", request=request)
                raise httpx.ConnectError("平台连接未完成", request=request)
            return httpx.Response(
                response["status"],
                headers=response["headers"],
                content=base64.b64decode(response["body"], validate=True),
                request=request,
            )
        except (TimeoutError, asyncio.CancelledError) as error:
            try:
                async with asyncio.timeout(2):
                    await self.call("http.cancel", json.dumps({"id": request_id}))
            except Exception:
                pass  # 清理失败不覆盖调用者的超时或取消原因。
            if isinstance(error, asyncio.CancelledError):
                raise
            raise httpx.ReadTimeout("平台请求超时", request=request) from None
        except httpx.HTTPError:
            raise
        except Exception:
            raise httpx.ConnectError("手机网络请求未完成", request=request) from None

    @staticmethod
    def _cloud_host(request: httpx.Request) -> str:
        """本次请求若发往设置里的云端后端，返回该主机名；否则返回空串。

        取值只来自 state.data.settings.CloudBaseUrl，且沿用保存时的
        app.services.cloud.validate_cloud_url 校验（https、无路径/参数/凭据）；
        这里只比较主机名，不做自己的地址策略判断。云端同步（app/services/cloud.py）
        与转发层（app/core/relay.py:64,77-85）用的是同一个 CloudBaseUrl，因此同一套放行通用。
        """
        try:
            # 延迟导入：services 不反向依赖 core，也避免模块级循环导入。
            from app.core.state import state
            from app.services.cloud import validate_cloud_url

            base = validate_cloud_url(state.data.settings.CloudBaseUrl or "")
        except Exception:
            # 未配置、配置非法或状态尚未加载时，本次请求不声明任何主机。
            return ""
        host = (urlsplit(base).hostname or "").lower()
        if not host or request.url.host.lower() != host:
            return ""
        return host
