"""本机 AUTO-MAS 的有限接口连接；不读取其文件、凭据或运行日志。"""

import asyncio
from urllib.parse import urlsplit

from app.services.network import network


def validate_base_url(value: str) -> str:
    url = urlsplit(value)
    if (
        url.scheme not in {"http", "https"}
        or url.hostname not in {"127.0.0.1", "localhost", "::1"}
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
    ):
        raise ValueError("MAS 地址必须是服务所在电脑的 localhost 或环回 IP 地址")
    if url.port is not None and not 1 <= url.port <= 65535:
        raise ValueError("MAS 端口无效")
    return value.rstrip("/")


async def request(base_url: str, path: str, *, payload: dict | None = None) -> dict:
    if not network.local_connections:
        raise ValueError("纯 Cloudflare 版无法连接本机 MAS，请使用桌面版或 Linux 后端")
    base = validate_base_url(base_url)
    async with network.client(
        trust_env=False, timeout=15, follow_redirects=False
    ) as client:
        response = await client.request(
            "POST" if payload is not None else "GET", base + path, json=payload
        )
        response.raise_for_status()
        result = response.json()
    if not isinstance(result, dict) or result.get("code", 200) != 200:
        # 原 MAS 的异常可能携带内部数据，不直接转发其原文。
        raise ValueError("MAS 未完成该操作，请在 MAS 中查看任务状态")
    return result


async def snapshot(base_url: str) -> dict:
    queues, running = await asyncio.gather(
        request(base_url, "/api/queue/get", payload={}),
        request(base_url, "/api/dispatch/runtime-snapshot"),
    )
    queue_data = queues.get("data", {})
    return {
        "baseUrl": validate_base_url(base_url),
        "queues": [
            {
                "id": str(item["uid"]),
                "name": str(
                    (queue_data.get(item["uid"], {}).get("Info") or {}).get("Name")
                    or item["uid"]
                ),
            }
            for item in queues.get("index", [])
        ],
        "tasks": [
            {
                "id": str(item["taskId"]),
                "mode": str(item.get("mode", "")),
                "stopping": bool(item.get("stopping")),
            }
            for item in running.get("tasks", [])
        ],
    }
