"""本进程的社区请求设置，不依赖 MAS 配置或全局代理变量。"""

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

import httpx

from app.utils.logger import get_logger
from app.utils.security import sanitize_log_message

logger = get_logger("上游请求")


class DiagnosticClient(httpx.AsyncClient):
    async def request(
        self, method: str, url: httpx.URL | str, **options
    ) -> httpx.Response:
        target = httpx.URL(url)
        endpoint = f"{target.scheme}://{target.host}{target.path}"
        started = monotonic()
        logger.debug(f"开始 {method} {endpoint}")
        try:
            response = await super().request(method, url, **options)
        except Exception as error:
            elapsed = int((monotonic() - started) * 1000)
            if isinstance(error, httpx.HTTPError):
                logger.warning(
                    f"{method} {endpoint} {type(error).__name__} 耗时={elapsed}ms"
                )
            else:
                logger.exception(f"{method} {endpoint} 请求异常 耗时={elapsed}ms")
            raise
        elapsed = int((monotonic() - started) * 1000)
        detail = f"{method} {endpoint} HTTP={response.status_code} 耗时={elapsed}ms"
        failed = response.is_error
        # 只读取有限的业务状态字段，绝不输出请求头、Cookie、请求体或响应 data。
        if (
            "json" in response.headers.get("content-type", "")
            and len(response.content) <= 1_000_000
        ):
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                for key in ("retcode", "code", "status"):
                    code = payload.get(key)
                    if isinstance(code, (str, int)):
                        detail += f" {key}={sanitize_log_message(str(code))[:80]}"
                code = payload.get("retcode", payload.get("code"))
                failed |= code is not None and str(code) not in {"0", "200", "10000"}
                message = payload.get("message", payload.get("msg"))
                if failed and isinstance(message, str):
                    detail += f" 原因={sanitize_log_message(message)[:200]}"
        logger.log("WARNING" if failed else "DEBUG", detail)
        return response


@dataclass
class CommunityNetwork:
    proxy: str | None = None
    transport_factory: Callable[[], httpx.AsyncBaseTransport] | None = None
    local_connections: bool = True

    def client(self, **options) -> httpx.AsyncClient:
        if self.transport_factory is not None:
            if options.get("proxy"):
                raise ValueError("纯 Cloudflare 版不支持本机代理")
            options.setdefault("transport", self.transport_factory())
        return DiagnosticClient(**options)


network = CommunityNetwork()
