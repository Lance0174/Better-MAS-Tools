"""整份配置加密、原子写入；不会读取 AUTO-MAS 的配置目录。"""

import asyncio
import base64
import json
import os
import secrets
from pathlib import Path
from sys import platform as storage_platform
from tempfile import NamedTemporaryFile
from typing import Protocol

from Crypto.Cipher import AES

from app.models.config import SavedState
from app.utils.secrets import dpapi_decrypt, dpapi_encrypt


class StateStore(Protocol):
    async def save_async(self, state: SavedState) -> None: ...


class StateStorage:
    def __init__(self, directory: Path):
        self.path = directory / "state.json"
        self.format: str | None = None

    def _key(self, *, create: bool) -> bytes:
        supplied = os.environ.get("COMMUNITY_ENCRYPTION_KEY")
        if supplied:
            key = base64.b64decode(supplied, validate=True)
        else:
            path = self.path.parent / "master.key"
            if create and not path.exists():
                path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                try:
                    descriptor = os.open(
                        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                    )
                except FileExistsError:
                    pass
                else:
                    with os.fdopen(descriptor, "wb") as file:
                        file.write(secrets.token_bytes(32))
                        file.flush()
                        os.fsync(file.fileno())
            if os.name != "nt" and path.stat().st_mode & 0o077:
                raise RuntimeError("加密密钥权限必须为 0600")
            key = path.read_bytes()
        if len(key) != 32:
            raise RuntimeError("加密密钥必须为 32 字节")
        return key

    def _encrypt(self, value: str) -> dict[str, str]:
        if (
            storage_platform == "win32"
            and self.format != "aesgcm-v1"
            and not os.environ.get("COMMUNITY_ENCRYPTION_KEY")
        ):
            return {"format": "dpapi-v1", "data": dpapi_encrypt(value)}
        cipher = AES.new(
            self._key(create=True), AES.MODE_GCM, nonce=secrets.token_bytes(12)
        )
        cipher.update(b"BMASC-state-v1")
        encrypted, tag = cipher.encrypt_and_digest(value.encode("utf-8"))
        return {
            "format": "aesgcm-v1",
            "data": base64.b64encode(cipher.nonce + tag + encrypted).decode("ascii"),
        }

    def load(self) -> SavedState:
        if not self.path.exists():
            return SavedState()
        try:
            envelope = json.loads(self.path.read_text(encoding="utf-8"))
            if envelope.get("format") == "dpapi-v1":
                plaintext = dpapi_decrypt(envelope["data"])
            elif envelope.get("format") == "aesgcm-v1":
                raw = base64.b64decode(envelope["data"], validate=True)
                cipher = AES.new(self._key(create=False), AES.MODE_GCM, nonce=raw[:12])
                cipher.update(b"BMASC-state-v1")
                plaintext = cipher.decrypt_and_verify(raw[28:], raw[12:28]).decode(
                    "utf-8"
                )
            else:
                raise ValueError("不支持的配置格式")
            data = SavedState.model_validate_json(plaintext)
            self.format = envelope["format"]
            return data
        except Exception:
            # 损坏或其他 Windows 用户的密文不能静默重置，以免覆盖唯一凭据。
            raise RuntimeError(
                "配置无法读取或解密，请检查原 Windows 用户或 Linux 加密密钥；原文件已保留"
            ) from None

    def save(self, state: SavedState) -> None:
        envelope = self._encrypt(state.model_dump_json())
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix="state-",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary = Path(file.name)
                json.dump(envelope, file, ensure_ascii=False)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    async def save_async(self, state: SavedState) -> None:
        await asyncio.to_thread(self.save, state)
