"""本进程的社区请求设置，不依赖 MAS 配置或全局代理变量。"""

from collections.abc import Callable
from dataclasses import dataclass

import httpx


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
        return httpx.AsyncClient(**options)


network = CommunityNetwork()
