"""SRA 公开活动源：多游戏活动日历的取数客户端（仅 httpx 与标准库）。

数据来源与许可
--------------
* 接口：https://starrailassistant.top/api/v1/activity/{game}.json
  （StarRailAssistant，https://starrailassistant.top），来源与说明见 NOTICE.md。
  它的数据由该项目定期抓取维护，本项目只读取公开 JSON，不做二次分发；取不到时
  由调用方降级到本机缓存或本地解包数据，不影响其它功能。
* 上游时间戳不带时区标记（实测 `2026-10-05T12:00:00`），实际为北京时间；前端按
  浏览器本地时区解析会整体偏移，因此统一在这里补上 `+08:00`。

字段实测（2026-10-16，各游戏均为 HTTP 200）
------------------------------------------
* 顶层除 `activities` 外还有 `version`、`versionName`、`cover`、`startTime`、
  `endTime`（当前版本的时间窗与主视觉），一并解析出来交给调用方。
* 条目字段为 `name` / `description` / `startTime` / `endTime` / `cover`，另有
  `kind`，但 **kind 各游戏不一致**：`end` 是中文分类（限时活动、签到活动……）、
  `ak` 混用英文枚举与中文（SideStory、矢志突破）、`ww` 干脆没有该字段。所以这里
  只做「有则原样透传、无则留空」，调用方不得用它做逻辑分支或当作必填字段。
* `banner`（cover）缺失是常态，不是异常：实测 end 14 条缺 5、ak 5 条缺 3、
  sr 15 条缺 5、zzz 12 条缺 7、ww 12 条缺 1、nte 9 条缺 3、xtlr 5 条全缺，
  只有 ys 8 条齐全。前端必须自己准备占位图。
* 各游戏条数（2026-10-16）：end 14、sr 15、ys 8、zzz 12、ww 12、nte 9、ak 5、
  xtlr 5。

本模块只做平台协议与纯转换：不发通知、不落盘、不抛异常，取不到数据一律返回
`None`，由 services 层决定走缓存还是降级。
"""

from __future__ import annotations

import httpx

from app.services.network import network
from app.utils.logger import get_logger

__all__ = [
    "ACTIVITY_BASE",
    "BEIJING_OFFSET",
    "REQUEST_TIMEOUT",
    "USER_AGENT",
    "beijing_time",
    "fetch_activities",
    "normalize",
]

logger = get_logger("活动日历")

# 对方是静态站，正常几百毫秒就回来了；超时给宽一点，别让接口那头干等。
REQUEST_TIMEOUT = 15.0
# 与仓库其它社区请求一致：只认本进程的代理设置，不读环境代理变量。
USER_AGENT = "Better-MAS-Tools/1.0 (independent community toolkit; activity calendar)"
ACTIVITY_BASE = "https://starrailassistant.top/api/v1/activity"
BEIJING_OFFSET = "+08:00"


def beijing_time(value: object) -> str:
    """把 SRA 的 ``2026-09-29T16:00:00`` 补成带 ``+08:00`` 的 ISO 串。

    已经带时区标记（``Z`` 或偏移量）的原样返回；取不到值返回空串。SRA 的时间是
    不带时区标记的北京时间，前端按本地时区解析会整体偏移，所以在这里补齐。
    """
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not text:
        return ""
    body = text[10:]
    if text.endswith("Z") or "+" in body or "-" in body:
        return text
    if "T" not in text:
        # 只有日期时直接拼 +08:00 会得到 ``2026-09-29+08:00`` 这种非法串。
        return f"{text}T00:00:00{BEIJING_OFFSET}"
    return f"{text}{BEIJING_OFFSET}"


def normalize(payload: object) -> dict | None:
    """SRA 响应 -> 供上层消费的字典；结构不对时返回 ``None``。

    返回 ``{"activities": [...], "version": ...}``：条目统一为 name / kind /
    description / startTime / endTime / cover，时间为补过时区的 ISO 串。
    """
    if not isinstance(payload, dict):
        return None
    items = payload.get("activities")
    if not isinstance(items, list):
        return None
    activities = [
        {
            "name": str(item.get("name") or "").strip(),
            # kind 各游戏不一致（中文 / 英文枚举 / 缺失），只透传，不做分支。
            "kind": str(item.get("kind") or "").strip(),
            "description": str(item.get("description") or "").strip(),
            "startTime": beijing_time(item.get("startTime")),
            "endTime": beijing_time(item.get("endTime")),
            "cover": str(item.get("cover") or ""),
        }
        for item in items
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    return {
        "activities": activities,
        "version": str(payload.get("version") or "").strip(),
        "versionName": str(payload.get("versionName") or "").strip(),
        "cover": str(payload.get("cover") or ""),
        "startTime": beijing_time(payload.get("startTime")),
        "endTime": beijing_time(payload.get("endTime")),
    }


async def fetch_activities(
    game: str, transport: httpx.AsyncBaseTransport | None = None
) -> dict | None:
    """取回某个游戏在 SRA 上的活动列表。

    Args:
        game: SRA 的游戏标识（``end`` 终末地、``ak`` 明日方舟、``ys`` 原神、
            ``sr`` 星穹铁道、``zzz`` 绝区零、``ww`` 鸣潮、``nte`` 异环、
            ``xtlr`` 星塔旅人）。
        transport: 测试注入的假传输层；生产路径不传，走本进程的社区请求设置。

    Returns:
        :func:`normalize` 的结果；超时、非 2xx、JSON 解析失败或结构不对时返回
        ``None``（只记一条警告日志，不上抛），由调用方决定降级方式。
    """
    options: dict = {
        "trust_env": False,
        "headers": {"User-Agent": USER_AGENT, "Accept": "application/json"},
        "timeout": REQUEST_TIMEOUT,
        "follow_redirects": True,
    }
    if transport is not None:
        options["transport"] = transport  # 测试注入；生产路径不传。
    url = f"{ACTIVITY_BASE}/{game}.json"
    try:
        async with network.client(**options) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception as error:  # 上游是附带信息：静默降级，只留一条日志
        logger.warning(f"取 SRA 活动数据失败（{game}）：{type(error).__name__}")
        return None
    normalized = normalize(payload)
    if normalized is None:
        logger.warning(f"SRA 活动数据格式不正确（{game}）：{type(payload).__name__}")
    return normalized
