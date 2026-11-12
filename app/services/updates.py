"""从唯一官方仓库读取公开 Release；不携带账号或 GitHub 凭据。"""

import json

import httpx

from app.models.updates import UpdateCheckOut
from app.services.network import network
from app.tools.update_release import REPOSITORY, select_update
from app.version import VERSION


async def check_updates(*, platform: str, channel: str) -> UpdateCheckOut:
    try:
        async with network.client(proxy=network.proxy, timeout=25) as client:
            async with client.stream(
                "GET",
                f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=30",
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "Better-MAS-Tools-update",
                },
            ) as response:
                if response.status_code == 403 or response.status_code == 429:
                    raise ValueError("更新检查过于频繁，请稍后再试")
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 2_000_000:
                        raise ValueError("更新信息过大，已停止读取")
                releases = httpx.Response(200, content=bytes(content)).json()
    except httpx.HTTPError:
        raise ValueError("无法连接官方更新服务，请检查网络后重试") from None
    except (json.JSONDecodeError, TypeError, UnicodeError):
        raise ValueError("更新信息无法解析，请稍后重试") from None
    return select_update(releases, current=VERSION, platform=platform, channel=channel)
