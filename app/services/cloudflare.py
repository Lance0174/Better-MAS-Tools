"""Workers Fetch 与 Durable Object SQLite 适配；不依赖临时文件或线程。"""

import asyncio
import base64
import re
import secrets
import zlib

import httpx
from Crypto.Cipher import AES

from app.models.config import SavedState


class DurableWikiStorage:
    """Durable Object SQLite 中的资料库与日历 JSON 存储。"""

    MAX_BYTES = 8_000_000
    PATH_PATTERN = re.compile(r"wiki/(?:index|state|arknights|calendar-[a-z0-9_-]+)\.json\Z")

    def __init__(self, storage):
        self.storage = storage
        self.storage.sql.exec(
            "CREATE TABLE IF NOT EXISTS community_wiki "
            "(path TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )

    @staticmethod
    def _validate(path: str) -> str:
        if (
            not isinstance(path, str)
            or not DurableWikiStorage.PATH_PATTERN.fullmatch(path)
            or len(path) > 160
        ):
            raise ValueError("资料库缓存路径无效")
        return path

    async def read(self, name: str) -> str | None:
        path = self._validate(name)
        row = self.storage.sql.exec(
            "SELECT payload FROM community_wiki WHERE path = ?", path
        ).one()
        if row is None:
            return None
        payload = str(row["payload"])
        if len(payload.encode("utf-8")) > self.MAX_BYTES:
            raise ValueError("资料库缓存超过8MB")
        return payload

    async def write(self, name: str, text: str) -> None:
        path = self._validate(name)
        if len(text.encode("utf-8")) > self.MAX_BYTES:
            raise ValueError("资料库缓存超过8MB")
        self.storage.sql.exec(
            "INSERT INTO community_wiki (path, payload) VALUES (?, ?) "
            "ON CONFLICT (path) DO UPDATE SET payload = excluded.payload",
            path,
            text,
        )
        await self.storage.sync()


class FetchTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        from workers import fetch

        if request.url.scheme != "https":
            raise httpx.UnsupportedProtocol(
                "Workers 上游请求必须使用 HTTPS", request=request
            )
        options = {
            "method": request.method,
            "headers": list(request.headers.multi_items()),
            "redirect": "manual",
        }
        body = await request.aread()
        if body:
            options["body"] = body
        try:
            timeout = request.extensions.get("timeout", {}).get("read") or 30
            async with asyncio.timeout(timeout):
                response = await fetch(str(request.url), **options)
                content = await response.bytes()
            headers = [
                (key, value)
                for key, value in response.headers.items()
                if key.lower() not in {"content-encoding", "content-length"}
            ]
            return httpx.Response(
                response.status, headers=headers, content=content, request=request
            )
        except TimeoutError:
            raise httpx.ReadTimeout("上游响应超时", request=request) from None
        except httpx.HTTPError:
            raise
        except Exception:
            raise httpx.ConnectError("上游连接未完成", request=request) from None


class DurableStorage:
    """整份状态压缩加密后分块，单个 SQLite 事务替换，失败保留上一版。"""

    def __init__(self, storage, encoded_key: str):
        self.storage = storage
        self.key = base64.b64decode(encoded_key, validate=True)
        if len(self.key) != 32:
            raise ValueError("COMMUNITY_ENCRYPTION_KEY 必须为32字节随机密钥的 Base64")
        self.storage.sql.exec(
            "CREATE TABLE IF NOT EXISTS community_state (part INTEGER PRIMARY KEY, payload TEXT NOT NULL)"
        )

    def load(self) -> SavedState:
        chunks = list(
            self.storage.sql.exec("SELECT payload FROM community_state ORDER BY part")
        )
        if not chunks:
            return SavedState()
        try:
            raw = base64.b64decode(
                "".join(row["payload"] for row in chunks), validate=True
            )
            cipher = AES.new(self.key, AES.MODE_GCM, nonce=raw[:12])
            cipher.update(b"BMASC-worker-state-v1")
            compressed = cipher.decrypt_and_verify(raw[28:], raw[12:28])
            return SavedState.model_validate_json(zlib.decompress(compressed))
        except Exception:
            raise RuntimeError("云端数据无法解密，请检查原密钥；原数据已保留") from None

    async def save_async(self, state: SavedState) -> None:
        plain = state.model_dump_json().encode("utf-8")
        if len(plain) > 8_000_000:
            raise ValueError("纯 Workers 状态超过8MB，请导出记录并改用 Linux 完整后端")
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=secrets.token_bytes(12))
        cipher.update(b"BMASC-worker-state-v1")
        data, tag = cipher.encrypt_and_digest(zlib.compress(plain))
        encoded = base64.b64encode(cipher.nonce + tag + data).decode("ascii")

        def replace():
            self.storage.sql.exec("DELETE FROM community_state")
            for index, offset in enumerate(range(0, len(encoded), 64_000)):
                self.storage.sql.exec(
                    "INSERT INTO community_state VALUES (?, ?)",
                    index,
                    encoded[offset : offset + 64_000],
                )

        self.storage.transactionSync(replace)
        await self.storage.sync()
