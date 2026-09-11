"""本机凭据加密边界，Windows 使用当前用户的 DPAPI。"""

import base64
import sys


def dpapi_encrypt(value: str) -> str:
    if not value:
        return ""
    if sys.platform != "win32":
        raise RuntimeError("当前版本的加密凭据存储需要 Windows")
    import win32crypt

    encrypted = win32crypt.CryptProtectData(
        value.encode("utf-8"), "Better MAS Community", None, None, None, 0
    )
    return base64.b64encode(encrypted).decode("ascii")


def dpapi_decrypt(value: str) -> str:
    if not value:
        return ""
    if sys.platform != "win32":
        raise RuntimeError("当前版本的加密凭据存储需要 Windows")
    import win32crypt

    return win32crypt.CryptUnprotectData(
        base64.b64decode(value, validate=True), None, None, None, 0
    )[1].decode("utf-8")
