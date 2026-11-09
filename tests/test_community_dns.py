"""社区加密 DNS 回退的离线用例：所有连接都由假 transport 顶替，不联网。"""

import httpx
import pytest

from app.services import community_dns, network
from app.services.community_dns import CommunityHTTPTransport


class FakeTransport(httpx.AsyncBaseTransport):
    """记录收到的请求；按需要抛出连接错误或直接返回响应。"""

    def __init__(self, *, fail: Exception | None = None, status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.closed = 0
        self._fail = fail
        self._status = status

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._fail is not None:
            raise self._fail
        return httpx.Response(self._status, json={"ok": True}, request=request)

    async def aclose(self) -> None:
        self.closed += 1


def _request(host: str = "zonai.skland.com", scheme: str = "https") -> httpx.Request:
    url = f"{scheme}://{host}/web/v1/user/auth/generate_cred_by_code"
    return httpx.Request("POST", url, json={"code": "x"})


def _connect_error() -> httpx.ConnectError:
    return httpx.ConnectError("", request=_request())


def _resolver(values: list[tuple[str, float]]) -> community_dns.Resolver:
    async def resolve(_host: str) -> list[tuple[str, float]]:
        return values

    return resolve


async def _no_dns(_host: str) -> list[str]:
    return []


def test_extract_addresses_keeps_only_public_ipv4_and_clamps_ttl() -> None:
    answer = [
        {"type": 1, "data": "93.184.216.34", "TTL": 5},
        {"type": 1, "data": "10.0.0.1", "TTL": 60},
        {"type": 1, "data": "not-an-ip", "TTL": 60},
        {"type": 28, "data": "2606:2800:220:1::1", "TTL": 60},
        {"type": 1, "data": "93.184.216.35", "TTL": 900},
        {"type": 1, "data": "93.184.216.36", "TTL": 120},
    ]
    # 内网地址会指向本机或局域网服务，必须丢弃；TTL 夹到 60-300 秒；最多取两条。
    assert community_dns._extract_addresses(answer) == [
        ("93.184.216.34", 60.0),
        ("93.184.216.35", 300.0),
    ]
    assert community_dns._extract_addresses(None) == []


@pytest.mark.asyncio
async def test_connect_failure_retries_with_resolved_ip() -> None:
    primary = FakeTransport(fail=_connect_error())
    fallback = FakeTransport()
    transport = CommunityHTTPTransport(resolver=_resolver([("93.184.216.34", 120.0)]))
    transport._transport = primary
    transport._transport_factory = lambda: fallback

    response = await transport.handle_async_request(_request())

    assert response.status_code == 200
    assert len(primary.requests) == 1
    retried = fallback.requests[0]
    # 请求发到 IP，但 Host 头与 TLS SNI 仍是原域名，证书照原域名校验。
    assert retried.url.host == "93.184.216.34"
    assert retried.headers["host"] == "zonai.skland.com"
    assert retried.extensions["sni_hostname"] == "zonai.skland.com"
    assert retried.content == _request().content


@pytest.mark.asyncio
async def test_success_does_not_touch_the_resolver() -> None:
    async def resolver(_host: str):
        raise AssertionError("直连成功时不应回退解析")

    transport = CommunityHTTPTransport(resolver=resolver)
    transport._transport = FakeTransport()
    transport._transport_factory = lambda: FakeTransport()

    response = await transport.handle_async_request(_request())
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_explicit_proxy_skips_fallback(monkeypatch) -> None:
    async def resolver(_host: str):
        raise AssertionError("走代理时不应用加密 DNS 绕过代理")

    monkeypatch.setattr(community_dns, "local_addresses", _no_dns)
    transport = CommunityHTTPTransport(proxy="http://127.0.0.1:7890", resolver=resolver)
    transport._transport = FakeTransport(fail=_connect_error())
    transport._transport_factory = lambda: FakeTransport()

    with pytest.raises(httpx.ConnectError) as error:
        await transport.handle_async_request(_request())
    assert "代理" in str(error.value)


@pytest.mark.asyncio
async def test_plain_http_is_not_retried(monkeypatch) -> None:
    monkeypatch.setattr(community_dns, "local_addresses", _no_dns)
    fallback = FakeTransport()
    transport = CommunityHTTPTransport(resolver=_resolver([("93.184.216.34", 120.0)]))
    transport._transport = FakeTransport(fail=_connect_error())
    transport._transport_factory = lambda: fallback

    with pytest.raises(httpx.ConnectError):
        await transport.handle_async_request(_request(scheme="http"))
    assert fallback.requests == []


@pytest.mark.asyncio
async def test_resolved_address_is_cached_until_ttl() -> None:
    calls: list[str] = []

    async def resolver(host: str) -> list[tuple[str, float]]:
        calls.append(host)
        return [("93.184.216.34", 120.0)]

    primary = FakeTransport(fail=_connect_error())
    fallback = FakeTransport()
    transport = CommunityHTTPTransport(resolver=resolver)
    transport._transport = primary
    transport._transport_factory = lambda: fallback

    await transport.handle_async_request(_request())
    await transport.handle_async_request(_request())

    assert calls == ["zonai.skland.com"]
    assert len(primary.requests) == 1
    assert len(fallback.requests) == 2


@pytest.mark.asyncio
async def test_close_releases_every_transport() -> None:
    primary = FakeTransport()
    fallback = FakeTransport()
    transport = CommunityHTTPTransport(resolver=_resolver([]))
    transport._transport = primary
    transport._transport_factory = lambda: fallback
    transport._resolved_transports["zonai.skland.com"] = fallback

    await transport.aclose()

    assert primary.closed == 1
    assert fallback.closed == 1
    assert transport._resolved_transports == {}


def test_failure_message_names_the_fake_ip() -> None:
    message = community_dns.describe_failure("zonai.skland.com", ["198.18.0.170"])
    assert "198.18.0.170" in message
    assert "Fake-IP" in message
    assert "直连规则" in message

    assert "解析不到" in community_dns.describe_failure("zonai.skland.com", [])
    assert "加密 DNS" in community_dns.describe_failure("zonai.skland.com", ["8.153.80.203"])


@pytest.mark.asyncio
async def test_local_mcp_failure_never_queries_public_dns() -> None:
    async def resolver(_host: str):
        raise AssertionError("本机地址不应发送给公共 DNS")

    primary = FakeTransport(fail=_connect_error())
    async with CommunityHTTPTransport(
        resolver=resolver, transport_factory=lambda: primary
    ) as transport:
        with pytest.raises(httpx.ConnectError):
            await transport.handle_async_request(_request(host="localhost"))
    assert len(primary.requests) == 1


@pytest.mark.asyncio
async def test_read_failure_is_not_replayed() -> None:
    async def resolver(_host: str):
        raise AssertionError("已经发出的请求不得重放")

    primary = FakeTransport(fail=httpx.ReadTimeout("uncertain"))
    async with CommunityHTTPTransport(
        resolver=resolver, transport_factory=lambda: primary
    ) as transport:
        with pytest.raises(httpx.ReadTimeout):
            await transport.handle_async_request(_request())
    assert len(primary.requests) == 1


@pytest.mark.asyncio
async def test_network_client_installs_doh_transport() -> None:
    local = network.CommunityNetwork()
    client = local.client(proxy="http://127.0.0.1:7890", timeout=5.0)
    assert isinstance(client._transport, CommunityHTTPTransport)
    # httpx 0.28 见到 transport 就忽略 proxy 参数，代理必须并进 transport 里。
    assert client._transport._uses_proxy is True
    await client.aclose()

    plain = local.client()
    assert plain._transport._uses_proxy is False
    await plain.aclose()


def test_transport_factory_still_wins_for_cloudflare_build() -> None:
    local = network.CommunityNetwork(transport_factory=FakeTransport)
    client = local.client()
    assert isinstance(client._transport, FakeTransport)
    with pytest.raises(ValueError):
        local.client(proxy="http://127.0.0.1:7890")
