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
@pytest.mark.parametrize("host", ["zonai.skland.com", "as.hypergryph.com", "fp-it.portal101.cn"])
async def test_connect_failure_retries_with_resolved_ip(host: str) -> None:
    primary = FakeTransport(fail=_connect_error())
    fallback = FakeTransport()
    transport = CommunityHTTPTransport(resolver=_resolver([("93.184.216.34", 120.0)]))
    transport._transport = primary
    transport._transport_factory = lambda: fallback

    response = await transport.handle_async_request(_request(host=host))

    assert response.status_code == 200
    assert len(primary.requests) == 1
    retried = fallback.requests[0]
    # 请求发到 IP，但 Host 头与 TLS SNI 仍是原域名，证书照原域名校验。
    assert retried.url.host == "93.184.216.34"
    assert retried.headers["host"] == host
    assert retried.extensions["sni_hostname"] == host
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
@pytest.mark.parametrize("proxy", [
    "http://10.0.0.1:7890", "http://127.0.0.1:7890",
    "http://localhost:7890", "http://[::1]:7890",
])
async def test_explicit_proxy_never_changes_egress(monkeypatch, proxy: str) -> None:
    async def resolver(_host: str):
        raise AssertionError("远端代理可能就是唯一出口，不能绕开它直连")

    monkeypatch.setattr(community_dns, "local_addresses", _no_dns)
    transport = CommunityHTTPTransport(proxy=proxy, resolver=resolver)
    transport._transport = FakeTransport(fail=_connect_error())
    fallback = FakeTransport()
    transport._transport_factory = lambda: fallback

    with pytest.raises(httpx.ConnectError) as error:
        await transport.handle_async_request(_request())
    assert "代理" in str(error.value)
    assert fallback.requests == []


@pytest.mark.asyncio
async def test_resolver_without_addresses_does_not_retry() -> None:
    fallback = FakeTransport()
    transport = CommunityHTTPTransport(resolver=_resolver([]))
    transport._transport = FakeTransport(fail=_connect_error())
    transport._transport_factory = lambda: fallback

    with pytest.raises(httpx.ConnectError):
        await transport.handle_async_request(_request())
    assert fallback.requests == []


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




def _dns_response(*addresses: tuple[str, int]) -> bytes:
    """拼一条 DNS 应答：问题段回显域名，答案段全是 A 记录。"""

    import struct

    question = b"\x05zonai\x06skland\x03com\x00" + struct.pack("!HH", 1, 1)
    answers = b"".join(
        b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, ttl, 4) + bytes(map(int, ip.split(".")))
        for ip, ttl in addresses
    )
    header = struct.pack("!HHHHHH", 0x1234, 0x8180, 1, len(addresses), 0, 0)
    return header + question + answers


def test_udp_query_carries_random_id_and_fqdn() -> None:
    query = community_dns._build_dns_query("zonai.skland.com")

    assert len(query[:2]) == 2
    # 域名按标签编码，末尾补 0，再接 QTYPE=A / QCLASS=IN。
    assert query[12:-4] == b"\x05zonai\x06skland\x03com\x00"
    assert query[-4:] == b"\x00\x01\x00\x01"


def test_udp_answers_keep_only_public_ipv4() -> None:
    payload = _dns_response(("8.153.80.203", 30), ("10.1.2.3", 300), ("79.26.1.2", 900))
    addresses = community_dns._parse_dns_answers(payload)

    # TTL 同样夹到 60-300；内网地址丢弃；顺序按应答顺序，最多两条。
    assert addresses == [("8.153.80.203", 60.0), ("79.26.1.2", 300.0)]
    assert community_dns._parse_dns_answers(b"") == []


@pytest.mark.parametrize("flags", [0x0100, 0x8380, 0x8183, 0x8980])
def test_udp_rejects_queries_truncated_errors_and_nonstandard_replies(flags: int) -> None:
    payload = bytearray(_dns_response(("8.153.80.203", 60)))
    payload[2:4] = flags.to_bytes(2, "big")
    assert community_dns._parse_dns_answers(bytes(payload)) == []


@pytest.mark.parametrize("missing", [1, 2, 3, 6, 12])
def test_udp_truncated_answer_does_not_crash_qr_creation(missing: int) -> None:
    payload = _dns_response(("8.153.80.203", 60))[:-missing]
    assert community_dns._parse_dns_answers(payload) == []


@pytest.mark.asyncio
async def test_resolve_direct_prefers_doh(monkeypatch) -> None:
    calls: list[str] = []

    async def doh(host: str):
        calls.append("doh")
        return [("8.153.80.203", 120.0)]

    async def udp(host: str):
        calls.append("udp")
        return []

    monkeypatch.setattr(community_dns, "resolve_over_https", doh)
    monkeypatch.setattr(community_dns, "resolve_via_udp", udp)

    assert await community_dns.resolve_direct("zonai.skland.com") == [
        ("8.153.80.203", 120.0)
    ]
    assert calls == ["doh"]


@pytest.mark.asyncio
async def test_resolve_direct_falls_back_to_plain_dns(monkeypatch) -> None:
    async def doh(_host: str):
        return []

    async def udp(host: str):
        assert host == "zonai.skland.com"
        return [("79.26.1.2", 60.0)]

    monkeypatch.setattr(community_dns, "resolve_over_https", doh)
    monkeypatch.setattr(community_dns, "resolve_via_udp", udp)

    # TUN 连 DoH 的 443 一起接管时，加密 DNS 会返回空；这条明文路径是最后的退路。
    assert await community_dns.resolve_direct("zonai.skland.com") == [("79.26.1.2", 60.0)]


def test_transport_factory_still_wins_for_cloudflare_build() -> None:
    local = network.CommunityNetwork(transport_factory=FakeTransport)
    client = local.client()
    assert isinstance(client._transport, FakeTransport)
    with pytest.raises(ValueError):
        local.client(proxy="http://127.0.0.1:7890")
