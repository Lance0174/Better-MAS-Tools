"""多游戏活动日历：SRA 取数、本机缓存与契约行转换。

数据来源与降级顺序
------------------
* 除终末地外，各游戏都用 SRA（https://starrailassistant.top，见 NOTICE.md）作为唯一
  来源；终末地的权威数据是本机 AKEData 解包索引里的日历，SRA 只在索引还没有活动
  （或索引尚未同步）时补位，见 `WikiStore.calendar_outcomes`。
* 明日方舟另有本机解包游戏表（`app/tools/game_calendar_arknights.py`，Priestess-bot
  移植）作为第二降级：SRA 与缓存都取不到时才回退，且不因此上抛错误。
* 每个游戏各取各的、各存各的：一个游戏失败既不影响另一个游戏，也不会把整个请求
  变成错误；失败一律用「空列表 + 该游戏的 message」表达。

缓存
----
结果写在 wiki 数据目录下的 `calendar-<game>.json`（与索引同级，随用户删除本机数据
而消失），TTL 为 :data:`CACHE_TTL`。TTL 内直接用缓存；过期后先向上游取，取不到就
回落到「上次成功结果」并说明数据的时间，实在没有才返回空列表。

上游字段实测见 `app/tools/sra_activity.py` 的模块文档：`kind` 各游戏不一致（中文 /
英文枚举 / 缺失），封面缺失是常态，时间戳不带时区需要补 `+08:00`。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, Sequence

import httpx

from app.tools import sra_activity
from app.utils.atomic_io import atomic_write_text
from app.utils.constants import UTC8
from app.utils.logger import get_logger

logger = get_logger("活动日历")

__all__ = [
    "CACHE_SCHEMA",
    "CACHE_TTL",
    "CALENDAR_GAMES",
    "GAME_NAMES",
    "SRA_SOURCES",
    "STALE_MAX_SECONDS",
    "SUBTITLE_MAX",
    "CalendarOutcome",
    "aggregate",
    "cache_file",
    "clear_memory",
    "fetch",
    "load",
    "save",
    "status_text",
    "to_calendar_rows",
]

# 游戏枚举（API 契约）-> SRA 标识。顺序即 `/api/wiki/calendar-all` 的返回顺序。
SRA_SOURCES = {
    "endfield": "end",
    "arknights": "ak",
    "genshin": "ys",
    "starrail": "sr",
    "zenless": "zzz",
    "wutheringwaves": "ww",
    "nte": "nte",
    "stellasora": "xtlr",
    "infinitynikki": "infinitynikki",
}
CALENDAR_GAMES = tuple(SRA_SOURCES)
# 展示名用中文常量，避免界面语言变化影响数据标识（与 AUTO-MAS 的做法一致）。
GAME_NAMES = {
    "endfield": "明日方舟：终末地",
    "arknights": "明日方舟",
    "genshin": "原神",
    "starrail": "崩坏：星穹铁道",
    "zenless": "绝区零",
    "wutheringwaves": "鸣潮",
    "nte": "异环",
    "stellasora": "星塔旅人",
    "infinitynikki": "无限暖暖",
}
CACHE_SCHEMA = 1
CACHE_TTL = 30 * 60.0  # 30 分钟：SRA 是静态站，不必每次访问都回源
# 上游失败时最多兜底 24 小时。再旧的活动已经结束或与当前版本无关，继续展示比
# 「暂无数据」更误导：用户看到的是一份三周前的时间表。
STALE_MAX_SECONDS = 24 * 3600.0
SUBTITLE_MAX = 60  # subtitle 是描述摘要，超长按字符截断
# 进程内的缓存，避免同一进程内重复读盘（测试可用 clear_memory 复位）。
_MEMORY: dict[tuple[str, str], dict] = {}


class CalendarOutcome(NamedTuple):
    """单个游戏的结果：行、说明、来源与当前版本信息。

    ``source`` 是数据来源，供调用方与前端区分「刚取的」和「兜底的缓存」：
    ``sra``（刚取到）/ ``cache``（TTL 内的本机缓存）/ ``stale-cache``（上游失败，
    回落到上次成功结果）/ ``local``（本机解包索引）/ ``none``（没有任何数据）。
    """

    game: str
    rows: list[dict]
    message: str
    source: str = "none"
    version: str = ""
    version_name: str = ""
    cover: str = ""

    def contract(self) -> dict:
        """契约条目：每个游戏一份，失败时 data 为空、message 说明原因。"""
        return {
            "game": self.game,
            "name": GAME_NAMES.get(self.game, self.game),
            "source": self.source,
            "version": self.version,
            "versionName": self.version_name,
            "cover": self.cover,
            "activities": self.rows,
            "message": self.message,
        }


def cache_file(directory: Path, game: str) -> Path:
    """某个游戏的缓存文件；directory 由调用方给定（wiki 数据目录）。"""
    return Path(directory) / f"calendar-{game}.json"


def load(wiki_directory: Path, game: str) -> dict:
    """读取本机缓存；文件缺失或损坏时按空缓存处理。"""
    if game not in CALENDAR_GAMES:
        return {}
    key = (str(wiki_directory), game)
    cached = _MEMORY.get(key)
    if cached is None:
        cached = _read(cache_file(wiki_directory, game))
        _MEMORY[key] = cached
    return cached


def _read(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save(wiki_directory: Path, game: str, payload: dict) -> None:
    """写入缓存；磁盘出错只记日志，不影响本次结果。"""
    path = cache_file(wiki_directory, game)
    try:
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False))
    except OSError as error:
        logger.warning(f"活动日历缓存写入失败（{game}）：{type(error).__name__}")
        return
    _MEMORY[(str(wiki_directory), game)] = payload


def clear_memory() -> None:
    """清空进程内缓存；测试或手动刷新时使用。"""
    _MEMORY.clear()


def _usable(cached: dict, now: float) -> bool:
    """缓存结构正确且在 TTL 内才算可用。"""
    if cached.get("schema") != CACHE_SCHEMA or not isinstance(cached.get("activities"), list):
        return False
    fetched = cached.get("fetched")
    return isinstance(fetched, (int, float)) and now - float(fetched) < CACHE_TTL


def _age_text(seconds: float) -> str:
    """把缓存年龄说成人话：不到 1 分钟 / 23 分钟 / 5 小时 / 2 天。"""
    if seconds < 60:
        return "不到 1 分钟"
    if seconds < 3600:
        return f"{int(seconds // 60)} 分钟"
    if seconds < 86400:
        return f"{int(seconds // 3600)} 小时"
    return f"{int(seconds // 86400)} 天"


def _parse_moment(value: object) -> datetime | None:
    """ISO 串 -> 带时区的 datetime；解析不了返回 None。

    SRA 的时间已由 `sra_activity.beijing_time` 补上 `+08:00`；这里再兜一层：万一上游
    改成不带时区的形式，按北京时间理解，绝不让前端拿到裸时间。
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC8)


def status_text(
    starts: datetime | None, ends: datetime | None, now: float
) -> str:
    """日历行状态：进行中 / 即将开始 / 已结束 / 常驻。

    活动统一按限时处理，只有结束时间确实缺失时才落到「常驻」——实测 SRA 各游戏都
    有无结束时间的条目，不能因为上游漏了字段就把它当成常驻。
    """
    if starts is None and ends is None:
        return ""
    if starts is not None and starts.timestamp() > now:
        return "即将开始"
    if ends is None:
        return "常驻"
    return "进行中" if now < ends.timestamp() else "已结束"


def _subtitle(description: object, kind: object) -> str:
    """subtitle 放描述摘要：压缩空白、超长截断；描述为空时退回上游分类。

    `kind` 实测各游戏不一致（end 中文、ak 中英混用、ww 根本没有），所以只作展示，
    不参与任何判断，也不做必填校验。
    """
    text = re.sub(r"\s+", " ", str(description or "")).strip()
    if len(text) > SUBTITLE_MAX:
        text = text[:SUBTITLE_MAX].rstrip() + "…"
    return text or str(kind or "").strip()


def to_calendar_rows(game: str, payload: dict, now: float | None = None) -> list[dict]:
    """缓存或上游结果 -> 日历行（契约字段，camelCase）。"""
    moment = time.time() if now is None else now
    rows = []
    for item in payload.get("activities") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("name") or "").strip()
        if not title:
            continue
        starts = _parse_moment(item.get("startTime"))
        ends = _parse_moment(item.get("endTime"))
        rows.append(
            {
                "game": game,
                "kind": "activity",
                "title": title,
                "subtitle": _subtitle(item.get("description"), item.get("kind")),
                "startsAt": starts.isoformat(timespec="seconds") if starts else "",
                "endsAt": ends.isoformat(timespec="seconds") if ends else "",
                # 实测封面缺失是常态（xtlr 5 条全无、end 14 条缺 5……），空串合法。
                "banner": str(item.get("cover") or ""),
                "status": status_text(starts, ends, moment),
            }
        )
    return sorted(rows, key=lambda row: (row["startsAt"], row["title"]))


def _outcome(
    game: str, payload: dict, source: str, message: str, now: float | None = None
) -> CalendarOutcome:
    return CalendarOutcome(
        game=game,
        # 状态文案必须与缓存判定用同一个时刻，否则注入的 now 只影响 TTL。
        rows=to_calendar_rows(game, payload, now),
        message=message,
        source=source,
        version=str(payload.get("version") or ""),
        version_name=str(payload.get("versionName") or ""),
        cover=str(payload.get("cover") or ""),
    )


async def fetch(
    game: str,
    wiki_directory: Path,
    transport: httpx.AsyncBaseTransport | None = None,
    now: float | None = None,
) -> CalendarOutcome:
    """取一个游戏的活动：TTL 缓存 -> SRA -> 上次成功结果。

    任何失败都不上抛：到手的缓存仍然返回，并在 message 里说明；两条路都没有时返回
    空列表与一句可读的原因。
    """
    if game not in CALENDAR_GAMES:
        raise ValueError(f"不支持的日历：{game}")
    moment = time.time() if now is None else now
    cached = load(wiki_directory, game)
    if _usable(cached, moment):
        age = _age_text(moment - float(cached["fetched"]))
        return _outcome(game, cached, "cache", f"本机缓存（{age}前）", moment)
    data = await sra_activity.fetch_activities(SRA_SOURCES[game], transport=transport)
    if data is not None:
        payload = {
            "schema": CACHE_SCHEMA,
            "game": game,
            "source": "sra",
            "fetched": moment,
            **data,
        }
        save(wiki_directory, game, payload)
        message = f"已从 SRA 更新 {len(data['activities'])} 条"
        if data.get("versionName"):
            message += f"（当前版本 {data['versionName']}）"
        return _outcome(game, data, "sra", message, moment)
    # 只有结构正确的缓存才配叫"上次成功结果"：旧格式或损坏的文件不在此列。
    if cached.get("schema") == CACHE_SCHEMA and isinstance(cached.get("activities"), list):
        fetched = cached.get("fetched")
        age_seconds = moment - float(fetched) if isinstance(fetched, (int, float)) else None
        if age_seconds is not None and 0 <= age_seconds <= STALE_MAX_SECONDS:
            age = _age_text(age_seconds)
            return _outcome(
                game,
                cached,
                "stale-cache",
                f"SRA 暂不可用，显示上次成功获取的数据（{age}前）",
                moment,
            )
        if age_seconds is not None and age_seconds > STALE_MAX_SECONDS:
            age = _age_text(age_seconds)
            return CalendarOutcome(
                game,
                [],
                f"SRA 暂不可用，上次成功数据已是 {age}前，超过 24 小时不再展示",
                "none",
            )
    return CalendarOutcome(game, [], "SRA 暂不可用，稍后重试", "none")


async def aggregate(
    games: Sequence[str],
    wiki_directory: Path,
    transport: httpx.AsyncBaseTransport | None = None,
    now: float | None = None,
) -> list[CalendarOutcome]:
    """并发取多个游戏；各游戏的失败互相隔离，顺序与 games 一致。"""
    return list(
        await asyncio.gather(
            *(
                fetch(game, wiki_directory, transport=transport, now=now)
                for game in games
            )
        )
    )
