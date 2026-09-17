"""单用户远端访问设置和限时会话；仅从部署进程取得访问密码。"""

import hmac
import os
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit


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

    def login(self, password: str, peer: str) -> str:
        now = time.time()
        self.failures = {
            key: [stamp for stamp in values if stamp > now - 300]
            for key, values in self.failures.items()
            if any(stamp > now - 300 for stamp in values)
        }
        attempts = self.failures.get(peer, [])
        if len(attempts) >= 5 or len(self.failures) > 1024:
            raise ValueError("登录尝试过多，请 5 分钟后重试")
        if not hmac.compare_digest(password.encode(), self.access.password.encode()):
            self.failures[peer] = attempts + [now]
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
    import hashlib

    return hashlib.sha256(value.encode()).hexdigest()
