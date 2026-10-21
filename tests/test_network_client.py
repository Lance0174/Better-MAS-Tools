"""上游请求客户端的统一网络设置：代理只来自本进程配置。"""

import pytest

from app.services.network import network


@pytest.mark.asyncio
async def test_client_ignores_environment_proxies(monkeypatch):
    # 系统里存在 HTTP_PROXY 时，带 Token 的社区请求不能被送到第三方代理。
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    async with network.client() as client:
        assert client._trust_env is False


@pytest.mark.asyncio
async def test_client_still_honours_explicit_trust_env(monkeypatch):
    async with network.client(trust_env=True) as client:
        assert client._trust_env is True
