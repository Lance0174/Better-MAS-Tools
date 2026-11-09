"""社区请求的加密 DNS 回退与连接诊断，不改系统 DNS、不接管系统代理。"""

import asyncio
import ipaddress
import socket
import time
from collections.abc import Awaitable, Callable

import httpx

from app.utils.logger import get_logger
from app.utils.security import sanitize_log_message

logger = get_logger("上游请求")

# 阿里云公共 DNS 的加密解析入口。固定写 IP：本地 DNS 被污染或处在 Fake-IP 模式时，
# 连 dns.alidns.com 这个名字本身也会解析错。
DOH_ENDPOINTS = ("https://223.5.5.5/resolve", "https://223.6.6.6/resolve")
DOH_HOST = "dns.alidns.com"
DOH_TIMEOUT_SECONDS = 3.0
CACHE_TTL_MIN_SECONDS = 60.0
CACHE_TTL_MAX_SECONDS = 300.0
MAX_FALLBACK_ADDRESSES = 2
# 只处理本次确认存在连接问题的森空岛官方域名；本机 MAS 等请求不做公网解析。
FALLBACK_HOSTS = frozenset({"zonai.skland.com", "as.hypergryph.com"})
# 连接阶段失败可以安全重放：请求一个字节都还没发出去。读写失败不能重放，
# 否则签到、扫码保存这类 POST 会被执行两次。
CONNECT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ProxyError)
# Clash、Surge 等 TUN 模式的 Fake-IP 网段，命中说明本机 DNS 返回的是代理伪造地址。
FAKE_IP_NETWORKS = (ipaddress.ip_network("198.18.0.0/15"),)

Resolver = Callable[[str], Awaitable[list[tuple[str, float]]]]


class CommunityConnectionError(httpx.ConnectError):
    """由本模块生成的安全连接说明，可展示给用户。"""


def _extract_addresses(answer: object) -> list[tuple[str, float]]:
    """从 DNS-over-HTTPS 的 Answer 里取可直连的 A 记录，返回 (地址, 剩余有效秒数)。"""

    if not isinstance(answer, list):
        return []
    addresses: list[tuple[str, float]] = []
    for record in answer:
        if not isinstance(record, dict) or record.get("type") != 1:
            continue
        try:
            address = ipaddress.ip_address(str(record.get("data") or "").strip())
        except ValueError:
            continue
        # 只认公网 IPv4：内网地址会落到本机或局域网服务上，把凭据送错地方。
        if address.version != 4 or not address.is_global:
            continue
        try:
            ttl = float(record.get("TTL") or CACHE_TTL_MIN_SECONDS)
        except (TypeError, ValueError):
            ttl = CACHE_TTL_MIN_SECONDS
        ttl = min(max(ttl, CACHE_TTL_MIN_SECONDS), CACHE_TTL_MAX_SECONDS)
        addresses.append((str(address), ttl))
    return addresses[:MAX_FALLBACK_ADDRESSES]


async def resolve_over_https(hostname: str) -> list[tuple[str, float]]:
    """用阿里云加密 DNS 解析 A 记录，失败返回空列表（回退不是必需步骤，不能抛）。"""

    async with httpx.AsyncClient(
        trust_env=False, timeout=DOH_TIMEOUT_SECONDS
    ) as client:
        for endpoint in DOH_ENDPOINTS:
            try:
                response = await client.get(
                    endpoint,
                    params={"name": hostname, "type": "A"},
                    headers={"Host": DOH_HOST, "Accept": "application/dns-json"},
                    # Host 与 TLS SNI 都写服务域名：证书仍按 dns.alidns.com 校验。
                    extensions={"sni_hostname": DOH_HOST},
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                continue
            if not isinstance(payload, dict) or payload.get("Status") != 0:
                continue
            addresses = _extract_addresses(payload.get("Answer"))
            if addresses:
                return addresses
    return []


def _looks_like_fake_ip(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(parsed in network for network in FAKE_IP_NETWORKS)


async def local_addresses(hostname: str) -> list[str]:
    """查本机 DNS 给这个域名返回了什么，仅用于失败诊断。"""

    def resolve() -> list[str]:
        try:
            infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        except OSError:
            return []
        return [str(info[4][0]) for info in infos]

    try:
        return await asyncio.wait_for(asyncio.to_thread(resolve), timeout=3.0)
    except (OSError, asyncio.TimeoutError):
        return []


def describe_failure(hostname: str, addresses: list[str]) -> str:
    """把「连不上」翻译成能照着做的提示，而不是让用户只看到 ConnectError。"""

    fake = [address for address in addresses if _looks_like_fake_ip(address)]
    if fake:
        return (
            f"本机 DNS 把 {hostname} 解析到 {fake[0]}，"
            "这是 Clash/Surge 等代理软件 TUN 模式的 Fake-IP，握手被代理接管后失败。"
            "请把该域名加入代理的直连规则，或临时关闭 TUN/增强模式后重试。"
        )
    if not addresses:
        return f"本机 DNS 解析不到 {hostname}，请检查网络或 DNS 设置后重试。"
    return (
        f"连接 {hostname}（本机解析到 {addresses[0]}）失败，"
        "加密 DNS 回退也没能建立连接；请检查代理/TUN 的规则后重试。"
    )


class CommunityHTTPTransport(httpx.AsyncBaseTransport):
    """直连失败时改用加密 DNS 解析出的 IP 重试，Host 与证书域名保持原样。"""

    def __init__(
        self,
        proxy: str | httpx.Proxy | None = None,
        *,
        resolver: Resolver | None = None,
        transport_factory: Callable[[], httpx.AsyncBaseTransport] | None = None,
    ) -> None:
        self._uses_proxy = proxy is not None
        self._resolver = resolver or resolve_over_https
        # 注入点：测试用假 transport 顶替真实连接，既不联网也不依赖 DNS。
        self._transport_factory = transport_factory or (
            lambda: httpx.AsyncHTTPTransport(proxy=proxy, trust_env=False)
        )
        self._transport = self._transport_factory()
        self._resolved: dict[str, tuple[str, float]] = {}
        self._resolved_transports: dict[str, httpx.AsyncBaseTransport] = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        hostname = request.url.host
        cached = self._resolved.get(hostname)
        try:
            if cached and time.monotonic() < cached[1]:
                return await self._send_to_address(request, cached[0])
            return await self._transport.handle_async_request(request)
        except CONNECT_ERRORS as error:
            self._resolved.pop(hostname, None)
            # 有显式代理时代理应自己解析域名，回退只会绕过代理把请求发到本机网络。
            if (
                not self._uses_proxy
                and request.url.scheme == "https"
                and hostname in FALLBACK_HOSTS
            ):
                for address, expires_in in await self._resolver(hostname):
                    try:
                        response = await self._send_to_address(request, address)
                    except CONNECT_ERRORS:
                        continue
                    self._resolved[hostname] = (address, time.monotonic() + expires_in)
                    logger.info(f"{hostname} 直连失败，已改用加密 DNS 解析的 {address}")
                    return response
            if hostname not in FALLBACK_HOSTS:
                raise
            raise await self._connect_error(request, error) from error

    async def _send_to_address(
        self, request: httpx.Request, address: str
    ) -> httpx.Response:
        hostname = request.url.host
        headers = httpx.Headers(request.headers)
        # URL 换成 IP 之后 httpcore 会用 IP 生成 Host 头，CDN 按 Host 分流会直接
        # 404，所以这里显式把 Host 改回原域名（上游只设置了 SNI，没有补 Host）。
        headers["host"] = hostname
        resolved_request = httpx.Request(
            request.method,
            request.url.copy_with(host=address),
            headers=headers,
            content=await request.aread(),
            # 证书校验仍按原域名：SNI 是原域名，不是 IP。
            extensions={**request.extensions, "sni_hostname": hostname},
        )
        # 不同域名可能解析到同一个 CDN IP；各用独立连接池，证书各验各的。
        transport = self._resolved_transports.get(hostname)
        if transport is None:
            transport = self._transport_factory()
            self._resolved_transports[hostname] = transport
        return await transport.handle_async_request(resolved_request)

    async def _connect_error(
        self, request: httpx.Request, error: Exception
    ) -> httpx.ConnectError:
        hostname = request.url.host
        if self._uses_proxy:
            reason = "社区代理连接失败，请检查设置里的代理地址与代理服务后重试"
        else:
            reason = describe_failure(hostname, await local_addresses(hostname))
        logger.warning(
            sanitize_log_message(
                f"连接 {hostname} 失败：{type(error).__name__}: {error}；{reason}"
            )
        )
        return CommunityConnectionError(reason, request=request)

    async def aclose(self) -> None:
        await self._transport.aclose()
        for transport in self._resolved_transports.values():
            await transport.aclose()
        self._resolved_transports.clear()
        self._resolved.clear()
