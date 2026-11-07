"""明日方舟活动与寻访卡池：游戏表拉取、缓存与日历行转换。

移植自 Priestess-bot 的 plugins/game_calendar/arknights.py（MIT License，
Copyright (c) 2026 Billtranscend）。来源与许可见 NOTICE.md。

数据来源与许可
--------------
* 游戏表：https://github.com/yuanyan3060/ArknightsGameResource
  （activity_table.json 提供活动，gacha_table.json 提供卡池）。该上游按 AGPL-3.0
  发布，因此本项目只在运行时下载，不把任何数据快照提交进仓库；缓存写在 BMT 的
  本机数据目录，随用户删除本机数据而消失。
* PRTS Wiki（https://prts.wiki/api.php）为 CC BY-NC-SA 4.0。上游用它补齐游戏表
  尚未更新的活动横幅（Semantic MediaWiki 的 ask 查询）。本项目当前只采用游戏表
  单一来源，见 PRTS_ENABLED；未接入 PRTS 的双源合并、横幅补齐与卡池配对。
  接入时必须让 wiki 失败静默降级，不影响主流程。
* 表里的时间是 unix 秒。

游戏表要等客户端更新后才会有活动，通常在开启当天；因此索引最多每 MAX_AGE 重建
一次，且始终以表里的内容为准。

本模块只做平台协议与纯转换：缓存文件路径由调用方给定，是否重建由调用方决定。
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.network import network
from app.tools.akedata_client import AkedataError
from app.utils.atomic_io import atomic_write_text
from app.utils.constants import UTC8

__all__ = [
    "GAME_ACTIVITIES_KEY",
    "KEEP_ENDED",
    "MAX_AGE",
    "PRTS_ENABLED",
    "build",
    "load",
    "refresh",
    "to_calendar_rows",
    "version_due",
]

RAW = "https://raw.githubusercontent.com/yuanyan3060/ArknightsGameResource"
VERSION_URL = f"{RAW}/refs/heads/main/version"
ACTIVITY_URL = f"{RAW}/main/gamedata/excel/activity_table.json"
GACHA_URL = f"{RAW}/main/gamedata/excel/gacha_table.json"
WIKI_API = "https://prts.wiki/api.php"  # 预留：接入 PRTS 的 ask 查询时使用，当前未调用
# 游戏表要等客户端更新，PRTS 在活动公布时就有；索引最多每 12 小时重建一次。
MAX_AGE = 12 * 3600
KEEP_ENDED = 30 * 86400  # 已结束更久的活动不再保留
PERMANENT = 180 * 86400  # 超过这个时长的池子（归航寻访……）不算限时
GENERIC_POOL_NAME = "适合多种场合的强力干员"
USER_AGENT = "Better-MAS-Tools/1.0 (independent community toolkit; activity calendar)"
GAME_ACTIVITIES_KEY = "game_activities"
# PRTS 的 SMW 查询尚未接入 refresh：上游还有 parse_wiki / parse_wiki_pools /
# apply_banners / pool_images / merge 五个函数用于双源合并，本项目保留游戏表单一
# 来源，未移植这些函数（接入前它们是死代码）。
PRTS_ENABLED = False
# 活动类型前缀 -> 分类标签。
KINDS = (
    ("CHECKIN", "签到"),
    ("LOGIN", "签到"),
    ("BLESS", "签到"),
    ("PRAY", "签到"),
    ("UNIQUE", "签到"),
    ("MINISTORY", "故事集"),
    ("TYPE_MAINSS", "主线"),
    ("TYPE_ACT", "活动"),
    ("VEC_BREAK", "矢量突破"),
    ("BOSS_RUSH", "引航者"),
    ("AUTOCHESS", "卫戍协议"),
    ("ENEMY_DUEL", "争锋频道"),
    ("MULTIPLAY", "多人"),
    ("ROGUE", "集成战略"),
    ("SANDBOX", "生息演算"),
    ("SWITCH", "合作"),
)
# 池子 id 前缀 -> 池子分类；都不匹配的跳过（新手与回归池）。
POOL_KINDS = (
    ("FESCLASSIC", "中坚甄选"),
    ("CLASSIC", "中坚寻访"),
    ("LIMITED", "限定寻访"),
    ("LINKAGE", "联动寻访"),
    ("SPECIAL", "定向甄选"),
    ("DOUBLE", "标准寻访"),
    ("SINGLE", "标准寻访"),
    ("NORM", "标准寻访"),
)


def _kind(activity_type: str, replicate: bool) -> str:
    label = next((label for prefix, label in KINDS if activity_type.startswith(prefix)), "")
    return f"{label}·复刻" if replicate and label == "活动" else label


def build(
    activity_table: dict,
    gacha_table: dict,
    pool_details: dict | None,
    names: dict[str, str],
    now: float,
) -> tuple[list[dict], list[dict]]:
    """从游戏表取出（活动, 卡池）：正在进行的、即将开始的，以及刚结束的。

    pool_details 是 PRTS 的卡池详情副本（weedy.prts.wiki/gacha_table.json），
    只有它带 UP 干员；本项目不接 PRTS，因此该参数固定为 None，卡池照常列出，只是
    没有 UP 名单。names 是干员 id -> 名字。
    """
    activities = [
        {
            "id": row["id"],
            "name": row["name"],
            "kind": _kind(row.get("type", ""), bool(row.get("isReplicate"))),
            "start": row["startTime"],
            "end": row["endTime"],
        }
        for row in (activity_table.get("basicInfo") or {}).values()
        if row.get("name")
        and row.get("startTime")
        and row.get("endTime", 0) > now - KEEP_ENDED
    ]
    up: dict[str, list[str]] = {}
    for pool in (pool_details or {}).get("gachaPoolClient") or []:
        detail = (pool.get("gachaPoolDetail") or {}).get("detailInfo") or {}
        groups = (detail.get("upCharInfo") or {}).get("perCharList") or []
        six = [
            names.get(char_id, "")
            for group in groups
            if group.get("rarityRank") == 5
            for char_id in group.get("charIdList") or []
        ]
        up[pool.get("gachaPoolId")] = [name for name in six if name]
    pools = []
    for row in gacha_table.get("gachaPoolClient") or []:
        kind = next(
            (
                label
                for prefix, label in POOL_KINDS
                if str(row.get("gachaPoolId", "")).startswith(prefix)
            ),
            "",
        )
        start, end = row.get("openTime") or 0, row.get("endTime") or 0
        if not kind or not start or end <= now - KEEP_ENDED or end - start > PERMANENT:
            continue
        name = row.get("gachaPoolName") or ""
        pools.append(
            {
                "id": row["gachaPoolId"],
                "name": kind if not name or name == GENERIC_POOL_NAME else name,
                "kind": kind,
                "up": up.get(row["gachaPoolId"], []),
                "start": start,
                "end": end,
            }
        )
    return (
        sorted(activities, key=lambda a: a["start"]),
        sorted(pools, key=lambda p: p["start"]),
    )


def load(cache_file: Path) -> dict:
    """读取本机缓存；文件缺失或损坏时按空索引处理（下次 refresh 会重建）。"""
    try:
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def version_due(cached: dict, version: str, now: float) -> bool:
    """版本变化、缓存结构缺失，或距上次重建已超过 MAX_AGE 时为真。"""
    return (
        cached.get("version") != version
        or GAME_ACTIVITIES_KEY not in cached
        or "pools" not in cached
        or now - cached.get("fetched", 0) >= MAX_AGE
    )


def write_cache(cache_file: Path, payload: dict) -> None:
    """原子替换写盘：先写 .tmp 再 replace，失败时原文件保持可用。"""
    atomic_write_text(cache_file, json.dumps(payload, ensure_ascii=False))


async def _fetch_json(client, url: str) -> Any:
    endpoint = url.split("?", 1)[0]
    try:
        response = await client.get(url)
        response.raise_for_status()
    except Exception as error:  # httpx.HTTPError 及其子类；不回显上游响应体
        raise AkedataError(f"数据源请求失败（{endpoint}）：{type(error).__name__}") from None
    try:
        return response.json()
    except ValueError:
        raise AkedataError(f"数据源返回的不是有效 JSON（{endpoint}）") from None


async def refresh(cache_file: Path) -> str:
    """把缓存更新到最新；无变化时返回"已是最新"。

    只用游戏表这一来源；PRTS 的 SMW 查询见模块文档，尚未接入。
    """
    cached = load(cache_file)
    now = time.time()
    async with network.client(
        trust_env=False,
        headers={"User-Agent": USER_AGENT},
        timeout=90.0,
        follow_redirects=True,
    ) as client:
        try:
            response = await client.get(VERSION_URL)
            response.raise_for_status()
        except Exception as error:
            raise AkedataError(f"版本文件请求失败：{type(error).__name__}") from None
        version = response.text.strip()
        if not version:
            raise AkedataError("版本文件为空")
        if not version_due(cached, version, now):
            return "已是最新"
        activity_table = await _fetch_json(client, ACTIVITY_URL)
        gacha_table = await _fetch_json(client, GACHA_URL)
    activities, pools = build(activity_table, gacha_table, None, {}, now)
    payload = {
        **cached,
        "version": version,
        "fetched": now,
        GAME_ACTIVITIES_KEY: activities,
        "pools": pools,
    }
    # 日历读的是合并后的 activities；未接 PRTS 时它等于游戏表的活动。
    payload["activities"] = activities
    payload.setdefault("pool_images", {})
    write_cache(cache_file, payload)
    return f"已同步 {version}（活动 {len(activities)}，卡池 {len(pools)}）"


def _epoch(seconds: Any) -> int | None:
    """缓存里的 unix 秒 -> int；缺失或非正数时返回 None。"""
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _moment(seconds: Any) -> str:
    """unix 秒 -> 北京时间 ISO 8601；取不到时返回空字符串。"""
    value = _epoch(seconds)
    if value is None:
        return ""
    # 必须按 UTC+8 时区换算，而不是把 +8 小时叠加到本机时间上：
    # 后者在 UTC+8 主机上等于补了两次时区，活动起止时间会整体偏移 8 小时。
    return datetime.fromtimestamp(value, tz=UTC8).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def _status(start: int | None, end: int | None, now: float) -> str:
    """日历行状态：与 services 层用同一套文案，前端可原样展示。"""
    if start is None:
        return ""
    if start > now:
        return "即将开始"
    if end is None:
        return "常驻"
    return "进行中" if now < end else "已结束"


def to_calendar_rows(index: dict, now: float | None = None) -> list[dict]:
    """缓存索引 -> /api/wiki/calendar 的行（契约字段，camelCase）。

    前端只做通用渲染，所以这里把活动与卡池合并成一个按开始时间排序的列表；UP 名单
    并入 subtitle，没有截止时间的行按常驻处理。
    """
    moment = time.time() if now is None else now
    images = index.get("pool_images") or {}
    rows = []
    for activity in index.get("activities") or []:
        start, end = _epoch(activity.get("start")), _epoch(activity.get("end"))
        rows.append(
            {
                "game": "arknights",
                "kind": "activity",
                "title": activity.get("name", ""),
                "subtitle": activity.get("kind", ""),
                "startsAt": _moment(start),
                "endsAt": _moment(end),
                "banner": activity.get("image", ""),
                "status": _status(start, end, moment),
            }
        )
    for pool in index.get("pools") or []:
        start, end = _epoch(pool.get("start")), _epoch(pool.get("end"))
        up = pool.get("up") or []
        rows.append(
            {
                "game": "arknights",
                "kind": "gacha",
                "title": pool.get("name", ""),
                "subtitle": f'UP：{"、".join(up)}' if up else pool.get("kind", ""),
                "startsAt": _moment(start),
                "endsAt": _moment(end),
                "banner": images.get(pool.get("id", ""), ""),
                "status": _status(start, end, moment),
            }
        )
    return sorted(rows, key=lambda row: row["startsAt"])
