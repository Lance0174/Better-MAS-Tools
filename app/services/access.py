"""单用户远端访问设置和限时会话；仅从部署进程取得访问密码。"""

import asyncio
import hashlib
import hmac
import ipaddress
import os
import secrets
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# 同一来源在窗口内的失败上限；超过就拒绝该来源，保持原有防爆破强度。
PER_SOURCE_FAILURE_LIMIT = 5
FAILURE_WINDOW_SECONDS = 300.0
# 全局失败达到阈值后只延迟响应，不再整体拒绝：反代/Workers 下所有请求同源，
# 硬性全局锁会让一个匿名来源的 5 次错密码把全部合法用户锁在门外。
GLOBAL_BACKOFF_THRESHOLD = 10
MAX_BACKOFF_SECONDS = 2.0
MAX_TRACKED_SOURCES = 4096


def _is_private_host(peer: str) -> bool:
    """判断来源是否为环回/内网地址；只有这种来源才可能带可信转发头。"""

    try:
        address = ipaddress.ip_address(peer.strip("[]"))
    except ValueError:
        return False
    return address.is_loopback or address.is_private


def resolve_peer(peer: str, headers: Mapping[str, str]) -> str:
    """从转发链还原真实来源，避免按"隧道 IP"聚合导致互相封禁。

    仅在直连来源是本机/内网（cloudflared、nginx 反代）时才信任转发头；
    公网直连时使用连接来源，防止伪造 ``CF-Connecting-IP`` 绕过限流。
    """

    if not _is_private_host(peer):
        return peer
    for name in ("cf-connecting-ip", "x-forwarded-for"):
        raw = headers.get(name) or ""
        candidate = raw.split(",")[0].strip()
        if candidate:
            return candidate
    return peer


@dataclass(frozen=True)
class RemoteAccess:
    origin: str
    password: str = field(repr=False)

    def __post_init__(self):
        url = urlsplit(self.origin)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.path not in {"", "/"}
            or url.query
            or url.fragment
            or url.username
            or url.password
        ):
            raise ValueError(
                "远端模式需要 HTTPS 的 COMMUNITY_PUBLIC_ORIGIN（不含路径）；请在项目根目录 .env 或系统环境变量中配置"
            )
        if len(self.password) < 12:
            raise ValueError(
                "远端模式需要至少 12 字符的 COMMUNITY_ACCESS_PASSWORD；请在项目根目录 .env 或系统环境变量中配置"
            )

    @classmethod
    def from_environment(cls):
        if os.environ.get("COMMUNITY_REMOTE") != "1":
            return None
        return cls(
            os.environ.get("COMMUNITY_PUBLIC_ORIGIN", "").rstrip("/"),
            os.environ.get("COMMUNITY_ACCESS_PASSWORD", ""),
        )


class RemoteSessions:
    def __init__(self, access: RemoteAccess):
        self.access = access
        self.sessions: dict[str, float] = {}
        self.failures: dict[str, list[float]] = {}

    def _recent_failures(self, now: float) -> list[float]:
        """清理窗口外的失败记录，并返回窗口内全部来源的失败时间戳。"""

        window_start = now - FAILURE_WINDOW_SECONDS
        self.failures = {
            key: stamps
            for key, stamps in (
                (key, [stamp for stamp in values if stamp > window_start])
                for key, values in self.failures.items()
            )
            if stamps
        }
        if len(self.failures) > MAX_TRACKED_SOURCES:
            # 只保留最近登记的来源，避免字典无限增长；限流强度由每来源上限与
            # 全局退避共同保证，清掉旧键不会放宽。
            self.failures = dict(list(self.failures.items())[-MAX_TRACKED_SOURCES // 4 :])
        return [stamp for values in self.failures.values() for stamp in values]

    async def login(
        self,
        password: str,
        peer: str,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> str:
        now = time.time()
        recent = self._recent_failures(now)
        attempts = self.failures.get(peer, [])
        if len(attempts) >= PER_SOURCE_FAILURE_LIMIT:
            raise ValueError("登录尝试过多，请 5 分钟后重试")
        if not hmac.compare_digest(password.encode(), self.access.password.encode()):
            self.failures[peer] = attempts + [now]
            failures = len(recent) + 1
            if failures > GLOBAL_BACKOFF_THRESHOLD:
                # 全局退避只延迟响应：让暴力破解变慢，但不把合法用户一起锁死。
                delay = min(
                    MAX_BACKOFF_SECONDS,
                    0.25 * 2 ** (failures - GLOBAL_BACKOFF_THRESHOLD),
                )
                await sleep(delay)
            raise ValueError("访问密码不正确")
        self.failures.pop(peer, None)
        self.sessions = {
            key: expiry for key, expiry in self.sessions.items() if expiry > now
        }
        if len(self.sessions) >= 32:
            self.sessions.pop(next(iter(self.sessions)))
        key = secrets.token_urlsafe(32)
        self.sessions[hashlib_key(key)] = now + 12 * 3600
        return key

    def valid(self, key: str) -> bool:
        return self.sessions.get(hashlib_key(key), 0) > time.time()


def hashlib_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
