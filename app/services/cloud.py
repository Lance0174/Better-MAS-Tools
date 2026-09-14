"""本地→云端签到同步：打包账号 token 上传，云端执行后取回结果。

只在本机云端模式下调用。token 经 HTTPS 发送到用户配置的云端后端，
云端不持久化；本地保存的是云端返回的签到结果，不保存云端明文凭据。
"""

from urllib.parse import urlsplit

from app.services.network import network
from app.utils.logger import get_logger

logger = get_logger("云端同步")


def validate_cloud_url(value: str) -> str:
    """校验云端后端地址：HTTPS，无路径/查询/凭据。"""
    url = urlsplit(value)
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
    ):
        raise ValueError("云端地址必须是 http/https 根地址，不含路径或参数")
    return value.rstrip("/")


async def sync_sign(
    *,
    base_url: str,
    password: str,
    accounts: list[dict[str, object]],
    miyoushe_bbs: bool,
) -> list[dict[str, object]]:
    """把账号 token 上传云端执行签到，返回结果列表。

    Args:
        base_url: 云端后端地址（用户配置）。
        password: 云端访问密码；先换取会话再执行，避免明文密码进请求体。
        accounts: 本地账号 [{uid, name, enabled, tokens}]。
        miyoushe_bbs: 是否执行米游币任务。

    Returns:
        云端返回的签到结果列表（status/reward/reason/signedAt 等）。
    """
    base = validate_cloud_url(base_url)
    if not password:
        raise ValueError("请先在设置中填写云端访问密码")

    async with network.client(
        proxy=None, trust_env=False, timeout=60, follow_redirects=False
    ) as client:
        # 先用密码换会话密钥（与远端登录一致）；程序调用不带 Origin，避免被云端来源校验拒绝。
        session_resp = await client.post(
            base + "/api/session",
            json={"password": password},
        )
        session_resp.raise_for_status()
        session = session_resp.json()
        if not isinstance(session, dict) or not session.get("key"):
            raise ValueError("云端登录失败，请检查访问密码与地址")
        headers = {"x-community-session": str(session["key"])}

        # 上传账号并执行签到。
        resp = await client.post(
            base + "/api/cloud/sync",
            json={
                "accounts": [
                    {
                        "uid": item["uid"],
                        "name": item.get("name", ""),
                        "enabled": item.get("enabled", True),
                        "tokens": item.get("tokens", {}),
                    }
                    for item in accounts
                ],
                "miyoushe_bbs": miyoushe_bbs,
            },
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or data.get("code") not in (200, None):
            message = data.get("message", "云端签到未完成") if isinstance(data, dict) else "云端响应无效"
            raise ValueError(message)
        results = data.get("data") or []
        if not isinstance(results, list):
            raise ValueError("云端返回结果格式无效")
        return [dict(item) for item in results if isinstance(item, dict)]
