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
  xtlr 5。infinitynikki（无限暖暖）为后续补充的源：2026-11-05 实测 2 条，条目带
  `kind`（如「限时联动活动」）与 cover，顶层 version 2.11 / versionName「时光缝合的扉页」。

本模块只做平台协议与纯转换：不发通知、不落盘、不抛异常，取不到数据一律返回
`None`，由 services 层决定走缓存还是降级。
"""

from __future__ import annotations

import asyncio
import time

import httpx

from app.services.network import network
from app.utils.logger import get_logger

__all__ = [
    "ACTIVITY_BASE",
    "BEIJING_OFFSET",
    "FAILURE_RETRY_SECONDS",
    "MAX_ATTEMPTS",
    "REQUEST_TIMEOUT",
    "RETRY_DELAY_SECONDS",
    "TOTAL_TIMEOUT",
    "USER_AGENT",
    "WARNING_INTERVAL_SECONDS",
    "beijing_time",
    "fetch_activities",
    "normalize",
    "reset_failure_state",
]

logger = get_logger("活动日历")

# 游戏的失败冷却与上次告警时刻（monotonic 秒）。只存进程内状态，不落盘。
_cooldown_until: dict[str, float] = {}
_warned_at: dict[str, float] = {}


def reset_failure_state() -> None:
    """清空失败冷却与告警节流记录；测试或手动刷新时使用。"""
    _cooldown_until.clear()
    _warned_at.clear()


def _retryable(error: Exception) -> bool:
    """只有网络层故障与上游临时错误值得重试；4xx 与结构错误重试也没用。"""
    if isinstance(error, (httpx.TransportError, TimeoutError)):
        return True
    return isinstance(error, httpx.HTTPStatusError) and (
        error.response.status_code in (408, 429) or error.response.status_code >= 500
    )

# 弱网下允许重试，但整批尝试共用一个总时限，别让日历接口长时间干等（上游 #1599）。
TOTAL_TIMEOUT = 15.0
# 单次请求的时限：总时限内可以重试 3 次，每次单独算超时。
REQUEST_TIMEOUT = 5.0
MAX_ATTEMPTS = 3
# 指数退避：0.5s、1s。
RETRY_DELAY_SECONDS = 0.5
# 失败后 1 分钟内不再回源：上游挂掉时避免每个请求都重试一轮。
FAILURE_RETRY_SECONDS = 60.0
# 同一游戏的失败日志每小时最多一条，避免日历页每 30 分钟刷新都刷屏。
WARNING_INTERVAL_SECONDS = 3600.0
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
        ```None``（不上抛），由调用方决定走本机缓存还是空列表。弱网时会重试
        最多 :data:`MAX_ATTEMPTS` 次（共用 :data:`TOTAL_TIMEOUT` 总时限）；失败过的
        游戏在 :data:`FAILURE_RETRY_SECONDS` 内直接返回 ``None``，不再回源。
    """
    if _cooldown_until.get(game, 0.0) > time.monotonic():
        # 冷却期内不回源：调用方会立刻落到本机缓存或空列表，日历页不会因此变慢。
        return None
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
        async with asyncio.timeout(TOTAL_TIMEOUT):
            data = await _fetch_with_retry(url, options)
    except Exception as error:  # 上游是附带信息：静默降级，只留一条日志
        _record_failure(game, error)
        return None
    _cooldown_until.pop(game, None)
    _warned_at.pop(game, None)
    return data


async def _fetch_with_retry(url: str, options: dict) -> dict:
    """按指数退避重试取数并解析；坏数据当异常处理，交给 ``fetch_activities`` 兜底。"""
    async with network.client(**options) as client:
        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await client.get(url)
                response.raise_for_status()
                break
            except httpx.HTTPError as error:
                if not _retryable(error) or attempt == MAX_ATTEMPTS - 1:
                    raise
                await asyncio.sleep(RETRY_DELAY_SECONDS * 2**attempt)
        payload = response.json()
    normalized = normalize(payload)
    if normalized is None:
        # 结构不对不会因为重试变好，直接当失败，走 60 秒冷却。
        raise ValueError(f"活动数据结构不正确：{type(payload).__name__}")
    return normalized


def _record_failure(game: str, error: Exception) -> None:
    """记冷却并按小时节流写一条日志；响应体一律不进日志。"""
    now = time.monotonic()
    _cooldown_until[game] = now + FAILURE_RETRY_SECONDS
    # 非可重试错误（结构错误、4xx）说明上游可能变了，每次都值得记；弱网失败按小时节流。
    last_warned = _warned_at.get(game)
    if _retryable(error) and last_warned is not None and now - last_warned < WARNING_INTERVAL_SECONDS:
        return
    _warned_at[game] = now
    logger.warning(f"取 SRA 活动数据失败（{game}）：{type(error).__name__}: {error}")
