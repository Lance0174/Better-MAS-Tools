"""转发层指令存储：控制端入队、执行层长轮询领取、结果一次性回读。

抽象出 RelayStore 供两种部署形态共用：本地演练/测试用内存实现；
Cloudflare Durable Object 用独立 SQLite 表（不进 SavedState），
payload 与 result 沿用 COMMUNITY_ENCRYPTION_KEY 加密。
"""

import asyncio
import base64
import secrets
import time
import zlib
from datetime import datetime
from typing import Protocol

from Crypto.Cipher import AES

from app.utils.constants import UTC8
from app.utils.logger import get_logger

logger = get_logger("转发层")

COMMAND_TTL_SECONDS = 60
POLL_HOLD_SECONDS = 25.0
NODE_ONLINE_SECONDS = 45
RESULT_RETENTION_SECONDS = 3600
RELAY_VERSION = 1


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC8).isoformat(timespec="seconds")


class _Cipher:
    """沿用 DurableStorage 的 AES-GCM 约定；AAD 区分数据域。"""

    def __init__(self, encoded_key: str):
        self.key = base64.b64decode(encoded_key, validate=True)
        if len(self.key) != 32:
            raise ValueError("COMMUNITY_ENCRYPTION_KEY 必须为32字节随机密钥的 Base64")

    def encrypt(self, text: str) -> str:
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=secrets.token_bytes(12))
        cipher.update(b"BMASC-relay-v1")
        data, tag = cipher.encrypt_and_digest(zlib.compress(text.encode("utf-8")))
        return base64.b64encode(cipher.nonce + tag + data).decode("ascii")

    def decrypt(self, encoded: str) -> str:
        raw = base64.b64decode(encoded, validate=True)
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=raw[:12])
        cipher.update(b"BMASC-relay-v1")
        return zlib.decompress(cipher.decrypt_and_verify(raw[28:], raw[12:28])).decode(
            "utf-8"
        )


class RelayStore(Protocol):
    async def enqueue(self, command_type: str, payload: dict) -> str: ...

    async def take_wait(self, node_id: str, timeout: float) -> dict | None: ...

    async def submit_result(
        self, node_id: str, command_id: str, ok: bool, data: dict, error: str
    ) -> None: ...

    async def nodes(self) -> list[dict]: ...

    async def command_status(self, command_id: str) -> dict | None: ...


class MemoryRelayStore:
    """单进程内存实现：本地演练与单元测试用。"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._commands: dict[str, dict] = {}
        self._nodes: dict[str, float] = {}

    async def _sweep(self) -> None:
        now = time.time()
        for command_id, item in list(self._commands.items()):
            if item["status"] in {"pending", "dispatched"}:
                if now > item["expire_at"]:
                    item["status"] = "expired"
                    item["finished_at"] = now
            elif (
                item.get("finished_at") or item["expire_at"]
            ) + RESULT_RETENTION_SECONDS < now:
                del self._commands[command_id]

    async def enqueue(self, command_type: str, payload: dict) -> str:
        async with self._lock:
            await self._sweep()
            now = time.time()
            command_id = secrets.token_hex(8)
            self._commands[command_id] = {
                "type": command_type,
                "payload": payload,
                "status": "pending",
                "created_at": now,
                "expire_at": now + COMMAND_TTL_SECONDS,
                "finished_at": None,
                "result": None,
            }
            logger.info(f"指令入队 {command_type}（{command_id}）")
            return command_id

    async def take_wait(self, node_id: str, timeout: float) -> dict | None:
        deadline = time.time() + timeout
        while True:
            async with self._lock:
                await self._sweep()
                self._nodes[node_id] = time.time()
                for command_id, item in self._commands.items():
                    if item["status"] == "pending" and time.time() <= item["expire_at"]:
                        item["status"] = "dispatched"
                        logger.info(f"指令下发 {item['type']}（{command_id}）→ {node_id}")
                        return {
                            "id": command_id,
                            "type": item["type"],
                            "payload": item["payload"],
                            "createdAt": _iso(item["created_at"]),
                            "expireAt": _iso(item["expire_at"]),
                            "version": RELAY_VERSION,
                        }
            if time.time() >= deadline:
                return None
            await asyncio.sleep(1)

    async def submit_result(
        self, node_id: str, command_id: str, ok: bool, data: dict, error: str
    ) -> None:
        async with self._lock:
            await self._sweep()
            self._nodes[node_id] = time.time()
            item = self._commands.get(command_id)
            if item is None or item["status"] != "dispatched":
                logger.warning(f"结果被拒绝（{command_id}）：指令不存在或不在执行中")
                return
            item["status"] = "done" if ok else "failed"
            item["result"] = {"data": data, "error": error}
            item["finished_at"] = time.time()
            logger.info(f"结果回传（{command_id}）：{'成功' if ok else '失败'}")

    async def nodes(self) -> list[dict]:
        async with self._lock:
            await self._sweep()
            now = time.time()
            return [
                {
                    "nodeId": node_id,
                    "online": now - last_seen <= NODE_ONLINE_SECONDS,
                    "lastSeenAt": _iso(last_seen),
                }
                for node_id, last_seen in self._nodes.items()
            ]

    async def command_status(self, command_id: str) -> dict | None:
        async with self._lock:
            await self._sweep()
            item = self._commands.get(command_id)
            if item is None:
                return None
            return {
                "id": command_id,
                "type": item["type"],
                "status": item["status"],
                "result": item["result"],
            }


class DurableRelayStore:
    """Durable Object SQLite 实现；指令为短暂数据，不写入 SavedState。"""

    def __init__(self, storage, encoded_key: str):
        self.storage = storage
        self.cipher = _Cipher(encoded_key)
        self.storage.sql.exec(
            "CREATE TABLE IF NOT EXISTS relay_commands ("
            "id TEXT PRIMARY KEY, type TEXT NOT NULL, payload TEXT NOT NULL, "
            "status TEXT NOT NULL, created_at REAL NOT NULL, expire_at REAL NOT NULL, "
            "finished_at REAL, result TEXT)"
        )
        self.storage.sql.exec(
            "CREATE TABLE IF NOT EXISTS relay_nodes ("
            "node_id TEXT PRIMARY KEY, last_seen REAL NOT NULL)"
        )

    async def _sync(self) -> None:
        await self.storage.sync()

    def sweep(self) -> None:
        now = time.time()

        def expire():
            self.storage.sql.exec(
                "UPDATE relay_commands SET status = 'expired', finished_at = ? "
                "WHERE status IN ('pending', 'dispatched') AND expire_at < ?",
                now,
                now,
            )
            self.storage.sql.exec(
                "DELETE FROM relay_commands WHERE status IN ('done', 'failed') "
                "AND finished_at < ?",
                now - RESULT_RETENTION_SECONDS,
            )
            self.storage.sql.exec(
                "DELETE FROM relay_commands WHERE status = 'expired' AND finished_at < ?",
                now - RESULT_RETENTION_SECONDS,
            )

        self.storage.transactionSync(expire)

    async def enqueue(self, command_type: str, payload: dict) -> str:
        self.sweep()
        now = time.time()
        command_id = secrets.token_hex(8)
        self.storage.sql.exec(
            "INSERT INTO relay_commands VALUES (?, ?, ?, 'pending', ?, ?, NULL, NULL)",
            command_id,
            command_type,
            self.cipher.encrypt(str(payload)),
            now,
            now + COMMAND_TTL_SECONDS,
        )
        await self._sync()
        logger.info(f"指令入队 {command_type}（{command_id}）")
        return command_id

    def _take_pending(self, node_id: str) -> dict | None:
        row = self.storage.sql.exec(
            "SELECT id, type, payload, created_at, expire_at FROM relay_commands "
            "WHERE status = 'pending' AND expire_at >= ? ORDER BY created_at LIMIT 1",
            time.time(),
        ).one()
        if row is None:
            return None
        self.storage.sql.exec(
            "UPDATE relay_commands SET status = 'dispatched' WHERE id = ?", row["id"]
        )
        self.storage.sql.exec(
            "INSERT INTO relay_nodes VALUES (?, ?) "
            "ON CONFLICT (node_id) DO UPDATE SET last_seen = excluded.last_seen",
            node_id,
            time.time(),
        )
        logger.info(f"指令下发 {row['type']}（{row['id']}）→ {node_id}")
        return {
            "id": row["id"],
            "type": row["type"],
            "payload": self.cipher.decrypt(row["payload"]),
            "createdAt": _iso(row["created_at"]),
            "expireAt": _iso(row["expire_at"]),
            "version": RELAY_VERSION,
        }

    async def take_wait(self, node_id: str, timeout: float) -> dict | None:
        deadline = time.time() + timeout
        while True:
            command = self._take_pending(node_id)
            if command is not None:
                await self._sync()
                return command
            self.sweep()
            if time.time() >= deadline:
                self.storage.sql.exec(
                    "INSERT INTO relay_nodes VALUES (?, ?) "
                    "ON CONFLICT (node_id) DO UPDATE SET last_seen = excluded.last_seen",
                    node_id,
                    time.time(),
                )
                await self._sync()
                return None
            await asyncio.sleep(1)

    async def submit_result(
        self, node_id: str, command_id: str, ok: bool, data: dict, error: str
    ) -> None:
        self.sweep()
        cursor = self.storage.sql.exec(
            "UPDATE relay_commands SET status = ?, result = ?, finished_at = ? "
            "WHERE id = ? AND status = 'dispatched'",
            "done" if ok else "failed",
            self.cipher.encrypt(str({"data": data, "error": error})),
            time.time(),
            command_id,
        )
        if cursor.rowcount:
            logger.info(f"结果回传（{command_id}）：{'成功' if ok else '失败'}")
        else:
            logger.warning(f"结果被拒绝（{command_id}）：指令不存在或不在执行中")
        self.storage.sql.exec(
            "INSERT INTO relay_nodes VALUES (?, ?) "
            "ON CONFLICT (node_id) DO UPDATE SET last_seen = excluded.last_seen",
            node_id,
            time.time(),
        )
        await self._sync()

    async def nodes(self) -> list[dict]:
        self.sweep()
        now = time.time()
        rows = list(
            self.storage.sql.exec("SELECT node_id, last_seen FROM relay_nodes")
        )
        return [
            {
                "nodeId": row["node_id"],
                "online": now - row["last_seen"] <= NODE_ONLINE_SECONDS,
                "lastSeenAt": _iso(row["last_seen"]),
            }
            for row in rows
        ]

    async def command_status(self, command_id: str) -> dict | None:
        self.sweep()
        row = self.storage.sql.exec(
            "SELECT id, type, status, result FROM relay_commands WHERE id = ?",
            command_id,
        ).one()
        if row is None:
            return None
        result = None
        if row["result"] is not None:
            result = self.cipher.decrypt(row["result"])
        return {
            "id": row["id"],
            "type": row["type"],
            "status": row["status"],
            "result": result,
        }
