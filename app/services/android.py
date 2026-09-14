"""Android 本地网络与存储适配；凭据只交给应用私有存储。"""

import asyncio
import base64
import json
import secrets
from collections.abc import Awaitable, Callable

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
